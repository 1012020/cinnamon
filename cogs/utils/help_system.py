"""Enhanced help system with categories, examples, and command info"""

import discord
from typing import Dict, List, Optional

# Command categories and detailed information
COMMAND_INFO = {
    "download": {
        "category": "Download & Convert",
        "description": "Download audio from YouTube, SoundCloud, or pekora.zip",
        "usage": "!download <url or pekora.zip ID>",
        "examples": [
            "!download https://youtube.com/watch?v=...",
            "!download https://soundcloud.com/...",
            "!download 12345 (pekora.zip ID)"
        ],
        "aliases": [],
        "premium": True
    },
    "convert": {
        "category": "Download & Convert",
        "description": "Convert audio between formats",
        "usage": "!convert <attachment/url> [format]",
        "examples": [
            "!convert <attach file> ogg",
            "!convert https://... mp3",
            "!convert flac (with attachment)"
        ],
        "aliases": [],
        "premium": True,
        "notes": "Supported: mp3, ogg, wav, flac, m4a, aac, wma"
    },
    "compress": {
        "category": "Download & Convert",
        "description": "Reduce file size (96kbps at 44100Hz)",
        "usage": "!compress <attachment/url>",
        "examples": ["!compress <attach file>", "!compress https://..."],
        "aliases": [],
        "premium": True
    },
    "intro": {
        "category": "Audio Processing",
        "description": "Add intro audio to beginning of song",
        "usage": "!intro <main audio> <intro audio>",
        "examples": [
            "!intro <attach song> https://intro.mp3",
            "!intro https://song.mp3 https://intro.mp3"
        ],
        "aliases": [],
        "premium": True
    },
    "loud": {
        "category": "Audio Processing",
        "description": "300db gain boost",
        "usage": "!loud <attachment/url>",
        "examples": ["!loud <attach file>"],
        "aliases": [],
        "premium": True
    },
    "loudv2": {
        "category": "Audio Processing",
        "description": "Vocal-forward processing",
        "usage": "!loudv2 <attachment/url>",
        "examples": ["!loudv2 <attach file>"],
        "aliases": [],
        "premium": True
    },
    "2db": {
        "category": "Audio Processing",
        "description": "Normalize audio to -2db",
        "usage": "!2db <attachment/url>",
        "examples": ["!2db <attach file>"],
        "aliases": [],
        "premium": True
    },
    "nobass": {
        "category": "Audio Processing",
        "description": "Remove low frequencies",
        "usage": "!nobass <attachment/url>",
        "examples": ["!nobass <attach file>"],
        "aliases": [],
        "premium": True
    },
    "32mono": {
        "category": "Advanced Techniques",
        "description": "Bait for 2018-2020 (requires .ogg file)",
        "usage": "!32mono <attachment/url>",
        "examples": ["!32mono <attach .ogg file>"],
        "aliases": [],
        "premium": True,
        "notes": "Only works with .ogg files"
    },
    "fullbait": {
        "category": "Advanced Techniques",
        "description": "Bait for 2020 (requires .ogg file)",
        "usage": "!fullbait <attachment/url>",
        "examples": ["!fullbait <attach .ogg file>"],
        "aliases": [],
        "premium": True,
        "notes": "Only works with .ogg files"
    },
    "mp3bait": {
        "category": "Advanced Techniques",
        "description": "Bait for 2017-2018 (mp3)",
        "usage": "!mp3bait <attachment/url>",
        "examples": ["!mp3bait <attach file>"],
        "aliases": [],
        "premium": True
    },
    "img": {
        "category": "Advanced Techniques",
        "description": "Embed audio in PNG images",
        "usage": "!img <audio attachment/url>",
        "examples": ["!img <attach audio>"],
        "aliases": [],
        "premium": True
    },
    "createchannels": {
        "category": "Advanced Techniques",
        "description": "Create 1-32 channel audio",
        "usage": "!createchannels <attachment/url> <channel count>",
        "examples": ["!createchannels <attach file> 16"],
        "aliases": [],
        "premium": True,
        "notes": "Channel count must be between 1 and 32"
    },
    "stereobait": {
        "category": "Advanced Techniques",
        "description": "Advanced stereo bait processing",
        "usage": "!stereobait <attachment/url>",
        "examples": ["!stereobait <attach file>"],
        "aliases": [],
        "premium": True
    },
    "hex": {
        "category": "Anti-Logger Tools",
        "description": "Padded hex generation",
        "usage": "!hex <audio ID>",
        "examples": ["!hex 12345"],
        "aliases": [],
        "premium": True
    },
    "hash": {
        "category": "Anti-Logger Tools",
        "description": "16kb hash generation",
        "usage": "!hash <attachment/url>",
        "examples": ["!hash <attach file>"],
        "aliases": [],
        "premium": True
    },
    "embed": {
        "category": "Image Tools",
        "description": "Embed ICC profile in PNG",
        "usage": "!embed [saveas <filename>] <png attachment/url>",
        "examples": [
            "!embed <attach png>",
            "!embed saveas custom.png <attach png>"
        ],
        "aliases": [],
        "premium": False,
        "notes": "Only works in designated channel"
    },
    "stats": {
        "category": "Utilities",
        "description": "View bot usage statistics",
        "usage": "!stats [timeframe]",
        "examples": ["!stats", "!stats day", "!stats week"],
        "aliases": [],
        "premium": False
    },
    "whois": {
        "category": "Utilities",
        "description": "View user profiles and stats",
        "usage": "!whois [@user or ID]",
        "examples": ["!whois", "!whois @user", "!whois 123456789"],
        "aliases": [],
        "premium": True
    },
    "cancel": {
        "category": "Utilities",
        "description": "Cancel current processing task",
        "usage": "!cancel",
        "examples": ["!cancel"],
        "aliases": [],
        "premium": True
    },
    "createpreset": {
        "category": "Presets",
        "description": "Save a command sequence as preset",
        "usage": "!createpreset <name> <command1> [command2] ...",
        "examples": [
            "!createpreset myloud loud convert ogg",
            "!createpreset enhance loudv2 2db"
        ],
        "aliases": [],
        "premium": True
    },
    "presets": {
        "category": "Presets",
        "description": "List your saved presets",
        "usage": "!presets",
        "examples": ["!presets"],
        "aliases": [],
        "premium": True
    },
    "preset": {
        "category": "Presets",
        "description": "Run a saved preset",
        "usage": "!preset <name> <attachment/url>",
        "examples": ["!preset myloud <attach file>"],
        "aliases": [],
        "premium": True
    },
    "presetdelete": {
        "category": "Presets",
        "description": "Delete a preset",
        "usage": "!presetdelete <name>",
        "examples": ["!presetdelete myloud"],
        "aliases": [],
        "premium": True
    },
    "genkey": {
        "category": "Admin",
        "description": "Generate access keys",
        "usage": "!genkey <count>",
        "examples": ["!genkey 5"],
        "aliases": [],
        "premium": False,
        "admin": True
    },
    "postkeys": {
        "category": "Admin",
        "description": "Post live keys message (auto-updates on redemption)",
        "usage": "!postkeys",
        "examples": ["!postkeys"],
        "aliases": [],
        "premium": False,
        "admin": True
    },
    "redeem": {
        "category": "Access",
        "description": "Redeem access key",
        "usage": "!redeem <key>",
        "examples": ["!redeem ABC123XYZ"],
        "aliases": [],
        "premium": False
    },
    "revoke": {
        "category": "Admin",
        "description": "Revoke user access",
        "usage": "!revoke <user ID>",
        "examples": ["!revoke 123456789"],
        "aliases": [],
        "premium": False,
        "admin": True
    }
}


