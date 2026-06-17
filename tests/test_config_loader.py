"""Tests for config loader (.env + ${VAR} substitution)."""

import os

from src.utils.config_loader import load_config, resolve_env_placeholders


def test_resolve_env_placeholders():
    os.environ["TEST_BDW_VAR"] = "resolved_value"
    try:
        text = "user: ${TEST_BDW_VAR}\npass: ${MISSING_VAR}"
        out = resolve_env_placeholders(text)
        assert "resolved_value" in out
        assert "${TEST_BDW_VAR}" not in out
        assert "pass: " in out
    finally:
        os.environ.pop("TEST_BDW_VAR", None)


def test_load_config_substitutes_from_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DW_USER=testuser\nDW_PASSWORD=testpass\n", encoding="utf-8")

    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "datawarehouse:\n  connection:\n    user: ${DW_USER}\n    password: ${DW_PASSWORD}\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("DW_USER", raising=False)
    monkeypatch.delenv("DW_PASSWORD", raising=False)

    cfg = load_config(config_path=cfg_file, env_path=env_file)
    assert cfg["datawarehouse"]["connection"]["user"] == "testuser"
    assert cfg["datawarehouse"]["connection"]["password"] == "testpass"


def test_load_config_dw_host_from_env(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("DW_HOST=db.example.internal\n", encoding="utf-8")
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(
        "datawarehouse:\n  connection:\n    host: ${DW_HOST}\n",
        encoding="utf-8",
    )
    monkeypatch.delenv("DW_HOST", raising=False)
    cfg = load_config(config_path=cfg_file, env_path=env_file)
    assert cfg["datawarehouse"]["connection"]["host"] == "db.example.internal"
