# Operations Guide

## Prerequisites

- Python 3.10+
- FFmpeg installed and available on PATH
- Network egress to Discord + upload providers + optional media providers

## Start Procedure

1. Create/activate virtual environment.
2. Install dependencies from requirements.txt.
3. Set DISCORD_BOT_TOKEN (required).
4. Set OWNER_ID and ADMIN_TOKEN (recommended).
5. Start with python main.py.

## Health Checks

- Bot login confirmation appears in console.
- Dashboard reachable at http://127.0.0.1:5000.
- /api/health reports healthy + bot_connected true.

## Backup and Persistence

- keys.json is copied hourly to data/backups/.
- Log rotation is managed by cogs/utils/logging_system.py.
- Preserve data/ for continuity across restarts.

## Security Operations

- Rotate DISCORD_BOT_TOKEN immediately if exposure is suspected.
- Use a strong ADMIN_TOKEN and avoid exposing dashboard to the internet.
- Keep .env out of source control.
- Periodically review role/channel restrictions in config.py.

## Deployment Recommendations

- Run behind a process manager (systemd, supervisord, container orchestrator).
- Restrict filesystem permissions for data/ and .env.
- Keep separate environments for staging and production.
- Monitor disk growth for backups and logs.

## Incident Response (Minimal)

- If credentials leak: rotate tokens and restart service.
- If command misuse occurs: update role/channel restrictions and revoke access keys.
- If storage grows unexpectedly: archive logs/backups and enforce retention.

## Upgrade Notes

- Update dependencies regularly, especially discord.py and yt-dlp.
- Test high-use commands in a staging guild before production rollout.
- Validate FFmpeg compatibility after system updates.
