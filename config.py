import os

# Required secret. Set this in your environment before starting the bot.
TOKEN = os.getenv("DISCORD_BOT_TOKEN", "")

TARGET_SIZE_MB = 10.0
MAX_CHANNELS_LIMIT = 32

TARGET_LIMIT = 8165
NOISE_COUNT = 6

PREFIX_FILE = "assets/headah.ogg"
CINNAMON_FILE = "assets/cinnamon.ogg"
BAIT_DIRECTORY = "assets/short baits"
IDS_FILE = "assets/IDs.txt"

ALLOWED_GUILD_ID = 1458794126123335720
ALLOWED_CHANNEL_ID = 1458811026450546965
ALLOWED_DOMAINS = ["cdn.discordapp.com", "media.discordapp.net"]
ISRAELITE_ROLE_ID = 1464787461719720133

# Owner ID constant (use config.OWNER_ID rather than hardcoding elsewhere)
OWNER_ID = int(os.getenv("OWNER_ID", "1423665222870241422"))

# Optional admin dashboard token. Leave unset to restrict privileged API usage
# to localhost convenience access only.
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")
