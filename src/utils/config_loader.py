"""
Load config.yaml with .env and ${VAR} placeholder substitution.
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

import yaml

_ENV_PATTERN = re.compile(r"\$\{([^}]+)\}")


def project_root() -> Path:
    """data-catalog-assistant repository root (parent of src/)."""
    return Path(__file__).resolve().parents[2]


def resolve_path(path: Union[str, Path], root: Optional[Path] = None) -> Path:
    """Resolve a path relative to cwd or project root."""
    p = Path(path)
    if p.is_absolute() and p.exists():
        return p
    if p.exists():
        return p.resolve()
    base = root or project_root()
    candidate = base / p
    if candidate.exists():
        return candidate.resolve()
    return p.resolve()


def load_dotenv_file(env_path: Path) -> None:
    """Load KEY=VALUE lines into os.environ (does not override existing vars)."""
    if not env_path.exists():
        return

    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, val = line.split("=", 1)
        key = key.strip()
        val = val.strip().strip('"').strip("'")
        if key and os.environ.get(key) is None:
            os.environ[key] = val


def resolve_env_placeholders(text: str, environ: Optional[Dict[str, str]] = None) -> str:
    """Replace ${VAR_NAME} with values from environ (default: os.environ)."""
    env = environ if environ is not None else os.environ

    def repl(match: re.Match) -> str:
        return env.get(match.group(1).strip(), "")

    return _ENV_PATTERN.sub(repl, text)


def load_config(
    config_path: Optional[Union[str, Path]] = None,
    env_path: Optional[Union[str, Path]] = None,
    load_env: bool = True,
) -> Dict[str, Any]:
    """
    Load application configuration.

    1. Loads .env into os.environ (if load_env=True)
    2. Reads YAML config
    3. Substitutes ${VAR} from environment

    Args:
        config_path: Path to config.yaml (default: <project>/config/config.yaml)
        env_path: Path to .env (default: <project>/.env)
        load_env: Whether to load .env before parsing config

    Returns:
        Parsed configuration dictionary
    """
    root = project_root()
    cfg_path = resolve_path(config_path or "config/config.yaml", root)

    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")

    if load_env:
        dotenv_path = resolve_path(env_path or ".env", root)
        load_dotenv_file(dotenv_path)
        try:
            from dotenv import load_dotenv

            load_dotenv(dotenv_path, override=False)
        except ImportError:
            pass

    raw = cfg_path.read_text(encoding="utf-8")
    resolved = resolve_env_placeholders(raw)
    config = yaml.safe_load(resolved)

    if not isinstance(config, dict):
        raise ValueError(f"Invalid config format in {cfg_path}")

    return config
