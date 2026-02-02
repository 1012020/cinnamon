import io
import struct
import os
import uuid
import random
import subprocess
import json
import tempfile
from pydub import AudioSegment
import config
from cogs.utils.helpers import ASSET_CACHE
import numpy as np
import soundfile as sf
import pyloudnorm as pyln
from scipy.signal import butter, lfilter
from PIL import Image
from PIL.PngImagePlugin import PngInfo

def process_intro(main_path, intro_path, output_path, export_format):
    main = AudioSegment.from_file(main_path)
    intro = AudioSegment.from_file(intro_path)
    combined = intro + main
    combined.export(output_path, format=export_format)

def process_32mono(input_path, output_file, bait_path, add_watermark=True):
    SLOWDOWN_FACTOR = 4.0
    HIGH_QUALITY_RATE = 176400
    input_segment = AudioSegment.from_file(input_path)
    if add_watermark:
        cinnamon_segment = ASSET_CACHE.get("cinnamon_seg")
        if not cinnamon_segment:
            cinnamon_segment = AudioSegment.from_file(config.CINNAMON_FILE)
        audio = cinnamon_segment + input_segment
    else:
        audio = input_segment
    audio_high_res = audio.set_frame_rate(HIGH_QUALITY_RATE)
    new_slow_rate = int(HIGH_QUALITY_RATE / SLOWDOWN_FACTOR)
    audio_slowed = audio_high_res._spawn(
        audio_high_res.raw_data,
        overrides={"frame_rate": new_slow_rate}
    )
    middle_buffer = io.BytesIO()
    audio_slowed.export(
        middle_buffer, 
        format="ogg", 
        parameters=["-ar", str(HIGH_QUALITY_RATE)] 
    )
    middle_bytes = middle_buffer.getvalue()
    head_bytes = ASSET_CACHE.get("head")
    if not head_bytes:
        with open(config.PREFIX_FILE, "rb") as f: head_bytes = f.read()
    with open(bait_path, "rb") as f:
        tail_bytes = f.read()
    with open(output_file, "wb") as out_f:
        out_f.write(head_bytes)
        out_f.write(middle_bytes)
        out_f.write(tail_bytes)

def process_compression(input_path, output_path):
    """Compress file size significantly while maintaining good quality."""
    audio = AudioSegment.from_file(input_path)
    
    # Get file extension to determine output format
    ext = output_path.split('.')[-1].lower()
    
    # Use moderate compression for significant file size reduction
    if ext == "mp3":
        # Use 96kbps CBR for good quality and small size
        audio.export(output_path, format="mp3", bitrate="96k")
    elif ext == "ogg":
        # Use quality level 0 for more compression
        audio.export(output_path, format="ogg", parameters=["-q:a", "0"])
    elif ext == "m4a":
        # Use 96kbps AAC
        audio.export(output_path, format="ipod", bitrate="96k")
    else:
        # Default: convert to mp3 at 96kbps
        audio.export(output_path, format="mp3", bitrate="96k")

def process_loud(input_path, output_path, export_format):
    audio = AudioSegment.from_file(input_path)
    if audio.channels < 2: audio = audio.set_channels(2)
    (audio + 300).export(output_path, format=export_format)

def process_2db(input_path, output_path, export_format):
    audio = AudioSegment.from_file(input_path)
    audio = audio.high_pass_filter(10)
    peak = audio.max_dBFS
    target = -2.0
    gain_needed = target - peak
    audio = audio.apply_gain(gain_needed)
    # Optimization: Single pass with safety margin for compression artifacts
    # Instead of re-encoding 3 times, we target slightly lower to be safe.
    if export_format in ["mp3", "ogg"]:
        audio = audio.apply_gain(-0.5) # Extra headroom for lossy formats
    audio.export(output_path, format=export_format)

def process_nobass(input_path, output_path, export_format):
    audio = AudioSegment.from_file(input_path)
    (audio.high_pass_filter(300) + 4).export(output_path, format=export_format)

def process_create_channels(input_path, output_path, num_channels):
    """Create multi-channel audio by duplicating the input into specified number of channels."""
    audio = AudioSegment.from_file(input_path)
    
    # Convert to mono first to ensure consistent source
    if audio.channels > 1:
        audio = audio.set_channels(1)
    
    # Get raw audio data
    samples = np.array(audio.get_array_of_samples())
    
    # Create multi-channel array by duplicating samples
    multi_channel = np.tile(samples, (num_channels, 1)).T
    
    # Export using soundfile for multi-channel support
    import soundfile as sf
    sf.write(output_path, multi_channel, audio.frame_rate, format='OGG', subtype='VORBIS')

def process_convert(input_path, output_path, export_fmt):
    audio = AudioSegment.from_file(input_path)
    audio.export(output_path, format=export_fmt)

