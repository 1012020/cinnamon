import discord
from discord.ext import commands
import os
import json
import secrets
from datetime import datetime
from cogs.utils.helpers import run_blocking, is_allowed_location, send_error, write_file, protected_id, send_file_checked, send_status
import sys
sys.path.append('..')
import config
from cogs.utils.network import download_file, upload_file
from cogs.utils import audio_processing as ap
from cogs.utils.settings import get_fullbait_mode
import random
import shutil
import os
import uuid
from cogs.utils.logging_system import get_logger

logger = get_logger()

# IDs rotation helper to avoid unbounded growth
MAX_IDS_LINES = 10_000

def _append_id_log(line: str):
    path = "data/IDs.txt"
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
        # Rotate if too large
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        if len(lines) > MAX_IDS_LINES:
            with open(path, "w", encoding="utf-8") as f:
                f.writelines(lines[-MAX_IDS_LINES:])
    except Exception:
        pass

class ToolCommands(commands.Cog):
    @commands.command(name='embed')
    async def embed_icc_command(self, ctx, *args):
        # Restrict to channel 1469978323667910810
        if ctx.channel.id != 1469978323667910810:
            await send_status(ctx, "error: this command can only be used in <#1469978323667910810>.")
            return
            return

        # Parse arguments for 'saveas' option
        save_as = None
        image_url = None
        if args and args[0].lower() == 'saveas' and len(args) >= 3:
            save_as = args[1]
            image_url = args[2]
        elif args:
            image_url = args[0]

        msg = await send_status(ctx, "processing image...")
        input_path = f"input_{ctx.author.id}.png"
        output_path = save_as if save_as else f"output_{ctx.author.id}.png"
        icc_profile = os.path.join('assets', 'iccp', 'custom.icc')
        try:
            # Download from attachment or URL
            if ctx.message.attachments:
                attachment = ctx.message.attachments[0]
                if not attachment.filename.lower().endswith('.png'):
                    await send_status(ctx, "error: only PNG images are supported.", status_msg=msg)
                    return
                await attachment.save(input_path)
            elif image_url:
                if not (image_url.lower().endswith('.png') or ('.png?' in image_url.lower())):
                    await send_status(ctx, "error: only PNG images are supported.", status_msg=msg)
                    return
                import aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(image_url) as resp:
                        if resp.status != 200:
                            await send_status(ctx, "error: failed to download image from URL.", status_msg=msg)
                            return
                        with open(input_path, 'wb') as f:
                            f.write(await resp.read())
            else:
                await send_status(ctx, "error: please attach a PNG image or provide a direct PNG URL.", status_msg=msg)
                return

            # Import the embedder
            from cogs.utils.icc_embedder import embed_icc_profile
            await run_blocking(embed_icc_profile, input_path, output_path, icc_profile)

            # Send the result
            await send_file_checked(
                ctx,
                output_path,
                caption="done! output with ICC profile embedded.\n\nsave as > upload, do not copy image",
                status_msg=msg
            )
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)
            # Only delete output if not using saveas
            if not save_as and os.path.exists(output_path):
                os.remove(output_path)
        # (duplicate block removed)
            if os.path.exists(output_path):
                os.remove(output_path)
    def __init__(self, bot):
        self.bot = bot
        self.keys_file = "data/keys.json"
        self.generated_keys = self._load_keys()
        self.presets_file = "data/presets.json"
        self.presets = self._load_presets()
        self.keys_message_id = None  # Track live keys message for editing
        self.keys_channel_id = 1478989104497561642  # Channel to post keys
    
    def _load_keys(self):
        """Load keys from file if it exists"""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Failed to load keys file: {e}")
                return {}
        return {}

    def _load_presets(self):
        if os.path.exists(self.presets_file):
            try:
                with open(self.presets_file, 'r') as f:
                    raw = json.load(f)
                    # Normalize legacy format (name -> [steps]) to {name: {'owner': None, 'steps': [...]}}
                    normalized = {}
                    for k, v in raw.items():
                        if isinstance(v, list):
                            normalized[k] = {"owner": None, "steps": v}
                        elif isinstance(v, dict) and 'steps' in v:
                            normalized[k] = v
                        else:
                            # unknown format, skip
                            continue
                    return normalized
            except Exception as e:
                logger.error(f"Failed to load presets: {e}")
                return {}
        return {}

    def _save_presets(self):
        try:
            # Save in the normalized dict format
            with open(self.presets_file, 'w') as f:
                json.dump(self.presets, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save presets: {e}")
    
    def _save_keys(self):
        """Save keys to file"""
        with open(self.keys_file, "w") as f:
            json.dump(self.generated_keys, f, indent=2)

    def _get_unused_keys(self) -> list:
        """Get list of unused keys only"""
        return [k for k, v in self.generated_keys.items() if not v["used"]]

    async def _update_keys_message(self):
        """Update the live keys message in the channel"""
        if not self.keys_message_id:
            return
        try:
            channel = self.bot.get_channel(self.keys_channel_id)
            if not channel:
                return
            message = await channel.fetch_message(self.keys_message_id)
            unused = self._get_unused_keys()
            if not unused:
                await message.delete()
                self.keys_message_id = None
            else:
                key_list = "\n".join(unused)
                await message.edit(content=f"**available keys** ({len(unused)} remaining)\n\n```\n{key_list}\n```")
        except Exception as e:
            print(f"Failed to update keys message: {e}")

    @commands.command(name='hex')
    async def make_hex(self, ctx, audio_id: str = None):
        # Check if command is in DM or allowed channel
        if ctx.guild is not None and ctx.channel.id != 1458811026450546965:
            await send_status(ctx, "error: this command can only be used in DMs or in <#1458811026450546965>.")
            return
        
        # Check if user has the required role (check in mutual guild)
        has_role = False
        for guild in self.bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and any(r.id == 1458951498615750888 for r in member.roles):
                has_role = True
                break
        
        if not has_role:
            await send_status(ctx, "error: you don't have the required role.")
            return
        
        # Delete the command message instantly
        try:
            await ctx.message.delete()
        except:
            pass
        
        msg = await send_status(ctx, "generating hex...")
        if not audio_id:
            await send_status(ctx, "please provide an audio id.", status_msg=msg)
            return
        try:
            import random
            value = int(audio_id)
            await send_status(ctx, "warning: this only works on certain boomboxes, please use an audio you don't care about first and check f9 before using an audio you care about, also this is pretty easy to bypass, so it isn't 100%")
            hex_digits = format(value, "X")
            zeros_needed = 8164 - 2 - len(hex_digits)
            hex_string = "0x" + "0" * zeros_needed + hex_digits
            random_num = random.randint(100000, 999999)
            output_filename = f"hex_{random_num}.txt"
            await run_blocking(write_file, output_filename, hex_string.encode('utf-8'))
            # Save ID to IDs.txt (rotating)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _append_id_log(f"hash: {audio_id} - {ctx.author.name} - {ctx.author.id} - {timestamp}")
            await msg.delete()
            await send_status(ctx, file=discord.File(output_filename))
            if os.path.exists(output_filename): os.remove(output_filename)
        except ValueError:
            await send_status(ctx, "error: id must be a valid number.", status_msg=msg)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)

    @commands.command(name='hash')
    async def make_hash(self, ctx, target_id: str = None):
        # Check if command is in DM or allowed channel
        if ctx.guild is not None and ctx.channel.id != 1458811026450546965:
            await send_status(ctx, "error: this command can only be used in DMs or in <#1458811026450546965>.")
            return
        
        # Check if user has the required role (check in mutual guild)
        has_role = False
        for guild in self.bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and any(r.id == 1458951498615750888 for r in member.roles):
                has_role = True
                break
        
        if not has_role:
            await send_status(ctx, "error: you don't have the required role.")
            return
        
        if not target_id:
            await send_status(ctx, "error: need an id first.")
            return
        
        # Delete the command message instantly
        try:
            await ctx.message.delete()
        except:
            pass
        
        msg = await send_status(ctx, "generating...")
        try:
            import random
            final_string = await run_blocking(protected_id, target_id)
            random_num = random.randint(100000, 999999)
            filename = f"hash_{random_num}.txt"
            await run_blocking(write_file, filename, final_string.encode('utf-8'))
            # Save ID to IDs.txt (rotating)
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            _append_id_log(f"hash: {target_id} - {ctx.author.name} - {ctx.author.id} - {timestamp}")
            await msg.delete()
            await send_status(ctx, "only works on certain boomboxes", file=discord.File(filename))
            if os.path.exists(filename): os.remove(filename)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)

    @commands.command(name='rape')
    @commands.check(is_allowed_location)
    async def make_rape(self, ctx, user: discord.Member = None):
        if not user:
            await send_status(ctx, "mention someone.")
            return
        await send_status(ctx, f"*rapes {user.mention}*\nhttps://tenor.com/view/spiderman-lizard-backshot-gif-27712172")

    @commands.command(name='status')
    @commands.check(is_allowed_location)
    async def check_status(self, ctx):
        msg = await send_status(ctx, "checking providers...")
        from cogs.utils.network import check_providers
        results = await check_providers(self.bot.session)
        
        embed = discord.Embed(title="upload provider status", color=0xE1F6FF)
        for name, (status, lat) in results.items():
            emoji = "🟢" if status == 200 else "🔴"
            embed.add_field(name=f"{emoji} {name}", value=f"code: {status}\nping: {lat}", inline=False)
        
        await send_status(ctx, embed=embed, status_msg=msg)

    @commands.command(name='genkey')
    @commands.check(is_allowed_location)
    async def gen_key(self, ctx, count: int = 1):
        """Generate activation keys for the role"""
        if ctx.author.id != config.OWNER_ID:
            await send_status(ctx, "error: you don't have permission to generate keys.")
            return
        
        if count < 1 or count > 100:
            await send_status(ctx, "error: count must be between 1 and 100.")
            return
        
        keys = []
        for _ in range(count):
            key = secrets.token_urlsafe(32)
            self.generated_keys[key] = {
                "used": False,
                "user_id": None,
                "created_at": datetime.now().isoformat(),
                "redeemed_at": None
            }
            keys.append(key)
        
        self._save_keys()
        
        # Save keys to easy copy file
        with open("data/keys_copy.txt", "w") as f:
            f.write("\n".join(keys))
        
        await send_status(ctx, f"generated {count} key(s). check data/keys_copy.txt to copy them.")

    @commands.command(name='postkeys')
    async def post_keys(self, ctx):
        """Post a live message of available keys that updates on redemption (owner only)"""
        if ctx.author.id != config.OWNER_ID:
            await send_status(ctx, "error: owner only.")
            return
        
        try:
            channel = self.bot.get_channel(self.keys_channel_id)
            if not channel:
                await send_status(ctx, f"error: channel {self.keys_channel_id} not found.")
                return
            
            unused = self._get_unused_keys()
            if not unused:
                content = "❌ no keys available to post."
            else:
                key_list = "\n".join(unused)
                content = f"**available keys** ({len(unused)} total)\n\n```\n{key_list}\n```\n\nreply with `!redeem <key>` in <#1465525274874609817> to redeem."
            
            message = await channel.send(content)
            self.keys_message_id = message.id
            await send_status(ctx, f"posted keys message. link: {message.jump_url}")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='redeem')
    async def redeem_key(self, ctx, key: str = None):
        """Redeem an activation key to get the role"""
        if ctx.channel.id != 1465525274874609817:
            await send_status(ctx, "error: use this command in <#1465525274874609817>.")
            return
        
        if not key:
            await send_status(ctx, "error: please provide a key.")
            return
        
        if key not in self.generated_keys:
            await send_status(ctx, "error: invalid key.")
            return
        
        if self.generated_keys[key]["used"]:
            await send_status(ctx, "error: this key has already been used.")
            return
        
        # Check if user already redeemed a key
        for k, v in self.generated_keys.items():
            if v["used"] and v["user_id"] == ctx.author.id:
                await send_status(ctx, "error: you have already redeemed a key.")
                return
        
        try:
            role = ctx.guild.get_role(1458951498615750888)
            if not role:
                await send_status(ctx, "error: role not found.")
                return
            
            await ctx.author.add_roles(role)
            self.generated_keys[key]["used"] = True
            self.generated_keys[key]["user_id"] = ctx.author.id
            self.generated_keys[key]["redeemed_at"] = datetime.now().isoformat()
            # Assign redemption order
            redemption_count = sum(1 for data in self.generated_keys.values() if data["used"])
            self.generated_keys[key]["redemption_order"] = redemption_count
            self._save_keys()
            
            # Update the live keys message if it exists
            await self._update_keys_message()
            
            await send_status(ctx, f"you now have the role!")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='revoke')
    @commands.check(is_allowed_location)
    async def revoke_key(self, ctx, member: discord.Member = None):
        """Revoke a user's key and remove the role from them (owner only)"""
        if not any(r.id == 1458951003725369345 for r in ctx.author.roles):
            await send_status(ctx, "error: owner only.")
            return
        
        if not member:
            await send_status(ctx, "error: please mention a user.")
            return
        
        # Find the key for this user
        user_key = None
        for key, data in self.generated_keys.items():
            if data["used"] and data["user_id"] == member.id:
                user_key = key
                break
        
        if not user_key:
            await send_status(ctx, "error: this user has not redeemed a key.")
            return
        
        try:
            role = ctx.guild.get_role(1458951498615750888)
            if role:
                await member.remove_roles(role)
            
            # Delete the key
            del self.generated_keys[user_key]
            self._save_keys()
            
            await send_status(ctx, f"revoked key for {member.mention}.")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='whois')
    @commands.check(is_allowed_location)
    async def whois(self, ctx, member: discord.Member = None):
        """Show detailed user information including stats"""
        if not member:
            member = ctx.author
        
        # Find the key for this user
        key_data = None
        for key, data in self.generated_keys.items():
            if data["used"] and data["user_id"] == member.id:
                key_data = data
                break
        
        # Get user stats from bot
        user_stats = self.bot.command_stats.get("users", {}).get(str(member.id), {})
        total_cmds = user_stats.get("commands", 0)
        last_cmd = user_stats.get("last_command", "Never")
        
        if last_cmd != "Never":
            try:
                last_cmd_dt = datetime.fromisoformat(last_cmd)
                last_cmd = last_cmd_dt.strftime("%Y-%m-%d %H:%M:%S")
            except:
                pass
        
        embed = discord.Embed(color=0xE1F6FF, title="user profile")
        embed.set_author(name=member.name, icon_url=member.avatar.url if member.avatar else None)
        embed.set_thumbnail(url=member.avatar.url if member.avatar else None)
        
        # User info
        user_info = f"• **username** - {member.name}\n• **user id** - `{member.id}`\n• **joined discord** - <t:{int(member.created_at.timestamp())}:R>"
        embed.add_field(name="user info", value=user_info, inline=False)
        
        # Key status
        if key_data:
            redeemed_at = key_data.get("redeemed_at", "N/A")
            redemption_order = key_data.get("redemption_order", "N/A")
            try:
                redeemed_dt = datetime.fromisoformat(redeemed_at)
                redeemed_display = f"<t:{int(redeemed_dt.timestamp())}:R>"
            except:
                redeemed_display = redeemed_at
            key_info = f"• **uid** - #{redemption_order}\n• **key redeemed** - {redeemed_display}"
            embed.add_field(name="key status", value=key_info, inline=False)
        else:
            embed.add_field(name="key status", value="• no key redeemed", inline=False)
        
        # Bot activity
        activity = f"• **total commands** - `{total_cmds}`\n• **last command** - `{last_cmd}`"
        embed.add_field(name="bot activity", value=activity, inline=False)
        
        await send_status(ctx, embed=embed)

    @commands.command(name='createpreset')
    @commands.check(is_allowed_location)
    async def create_preset(self, ctx, name: str = None, *tokens):
        """Create or overwrite a preset. Usage: !createpreset name step1 step2 ..."""
        if not name:
            await send_status(ctx, "error: please provide a preset name and at least one step.")
            return
        if not tokens:
            await send_status(ctx, "error: please provide at least one processing step.")
            return
        # enforce a maximum of 7 steps per preset
        if len(tokens) > 7:
            await send_status(ctx, "error: too many steps; maximum is 7.")
            return
        key = name.lower()
        self.presets[key] = {"owner": ctx.author.id, "steps": [t.lower() for t in tokens]}
        self._save_presets()
        await send_status(ctx, f"preset '{key}' saved. steps: {', '.join(self.presets[key]['steps'])}")

    @commands.command(name='presets')
    @commands.check(is_allowed_location)
    async def list_presets(self, ctx):
        """List saved presets."""
        if not self.presets:
            await send_status(ctx, "no presets saved.")
            return
        embed = discord.Embed(title="presets", color=0xE1F6FF)
        embed.set_footer(text="Use !preset <name> to run a preset")

        lines = []
        for name, v in self.presets.items():
            steps = v['steps'] if isinstance(v, dict) and 'steps' in v else (v if isinstance(v, list) else [])
            owner_id = v.get('owner') if isinstance(v, dict) else None
            owner_name = "unknown"
            if owner_id:
                try:
                    user = self.bot.get_user(owner_id) or await self.bot.fetch_user(owner_id)
                    owner_name = f"{user.name}#{user.discriminator}" if getattr(user, 'discriminator', None) is not None else user.name
                except Exception:
                    owner_name = str(owner_id)

            steps_str = ' '.join(steps)
            if len(steps_str) > 100:
                steps_str = steps_str[:97] + '...'

            # Escape angle brackets to prevent mentions/links
            safe_name = name.replace('<', '\u200b<').replace('>', '>\u200b')
            safe_steps = steps_str.replace('<', '\u200b<').replace('>', '>\u200b')

            lines.append(f"{safe_name} | {len(steps)} steps | {owner_name} | {safe_steps}")

        # Chunk lines into embed fields without spamming (max ~1024 chars per field)
        if not lines:
            await send_status(ctx, "no presets saved.")
            return

        field_lines = []
        current = []
        cur_len = 0
        for ln in lines:
            if cur_len + len(ln) + 1 > 900 and current:
                field_lines.append('\n'.join(current))
                current = [ln]
                cur_len = len(ln) + 1
            else:
                current.append(ln)
                cur_len += len(ln) + 1
        if current:
            field_lines.append('\n'.join(current))

        for idx, block in enumerate(field_lines):
            # use invisible name for compact look after the title
            field_name = "\u200b" if idx > 0 else "\u200b"
            embed.add_field(name=field_name, value=block, inline=False)

        await send_status(ctx, embed=embed)

    @commands.command(name='preset')
    @commands.check(is_allowed_location)
    async def run_preset(self, ctx, name: str = None, url: str = None):
        """Run a saved preset. Usage: !preset name [url_or_attach]
        The command downloads an attachment or URL (discord CDN only) and applies the preset steps in order."""
        if not name:
            await send_status(ctx, "error: please provide a preset name.")
            return
        key = name.lower()
        if key not in self.presets:
            await send_status(ctx, "error: preset not found.")
            return

        # support both normalized dict format and legacy list format
        entry = self.presets.get(key)
        if isinstance(entry, dict) and 'steps' in entry:
            steps = entry['steps']
        elif isinstance(entry, list):
            steps = entry
        else:
            await send_status(ctx, "error: preset is malformed.")
            return
        # if preset contains fullbait, run status and final result in DMs to avoid posting in channel
        dm_mode = any((isinstance(s, str) and s.strip().split()[0] == 'fullbait') for s in steps)
        msg = await send_status(ctx, "initializing preset...", to_dm=dm_mode)
        # Download initial input
        try:
            in_path, original_filename = await download_file(ctx, url, status_msg=msg)
            if not in_path:
                return
            current_path = in_path
            # default desired format is original ext
            if '.' in (original_filename or ''):
                desired_format = original_filename.split('.')[-1].lower()
            else:
                desired_format = 'mp3'
            stereo_label = None
            for i, step in enumerate(steps):
                # format specifier
                if step in ('mp3','ogg','wav','flac','m4a','aac'):
                    desired_format = step
                    continue

                await send_status(ctx, f"running step {i+1}/{len(steps)}: {step}...", status_msg=msg)

                # effects that accept (input_path, output_path, export_format)
                format_effects = {
                    'loud': ap.process_loud,
                    'loudv2': ap.process_loudv2,
                    '2db': ap.process_2db,
                    'nobass': ap.process_nobass,
                    'convert': ap.process_convert
                }

                if step in format_effects:
                    out_path = f"out_{uuid.uuid4().hex}.{desired_format}"
                    await run_blocking(format_effects[step], current_path, out_path, desired_format)
                    # cleanup previous
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    continue

                # createchannels step: e.g. 'createchannels 32'
                if step.startswith('createchannels'):
                    parts = step.split()
                    if len(parts) == 2 and parts[1].isdigit():
                        num_channels = int(parts[1])
                        out_path = f"channels_{uuid.uuid4().hex}.wav"
                        await run_blocking(ap.process_create_channels, current_path, out_path, num_channels)
                        try:
                            if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                        except: pass
                        current_path = out_path
                        continue
                    else:
                        await send_status(ctx, "error: createchannels step must be in format 'createchannels <num_channels>'", status_msg=msg)
                        return

                # mp3bait step: e.g. 'mp3bait decoy.mp3 hidden.mp3'
                if step.startswith('mp3bait'):
                    parts = step.split()
                    if len(parts) == 3:
                        # Validate that preset paths refer to audio files to avoid arbitrary local paths
                        AUDIO_EXTS = {'.mp3', '.ogg', '.wav', '.flac', '.m4a'}
                        if not (os.path.splitext(parts[1])[1].lower() in AUDIO_EXTS and
                                os.path.splitext(parts[2])[1].lower() in AUDIO_EXTS):
                            await send_status(ctx, "error: mp3bait paths must be audio files.", status_msg=msg)
                            return
                        decoy_path = parts[1]
                        hidden_path = parts[2]
                        out_path = f"mp3bait_{uuid.uuid4().hex}.mp3"
                        await run_blocking(ap.process_mp3bait, decoy_path, hidden_path, out_path)
                        try:
                            if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                        except: pass
                        current_path = out_path
                        continue
                    else:
                        await send_status(ctx, "error: mp3bait step must be in format 'mp3bait <decoy_path> <hidden_path>'", status_msg=msg)
                        return

                if step == 'compress':
                    out_path = f"out_{uuid.uuid4().hex}.{desired_format}"
                    await run_blocking(ap.process_compression, current_path, out_path)
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    continue

                if step == 'fullbait':
                    # access depends on global mode
                    mode = get_fullbait_mode()
                    author_roles = getattr(ctx.author, "roles", []) or []
                    has_required_role = any(getattr(r, "id", None) == config.ISRAELITE_ROLE_ID for r in author_roles)
                    if mode == 'role_only' and not has_required_role:
                        await send_status(ctx, "error: you don't have the required role to use fullbait.", status_msg=msg)
                        return

                    # find fullbaits dir
                    fullbaits_dir = os.path.join(os.path.dirname(config.BAIT_DIRECTORY), "fullbaits")
                    if not os.path.exists(fullbaits_dir): fullbaits_dir = "assets/fullbaits"
                    if not os.path.exists(fullbaits_dir):
                        await send_status(ctx, "error: fullbaits directory not found.", status_msg=msg)
                        return

                    all_baits = [f for f in os.listdir(fullbaits_dir) if f.endswith('.ogg')]
                    if not all_baits:
                        await send_status(ctx, "error: no .ogg files in fullbaits directory.", status_msg=msg)
                        return

                    selected_bait = random.choice(all_baits)
                    bait_path = os.path.join(fullbaits_dir, selected_bait)
                    out_path = f"fullbait_{uuid.uuid4().hex}.ogg"
                    if mode == 'everyone_watermark':
                        should_watermark = True
                    else:
                        should_watermark = not any(getattr(r, "id", None) == config.ISRAELITE_ROLE_ID for r in ctx.author.roles)
                    await run_blocking(ap.process_fullbait, current_path, out_path, bait_path, add_watermark=should_watermark)
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    continue

                if step == 'stereobait':
                    # choose effect1 from stereobait_files and build 32-channel file
                    stereobait_dir = os.path.join(os.path.dirname(config.BAIT_DIRECTORY), "stereobait_files")
                    if not os.path.exists(stereobait_dir): stereobait_dir = os.path.join('assets', 'stereobait_files')
                    if not os.path.exists(stereobait_dir):
                        await send_status(ctx, "error: stereobait_files directory not found for preset.", status_msg=msg)
                        return
                    all_choices = [f for f in os.listdir(stereobait_dir) if os.path.isfile(os.path.join(stereobait_dir, f)) and f.lower().endswith(('.ogg', '.mp3', '.wav', '.flac', '.m4a'))]
                    if not all_choices:
                        await send_status(ctx, "error: no audio files in stereobait_files directory for preset.", status_msg=msg)
                        return
                    selected_name = random.choice(all_choices)
                    effect1 = os.path.join(stereobait_dir, selected_name)
                    out_path = f"stereobait_{uuid.uuid4().hex}.ogg"
                    await run_blocking(ap.process_stereobait, effect1, current_path, out_path)
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    stereo_label = selected_name
                    continue

                if step == '32mono' or step == '32-mono' or step == '32_mon o':
                    # ensure ogg input (original command required .ogg)
                    if not current_path.lower().endswith('.ogg'):
                        tmp_ogg = f"out_{uuid.uuid4().hex}.ogg"
                        await run_blocking(ap.process_convert, current_path, tmp_ogg, 'ogg')
                        try:
                            if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                        except: pass
                        current_path = tmp_ogg

                    # choose a bait from config.BAIT_DIRECTORY
                    bait_dir = config.BAIT_DIRECTORY if os.path.exists(config.BAIT_DIRECTORY) else None
                    if not bait_dir:
                        # try assets folder fallback
                        bait_dir = os.path.join('assets', 'fullbaits') if os.path.exists(os.path.join('assets', 'fullbaits')) else None
                    if not bait_dir:
                        await send_status(ctx, "error: bait directory not found for 32mono step.", status_msg=msg)
                        return
                    all_baits = [f for f in os.listdir(bait_dir) if os.path.isfile(os.path.join(bait_dir, f))]
                    valid_baits = [f for f in all_baits if f.lower().endswith(('.mp3', '.ogg', '.wav', '.flac'))]
                    if not valid_baits:
                        await send_status(ctx, "error: no audio files in bait directory for 32mono.", status_msg=msg)
                        return
                    selected_bait_name = random.choice(valid_baits)
                    selected_bait_path = os.path.join(bait_dir, selected_bait_name)
                    out_path = f"32mono_{uuid.uuid4().hex}.mp3"
                    should_watermark = not any(getattr(r, "id", None) == config.ISRAELITE_ROLE_ID for r in ctx.author.roles)
                    await run_blocking(ap.process_32mono, current_path, out_path, selected_bait_path, add_watermark=should_watermark)
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    continue

                if step == 'img':
                    # ensure mp3 for embedding
                    if not current_path.lower().endswith('.mp3'):
                        tmp_mp3 = f"out_{uuid.uuid4().hex}.mp3"
                        await run_blocking(ap.process_convert, current_path, tmp_mp3, 'mp3')
                        try:
                            if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                        except: pass
                        current_path = tmp_mp3

                    # choose random image
                    img_dir = os.path.join('assets', 'img baits')
                    if not os.path.exists(img_dir): img_dir = 'assets/img baits'
                    if not os.path.exists(img_dir):
                        await send_status(ctx, "error: img baits directory not found for img step.", status_msg=msg)
                        return
                    images = [f for f in os.listdir(img_dir) if os.path.isfile(os.path.join(img_dir, f)) and f.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.bmp'))]
                    if not images:
                        await send_status(ctx, "error: no images available for img step.", status_msg=msg)
                        return
                    selected = random.choice(images)
                    selected_path = os.path.join(img_dir, selected)
                    out_path = f"img_{uuid.uuid4().hex}.png"
                    await run_blocking(ap.process_img_bait, selected_path, current_path, out_path)
                    try:
                        if current_path != in_path and os.path.exists(current_path): os.remove(current_path)
                    except: pass
                    current_path = out_path
                    continue

                # unknown step
                await send_status(ctx, f"error: unknown step '{step}' in preset.", status_msg=msg)
                return

            # check final file size before uploading
            try:
                size_mb = os.path.getsize(current_path) / (1024 * 1024)
            except Exception:
                size_mb = 0

            if size_mb > 17.5:
                try:
                    await send_status(ctx, "it's over 17.5mb, cut down your file", status_msg=msg)
                except:
                    try: await send_status(ctx, "it's over 17.5mb, cut down your file")
                    except: pass
                return

            # upload final file
            await send_status(ctx, "uploading final result...", status_msg=msg)
            link = await upload_file(self.bot.session, current_path, status_msg=msg)
            if link:
                try:
                    if stereo_label:
                        text = (f"{ctx.author.mention} done: {link}\n"
                                f"when uploading, call it {stereo_label}\n"
                                "works best on kornet")
                        if dm_mode:
                            await send_status(ctx, text, to_dm=True)
                        else:
                            await send_status(ctx, text)
                    else:
                        if dm_mode:
                            await send_status(ctx, f"done: {link}", to_dm=True)
                        else:
                            await send_status(ctx, f"{ctx.author.mention} done: {link}")
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)
            else:
                # fallback: try to send file directly
                try:
                    if stereo_label:
                        caption = (f"{ctx.author.mention} done:\n"
                                   f"when uploading, call it {stereo_label}\n"
                                   "works best on kornet")
                        if dm_mode:
                            await send_status(ctx, caption, file=discord.File(current_path, filename=stereo_label), to_dm=True)
                        else:
                            await send_status(ctx, caption, file=discord.File(current_path, filename=stereo_label))
                    else:
                        if dm_mode:
                            await send_status(ctx, file=discord.File(current_path), to_dm=True)
                        else:
                            await send_status(ctx, f"{ctx.author.mention} done:", file=discord.File(current_path))
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            try:
                if 'current_path' in locals() and os.path.exists(current_path): os.remove(current_path)
            except: pass
            try:
                if 'in_path' in locals() and os.path.exists(in_path): os.remove(in_path)
            except: pass
            if ctx.author.id in self.bot.active_tasks:
                del self.bot.active_tasks[ctx.author.id]

    @commands.command(name='stereobait')
    @commands.check(is_allowed_location)
    async def stereobait(self, ctx, url: str = None):
        """Create a 32-channel stereobait using a random asset as effect1 and
        the provided file (attachment or discord CDN url) as effect2."""
        msg = await send_status(ctx, "creating stereobait...")
        in_path = None
        out_path = None
        try:
            in_path, original = await download_file(ctx, url, status_msg=msg)
            if not in_path:
                return

            # locate stereobait assets
            stereobait_dir = r"C:\Users\User\Desktop\folder where every other folder is\coding stuff ;3\cinnamon\optimized cinnamon\assets\stereobait_files"
            if not os.path.exists(stereobait_dir):
                stereobait_dir = os.path.join('assets', 'stereobait_files')
            if not os.path.exists(stereobait_dir):
                await send_status(ctx, "error: stereobait_files directory not found.", status_msg=msg)
                return

            candidates = [f for f in os.listdir(stereobait_dir) if os.path.isfile(os.path.join(stereobait_dir, f)) and f.lower().endswith(('.ogg', '.mp3', '.wav', '.flac', '.m4a'))]
            if not candidates:
                await send_status(ctx, "error: no audio files in stereobait_files directory.", status_msg=msg)
                return
            selected_name = random.choice(candidates)
            effect1 = os.path.join(stereobait_dir, selected_name)
            out_path = f"stereobait_{uuid.uuid4().hex}.ogg"

            await run_blocking(ap.process_stereobait, effect1, in_path, out_path)

            # check final size and refuse upload if too large
            try:
                size_mb = os.path.getsize(out_path) / (1024 * 1024)
            except Exception:
                size_mb = 0

            if size_mb > 17.5:
                try:
                    await send_status(ctx, "it's over 17.5mb, cut down your file", status_msg=msg)
                except:
                    try: await send_status(ctx, "it's over 17.5mb, cut down your file")
                    except: pass
                return

            await send_status(ctx, "uploading final result...", status_msg=msg)
            link = await upload_file(self.bot.session, out_path, status_msg=msg)
            if link:
                try:
                    text = (f"{ctx.author.mention} done: {link}\n"
                            f"when uploading, call it {selected_name}\n"
                            "works best on kornet")
                    await send_status(ctx, text)
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)
            else:
                try:
                    caption = (f"{ctx.author.mention} done:\n"
                               f"when uploading, call it {selected_name}\n"
                               "works best on kornet")
                    await send_status(ctx, caption, file=discord.File(out_path, filename=selected_name))
                except Exception as e:
                    await send_error(ctx, e, status_msg=msg)

        except Exception as e:
            await send_error(ctx, e, status_msg=msg)
        finally:
            try:
                if in_path and os.path.exists(in_path): os.remove(in_path)
            except: pass
            try:
                if out_path and os.path.exists(out_path): os.remove(out_path)
            except: pass

    @commands.command(name='stats')
    @commands.check(is_allowed_location)
    async def show_stats(self, ctx, timeframe: str = None):
        """Show bot usage statistics with optional timeframe (hour/day/week or 'graph' for velocity chart)"""
        
        # If timeframe is 'graph', show the velocity graph
        if timeframe and timeframe.lower() == 'graph':
            await self._show_graph_stats(ctx)
            return
        
        # Use enhanced stats system for other views
        if timeframe and timeframe.lower() in ['hour', 'day', 'week']:
            try:
                from cogs.utils.enhanced_stats import StatsAnalyzer, create_stats_embed
                analyzer = StatsAnalyzer(self.bot.stats_file, self.bot.history_file)
                embed = create_stats_embed(analyzer, timeframe=timeframe.lower())
                await ctx.send(embed=embed)
                return
            except Exception as e:
                print(f"Enhanced stats error: {e}")
                # Fall back to basic stats
        
        # Default: show basic stats with overview
        await self._show_basic_stats(ctx)
    
    async def _show_basic_stats(self, ctx):
        """Show basic stats overview"""
        stats = self.bot.command_stats
        total_cmds = stats.get("total_commands", 0)
        commands = stats.get("commands", {})
        users = stats.get("users", {})
        history = self.bot.command_history
        errors = stats.get("errors", {})
        
        # Calculate most popular time of day
        hour_counts = [0] * 24
        for entry in history:
            try:
                hour = entry[2] if isinstance(entry, list) else entry.get("hour")
                if hour is not None and 0 <= hour < 24:
                    hour_counts[hour] += 1
            except (IndexError, KeyError, TypeError):
                continue
        
        if sum(hour_counts) > 0:
            peak_hour = hour_counts.index(max(hour_counts))
            peak_hour_str = f"{peak_hour:02d}:00"
        else:
            peak_hour_str = "n/a"
        
        embed = discord.Embed(title="bot statistics", color=0xE1F6FF)
        
        # Overview
        overview = f"• **total commands** - `{total_cmds}`\n• **total users** - `{len(users)}`\n• **unique commands** - `{len(commands)}`\n• **peak hour** - `{peak_hour_str}`"
        embed.add_field(name="overview", value=overview, inline=False)
        
        # Top 5 most used commands
        if commands:
            sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)[:5]
            top_cmds = "\n".join([f"• **{i+1}. {cmd}** - {count} uses" for i, (cmd, count) in enumerate(sorted_cmds)])
            embed.add_field(name="top commands", value=top_cmds, inline=False)
        
        # Error rates per command
        if errors:
            total_errors = sum(errors.values())
            sorted_errors = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:3]
            error_lines = []
            for cmd, err_count in sorted_errors:
                cmd_total = commands.get(cmd, 0) + err_count
                error_rate = (err_count / cmd_total * 100) if cmd_total > 0 else 0
                error_lines.append(f"• **{cmd}** - {err_count} errors ({error_rate:.1f}%)")
            embed.add_field(name="errors", value="\n".join(error_lines) if error_lines else "• none", inline=False)
        
        # Top 5 most active users
        if users:
            sorted_users = sorted(users.items(), key=lambda x: x[1].get("commands", 0), reverse=True)[:5]
            top_users_list = []
            for i, (user_id, data) in enumerate(sorted_users):
                username = data.get("username", "unknown")
                top_users_list.append(f"• **{i+1}. {username}** - {data.get('commands', 0)} commands")
            top_users = "\n".join(top_users_list)
            embed.add_field(name="top users", value=top_users, inline=False)
        
        embed.set_footer(text="use !stats <hour/day/week> for timeframe view • !stats graph for velocity chart")
        await ctx.send(embed=embed)
    
    async def _show_graph_stats(self, ctx):
        """Show velocity graph stats (original implementation)"""
        stats = self.bot.command_stats
        total_cmds = stats.get("total_commands", 0)
        commands = stats.get("commands", {})
        users = stats.get("users", {})
        history = self.bot.command_history  # Load from separate history file
        errors = stats.get("errors", {})
        
        # Calculate most popular time of day
        hour_counts = [0] * 24
        for entry in history:
            try:
                # Handle compact format: [cmd, timestamp, hour]
                hour = entry[2] if isinstance(entry, list) else entry.get("hour")
                if hour is not None and 0 <= hour < 24:
                    hour_counts[hour] += 1
            except (IndexError, KeyError, TypeError):
                continue
        
        if sum(hour_counts) > 0:
            peak_hour = hour_counts.index(max(hour_counts))
            peak_hour_str = f"{peak_hour:02d}:00"
        else:
            peak_hour_str = "n/a"
        
        # Generate velocity graph if we have history
        graph_path = None
        if history and len(history) > 1:
            try:
                import matplotlib
                matplotlib.use('Agg')
                import matplotlib.pyplot as plt
                from datetime import datetime, timedelta
                from collections import defaultdict
                
                # Parse timestamps and count commands per hour
                hourly_counts = defaultdict(int)
                for entry in history:
                    try:
                        # Handle compact format: [cmd, timestamp, hour]
                        timestamp_str = entry[1] if isinstance(entry, list) else entry["timestamp"]
                        dt = datetime.fromisoformat(timestamp_str)
                        # Round to nearest hour
                        hour = dt.replace(minute=0, second=0, microsecond=0)
                        hourly_counts[hour] += 1
                    except:
                        continue
                
                if hourly_counts:
                    if len(hours) > 2:
                        # Convert datetimes to numeric values
                        hours_num = mdates.date2num(hours)

                        # Create smooth interpolation
                        from scipy.interpolate import make_interp_spline
                        x_smooth = np.linspace(hours_num[0], hours_num[-1], 300)
                        k_degree = min(3, len(hours) - 1)
                        if k_degree > 0:
                            spline = make_interp_spline(hours_num, counts, k=k_degree)
                            y_smooth = spline(x_smooth)
                        else:
                            # Not enough points for spline, use linear
                            y_smooth = np.interp(x_smooth, hours_num, counts)

                        # Plot smooth line
                        ax.plot_date(x_smooth, y_smooth, '-', linewidth=3, color='#5865f2', zorder=3, 
                                    solid_capstyle='round', antialiased=True)
                        ax.fill_between(x_smooth, y_smooth, alpha=0.25, color='#5865f2', zorder=2)

                        # Add dots at actual data points
                        ax.plot_date(hours_num, counts, 'o', markersize=8, color='#5865f2', 
                                    markeredgecolor='#ffffff', markeredgewidth=2, zorder=5)
                    else:
                        # Not enough points for smooth curve, plot normally
                        ax.plot(hours, counts, linewidth=3, color='#5865f2', zorder=3, 
                               solid_capstyle='round', antialiased=True)
                        ax.fill_between(hours, counts, alpha=0.25, color='#5865f2', zorder=2)
                        ax.scatter(hours, counts, s=50, color='#5865f2', edgecolors='#ffffff', 
                                 linewidths=2, zorder=5)
                    
                    # Format x-axis for dates
                    ax.xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
                    
                    # Clean labels (all lowercase)
                    ax.set_xlabel('time', fontsize=12, color='#b5bac1', labelpad=10)
                    ax.set_ylabel('commands/hour', fontsize=12, color='#b5bac1', labelpad=10)
                    ax.set_title('command velocity', fontsize=15, color='#ffffff', 
                               fontweight='600', pad=15)
                    
                    # Minimal grid
                    ax.grid(True, alpha=0.1, color='#4e5058', linestyle='-', linewidth=1)
                    ax.set_axisbelow(True)
                    
                    # Clean ticks
                    ax.tick_params(colors='#b5bac1', labelsize=9, length=4)
                    plt.xticks(rotation=30, ha='right')
                    
                    # Minimal borders
                    for spine in ['top', 'right']:
                        ax.spines[spine].set_visible(False)
                    for spine in ['bottom', 'left']:
                        ax.spines[spine].set_color('#4e5058')
                        ax.spines[spine].set_linewidth(1)
                    
                    plt.tight_layout()
                    
                    # Save graph
                    graph_path = f"stats_graph_{ctx.author.id}.png"
                    plt.savefig(graph_path, dpi=200, bbox_inches='tight', 
                              facecolor='#2b2d31', edgecolor='none')
                    plt.close()
            except Exception as e:
                print(f"Graph generation error: {e}")
        
        embed = discord.Embed(title="bot statistics", color=0xE1F6FF)
        
        # Overview
        overview = f"• **total commands** - `{total_cmds}`\n• **total users** - `{len(users)}`\n• **unique commands** - `{len(commands)}`\n• **peak hour** - `{peak_hour_str}`"
        embed.add_field(name="overview", value=overview, inline=False)
        
        # Top 5 most used commands
        if commands:
            sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)[:5]
            top_cmds = "\n".join([f"• **{i+1}. {cmd}** - {count} uses" for i, (cmd, count) in enumerate(sorted_cmds)])
            embed.add_field(name="top commands", value=top_cmds, inline=False)
        
        # Error rates per command
        if errors:
            total_errors = sum(errors.values())
            sorted_errors = sorted(errors.items(), key=lambda x: x[1], reverse=True)[:3]
            error_lines = []
            for cmd, err_count in sorted_errors:
                cmd_total = commands.get(cmd, 0) + err_count
                error_rate = (err_count / cmd_total * 100) if cmd_total > 0 else 0
                error_lines.append(f"• **{cmd}** - {err_count} errors ({error_rate:.1f}%)")
            embed.add_field(name="errors", value="\n".join(error_lines) if error_lines else "• none", inline=False)
        
        # Top 5 most active users
        if users:
            sorted_users = sorted(users.items(), key=lambda x: x[1].get("commands", 0), reverse=True)[:5]
            top_users_list = []
            for i, (user_id, data) in enumerate(sorted_users):
                username = data.get("username", "unknown")
                top_users_list.append(f"• **{i+1}. {username}** - {data.get('commands', 0)} commands")
            top_users = "\n".join(top_users_list)
            embed.add_field(name="top users", value=top_users, inline=False)
        
        # Send with graph if available
        if graph_path and os.path.exists(graph_path):
            file = discord.File(graph_path, filename="velocity.png")
            embed.set_image(url="attachment://velocity.png")
            await send_status(ctx, embed=embed, file=file)
            os.remove(graph_path)
        else:
            await send_status(ctx, embed=embed)

    @commands.command(name='presetdelete')
    @commands.check(is_allowed_location)
    async def delete_preset(self, ctx, name: str = None):
        """Delete a preset you created. Usage: !presetdelete name"""
        if not name:
            await send_status(ctx, "error: please provide a preset name to delete.")
            return
        key = name.lower()
        if key not in self.presets:
            await send_status(ctx, "error: preset not found.")
            return
        entry = self.presets.get(key)
        owner = entry.get('owner') if isinstance(entry, dict) else None
        # allow deletion if owner matches or user has owner role
        is_owner_role = any(getattr(r, 'id', None) == 1458951003725369345 for r in ctx.author.roles)
        if owner is not None and owner != ctx.author.id and not is_owner_role:
            await send_status(ctx, "error: you can only delete presets you created.")
            return
        # delete and save
        try:
            del self.presets[key]
            self._save_presets()
            await send_status(ctx, f"preset '{key}' deleted.")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='cancel')
    async def cancel_task(self, ctx):
        """Cancel your current processing task"""
        user_id = ctx.author.id
        
        if user_id not in self.bot.active_tasks:
            await send_status(ctx, "error: you don't have any active tasks running.")
            return
        
        task_info = self.bot.active_tasks[user_id]
        task_msg = task_info.get("message")
        files = task_info.get("files", [])
        
        # Delete any downloaded files
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except:
                pass
        
        # Remove from active tasks
        del self.bot.active_tasks[user_id]
        
        if task_msg:
            try:
                await send_status(ctx, "ok! canceled", status_msg=task_msg)
            except:
                await send_status(ctx, "ok! canceled")
        else:
            await send_status(ctx, "ok! canceled")

    @commands.command(name='nuke')
    async def nuke_channel(self, ctx):
        """Delete all messages in the channel (owner only)"""
        if not any(r.id == 1458951003725369345 for r in ctx.author.roles):
            await send_status(ctx, "error: owner only.")
            return
        
        try:
            deleted = await ctx.channel.purge(limit=None, bulk=True)
            await send_status(ctx, f"nuked {len(deleted)} messages.")
        except Exception as e:
            await send_error(ctx, e)

async def setup(bot):
    await bot.add_cog(ToolCommands(bot))
