import discord
from discord.ext import commands
import os
import random
import shutil
import config
from cogs.utils.helpers import run_blocking, is_allowed_location, send_error, clean_filename
from cogs.utils.network import download_file, download_url_simple, upload_file, download_sc_yt_logic
from cogs.utils import audio_processing as ap

class AudioCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name='download')
    @commands.check(is_allowed_location)
    async def download_sc_yt(self, ctx, url: str = None):
        msg = await ctx.send("initializing...")
        if not url:
            await msg.edit(content="error: please provide a link.")
            return
        valid_domains = ['youtube.com', 'youtu.be', 'soundcloud.com']
        if not any(domain in url for domain in valid_domains):
            await msg.edit(content="error: only youtube and soundcloud links are allowed.")
            return

        await msg.edit(content="checking duration & downloading audio...")
        file_path, error_msg, title = await run_blocking(download_sc_yt_logic, url)

        if error_msg:
            await msg.edit(content=f"error: {error_msg}")
            return

        if file_path and title:
            try:
                clean_title = clean_filename(title)
                upload_path = f"{clean_title}.mp3"
                if os.path.exists(upload_path): os.remove(upload_path)
                os.rename(file_path, upload_path)
                await msg.edit(content="uploading...")
                await ctx.send(file=discord.File(upload_path))
                await msg.delete()
                if os.path.exists(upload_path): os.remove(upload_path)
            except Exception as e:
                await send_error(ctx, e, status_msg=msg)
                if os.path.exists(file_path): os.remove(file_path)
                if 'upload_path' in locals() and os.path.exists(upload_path): os.remove(upload_path)

    @commands.command(name='intro')
    @commands.check(is_allowed_location)
    async def make_intro(self, ctx, arg1: str = None, arg2: str = None):
        msg = await ctx.send("initializing...")
        main_url = None
        intro_url = None
        original_name = "song.mp3"
        if ctx.message.attachments:
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
            return
        if not main_url.startswith("http") or not intro_url.startswith("http"):
            await msg.edit(content="error: inputs must be valid links.")
            return
        await msg.edit(content="downloading main audio...")
        main_path = await download_url_simple(self.bot.session, main_url)
        if not main_path:
            await msg.edit(content="error: failed to download main audio.")
            return
        await msg.edit(content="downloading intro audio...")
        intro_path = await download_url_simple(self.bot.session, intro_url)
        if not intro_path:
            await msg.edit(content="error: failed to download intro audio.")
            if os.path.exists(main_path): os.remove(main_path)
            return
        try:
            await msg.edit(content="stitching audio...")
            ext = main_path.split('.')[-1].lower()
            clean_name = clean_filename(original_name)
            output_path = f"{clean_name}_intro.{ext}"
            format_map = {"m4a": "ipod", "jpg": "mp3", "png": "mp3"}
            export_fmt = format_map.get(ext, ext)
            await run_blocking(ap.process_intro, main_path, intro_path, output_path, export_fmt)
            # Save intro file to intro folder
            if not os.path.exists("intro"):
                os.makedirs("intro")
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            intro_ext = intro_path.split('.')[-1].lower()
            intro_save_name = f"intro_{ctx.author.name}_{ctx.author.id}_{timestamp}.{intro_ext}"
            intro_save_path = os.path.join("intro", intro_save_name)
            with open(intro_path, "rb") as src:
                with open(intro_save_path, "wb") as dst:
                    dst.write(src.read())
            await msg.edit(content="uploading...")
            await ctx.send(file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(main_path): os.remove(main_path)
            if os.path.exists(intro_path): os.remove(intro_path)

    @commands.command(name='convert')
    @commands.check(is_allowed_location)
    async def make_convert(self, ctx, arg1: str = None, arg2: str = None):
        msg = await ctx.send("initializing...")
        target_url = None
        target_ext = "ogg"
        args = [x for x in [arg1, arg2] if x is not None]
        for a in args:
            if a.startswith("http"):
                target_url = a
                break
        if not target_url and ctx.message.attachments:
            target_url = ctx.message.attachments[0].url
        for a in args:
            if a != target_url:
                target_ext = a
                break
        if not target_url:
            await msg.edit(content="error: please provide a valid link or attachment.")
            return
        target_ext = target_ext.lower().replace(".", "").strip()
        allowed_formats = ["mp3", "ogg", "wav", "flac", "m4a", "aac", "wma"]
        if target_ext not in allowed_formats:
            await msg.edit(content=f"error: unsupported format '{target_ext}'. supported: {', '.join(allowed_formats)}")
            return
        input_path, original_filename = await download_file(ctx, target_url, status_msg=msg)
        if not input_path: return
        try:
            await msg.edit(content=f"converting to {target_ext}...")
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}.{target_ext}"
            format_map = { "m4a": "ipod", "aac": "adts" }
            export_fmt = format_map.get(target_ext, target_ext)
            await run_blocking(ap.process_convert, input_path, output_path, export_fmt)
            await msg.edit(content="uploading...")
            await ctx.send(file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e: await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(input_path): os.remove(input_path)

    @commands.command(name='32mono')
    @commands.check(is_allowed_location)
    async def make_32mono(self, ctx, url: str = None):
        msg = await ctx.send("initializing...")
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path: return
        if not input_path.lower().endswith(".ogg"):
            await msg.edit(content="error: input has to be an .ogg file.")
            os.remove(input_path)
            return
        if not os.path.exists(config.BAIT_DIRECTORY):
            await msg.edit(content="error: bait directory not found.")
            os.remove(input_path)
            return
        all_baits = [f for f in os.listdir(config.BAIT_DIRECTORY) if os.path.isfile(os.path.join(config.BAIT_DIRECTORY, f))]
        valid_baits = [f for f in all_baits if f.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))]
        if not valid_baits:
            await msg.edit(content="error: no audio files in bait directory.")
            os.remove(input_path)
            return
        selected_bait_name = random.choice(valid_baits)
        selected_bait_path = os.path.join(config.BAIT_DIRECTORY, selected_bait_name)
        bait_base = os.path.splitext(selected_bait_name)[0]
        rand_suffix = ''.join(random.choices('0123456789abcdef', k=16))
        output_file = f"{bait_base}_{rand_suffix}.mp3"
        try:
            await msg.edit(content=f"processing using bait: {selected_bait_name}...")
            should_watermark = not any(r.id == config.ISRAELITE_ROLE_ID for r in ctx.author.roles)
            await run_blocking(ap.process_32mono, input_path, output_file, selected_bait_path, add_watermark=should_watermark)
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                await msg.edit(content=f"done: {download_link} (expires in 1h)\nwhen uploading it call it: **{output_file}** or not, it's your call")
            else:
                await msg.edit(content="error: upload to litterbox failed.")
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_file): os.remove(output_file)

    @commands.command(name='fullbait')
    @commands.check(is_allowed_location)
    async def make_fullbait(self, ctx, url: str = None):
        msg = await ctx.send("initializing...")
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path: return
        
        fullbaits_dir = os.path.join(os.path.dirname(config.BAIT_DIRECTORY), "fullbaits")
        if not os.path.exists(fullbaits_dir): fullbaits_dir = "fullbaits"
        
        if not os.path.exists(fullbaits_dir):
            await msg.edit(content="error: fullbaits directory not found.")
            os.remove(input_path)
            return

        all_baits = [f for f in os.listdir(fullbaits_dir) if f.endswith('.ogg')]
        if not all_baits:
            await msg.edit(content="error: no .ogg files in fullbaits directory.")
            os.remove(input_path)
            return

        selected_bait = random.choice(all_baits)
        bait_path = os.path.join(fullbaits_dir, selected_bait)
        clean_name = clean_filename(original_filename)
        output_file = f"{clean_name}_fullbait.ogg"

        try:
            await msg.edit(content="processing...")
            should_watermark = not any(r.id == config.ISRAELITE_ROLE_ID for r in ctx.author.roles)
            await run_blocking(ap.process_fullbait, input_path, output_file, bait_path, add_watermark=should_watermark)
            download_link = await upload_file(self.bot.session, output_file, status_msg=msg)
            if download_link:
                await msg.edit(content=f"done: {download_link} (expires in 1h)\nwhen uploading it call it: **{selected_bait}** or not, it's your call")
            else:
                await msg.edit(content="error: upload failed.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(input_path): os.remove(input_path)
            if os.path.exists(output_file): os.remove(output_file)

    async def _process_simple_effect(self, ctx, url, effect_func, effect_name):
        msg = await ctx.send("starting...")
        input_path, original_filename = await download_file(ctx, url, status_msg=msg)
        if not input_path: return
        try:
            await msg.edit(content=f"{effect_name}...")
            ext = input_path.split('.')[-1].lower()
            clean_name = clean_filename(original_filename)
            output_path = f"{clean_name}_{effect_name.replace(' ', '')}.{ext}"
            format_map = { "m4a": "ipod", "jpg": "mp3", "png": "mp3" }
            export_format = format_map.get(ext, ext)
            await run_blocking(effect_func, input_path, output_path, export_format)
            await msg.edit(content="uploading...")
            await ctx.send(file=discord.File(output_path))
            await msg.delete()
            if os.path.exists(output_path): os.remove(output_path)
        except Exception as e: await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(input_path): os.remove(input_path)

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

async def setup(bot):
    await bot.add_cog(AudioCommands(bot))