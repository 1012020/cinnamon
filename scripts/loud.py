from pydub import AudioSegment
import pyloudnorm as pyln
import numpy as np
from scipy import signal
import sys
import os

def maximize_loudness(input_file, output_file=None):
    """
    Maximize loudness to absolute maximum without any clipping.
    Uses multi-stage processing for maximum loudness.
    """
    # Load the audio file
    print(f"Loading {input_file}...")
    audio = AudioSegment.from_ogg(input_file)
    
    # Convert to numpy array for processing
    samples = np.array(audio.get_array_of_samples()).astype(np.float64)
    
    # Handle stereo
    if audio.channels == 2:
        samples = samples.reshape((-1, 2))
    
    # Normalize to [-1, 1] range
    samples = samples / (2**15)  # 16-bit audio
    
    print(f"Original peak: {np.max(np.abs(samples)):.6f}")
    
    # Stage 1: LUFS normalization to very loud level
    meter = pyln.Meter(audio.frame_rate)
    current_loudness = meter.integrated_loudness(samples)
    print(f"Current loudness: {current_loudness:.2f} LUFS")
    
    # Normalize to extremely loud LUFS target
    target_lufs = -3.0  # Ridiculously loud
    print(f"Normalizing to {target_lufs:.2f} LUFS...")
    samples = pyln.normalize.loudness(samples, current_loudness, target_lufs)
    
    # Stage 2: Soft clipper to shave peaks (increases RMS without hard clipping)
    print("Applying soft clipping...")
    samples = soft_clip(samples, threshold=0.7)
    
    # Stage 3: Multi-band compression for even distribution
    print("Applying multi-band compression...")
    samples = multiband_compress(samples, audio.frame_rate)
    
    # Stage 4: Multiple passes of limiting for maximum density
    print("Applying multi-stage limiting...")
    samples = brickwall_limiter(samples, threshold=0.95, attack_samples=5, release_samples=50)
    samples = brickwall_limiter(samples, threshold=0.97, attack_samples=8, release_samples=80)
    samples = brickwall_limiter(samples, threshold=0.99, attack_samples=10, release_samples=100)
    
    # Stage 4: Final peak normalization to absolute maximum
    print("Final peak normalization...")
    peak = np.max(np.abs(samples))
    if peak > 0:
        # Scale to 0.999 to avoid any possible clipping
        samples = samples * (0.999 / peak)
    
    # Measure final stats
    final_loudness = meter.integrated_loudness(samples)
    final_peak = np.max(np.abs(samples))
    final_rms = np.sqrt(np.mean(samples**2))
    
    print(f"\n=== FINAL STATS ===")
    print(f"Final loudness: {final_loudness:.2f} LUFS")
    print(f"Final peak: {final_peak:.6f} ({20*np.log10(final_peak):.2f} dBFS)")
    print(f"Final RMS: {final_rms:.6f} ({20*np.log10(final_rms):.2f} dBFS)")
    print(f"Crest factor: {20*np.log10(final_peak/final_rms):.2f} dB")
    
    # Check for clipping
    clipped_samples = np.sum(np.abs(samples) >= 1.0)
    print(f"Clipped samples: {clipped_samples} (should be 0)")
    
    # Convert back to 16-bit integer
    samples = np.clip(samples, -1.0, 1.0)  # Safety clip
    samples = (samples * 32767).astype(np.int16)
    
    # Convert back to AudioSegment
    if audio.channels == 2:
        samples = samples.flatten()
    
    result = AudioSegment(
        samples.tobytes(),
        frame_rate=audio.frame_rate,
        sample_width=2,
        channels=audio.channels
    )
    
    # Set output filename
    if output_file is None:
        base, ext = os.path.splitext(input_file)
        output_file = f"{base}_maximized{ext}"
    
    # Export with high quality settings
    print(f"\nExporting to {output_file}...")
    result.export(output_file, format="ogg", codec="libvorbis", 
                  parameters=["-q:a", "10"])  # Quality 10 (highest)
    
    print("Done! Audio maximized to absolute loudness without clipping.")
    return output_file

def soft_clip(audio, threshold=0.7):
    """
    Soft clipping to reduce peaks while maintaining RMS loudness.
    This allows more headroom for overall loudness increase.
    """
    # Hyperbolic tangent soft clipping
    # Smoothly compresses signals above threshold
    output = np.copy(audio)
    
    mask = np.abs(audio) > threshold
    
    # Apply soft clipping formula
    sign = np.sign(audio[mask])
    magnitude = np.abs(audio[mask])
    
    # Smooth saturation curve
    clipped = threshold + (1 - threshold) * np.tanh((magnitude - threshold) / (1 - threshold))
    output[mask] = sign * clipped
    
    return output

