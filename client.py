"""
hermes-mattermost-tools
=======================

Mattermost REST API client for the agent tools.

All calls are synchronous wrappers around the Mattermost v4 REST API so they
can be called from standard tool handlers without managing an event loop.
The module re-uses the MATTERMOST_URL and MATTERMOST_TOKEN env vars that the
gateway platform adapter already requires — no new credentials needed.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional


def _base_url() -> str:
    url = os.environ.get("MATTERMOST_URL", "").rstrip("/")
    if not url:
        raise RuntimeError("MATTERMOST_URL is not set")
    return url


def _token() -> str:
    token = os.environ.get("MATTERMOST_TOKEN", "")
    if not token:
        raise RuntimeError("MATTERMOST_TOKEN is not set")
    return token


def _headers() -> Dict[str, str]:
    return {
        "Authorization": f"Bearer {_token()}",
        "Content-Type": "application/json",
        "User-Agent": "hermes-mattermost-tools/0.1",
    }


def _request(
    method: str,
    path: str,
    payload: Any = None,
    params: Optional[Dict[str, Any]] = None,
) -> Any:
    """Make a Mattermost API request; return parsed JSON or raise on error."""
    url = f"{_base_url()}/api/v4/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=body, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode(errors="replace")
        raise RuntimeError(
            f"Mattermost API {method} {path} → HTTP {exc.code}: {body_text[:300]}"
        ) from exc


# ---------------------------------------------------------------------------
# Public helpers used by the tool handlers
# ---------------------------------------------------------------------------

def get_teams() -> List[Dict[str, Any]]:
    """Return all teams the bot belongs to."""
    return _request("GET", "users/me/teams") or []


def get_team_id() -> str:
    """Return the ID of the first team, used when only one team exists."""
    teams = get_teams()
    if not teams:
        raise RuntimeError("Bot is not a member of any Mattermost team")
    return teams[0]["id"]


def list_team_channels(team_id: str, scope: str = "joined", limit: int = 200) -> List[Dict[str, Any]]:
    """
    Return channels for the team.

    scope='joined'  → /users/me/teams/{team_id}/channels
        All channels the bot is a member of (public + private).
    scope='public'  → /teams/{team_id}/channels
        Public channels only (regardless of membership).
    """
    if scope == "joined":
        return _request("GET", f"users/me/teams/{team_id}/channels") or []
    else:
        return _request("GET", f"teams/{team_id}/channels", params={"per_page": limit}) or []


def list_team_members(team_id: str, limit: int = 200, search: str = "") -> List[Dict[str, Any]]:
    """Return users in the team, optionally filtered by search term."""
    if search:
        results = _request("POST", "users/search", {"term": search, "team_id": team_id}) or []
        return results[:limit]
    return _request("GET", f"users", params={"in_team": team_id, "per_page": limit, "active": "true"}) or []


def resolve_channel(name_or_id: str, team_id: Optional[str] = None) -> str:
    """
    Resolve a channel name or ID to a channel ID.

    Accepts:
      - A raw channel ID (26-char alphanumeric) — returned as-is.
      - A display name or handle — searched within the team.
    """
    # Looks like an ID already (Mattermost IDs are 26 lowercase alphanum chars)
    if len(name_or_id) == 26 and name_or_id.isalnum():
        return name_or_id

    tid = team_id or get_team_id()
    # Try exact name match first
    name_slug = name_or_id.lower().strip().lstrip("~#")
    try:
        data = _request("GET", f"teams/{tid}/channels/name/{urllib.parse.quote(name_slug)}")
        if data and "id" in data:
            return data["id"]
    except RuntimeError:
        pass

    # Fall back to search
    results = _request("POST", f"teams/{tid}/channels/search", {"term": name_slug}) or []
    matches = [c for c in results if c.get("name") == name_slug or c.get("display_name", "").lower() == name_slug]
    if matches:
        return matches[0]["id"]
    if results:
        return results[0]["id"]

    raise RuntimeError(f"Channel not found: {name_or_id!r}")


def resolve_user(username_or_id: str) -> str:
    """Resolve a username or user ID to a user ID."""
    if len(username_or_id) == 26 and username_or_id.isalnum():
        return username_or_id
    handle = username_or_id.lstrip("@")
    data = _request("GET", f"users/username/{urllib.parse.quote(handle)}")
    if data and "id" in data:
        return data["id"]
    raise RuntimeError(f"User not found: {username_or_id!r}")


def open_direct_channel(user_id: str) -> str:
    """Open (or get existing) DM channel with a user; return channel ID."""
    me = _request("GET", "users/me")
    my_id = me["id"]
    data = _request("POST", "channels/direct", [my_id, user_id])
    if data and "id" in data:
        return data["id"]
    raise RuntimeError(f"Could not open DM with user {user_id}")
