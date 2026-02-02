import discord
from discord.ext import commands, tasks
import aiohttp
import config
import concurrent.futures
import os
import shutil
import json
from datetime import datetime
from cogs.utils.helpers import load_assets, run_blocking, is_allowed_location

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

class OptimizedBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None, case_insensitive=True)
        self.session = None
        self.stats_file = "data/stats.json"
        self.history_file = "data/history.json"
        self.command_stats = self._load_stats()
        self.command_history = self._load_history()
        self.active_tasks = {}  # user_id: task_info for cancellation
    
    def _load_stats(self):
        """Load command statistics from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    return json.load(f)
            except:
                return {"total_commands": 0, "commands": {}, "users": {}}
        return {"total_commands": 0, "commands": {}, "users": {}}
    
    def _load_history(self):
        """Load command history from separate file"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except:
                return []
        return []

    async def setup_hook(self):
        from cogs.utils import helpers
        helpers.EXECUTOR = concurrent.futures.ThreadPoolExecutor(max_workers=4)
        self.session = aiohttp.ClientSession()
        # Create logs directory if it doesn't exist
        if not os.path.exists("data/logs"):
            os.makedirs("data/logs")
        # Create backups directory if it doesn't exist
        if not os.path.exists("data/backups"):
            os.makedirs("data/backups")
        # Load Cogs
        await self.load_extension('cogs.audio')
        await self.load_extension('cogs.tools')
        # Start auto-backup task
        self.auto_backup.start()

    async def close(self):
        from cogs.utils import helpers
        if helpers.EXECUTOR: helpers.EXECUTOR.shutdown(wait=False)
        if self.session:
            await self.session.close()
        # Cancel backup task
        self.auto_backup.cancel()
        await super().close()

    @tasks.loop(hours=1)
    async def auto_backup(self):
        """Automatically backup keys.json every hour"""
        try:
            if os.path.exists("data/keys.json"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join("data", "backups", f"keys_{timestamp}.json")
                shutil.copy("data/keys.json", backup_path)
                # Keep only last 24 backups
                if os.path.exists("data/backups"):
                    backups = sorted([f for f in os.listdir("data/backups") if f.startswith("keys_")])
                    if len(backups) > 24:
                        for old_backup in backups[:-24]:
                            os.remove(os.path.join("data", "backups", old_backup))
        except Exception as e:
            try:
                with open("data/logs/errors.log", "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] Auto-backup error: {str(e)}\\n")
            except:
                print(f"Auto-backup error: {e}")

bot = OptimizedBot()

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')
    await run_blocking(load_assets)
    print('assets loaded. ready.')

@bot.event
async def on_command(ctx):
    """Track command usage statistics"""
    if ctx.command:
        cmd_name = ctx.command.name
        user_id = str(ctx.author.id)
        timestamp = datetime.now()
        
        # Update total commands
        bot.command_stats["total_commands"] = bot.command_stats.get("total_commands", 0) + 1
        
        # Update command-specific stats
        if "commands" not in bot.command_stats:
            bot.command_stats["commands"] = {}
        bot.command_stats["commands"][cmd_name] = bot.command_stats["commands"].get(cmd_name, 0) + 1
        
        # Track command history in separate file (compact format: [cmd, timestamp, hour])
        bot.command_history.append([cmd_name, timestamp.isoformat(), timestamp.hour])
        
        # Save history to separate file with minimal formatting
        try:
            with open(bot.history_file, "w") as f:
                json.dump(bot.command_history, f, separators=(',', ':'))
        except Exception as e:
            print(f"Failed to save history: {e}")
        
        # Initialize error tracking
        if "errors" not in bot.command_stats:
            bot.command_stats["errors"] = {}
        
        # Update user-specific stats with real data
        if "users" not in bot.command_stats:
            bot.command_stats["users"] = {}
        if user_id not in bot.command_stats["users"]:
            bot.command_stats["users"][user_id] = {"username": str(ctx.author), "commands": 0, "last_command": None}
        bot.command_stats["users"][user_id]["commands"] += 1
        bot.command_stats["users"][user_id]["last_command"] = timestamp.isoformat()
        bot.command_stats["users"][user_id]["username"] = str(ctx.author)
        
        # Save stats (without history)
        try:
            with open(bot.stats_file, "w") as f:
                json.dump(bot.command_stats, f, indent=2)
        except Exception as e:
            print(f"Failed to save stats: {e}")

@bot.event
async def on_command_error(ctx, error):
    """Log all command errors"""
    # Log with real user info
    try:
        error_msg = f"[{datetime.now().isoformat()}] User: {ctx.author} ({ctx.author.id}) | Command: {ctx.command} | Error: {str(error)}\n"
        with open("data/logs/errors.log", "a") as f:
            f.write(error_msg)
    except Exception as e:
        print(f"Failed to log error: {e}")
    
    # Track error rates per command
    if ctx.command:
        cmd_name = ctx.command.name
        if "errors" not in bot.command_stats:
            bot.command_stats["errors"] = {}
        bot.command_stats["errors"][cmd_name] = bot.command_stats["errors"].get(cmd_name, 0) + 1
        
        # Save stats
        try:
            with open(bot.stats_file, "w") as f:
                json.dump(bot.command_stats, f, indent=2)
        except Exception as e:
            print(f"Failed to save error stats: {e}")
    
    print(f"Error logged: {error}")

def has_required_role(ctx):
    """Check if user has the required role in any mutual guild"""
    for guild in ctx.bot.guilds:
        member = guild.get_member(ctx.author.id)
        if member and any(r.id == 1458951498615750888 for r in member.roles):
            return True
    return False

@bot.command(name='help', aliases=['cmds', 'commands'])
async def help_menu(ctx):
    has_role = has_required_role(ctx)
    
    if has_role:
        embed = discord.Embed(title="cinnamon", description="audio processing for discord", color=0xE1F6FF)
        
        embed.add_field(
            name="download & convert",
            value="• **!download** - youtube, soundcloud, pekora.zip\n• **!convert** - mp3, ogg, wav, flac, m4a\n• **!compress** - reduce file size (96kbps)",
            inline=False
        )
        
        embed.add_field(
            name="audio processing",
            value="• **!loud** - 300db gain boost\n• **!loudv2** - vocal-forward processing\n• **!nobass** - remove low frequencies\n• **!2db** - normalize to -2db\n• **!intro** - add intro to songs",
            inline=False
        )
        
        embed.add_field(
            name="advanced techniques",
            value="• **!32mono** - bait for 2018-2020 (works with .ogg)\n• **!fullbait** - bait for 2020 (works with .ogg)\n• **!mp3bait** - bait for 2017-2018 (mp3)\n• **!img** - embed audio in png images\n• **!createchannels** - create 1-32 channel audio",
            inline=False
        )
        
        embed.add_field(
            name="anti-logger tools",
            value="• **!hex** - padded hex generation\n• **!hash** - 16kb hash generation",
            inline=False
        )
        
        embed.add_field(
            name="utilities",
            value="• **!stats** - bot usage stats\n• **!whois** - user profiles\n• **!cancel** - cancel processing",
            inline=False
        )
        
        embed.set_footer(text="supported formats: mp3, ogg, wav, flac, m4a")
    else:
        embed = discord.Embed(title="cinnamon", description="audio processing for discord", color=0xE1F6FF)
        embed.add_field(name="!preview", value='see all available commands', inline=False)
        embed.add_field(name="!redeem [key]", value='redeem a key to get access', inline=False)
        embed.set_footer(text="get access to unlock audio processing")
    
    await ctx.send(embed=embed)

@bot.command(name='preview')
async def preview_menu(ctx):
    """Show preview of all features (available to everyone)"""
    embed = discord.Embed(
        title="cinnamon - premium features",
        description="audio processing for discord",
        color=0xE1F6FF
    )
    
    embed.add_field(
        name="download & convert",
        value="• **!download** - youtube, soundcloud, pekora.zip\n• **!convert** - mp3, ogg, wav, flac, m4a\n• **!compress** - reduce file size (96kbps)",
        inline=False
    )
    
    embed.add_field(
        name="audio processing",
        value="• **!loud** - 300db gain boost\n• **!loudv2** - vocal-forward processing\n• **!nobass** - remove low frequencies\n• **!2db** - normalize to -2db\n• **!intro** - add intro to songs",
        inline=False
    )
    
    embed.add_field(
        name="advanced techniques",
        value="• **!32mono** - bait for 2018-2020 (works with .ogg)\n• **!fullbait** - bait for 2020 (works with .ogg)\n• **!mp3bait** - bait for 2017-2018 (mp3)\n• **!img** - embed audio in png images\n• **!createchannels** - create 1-32 channel audio",
        inline=False
    )
    
    embed.add_field(
        name="anti-logger tools",
        value="• **!hex** - padded hex generation\n• **!hash** - 16kb hash generation",
        inline=False
    )
    
    embed.add_field(
        name="utilities",
        value="• **!stats** - bot usage stats\n• **!whois** - user profiles\n• **!cancel** - cancel processing",
        inline=False
    )
    
    embed.add_field(
        name="get access",
        value="use **!redeem [key]** to unlock all features",
        inline=False
    )
    
    embed.set_footer(text="supported formats: mp3, ogg, wav, flac, m4a")
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(config.TOKEN)
