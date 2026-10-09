# hermes-mattermost-tools

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) backend plugin that gives the agent proactive, two-way access to Mattermost. The plugin can send messages to channels and direct-message conversations, read recent channel history, list channels and users, and open direct-message conversations.

Version `0.2.0` adds support for attachment-only webhook posts, including Zabbix and other integrations that store visible message content under Mattermost `props.attachments` rather than the top-level `message` field.

## What this adds

| Tool | Description |
|---|---|
| `mm_send` | Post a message to a Mattermost channel or direct-message conversation. |
| `mm_read` | Read recent messages from a channel or DM, including standard text posts, attachment-only webhook posts, Slack-compatible attachments, and Mattermost blocks. |
| `mm_list_channels` | List channels the bot belongs to, including public and private channels, or discover public channels. |
| `mm_list_users` | List team members, optionally filtered by username or display name. |
| `mm_open_dm` | Open a DM with a user and optionally send the first message. |

Without this plugin, the Hermes Mattermost gateway primarily responds when a user messages or mentions the agent. With this plugin enabled, the agent can explicitly read channel context, send proactive notifications, list Mattermost resources, and coordinate through shared channels.

## Message types supported by `mm_read`

The `mm_read` tool reads the following Mattermost post content:

- Standard top-level `message` text
- Attachment-only webhook posts
- Slack-compatible attachment fields:
  - `pretext`
  - `title`
  - `text`
  - `fallback`
  - `fields`
  - `image_url`
  - `title_link`
- Mattermost block text under `props.mm_blocks`
- Block field text

This is important for monitoring integrations such as Zabbix. A Zabbix alarm may appear correctly in the Mattermost interface while its top-level `message` field is empty. The visible alarm title, host, IP address, severity, event time, tags, and description can instead be stored under `props.attachments`. Version `0.2.0` extracts those values and returns them as readable text to Hermes.

## Requirements

- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- A configured Mattermost server and bot account or personal access token
- The bot must belong to the target Mattermost team
- The bot must belong to every private channel it needs to read
- `MATTERMOST_URL` and `MATTERMOST_TOKEN` must be available in the Hermes process environment

No additional Python dependencies are required. The plugin uses Python standard-library `urllib` for Mattermost REST API requests.

## Required environment variables

```dotenv
MATTERMOST_URL=http://mattermost-hermes:8065
MATTERMOST_TOKEN=YOUR_MATTERMOST_BOT_TOKEN
```

For an HTTPS deployment, the URL can instead be:

```dotenv
MATTERMOST_URL=https://mattermost.example.com
```

> [!IMPORTANT]
> The plugin checks `MATTERMOST_URL` and `MATTERMOST_TOKEN` directly through `os.environ`. Storing the variables only in a Hermes profile file such as `/opt/data/.env` may not make them available to the plugin process. In Docker Swarm, pass them through the Hermes service `environment` section.

Example Docker Swarm configuration:

```yaml
services:
  hermes:
    environment:
      MATTERMOST_URL: "${MATTERMOST_URL:-http://mattermost-hermes:8065}"
      MATTERMOST_TOKEN: "${MATTERMOST_TOKEN:?MATTERMOST_TOKEN must be set}"
```

If Hermes and Mattermost use a dedicated overlay network, both services must join the same network. Example Mattermost alias:

```yaml
services:
  mattermost:
    networks:
      hermes-messaging:
        aliases:
          - mattermost-hermes

networks:
  hermes-messaging:
    external: true
```

Example Hermes network attachment:

```yaml
services:
  hermes:
    networks:
      - hermes-messaging

networks:
  hermes-messaging:
    external: true
```

## Installation

### Option 1: Clone into the Hermes plugin directory

For the `ngslabex` repository:

```bash
git clone \
  https://github.com/ngslabex/hermes-mattermost-tools.git \
  ~/.hermes/plugins/mattermost-tools
```

In the official Hermes container layout used by the SCADA deployment:

```bash
git clone \
  https://github.com/ngslabex/hermes-mattermost-tools.git \
  /opt/data/plugins/mattermost-tools
```

### Option 2: Link a local checkout

```bash
ln -s \
  /path/to/hermes-mattermost-tools \
  ~/.hermes/plugins/mattermost-tools
```

## Enable the plugin

Hermes plugins are opt-in. Check the current plugin configuration before changing it:

```bash
hermes config show | grep -A10 -B2 'plugins:'
```

Enable only this plugin:

```bash
hermes config set \
  plugins.enabled \
  '["mattermost-tools"]'
```

If other plugins are already enabled, preserve them in the same array:

```bash
hermes config set \
  plugins.enabled \
  '["my-other-plugin","mattermost-tools"]'
```

> [!WARNING]
> `hermes config set plugins.enabled` replaces the complete enabled-plugin list. It does not append to the existing list.

Restart Hermes after installing, updating, or enabling the plugin. For Docker Swarm:

```bash
docker service update --force hermes_hermes
```

## Verify the installation

List the registered Mattermost tools:

```bash
hermes tools list | grep -Ei \
  'mm_send|mm_read|mm_list_channels|mm_list_users|mm_open_dm|mattermost'
```

Expected tools:

```text
mm_send
mm_read
mm_list_channels
mm_list_users
mm_open_dm
```

Validate the required process environment without displaying the token:

```bash
for variable in MATTERMOST_URL MATTERMOST_TOKEN
do
  eval "value=\${$variable:-}"

  if [ -n "$value" ]; then
    echo "$variable=defined"
  else
    echo "$variable=MISSING"
  fi
done
```

Test Mattermost connectivity:

```bash
curl -sS \
  "$MATTERMOST_URL/api/v4/system/ping"
```

Test token authentication:

```bash
curl -sS \
  -H "Authorization: Bearer $MATTERMOST_TOKEN" \
  "$MATTERMOST_URL/api/v4/users/me"
```

## Usage examples

Once installed, Hermes can select these tools automatically. A user can also name a tool explicitly.

### Send a channel message

```text
Use mm_send to post "The build finished successfully" to #operations.
```

### Read recent channel messages

```text
Use mm_read to read the last 10 messages in #general and summarize them.
```

### Summarize Zabbix alarm cards

```text
Use mm_read to read the last 10 posts in scada-alerts. Include the title, text,
fallback, and fields from Zabbix alarm cards, then summarize device, IP address,
severity, event time, and description.
```

### List channels

```text
Use mm_list_channels to list joined channels containing "scada".
```

### List users

```text
Use mm_list_users to find users whose name contains "alice".
```

### Open a direct message

```text
Use mm_open_dm to open a DM with @alice and tell the user that the report is ready.
```

## Zabbix and attachment-only webhook posts

Mattermost can store a webhook-generated alarm as an attachment-only post:

```json
{
  "type": "slack_attachment",
  "message": "",
  "props": {
    "attachments": [
      {
        "title": "Problem: Device is unavailable by ICMP",
        "fields": [
          {
            "title": "Host",
            "value": "CBS001-RTR-01 [10.251.1.11]"
          },
          {
            "title": "Severity",
            "value": "High"
          }
        ]
      }
    ]
  }
}
```

The Mattermost client renders this post as a visible card even though `message` is empty. The current `mm_read` implementation extracts the attachment title and fields so the output includes readable alarm details instead of an empty post.

## Troubleshooting

### Tools appear, but calls report unavailable or return no channel data

Check that the variables are in the Hermes process environment:

```bash
tr '\0' '\n' < /proc/1/environ |
grep -E '^MATTERMOST_(URL|TOKEN)=' |
sed 's/=.*/=<hidden>/'
```

If the variables exist only in `/opt/data/.env`, add them to the Hermes Docker service `environment` section and redeploy the stack.

### Mattermost authentication fails

Check the current bot identity:

