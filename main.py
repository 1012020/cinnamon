import discord
from discord.ext import commands, tasks
import aiohttp
import config
import concurrent.futures
import os
import shutil
from datetime import datetime
from cogs.utils.helpers import load_assets, run_blocking, is_allowed_location

intents = discord.Intents.default()
intents.message_content = True

class OptimizedBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix='!', intents=intents, help_command=None, case_insensitive=True)
        self.session = None

    async def setup_hook(self):
        from cogs.utils import helpers
        helpers.EXECUTOR = concurrent.futures.ProcessPoolExecutor()
        self.session = aiohttp.ClientSession()
        # Create logs directory if it doesn't exist
        if not os.path.exists("logs"):
            os.makedirs("logs")
        # Create backups directory if it doesn't exist
        if not os.path.exists("backups"):
            os.makedirs("backups")
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
            if os.path.exists("keys.json"):
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = os.path.join("backups", f"keys_{timestamp}.json")
                shutil.copy("keys.json", backup_path)
                # Keep only last 24 backups
                backups = sorted([f for f in os.listdir("backups") if f.startswith("keys_")])
                if len(backups) > 24:
                    for old_backup in backups[:-24]:
                        os.remove(os.path.join("backups", old_backup))
        except Exception as e:
            with open("logs/errors.log", "a") as f:
                f.write(f"[{datetime.now().isoformat()}] Auto-backup error: {str(e)}\n")

bot = OptimizedBot()

@bot.event
async def on_ready():
    print(f'logged in as {bot.user}')
    await run_blocking(load_assets)
    print('assets loaded. ready.')

@bot.event
async def on_command_error(ctx, error):
    """Log all command errors"""
    error_msg = f"[{datetime.now().isoformat()}] User: {ctx.author} | Command: {ctx.command} | Error: {str(error)}\n"
    with open("logs/errors.log", "a") as f:
        f.write(error_msg)
    print(f"Error logged: {error}")

@bot.command(name='help', aliases=['cmds', 'commands'])
@commands.check(is_allowed_location)
async def help_menu(ctx):
    embed = discord.Embed(title="cinnamon", description="attach a file or paste a discord link.", color=0xE1F6FF)
    embed.add_field(name="!download [url]", value="downloads audio from youtube or soundcloud (max 9 mins)", inline=False)
    embed.add_field(name="!loud", value="applies 300db gain, keeps original format", inline=False)
    embed.add_field(name="!loudv2", value="applies vocal-forward loudness processing", inline=False)
    embed.add_field(name="!nobass", value="removes low frequencies, keeps original format", inline=False)
    embed.add_field(name="!2db", value="normalizes audio to exactly -2db", inline=False)
    embed.add_field(name="!intro [links]", value="adds an intro to the start of a song", inline=False)
    embed.add_field(name="!convert [fmt]", value="converts audio to mp3, ogg, wav, flac, etc", inline=False)
    embed.add_field(name="!maxchannels", value='crams max channels example into 10mb (ogg)', inline=False)
    embed.add_field(name="!compress", value='forces significant file size reduction', inline=False)
    embed.add_field(name="!32mono", value='requires .ogg, uploads to litterbox (1h), uses random bait, works on 2018 to 2020', inline=False)
    embed.add_field(name="!fullbait", value='requires .ogg, uploads to litterbox (1h), uses random bait, works on 2020 only', inline=False)
    embed.add_field(name="!hex [id]", value='generates padded hex to fuck over loggers', inline=False)
    embed.add_field(name="!hash [id]", value='generates 16kb hash to fuck over loggers', inline=False)
    embed.add_field(name="!redeem [key]", value='redeem a key to get the special role', inline=False)
    embed.set_footer(text="supported: mp3, ogg, wav, flac, m4a")
    await ctx.send(embed=embed)

if __name__ == "__main__":
    bot.run(config.TOKEN)