def get_command_categories() -> Dict[str, List[str]]:
    """Get commands organized by category"""
    categories = {}
    for cmd_name, info in COMMAND_INFO.items():
        category = info.get("category", "Other")
        if category not in categories:
            categories[category] = []
        categories[category].append(cmd_name)
    return categories


def create_help_embed(has_premium: bool = False, category: Optional[str] = None) -> discord.Embed:
    """Create comprehensive help embed"""
    if category:
        # Show detailed help for specific category
        embed = discord.Embed(
            title=f"cinnamon - {category}",
            description="detailed command reference",
            color=0xE1F6FF
        )
        
        commands_in_category = [
            (name, info) for name, info in COMMAND_INFO.items()
            if info.get("category") == category
        ]
        
        for cmd_name, info in commands_in_category:
            if info.get("admin"):
                continue
            if info.get("premium", False) and not has_premium:
                continue
                
            value = f"**usage:** {info['usage']}\n"
            if info.get("examples"):
                value += f"**example:** {info['examples'][0]}\n"
            if info.get("notes"):
                value += f"*{info['notes']}*"
            
            embed.add_field(
                name=f"!{cmd_name}",
                value=value,
                inline=False
            )
    else:
        # Main help overview
        embed = discord.Embed(
            title="cinnamon",
            description="audio processing for discord",
            color=0xE1F6FF
        )
        
        categories = get_command_categories()
        category_order = [
            "Download & Convert",
            "Audio Processing",
            "Advanced Techniques",
            "Anti-Logger Tools",
            "Image Tools",
            "Presets",
            "Utilities",
            "Access"
        ]
        
        for cat_name in category_order:
            if cat_name not in categories:
                continue
            
            commands = categories[cat_name]
            # Filter out admin commands and premium commands if no access
            filtered_cmds = [
                cmd for cmd in commands
                if not COMMAND_INFO[cmd].get("admin")
                and (has_premium or not COMMAND_INFO[cmd].get("premium", False))
            ]
            
            if not filtered_cmds:
                continue
            
            cmd_list = ", ".join([f"**!{cmd}**" for cmd in filtered_cmds[:6]])
            if len(filtered_cmds) > 6:
                cmd_list += f" +{len(filtered_cmds) - 6} more"
            
            embed.add_field(
                name=cat_name.lower(),
                value=cmd_list,
                inline=False
            )
        
        if has_premium:
            embed.add_field(
                name="more help",
                value="**!help <command>** - detailed command info\n**!help <category>** - category overview\n**!commands** - list all commands",
                inline=False
            )
        else:
            embed.add_field(
                name="get access",
                value="use **!redeem [key]** to unlock all features\n**!preview** - see all available commands",
                inline=False
            )
        
        embed.set_footer(text="type !help <command> for detailed usage")
    
    return embed