def process_max_channels(in_p, original_name):
    from cogs.utils.helpers import clean_filename # Local import to avoid circular
    source_audio = AudioSegment.from_file(in_p)
    # Optimization: Use source directly, downsample in memory if needed to save space
    base_audio = source_audio.set_frame_rate(22050) # Lower sample rate to save space for more channels
    source_tracks = base_audio.split_to_mono() if base_audio.channels >= 2 else [base_audio]
    best_channels = 1
    current_channels = 2
    clean_name = clean_filename(original_name)
    final_out_path = f"{clean_name}_dense.ogg"
    while current_channels <= config.MAX_CHANNELS_LIMIT:
        channels_list = [source_tracks[i % len(source_tracks)] for i in range(current_channels)]
        test_audio = AudioSegment.from_mono_audiosegments(*channels_list)
        buf = io.BytesIO()
        test_audio.export(buf, format="ogg", codec="libvorbis", parameters=["-ac", str(current_channels), "-qscale:a", "10"])
        size_mb = buf.getbuffer().nbytes / (1024 * 1024)
        if size_mb < config.TARGET_SIZE_MB:
            best_channels = current_channels
            if current_channels * 2 > config.MAX_CHANNELS_LIMIT: break
            current_channels *= 2
        else:
            break 
    final_list = [source_tracks[i % len(source_tracks)] for i in range(best_channels)]
    final_audio = AudioSegment.from_mono_audiosegments(*final_list)
    final_audio.export(final_out_path, format="ogg", codec="libvorbis", parameters=["-ac", str(best_channels), "-qscale:a", "10"])
    return final_out_path, best_channels

def calc_ogg_crc(data):
    crc_table = [0] * 256
    for i in range(256):
        r = i << 24
        for _ in range(8):
            r = (r << 1) ^ 0x04c11db7 if r & 0x80000000 else r << 1
        crc_table[i] = r & 0xffffffff
    crc = 0
    for byte in data:
        crc = (crc << 8) ^ crc_table[((crc >> 24) ^ byte) & 0xff]
    return crc & 0xffffffff

def get_pages(data_bytes, new_serial):
    pages = []
    offset = 0
    while offset < len(data_bytes):
        if data_bytes[offset:offset+4] == b'OggS':
            segments = data_bytes[offset+26]
            p_size = 27 + segments + sum(data_bytes[offset+27:offset+27+segments])
            page = bytearray(data_bytes[offset:offset+p_size])
            struct.pack_into('<I', page, 14, new_serial)
            pages.append(page)
            offset += p_size
        else:
            offset += 1
    return pages

def write_page(page, seq, force_type=None, clear_eos=False):
    new_page = bytearray(page)
    struct.pack_into('<I', new_page, 18, seq)
    if force_type is not None: 
        new_page[5] = force_type
    if clear_eos:
        new_page[5] &= ~0x04 
    struct.pack_into('<I', new_page, 22, 0)
    struct.pack_into('<I', new_page, 22, calc_ogg_crc(new_page))
    return new_page

def process_fullbait(input_path, output_file, bait_path, add_watermark=True):
    SERIAL_A = 0x0000737E
    SERIAL_B = 0x000056B4
    HIGH_RATE = 176400
    SLOW_RATE = 44100

    seg_payload = AudioSegment.from_file(input_path)
    if add_watermark:
        cinnamon_segment = ASSET_CACHE.get("cinnamon_seg")
        if not cinnamon_segment:
            cinnamon_segment = AudioSegment.from_file(config.CINNAMON_FILE)
        combined = cinnamon_segment + seg_payload
    else:
        combined = seg_payload
    
    combined_high = combined.set_frame_rate(HIGH_RATE)
    audio_slowed = combined_high._spawn(combined_high.raw_data, overrides={"frame_rate": SLOW_RATE})

    buffer_a = io.BytesIO()
    audio_slowed.export(buffer_a, format="ogg", parameters=["-ar", str(HIGH_RATE)])
    stream_a_bytes = buffer_a.getvalue()

    with open(bait_path, "rb") as f:
        stream_b_bytes = f.read()

    p_a = get_pages(stream_a_bytes, SERIAL_A)
    p_b = get_pages(stream_b_bytes, SERIAL_B)

    final_data = bytearray()
    for i in range(3):
        if i < len(p_b): final_data.extend(write_page(p_b[i], i, clear_eos=True))
    final_data.extend(write_page(p_b[0], 0, force_type=0x02)) 
    final_data.extend(write_page(p_a[0], 0, force_type=0x02))
    for i in range(1, len(p_a)): final_data.extend(write_page(p_a[i], i, clear_eos=True))
    final_data.extend(b'\x0D\x20')
    b_seq = 3
    for i in range(3, len(p_b)):
        is_last = (i == len(p_b) - 1)
        flag = 0x04 if is_last else 0x00
        final_data.extend(write_page(p_b[i], b_seq, force_type=flag))
        b_seq += 1

    with open(output_file, "wb") as f:
        f.write(final_data)

