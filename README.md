# Discord Always-Online Idler

Keeps up to 5 Discord accounts appearing online by maintaining a heartbeat to the Discord Gateway.

Use responsibly. Automating user accounts may violate Discord's Terms of Service. This project is for educational purposes only.

## Requirements

- Python 3.9+ (tested on Windows)
- `pip` to install dependencies

## Install

```powershell
pip install -r requirements.txt
```

## Configure Tokens (max 5)

Set either a single token in `TOKEN` or multiple tokens in `TOKENS` (space/comma/semicolon separated). The script will use at most the first 5 tokens.

Examples (PowerShell):

```powershell
# Single account
$env:TOKEN = "discord_token_here"

# Multiple accounts (up to 5)
$env:TOKENS = "token1 token2 token3 token4 token5"
# Commas or semicolons also work
$env:TOKENS = "token1,token2,token3"; $env:TOKENS = "token1; token2; token3"
```

Notes:

- Environment variables set like above are scoped to the current PowerShell session.
- Keep your tokens secret. Do not commit or share them.

## Run

```powershell
python main.py
```

You should see a login confirmation for each valid token, then the process will keep all listed accounts online.

## Run with PM2 (optional)

- PM2 keeps the script running and restarts it on failure.
- On Windows, ensure Node.js is installed.

### Setup

```powershell
# Install PM2 globally
npm install -g pm2
```

### Start

```powershell
pm2 start ecosystem.config.js
```

### Manage

```powershell
pm2 status
pm2 logs online-forever --lines 100
pm2 restart online-forever
pm2 stop online-forever
```

Notes:

- `ecosystem.config.js` defines up to 5 tokens; extras are ignored by the app.
- It defaults to the `python` interpreter; override via `PYTHON_INTERPRETER`.
- PM2 logs go to `pm2-out.log` and `pm2-error.log`.

## Behavior

- The script attempts to validate tokens via the Discord REST API (user first, then bot format).
- On success, it opens a persistent WebSocket connection to the Discord Gateway and sends heartbeat messages to keep the session online.
- If more than 5 tokens are provided, the script will inform you and only use the first 5.

## Troubleshooting

- "No token found": Ensure `TOKEN` or `TOKENS` is set in your shell before running.
- "Token rejected": The token may be invalid or revoked.
- Network errors: The script backs off and retries automatically.

## Uninstall

```powershell
pip uninstall -r requirements.txt -y
```
