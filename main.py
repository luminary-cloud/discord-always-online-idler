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
    headers = {"Authorization": token, "Content-Type": "application/json"}
    r = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
    if r.status_code == 401:
        headers = {"Authorization": f"Bot {token}", "Content-Type": "application/json"}
        r = requests.get("https://discord.com/api/v10/users/@me", headers=headers)
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
    now = datetime.now(ZoneInfo(timezone))
    current_minutes = now.hour * 60 + now.minute
    sleep_minutes = sleep_hour * 60 + sleep_minute
    wake_minutes = wake_hour * 60 + wake_minute

    if sleep_minutes > wake_minutes:
        # Crosses midnight
        return current_minutes >= sleep_minutes or current_minutes < wake_minutes
    else:
        return sleep_minutes <= current_minutes < wake_minutes

async def onliner(token, username, human_schedule=False, timezone='Europe/Amsterdam', sleep_start=22, sleep_end=2, wake_start=6, wake_end=10, play_game=False, game_name='Counter-Strike 2', game_image='', min_play_hours=2, max_play_hours=5, game_sessions='11-14,20-23'):
    backoff = 1
    max_backoff = 60
    sleep_logged = False
    current_sleep_hour = None
    current_wake_hour = None
    current_sleep_minute = None
    current_wake_minute = None
    schedule_date = None
    game_session_end = None
    is_playing = False
    game_start_delay = None
    daily_game_times = []
    game_times_generated = None

    # Session tracking for RESUME support
    session_id = None
    resume_gateway_url = None
    seq = None

    game_session_windows = []
    if play_game and game_sessions:
        for session in game_sessions.split(','):
            if '-' in session:
                try:
                    start, end = session.strip().split('-')
                    game_session_windows.append((int(start), int(end)))
                except ValueError:
                    pass

    if human_schedule:
        now = datetime.now(ZoneInfo(timezone))
        today = now.date()

        if sleep_start > sleep_end:
            # Crosses midnight
            current_sleep_hour = random.choice(list(range(sleep_start, 24)) + list(range(0, sleep_end + 1)))
        else:
            current_sleep_hour = random.randint(sleep_start, sleep_end)

        current_wake_hour = random.randint(wake_start, wake_end)

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
            if human_schedule:
                now = datetime.now(ZoneInfo(timezone))
                today = now.date()

                if schedule_date != today:
                    if sleep_start > sleep_end:
                        # Crosses midnight
                        current_sleep_hour = random.choice(list(range(sleep_start, 24)) + list(range(0, sleep_end + 1)))
                    else:
                        current_sleep_hour = random.randint(sleep_start, sleep_end)

                    current_wake_hour = random.randint(wake_start, wake_end)

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

            if play_game and game_session_windows:
                now = datetime.now(ZoneInfo(timezone))
                today = now.date()

                if game_times_generated != today:
                    daily_game_times = []
                    for window_start, window_end in game_session_windows:
                        if random.random() < 0.7:
                            window_duration = window_end - window_start
                            if window_duration < min_play_hours:
                                continue

                            max_possible_duration = min(max_play_hours, window_duration)
                            duration = random.uniform(min_play_hours, max_possible_duration)
                            latest_start = window_end - duration
                            start_offset_hours = random.uniform(0, latest_start - window_start)
                            start_hour = window_start + start_offset_hours

                            daily_game_times.append((start_hour, duration))

                    game_times_generated = today
                    if daily_game_times:
                        sessions_str = ", ".join([f"{int(s[0]):02d}:{int((s[0] % 1) * 60):02d} ({s[1]:.1f}h)" for s in daily_game_times])
                        print(f"{Fore.WHITE}[{Fore.CYAN}🎮{Fore.WHITE}] {username} game sessions today: {sessions_str}")

            if human_schedule and is_sleep_time(timezone, current_sleep_hour, current_sleep_minute, current_wake_hour, current_wake_minute):
                if not sleep_logged:
                    now = datetime.now(ZoneInfo(timezone))
                    print(f"{Fore.WHITE}[{Fore.YELLOW}💤{Fore.WHITE}] {username} is sleeping (offline until ~{current_wake_hour:02d}:{current_wake_minute:02d} {timezone})")
                    sleep_logged = True
                    is_playing = False
                    game_session_end = None
                    game_start_delay = None
                await asyncio.sleep(300)
                continue
            elif sleep_logged:
                now = datetime.now(ZoneInfo(timezone))
                print(f"{Fore.WHITE}[{Fore.GREEN}☀️{Fore.WHITE}] {username} waking up at {now.strftime('%H:%M')}")
                sleep_logged = False
                backoff = 1

            gateway_url = resume_gateway_url if resume_gateway_url else "wss://gateway.discord.gg/?v=10&encoding=json"

            async with websockets.connect(
                gateway_url,
                max_size=None,
            ) as ws:
                hello = json.loads(await ws.recv())
                interval = hello["d"]["heartbeat_interval"] / 1000
                # Jitter prevents all clients from syncing heartbeats
                jitter = random.uniform(0, 5)
                interval += jitter

                if session_id and seq is not None:
                    resume = {
                        "op": 6,
                        "d": {
                            "token": token,
                            "session_id": session_id,
                            "seq": seq
                        }
                    }
                    await ws.send(json.dumps(resume))
                else:
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

                ready_received = False
                while not ready_received:
                    msg = await ws.recv()
                    evt = json.loads(msg)
                    if evt.get("t") == "READY":
                        session_id = evt["d"]["session_id"]
                        resume_gateway_url = evt["d"].get("resume_gateway_url", "wss://gateway.discord.gg/?v=10&encoding=json")
                        ready_received = True
                    elif evt.get("t") == "RESUMED":
                        ready_received = True
                    elif evt.get("op") == 9:  # INVALID_SESSION
                        session_id = None
                        seq = None
                        resume_gateway_url = None
                        await asyncio.sleep(random.uniform(1, 5))
                        await ws.close()
                        break
                    if "s" in evt and evt["s"]:
                        seq = evt["s"]

                if not ready_received:
                    continue

                if play_game and is_playing:
                    activity = {
                        "name": game_name,
                        "type": 0,
                    }
                    activity["timestamps"] = {
                        "start": int(time.time() * 1000)
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

                loop = asyncio.get_event_loop()
                next_heartbeat = loop.time() + interval
                last_sleep_check = loop.time()
                last_game_check = loop.time()
                last_heartbeat_ack = loop.time()
                heartbeat_ack_received = True

                while True:
                    # Zombie connection: no ACK in 2 intervals
                    if not heartbeat_ack_received and (loop.time() - last_heartbeat_ack) > (interval * 2):
                        print(f"{Fore.WHITE}[{Fore.YELLOW}⚠{Fore.WHITE}] {username} zombie connection detected, reconnecting...")
                        await ws.close()
                        break

                    if play_game and daily_game_times and not is_playing and game_session_end is None and (loop.time() - last_game_check) >= 90:
                        now = datetime.now(ZoneInfo(timezone))
                        current_time = now.hour + now.minute / 60.0

                        for session_start, session_duration in daily_game_times:
                            time_until_start = (session_start - current_time) * 3600

                            if -300 <= time_until_start <= 300:  # Within 5 min window
                                play_duration = session_duration * 3600
                                game_session_end = loop.time() + play_duration
                                game_start_delay = loop.time() + random.randint(60, 300)
                                print(f"{Fore.WHITE}[{Fore.CYAN}⏰{Fore.WHITE}] {username} preparing to start {game_name} (~{session_duration:.1f}h session)")
                                break
                        last_game_check = loop.time()

                    if play_game and not is_playing and game_start_delay and loop.time() >= game_start_delay:
                        is_playing = True
                        game_start_delay = None
                        hours = (game_session_end - loop.time()) / 3600
                        print(f"{Fore.WHITE}[{Fore.GREEN}🎮{Fore.WHITE}] {username} starting {game_name} (~{hours:.1f}h session)")
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

                    if play_game and is_playing and game_session_end and loop.time() >= game_session_end:
                        is_playing = False
                        game_session_end = None
                        game_start_delay = None
                        print(f"{Fore.WHITE}[{Fore.YELLOW}🛑{Fore.WHITE}] {username} stopped playing {game_name}")
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

                    if human_schedule and (loop.time() - last_sleep_check) >= 300:
                        if is_sleep_time(timezone, current_sleep_hour, current_sleep_minute, current_wake_hour, current_wake_minute):
                            await ws.close()
                            break
                        last_sleep_check = loop.time()

                    timeout = max(0, next_heartbeat - loop.time())
                    try:
                        msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                        evt = json.loads(msg)

                        if "s" in evt and evt["s"]:
                            seq = evt["s"]

                        if evt.get("op") == 11:
                            heartbeat_ack_received = True
                            last_heartbeat_ack = loop.time()

                        elif evt.get("op") == 7:
                            print(f"{Fore.WHITE}[{Fore.CYAN}🔄{Fore.WHITE}] {username} received reconnect request")
                            await ws.close()
                            backoff = 1
                            break

                        elif evt.get("op") == 9:
                            session_id = None
                            seq = None
                            resume_gateway_url = None
                            resumable = evt.get("d", False)
                            if not resumable:
                                await asyncio.sleep(random.uniform(1, 5))
                            await ws.close()
                            break

                    except asyncio.TimeoutError:
                        heartbeat_ack_received = False
                        hb = {"op": 1, "d": seq}
                        await ws.send(json.dumps(hb))
                        next_heartbeat += interval
        # 1000=normal, 1001=going away, 1006=abnormal, 4000=unknown
        except websockets.exceptions.ConnectionClosed as e:
            if e.code in [1000, 1001, 1006, 4000]:
                backoff = 1
                continue
            elif e.code in [4004, 4010, 4011, 4012, 4013, 4014]:
                print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] {username} authentication error ({e.code}): {e.reason}. Cannot reconnect.")
                return
            else:
                print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] {username} connection closed ({e.code}): {e.reason}. Retrying...")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
        except Exception as e:
            print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] {username} connection error: {e}. Retrying...")
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

    if len(tokens) > 5:
        print(f"{Fore.WHITE}[{Fore.YELLOW}!{Fore.WHITE}] More than 5 tokens provided; using the first 5.")
        tokens = tokens[:5]

    if not tokens:
        print(f"{Fore.WHITE}[{Fore.RED}-{Fore.WHITE}] No token found. Set TOKEN or TOKENS (max 5).")
        sys.exit()

    human_schedule = os.getenv("HUMAN_SCHEDULE_MODE", "false").lower() in ["true", "1", "yes"]
    timezone = os.getenv("TIMEZONE", "Europe/Amsterdam")
    sleep_start = int(os.getenv("SLEEP_TIME_START", "22"))
    sleep_end = int(os.getenv("SLEEP_TIME_END", "2"))
    wake_start = int(os.getenv("WAKE_TIME_START", "6"))
    wake_end = int(os.getenv("WAKE_TIME_END", "10"))

    game_name = os.getenv("GAME_NAME", "Counter-Strike 2")
    game_image = os.getenv("GAME_IMAGE", "")
    game_sessions = os.getenv("GAME_SESSIONS", "11-14,20-23")
    min_play_hours = float(os.getenv("MIN_PLAY_HOURS", "2"))
    max_play_hours = float(os.getenv("MAX_PLAY_HOURS", "5"))
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

        play_game = False
        if game_accounts:
            play_game = a['username'] in game_accounts or a['userid'] in game_accounts

        game_info = ""
        if play_game:
            game_info = f" {Fore.GREEN}[Playing: {game_name}]"

        print(f"{Fore.WHITE}[{Fore.LIGHTGREEN_EX}+{Fore.WHITE}] Logged in as {Fore.LIGHTBLUE_EX}{a['username']} {Fore.WHITE}({a['userid']}){schedule_info}{game_info}")

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
