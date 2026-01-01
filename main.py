import os
import sys
import json
import asyncio
import platform
import re
import requests
import websockets
from colorama import init, Fore

init(autoreset=True)

def get_user_info(token):
    # Try as user token first
    headers = {"Authorization": token, "Content-Type": "application/json"}
    r = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
    if r.status_code == 401:
        # Fallback: try as bot token (HTTP requires 'Bot ' prefix)
        headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        r = requests.get("https://canary.discordapp.com/api/v9/users/@me", headers=headers)
    if r.status_code != 200:
        try:
            msg = r.json().get("message")
        except Exception:
            msg = r.text
        print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Token rejected ({r.status_code}): {msg}")
        return None
    data = r.json()
    return {
        "token": token,
        "username": data.get("username"),
        "userid": data.get("id"),
    }

async def onliner(token):
    backoff = 1
    max_backoff = 60
    while True:
        try:
            async with websockets.connect(
                "wss://gateway.discord.gg/?v=9&encoding=json",
                max_size=None,
            ) as ws:
                hello = json.loads(await ws.recv())
                interval = hello["d"]["heartbeat_interval"] / 1000

                auth = {
                    "op": 2,
                    "d": {
                        "token": token,
                        "properties": {
                            "$os": "Windows 10",
                            "$browser": "Google Chrome",
                            "$device": "Windows",
                        },
                    },
                }
                await ws.send(json.dumps(auth))

                # No custom status or activities; keep account online only

                seq = None
                loop = asyncio.get_event_loop()
                next_heartbeat = loop.time() + interval
                while True:
                    timeout = max(0, next_heartbeat - loop.time())
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        evt = json.loads(msg)
                        if "s" in evt:
                            seq = evt["s"]
                        if evt.get("op") == 11:
                            pass
                    except asyncio.TimeoutError:
                        hb = {"op": 1, "d": seq}
                        await ws.send(json.dumps(hb))
                        next_heartbeat += interval
        except Exception as e:
            print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Connection error: {e}. Retrying...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

async def run_account(account):
    await onliner(account["token"])

async def run_onliner():
    tokens_env = os.getenv("TOKENS", "").strip()
    tokens = [t.strip() for t in re.split(r"[\s,;]+", tokens_env) if t and t.strip()]
    if not tokens:
        single = os.getenv("TOKEN")
        if single:
            tokens = [single]

    # Enforce a maximum of 5 accounts
    if len(tokens) > 5:
        print(f"{Fore.WHITE}[{Fore.YELLOW}!{Fore.WHITE}] More than 5 tokens provided; using the first 5.")
        tokens = tokens[:5]

    if not tokens:
        print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] No token found. Set TOKEN or TOKENS (max 5).")
        sys.exit()

    accounts = []
    print(f"{Fore.WHITE}[{Fore.LIGHTBLUE_EX}i{Fore.WHITE}] Tokens provided: {len(tokens)}")
    for t in tokens:
        info = get_user_info(t)
        if not info:
            print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Invalid token skipped.")
            continue
        accounts.append(info)

    if not accounts:
        print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] No valid tokens. Exiting.")
        sys.exit()

    if platform.system() == "Windows":
        os.system("cls")
    else:
        os.system("clear")

    for a in accounts:
        print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{a['username']} {Fore.WHITE}({a['userid']})!")

    tasks = [asyncio.create_task(run_account(a)) for a in accounts]
    await asyncio.gather(*tasks)

asyncio.run(run_onliner())