def multiband_compress(audio, sr, bands=3):
    """
    Apply compression to different frequency bands for more even loudness.
    """
    if len(audio.shape) == 1:
        audio = audio.reshape(-1, 1)
    
    # Define frequency bands (low, mid, high)
    if bands == 3:
        freqs = [250, 2000]  # Crossover frequencies
    else:
        freqs = [250]
    
    # Design filters
    nyquist = sr / 2
    
    # Simple approach: compress each channel
    result = np.zeros_like(audio)
    
    for ch in range(audio.shape[1]):
        channel = audio[:, ch]
        
        # Low band
        sos_low = signal.butter(4, freqs[0] / nyquist, btype='low', output='sos')
        low = signal.sosfilt(sos_low, channel)
        low = compress(low, threshold=0.25, ratio=8.0)
        
        # High band
        sos_high = signal.butter(4, freqs[-1] / nyquist, btype='high', output='sos')
        high = signal.sosfilt(sos_high, channel)
        high = compress(high, threshold=0.25, ratio=8.0)
        
        if bands == 3:
            # Mid band
            sos_mid = signal.butter(4, [freqs[0] / nyquist, freqs[1] / nyquist], btype='band', output='sos')
            mid = signal.sosfilt(sos_mid, channel)
            mid = compress(mid, threshold=0.25, ratio=8.0)
            result[:, ch] = low + mid + high
        else:
            result[:, ch] = low + high
    
    if result.shape[1] == 1:
        result = result.flatten()
    
    return result

def compress(audio, threshold=0.4, ratio=6.0, attack=0.003, release=0.08):
    """
    Apply aggressive dynamic range compression.
    """
    output = np.copy(audio)
    envelope = np.abs(audio)
    
    # Simple envelope follower
    alpha_attack = 1.0 - np.exp(-1.0 / (attack * 44100))
    alpha_release = 1.0 - np.exp(-1.0 / (release * 44100))
    
    env_smooth = 0.0
    for i in range(len(envelope)):
        if envelope[i] > env_smooth:
            env_smooth = alpha_attack * envelope[i] + (1 - alpha_attack) * env_smooth
        else:
            env_smooth = alpha_release * envelope[i] + (1 - alpha_release) * env_smooth
        
        if env_smooth > threshold:
            # Calculate gain reduction
            excess = env_smooth - threshold
            gain = 1.0 - (excess * (1.0 - 1.0/ratio))
            output[i] *= gain
    
    return output

def brickwall_limiter(audio, threshold=0.99, attack_samples=10, release_samples=100):
    """
    Brick-wall limiter with look-ahead to prevent any clipping.
    """
    if len(audio.shape) == 1:
        audio = audio.reshape(-1, 1)
    
    output = np.copy(audio)
    
    for ch in range(audio.shape[1]):
        channel = audio[:, ch]
        gain = np.ones(len(channel))
        
        # Look-ahead buffer
        for i in range(attack_samples, len(channel)):
            # Check future samples
            future_peak = np.max(np.abs(channel[i:i+attack_samples]))
            
            if future_peak > threshold:
                # Calculate required gain reduction
                required_gain = threshold / future_peak
                gain[i] = min(gain[i], required_gain)
        
        # Smooth gain reduction
        for i in range(1, len(gain)):
            if gain[i] < gain[i-1]:
                # Attack
                gain[i] = max(gain[i], gain[i-1] - 1.0/attack_samples)
            else:
                # Release
                gain[i] = min(1.0, gain[i-1] + 1.0/release_samples)
        
        output[:, ch] = channel * gain
    
    if output.shape[1] == 1:
        output = output.flatten()
    
    return output

if __name__ == "__main__":
    input_file = "assets/cinnamon.ogg"
    output_file = None
    
    # Parse arguments if provided
    if len(sys.argv) > 1:
        for i in range(1, len(sys.argv)):
            if sys.argv[i] == "--output" and i + 1 < len(sys.argv):
                output_file = sys.argv[i + 1]
    
    if not os.path.exists(input_file):
        print(f"Error: File '{input_file}' not found!")
        print(f"Please ensure 'assets/cinnamon.ogg' exists.")
        sys.exit(1)
    
    maximize_loudness(input_file, output_file)