```bash
curl -sS \
  -H "Authorization: Bearer $MATTERMOST_TOKEN" \
  "$MATTERMOST_URL/api/v4/users/me"
```

Confirm that the token belongs to the expected bot and has not been regenerated or revoked.

### Channel cannot be read

- Ensure the bot belongs to the Mattermost team.
- Ensure the bot belongs to the private channel.
- Verify the channel name or use the 26-character channel ID.
- Test `mm_list_channels` with `scope=joined`.

### Alarm cards appear as empty posts

Confirm that the installed `tools.py` contains attachment support:

```bash
grep -n \
  'attachment-only webhook posts' \
  /opt/data/plugins/mattermost-tools/tools.py
```

Validate Python syntax:

```bash
python -m py_compile \
  /opt/data/plugins/mattermost-tools/tools.py
```

If the marker is missing, install version `0.2.0` or later. A plugin reinstall or update may replace locally patched files, so use a tagged repository version rather than an untracked container-side edit.

### Dedicated Mattermost alias does not resolve

Test from the Hermes container:

```bash
curl -sS \
  --connect-timeout 5 \
  http://mattermost-hermes:8065/api/v4/system/ping
```

Ensure Hermes and Mattermost both join the external `hermes-messaging` overlay network and Mattermost has the `mattermost-hermes` alias.

## Updating

Update the plugin from Git:

```bash
cd /opt/data/plugins/mattermost-tools

git fetch --tags origin
git checkout v0.2.0
python -m py_compile tools.py
```

Restart Hermes:

```bash
docker service update --force hermes_hermes
```

Verify the plugin manifest version:

```bash
grep -E '^(name|version):' \
  /opt/data/plugins/mattermost-tools/plugin.yaml
```

Expected:

```text
name: mattermost-tools
version: 0.2.0
```

## Design notes

Hermes includes messaging engines used by gateways, cron jobs, and the CLI. Those capabilities are not necessarily exposed to the model as callable tools. This plugin is an explicit opt-in that exposes Mattermost operations to the agent.

The plugin:

- Uses the Mattermost v4 REST API
- Uses Python standard-library `urllib`
- Performs synchronous requests suitable for standard Hermes tool handlers
- Uses the existing Mattermost URL and token
- Does not require an additional service account
- Reads webhook and bot posts without filtering them by sender type
- Converts attachment-only alarm cards into readable text

## Security considerations

- Keep `MATTERMOST_TOKEN` out of Git.
- Store deployment secrets in a protected `.env`, Docker secret, or enterprise password vault.
- Restrict `.env` permissions:

```bash
chmod 600 .env
```

- Use a dedicated Mattermost bot account with the minimum required channel membership.
- Do not add the bot to channels it does not need to read.
- Rotate the token if it appears in logs, shell history, screenshots, or commits.
- Treat proactive messaging tools as privileged capabilities.

## Repository structure

```text
hermes-mattermost-tools/
├── plugin.yaml      # Plugin manifest, version, tools, and required environment variables
├── __init__.py      # Plugin entry point; register(ctx) is called by Hermes
├── tools.py         # Tool schemas, message formatting, and handlers
├── client.py        # Thin synchronous Mattermost REST API client
├── AGENTS.md        # Guidance for AI coding assistants working on the repository
└── README.md        # Installation, usage, troubleshooting, and design documentation
```

## Release notes

### 0.2.0

- Added attachment-only webhook post support to `mm_read`
- Added extraction of attachment `pretext`, `title`, `text`, `fallback`, and `fields`
- Added `image_url` and `title_link` extraction
- Added Mattermost block text extraction
- Added duplicate-text suppression
- Added safer timestamp and argument handling
- Documented Docker Swarm environment requirements
- Documented Zabbix alarm-card behavior and troubleshooting

### 0.1.0

- Initial release
- Added channel and DM messaging
- Added channel history reading
- Added channel and user listing
- Added direct-message creation

## License

MIT
