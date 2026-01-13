import os
import sys
import json
import asyncio
import platform
import re
import random
import requests
import websockets
import time
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

async def onliner(token, username, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10, play_game=False, game_name='Counter-Strike 2', game_image='', min_play_hours=2, max_play_hours=5):
    backoff = 1
    max_backoff = 60
    current_sleep_hour = None
    current_wake_hour = None
    schedule_date = None
    game_session_end = None
    is_playing = False
    
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
            
            # Start new game session if enabled and not currently playing
            if play_game and game_session_end is None:
                # Random play duration between min and max hours
                play_duration = random.uniform(min_play_hours * 3600, max_play_hours * 3600)
                game_session_end = asyncio.get_event_loop().time() + play_duration
                is_playing = True
                hours = play_duration / 3600
                print(f"{Fore.WHITE}[{Fore.GREEN}🎮{Fore.WHITE}] {username} starting {game_name} session (~{hours:.1f} hours)")
            
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

                # Wait for READY event before sending presence
                await asyncio.sleep(2)

                # Send presence update with game activity if playing
                if play_game and is_playing:
                    activity = {
                        "name": game_name,
                        "type": 0,  # 0 = Playing
                    }
                    
                    # Add timestamp for elapsed time
                    activity["timestamps"] = {
                        "start": int(time.time() * 1000)
                    }
                    
                    # Extract and add application ID from image URL for clickable game
                    if game_image:
                        app_id_match = re.search(r'app-icons/(\d+)/', game_image)
                        if app_id_match:
                            activity["application_id"] = app_id_match.group(1)
                    
                    presence = {
                        "op": 3,
                        "d": {
                            "status": "online",
                            "activities": [activity],
                            "since": None,
                            "afk": False
                        }
                    }
                    await ws.send(json.dumps(presence))

                seq = None
                loop = asyncio.get_event_loop()
                next_heartbeat = loop.time() + interval
                last_sleep_check = loop.time()
                
                while True:
                    # Check if game session should end
                    if play_game and is_playing and game_session_end and loop.time() >= game_session_end:
                        is_playing = False
                        game_session_end = None
                        print(f"{Fore.WHITE}[{Fore.YELLOW}🛑{Fore.WHITE}] {username} stopped playing {game_name}")
                        # Send presence update to clear game activity
                        presence = {
                            "op": 3,
                            "d": {
                                "status": "online",
                                "activities": [],
                                "since": None,
                                "afk": False
                            }
                        }
                        await ws.send(json.dumps(presence))
                    
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

async def run_account(account, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10, play_game=False, game_name='Counter-Strike 2', game_image='', min_play_hours=2, max_play_hours=5):
    await onliner(account["token"], account["username"], human_schedule, timezone, sleep_start, sleep_end, wake_start, wake_end, play_game, game_name, game_image, min_play_hours, max_play_hours)

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
    
    # Read game activity settings
    game_name = os.getenv("GAME_NAME", "Counter-Strike 2")
    game_image = os.getenv("GAME_IMAGE", "")  # URL to game icon/image
    min_play_hours = float(os.getenv("MIN_PLAY_HOURS", "2"))
    max_play_hours = float(os.getenv("MAX_PLAY_HOURS", "5"))
    # Comma-separated list of account usernames or user IDs that should play the game
    game_accounts_str = os.getenv("GAME_ACCOUNTS", "")
    game_accounts = [a.strip() for a in game_accounts_str.split(",") if a.strip()] if game_accounts_str else []

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
        
        # Check if this account should play the game
        play_game = False
        if game_accounts:
            play_game = a['username'] in game_accounts or a['userid'] in game_accounts
        
        game_info = ""
        if play_game:
            game_info = f" {Fore.GREEN}[Playing: {game_name}]"
        
        print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{a['username']} {Fore.WHITE}({a['userid']}){schedule_info}{game_info}")
        
        # Store play_game in account dict for task creation
        a['play_game'] = play_game

    tasks = [
        asyncio.create_task(
            run_account(
                a, 
                human_schedule, 
                timezone, 
                sleep_start,
                sleep_end,
                wake_start,
                wake_end,
                a.get('play_game', False),
                game_name,
                game_image,
                min_play_hours,
                max_play_hours
            )
        ) 
        for a in accounts
    ]
    await asyncio.gather(*tasks)

asyncio.run(run_onliner())
