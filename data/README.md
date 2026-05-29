# Data Directory

This folder stores runtime state and should be treated as environment-specific data.

Typical files:
- keys.json / keys backups
- stats.json / history.json
- applications.json
- logs/

Guidance:
- Do not commit production user data or key material.
- Back up this directory in private infrastructure only.
- For fresh environments, files are created automatically as commands run.