def butter_highpass(cutoff, fs, order=3):
    nyq = 0.5 * fs
    return butter(order, cutoff / nyq, btype="high")

def butter_bandpass(low, high, fs, order=2):
    nyq = 0.5 * fs
    return butter(order, [low / nyq, high / nyq], btype="band")

def apply_filter(audio, b, a):
    return lfilter(b, a, audio, axis=0)

def vocal_saturate(x, drive=1.15):
    return np.tanh(x * drive) / np.tanh(drive)

def rms_compressor(x, threshold=0.11, ratio=4.5):
    rms = np.sqrt(np.mean(x**2, axis=0, keepdims=True))
    gain = np.minimum(1.0, (threshold / (rms + 1e-9)) ** (ratio - 1))
    return x * gain

def process_loudv2(input_path, output_path, export_format):
    audio, sr = sf.read(input_path)

    if audio.ndim == 1:
        audio = np.stack([audio, audio], axis=1)

    b, a = butter_highpass(85, sr, order=3)
    audio = apply_filter(audio, b, a)

    b, a = butter_bandpass(1800, 4800, sr, order=2)
    vocal_band = apply_filter(audio, b, a)
    audio = audio + (vocal_band * 0.5)

    audio = rms_compressor(audio, threshold=0.13, ratio=3.5)
    audio = vocal_saturate(audio, drive=1.15)
    audio = rms_compressor(audio, threshold=0.10, ratio=4.5)
    audio = vocal_saturate(audio, drive=1.08)

    try:
        meter = pyln.Meter(sr)
        current_loudness = meter.integrated_loudness(audio)
        target_loudness = 12.0
        audio = pyln.normalize.loudness(audio, current_loudness, target_loudness)
    except:
        pass

    audio = np.clip(audio, -1.0, 1.0)

    audio_int16 = (audio * 32767).astype(np.int16)
    
    if audio.shape[1] == 2:
        raw_data = audio_int16.flatten().tobytes()
        channels = 2
    else:
        raw_data = audio_int16.tobytes()
        channels = 1
        
    seg = AudioSegment(data=raw_data, sample_width=2, frame_rate=sr, channels=channels)
    seg.export(output_path, format=export_format)

def process_mp3bait(decoy_path, hidden_path, output_path):
    """Create glitched MP3 with decoy and hidden audio. Target ~500 KB for hidden."""
    TARGET_HIDDEN_SIZE = 500_000  # 500 KB
    marker_size = 2048  # 2 KB marker
    
    def _get_duration(path):
        """Get audio duration in seconds using ffprobe."""
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", path],
            capture_output=True, text=True, check=True
        )
        return float(json.loads(result.stdout)["format"]["duration"])
    
    def _convert_decoy(path):
        """Convert decoy to mono MP3."""
        temp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
        try:
            audio = AudioSegment.from_file(path).set_channels(1)
            audio.export(temp, format="mp3", parameters=["-map_metadata", "-1"])
            with open(temp, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp):
                os.remove(temp)
    
    def _convert_hidden_compressed(path):
        """Compress hidden audio to ~500 KB."""
        duration = _get_duration(path)
        bitrate_bps = (TARGET_HIDDEN_SIZE * 8) / duration
        bitrate_kbps = max(8, int(bitrate_bps / 1000))
        
        temp = os.path.join(tempfile.gettempdir(), f"{uuid.uuid4().hex}.mp3")
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, "-ar", "48000", "-ac", "2", 
                 "-b:a", f"{bitrate_kbps}k", "-map_metadata", "-1", temp],
                check=True, capture_output=True
            )
            with open(temp, "rb") as f:
                return f.read()
        finally:
            if os.path.exists(temp):
                os.remove(temp)
    
    # Convert both files
    decoy = _convert_decoy(decoy_path)
    hidden = _convert_hidden_compressed(hidden_path)
    
    # Write glitched MP3
    with open(output_path, "wb") as f:
        f.write(decoy)
        # Write marker
        marker = b"STOP"
        remaining = marker_size - len(marker)
        f.write(b"\x00" * (remaining // 2))
        f.write(marker)
        f.write(b"\xFF" * (remaining - remaining // 2))
        f.write(hidden)

def process_img_bait(image_path, audio_path, output_path):
    """Embed audio file into PNG metadata."""
    # Validate image file
    if not image_path.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp')):
        raise ValueError(f"Invalid image file: {image_path}")
    
    # Validate audio file
    if not audio_path.lower().endswith(('.mp3', '.wav', '.ogg', '.m4a', '.flac')):
        raise ValueError(f"Invalid audio file: {audio_path}")
    
    # Open the base image
    target_image = Image.open(image_path)
    
    # Prepare metadata
    metadata = PngInfo()
    
    # Inject the raw binary data of the audio into the PNG metadata
    with open(audio_path, "rb") as audio_file:
        metadata.add_text("", audio_file.read())
    
    # Save the result
    target_image.save(output_path, pnginfo=metadata)