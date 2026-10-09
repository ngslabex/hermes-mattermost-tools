"""Tool schemas and handlers for the Hermes Mattermost tools plugin."""

from __future__ import annotations

import datetime
import json
import os
from typing import Any, Dict, Iterable, List


MM_SEND_SCHEMA: Dict[str, Any] = {
    "name": "mm_send",
    "description": (
        "Send a message to a Mattermost channel or direct-message conversation. "
        "Long messages are split automatically into ordered posts. Accepts a "
        "channel name, channel ID, or '@username' for a DM."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": "Channel name, channel ID, or '@username' for a DM.",
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
        "Read recent messages from a Mattermost channel or DM. Returns posts "
        "newest first. Reads standard text, attachment-only webhook posts, "
        "Slack-compatible attachments, fields, and Mattermost blocks."
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
                "description": "Number of messages to return (1-100, default 20).",
                "default": 20,
            },
        },
        "required": ["target"],
    },
}

MM_LIST_CHANNELS_SCHEMA: Dict[str, Any] = {
    "name": "mm_list_channels",
    "description": (
        "List Mattermost channels. scope='joined' returns channels the bot has "
        "joined; scope='public' discovers public channels."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["joined", "public"],
                "default": "joined",
            },
            "search": {
                "type": "string",
                "description": "Optional channel-name filter.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum channels to return (1-200, default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

MM_LIST_USERS_SCHEMA: Dict[str, Any] = {
    "name": "mm_list_users",
    "description": "List Mattermost team members, optionally filtered by name.",
    "parameters": {
        "type": "object",
        "properties": {
            "search": {
                "type": "string",
                "description": "Optional username or display-name filter.",
            },
            "limit": {
                "type": "integer",
                "description": "Maximum users to return (1-200, default 50).",
                "default": 50,
            },
        },
        "required": [],
    },
}

MM_OPEN_DM_SCHEMA: Dict[str, Any] = {
    "name": "mm_open_dm",
    "description": (
        "Open a direct-message conversation and optionally send the first message."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "username": {
                "type": "string",
                "description": "Mattermost username, with or without '@'.",
            },
            "message": {
                "type": "string",
                "description": "Optional opening message.",
            },
        },
        "required": ["username"],
    },
}


def _check_available() -> bool:
    return bool(os.environ.get("MATTERMOST_URL") and os.environ.get("MATTERMOST_TOKEN"))


def _resolve_target(target: str):
    """Return ``(channel_id, is_dm)`` for a channel, ID, or username."""
    from .client import open_direct_channel, resolve_channel, resolve_user

    if target.startswith("@"):
        user_id = resolve_user(target)
        return open_direct_channel(user_id), True
    return resolve_channel(target), False


def _append_text(parts: List[str], value: Any) -> None:
    if isinstance(value, str) and value.strip():
        parts.append(value.strip())


def _deduplicate(parts: Iterable[str]) -> List[str]:
    unique: List[str] = []
    seen = set()
    for part in parts:
        normalized = part.strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def _parse_list(value: Any) -> List[Any]:
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
    return value if isinstance(value, list) else []


def _extract_attachment_text(value: Any) -> List[str]:
    """Extract visible text from Slack-compatible Mattermost attachments."""
    parts: List[str] = []
    for attachment in _parse_list(value):
        if not isinstance(attachment, dict):
            continue
        for key in ("pretext", "title", "text", "fallback"):
            _append_text(parts, attachment.get(key))
        for field in _parse_list(attachment.get("fields")):
            if not isinstance(field, dict):
                continue
            title = str(field.get("title") or "").strip()
            field_value = str(field.get("value") or "").strip()
            if title and field_value:
                parts.append(f"{title}: {field_value}")
            elif field_value:
                parts.append(field_value)
        for key, label in (("image_url", "Image"), ("title_link", "Link")):
            item = attachment.get(key)
            if isinstance(item, str) and item.strip():
                parts.append(f"{label}: {item.strip()}")
    return parts


def _extract_block_text(value: Any) -> List[str]:
    parts: List[str] = []
    for block in _parse_list(value):
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if isinstance(text, dict):
            text = text.get("text")
        _append_text(parts, text)
        for field in _parse_list(block.get("fields")):
            _append_text(parts, field.get("text") if isinstance(field, dict) else field)
    return parts


def _format_timestamp(timestamp_ms: Any) -> str:
    try:
        return datetime.datetime.fromtimestamp(
            int(timestamp_ms) / 1000,
            tz=datetime.timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return "unknown-time"


def _fmt_posts(posts_data: dict, limit: int) -> str:
    """Format posts, including attachment-only webhook posts."""
    order = posts_data.get("order", [])
    posts = posts_data.get("posts", {})
    if not isinstance(order, list) or not isinstance(posts, dict):
        return "(no messages)"

    output: List[str] = []
    for post_id in order[:limit]:
        post = posts.get(post_id, {})
        if not isinstance(post, dict):
            continue
        props = post.get("props") or {}
        if not isinstance(props, dict):
            props = {}
        author = props.get("override_username") or post.get("user_id") or "unknown"
        timestamp = _format_timestamp(post.get("create_at", 0))

        parts: List[str] = []
        _append_text(parts, post.get("message"))
        parts.extend(_extract_attachment_text(props.get("attachments")))
        parts.extend(_extract_block_text(props.get("mm_blocks")))
        message = "\n".join(_deduplicate(parts)) or "(empty post)"
        output.append(f"[{timestamp}] {author}: {message}")

    return "\n\n".join(output) if output else "(no messages)"


def _split_message(message: str, max_length: int = 4000) -> List[str]:
    """Split long Markdown at paragraph, line, word, then hard boundaries."""
    message = message.strip()
    if not message:
        return []
    if max_length < 500:
        raise ValueError("max_length must be at least 500")
    if len(message) <= max_length:
        return [message]

    chunks: List[str] = []
    remaining = message
    while len(remaining) > max_length:
        split_at = remaining.rfind("\n\n", 0, max_length + 1)
        if split_at < max_length // 2:
            split_at = remaining.rfind("\n", 0, max_length + 1)
        if split_at < max_length // 2:
            split_at = remaining.rfind(" ", 0, max_length + 1)
        if split_at <= 0:
            split_at = max_length
        chunk = remaining[:split_at].strip()
        if chunk:
            chunks.append(chunk)
        remaining = remaining[split_at:].strip()
    if remaining:
        chunks.append(remaining)
    return chunks


def _part_prefix(index: int, total: int) -> str:
    return f"**Part {index}/{total}**\n\n" if total > 1 else ""


def handle_mm_send(args: Dict[str, Any], **_) -> str:
    target = (args.get("target") or "").strip()
    message = (args.get("message") or "").strip()
    if not target:
        return json.dumps({"error": "target is required"})
    if not message:
        return json.dumps({"error": "message is required"})

    try:
        from .client import _request

        channel_id, _is_dm = _resolve_target(target)
        chunks = _split_message(message, max_length=4000)
        post_ids: List[str] = []
        total = len(chunks)

        for index, chunk in enumerate(chunks, start=1):
            rendered = f"{_part_prefix(index, total)}{chunk}"
            data = _request(
                "POST",
                "posts",
                {"channel_id": channel_id, "message": rendered},
            )
            post_ids.append(data.get("id", "?"))

        return json.dumps(
            {
                "ok": True,
                "channel_id": channel_id,
                "post_ids": post_ids,
                "post_count": len(post_ids),
                "character_count": len(message),
            }
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_read(args: Dict[str, Any], **_) -> str:
    target = (args.get("target") or "").strip()
    try:
        limit = max(1, min(100, int(args.get("limit") or 20)))
    except (TypeError, ValueError):
        return json.dumps({"error": "limit must be an integer"})
    if not target:
        return json.dumps({"error": "target is required"})

    try:
        from .client import _request

        channel_id, _is_dm = _resolve_target(target)
        data = _request(
            "GET",
            f"channels/{channel_id}/posts",
            params={"page": 0, "per_page": limit},
        )
        return _fmt_posts(data, limit)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_list_channels(args: Dict[str, Any], **_) -> str:
    scope = (args.get("scope") or "joined").strip()
    search = (args.get("search") or "").strip()
    if scope not in {"joined", "public"}:
        return json.dumps({"error": "scope must be 'joined' or 'public'"})
    try:
        limit = max(1, min(200, int(args.get("limit") or 50)))
    except (TypeError, ValueError):
        return json.dumps({"error": "limit must be an integer"})

    try:
        from .client import _request, get_team_id, list_team_channels

        team_id = get_team_id()
        results = (
            _request("POST", f"teams/{team_id}/channels/search", {"term": search})
            if search
            else list_team_channels(team_id, scope=scope, limit=limit)
        ) or []
        channels = [
            {
                "id": channel["id"],
                "name": channel.get("name"),
                "display_name": channel.get("display_name"),
                "type": channel.get("type"),
            }
            for channel in results[:limit]
            if isinstance(channel, dict) and channel.get("id")
        ]
        return json.dumps(channels, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_list_users(args: Dict[str, Any], **_) -> str:
    search = (args.get("search") or "").strip()
    try:
        limit = max(1, min(200, int(args.get("limit") or 50)))
    except (TypeError, ValueError):
        return json.dumps({"error": "limit must be an integer"})

    try:
        from .client import get_team_id, list_team_members

        users = list_team_members(get_team_id(), limit=limit, search=search)
        result = []
        for user in users:
            if not isinstance(user, dict) or not user.get("id"):
                continue
            full_name = f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
            result.append(
                {
                    "id": user["id"],
                    "username": user.get("username"),
                    "display_name": full_name or user.get("username"),
                    "email": user.get("email"),
                }
            )
        return json.dumps(result, indent=2)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def handle_mm_open_dm(args: Dict[str, Any], **_) -> str:
    username = (args.get("username") or "").strip()
    message = (args.get("message") or "").strip()
    if not username:
        return json.dumps({"error": "username is required"})

    try:
        from .client import _request, open_direct_channel, resolve_user

        user_id = resolve_user(username)
        channel_id = open_direct_channel(user_id)
        result: Dict[str, Any] = {
            "ok": True,
            "channel_id": channel_id,
            "user_id": user_id,
        }
        if message:
            data = _request(
                "POST",
                "posts",
                {"channel_id": channel_id, "message": message},
            )
            result["post_id"] = data.get("id", "?")
        return json.dumps(result)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
