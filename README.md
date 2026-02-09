# Cinnamon 🎵

A powerful Discord bot for advanced audio processing and manipulation. Cinnamon provides professional-grade audio tools for downloading, converting, and processing audio files directly through Discord.

## Features

### Download & Convert
- **!download** - Download audio from YouTube, SoundCloud, and pekora.zip
- **!convert** - Convert between multiple formats (MP3, OGG, WAV, FLAC, M4A)
- **!compress** - Reduce file size with 96kbps compression

### Audio Processing
- **!loud** - Apply 300db gain boost for maximum volume
- **!loudv2** - Vocal-forward processing for enhanced clarity
- **!nobass** - Remove low frequencies
- **!2db** - Normalize audio to -2db
- **!intro** - Add custom intro to songs

### Advanced Techniques
- **!32mono** - Bait technique for 2018-2020 (works with .ogg)
- **!fullbait** - Bait technique for 2020 (works with .ogg)
- **!mp3bait** - Bait technique for 2017-2018 (MP3 format)
- **!img** - Embed audio in PNG images
- **!createchannels** - Create multi-channel audio (1-32 channels)

### Anti-Logger Tools
- **!hex** - Generate padded hex data
- **!hash** - Generate 16kb hash data

### Utilities
- **!stats** - View bot usage statistics
- **!whois** - View user profiles
- **!cancel** - Cancel ongoing processing tasks
- **!help** - Show all available commands
- **!preview** - Preview features before redeeming access
- **!redeem [key]** - Redeem a key to unlock full access

## Installation

### Prerequisites
- Python 3.8 or higher
- FFmpeg (for audio processing)
- Discord Bot Token

### Setup

1. Clone the repository:
```bash
git clone https://github.com/1012020/cinnamon.git
cd cinnamon
```

2. Install required dependencies:
```bash
pip install discord.py aiohttp
```

3. Configure the bot:
   - Edit `config.py` with your Discord bot token and settings
   - Set up your `TOKEN`, role IDs, and channel IDs

4. Prepare assets:
   - Place required audio assets in the `assets/` directory
   - Ensure `headah.ogg`, `cinnamon.ogg`, and bait files are present

5. Run the bot:
```bash
python main.py
```

## Configuration

The bot uses `config.py` for configuration. Key settings include:

- `TOKEN` - Your Discord bot token
- `ALLOWED_GUILD_ID` - The guild where the bot operates
- `ALLOWED_CHANNEL_ID` - Specific channel for bot commands
- `TARGET_SIZE_MB` - Target file size for processing
- `MAX_CHANNELS_LIMIT` - Maximum audio channels (default: 32)

## Supported Formats

- MP3
- OGG
- WAV
- FLAC
- M4A

## Project Structure

```
cinnamon/
├── main.py              # Main bot entry point
├── config.py            # Configuration settings
├── cogs/                # Command modules
│   ├── audio.py         # Audio processing commands
│   ├── tools.py         # Utility commands
│   └── utils/           # Helper functions
├── assets/              # Audio assets and resources
├── data/                # Data storage and logs
└── scripts/             # Processing scripts
```

## Features Details

### Key Management System
- Key-based access control with redemption system
- Automatic hourly backups of keys
- Maintains last 24 backups automatically

### Statistics Tracking
- Tracks total commands executed
- Per-command usage statistics
- Per-user activity tracking
- Command history with timestamps
- Error rate tracking

### Performance Optimization
- Asynchronous processing with thread pool executor
- Task cancellation support for long-running operations
- Efficient file handling with automatic cleanup
- Separate history file for performance optimization

## Usage Examples

### Basic Audio Processing
```
!download https://youtube.com/watch?v=example
!convert .mp3
!loud
```

### Advanced Techniques
```
!32mono
!img
```

### Getting Access
```
!preview              # See all available features
!redeem YOUR_KEY     # Unlock full access
```

## Error Logging

All errors are automatically logged to `data/logs/errors.log` with:
- Timestamp
- User information
- Command that caused the error
- Error details

## Backups

The bot automatically creates hourly backups of `keys.json` in `data/backups/`, keeping the last 24 backups.

## Security

- Role-based access control
- Domain whitelist for file processing
- Safe file handling with validation
- Automatic error logging and monitoring

## License

This project is provided as-is for educational and personal use.

## Support

For issues or questions, please open an issue on the GitHub repository.
