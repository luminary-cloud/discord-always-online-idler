# discord-always-online-idler

Keeps up to 5 Discord accounts appearing online by maintaining a WebSocket heartbeat to the Discord gateway. Python 3.9+, no Discord library required.

Automating user accounts violates Discord's Terms of Service. Use at your own risk.

## What it does

- Validates tokens via the Discord REST API (tries user token first, falls back to bot format)
- Opens a persistent WebSocket connection to the Discord gateway and sends heartbeats to maintain online status
- Supports gateway RESUME on reconnect, with exponential backoff on failure
- Optional human-like sleep schedule with randomized daily times within configurable windows
- Optional fake game activity with scheduled session windows, random durations, and clickable game icons
- Runs up to 5 accounts concurrently via asyncio

## Requirements

- Python 3.9+
- pip
- Node.js (for PM2, optional but recommended for 24/7 operation)

## Install

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

On Windows PowerShell, activate with `.\venv\Scripts\Activate.ps1` instead.

On newer Debian/Ubuntu, virtual environments are required to avoid `externally-managed-environment` errors.

## Configure

Edit `ecosystem.config.js`. All settings live in the `env` block.

**Tokens.** Comma-separated, max 5. Keep them secret, do not commit them.

```javascript
TOKENS: 'token1, token2, token3',
```

**Sleep schedule.** Each account picks a random sleep and wake time within these hour ranges daily, with per-minute variation.

```javascript
HUMAN_SCHEDULE_MODE: 'true',
TIMEZONE: 'Europe/Amsterdam',
SLEEP_TIME_START: '21',   // earliest sleep hour
SLEEP_TIME_END: '2',      // latest sleep hour
WAKE_TIME_START: '6',     // earliest wake hour
WAKE_TIME_END: '10',      // latest wake hour
```

**Game activity.** Each configured window has a 70% chance of spawning a session. Duration and start time are randomized within the window.

```javascript
GAME_ACCOUNTS: 'user1,123456789',   // usernames or user IDs
GAME_NAME: 'Counter-Strike 2',
GAME_IMAGE: 'https://cdn.discordapp.com/app-icons/...',
GAME_SESSIONS: '10-15,18-23',       // hour windows
MIN_PLAY_HOURS: '2',
MAX_PLAY_HOURS: '5',
```

**Interpreter.** If using a virtual environment, update the interpreter path to match your OS.

```javascript
interpreter: './venv/bin/python3',        // Linux/Mac
// interpreter: './venv/Scripts/python.exe',  // Windows
```

## Run with PM2

PM2 keeps the script running and restarts it on failure. Requires Node.js.

```bash
npm install -g pm2
pm2 start ecosystem.config.js
```

Auto-start on boot (Linux):

```bash
pm2 startup
# run the command it prints, then:
pm2 save
```

Management:

```bash
pm2 status
pm2 logs discord-always-online-idler --lines 100
pm2 restart discord-always-online-idler
pm2 stop discord-always-online-idler
```

If PM2 reports "Process not found", delete the old entry first:

```bash
pm2 delete discord-always-online-idler
pm2 start ecosystem.config.js
```

## Troubleshooting

- **No token found**: set `TOKENS` in `ecosystem.config.js`.
- **Token rejected**: token is invalid or revoked.
- **Game not showing**: check that `GAME_ACCOUNTS` has the correct usernames or user IDs and that `GAME_IMAGE` is a valid Discord CDN URL with an app icon path.
- **Network errors**: the script retries with exponential backoff automatically.

## Uninstall

```bash
pm2 stop discord-always-online-idler
pm2 delete discord-always-online-idler
pm2 save
pip uninstall -r requirements.txt -y
```

## License

[MIT](LICENSE).
