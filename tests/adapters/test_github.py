import pytest
import respx
import httpx
from conduit.adapters.github import server as github_server


@respx.mock
@pytest.mark.asyncio
async def test_github_list_repos(github_core):
    respx.get("https://api.github.com/user/repos").mock(
        return_value=httpx.Response(200, json=[
            {"full_name": "user/repo1", "description": "Desc", "html_url": "https://github.com/user/repo1", "stargazers_count": 5, "language": "Python"},
        ])
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_list_repos", {})
        assert "user/repo1" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_create_issue(github_core):
    respx.post("https://api.github.com/repos/owner/repo/issues").mock(
        return_value=httpx.Response(201, json={
            "number": 42, "title": "Bug", "html_url": "https://github.com/owner/repo/issues/42",
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_create_issue", {
            "owner": "owner", "repo": "repo", "title": "Bug", "body": "Details"
        })
        assert "42" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_list_prs(github_core):
    respx.get("https://api.github.com/repos/owner/repo/pulls").mock(
        return_value=httpx.Response(200, json=[
            {"number": 10, "title": "Fix", "state": "open", "html_url": "https://github.com/owner/repo/pull/10", "user": {"login": "dev"}},
        ])
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_list_prs", {"owner": "owner", "repo": "repo"})
        assert "Fix" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_search_code(github_core):
    respx.get("https://api.github.com/search/code").mock(
        return_value=httpx.Response(200, json={
            "total_count": 1,
            "items": [{"name": "main.py", "path": "src/main.py", "repository": {"full_name": "user/repo"}, "html_url": "https://github.com/user/repo/blob/main/src/main.py"}],
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_search_code", {"query": "def main"})
        assert "main.py" in str(result)


@respx.mock
@pytest.mark.asyncio
async def test_github_get_pr(github_core):
    respx.get("https://api.github.com/repos/owner/repo/pulls/10").mock(
        return_value=httpx.Response(200, json={
            "number": 10, "title": "Fix bug", "state": "open", "body": "Details",
            "html_url": "https://github.com/owner/repo/pull/10",
            "user": {"login": "dev"}, "merged": False,
            "additions": 10, "deletions": 3, "changed_files": 2,
        })
    )
    from fastmcp import Client
    async with Client(github_server) as client:
        result = await client.call_tool("github_get_pr", {"owner": "owner", "repo": "repo", "number": 10})
        assert "Fix bug" in str(result)
