# Cinnamon

A Discord bot for audio transformation workflows, gated access management, and lightweight operations monitoring.

This repository contains:
- A command-based Discord bot (audio processing, conversion, presets, access keys, applications)
- A local admin dashboard for monitoring and maintenance
- Persistent JSON-backed state for usage analytics and workflow data

## Highlights

- Audio workflows: conversion, compression, intro stitching, loudness/effect transforms, multi-channel generation
- Asset-driven transformations with configurable bait/intro/image libraries
- Role/key-based access control and redemption flow
- Application intake and review process (Discord DM + dashboard APIs)
- Structured logging with rotation and basic analytics
- Hourly key backups and health/status endpoints

## Tech Stack

- Python 3.10+
- discord.py
- Flask (admin dashboard)
- pydub + FFmpeg (audio processing)
- NumPy / SciPy / pyloudnorm / soundfile
- yt-dlp (YouTube/SoundCloud download support)

## Project Layout

```text
cinnamon-main/
  main.py                 # bot entrypoint
  config.py               # environment-driven runtime configuration
  cogs/
    audio.py              # audio commands
    tools.py              # utility/admin/access commands
    application.py        # application workflow
    utils/
      audio_processing.py # processing primitives
      network.py          # download/upload provider logic
      admin_dashboard.py  # Flask dashboard API + control center
      help_system.py      # command catalog/metadata
      logging_system.py   # structured logging + rotation
  dashboard/templates/    # dashboard frontend template
  assets/                 # local media/profile assets used by commands
  data/                   # runtime state (keys, stats, logs, backups)
  docs/                   # architecture and operations docs
```

See also:
- docs/ARCHITECTURE.md
- docs/OPERATIONS.md
- assets/README.md
- data/README.md

## Quick Start

1. Clone and enter the repository.
2. Create a virtual environment.
3. Install dependencies.
4. Configure environment variables.
5. Run the bot.

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
# Set env vars in your shell (or your process manager)
$env:DISCORD_BOT_TOKEN="<your-token>"
$env:OWNER_ID="<your-discord-user-id>"
$env:ADMIN_TOKEN="<strong-random-token>"
python main.py
```

### Linux/macOS

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
export DISCORD_BOT_TOKEN="<your-token>"
export OWNER_ID="<your-discord-user-id>"
export ADMIN_TOKEN="<strong-random-token>"
python main.py
```

## Configuration

Core configuration lives in config.py and is now environment-driven for secrets.

Required:
- DISCORD_BOT_TOKEN: Discord bot token

Recommended:
- OWNER_ID: Bot owner user ID used by owner-restricted commands
- ADMIN_TOKEN: Dashboard API token (required for remote privileged API usage)

Static IDs and channel/guild constraints are also defined in config.py.
Adjust these to match your Discord server before production use.

## Commands Overview

Commands are grouped in the in-app help system:
- Download & Convert
- Audio Processing
- Advanced Techniques
- Anti-Logger Tools
- Image Tools
- Presets
- Utilities
- Access/Admin

Use !help in Discord for category and per-command details.

## Dashboard

The dashboard starts with the bot and binds to:
- http://127.0.0.1:5000

Capabilities include:
- Stats/log visibility
- Active task inspection
- Application review actions
- Maintenance controls (reload cogs, backups, key management, etc.)

Security notes:
- Privileged /api/control* routes require ADMIN_TOKEN.
- Localhost requests are allowed for convenience.
- Do not expose dashboard endpoints publicly without a reverse proxy and strong auth controls.

## Data and State

Runtime JSON files are stored under data/.
The bot automatically creates required directories and rotates key backups.

For public repository hygiene:
- Keep secrets out of source control
- Do not commit production keys or user data
- Use the provided .gitignore and environment variable workflow

## Development Notes

- Audio commands rely on FFmpeg availability on PATH.
- Some commands are intentionally restricted by guild/channel/role checks.
- The bot enforces file-size limits for uploads and many downloads.

## Troubleshooting

- Missing token at startup:
  - Ensure DISCORD_BOT_TOKEN is set in the running process environment.
- Audio conversion failures:
  - Verify FFmpeg installation and PATH.
- Download failures (YouTube/SoundCloud):
  - Update yt-dlp and confirm source URL accessibility.
- Dashboard authorization errors:
  - Set ADMIN_TOKEN and send it as X-Admin-Token or Authorization: Bearer <token>.

## Security Checklist (Before Public Deployment)

- Rotate any previously exposed bot tokens immediately.
- Use a fresh ADMIN_TOKEN.
- Verify channel/guild/role IDs in config.py.
- Restrict dashboard network exposure.
- Review command set and disable anything not intended for your audience.

## License

No license file is currently defined in this repository.
Add a LICENSE file before open-source publication.
