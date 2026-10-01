from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


class ConfigError(ValueError):
    """Invalid Copout configuration."""


@dataclass(frozen=True, slots=True)
class ContextOptions:
    enabled: bool = True
    git: bool = True
    git_extended: bool = False
    git_diff: bool = False
    shell: bool = True
    shell_version: bool = False
    platform: bool = True
    os_version: bool = False
    hostname: bool = False
    session: bool = True
    python: bool = True
    env: tuple[str, ...] = ()
    executables: tuple[str, ...] = ()

    def with_overrides(self, **overrides: Any) -> ContextOptions:
        values = {name: value for name, value in overrides.items() if value is not None}
        return replace(self, **values)


_DEFAULT_CONFIG = ContextOptions()
_BOOL_FIELDS = {
    "enabled",
    "git",
    "git_extended",
    "git_diff",
    "shell",
    "shell_version",
    "platform",
    "os_version",
    "hostname",
    "session",
    "python",
}
_LIST_FIELDS = {"env", "executables"}


def default_config_path() -> Path:
    if configured := os.environ.get("COPOUT_CONFIG"):
        return Path(configured).expanduser()
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "copout" / "config.toml"


def _parse_context(data: object) -> ContextOptions:
    if not isinstance(data, dict):
        raise ConfigError("[context] must be a TOML table")

    unknown = set(data) - _BOOL_FIELDS - _LIST_FIELDS
    if unknown:
        names = ", ".join(sorted(unknown))
        raise ConfigError(f"unknown [context] setting(s): {names}")

    values: dict[str, Any] = {}
    for name in _BOOL_FIELDS:
        if name not in data:
            continue
        value = data[name]
        if not isinstance(value, bool):
            raise ConfigError(f"context.{name} must be true or false")
        values[name] = value

    for name in _LIST_FIELDS:
        if name not in data:
            continue
        value = data[name]
        if not isinstance(value, list) or not all(isinstance(item, str) and item for item in value):
            raise ConfigError(f"context.{name} must be an array of non-empty strings")
        values[name] = tuple(dict.fromkeys(value))

    return replace(_DEFAULT_CONFIG, **values)


def load_context_options(path: Path | None = None) -> ContextOptions:
    config_path = default_config_path() if path is None else path.expanduser()
    if not config_path.exists():
        if path is not None:
            raise ConfigError(f"config file does not exist: {config_path}")
        return _DEFAULT_CONFIG

    try:
        with config_path.open("rb") as handle:
            raw = tomllib.load(handle)
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"could not read {config_path}: {exc}") from exc

    context = raw.get("context", {})
    return _parse_context(context)
