"""GitHub adapter — 5 tools for repos, issues, PRs, and code search."""
from __future__ import annotations

from typing import Annotated
from pydantic import Field

import httpx
from fastmcp import FastMCP
from spine import Core
from conduit.gate import check_gate

SERVICE = "github"
API = "https://api.github.com"

server = FastMCP("GitHub")


def _headers() -> dict[str, str]:
    tokens = Core.instance().get("tokens")
    config = Core.instance().get("config")
    token = tokens.get(config.github.token_ref)
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


@server.tool
async def github_list_repos(
    sort: Annotated[str, Field(description="Sort by: updated, created, pushed, full_name")] = "updated",
    per_page: Annotated[int, Field(description="Results per page (max 100)", ge=1, le=100)] = 30,
) -> list[dict]:
    """List your GitHub repositories, sorted by most recently updated."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/user/repos",
            headers=_headers(),
            params={"sort": sort, "per_page": per_page, "type": "owner"},
        )
        resp.raise_for_status()
    return [
        {"name": r["full_name"], "description": r["description"],
         "url": r["html_url"], "stars": r["stargazers_count"], "language": r["language"]}
        for r in resp.json()
    ]


@server.tool
async def github_create_issue(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    title: Annotated[str, Field(description="Issue title")],
    body: Annotated[str, Field(description="Issue body (markdown)")] = "",
    labels: Annotated[list[str], Field(description="Labels to apply")] = [],
) -> dict:
    """Create a new issue in a GitHub repository."""
    check_gate(SERVICE)
    payload = {"title": title, "body": body}
    if labels:
        payload["labels"] = labels
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{API}/repos/{owner}/{repo}/issues",
            headers=_headers(),
            json=payload,
        )
        resp.raise_for_status()
    data = resp.json()
    return {"number": data["number"], "title": data["title"], "url": data["html_url"]}


@server.tool
async def github_list_prs(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    state: Annotated[str, Field(description="Filter: open, closed, all")] = "open",
) -> list[dict]:
    """List pull requests for a GitHub repository."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/repos/{owner}/{repo}/pulls",
            headers=_headers(),
            params={"state": state, "per_page": 30},
        )
        resp.raise_for_status()
    return [
        {"number": p["number"], "title": p["title"], "state": p["state"],
         "author": p["user"]["login"], "url": p["html_url"]}
        for p in resp.json()
    ]


@server.tool
async def github_get_pr(
    owner: Annotated[str, Field(description="Repository owner")],
    repo: Annotated[str, Field(description="Repository name")],
    number: Annotated[int, Field(description="PR number")],
) -> dict:
    """Get details of a specific pull request."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/repos/{owner}/{repo}/pulls/{number}",
            headers=_headers(),
        )
        resp.raise_for_status()
    pr = resp.json()
    return {
        "number": pr["number"], "title": pr["title"], "state": pr["state"],
        "body": pr.get("body", ""), "author": pr["user"]["login"],
        "merged": pr["merged"], "additions": pr["additions"],
        "deletions": pr["deletions"], "changed_files": pr["changed_files"],
        "url": pr["html_url"],
    }


@server.tool
async def github_search_code(
    query: Annotated[str, Field(description="Search query (GitHub code search syntax)")],
    per_page: Annotated[int, Field(description="Results per page", ge=1, le=100)] = 10,
) -> dict:
    """Search code across GitHub repositories."""
    check_gate(SERVICE)
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{API}/search/code",
            headers=_headers(),
            params={"q": query, "per_page": per_page},
        )
        resp.raise_for_status()
    data = resp.json()
    return {
        "total_count": data["total_count"],
        "items": [
            {"file": i["name"], "path": i["path"],
             "repo": i["repository"]["full_name"], "url": i["html_url"]}
            for i in data["items"]
        ],
    }
