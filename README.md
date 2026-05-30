# Cinnamon

A Discord bot for audio making on Roblox revivals, using Notepad++ methods.

This repository contains:

* A command-based Discord bot (audio processing, conversion, presets, access keys, applications)
* A local admin dashboard for monitoring and maintenance
* Persistent JSON-backed state for usage analytics and workflow data

## Highlights

* Audio workflows: conversion, compression, intro stitching, loudness/effect transforms, multi-channel generation
* Asset-driven transformations with configurable bait/intro/image libraries
* Role/key-based access control and redemption flow
* Application intake and review process (Discord DM + dashboard APIs)
* Structured logging with rotation and basic analytics
* Hourly key backups and health/status endpoints

## Tech Stack

* Python 3.10+
* discord.py
* Flask (admin dashboard)
* pydub + FFmpeg (audio processing)
* NumPy / SciPy / pyloudnorm / soundfile
* yt-dlp (YouTube/SoundCloud download support)

## Project Layout

```text
cinnamon-main/
  main.py
  config.py
  cogs/
    audio.py
    tools.py
    application.py
    utils/
      audio_processing.py
      network.py
      admin_dashboard.py
      help_system.py
      logging_system.py
  dashboard/templates/
  assets/
  data/
  docs/
```

## Quick Start

### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
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

Required:

* DISCORD_BOT_TOKEN

Recommended:

* OWNER_ID
* ADMIN_TOKEN

## Dashboard

* http://127.0.0.1:5000

## License

Custom Non-Commercial License (Attribution Required)

Copyright (c) 2026 1012020

Permission is hereby granted to use, copy, modify, and distribute this software
for **non-commercial purposes only**, subject to the following conditions:

1. Attribution is required. You must give clear credit to **1012020** as the original creator of Cinnamon in any copies, forks, or derivatives.
2. You may not sell, sublicense, or commercially distribute this software or any derivative works.
3. You may not use this software as part of any paid service, product, or monetized platform.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
