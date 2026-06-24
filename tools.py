"""
Tool handlers and JSON schemas for the Mattermost agent tools.

Four tools:
  mm_send          — post a message to a channel or DM
  mm_read          — read recent messages from a channel
  mm_list_channels — list channels in the team
  mm_open_dm       — open a DM and optionally send a first message
"""

from __future__ import annotations

import json
from typing import Any, Dict


# ---------------------------------------------------------------------------
# JSON Schemas (OpenAI tool-calling format)
# ---------------------------------------------------------------------------

MM_SEND_SCHEMA: Dict[str, Any] = {
    "name": "mm_send",
    "description": (
        "Send a message to a Mattermost channel or direct-message conversation. "
        "Accepts a channel name (e.g. 'agents-flood', '~town-square'), a channel ID, "
        "or a username prefixed with '@' for a DM (e.g. '@alice'). "
        "Use this whenever you need to post proactively — notifications, status updates, "
        "or kicking off a conversation in a specific channel."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "Channel name, channel ID, or '@username' for a DM. "
                    "Examples: 'agents-flood', 'town-square', '@bob', 'abc123def456ghi789jkl012mn'."
                ),
            },
            "message": {
                "type": "string",
                "description": "Message text. Mattermost renders standard Markdown.",
            },
        },
        "required": ["target", "message"],
    },
}

MM_READ_SCHEMA: Dict[str, Any] = {
    "name": "mm_read",
    "description": (
        "Read recent messages from a Mattermost channel or DM. "
        "Returns posts in reverse-chronological order (newest first). "
        "Use this to catch up on a channel before responding, or to check "
        "whether a message you sent was received."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Channel name, channel ID, or '@username' for a DM.",
            },
            "limit": {
                "type": "integer",
                "description": "Number of messages to return (1–100, default 20).",
                "default": 20,
            },
        },
        "required": ["target"],
    },
}

MM_LIST_CHANNELS_SCHEMA: Dict[str, Any] = {
    "name": "mm_list_channels",
    "description": (
        "List Mattermost channels. "
        "scope='joined' (default) returns all channels the bot is a member of — "
        "both public and private. Use this to see what's available before posting. "
        "scope='public' returns public channels only, useful for discovery. "
        "Returns channel names, IDs, and types."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["joined", "public"],
                "description": (
                    "'joined' (default): all channels the bot belongs to (public + private). "
                    "'public': public channels only, regardless of membership."
                ),
                "default": "joined",
            },
            "search": {
                "type": "string",
                "description": "Optional keyword to filter results by channel name.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum channels to return (1–200, default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}
MM_OPEN_DM_SCHEMA: Dict[str, Any] = {
    "name": "mm_open_dm",
    "description": (
        "Open a direct-message conversation with a Mattermost user. "
        "Optionally sends an initial message. Returns the DM channel ID "
        "which you can then pass to mm_send or mm_read."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "username": {
                "type": "string",
                "description": "Mattermost username (with or without leading '@').",
            },
            "message": {
                "type": "string",
                "description": "Optional opening message to send immediately.",
            },
        },
        "required": ["username"],
    },
}

MM_LIST_USERS_SCHEMA: Dict[str, Any] = {
    "name": "mm_list_users",
    "description": (
        "List users in the Mattermost team. "
        "Returns usernames, display names, and user IDs. "
        "Use this to find someone's username before opening a DM or @mentioning them. "
        "Supports optional search to filter by name or username."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional keyword to filter by username or display name.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum users to return (1–200, default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def _check_available() -> bool:
    import os
    return bool(os.environ.get("MATTERMOST_URL") and os.environ.get("MATTERMOST_TOKEN"))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _resolve_target(target: str):
    """Return (channel_id, is_dm) for any target string."""
    from .client import open_direct_channel, resolve_channel, resolve_user
    if target.startswith("@"):
        uid = resolve_user(target)
        cid = open_direct_channel(uid)
        return cid, True
    cid = resolve_channel(target)
    return cid, False


def _fmt_posts(posts_data: dict, limit: int) -> str:
    """Format a Mattermost posts response into readable text."""
    order = posts_data.get("order", [])
    posts = posts_data.get("posts", {})
    out = []
    for pid in order[:limit]:
        p = posts.get(pid, {})
        author = p.get("props", {}).get("override_username") or p.get("user_id", "?")
        ts_ms = p.get("create_at", 0)
        import datetime
        ts = datetime.datetime.utcfromtimestamp(ts_ms / 1000).strftime("%Y-%m-%d %H:%M UTC")
        msg = p.get("message", "").strip()
        out.append(f"[{ts}] {author}: {msg}")
    return "\n".join(out) if out else "(no messages)"


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_mm_send(args: Dict[str, Any], **_) -> str:
    target = (args.get("target") or "").strip()
    message = (args.get("message") or "").strip()
    if not target:
        return json.dumps({"error": "target is required"})
    if not message:
        return json.dumps({"error": "message is required"})
    try:
        from .client import _request, open_direct_channel, resolve_user, resolve_channel
        channel_id, is_dm = _resolve_target(target)
        data = _request("POST", "posts", {"channel_id": channel_id, "message": message})
        post_id = data.get("id", "?")
        return json.dumps({"ok": True, "post_id": post_id, "channel_id": channel_id})
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_read(args: Dict[str, Any], **_) -> str:
    target = (args.get("target") or "").strip()
    limit = max(1, min(100, int(args.get("limit") or 20)))
    if not target:
        return json.dumps({"error": "target is required"})
    try:
        from .client import _request
        channel_id, _ = _resolve_target(target)
        data = _request("GET", f"channels/{channel_id}/posts", params={"per_page": limit})
        return _fmt_posts(data, limit)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_list_channels(args: Dict[str, Any], **_) -> str:
    scope = (args.get("scope") or "joined").strip()
    search = (args.get("search") or "").strip()
    limit = max(1, min(200, int(args.get("limit") or 50)))
    try:
        from .client import get_team_id, list_team_channels, _request
        team_id = get_team_id()
        if search:
            results = _request("POST", f"teams/{team_id}/channels/search", {"term": search}) or []
        else:
            results = list_team_channels(team_id, scope=scope, limit=limit)
        channels = [
            {"id": c["id"], "name": c.get("name"), "display_name": c.get("display_name"), "type": c.get("type")}
            for c in results[:limit]
        ]
        return json.dumps(channels, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_list_users(args: Dict[str, Any], **_) -> str:
    search = (args.get("search") or "").strip()
    limit = max(1, min(200, int(args.get("limit") or 50)))
    try:
        from .client import get_team_id, list_team_members
        team_id = get_team_id()
        users = list_team_members(team_id, limit=limit, search=search)
        result = [
            {
                "id": u["id"],
                "username": u.get("username"),
                "display_name": (u.get("props") or {}).get("customStatus") or
                                f"{u.get('first_name', '')} {u.get('last_name', '')}".strip()
                                or u.get("username"),
                "email": u.get("email"),
            }
            for u in users
        ]
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_open_dm(args: Dict[str, Any], **_) -> str:
    username = (args.get("username") or "").strip()
    message = (args.get("message") or "").strip()
    if not username:
        return json.dumps({"error": "username is required"})
    try:
        from .client import open_direct_channel, resolve_user, _request
        uid = resolve_user(username)
        channel_id = open_direct_channel(uid)
        result: Dict[str, Any] = {"ok": True, "channel_id": channel_id, "user_id": uid}
        if message:
            data = _request("POST", "posts", {"channel_id": channel_id, "message": message})
            result["post_id"] = data.get("id", "?")
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
