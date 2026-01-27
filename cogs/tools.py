import discord
from discord.ext import commands
import os
import json
import secrets
from datetime import datetime
from cogs.utils.helpers import run_blocking, is_allowed_location, send_error, write_file, protected_id
import config

class ToolCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.keys_file = "keys.json"
        self.generated_keys = self._load_keys()
    
    def _load_keys(self):
        """Load keys from file if it exists"""
        if os.path.exists(self.keys_file):
            try:
                with open(self.keys_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def _save_keys(self):
        """Save keys to file"""
        with open(self.keys_file, "w") as f:
            json.dump(self.generated_keys, f, indent=2)

    @commands.command(name='hex')
    @commands.check(is_allowed_location)
    async def make_hex(self, ctx, audio_id: str = None):
        msg = await ctx.send("generating hex...")
        if not audio_id:
            await msg.edit(content="please provide an audio id.")
            return
        try:
            value = int(audio_id)
            await ctx.send("WARNING: this only works on certain boomboxes, please use an audio you don't care about first and check f9 before using an audio you care about, also this is pretty easy to bypass, so it isn't 100%")
            hex_digits = format(value, "X")
            zeros_needed = 8164 - 2 - len(hex_digits)
            hex_string = "0x" + "0" * zeros_needed + hex_digits
            output_filename = f"hex_{audio_id}.txt"
            await run_blocking(write_file, output_filename, hex_string.encode('utf-8'))
            # Save ID to IDs.txt
            with open("IDs.txt", "a") as f:
                f.write(f"hex: {audio_id}\n")
            await msg.delete()
            await ctx.send(file=discord.File(output_filename))
            if os.path.exists(output_filename): os.remove(output_filename)
        except ValueError:
            await msg.edit(content="error: id must be a valid number.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)

    @commands.command(name='hash')
    @commands.check(is_allowed_location)
    async def make_hash(self, ctx, target_id: str = None):
        if not target_id:
            await ctx.send("need an id first.")
            return
        msg = await ctx.send("generating...")
        try:
            final_string = await run_blocking(protected_id, target_id)
            filename = f"hash_{target_id}.txt"
            await run_blocking(write_file, filename, final_string.encode('utf-8'))
            # Save ID to IDs.txt
            with open("IDs.txt", "a") as f:
                f.write(f"hash: {target_id}\n")
            await msg.delete()
            await ctx.send("only works on certain boomboxes", file=discord.File(filename))
            if os.path.exists(filename): os.remove(filename)
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)

    @commands.command(name='rape')
    @commands.check(is_allowed_location)
    async def make_rape(self, ctx, user: discord.Member = None):
        if not user:
            await ctx.send("mention someone.")
            return
        await ctx.send(f"*rapes {user.mention}*\nhttps://tenor.com/view/spiderman-lizard-backshot-gif-27712172")

    @commands.command(name='status')
    @commands.check(is_allowed_location)
    async def check_status(self, ctx):
        msg = await ctx.send("checking providers...")
        from cogs.utils.network import check_providers
        results = await check_providers(self.bot.session)
        
        embed = discord.Embed(title="upload provider status", color=0xE1F6FF)
        for name, (status, lat) in results.items():
            emoji = "🟢" if status == 200 else "🔴"
            embed.add_field(name=f"{emoji} {name}", value=f"code: {status}\nping: {lat}", inline=False)
        
        await msg.edit(content=None, embed=embed)

    @commands.command(name='genkey')
    @commands.check(is_allowed_location)
    async def gen_key(self, ctx, count: int = 1):
        """Generate activation keys for the role"""
        if ctx.author.id != 1423665222870241422:
            await ctx.send("error: you don't have permission to generate keys.")
            return
        
        if count < 1 or count > 100:
            await ctx.send("error: count must be between 1 and 100.")
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
        await ctx.send(f"generated {count} key(s).")

    @commands.command(name='redeem')
    async def redeem_key(self, ctx, key: str = None):
        """Redeem an activation key to get the role"""
        if ctx.channel.id != 1465525274874609817:
            await ctx.send("error: use this command in <#1465525274874609817>.")
            return
        
        if not key:
            await ctx.send("error: please provide a key.")
            return
        
        if key not in self.generated_keys:
            await ctx.send("error: invalid key.")
            return
        
        if self.generated_keys[key]["used"]:
            await ctx.send("error: this key has already been used.")
            return
        
        # Check if user already redeemed a key
        for k, v in self.generated_keys.items():
            if v["used"] and v["user_id"] == ctx.author.id:
                await ctx.send("error: you have already redeemed a key.")
                return
        
        try:
            role = ctx.guild.get_role(1458951498615750888)
            if not role:
                await ctx.send("error: role not found.")
                return
            
            await ctx.author.add_roles(role)
            self.generated_keys[key]["used"] = True
            self.generated_keys[key]["user_id"] = ctx.author.id
            self.generated_keys[key]["redeemed_at"] = datetime.now().isoformat()
            # Assign redemption order
            redemption_count = sum(1 for data in self.generated_keys.values() if data["used"])
            self.generated_keys[key]["redemption_order"] = redemption_count
            self._save_keys()
            
            await ctx.send(f"you now have the role!")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='revoke')
    @commands.check(is_allowed_location)
    async def revoke_key(self, ctx, member: discord.Member = None):
        """Revoke a user's key and remove the role from them (owner only)"""
        if not any(r.id == 1458951003725369345 for r in ctx.author.roles):
            await ctx.send("error: owner only.")
            return
        
        if not member:
            await ctx.send("error: please mention a user.")
            return
        
        # Find the key for this user
        user_key = None
        for key, data in self.generated_keys.items():
            if data["used"] and data["user_id"] == member.id:
                user_key = key
                break
        
        if not user_key:
            await ctx.send("error: this user has not redeemed a key.")
            return
        
        try:
            role = ctx.guild.get_role(1458951498615750888)
            if role:
                await member.remove_roles(role)
            
            # Delete the key
            del self.generated_keys[user_key]
            self._save_keys()
            
            await ctx.send(f"revoked key for {member.mention}.")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='whois')
    @commands.check(is_allowed_location)
    async def whois(self, ctx, member: discord.Member = None):
        """Show when a user redeemed their key and their redemption number"""
        if not member:
            await ctx.send("error: please mention a user.")
            return
        
        # Find the key for this user
        for key, data in self.generated_keys.items():
            if data["used"] and data["user_id"] == member.id:
                redeemed_at = data.get("redeemed_at", "N/A")
                redemption_order = data.get("redemption_order", "N/A")
                
                embed = discord.Embed(color=0xE1F6FF)
                embed.set_author(name=member.name, icon_url=member.avatar.url)
                embed.add_field(name="UID", value=f"#{redemption_order}", inline=False)
                embed.add_field(name="User", value=member.mention, inline=False)
                embed.add_field(name="Redeemed", value=redeemed_at, inline=False)
                embed.set_thumbnail(url=member.avatar.url)
                
                await ctx.send(embed=embed)
                return
        
        await ctx.send(f"error: {member.mention} has not redeemed a key.")

    @commands.command(name='nuke')
    @commands.check(is_allowed_location)
    async def nuke_channel(self, ctx):
        """Delete all messages in the channel (owner only)"""
        if not any(r.id == 1458951003725369345 for r in ctx.author.roles):
            await ctx.send("error: owner only.")
            return
        
        try:
            channel = self.bot.get_channel(1458811026450546965)
            if not channel:
                await ctx.send("error: channel not found.")
                return
            
            deleted = await channel.purge(limit=None, bulk=True)
            await ctx.send(f"nuked {len(deleted)} messages.")
        except Exception as e:
            await send_error(ctx, e)

async def setup(bot):
    await bot.add_cog(ToolCommands(bot))