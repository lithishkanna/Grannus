import logging
import numpy as np
import scipy.signal
from app.schemas import AcousticBiomarkerResult

logger = logging.getLogger("rural_care.acoustic_biomarkers")

def analyze_audio(audio_data: np.ndarray, sample_rate: int) -> AcousticBiomarkerResult:
    """
    Analyzes raw audio for acoustic biomarkers:
    - Cough Detection
    - Wheeze Detection
    - Breathlessness Score
    """
    if len(audio_data) == 0:
        return AcousticBiomarkerResult(
            is_experimental=True,
            cough_count=0,
            cough_rate=0.0,
            wheeze_detected=False,
            wheeze_ratio=0.0,
            breathlessness_pauses=0,
            speech_dyspnea_index=0.0,
            respiratory_distress_score=0.0,
            distress_level='none'
        )

    # Convert to mono if necessary
    if audio_data.ndim > 1:
        audio_data = audio_data.mean(axis=1)

    # Normalize audio
    max_val = np.max(np.abs(audio_data))
    if max_val > 0:
        audio_data = audio_data / max_val

    duration = len(audio_data) / sample_rate
    
    # 1. Cough Detection
    # Short high-energy transients
    frame_length = int(0.05 * sample_rate) # 50ms
    hop_length = int(0.025 * sample_rate) # 25ms
    
    # Compute RMS energy in frames
    num_frames = (len(audio_data) - frame_length) // hop_length + 1
    if num_frames <= 0:
        return AcousticBiomarkerResult(
            is_experimental=True,
            cough_count=0,
            cough_rate=0.0,
            wheeze_detected=False,
            wheeze_ratio=0.0,
            breathlessness_pauses=0,
            speech_dyspnea_index=0.0,
            respiratory_distress_score=0.0,
            distress_level='none'
        )

    rms_energy = np.zeros(num_frames)
    for i in range(num_frames):
        start = i * hop_length
        end = start + frame_length
        rms_energy[i] = np.sqrt(np.mean(audio_data[start:end]**2))
        
    median_energy = np.median(rms_energy)
    if median_energy < 1e-10:
        threshold = 0.01
    else:
        threshold = 3 * median_energy
    
    peaks, _ = scipy.signal.find_peaks(rms_energy, height=threshold, distance=int(0.3 / 0.025))
    cough_count = len(peaks)
    cough_rate = cough_count / (duration / 60.0) if duration > 0 else 0.0
    
    # 2. Wheeze Detection
    f, t, Sxx = scipy.signal.spectrogram(audio_data, fs=sample_rate, nperseg=int(0.05*sample_rate), noverlap=int(0.025*sample_rate))
    
    # Wheezing frequency: 200-800Hz
    wheeze_band = (f >= 200) & (f <= 800)
    
    if np.sum(Sxx) > 0 and np.any(wheeze_band):
        Sxx_wheeze = Sxx[wheeze_band, :]
        arith_mean = np.mean(Sxx_wheeze, axis=0)
        eps = 1e-10
        geo_mean = np.exp(np.mean(np.log(Sxx_wheeze + eps), axis=0))
        flatness = np.divide(geo_mean, arith_mean, out=np.zeros_like(arith_mean), where=arith_mean>eps)
        
        # significant energy in wheeze band
        wheeze_energy = np.sum(Sxx_wheeze, axis=0)
        total_energy_per_frame = np.sum(Sxx, axis=0)
        significant_energy = wheeze_energy > (0.01 * np.max(total_energy_per_frame))
        
        tonal_frames = (flatness < 0.3) & significant_energy & (arith_mean > eps)
        wheeze_ratio = float(np.mean(tonal_frames))
    else:
        wheeze_ratio = 0.0
        
    wheeze_detected = wheeze_ratio > 0.15
    
    # 3. Breathlessness Score
    # Pauses > 1.5 seconds
    pause_threshold = median_energy * 0.5
    is_pause_raw = rms_energy < pause_threshold
    
    # Trim leading and trailing silence
    speech_frames = np.where(rms_energy > (median_energy * 0.3))[0]
    if len(speech_frames) > 0:
        start_idx = speech_frames[0]
        end_idx = speech_frames[-1]
        is_pause = is_pause_raw[start_idx:end_idx + 1]
    else:
        is_pause = np.array([])
    
    # Find contiguous pause segments
    breathlessness_pauses = 0
    total_pause_duration = 0.0
    
    current_pause_frames = 0
    for p in is_pause:
        if p:
            current_pause_frames += 1
        else:
            if current_pause_frames * 0.025 > 1.5:
                breathlessness_pauses += 1
                total_pause_duration += current_pause_frames * 0.025
            current_pause_frames = 0
            
    if current_pause_frames * 0.025 > 1.5:
        breathlessness_pauses += 1
        total_pause_duration += current_pause_frames * 0.025
        
    speech_dyspnea_index = total_pause_duration / duration if duration > 0 else 0.0
    
    # 4. Overall Respiratory Distress Score
    # Normalize cough count: use cough_rate, max 20
    norm_cough = min(cough_rate / 20.0, 1.0)
    norm_wheeze = min(wheeze_ratio / 0.5, 1.0) # max out at 50% ratio
    norm_dyspnea = min(speech_dyspnea_index / 0.5, 1.0)
    
    respiratory_distress_score = (norm_cough + norm_wheeze + norm_dyspnea) / 3.0
    
    if respiratory_distress_score < 0.2:
        distress_level = 'none'
    elif respiratory_distress_score < 0.4:
        distress_level = 'mild'
    elif respiratory_distress_score < 0.6:
        distress_level = 'moderate'
    else:
        distress_level = 'severe'
        
    logger.info(f"Acoustic biomarkers computed: score={respiratory_distress_score:.2f}, level={distress_level}")

    return AcousticBiomarkerResult(
        is_experimental=True,
        cough_count=cough_count,
        cough_rate=cough_rate,
        wheeze_detected=wheeze_detected,
        wheeze_ratio=float(wheeze_ratio),
        breathlessness_pauses=breathlessness_pauses,
        speech_dyspnea_index=float(speech_dyspnea_index),
        respiratory_distress_score=float(respiratory_distress_score),
        distress_level=distress_level
    )
