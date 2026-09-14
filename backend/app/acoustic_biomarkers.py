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
            cough_count=0,
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
    rms_energy = np.zeros(num_frames)
    for i in range(num_frames):
        start = i * hop_length
        end = start + frame_length
        rms_energy[i] = np.sqrt(np.mean(audio_data[start:end]**2))
        
    median_energy = np.median(rms_energy)
    threshold = 3 * median_energy
    
    peaks, _ = scipy.signal.find_peaks(rms_energy, height=threshold, distance=int(0.3 / 0.025))
    cough_count = len(peaks)
    
    # 2. Wheeze Detection
    # Use scipy.signal.spectrogram
    f, t, Sxx = scipy.signal.spectrogram(audio_data, fs=sample_rate, nperseg=int(0.05*sample_rate), noverlap=int(0.025*sample_rate))
    
    # Wheezing frequency: 100-500Hz
    wheeze_band = (f >= 100) & (f <= 500)
    
    if np.sum(Sxx) > 0:
        wheeze_energy = np.sum(Sxx[wheeze_band, :], axis=0)
        total_energy = np.sum(Sxx, axis=0)
        
        # Avoid division by zero
        ratio_frames = np.divide(wheeze_energy, total_energy, out=np.zeros_like(wheeze_energy), where=total_energy!=0)
        wheeze_ratio = float(np.mean(ratio_frames))
    else:
        wheeze_ratio = 0.0
        
    wheeze_detected = wheeze_ratio > 0.2
    
    # 3. Breathlessness Score
    # Pauses > 1.5 seconds
    pause_threshold = median_energy * 0.5
    is_pause = rms_energy < pause_threshold
    
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
    # Normalize cough count: assume 10 is max
    norm_cough = min(cough_count / 10.0, 1.0)
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
        cough_count=cough_count,
        wheeze_detected=wheeze_detected,
        wheeze_ratio=float(wheeze_ratio),
        breathlessness_pauses=breathlessness_pauses,
        speech_dyspnea_index=float(speech_dyspnea_index),
        respiratory_distress_score=float(respiratory_distress_score),
        distress_level=distress_level
    )
