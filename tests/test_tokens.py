import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ghostserver.tokens import (
    EnvBackend,
    FileBackend,
    OpBackend,
    TokenStore,
    _auto_detect_backend,
)


# ---------------------------------------------------------------------------
# EnvBackend
# ---------------------------------------------------------------------------

def test_env_backend_reads_variable():
    with patch.dict(os.environ, {"GITHUB_TOKEN": "ghp_env123"}):
        backend = EnvBackend()
        assert backend.read("GITHUB_TOKEN") == "ghp_env123"


def test_env_backend_raises_when_missing():
    env = {k: v for k, v in os.environ.items() if k != "MISSING_VAR_XYZ"}
    with patch.dict(os.environ, env, clear=True):
        backend = EnvBackend()
        with pytest.raises(RuntimeError, match="MISSING_VAR_XYZ"):
            backend.read("MISSING_VAR_XYZ")


def test_env_backend_raises_when_empty():
    with patch.dict(os.environ, {"EMPTY_VAR": ""}, clear=False):
        backend = EnvBackend()
        with pytest.raises(RuntimeError, match="EMPTY_VAR"):
            backend.read("EMPTY_VAR")


# ---------------------------------------------------------------------------
# OpBackend
# ---------------------------------------------------------------------------

def test_op_backend_reads_secret():
    backend = OpBackend()
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="ghp_abc123\n")
        result = backend.read("op://Dev/GH/token")
    mock_sub.run.assert_called_once_with(
        ["op", "read", "op://Dev/GH/token"],
        capture_output=True, text=True, timeout=10,
    )
    assert result == "ghp_abc123"


def test_op_backend_raises_on_failure():
    backend = OpBackend()
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="not signed in")
        with pytest.raises(RuntimeError, match="not signed in"):
            backend.read("op://Dev/GH/token")


# ---------------------------------------------------------------------------
# FileBackend
# ---------------------------------------------------------------------------

def test_file_backend_reads_key(tmp_path: Path):
    creds = tmp_path / "credentials"
    creds.write_text("GITHUB_TOKEN=ghp_file123\nCLOUDFLARE_TOKEN=cf_abc\n")
    backend = FileBackend(str(creds))
    assert backend.read("GITHUB_TOKEN") == "ghp_file123"
    assert backend.read("CLOUDFLARE_TOKEN") == "cf_abc"


def test_file_backend_ignores_comments(tmp_path: Path):
    creds = tmp_path / "credentials"
    creds.write_text("# This is a comment\nMY_KEY=my_value\n")
    backend = FileBackend(str(creds))
    assert backend.read("MY_KEY") == "my_value"


def test_file_backend_raises_when_key_missing(tmp_path: Path):
    creds = tmp_path / "credentials"
    creds.write_text("OTHER_KEY=val\n")
    backend = FileBackend(str(creds))
    with pytest.raises(RuntimeError, match="MISSING_KEY"):
        backend.read("MISSING_KEY")


def test_file_backend_tolerates_missing_file(tmp_path: Path):
    backend = FileBackend(str(tmp_path / "nonexistent"))
    with pytest.raises(RuntimeError, match="SOME_KEY"):
        backend.read("SOME_KEY")


def test_file_backend_handles_value_with_equals(tmp_path: Path):
    creds = tmp_path / "credentials"
    creds.write_text("TOKEN=abc=def=ghi\n")
    backend = FileBackend(str(creds))
    assert backend.read("TOKEN") == "abc=def=ghi"


# ---------------------------------------------------------------------------
# TokenStore — with explicit backend
# ---------------------------------------------------------------------------

def test_token_store_delegates_to_backend():
    mock_backend = MagicMock()
    mock_backend.read.return_value = "tok_from_backend"
    store = TokenStore(backend=mock_backend)
    result = store.get("some_ref")
    mock_backend.read.assert_called_once_with("some_ref")
    assert result == "tok_from_backend"


def test_token_store_caches():
    mock_backend = MagicMock()
    mock_backend.read.return_value = "tok123"
    store = TokenStore(backend=mock_backend)
    store.get("ref")
    store.get("ref")
    assert mock_backend.read.call_count == 1


