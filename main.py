import discord
from discord.ext import commands, tasks
import aiohttp
import config
import concurrent.futures
import os
import shutil
import json
from datetime import datetime
from cogs.utils.helpers import load_assets, run_blocking, is_allowed_location, send_status
from cogs.utils.logging_system import init_logger, get_logger
from cogs.utils.fuzzy_match import find_similar_commands, get_suggestion_message, find_best_match
from cogs.utils.help_system import create_help_embed, create_command_help_embed, get_all_command_names, get_category_names
from cogs.utils.enhanced_stats import StatsAnalyzer, create_stats_embed, create_user_profile_embed
from PIL import Image
Image.MAX_IMAGE_PIXELS = 50_000_000  # limit to mitigate decompression bombs

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
        self.start_time = datetime.now()  # Track bot start time
        self.logger = None  # Will be initialized in setup_hook
    
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
        # Initialize enhanced logger
        self.logger = init_logger("cinnamon", "data/logs", max_size_mb=10.0, max_files=10)
        self.logger.info("Bot starting up")
        # Load Cogs
        await self.load_extension('cogs.audio')
        await self.load_extension('cogs.tools')
        await self.load_extension('cogs.application')
        # Start auto-backup task
        self.auto_backup.start()
        # Admin dashboard enabled
        self._start_dashboard()

    def _start_dashboard(self):
        """Start admin dashboard in background thread"""
        try:
            from cogs.utils.admin_dashboard import AdminDashboard
            dashboard = AdminDashboard(self, host="127.0.0.1", port=5000)
            dashboard.run_async()
            self.logger.info("Admin dashboard started on http://127.0.0.1:5000")
        except Exception as e:
            print(f"Failed to start admin dashboard: {e}")
    
    async def close(self):
        from cogs.utils import helpers
        if self.logger:
            self.logger.info("Bot shutting down")
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
                                try:
                                    os.remove(os.path.join("data", "backups", old_backup))
                                except Exception as e:
                                    print(f"Failed to remove old backup {old_backup}: {e}")
        except Exception as e:
            try:
                with open("data/logs/errors.log", "a") as f:
                    f.write(f"[{datetime.now().isoformat()}] Auto-backup error: {str(e)}\\n")
            except Exception as e2:
                print(f"Auto-backup logging error: {e2}")

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
    """Log all command errors with enhanced logging and fuzzy matching"""
    # Enhanced logging
    if bot.logger:
        bot.logger.command_error(
            str(ctx.author.id),
            str(ctx.author),
            str(ctx.command) if ctx.command else "unknown",
            str(error)
        )
    
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
    
    # Handle command not found with fuzzy matching
    if isinstance(error, commands.CommandNotFound):
        # Extract the command name from the error message
        import re
        match = re.search(r'Command "(.+?)" is not found', str(error))
        if match:
            invalid_cmd = match.group(1)
            all_cmds = get_all_command_names()
            suggestions = find_similar_commands(invalid_cmd, all_cmds, threshold=0.5, max_suggestions=3)
            
            if suggestions:
                suggestion_msg = get_suggestion_message(invalid_cmd, suggestions)
                await send_status(ctx, suggestion_msg)
                return
    
    print(f"Error logged: {error}")

def has_required_role(ctx):
    """Check if user has the required role in any mutual guild"""
    for guild in ctx.bot.guilds:
        member = guild.get_member(ctx.author.id)
        if member and any(r.id == 1458951498615750888 for r in member.roles):
            return True
    return False

@bot.command(name='help', aliases=['cmds', 'commands'])
async def help_menu(ctx, *, query: str = None):
    """Enhanced help command with categories and detailed command info"""
    has_role = has_required_role(ctx)
    
    if query:
        # Check if it's a specific command
        command_embed = create_command_help_embed(query.lower())
        if command_embed:
            await ctx.send(embed=command_embed)
            return
        
        # Check if it's a category
        category_names = get_category_names()
        matching_category = next((cat for cat in category_names if cat.lower() == query.lower()), None)
        if matching_category:
            embed = create_help_embed(has_premium=has_role, category=matching_category)
            await ctx.send(embed=embed)
            return
        
        # Not found
        await send_status(ctx, f"no help found for '{query}'. try !help to see all commands.")
    else:
        # Main help overview
        embed = create_help_embed(has_premium=has_role)
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
        value="• **!stats** - bot usage stats\n• **!whois** - user profiles\n• **!cancel** - cancel processing\n• **!createpreset** - save a preset (e.g. !createpreset name loud img)\n• **!presets** - list presets\n• **!preset <name>** - run a preset",
        inline=False
    )
    
    embed.add_field(
        name="get access",
        value="use **!redeem [key]** to unlock all features",
        inline=False
    )
    
    embed.set_footer(text="supported formats: mp3, ogg, wav, flac, m4a")
    await send_status(ctx, embed=embed)

if __name__ == "__main__":
    if not config.TOKEN:
        raise RuntimeError("DISCORD_BOT_TOKEN is not set. Configure environment variables before running the bot.")
    bot.run(config.TOKEN)
