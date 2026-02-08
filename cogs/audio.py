import discord
from discord.ext import commands
import os
import random
import shutil
import uuid
import config
from cogs.utils.helpers import run_blocking, is_allowed_location, send_error, clean_filename, get_elapsed_time
from cogs.utils.network import download_file, download_url_simple, upload_file, download_sc_yt_logic
from cogs.utils import audio_processing as ap

class AudioCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='download')
    @commands.check(is_allowed_location)
    async def download_sc_yt(self, ctx, url: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "download", "files": [], "start_time": datetime.now()}
        
        try:
            if not url:
                await msg.edit(content="error: please provide a link or pekora.zip ID.")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            # Check if it's a pekora.zip ID (numeric)
            if url.isdigit():
                pekora_url = f"https://www.pekora.zip/asset/?id={url}"
                await msg.edit(content=f"downloading from pekora.zip (ID: {url})...")
                
                # Download directly from pekora.zip
                file_path = await download_url_simple(self.bot.session, pekora_url)
                if not file_path:
                    await msg.edit(content="error: failed to download from pekora.zip. invalid ID?")
                    return
                
                if ctx.author.id in self.bot.active_tasks:
                    self.bot.active_tasks[ctx.author.id]["files"].append(file_path)
                
                try:
                    upload_path = f"pekora_{url}.mp3"
                    if os.path.exists(upload_path): os.remove(upload_path)
                    os.rename(file_path, upload_path)
                    
                    file_size = os.path.getsize(upload_path) / (1024 * 1024)
                    elapsed = get_elapsed_time(self.bot, ctx.author.id)
                    
                    await msg.edit(content="uploading...")
                    await ctx.send(f"pekora.zip ({file_size:.2f}mb) {elapsed}", file=discord.File(upload_path))
                    await msg.delete()
                    if os.path.exists(upload_path): os.remove(upload_path)
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)
                    if os.path.exists(file_path): os.remove(file_path)
                    if 'upload_path' in locals() and os.path.exists(upload_path): os.remove(upload_path)
                return
            
            # Original YouTube/SoundCloud logic
            valid_domains = ['youtube.com', 'youtu.be', 'soundcloud.com']
            if not any(domain in url for domain in valid_domains):
                await msg.edit(content="error: only youtube and soundcloud links are allowed.")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return

            await msg.edit(content="checking duration & downloading audio...")
            file_path, error_msg, title = await run_blocking(download_sc_yt_logic, url)

            if ctx.author.id in self.bot.active_tasks and file_path:
                self.bot.active_tasks[ctx.author.id]["files"].append(file_path)

            if error_msg:
                await msg.edit(content=f"error: {error_msg}")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return

            if file_path and title:
                try:
                    clean_title = clean_filename(title)
                    upload_path = f"{clean_title}.mp3"
                    if os.path.exists(upload_path): os.remove(upload_path)
                    os.rename(file_path, upload_path)
                    
                    file_size = os.path.getsize(upload_path) / (1024 * 1024)
                    elapsed = get_elapsed_time(self.bot, ctx.author.id)
                    
                    await msg.edit(content="uploading...")
                    await ctx.send(f"downloaded ({file_size:.2f}mb) {elapsed}", file=discord.File(upload_path))
                    await msg.delete()
                    if os.path.exists(upload_path): os.remove(upload_path)
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)
                    if 'file_path' in locals() and os.path.exists(file_path): os.remove(file_path)
                    if 'upload_path' in locals() and os.path.exists(upload_path): os.remove(upload_path)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]

    @commands.command(name='intro')
    @commands.check(is_allowed_location)
    async def make_intro(self, ctx, arg1: str = None, arg2: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "intro", "files": [], "start_time": datetime.now()}
        main_url = None
        intro_url = None
        original_name = "song.mp3"
        if ctx.message.attachments and len(ctx.message.attachments) > 0:
            main_url = ctx.message.attachments[0].url
            if arg1: intro_url = arg1
            original_name = ctx.message.attachments[0].filename
        elif arg1 and arg2:
            main_url = arg1
            intro_url = arg2
            try: original_name = arg1.split("?")[0].split("/")[-1]
            except: pass
        else:
            await msg.edit(content="error: missing inputs.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if not main_url or not intro_url or not main_url.startswith("http") or not intro_url.startswith("http"):
            await msg.edit(content="error: inputs must be valid links.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        await msg.edit(content="downloading main audio...")
        main_path = await download_url_simple(self.bot.session, main_url)
        if not main_path:
            await msg.edit(content="error: failed to download main audio.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(main_path)
        await msg.edit(content="downloading intro audio...")
        intro_path = await download_url_simple(self.bot.session, intro_url)
        if not intro_path:
            await msg.edit(content="error: failed to download intro audio.")
            if os.path.exists(main_path): os.remove(main_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(intro_path)
        try:
            await msg.edit(content="stitching audio...")
            ext = main_path.split('.')[-1].lower()
            clean_name = clean_filename(original_name)
            output_path = f"{clean_name}_intro.{ext}"
            format_map = {"m4a": "ipod", "jpg": "mp3", "png": "mp3"}
            export_fmt = format_map.get(ext, ext)
            await run_blocking(ap.process_intro, main_path, intro_path, output_path, export_fmt)
            # Save intro file to intro folder
            if not os.path.exists("assets/intro"):
                os.makedirs("assets/intro")
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            intro_ext = intro_path.split('.')[-1].lower()
            intro_save_name = f"intro_{ctx.author.name}_{ctx.author.id}_{timestamp}.{intro_ext}"
            intro_save_path = os.path.join("assets", "intro", intro_save_name)
            with open(intro_path, "rb") as src:
                with open(intro_save_path, "wb") as dst:
                    dst.write(src.read())
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            await msg.edit(content="uploading...")
            await ctx.send(f"done ({file_size:.2f}mb) {elapsed}", file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if os.path.exists(main_path): os.remove(main_path)
            if os.path.exists(intro_path): os.remove(intro_path)

    @commands.command(name='convert')
    @commands.check(is_allowed_location)
    async def make_convert(self, ctx, arg1: str = None, arg2: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "convert", "files": [], "start_time": datetime.now()}
        target_url = None
        target_ext = "ogg"
        args = [x for x in [arg1, arg2] if x is not None]
        for a in args:
            if a.startswith("http"):
                target_url = a
                break
        if not target_url and ctx.message.attachments and len(ctx.message.attachments) > 0:
            target_url = ctx.message.attachments[0].url
        for a in args:
            if a != target_url:
                target_ext = a
                break
        if not target_url:
            await msg.edit(content="error: please provide a valid link or attachment.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        target_ext = target_ext.lower().replace(".", "").strip()
        allowed_formats = ["mp3", "ogg", "wav", "flac", "m4a", "aac", "wma"]
        if target_ext not in allowed_formats:
            await msg.edit(content=f"error: unsupported format '{target_ext}'. supported: {', '.join(allowed_formats)}")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        input_path, original_filename = await download_file(ctx, target_url, status_msg=msg)
        if not input_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        try:
            await msg.edit(content=f"converting to {target_ext}...")
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}.{target_ext}"
            format_map = { "m4a": "ipod", "aac": "adts" }
            export_fmt = format_map.get(target_ext, target_ext)
            await run_blocking(ap.process_convert, input_path, output_path, export_fmt)
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            await msg.edit(content="uploading...")
            await ctx.send(f"converted to {target_ext} ({file_size:.2f}mb) {elapsed}", file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e: await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if os.path.exists(input_path): os.remove(input_path)

    @commands.command(name='32mono')
    @commands.check(is_allowed_location)
    async def make_32mono(self, ctx, url: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "32mono", "files": [], "start_time": datetime.now()}
        
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path: 
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        if not input_path.lower().endswith(".ogg"):
            await msg.edit(content="error: input has to be an .ogg file.")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        # Check channel count
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(input_path)
            if audio.channels != 2:
                await msg.edit(content=f"error: input has {audio.channels} channel(s). only 2 channels (stereo) are supported.")
                os.remove(input_path)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
        except Exception as e:
            await msg.edit(content=f"error: could not validate audio channels: {str(e)}")
            os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        if not os.path.exists(config.BAIT_DIRECTORY):
            await msg.edit(content="error: bait directory not found.")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        all_baits = [f for f in os.listdir(config.BAIT_DIRECTORY) if os.path.isfile(os.path.join(config.BAIT_DIRECTORY, f))]
        valid_baits = [f for f in all_baits if f.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))]
        if not valid_baits:
            await msg.edit(content="error: no audio files in bait directory.")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        selected_bait_name = random.choice(valid_baits)
        selected_bait_path = os.path.join(config.BAIT_DIRECTORY, selected_bait_name)
        bait_base = os.path.splitext(selected_bait_name)[0]
        rand_suffix = ''.join(random.choices('0123456789abcdef', k=16))
        output_file = f"{bait_base}_{rand_suffix}.mp3"
        try:
            await msg.edit(content=f"processing using bait: {selected_bait_name}...")
            should_watermark = not any(r.id == config.ISRAELITE_ROLE_ID for r in ctx.author.roles) if ctx.author.roles else True if ctx.author.roles else True
            await run_blocking(ap.process_32mono, input_path, output_file, selected_bait_path, add_watermark=should_watermark)
            
            # Check file size (10MB max)
            file_size = os.path.getsize(output_file)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if file_size > max_size:
                size_mb = file_size / (1024 * 1024)
                await msg.edit(content=f"error: song that was made was {size_mb:.2f}MB, the maximum should be 10MB. use !compress")
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_file): os.remove(output_file)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                elapsed = get_elapsed_time(self.bot, ctx.author.id)
                await msg.edit(content=f"done: {download_link} (expires in 1h) {elapsed}\nwhen uploading it call it: **{output_file}** or not, it's your call")
            else:
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_file): os.remove(output_file)

    @commands.command(name='fullbait')
    @commands.check(is_allowed_location)
    async def make_fullbait(self, ctx, url: str = None):
        from datetime import datetime
        # Check if user has the required role (by ID)
        author_roles = getattr(ctx.author, "roles", []) or []
        has_required_role = any(getattr(r, "id", None) == 1464787461719720133 for r in author_roles)
        if not has_required_role:
            await ctx.send("error: you don't have the required role to use this command.")
            return
        
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "fullbait", "files": [], "start_time": datetime.now()}
        
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        
        # Check channel count
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(input_path)
            if audio.channels != 2:
                await msg.edit(content=f"error: input has {audio.channels} channel(s). only 2 channels (stereo) are supported.")
                if os.path.exists(input_path):
                    os.remove(input_path)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
        except Exception as e:
            await msg.edit(content=f"error: could not validate audio channels: {str(e)}")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        fullbaits_dir = os.path.join(os.path.dirname(config.BAIT_DIRECTORY), "fullbaits")
        if not os.path.exists(fullbaits_dir): fullbaits_dir = "assets/fullbaits"
        
        if not os.path.exists(fullbaits_dir):
            await msg.edit(content="error: fullbaits directory not found.")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return

        all_baits = [f for f in os.listdir(fullbaits_dir) if f.endswith('.ogg')]
        if not all_baits:
            await msg.edit(content="error: no .ogg files in fullbaits directory.")
            if os.path.exists(input_path):
                os.remove(input_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return

        selected_bait = random.choice(all_baits)
        bait_path = os.path.join(fullbaits_dir, selected_bait)
        clean_name = clean_filename(original_filename)
        output_file = f"{clean_name}_fullbait.ogg"

        try:
            await msg.edit(content="processing...")
            should_watermark = not any(r.id == config.ISRAELITE_ROLE_ID for r in ctx.author.roles)
            await run_blocking(ap.process_fullbait, input_path, output_file, bait_path, add_watermark=should_watermark)
            
            # Check file size (17.5MB max for fullbait)
            file_size = os.path.getsize(output_file)
            max_size = int(17.5 * 1024 * 1024)  # 17.5MB in bytes
            if file_size > max_size:
                size_mb = file_size / (1024 * 1024)
                await msg.edit(content=f"error: song that was made was {size_mb:.2f}MB, the maximum should be 17.5MB. use !compress")
                if os.path.exists(input_path): os.remove(input_path)
                if os.path.exists(output_file): os.remove(output_file)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                elapsed = get_elapsed_time(self.bot, ctx.author.id)
                await msg.edit(content="done! check your DMs.")
                try:
                    await ctx.author.send(f"done: {download_link} (expires in 1h) {elapsed}\nwhen uploading it call it: **{selected_bait}** or not, it's your call")
                except discord.Forbidden:
                    await msg.edit(content="error: couldn't send DM. please enable DMs from server members.")
            else:
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if 'input_path' in locals() and os.path.exists(input_path): os.remove(input_path)
            if 'output_file' in locals() and os.path.exists(output_file): os.remove(output_file)

    async def _process_simple_effect(self, ctx, url, effect_func, effect_name):
        from datetime import datetime
        msg = await ctx.send("starting...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": effect_name, "files": [], "start_time": datetime.now()}
        
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        try:
            await msg.edit(content=f"{effect_name}...")
            ext = input_path.split('.')[-1].lower()
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}_{effect_name.replace(' ', '')}.{ext}"
            format_map = { "m4a": "ipod", "jpg": "mp3", "png": "mp3" }
            export_format = format_map.get(ext, ext)
            await run_blocking(effect_func, input_path, output_path, export_format)
            
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            await msg.edit(content="uploading...")
            await ctx.send(f"done ({file_size:.2f}mb) {elapsed}", file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e: await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if 'input_path' in locals() and os.path.exists(input_path): os.remove(input_path)

    @commands.command(name='loud')
    @commands.check(is_allowed_location)
    async def make_loud(self, ctx, url: str = None):
        await self._process_simple_effect(ctx, url, ap.process_loud, "applying 300db gain")

    @commands.command(name='loudv2')
    @commands.check(is_allowed_location)
    async def make_loudv2(self, ctx, url: str = None):
        await self._process_simple_effect(ctx, url, ap.process_loudv2, "applying vocal-forward loudness")

    @commands.command(name='2db')
    @commands.check(is_allowed_location)
    async def make_2db(self, ctx, url: str = None):
        await self._process_simple_effect(ctx, url, ap.process_2db, "normalizing to -2db")

    @commands.command(name='nobass')
    @commands.check(is_allowed_location)
    async def make_nobass(self, ctx, url: str = None):
        await self._process_simple_effect(ctx, url, ap.process_nobass, "removing bass")

    @commands.command(name='createchannels')
    @commands.check(is_allowed_location)
    async def make_create_channels(self, ctx, num_channels: int = None, url: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "createchannels", "files": [], "start_time": datetime.now()}
        
        if not num_channels:
            await msg.edit(content="error: please specify number of channels (1-32).")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        if num_channels > 32:
            await msg.edit(content="error: we've tried going over 32, it doesn't work")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        if num_channels < 1:
            await msg.edit(content="error: number of channels must be at least 1.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        
        try:
            await msg.edit(content=f"creating {num_channels} channel audio...")
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}_{num_channels}ch.ogg"
            
            print(f"DEBUG: About to call process_create_channels with {input_path}, {output_path}, {num_channels}")
            await run_blocking(ap.process_create_channels, input_path, output_path, num_channels)
            print(f"DEBUG: process_create_channels completed successfully")
            
            # Show file info
            file_size = os.path.getsize(output_path) / (1024 * 1024)
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            # Check file size - only upload if 15MB or less
            if file_size > 15:
                await msg.edit(content=f"error: file size ({file_size:.2f}mb) is too large to upload on site. max is 15mb, use !compress")
            else:
                await msg.edit(content="uploading...")
                await ctx.send(
                    f"created {num_channels} channel audio ({file_size:.2f}mb) {elapsed}",
                    file=discord.File(output_path)
                )
                await msg.delete()
            
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e:
            print(f"DEBUG: Exception caught in make_create_channels: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if os.path.exists(input_path): os.remove(input_path)

    @commands.command(name='compress')
    @commands.check(is_allowed_location)
    async def make_compress(self, ctx, url: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "compress", "files": [], "start_time": datetime.now()}
        
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(input_path)
        
        try:
            await msg.edit(content="compressing with high quality settings...")
            ext = input_path.split('.')[-1].lower()
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}_compressed.{ext}"
            
            await run_blocking(ap.process_compression, input_path, output_path)
            
            # Show file size comparison
            original_size = os.path.getsize(input_path) / (1024 * 1024)
            compressed_size = os.path.getsize(output_path) / (1024 * 1024)
            reduction = ((original_size - compressed_size) / original_size) * 100
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            await msg.edit(content="uploading...")
            await ctx.send(
                f"compressed: {original_size:.2f}mb → {compressed_size:.2f}mb ({reduction:.1f}% reduction) {elapsed}",
                file=discord.File(output_path)
            )
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if os.path.exists(input_path): os.remove(input_path)

    @commands.command(name='mp3bait')
    @commands.check(is_allowed_location)
    async def make_mp3bait(self, ctx, url: str = None):
        from datetime import datetime
        msg = await ctx.send("this method is NOT GOOD and rarely works. 2017-2018 only.\ninitializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "mp3bait", "files": [], "start_time": datetime.now()}
        
        # Get hidden audio from attachment or URL
        hidden_url = None
        if ctx.message.attachments and len(ctx.message.attachments) > 0:
            hidden_url = ctx.message.attachments[0].url
        elif url:
            hidden_url = url
        
        if not hidden_url:
            await msg.edit(content="error: please provide hidden audio (attachment or URL).")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        # Check if cinnamon.mp3 exists
        cinnamon_path = "assets/cinnamon.mp3"
        if not os.path.exists(cinnamon_path):
            await msg.edit(content="error: cinnamon.mp3 not found in assets folder.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        # Select random bait from mp3 baits directory
        mp3baits_dir = "assets/mp3 baits"
        if not os.path.exists(mp3baits_dir):
            await msg.edit(content="error: mp3 baits directory not found.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        all_baits = [f for f in os.listdir(mp3baits_dir) if os.path.isfile(os.path.join(mp3baits_dir, f))]
        valid_baits = [f for f in all_baits if f.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))]
        if not valid_baits:
            await msg.edit(content="error: no audio files in mp3 baits directory.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        selected_bait_name = random.choice(valid_baits)
        decoy_path = os.path.join(mp3baits_dir, selected_bait_name)
        
        await msg.edit(content=f"downloading hidden audio... (using bait: {selected_bait_name})")
        hidden_path, _ = await download_file(ctx, hidden_url, status_msg=msg)
        if not hidden_path:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(hidden_path)
        
        # Check channel count
        try:
            from pydub import AudioSegment
            audio = AudioSegment.from_file(hidden_path)
            if audio.channels != 2:
                await msg.edit(content=f"error: input has {audio.channels} channel(s). only 2 channels (stereo) are supported.")
                os.remove(hidden_path)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
        except Exception as e:
            await msg.edit(content=f"error: could not validate audio channels: {str(e)}")
            os.remove(hidden_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        output_file = f"mp3bait_{uuid.uuid4().hex[:8]}.mp3"
        stitched_temp = f"stitched_{uuid.uuid4().hex[:8]}.mp3"
        
        try:
            # Stitch cinnamon.mp3 + hidden audio together
            await run_blocking(ap.process_intro, hidden_path, cinnamon_path, stitched_temp, "mp3")
            
            await msg.edit(content="processing glitched MP3 (compressing hidden to ~500 KB)...")
            await run_blocking(ap.process_mp3bait, decoy_path, stitched_temp, output_file)
            
            # Check file size (10MB max)
            file_size = os.path.getsize(output_file)
            max_size = 10 * 1024 * 1024  # 10MB in bytes
            if file_size > max_size:
                size_mb = file_size / (1024 * 1024)
                await msg.edit(content=f"error: song that was made was {size_mb:.2f}MB, the maximum should be 10MB. use !compress")
                if 'hidden_path' in locals() and os.path.exists(hidden_path): os.remove(hidden_path)
                if 'stitched_temp' in locals() and os.path.exists(stitched_temp): os.remove(stitched_temp)
                if 'output_file' in locals() and os.path.exists(output_file): os.remove(output_file)
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                elapsed = get_elapsed_time(self.bot, ctx.author.id)
                await msg.edit(content=f"this method is NOT GOOD and rarely works. 2017-2018 only.\n\ndone: {download_link} (expires in 1h) {elapsed}\nwhen uploading it call it: **{selected_bait_name}** or not, it's your call")
            else:
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if 'hidden_path' in locals() and os.path.exists(hidden_path): os.remove(hidden_path)
            
            if 'output_file' in locals() and os.path.exists(output_file): os.remove(output_file)

    @commands.command(name='img')
    @commands.check(is_allowed_location)
    async def make_img_bait(self, ctx, arg1: str = None, arg2: str = None):
        from datetime import datetime
        msg = await ctx.send("initializing...")
        self.bot.active_tasks[ctx.author.id] = {"message": msg, "command": "img", "files": [], "start_time": datetime.now()}
        
        # Get audio and optional custom image
        audio_url = None
        custom_image_url = None
        
        # Check attachments: first = audio, second (if exists) = custom image
        if ctx.message.attachments and len(ctx.message.attachments) > 0:
            audio_url = ctx.message.attachments[0].url
            if len(ctx.message.attachments) > 1:
                custom_image_url = ctx.message.attachments[1].url
        
        # Parse URLs from arguments
        if arg1:
            if not audio_url:
                audio_url = arg1
            elif not custom_image_url and arg1.startswith("http"):
                custom_image_url = arg1
        
        if arg2 and arg2.startswith("http"):
            custom_image_url = arg2
        
        if not audio_url:
            await msg.edit(content="error: please provide audio file (attachment or URL).")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        # Check if cinnamon.mp3 exists
        cinnamon_path = "assets/cinnamon.mp3"
        if not os.path.exists(cinnamon_path):
            await msg.edit(content="error: cinnamon.mp3 not found in assets folder.")
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        
        # Handle custom image or select random
        custom_image_path = None
        selected_image_name = None
        
        if custom_image_url:
            # Download custom image
            await msg.edit(content="downloading custom image...")
            custom_image_path, _ = await download_file(ctx, custom_image_url, status_msg=msg)
            if not custom_image_path:
                await msg.edit(content="error: failed to download custom image.")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            if ctx.author.id in self.bot.active_tasks:
                self.bot.active_tasks[ctx.author.id]["files"].append(custom_image_path)
            selected_image_path = custom_image_path
            selected_image_name = "custom image"
        else:
            # Select random image from img baits directory
            img_baits_dir = "assets/img baits"
            if not os.path.exists(img_baits_dir):
                await msg.edit(content="error: img baits directory not found.")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            all_images = [f for f in os.listdir(img_baits_dir) if os.path.isfile(os.path.join(img_baits_dir, f))]
            valid_images = [f for f in all_images if f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
            if not valid_images:
                await msg.edit(content="error: no image files found in img baits directory.")
                if ctx.author.id in self.bot.active_tasks:
                    del self.bot.active_tasks[ctx.author.id]
                return
            
            selected_image_name = random.choice(valid_images)
            selected_image_path = os.path.join(img_baits_dir, selected_image_name)
        
        await msg.edit(content=f"downloading audio... (using: {selected_image_name})")
        hidden_path, _ = await download_file(ctx, audio_url, status_msg=msg)
        if not hidden_path:
            if custom_image_path and os.path.exists(custom_image_path): os.remove(custom_image_path)
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            return
        if ctx.author.id in self.bot.active_tasks:
            self.bot.active_tasks[ctx.author.id]["files"].append(hidden_path)
        
        output_file = f"img_bait_{uuid.uuid4().hex[:8]}.png"

        # Force the stitched audio used for img bait to be MP3 (stereo only).
        # We still try to detect channels for logging/fallback, but always use MP3.
        try:
            from pydub import AudioSegment
            hidden_ch = AudioSegment.from_file(hidden_path).channels
        except Exception:
            hidden_ch = 2

        try:
            await msg.edit(content="embedding audio into image...")

            # Require MP3 input for the image embed command
            if not hidden_path.lower().endswith('.mp3'):
                await msg.edit(content="error: audio must be an .mp3 file.")
                return

            # Embed raw MP3 bytes into PNG metadata using PIL
            from PIL import Image
            from PIL.PngImagePlugin import PngInfo

            try:
                target_image = Image.open(selected_image_path)
            except Exception as e:
                await msg.edit(content=f"error: failed to open image: {e}")
                return

            metadata = PngInfo()
            try:
                with open(hidden_path, "rb") as f:
                    audio_bytes = f.read()
            except Exception as e:
                await msg.edit(content=f"error: failed to read audio file: {e}")
                return

            metadata.add_text("", audio_bytes)
            target_image.save(output_file, pnginfo=metadata)

            # Check file size
            file_size = os.path.getsize(output_file)
            size_mb = file_size / (1024 * 1024)
            elapsed = get_elapsed_time(self.bot, ctx.author.id)
            
            await msg.edit(content="uploading...")
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                await msg.edit(content=f"done! final size: {size_mb:.2f}mb {elapsed}\n{download_link}")
            else:
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]
            if 'hidden_path' in locals() and os.path.exists(hidden_path): os.remove(hidden_path)
            if 'custom_image_path' in locals() and custom_image_path and os.path.exists(custom_image_path): os.remove(custom_image_path)
            
            if 'output_file' in locals() and os.path.exists(output_file): os.remove(output_file)

async def setup(bot):
    await bot.add_cog(AudioCommands(bot))
