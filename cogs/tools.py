import discord
from discord.ext import commands
import os
import json
import secrets
from datetime import datetime
from cogs.utils.helpers import run_blocking, is_allowed_location, send_error, write_file, protected_id
import sys
sys.path.append('..')
import config

class ToolCommands(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.keys_file = "data/keys.json"
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
    async def make_hex(self, ctx, audio_id: str = None):
        # Check if command is in DM or allowed channel
        if ctx.guild is not None and ctx.channel.id != 1458811026450546965:
            await ctx.send("error: this command can only be used in DMs or in <#1458811026450546965>.")
            return
        
        # Check if user has the required role (check in mutual guild)
        has_role = False
        for guild in self.bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and any(r.id == 1458951498615750888 for r in member.roles):
                has_role = True
                break
        
        if not has_role:
            await ctx.send("error: you don't have the required role.")
            return
        
        # Delete the command message instantly
        try:
            await ctx.message.delete()
        except:
            pass
        
        msg = await ctx.send("generating hex...")
        if not audio_id:
            await msg.edit(content="please provide an audio id.")
            return
        try:
            import random
            value = int(audio_id)
            await ctx.send("WARNING: this only works on certain boomboxes, please use an audio you don't care about first and check f9 before using an audio you care about, also this is pretty easy to bypass, so it isn't 100%")
            hex_digits = format(value, "X")
            zeros_needed = 8164 - 2 - len(hex_digits)
            hex_string = "0x" + "0" * zeros_needed + hex_digits
            random_num = random.randint(100000, 999999)
            output_filename = f"hex_{random_num}.txt"
            await run_blocking(write_file, output_filename, hex_string.encode('utf-8'))
            # Save ID to IDs.txt
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("data/IDs.txt", "a") as f:
                f.write(f"hash: {audio_id} - {ctx.author.name} - {ctx.author.id} - {timestamp}\n")
            await msg.delete()
            await ctx.send(file=discord.File(output_filename))
            if os.path.exists(output_filename): os.remove(output_filename)
        except ValueError:
            await msg.edit(content="error: id must be a valid number.")
        except Exception as e:
            await send_error(ctx, e, status_msg=msg)

    @commands.command(name='hash')
    async def make_hash(self, ctx, target_id: str = None):
        # Check if command is in DM or allowed channel
        if ctx.guild is not None and ctx.channel.id != 1458811026450546965:
            await ctx.send("error: this command can only be used in DMs or in <#1458811026450546965>.")
            return
        
        # Check if user has the required role (check in mutual guild)
        has_role = False
        for guild in self.bot.guilds:
            member = guild.get_member(ctx.author.id)
            if member and any(r.id == 1458951498615750888 for r in member.roles):
                has_role = True
                break
        
        if not has_role:
            await ctx.send("error: you don't have the required role.")
            return
        
        if not target_id:
            await ctx.send("need an id first.")
            return
        
        # Delete the command message instantly
        try:
            await ctx.message.delete()
        except:
            pass
        
        msg = await ctx.send("generating...")
        try:
            import random
            final_string = await run_blocking(protected_id, target_id)
            random_num = random.randint(100000, 999999)
            filename = f"hash_{random_num}.txt"
            await run_blocking(write_file, filename, final_string.encode('utf-8'))
            # Save ID to IDs.txt
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open("data/IDs.txt", "a") as f:
                f.write(f"hash: {target_id} - {ctx.author.name} - {ctx.author.id} - {timestamp}\n")
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
        
        # Save keys to easy copy file
        with open("data/keys_copy.txt", "w") as f:
            f.write("\n".join(keys))
        
        await ctx.send(f"generated {count} key(s). check data/keys_copy.txt to copy them.")

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
        
        await ctx.send(embed=embed)

    @commands.command(name='stats')
    @commands.check(is_allowed_location)
    async def show_stats(self, ctx):
        """Show bot usage statistics with velocity graph"""
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
                    # Sort by time
                    sorted_hours = sorted(hourly_counts.items())
                    hours = [h[0] for h in sorted_hours]
                    counts = [h[1] for h in sorted_hours]
                    
                    # Create graph with clean dark theme
                    fig, ax = plt.subplots(figsize=(14, 6), facecolor='#2b2d31')
                    ax.set_facecolor('#1e1f22')
                    
                    # Convert datetime to numeric for proper interpolation
                    import matplotlib.dates as mdates
                    import numpy as np
                    
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
            await ctx.send(embed=embed, file=file)
            os.remove(graph_path)
        else:
            await ctx.send(embed=embed)

    @commands.command(name='cancel')
    async def cancel_task(self, ctx):
        """Cancel your current processing task"""
        user_id = ctx.author.id
        
        if user_id not in self.bot.active_tasks:
            await ctx.send("error: you don't have any active tasks running.")
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
                await task_msg.edit(content="ok! canceled")
            except:
                await ctx.send("ok! canceled")
        else:
            await ctx.send("ok! canceled")

    @commands.command(name='nuke')
    async def nuke_channel(self, ctx):
        """Delete all messages in the channel (owner only)"""
        if not any(r.id == 1458951003725369345 for r in ctx.author.roles):
            await ctx.send("error: owner only.")
            return
        
        try:
            deleted = await ctx.channel.purge(limit=None, bulk=True)
            await ctx.send(f"nuked {len(deleted)} messages.")
        except Exception as e:
            await send_error(ctx, e)

async def setup(bot):
    await bot.add_cog(ToolCommands(bot))
