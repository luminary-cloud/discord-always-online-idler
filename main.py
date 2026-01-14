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

def is_sleep_time(timezone, sleep_hour, sleep_minute, wake_hour, wake_minute):
    """Check if current time in timezone is between sleep and wake times (including minutes)."""
    now = datetime.now(ZoneInfo(timezone))
    current_minutes = now.hour * 60 + now.minute
    sleep_minutes = sleep_hour * 60 + sleep_minute
    wake_minutes = wake_hour * 60 + wake_minute
    
    # Handle sleep time that crosses midnight
    if sleep_minutes > wake_minutes:
        # e.g., sleep at 23:30, wake at 7:15
        return current_minutes >= sleep_minutes or current_minutes < wake_minutes
    else:
        # e.g., sleep at 1:00, wake at 8:30
        return sleep_minutes <= current_minutes < wake_minutes

async def onliner(token, username, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10, play_game=False, game_name='Counter-Strike 2', game_image='', min_play_hours=2, max_play_hours=5, game_sessions='11-14,20-23'):
    backoff = 1
    max_backoff = 60
    sleep_logged = False  # Track if we've logged the sleep message
    current_sleep_hour = None
    current_wake_hour = None
    current_sleep_minute = None
    current_wake_minute = None
    schedule_date = None
    game_session_end = None
    is_playing = False
    game_start_delay = None  # Delay before starting game after wake/connect
    daily_game_times = []  # Scheduled game times for today [(start_time, duration), ...]
    game_times_generated = None  # Date when game times were generated
    
    # Parse game session windows (e.g., "11-14,20-23")
    game_session_windows = []
    if play_game and game_sessions:
        for session in game_sessions.split(','):
            if '-' in session:
                try:
                    start, end = session.strip().split('-')
                    game_session_windows.append((int(start), int(end)))
                except ValueError:
                    pass
    
    # Generate initial schedule outside the connection loop
    if human_schedule:
        now = datetime.now(ZoneInfo(timezone))
        today = now.date()
        
        # Random sleep time with variation
        if sleep_start > sleep_end:
            # Crosses midnight
            current_sleep_hour = random.choice(list(range(sleep_start, 24)) + list(range(0, sleep_end + 1)))
        else:
            current_sleep_hour = random.randint(sleep_start, sleep_end)
        
        # Random wake time
        current_wake_hour = random.randint(wake_start, wake_end)
        
        # Add minute variation (0-59 minutes) but keep within configured range
        # If we're at the end hour, set minute to 0 to not exceed the range
        if current_sleep_hour == sleep_end:
            current_sleep_minute = 0
        else:
            current_sleep_minute = random.randint(0, 59)
        
        if current_wake_hour == wake_end:
            current_wake_minute = 0
        else:
            current_wake_minute = random.randint(0, 59)
        
        schedule_date = today
        print(f"{Fore.WHITE}[{Fore.CYAN}📅{Fore.WHITE}] {username} schedule: Sleep {current_sleep_hour:02d}:{current_sleep_minute:02d}, Wake {current_wake_hour:02d}:{current_wake_minute:02d}")
    
    while True:
        try:
            # Check if we need to generate a new schedule for a new day
            if human_schedule:
                now = datetime.now(ZoneInfo(timezone))
                today = now.date()
                
                # Generate new times if it's a new day
                if schedule_date != today:
                    # Random sleep time with variation
                    if sleep_start > sleep_end:
                        # Crosses midnight
                        current_sleep_hour = random.choice(list(range(sleep_start, 24)) + list(range(0, sleep_end + 1)))
                    else:
                        current_sleep_hour = random.randint(sleep_start, sleep_end)
                    
                    # Random wake time
                    current_wake_hour = random.randint(wake_start, wake_end)
                    
                    # Add minute variation (0-59 minutes) but keep within configured range
                    # If we're at the end hour, set minute to 0 to not exceed the range
                    if current_sleep_hour == sleep_end:
                        current_sleep_minute = 0
                    else:
                        current_sleep_minute = random.randint(0, 59)
                    
                    if current_wake_hour == wake_end:
                        current_wake_minute = 0
                    else:
                        current_wake_minute = random.randint(0, 59)
                    
                    schedule_date = today
                    print(f"{Fore.WHITE}[{Fore.CYAN}📅{Fore.WHITE}] {username} new schedule: Sleep {current_sleep_hour:02d}:{current_sleep_minute:02d}, Wake {current_wake_hour:02d}:{current_wake_minute:02d}")
            
            # Generate random game times for today if needed
            if play_game and game_session_windows:
                now = datetime.now(ZoneInfo(timezone))
                today = now.date()
                
                if game_times_generated != today:
                    daily_game_times = []
                    # For each session window, randomly decide if we play (70% chance)
                    for window_start, window_end in game_session_windows:
                        if random.random() < 0.7:  # 70% chance to play in this window
                            # Check if window is large enough for minimum play time
                            window_duration = window_end - window_start
                            if window_duration < min_play_hours:
                                continue  # Skip this window, too small
                            
                            # Calculate maximum session duration that fits in window
                            max_possible_duration = min(max_play_hours, window_duration)
                            
                            # Random session duration
                            duration = random.uniform(min_play_hours, max_possible_duration)
                            
                            # Random start time within window (ensure session fits)
                            latest_start = window_end - duration
                            start_offset_hours = random.uniform(0, latest_start - window_start)
                            start_hour = window_start + start_offset_hours
                            
                            daily_game_times.append((start_hour, duration))
                    
                    game_times_generated = today
                    if daily_game_times:
                        sessions_str = ", ".join([f"{int(s[0]):02d}:{int((s[0] % 1) * 60):02d} ({s[1]:.1f}h)" for s in daily_game_times])
                        print(f"{Fore.WHITE}[{Fore.CYAN}🎮{Fore.WHITE}] {username} game sessions today: {sessions_str}")
            
            # Check if it's sleep time before connecting
            if human_schedule and is_sleep_time(timezone, current_sleep_hour, current_sleep_minute, current_wake_hour, current_wake_minute):
                # Only log once when entering sleep, not every 5 minutes
                if not sleep_logged:
                    now = datetime.now(ZoneInfo(timezone))
                    print(f"{Fore.WHITE}[{Fore.YELLOW}💤{Fore.WHITE}] {username} is sleeping (offline until ~{current_wake_hour:02d}:00 {timezone})")
                    sleep_logged = True
                # Sleep for 5 minutes then check again
                await asyncio.sleep(300)
                continue
            elif sleep_logged:  # Was sleeping, now awake
                now = datetime.now(ZoneInfo(timezone))
                print(f"{Fore.WHITE}[{Fore.GREEN}☀️{Fore.WHITE}] {username} waking up at {now.strftime('%H:%M')}")
                sleep_logged = False
                backoff = 1  # Reset backoff on successful wake
            
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
                last_game_check = loop.time()
                
                while True:
                    # Check if we should start a game session based on scheduled times (every 60 seconds)
                    if play_game and daily_game_times and not is_playing and game_session_end is None and (loop.time() - last_game_check) >= 60:
                        now = datetime.now(ZoneInfo(timezone))
                        current_time = now.hour + now.minute / 60.0
                        
                        # Check if it's time for any scheduled session
                        for session_start, session_duration in daily_game_times:
                            time_until_start = (session_start - current_time) * 3600  # Convert to seconds
                            
                            # If we're within 5 minutes of start time or past it (but not too late)
                            if -300 <= time_until_start <= 300:  # Within 5 min window
                                play_duration = session_duration * 3600
                                game_session_end = loop.time() + play_duration
                                game_start_delay = loop.time() + random.randint(60, 300)  # 1-5 min delay
                                print(f"{Fore.WHITE}[{Fore.CYAN}⏰{Fore.WHITE}] {username} preparing to start {game_name} (~{session_duration:.1f}h session)")
                                break
                        last_game_check = loop.time()
                    
                    # Check if it's time to start playing after delay
                    if play_game and not is_playing and game_start_delay and loop.time() >= game_start_delay:
                        is_playing = True
                        game_start_delay = None
                        hours = (game_session_end - loop.time()) / 3600
                        print(f"{Fore.WHITE}[{Fore.GREEN}🎮{Fore.WHITE}] {username} starting {game_name} (~{hours:.1f}h session)")
                        # Send presence update with game activity
                        activity = {
                            "name": game_name,
                            "type": 0,
                            "timestamps": {"start": int(time.time() * 1000)}
                        }
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
                    
                    # Check if game session should end
                    if play_game and is_playing and game_session_end and loop.time() >= game_session_end:
                        is_playing = False
                        game_session_end = None
                        game_start_delay = None
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
                        if is_sleep_time(timezone, current_sleep_hour, current_sleep_minute, current_wake_hour, current_wake_minute):
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
        except websockets.exceptions.ConnectionClosed as e:
            # Code 1000 (normal) and 1001 (going away) are expected Discord behavior
            if e.code in [1000, 1001]:
                # Silent reconnect for normal closure
                backoff = 1
                continue
            else:
                print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Connection closed ({e.code}): {e.reason}. Retrying...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        except Exception as e:
            print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] Connection error: {e}. Retrying...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)

async def run_account(account, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10, play_game=False, game_name='Counter-Strike 2', game_image='', min_play_hours=2, max_play_hours=5, game_sessions='11-14,20-23'):
    await onliner(account["token"], account["username"], human_schedule, timezone, sleep_start, sleep_end, wake_start, wake_end, play_game, game_name, game_image, min_play_hours, max_play_hours, game_sessions)

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
    game_sessions = os.getenv("GAME_SESSIONS", "11-14,20-23")  # Time windows for gaming (e.g., "11-14,20-23")
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
                max_play_hours,
                game_sessions
            )
        ) 
        for a in accounts
    ]
    await asyncio.gather(*tasks)

asyncio.run(run_onliner())