def test_token_store_clear_cache():
    mock_backend = MagicMock()
    mock_backend.read.side_effect = ["first", "second"]
    store = TokenStore(backend=mock_backend)
    assert store.get("ref") == "first"
    store.clear_cache()
    assert store.get("ref") == "second"


def test_token_store_backend_name():
    store = TokenStore(backend=EnvBackend())
    assert store.backend_name == "EnvBackend"

    store2 = TokenStore(backend=OpBackend())
    assert store2.backend_name == "OpBackend"


def test_refresh_google_token():
    store = TokenStore(backend=EnvBackend())
    with patch("ghostserver.tokens.httpx") as mock_httpx:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "access_token": "ya29.new_token",
            "expires_in": 3600,
        }
        mock_httpx.post.return_value = mock_response

        token = store.refresh_google(
            client_id="cid",
            client_secret="csec",
            refresh_token="rt_abc",
        )
    assert token == "ya29.new_token"


# ---------------------------------------------------------------------------
# Legacy-compatible tests (OpBackend via TokenStore, subprocess patch)
# These match the original test_tokens.py behaviour.
# ---------------------------------------------------------------------------

def test_get_token_calls_op():
    store = TokenStore(backend=OpBackend())
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(
            returncode=0, stdout="ghp_abc123\n"
        )
        token = store.get("op://Dev/GH/token")
    mock_sub.run.assert_called_once_with(
        ["op", "read", "op://Dev/GH/token"],
        capture_output=True, text=True, timeout=10,
    )
    assert token == "ghp_abc123"


def test_get_token_raises_on_failure():
    store = TokenStore(backend=OpBackend())
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="not signed in")
        with pytest.raises(RuntimeError, match="not signed in"):
            store.get("op://Dev/GH/token")


def test_get_token_caches():
    store = TokenStore(backend=OpBackend())
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok123\n")
        store.get("op://Dev/GH/token")
        store.get("op://Dev/GH/token")
    assert mock_sub.run.call_count == 1


def test_clear_cache():
    store = TokenStore(backend=OpBackend())
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok\n")
        store.get("op://Dev/GH/token")
    store.clear_cache()
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok2\n")
        result = store.get("op://Dev/GH/token")
    assert result == "tok2"


# ---------------------------------------------------------------------------
# _auto_detect_backend
# ---------------------------------------------------------------------------

def test_auto_detect_picks_op_when_available():
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="2.x.x")
        backend = _auto_detect_backend()
    assert isinstance(backend, OpBackend)


def test_auto_detect_picks_file_when_op_missing(tmp_path: Path):
    cred_file = tmp_path / ".ghostserver" / "credentials"
    cred_file.parent.mkdir(parents=True)
    cred_file.write_text("KEY=val\n")

    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.side_effect = FileNotFoundError
        with patch("ghostserver.tokens.Path") as mock_path_cls:
            mock_ghostserver_dir = MagicMock()
            mock_cred_path = MagicMock()
            mock_cred_path.exists.return_value = True
            mock_cred_path.__str__ = MagicMock(return_value=str(cred_file))
            mock_ghostserver_dir.__truediv__ = MagicMock(return_value=mock_cred_path)
            mock_home = MagicMock()
            mock_home.__truediv__ = MagicMock(return_value=mock_ghostserver_dir)
            mock_path_cls.home.return_value = mock_home

            backend = _auto_detect_backend()
    assert isinstance(backend, FileBackend)


def test_auto_detect_falls_back_to_env():
    with patch("ghostserver.tokens.subprocess") as mock_sub:
        mock_sub.run.side_effect = FileNotFoundError
        with patch("ghostserver.tokens.Path") as mock_path_cls:
            mock_ghostserver_dir = MagicMock()
            mock_cred_path = MagicMock()
            mock_cred_path.exists.return_value = False
            mock_ghostserver_dir.__truediv__ = MagicMock(return_value=mock_cred_path)
            mock_home = MagicMock()
            mock_home.__truediv__ = MagicMock(return_value=mock_ghostserver_dir)
            mock_path_cls.home.return_value = mock_home

            backend = _auto_detect_backend()
    assert isinstance(backend, EnvBackend)
