import json
import os
from typing import Literal

SETTINGS_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'settings.json')

def _ensure_file():
    if not os.path.exists(os.path.dirname(SETTINGS_PATH)):
        os.makedirs(os.path.dirname(SETTINGS_PATH), exist_ok=True)
    if not os.path.exists(SETTINGS_PATH):
        with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
            json.dump({"fullbait_mode": "role_only"}, f)

def _read_all():
    _ensure_file()
    try:
        with open(SETTINGS_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {"fullbait_mode": "role_only"}

def _write_all(data: dict):
    _ensure_file()
    with open(SETTINGS_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2)

FullbaitMode = Literal['role_only', 'everyone_watermark']

def get_fullbait_mode() -> FullbaitMode:
    data = _read_all()
    return data.get('fullbait_mode', 'role_only')

def set_fullbait_mode(mode: FullbaitMode):
    data = _read_all()
    data['fullbait_mode'] = mode
    _write_all(data)
