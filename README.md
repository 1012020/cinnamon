# Cinnamon 🎵

An advanced Discord bot for audio processing and manipulation, inspired by aux and miku.

## Features

### Audio Download & Conversion
- Download audio from YouTube, SoundCloud, and pekora.zip
- Convert between formats: mp3, ogg, wav, flac, m4a
- Compress audio files (96kbps)

### Audio Processing
- **!loud** - 300db gain boost
- **!loudv2** - Vocal-forward processing
- **!nobass** - Remove low frequencies
- **!2db** - Normalize to -2db
- **!intro** - Add intro to songs

### Advanced Techniques
- **!32mono** - Bait for 2018-2020 (works with .ogg)
- **!fullbait** - Bait for 2020 (works with .ogg)
- **!mp3bait** - Bait for 2017-2018 (mp3)
- **!img** - Embed audio in PNG images
- **!createchannels** - Create 1-32 channel audio

### Anti-Logger Tools
- **!hex** - Padded hex generation
- **!hash** - 16kb hash generation

### Utilities
- **!stats** - Bot usage statistics with velocity graph
- **!whois** - User profiles and activity
- **!leaderboard** - Top users by command usage
- **!cancel** - Cancel active processing
- **!status** - Check upload provider status
- **!keyinfo** - View key statistics (admin only)

## Setup

1. Install dependencies:
```bash
pip install discord.py aiohttp matplotlib scipy
```

2. Configure `config.py` with your Discord bot token

3. Run the bot:
```bash
python main.py
```

## Access Control

The bot uses a key-based access system. Users must redeem a key using `!redeem [key]` to access premium features.

Administrators can generate keys using `!genkey [count]`.

## Commands

- Use `!help` or `!commands` to see available commands
- Use `!preview` to see all features without access

## Support

For issues or questions, contact the bot administrator.
