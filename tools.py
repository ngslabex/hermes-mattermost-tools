"""
Tool handlers and JSON schemas for the Mattermost agent tools.

Five tools:
  mm_send          - post a message to a channel or DM
  mm_read          - read recent messages from a channel or DM
  mm_list_channels - list channels in the team
  mm_list_users    - list users in the team
  mm_open_dm       - open a DM and optionally send a first message
"""

from __future__ import annotations

import datetime
import json
from typing import Any, Dict, Iterable, List


# ---------------------------------------------------------------------------
# JSON Schemas (OpenAI tool-calling format)
# ---------------------------------------------------------------------------

MM_SEND_SCHEMA: Dict[str, Any] = {
    "name": "mm_send",
    "description": (
    "Send a message to a Mattermost channel or direct-message "
    "conversation. Long messages are automatically split into "
    "multiple ordered posts. Accepts a channel name, channel ID, "
    "or a username prefixed with '@' for a DM."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "target": {
                "type": "string",
                "description": (
                    "Channel name, channel ID, or '@username' for a DM. "
                    "Examples: 'agents-flood', 'town-square', '@bob', "
                    "'abc123def456ghi789jkl012mn'."
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
        "Reads standard message text and attachment-only webhook posts, including "
        "attachment title, pretext, text, fallback, fields, and Mattermost blocks. "
        "Use this to catch up on a channel before responding or to check whether "
        "a message was received."
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
        "List Mattermost channels. "
        "scope='joined' (default) returns all channels the bot is a member of, "
        "both public and private. Use this to see what is available before posting. "
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
                    "'joined' (default): all channels the bot belongs to (public and private). "
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
                "description": "Maximum channels to return (1-200, default 50).",
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
        "Optionally sends an initial message. Returns the DM channel ID, "
        "which can then be passed to mm_send or mm_read."
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
        "Use this to find a username before opening a DM or mentioning a user. "
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
                "description": "Maximum users to return (1-200, default 50).",
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

    return bool(
        os.environ.get("MATTERMOST_URL")
        and os.environ.get("MATTERMOST_TOKEN")
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_target(target: str):
    """Return (channel_id, is_dm) for any supported target string."""
    from .client import open_direct_channel, resolve_channel, resolve_user

    if target.startswith("@"):
        user_id = resolve_user(target)
        channel_id = open_direct_channel(user_id)
        return channel_id, True

    channel_id = resolve_channel(target)
    return channel_id, False


def _append_text(parts: List[str], value: Any) -> None:
    """Append a non-empty textual value to parts."""
    if isinstance(value, str):
        value = value.strip()
        if value:
            parts.append(value)


def _deduplicate(parts: Iterable[str]) -> List[str]:
    """Remove exact duplicates while preserving the original order."""
    unique: List[str] = []
    seen = set()

    for part in parts:
        normalized = part.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique.append(normalized)

    return unique


def _parse_attachments(value: Any) -> List[Dict[str, Any]]:
    """Normalize Mattermost attachment props into a list of dictionaries."""
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    if not isinstance(value, list):
        return []

    return [item for item in value if isinstance(item, dict)]


def _extract_attachment_text(attachments: Any) -> List[str]:
    """Extract readable text from Slack-compatible Mattermost attachments."""
    parts: List[str] = []

    for attachment in _parse_attachments(attachments):
        for key in ("pretext", "title", "text", "fallback"):
            _append_text(parts, attachment.get(key))

        fields = attachment.get("fields") or []
        if isinstance(fields, list):
            for field in fields:
                if not isinstance(field, dict):
                    continue

                field_title = str(field.get("title") or "").strip()
                field_value = str(field.get("value") or "").strip()

                if field_title and field_value:
                    parts.append(f"{field_title}: {field_value}")
                elif field_value:
                    parts.append(field_value)

        image_url = attachment.get("image_url")
        if isinstance(image_url, str) and image_url.strip():
            parts.append(f"Image: {image_url.strip()}")

        title_link = attachment.get("title_link")
        if isinstance(title_link, str) and title_link.strip():
            parts.append(f"Link: {title_link.strip()}")

    return parts


def _extract_block_text(blocks: Any) -> List[str]:
    """Extract readable text from Mattermost block data when present."""
    if isinstance(blocks, str):
        try:
            blocks = json.loads(blocks)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []

    if not isinstance(blocks, list):
        return []

    parts: List[str] = []

    for block in blocks:
        if not isinstance(block, dict):
            continue

        text = block.get("text")
        if isinstance(text, dict):
            text = text.get("text")
        _append_text(parts, text)

        fields = block.get("fields") or []
        if isinstance(fields, list):
            for field in fields:
                if isinstance(field, dict):
                    _append_text(parts, field.get("text"))
                else:
                    _append_text(parts, field)

    return parts


def _format_timestamp(timestamp_ms: Any) -> str:
    """Format a Mattermost millisecond timestamp as UTC."""
    try:
        return datetime.datetime.fromtimestamp(
            int(timestamp_ms) / 1000,
            tz=datetime.timezone.utc,
        ).strftime("%Y-%m-%d %H:%M UTC")
    except (TypeError, ValueError, OverflowError, OSError):
        return "unknown-time"


def _fmt_posts(posts_data: dict, limit: int) -> str:
    """Format Mattermost posts, including attachment-only webhook posts."""
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

        author = (
            props.get("override_username")
            or post.get("user_id")
            or "unknown"
        )
        timestamp = _format_timestamp(post.get("create_at", 0))

        message_parts: List[str] = []
        _append_text(message_parts, post.get("message"))

        message_parts.extend(
            _extract_attachment_text(props.get("attachments"))
        )
        message_parts.extend(
            _extract_block_text(props.get("mm_blocks"))
        )

        message_parts = _deduplicate(message_parts)
        formatted_message = "\n".join(message_parts) or "(empty post)"

        output.append(
            f"[{timestamp}] {author}: {formatted_message}"
        )

    return "\n\n".join(output) if output else "(no messages)"

# ---------------------------------------------------------------------------
# Split
# ---------------------------------------------------------------------------
def _split_message(
    message: str,
    max_length: int = 4000,
) -> List"""Split a long Mattermost message at safe Markdown boundaries."""

    message = message.strip()

    if not message:
        return []

    if len(message) <= max_length:
        return [message]

    chunks: List[str] = []
    remaining = message

    while len(remaining) > max_length:
        split_at = remaining.rfind("\n\n", 0, max_length)

        if split_at < max_length // 2:
            split_at = remaining.rfind("\n", 0, max_length)

        if split_at < max_length // 2:
            split_at = remaining.rfind(" ", 0, max_length)

        if split_at <= 0:
            split_at = max_length

        chunk = remaining[:split_at].strip()

        if chunk:
            chunks.append(chunk)

        remaining = remaining[split_at:].strip()

    if remaining:
        chunks.append(remaining)

    return chunks
# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def handle_mm_send(
    args: Dict[str, Any],
    **_,
) -> str:
    target = (args.get("target") or "").strip()
    message = (args.get("message") or "").strip()

    if not target:
        return json.dumps({
            "error": "target is required",
        })

    if not message:
        return json.dumps({
            "error": "message is required",
        })

    try:
        from .client import _request

        channel_id, _is_dm = _resolve_target(target)
        chunks = _split_message(message, max_length=4000)
        post_ids: List[str] = []

        total = len(chunks)

        for index, chunk in enumerate(chunks, start=1):
            if total > 1:
                chunk = (
                    f"**Part {index}/{total}**\n\n"
                    f"{chunk}"
                )

            data = _request(
                "POST",
                "posts",
                {
                    "channel_id": channel_id,
                    "message": chunk,
                },
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
        return json.dumps({
            "error": str(exc),
        })


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
        if search:
            results = _request(
                "POST",
                f"teams/{team_id}/channels/search",
                {"term": search},
            ) or []
        else:
            results = list_team_channels(
                team_id,
                scope=scope,
                limit=limit,
            )

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

        team_id = get_team_id()
        users = list_team_members(team_id, limit=limit, search=search)

        result = []
        for user in users:
            if not isinstance(user, dict) or not user.get("id"):
                continue

            full_name = (
                f"{user.get('first_name', '')} {user.get('last_name', '')}"
            ).strip()
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
