# hermes-mattermost-tools

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) plugin that gives the agent proactive, two-way access to Mattermost — it can send messages to channels and DMs on its own, not just reply when spoken to.

## What this adds

| Tool | What it does |
|---|---|
| `mm_send` | Post a message to any channel or DM |
| `mm_read` | Read recent messages from a channel or DM |
| `mm_list_channels` | List channels the bot belongs to (public + private), or public-only |
| `mm_list_users` | List team members, optionally filtered by name |
| `mm_open_dm` | Open a DM with a user, optionally send a first message |

Without this plugin, the Hermes agent can only respond when a user messages it. With it, the agent can proactively notify channels, coordinate with other agents over a shared channel, kick off conversations, and read context before responding.

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent) with the Mattermost gateway platform already configured
- The same environment variables used by the gateway platform:
  - `MATTERMOST_URL` — your Mattermost server URL
  - `MATTERMOST_TOKEN` — bot account or personal access token

No additional credentials needed.

## Installation

Link or copy the plugin directory into your Hermes user plugins folder:

```bash
# Clone directly into the Hermes plugins directory
git clone https://github.com/i-n-n-k-e-e-p-e-r/hermes-mattermost-tools ~/.hermes/plugins/mattermost-tools

# Or symlink from a local checkout
ln -s /path/to/hermes-mattermost-tools ~/.hermes/plugins/mattermost-tools
```

Hermes discovers plugins in `~/.hermes/plugins/`, but they are **opt-in** — you must explicitly enable each one in `config.yaml`. Add `mattermost-tools` to your enabled list:

```bash
# Check what's currently enabled
hermes config show | grep -A5 'plugins:'

# Add mattermost-tools (keep your existing plugins in the list)
hermes config set plugins.enabled '["mattermost-tools"]'
```

> If you already have other plugins enabled, include them in the array:
> `hermes config set plugins.enabled '["my-other-plugin","mattermost-tools"]'`
>
> Note: `hermes config set` replaces the entire list, not appends.

Then start a new Hermes session (plugins load at startup).

Verify the tools loaded:

```bash
hermes tools list | grep mm_
```

You should see `mm_send`, `mm_read`, `mm_list_channels`, `mm_open_dm` listed under the `mattermost` toolset.

## Usage examples

Once installed the agent can use these tools on its own. You can also ask it directly:

> "Send a message to #agents-flood saying the build finished"

> "Read the last 10 messages in #general"

> "Open a DM with @alice and let her know the report is ready"

> "What channels exist with 'agent' in the name?"

## Design notes

Hermes ships with a `send_message` engine used by cron jobs and the CLI, but it is intentionally not exposed to the agent as a model tool — the core team's position is that the agent should not fire off cross-platform messages autonomously. This plugin is an explicit opt-in: install it when you want the agent to have that capability in your environment.

The plugin uses only the stdlib `urllib` for HTTP — no new dependencies. It reuses the Mattermost v4 REST API that the gateway adapter already talks to.

## Structure

```
hermes-mattermost-tools/
├── plugin.yaml      # Plugin manifest (name, version, required env vars)
├── __init__.py      # Plugin entry point — register(ctx) called by Hermes
├── tools.py         # Tool schemas and handlers
├── client.py        # Thin synchronous Mattermost REST API client
├── AGENTS.md        # Guidance for AI coding assistants working on this repo
└── README.md        # This file
```

## License

MIT
