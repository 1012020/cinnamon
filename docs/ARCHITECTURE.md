# Architecture

## Runtime Components

- Bot runtime: main.py initializes the Discord client, loads cogs, starts backup loop, and launches the admin dashboard thread.
- Command cogs:
  - cogs/audio.py: audio pipeline commands and effect orchestration
  - cogs/tools.py: utility/access/admin-style commands
  - cogs/application.py: user application intake and review helpers
- Utility modules:
  - cogs/utils/audio_processing.py: CPU-heavy processing functions
  - cogs/utils/network.py: upload/download and provider selection logic
  - cogs/utils/logging_system.py: structured logger + file rotation
  - cogs/utils/help_system.py: command metadata and category views
  - cogs/utils/admin_dashboard.py: Flask dashboard routes + control actions

## Execution Flow

1. Process starts in main.py.
2. setup_hook creates HTTP session, thread pool, directories, and logger.
3. Extensions are loaded (audio/tools/application).
4. Dashboard starts on localhost:5000.
5. Commands execute through cogs, with heavy workloads delegated via run_blocking into thread pool.
6. Runtime metrics/logs are persisted in data/.

## Data Model (JSON-backed)

- data/stats.json: command usage counters and user stats
- data/history.json: compact command history timeline
- data/keys.json: generated key inventory and redemption states
- data/applications.json: application submissions and review outcomes
- data/presets.json: user preset definitions
- data/settings.json: feature flags/config toggles (for example fullbait mode)

## Operational Characteristics

- Async I/O for Discord + HTTP
- Background thread pool for expensive audio transformations
- File-based persistence (no external database)
- Upload provider fallback strategy (tmpfiles/tempfile/litterbox)
- Hourly key backup rotation in data/backups/

## Security Boundaries

- Command execution is constrained by guild/channel/role checks.
- Dashboard privileged APIs require ADMIN_TOKEN, with localhost convenience access.
- Input link handling is mostly restricted to approved domains.
- Secret material is expected via environment variables.

## Known Technical Debt

- Static IDs in config.py require manual adjustment per deployment.
- Some command behavior is tightly coupled to local asset folder conventions.
- Runtime JSON files can grow without archival automation beyond keys/log rotation.
- Dashboard control features are powerful and should be network-isolated.
