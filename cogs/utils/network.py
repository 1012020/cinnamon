import aiohttp
import os
import random
import string
import time
import asyncio
import yt_dlp
import config
from cogs.utils.helpers import send_error

async def _upload_litterbox(session, file_path, expiration):
    url = "https://litterbox.catbox.moe/resources/internals/api.php"
    try:
        with open(file_path, 'rb') as f:
            ext = os.path.splitext(file_path)[1]
            if not ext: ext = ".mp3"
            random_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + ext

            data = aiohttp.FormData()
            data.add_field('reqtype', 'fileupload')
            data.add_field('time', expiration)
            data.add_field('fileToUpload', f, filename=random_filename)
            
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    return await resp.text()
                else:
                    return None
    except Exception as e:
        print(f"upload error: {e}")
    return None

async def _upload_tmpfiles(session, file_path):
    url = "https://tmpfiles.org/api/v1/upload"
    try:
        with open(file_path, 'rb') as f:
            data = aiohttp.FormData()
            data.add_field('file', f)
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    if js.get('status') == 'success':
                        return js['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
    except Exception as e:
        print(f"tmpfiles upload error: {e}")
    return None

async def _upload_tempfile(session, file_path):
    url = "https://tempfile.org/api"
    try:
        with open(file_path, 'rb') as f:
            ext = os.path.splitext(file_path)[1]
            if not ext: ext = ".mp3"
            random_filename = ''.join(random.choices(string.ascii_letters + string.digits, k=16)) + ext

            data = aiohttp.FormData()
            data.add_field('file', f, filename=random_filename)
            
            async with session.post(url, data=data) as resp:
                if resp.status == 200:
                    js = await resp.json()
                    if js.get('status') == 'success':
                        return js['data']['url'].replace("tmpfiles.org/", "tmpfiles.org/dl/")
                    for key in ['url', 'link']:
                        if key in js and isinstance(js[key], str): return js[key]
                    if 'file' in js and isinstance(js['file'], dict) and 'url' in js['file']: return js['file']['url']
                    if 'data' in js and isinstance(js['data'], dict) and 'url' in js['data']: return js['data']['url']
    except Exception as e:
        print(f"tempfile upload error: {e}")
    return None

async def upload_file(session, file_path, expiration="1h", status_msg=None):
    async def check_ping(url):
        try:
            t0 = time.monotonic()
            async with session.head(url, timeout=2) as resp:
                return time.monotonic() - t0
        except:
            return float('inf')

    if status_msg:
        try: await status_msg.edit(content="checking upload speeds...")
        except: pass

    t_lat, tp_lat, l_lat = await asyncio.gather(
        check_ping("https://tmpfiles.org/"),
        check_ping("https://tempfile.org/"),
        check_ping("https://litterbox.catbox.moe/")
    )

    providers = [
        (t_lat, "tmpfiles", lambda: _upload_tmpfiles(session, file_path)),
        (tp_lat, "tempfile", lambda: _upload_tempfile(session, file_path)),
        (l_lat, "litterbox", lambda: _upload_litterbox(session, file_path, expiration))
    ]
    providers.sort(key=lambda x: x[0])

    for lat, name, func in providers:
        if status_msg:
            ping_str = f"{int(lat*1000)}ms" if lat != float('inf') else "N/A"
            try: await status_msg.edit(content=f"uploading to {name} ({ping_str})...")
            except: pass
        
        res = await func()
        if res: return res
    
    return None

async def download_url_simple(session, url):
    if not url: return None
    filename = "unknown.mp3"
    try: filename = url.split('?')[0].split('/')[-1]
    except: pass
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    if '.' in filename: ext = filename.split('.')[-1].lower()
    else: ext = "mp3"
    path = f"temp_{unique_id}.{ext}"
    try:
        async with session.get(url) as resp:
            if resp.status != 200: return None
            with open(path, 'wb') as f:
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    f.write(chunk)
        return path
    except:
        return None

async def download_file(ctx, url_arg, status_msg=None):
    target_url = None
    filename = "unknown.mp3"
    if ctx.message.attachments:
        target_url = ctx.message.attachments[0].url
        filename = ctx.message.attachments[0].filename
    elif url_arg:
        target_url = url_arg
        try: filename = target_url.split('?')[0].split('/')[-1]
        except: pass
    
    if not target_url or not any(d in target_url for d in config.ALLOWED_DOMAINS):
        msg = "i only accept links from cdn.discordapp.com"
        if status_msg: await status_msg.edit(content=msg)
        else: await ctx.send(msg)
        return None, None

    if status_msg: await status_msg.edit(content="downloading...")
    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    if '.' in filename: ext = filename.split('.')[-1].lower()
    else: ext = "mp3"
    input_path = f"in_{unique_id}.{ext}"

    try:
        async with ctx.bot.session.get(target_url) as resp:
            if resp.status != 200:
                msg = "download failed."
                if status_msg: await status_msg.edit(content=msg)
                else: await ctx.send(msg)
                return None, None
            with open(input_path, 'wb') as f:
                async for chunk in resp.content.iter_chunked(64 * 1024):
                    f.write(chunk)
        return input_path, filename
    except Exception as e:
        await send_error(ctx, e, status_msg)
        return None, None

def download_sc_yt_logic(target_url):
    ydl_opts_check = {'quiet': True, 'no_warnings': True, 'noplaylist': True, 'extract_flat': 'in_playlist'}
    try:
        with yt_dlp.YoutubeDL(ydl_opts_check) as ydl:
            info = ydl.extract_info(target_url, download=False)
            duration = info.get('duration', 0)
            title = info.get('title', 'audio')
            if duration > 540:
                return None, f"audio is too long ({duration}s). max is 9 minutes.", None
    except Exception as e:
        return None, f"failed to fetch info: {e}", None

    unique_id = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
    output_template = f"dl_{unique_id}.%(ext)s"
    ydl_opts_dl = {'format': 'bestaudio/best', 'outtmpl': output_template, 'quiet': True, 'noplaylist': True, 'writethumbnail': False, 'writeinfojson': False, 'postprocessors': [{'key': 'FFmpegExtractAudio', 'preferredcodec': 'mp3', 'preferredquality': '192'}]}
    try:
        with yt_dlp.YoutubeDL(ydl_opts_dl) as ydl:
            ydl.download([target_url])
        final_file = f"dl_{unique_id}.mp3"
        return (final_file, None, title) if os.path.exists(final_file) else (None, "download failed internally", None)
    except Exception as e:
        return None, f"download error: {e}", None

async def check_providers(session):
    results = {}
    targets = [
        ("tmpfiles", "https://tmpfiles.org/"),
        ("tempfile", "https://tempfile.org/"),
        ("litterbox", "https://litterbox.catbox.moe/")
    ]
    for name, url in targets:
        try:
            t0 = time.monotonic()
            async with session.get(url, timeout=5) as resp:
                lat = (time.monotonic() - t0) * 1000
                results[name] = (resp.status, f"{lat:.0f}ms")
        except:
            results[name] = ("down", "N/A")
    return results