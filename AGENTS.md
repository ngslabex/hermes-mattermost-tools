# AGENTS.md — hermes-mattermost-tools

Guidance for AI coding assistants working on this repository.

## What this is

A plugin for [Hermes Agent](https://github.com/NousResearch/hermes-agent) that registers four agent-callable Mattermost tools: `mm_send`, `mm_read`, `mm_list_channels`, `mm_open_dm`. It gives the Hermes agent proactive, two-way access to Mattermost — not just the ability to respond when messaged, but to initiate messages in any channel or DM.

## Repo layout

```
plugin.yaml      — Hermes plugin manifest
__init__.py      — Plugin entry point; register(ctx) is called by the Hermes plugin loader
tools.py         — JSON schemas (OpenAI tool-calling format) and handler functions
client.py        — Synchronous Mattermost v4 REST API client (stdlib urllib only)
```

## How Hermes plugins work

Hermes discovers plugins in `~/.hermes/plugins/<name>/`. A plugin directory must contain:
- `plugin.yaml` — manifest with `name`, `kind`, `version`, `provides_tools`
- `__init__.py` — with a top-level `register(ctx)` function

The `ctx` object exposes `ctx.register_tool(name, toolset, schema, handler, check_fn, emoji)`. The `check_fn` is called before each tool dispatch — return `False` to silently skip the tool (e.g. when env vars are missing). Tool handlers receive `(args: dict, **kwargs)` and must return a JSON string.

The plugin system is documented in `hermes-agent/hermes_cli/plugins.py`.

## Key design decisions

**No aiohttp / asyncio.** The Hermes tool dispatch loop is synchronous. The gateway adapter uses aiohttp in its own event loop, but tool handlers run in a standard thread. This plugin uses `urllib.request` only — zero new dependencies.

**No gateway adapter reuse.** We do not import from `plugins.platforms.mattermost.adapter`. That module manages a persistent WebSocket connection owned by the gateway. Tools need stateless one-shot HTTP calls, which `client.py` provides directly.

**`check_fn` gates on env vars.** The tools register unconditionally (so they appear in `hermes tools list`) but `_check_available()` returns `False` when `MATTERMOST_URL` or `MATTERMOST_TOKEN` are missing, preventing dispatch errors.

## Adding a new tool

1. Add a `MY_TOOL_SCHEMA` dict and `handle_my_tool(args, **_) -> str` in `tools.py`.
2. Register it in `__init__.py` by adding a row to `_TOOLS`.
3. Add the tool name to `provides_tools` in `plugin.yaml`.

## Testing

There are no automated tests yet. To test manually:

```bash
# Install into your local Hermes
ln -sf $(pwd) ~/.hermes/plugins/mattermost-tools

# Start a new session (plugins load at startup)
hermes

# In-session
/tools   # should show mm_send, mm_read, mm_list_channels, mm_open_dm
```

Or ask the agent: "List my Mattermost channels" and observe the tool call.

## Mattermost API reference

- Posts: `POST /api/v4/posts`
- Channel posts: `GET /api/v4/channels/{channel_id}/posts`
- Channel by name: `GET /api/v4/teams/{team_id}/channels/name/{channel_name}`
- Channel search: `POST /api/v4/teams/{team_id}/channels/search`
- Team channels: `GET /api/v4/teams/{team_id}/channels`
- Direct channel: `POST /api/v4/channels/direct`
- User by username: `GET /api/v4/users/username/{username}`
- Current user: `GET /api/v4/users/me`

Full docs: https://api.mattermost.com/

## What not to do

- Do not import from `plugins.platforms.mattermost` — that's the gateway adapter, not a library.
- Do not add async code to tool handlers — they run in a sync context.
- Do not hardcode channel IDs or user IDs — always resolve via `client.py` helpers.
- Do not store credentials — read from env vars at call time.
