from __future__ import annotations

import json
from pathlib import Path

_LOCALE_DIR = Path(__file__).parent
_DEFAULT_LOCALE = "zh_CN"
_current_locale_name: str = _DEFAULT_LOCALE
_current_locale: dict[str, str] = {}


def _load_locale_file(name: str) -> dict[str, str]:
    path = _LOCALE_DIR / f"{name}.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def set_locale(name: str) -> None:
    global _current_locale_name, _current_locale
    data = _load_locale_file(name)
    if not data:
        data = _load_locale_file(_DEFAULT_LOCALE)
        _current_locale_name = _DEFAULT_LOCALE
    else:
        _current_locale_name = name
    _current_locale = data


def get_locale() -> str:
    return _current_locale_name


def load_extra_locale(path: str) -> None:
    global _current_locale
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _current_locale.update(data)


def t(key: str, default: str = "", **kwargs) -> str:
    text = _current_locale.get(key, default or key)
    if kwargs:
        text = text.format(**kwargs)
    return text


set_locale(_DEFAULT_LOCALE)
