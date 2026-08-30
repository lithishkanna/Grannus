import io
import logging
import numpy as np
import scipy.signal
import scipy.io.wavfile as wavfile
import soundfile as sf

from app.schemas import AudioPreprocessingResult
from app.config import get_settings

logger = logging.getLogger('rural_care.audio_preprocessing')

class AudioPreprocessingError(Exception):
    """Base exception for audio preprocessing errors."""
    pass

class AudioTooShortError(AudioPreprocessingError):
    pass

class AudioTooLongError(AudioPreprocessingError):
    pass

class AudioFormatError(AudioPreprocessingError):
    pass

def _rms_energy(y: np.ndarray, frame_length: int, hop_length: int) -> np.ndarray:
    """Calculate RMS energy of frames."""
    if len(y) < frame_length:
        return np.array([np.sqrt(np.mean(y**2))])
    num_frames = (len(y) - frame_length) // hop_length + 1
    # Ensure contiguous array for stride tricks
    y = np.ascontiguousarray(y)
    shape = (num_frames, frame_length)
    strides = (y.itemsize * hop_length, y.itemsize)
    frames = np.lib.stride_tricks.as_strided(y, shape=shape, strides=strides)
    return np.sqrt(np.mean(frames**2, axis=1))

def preprocess_audio(audio_bytes: bytes, filename: str) -> tuple[bytes, AudioPreprocessingResult]:
    """
    Preprocess audio for Sarvam STT.
    Steps:
      1. Load audio
      2. Duration validation
      3. Mono conversion
      4. Resample to 16kHz
      5. Silence trimming
      6. Noise reduction
      7. Volume normalization
      8. Quality assessment
      9. Export to WAV 16-bit PCM
    """
    settings = get_settings()
    
    if not settings.enable_audio_preprocessing:
        logger.info("Audio preprocessing is disabled by settings.")
        return audio_bytes, AudioPreprocessingResult(
            original_duration_seconds=0.0,
            processed_duration_seconds=0.0,
            original_sample_rate=0,
            noise_reduced=False,
            volume_normalized=False,
            silence_trimmed=False,
            format_converted=False,
            quality_warning="Preprocessing disabled"
        )

    ext = filename.split('.')[-1].lower() if '.' in filename else ''
    
    # 1. Load audio
    audio_data = None
    sample_rate = None
    
    try:
        audio_data, sample_rate = sf.read(io.BytesIO(audio_bytes))
    except Exception as e:
        if ext == 'wav':
            try:
                sample_rate, audio_data = wavfile.read(io.BytesIO(audio_bytes))
                # Normalize integer PCM to float
                if np.issubdtype(audio_data.dtype, np.integer):
                    max_val = np.iinfo(audio_data.dtype).max
                    audio_data = audio_data.astype(np.float32) / max_val
                else:
                    audio_data = audio_data.astype(np.float32)
            except Exception as e2:
                logger.error(f"Failed to load WAV with scipy: {e2}")
                raise AudioFormatError(f"Failed to load WAV audio file: {e2}")
        else:
            logger.warning(f"Could not load audio file {filename} with soundfile: {e}")
            return audio_bytes, AudioPreprocessingResult(
                original_duration_seconds=0.0,
                processed_duration_seconds=0.0,
                original_sample_rate=0,
                quality_warning="format conversion skipped"
            )

    original_sample_rate = sample_rate
    original_duration = len(audio_data) / sample_rate

    # 3. Validate duration
    if original_duration < settings.min_audio_duration_seconds:
        msg = f"Audio duration {original_duration:.2f}s is shorter than minimum {settings.min_audio_duration_seconds}s."
        logger.error(msg)
        raise AudioTooShortError(msg)
    if original_duration > settings.max_audio_duration_seconds:
        msg = f"Audio duration {original_duration:.2f}s is longer than maximum {settings.max_audio_duration_seconds}s."
        logger.error(msg)
        raise AudioTooLongError(msg)

    # 4. Convert to mono
    if len(audio_data.shape) > 1 and audio_data.shape[1] > 1:
        audio_data = np.mean(audio_data, axis=1)
        
    format_converted = (ext != 'wav') or (original_sample_rate != settings.target_sample_rate)

    # 5. Resample to 16kHz
    if sample_rate != settings.target_sample_rate:
        num_samples = int(len(audio_data) * (settings.target_sample_rate / sample_rate))
        audio_data = scipy.signal.resample(audio_data, num_samples)
        sample_rate = settings.target_sample_rate

    # 6. Silence trimming
    frame_length = int(sample_rate * 0.02)  # 20ms
    hop_length = int(sample_rate * 0.01)    # 10ms
    threshold = 0.01
    
    rms = _rms_energy(audio_data, frame_length, hop_length)
    mask = rms > threshold
    
    silence_trimmed = False
    if np.any(mask):
        first_idx = np.argmax(mask)
        last_idx = len(mask) - 1 - np.argmax(mask[::-1])
        
        start_sample = first_idx * hop_length
        end_sample = last_idx * hop_length + frame_length
        
        padding = int(sample_rate * 0.1)  # 100ms
        start_sample = max(0, start_sample - padding)
        end_sample = min(len(audio_data), end_sample + padding)
        
        if start_sample > 0 or end_sample < len(audio_data):
            audio_data = audio_data[start_sample:end_sample]
            silence_trimmed = True
            
    processed_duration = len(audio_data) / sample_rate
    if processed_duration < settings.min_audio_duration_seconds:
        msg = f"Processed audio duration {processed_duration:.2f}s is too short after trimming."
        logger.error(msg)
        raise AudioTooShortError(msg)

    # 7. Noise reduction
    noise_reduced = False
    if settings.noise_reduction_strength > 0:
        try:
            import noisereduce as nr
            audio_data = nr.reduce_noise(y=audio_data, sr=sample_rate, prop_decrease=settings.noise_reduction_strength)
            noise_reduced = True
        except ImportError:
            logger.warning("noisereduce not installed, skipping noise reduction")
        except Exception as e:
            logger.warning(f"Noise reduction failed, skipping: {e}")

    # 8. Volume normalization
    max_val = np.max(np.abs(audio_data))
    volume_normalized = False
    if max_val > 0:
        audio_data = (audio_data / max_val) * 0.9
        volume_normalized = True

    # 9. Quality assessment
    rms_signal = np.sqrt(np.mean(audio_data**2))
    rms_frames = _rms_energy(audio_data, frame_length, hop_length)
    if len(rms_frames) > 0:
        noise_est = np.percentile(rms_frames, 10)
        snr = 20 * np.log10(rms_signal / (noise_est + 1e-6))
    else:
        snr = 0
        
    quality_warning = None
    if snr < 10:
        quality_warning = "Low signal-to-noise ratio"

    # 10. Export to WAV 16-bit PCM
    out_io = io.BytesIO()
    sf.write(out_io, audio_data, sample_rate, format='WAV', subtype='PCM_16')
    processed_bytes = out_io.getvalue()

    return processed_bytes, AudioPreprocessingResult(
        original_duration_seconds=original_duration,
        processed_duration_seconds=processed_duration,
        original_sample_rate=original_sample_rate,
        noise_reduced=noise_reduced,
        volume_normalized=volume_normalized,
        silence_trimmed=silence_trimmed,
        format_converted=format_converted,
        quality_warning=quality_warning
    )
