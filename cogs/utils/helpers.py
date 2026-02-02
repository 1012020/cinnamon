import os
import functools
import asyncio
import random
from datetime import datetime
from pydub import AudioSegment
import config

# --- ASSETS ---
ASSET_CACHE = {}

def get_elapsed_time(bot, user_id):
    """Get elapsed time for a user's current command"""
    if user_id in bot.active_tasks and "start_time" in bot.active_tasks[user_id]:
        start_time = bot.active_tasks[user_id]["start_time"]
        elapsed = (datetime.now() - start_time).total_seconds()
        return f"(took {elapsed:.1f}s)"
    return ""

def load_assets():
    try:
        if os.path.exists(config.PREFIX_FILE):
            with open(config.PREFIX_FILE, "rb") as f:
                ASSET_CACHE["head"] = f.read()
        if os.path.exists(config.CINNAMON_FILE):
            ASSET_CACHE["cinnamon_seg"] = AudioSegment.from_file(config.CINNAMON_FILE)
        print("assets cached successfully.")
    except Exception as e:
        print(f"warning: could not cache assets: {e}")

# --- CONCURRENCY ---
EXECUTOR = None

async def run_blocking(func, *args, **kwargs):
    global EXECUTOR
    loop = asyncio.get_running_loop()
    partial = functools.partial(func, *args, **kwargs)
    try:
        return await loop.run_in_executor(EXECUTOR, partial)
    except Exception as e:
        # If executor failed, try to recreate it
        print(f"executor error: {e}, attempting to recreate...")
        try:
            import concurrent.futures
            if EXECUTOR:
                EXECUTOR.shutdown(wait=False)
            EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
            return await loop.run_in_executor(EXECUTOR, partial)
        except:
            # Fallback: run in current thread
            return partial()

# --- FILE OPS ---
def write_file(path, data):
    with open(path, 'wb') as f:
        f.write(data)

def clean_filename(fname):
    name = os.path.splitext(fname)[0]
    return "".join(c for c in name if c.isalnum() or c in (' ', '_', '-')).strip().replace(" ", "_")

# --- DISCORD CHECKS ---
def is_allowed_location(ctx):
    if ctx.guild and ctx.guild.id == config.ALLOWED_GUILD_ID and ctx.channel.id == config.ALLOWED_CHANNEL_ID:
        return True
    else:
        invite_link = f"https://discord.com/channels/{config.ALLOWED_GUILD_ID}/{config.ALLOWED_CHANNEL_ID}"
        asyncio.create_task(ctx.send(f"sorry, i can't do that here, maybe in {invite_link}?"))
        return False

async def send_error(ctx, e, status_msg=None):
    error_msg = f"error: {e}"
    if len(error_msg) > 1900: error_msg = error_msg[:1900] + "..."
    if status_msg: await status_msg.edit(content=error_msg)
    else: await ctx.send(error_msg)

# --- GENERATORS (HASH/HEX) ---
def to_hex(text):
    """Helper to convert text to URL-encoded hex."""
    return "".join(f"%{ord(c):x}" for c in text)

def get_polymorphic_key():
    """Generates 'assetversionid' with randomized casing in hex."""
    base_key = "assetversionid"
    poly_key = "".join(f"%{ord(c.upper() if random.getrandbits(1) else c):x}" for c in base_key)
    return f"{poly_key}="

def protected_id(audio_id):
    MAX_LIMIT = 16296
    HIDDEN_TAG = "cinnamon" 
    BASE_PREFIX = "me when i cant log: (-﹏-。)"
    DELIM = "ဪဪဪဪဪဪဪဪဪဪ" 

    safe_prefix = BASE_PREFIX 
    encoded_key = get_polymorphic_key()
    encoded_id = to_hex(audio_id)
    
    header = f"&{DELIM}{HIDDEN_TAG}{DELIM}"
    
    payload_chars = list(header + "&" + encoded_key + encoded_id)
    
    remaining_limit = MAX_LIMIT - len(safe_prefix)
    total_chars = len(payload_chars)
    total_spaces = remaining_limit - total_chars
    
    if total_spaces < 0:
        raise ValueError("Payload generation failed (input too long).")

    base_gap = total_spaces // total_chars
    extra_spaces = total_spaces % total_chars
    
    gap_base = " " * base_gap
    gap_extra = " " * (base_gap + 1)

    parts = [safe_prefix]
    
    for char in payload_chars[:extra_spaces]:
        parts.append(gap_extra)
        parts.append(char)
        
    for char in payload_chars[extra_spaces:]:
        parts.append(gap_base)
        parts.append(char)
        
    return "".join(parts)