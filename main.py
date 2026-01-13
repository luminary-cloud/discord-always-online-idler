import os
import sys
import json
import asyncio
import platform
import re
import random
import requests
import websockets
from datetime import datetime
from zoneinfo import ZoneInfo
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

def is_sleep_time(timezone, sleep_hour, wake_hour):
    """Check if current time in timezone is between sleep and wake hours."""
    now = datetime.now(ZoneInfo(timezone))
    current_hour = now.hour
    
    # Handle sleep time that crosses midnight
    if sleep_hour > wake_hour:
        # e.g., sleep at 23:00, wake at 7:00
        return current_hour >= sleep_hour or current_hour < wake_hour
    else:
        # e.g., sleep at 1:00, wake at 8:00
        return sleep_hour <= current_hour < wake_hour

async def onliner(token, username, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10):
    backoff = 1
    max_backoff = 60
    current_sleep_hour = None
    current_wake_hour = None
    schedule_date = None
    
    while True:
        try:
            # Generate new sleep/wake times daily
            if human_schedule:
                now = datetime.now(ZoneInfo(timezone))
                today = now.date()
                
                # Generate new times if it's a new day or first run
                if schedule_date != today:
                    # Random sleep time with variation
                    if sleep_start > sleep_end:
                        # Crosses midnight
                        current_sleep_hour = random.choice(list(range(sleep_start, 24)) + list(range(0, sleep_end + 1)))
                    else:
                        current_sleep_hour = random.randint(sleep_start, sleep_end)
                    
                    # Random wake time
                    current_wake_hour = random.randint(wake_start, wake_end)
                    
                    # Add minute variation (0-59 minutes) for more realism
                    sleep_minute_offset = random.randint(0, 59)
                    wake_minute_offset = random.randint(0, 59)
                    
                    schedule_date = today
                    print(f"{Fore.WHITE}[{Fore.CYAN}📅{Fore.WHITE}] {username} new schedule: Sleep {current_sleep_hour:02d}:{sleep_minute_offset:02d}, Wake {current_wake_hour:02d}:{wake_minute_offset:02d}")
            
            # Check if it's sleep time before connecting
            if human_schedule and is_sleep_time(timezone, current_sleep_hour, current_wake_hour):
                now = datetime.now(ZoneInfo(timezone))
                print(f"{Fore.WHITE}[{Fore.YELLOW}💤{Fore.WHITE}] {username} is sleeping (offline until ~{current_wake_hour:02d}:00 {timezone})")
                # Sleep for 5 minutes then check again
                await asyncio.sleep(300)
                backoff = 1  # Reset backoff during sleep
                continue
            
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
                last_sleep_check = loop.time()
                
                while True:
                    # Check every 5 minutes if it's time to sleep
                    if human_schedule and (loop.time() - last_sleep_check) >= 300:
                        if is_sleep_time(timezone, current_sleep_hour, current_wake_hour):
                            now = datetime.now(ZoneInfo(timezone))
                            print(f"{Fore.WHITE}[{Fore.YELLOW}💤{Fore.WHITE}] {username} going to sleep at {now.strftime('%H:%M')}")
                            await ws.close()
                            break  # Exit to disconnect and sleep
                        last_sleep_check = loop.time()
                    
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

async def run_account(account, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10):
    await onliner(account["token"], account["username"], human_schedule, timezone, sleep_start, sleep_end, wake_start, wake_end)

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

    # Read human schedule mode settings
    human_schedule = os.getenv("HUMAN_SCHEDULE_MODE", "false").lower() in ["true", "1", "yes"]
    timezone = os.getenv("TIMEZONE", "Europe/Amsterdam")
    sleep_start = int(os.getenv("SLEEP_TIME_START", "22"))
    sleep_end = int(os.getenv("SLEEP_TIME_END", "2"))
    wake_start = int(os.getenv("WAKE_TIME_START", "6"))
    wake_end = int(os.getenv("WAKE_TIME_END", "10"))

    accounts = []
    print(f"{Fore.WHITE}[{Fore.LIGHTBLUE_EX}i{Fore.WHITE}] Tokens provided: {len(tokens)}")
    if human_schedule:
        print(f"{Fore.WHITE}[{Fore.LIGHTBLUE_EX}i{Fore.WHITE}] Human schedule mode enabled ({timezone})")
        print(f"{Fore.WHITE}[{Fore.LIGHTBLUE_EX}i{Fore.WHITE}] Sleep: {sleep_start:02d}:00-{sleep_end:02d}:00 | Wake: {wake_start:02d}:00-{wake_end:02d}:00")
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
        schedule_info = ""
        if human_schedule:
            schedule_info = f" {Fore.WHITE}[Daily schedule: Sleep {sleep_start}-{sleep_end}, Wake {wake_start}-{wake_end}]"
        print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{a['username']} {Fore.WHITE}({a['userid']}){schedule_info}")

    tasks = [
        asyncio.create_task(
            run_account(
                a, 
                human_schedule, 
                timezone, 
                sleep_start,
                sleep_end,
                wake_start,
                wake_end
            )
        ) 
        for a in accounts
    ]
    await asyncio.gather(*tasks)

asyncio.run(run_onliner())
