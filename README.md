# Discord Always-Online Idler

Keeps up to 5 Discord accounts appearing online by maintaining a heartbeat to the Discord Gateway.

Use responsibly. Automating user accounts may violate Discord's Terms of Service. This project is for educational purposes only.

## Requirements

- Python 3.9+ (tested on Linux)
- `pip` to install dependencies

## Install

### 1. Create a virtual environment (recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (Linux/Mac)
source venv/bin/activate

# On Windows PowerShell:
.\venv\Scripts\Activate.ps1
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

When the venv is activated, you'll see `(venv)` at the start of your terminal prompt.

**Note:** On newer Debian/Ubuntu systems, virtual environments are required to avoid `externally-managed-environment` errors.

## Configure

Edit `ecosystem.config.js` to set your tokens (max 5) and other settings.

```javascript
env: {
  TOKENS: 'token1, token2, token3',

  // Human-like sleep schedule
  HUMAN_SCHEDULE_MODE: 'true',
  TIMEZONE: 'Europe/Amsterdam',
  SLEEP_TIME_START: '22',
  SLEEP_TIME_END: '3',
  WAKE_TIME_START: '6',
  WAKE_TIME_END: '10',

  // Game activity (fake game playing)
  GAME_ACCOUNTS: '', // User IDs or usernames (comma-separated)
  GAME_NAME: 'GAME NAME',
  GAME_IMAGE: 'https://cdn.discordapp.com/app-icons/...',
  MIN_PLAY_HOURS: '2',
  MAX_PLAY_HOURS: '5',
}
```

**Important:** If using a virtual environment, update the interpreter:

```javascript
interpreter: './venv/bin/python3',  // Linux/Mac
// or
interpreter: './venv/Scripts/python.exe',  // Windows
```

Notes:

- Keep your tokens secret. Do not commit or share them.
- The script will use at most the first 5 tokens.

## Run with PM2

PM2 keeps the script running 24/7 and restarts it on failure. Requires Node.js.

### Setup

```bash
# Install PM2 globally
npm install -g pm2

# Make PM2 start on system boot (Linux)
pm2 startup
# Follow the command it gives you (run with sudo)

# Save PM2 process list to auto-start after reboot
pm2 save
```

### Start

```bash
pm2 start ecosystem.config.js
```

**If you get a "Process X not found" error:**

```bash
# Delete the old process and start fresh
pm2 delete discord-always-online-idler
pm2 start ecosystem.config.js
```

### Manage

```bash
pm2 status
pm2 logs discord-always-online-idler --lines 100
pm2 restart discord-always-online-idler
pm2 stop discord-always-online-idler
```

**Notes:**

- PM2 will automatically restart the script if it crashes (max 10 restarts).
- After running `pm2 startup` and `pm2 save`, the script will auto-start on server reboot.
- PM2 logs go to `pm2-out.log` and `pm2-error.log`.

## Features

### Human-like Sleep Schedule

- Accounts go offline during sleep hours with randomized times
- Configurable timezone and sleep/wake time ranges
- Adds realistic variation (minutes offset) daily

### Fake Game Activity

- Show "Playing Counter-Strike 2" (or any game)
- Clickable game with custom icon
- Random play duration (2-5 hours default)
- Select specific accounts to display game activity

## Behavior

- The script attempts to validate tokens via the Discord REST API (user first, then bot format).
- On success, it opens a persistent WebSocket connection to the Discord Gateway and sends heartbeat messages to keep the session online.
- If more than 5 tokens are provided, the script will inform you and only use the first 5.

## Troubleshooting

- **"No token found"**: Ensure tokens are set in `ecosystem.config.js`.
- **"Token rejected"**: The token may be invalid or revoked.
- **"Process X not found" error**: Run `pm2 delete discord-always-online-idler` then start again.
- **Network errors**: The script backs off and retries automatically.
- **Game not showing**: Verify `GAME_ACCOUNTS` has correct user IDs and `GAME_IMAGE` URL is valid.

## Uninstall

```bash
# Stop PM2 process
pm2 stop discord-always-online-idler
pm2 delete discord-always-online-idler
pm2 save

# Remove dependencies
pip uninstall -r requirements.txt -y
```
