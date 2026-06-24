"""
hermes-mattermost-tools plugin entry point.

Registers four agent-callable tools into the ``mattermost`` toolset:
  mm_send, mm_read, mm_list_channels, mm_open_dm

Called once by the Hermes plugin loader at startup.
"""

from __future__ import annotations

from .tools import (
    MM_LIST_CHANNELS_SCHEMA,
    MM_LIST_USERS_SCHEMA,
    MM_OPEN_DM_SCHEMA,
    MM_READ_SCHEMA,
    MM_SEND_SCHEMA,
    _check_available,
    handle_mm_list_channels,
    handle_mm_list_users,
    handle_mm_open_dm,
    handle_mm_read,
    handle_mm_send,
)

_TOOLS = (
    ("mm_send",          MM_SEND_SCHEMA,          handle_mm_send,          "📨"),
    ("mm_read",          MM_READ_SCHEMA,           handle_mm_read,          "📬"),
    ("mm_list_channels", MM_LIST_CHANNELS_SCHEMA,  handle_mm_list_channels, "📋"),
    ("mm_open_dm",       MM_OPEN_DM_SCHEMA,        handle_mm_open_dm,       "💬"),
    ("mm_list_users",    MM_LIST_USERS_SCHEMA,     handle_mm_list_users,    "👥"),
)


def register(ctx) -> None:
    """Register all Mattermost tools. Called once by the plugin loader."""
    for name, schema, handler, emoji in _TOOLS:
        ctx.register_tool(
            name=name,
            toolset="mattermost",
            schema=schema,
            handler=handler,
            check_fn=_check_available,
            emoji=emoji,
        )