def create_command_help_embed(command_name: str) -> Optional[discord.Embed]:
    """Create detailed help embed for specific command"""
    if command_name not in COMMAND_INFO:
        return None
    
    info = COMMAND_INFO[command_name]
    
    embed = discord.Embed(
        title=f"!{command_name}",
        description=info["description"],
        color=0xE1F6FF
    )
    
    embed.add_field(
        name="usage",
        value=f"`{info['usage']}`",
        inline=False
    )
    
    if info.get("examples"):
        examples_text = "\n".join([f"• `{ex}`" for ex in info["examples"]])
        embed.add_field(
            name="examples",
            value=examples_text,
            inline=False
        )
    
    if info.get("aliases"):
        aliases_text = ", ".join([f"`!{a}`" for a in info["aliases"]])
        embed.add_field(
            name="aliases",
            value=aliases_text,
            inline=False
        )
    
    if info.get("notes"):
        embed.add_field(
            name="notes",
            value=info["notes"],
            inline=False
        )
    
    details = []
    if info.get("premium"):
        details.append("🔒 premium required")
    if info.get("admin"):
        details.append("👑 admin only")
    
    if details:
        embed.set_footer(text=" • ".join(details))
    
    return embed


def get_all_command_names() -> List[str]:
    """Get list of all command names"""
    return list(COMMAND_INFO.keys())


def get_category_names() -> List[str]:
    """Get list of all category names"""
    return list(set(info.get("category", "Other") for info in COMMAND_INFO.values()))
