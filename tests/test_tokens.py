from unittest.mock import patch, MagicMock
from conduit.tokens import TokenStore


def test_get_token_calls_op():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
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
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=1, stderr="not signed in")
        try:
            store.get("op://Dev/GH/token")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "not signed in" in str(e)


def test_get_token_caches():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok123\n")
        store.get("op://Dev/GH/token")
        store.get("op://Dev/GH/token")
    assert mock_sub.run.call_count == 1


def test_refresh_google_token():
    store = TokenStore()
    with patch("conduit.tokens.httpx") as mock_httpx:
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


def test_clear_cache():
    store = TokenStore()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok\n")
        store.get("op://Dev/GH/token")
    store.clear_cache()
    with patch("conduit.tokens.subprocess") as mock_sub:
        mock_sub.run.return_value = MagicMock(returncode=0, stdout="tok2\n")
        result = store.get("op://Dev/GH/token")
    assert result == "tok2"
