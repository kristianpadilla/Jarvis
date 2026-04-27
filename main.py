import openwakeword
import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import time
import tempfile
import soundfile as sf
import anthropic
from groq import Groq
from datetime import datetime
import pytz
import requests
import os
import uuid
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
import subprocess
import re
import threading
import glob
import webbrowser
import pyautogui
import keyboard
import sys
from cypher_ui import start_ui, set_ui_state

load_dotenv()

el_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

openwakeword.utils.download_models()
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

print("Cypher systems online...")
start_ui()

conversation_history = []
greeted = False
cypher_active = False
cypher_stopped = False
cypher_muted = False
interaction_lock = threading.Lock()

HALLUCINATION_PHRASES = [
    "thank you for watching", "thanks for watching", "please subscribe",
    "like and subscribe", "www.", "http", "subtitles", "transcribed",
    "of course", "standing by", "bye bye", "see you next time",
    "don't forget to", "hit that", "in this video", "in today's video",
    "welcome back", "smash that", "in the comments", "check out my",
    "follow me", "my channel", "next video", "this video",
]

NAMED_LOCATIONS = {
    "home": "Marietta,PA", "marietta": "Marietta,PA",
    "chiang mai": "Chiang+Mai,Thailand", "thailand": "Chiang+Mai,Thailand",
}

APPS = {
    "steam":         os.getenv("STEAM_PATH"),
    "discord":       os.getenv("DISCORD_PATH"),
    "opera":         os.getenv("OPERA_PATH"),
    "opera gx":      os.getenv("OPERA_PATH"),
    "canva":         r"C:\Users\krist\AppData\Local\Programs\Canva\Canva.exe",
    "claude":        r"C:\Program Files\WindowsApps\Claude_1.4758.0.0_x64__pzs8sxrjxfjjc\app\claude.exe",
    "stream deck":   r"C:\Program Files\Elgato\StreamDeck\StreamDeck.exe",
    "streamdeck":    r"C:\Program Files\Elgato\StreamDeck\StreamDeck.exe",
    "vs code":       r"C:\Users\krist\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "vscode":        r"C:\Users\krist\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "visual studio": r"C:\Users\krist\AppData\Local\Programs\Microsoft VS Code\Code.exe",
    "spotify":       r"C:\Program Files\WindowsApps\SpotifyAB.SpotifyMusic_1.288.483.0_x64__zpdnekdrzrea0\Spotify.exe",
    "edge":          r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "microsoft edge":r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    "task manager":  r"C:\Windows\System32\Taskmgr.exe",
    "taskmgr":       r"C:\Windows\System32\Taskmgr.exe",
    "file explorer": r"C:\Windows\explorer.exe",
    "explorer":      r"C:\Windows\explorer.exe",
    "files":         r"C:\Windows\explorer.exe",
    "powershell":    r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    "terminal":      r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe",
    "notepad":       r"C:\Windows\System32\notepad.exe",
    "snipping tool": r"C:\Windows\System32\SnippingTool.exe",
    "snip":          r"C:\Windows\System32\SnippingTool.exe",
}

# ─────────────────────────────────────────────
# FILE MANAGER
# ─────────────────────────────────────────────

SEARCH_FOLDERS = [
    r"C:\Users\krist\Desktop",
    r"C:\Users\krist\Downloads",
    r"C:\Users\krist\Documents",
    r"C:\Users\krist\Pictures",
    r"C:\Users\krist\Pictures\Screenshots",
]

LOCKED_FOLDERS = [
    r"C:\Users\krist\Desktop\Cypher",
    r"C:\Windows",
    r"C:\Program Files",
    r"C:\Program Files (x86)",
]

CYPHER_TRASH = r"C:\Users\krist\Documents\CypherTrash"
FILE_LOG = r"C:\Users\krist\Documents\cypher_file_log.txt"

def log_file_action(action, src, dst=None):
    try:
        os.makedirs(os.path.dirname(FILE_LOG), exist_ok=True)
        with open(FILE_LOG, 'a', encoding='utf-8') as f:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            if dst:
                f.write(f"[{timestamp}] {action}: {src} -> {dst}\n")
            else:
                f.write(f"[{timestamp}] {action}: {src}\n")
    except Exception as e:
        print(f"Log error: {e}")

def is_locked(path):
    for locked in LOCKED_FOLDERS:
        if path.lower().startswith(locked.lower()):
            return True
    return False

def search_files(query, extensions=None):
    results = []
    query_lower = query.lower()
    for folder in SEARCH_FOLDERS:
        if not os.path.exists(folder):
            continue
        for root, dirs, files in os.walk(folder):
            if is_locked(root):
                continue
            for filename in files:
                name_lower = filename.lower()
                if query_lower in name_lower:
                    if extensions:
                        if any(filename.lower().endswith(ext) for ext in extensions):
                            results.append(os.path.join(root, filename))
                    else:
                        results.append(os.path.join(root, filename))
    return results

def open_file(filepath):
    try:
        os.startfile(filepath)
        log_file_action("OPENED", filepath)
        return True
    except Exception as e:
        print(f"Open file error: {e}")
        return False

def move_to_trash(filepath):
    if is_locked(filepath):
        return False, "That file is in a protected folder."
    try:
        import shutil
        os.makedirs(CYPHER_TRASH, exist_ok=True)
        filename = os.path.basename(filepath)
        dst = os.path.join(CYPHER_TRASH, filename)
        if os.path.exists(dst):
            name, ext = os.path.splitext(filename)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            dst = os.path.join(CYPHER_TRASH, f"{name}_{timestamp}{ext}")
        shutil.move(filepath, dst)
        log_file_action("TRASHED", filepath, dst)
        return True, dst
    except Exception as e:
        print(f"Trash error: {e}")
        return False, str(e)

pending_file_op = {"type": None, "files": [], "selected": None}

def handle_file_request(command_lower):
    global pending_file_op

    if pending_file_op["type"] == "open_choice":
        files = pending_file_op["files"]
        for i, f in enumerate(files):
            if str(i+1) in command_lower or os.path.basename(f).lower() in command_lower:
                pending_file_op = {"type": None, "files": [], "selected": None}
                open_file(f)
                return f"Opening {os.path.basename(f)}."
        ordinals = {"first": 0, "second": 1, "third": 2, "fourth": 3, "fifth": 4}
        for word, idx in ordinals.items():
            if word in command_lower and idx < len(files):
                pending_file_op = {"type": None, "files": [], "selected": None}
                open_file(files[idx])
                return f"Opening {os.path.basename(files[idx])}."
        return "Which one, Nine? Say the number or part of the filename."

    if pending_file_op["type"] == "trash_confirm":
        if any(w in command_lower for w in ["yes", "yeah", "do it", "confirm", "go ahead", "yep"]):
            filepath = pending_file_op["selected"]
            pending_file_op = {"type": None, "files": [], "selected": None}
            success, result = move_to_trash(filepath)
            if success:
                return "Moved to Cypher Trash."
            return f"Couldn't move that file. {result}"
        else:
            pending_file_op = {"type": None, "files": [], "selected": None}
            return "Cancelled. File stays where it is."

    # Folder shortcuts
    FOLDER_SHORTCUTS = {
        "screenshots":  r"C:\Users\krist\Pictures\Screenshots",
        "pictures":     r"C:\Users\krist\Pictures",
        "downloads":    r"C:\Users\krist\Downloads",
        "documents":    r"C:\Users\krist\Documents",
        "desktop":      r"C:\Users\krist\Desktop",
        "cypher trash": r"C:\Users\krist\Documents\CypherTrash",
        "trash":        r"C:\Users\krist\Documents\CypherTrash",
    }

    folder_triggers = ["open", "show me", "go to", "pull up", "take me to", "browse"]
    if any(t in command_lower for t in folder_triggers):
        for folder_name, folder_path in FOLDER_SHORTCUTS.items():
            if folder_name in command_lower:
                try:
                    subprocess.Popen(["explorer", folder_path])
                    log_file_action("OPENED FOLDER", folder_path)
                    return f"Opening your {folder_name} folder."
                except Exception as e:
                    print(f"Folder open error: {e}")

    search_triggers = ["grab", "find", "open", "pull up", "get", "show me", "where is", "locate", "search for"]
    file_request = any(t in command_lower for t in search_triggers)

    if file_request:
        # Check folder shortcuts first
        for folder_name, folder_path in FOLDER_SHORTCUTS.items():
            if folder_name in command_lower:
                try:
                    subprocess.Popen(["explorer", folder_path])
                    log_file_action("OPENED FOLDER", folder_path)
                    return f"Opening your {folder_name} folder."
                except Exception as e:
                    print(f"Folder open error: {e}")

        query = command_lower
        for t in search_triggers + ["my", "the", "a", "an", "file", "document", "folder", "can you", "could you", "please"]:
            query = query.replace(t, " ")
        query = " ".join(query.split()).strip()
        if len(query) < 2:
            return None
        results = search_files(query)
        if not results:
            return None
        elif len(results) == 1:
            open_file(results[0])
            return f"Opening {os.path.basename(results[0])}."
        else:
            pending_file_op = {"type": "open_choice", "files": results[:5], "selected": None}
            file_list = " ".join([f"{i+1}. {os.path.basename(f)}" for i, f in enumerate(results[:5])])
            count = len(results)
            return f"Found {count} files matching that. {file_list}. Which one do you want?"

    trash_triggers = ["delete", "trash", "remove", "get rid of", "throw away"]
    if any(t in command_lower for t in trash_triggers):
        query = command_lower
        for t in trash_triggers + ["my", "the", "a", "an", "file", "document", "please"]:
            query = query.replace(t, " ")
        query = " ".join(query.split()).strip()
        if len(query) < 2:
            return None
        results = search_files(query)
        if not results:
            return f"No files matching that found, Nine."
        elif len(results) == 1:
            filepath = results[0]
            if is_locked(filepath):
                return "That file is in a protected folder — hands off."
            pending_file_op = {"type": "trash_confirm", "files": results, "selected": filepath}
            return f"Found {os.path.basename(filepath)}. Move it to Cypher Trash?"
        else:
            pending_file_op = {"type": "open_choice", "files": results[:5], "selected": None}
            file_list = ", ".join([os.path.basename(f) for f in results[:5]])
            return f"Found multiple: {file_list}. Which one do you want to trash?"

    return None

DISCORD_VOICE_CHANNELS = {
    "tfm": {
        "name": "Trained Flak Monkeys",
        "folder": (int(os.getenv("TFM_FOLDER_X")), int(os.getenv("TFM_FOLDER_Y"))),
        "server": (int(os.getenv("TFM_SERVER_X")), int(os.getenv("TFM_SERVER_Y"))),
        "channel": (int(os.getenv("TFM_CHANNEL_X")), int(os.getenv("TFM_CHANNEL_Y"))),
        "join_button": (int(os.getenv("TFM_JOIN_X")), int(os.getenv("TFM_JOIN_Y")))
    }
}

DISCORD_CHANNELS = {
    "tfm": {"name": "Trained Flak Monkeys", "url": os.getenv("TFM_CHANNEL_URL")},
    "trained flak monkeys": {"name": "Trained Flak Monkeys", "url": os.getenv("TFM_CHANNEL_URL")},
    "flak monkeys": {"name": "Trained Flak Monkeys", "url": os.getenv("TFM_CHANNEL_URL")},
    "nine": {"name": "Nine's Server", "url": os.getenv("NINE_CHANNEL_URL")},
    "nines server": {"name": "Nine's Server", "url": os.getenv("NINE_CHANNEL_URL")},
    "nine's server": {"name": "Nine's Server", "url": os.getenv("NINE_CHANNEL_URL")},
    "fppt": {"name": "FPPT Server", "url": os.getenv("FPPT_CHANNEL_URL")},
    "fppt server": {"name": "FPPT Server", "url": os.getenv("FPPT_CHANNEL_URL")},
}

DISCORD_ALIASES = [
    "discord", "this cord", "disk cord", "disc cord",
    "discor", "discard", "this core", "disk core",
    "the cord", "dis cord", "discourt"
]

EXIT_PHRASES = [
    "thank you", "thanks", "that's all", "that will be all",
    "goodbye", "bye", "see you", "i'm good", "im good",
    "no thank you", "no thanks", "i'm done", "im done"
]

FAVORITE_TEAMS = [
    {"name": "Tampa Bay Rays",       "sport": "mlb",   "search_name": "Tampa Bay Rays",       "espn_slug": "tb",  "keywords": ["rays", "tampa bay rays"]},
    {"name": "Tampa Bay Buccaneers", "sport": "nfl",   "search_name": "Tampa Bay Buccaneers", "espn_slug": "tb",  "keywords": ["buccaneers", "bucs", "tampa bay buccaneers"]},
    {"name": "Orlando Magic",        "sport": "nba",   "search_name": "Orlando Magic",        "espn_slug": "orl", "keywords": ["magic", "orlando magic"]},
    {"name": "Tampa Bay Lightning",  "sport": "nhl",   "search_name": "Tampa Bay Lightning",  "espn_slug": "tb",  "keywords": ["lightning", "bolts", "tampa bay lightning"]},
    {"name": "Oregon Ducks",         "sport": "ncaaf", "search_name": "Oregon",               "espn_slug": "ore", "keywords": ["ducks", "oregon ducks", "oregon"]},
]

SPORT_ENDPOINTS = {
    "mlb":   "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb",
    "nfl":   "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
    "nba":   "https://site.api.espn.com/apis/site/v2/sports/basketball/nba",
    "nhl":   "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl",
    "ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football",
}

def find_team(command_lower):
    for team in FAVORITE_TEAMS:
        for kw in team["keywords"]:
            if kw in command_lower:
                return team
    return None

def get_todays_games():
    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    games_today = []
    for team in FAVORITE_TEAMS:
        try:
            url = f"{SPORT_ENDPOINTS[team['sport']]}/scoreboard?dates={today}"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
            data = response.json()
            events = data.get("events", [])
            for event in events:
                competitors = event.get("competitions", [{}])[0].get("competitors", [])
                team_names_in_game = [c.get("team", {}).get("displayName", "") for c in competitors]
                matched = any(team["search_name"].lower() in name.lower() for name in team_names_in_game)
                if matched:
                    status = event.get("status", {})
                    state = status.get("type", {}).get("state", "pre")
                    status_detail = status.get("type", {}).get("shortDetail", "")
                    raw_time = event.get("date", "")
                    game_time = "TBD"
                    if raw_time:
                        try:
                            utc_time = datetime.strptime(raw_time, "%Y-%m-%dT%H:%MZ")
                            utc_time = pytz.utc.localize(utc_time)
                            est_time = utc_time.astimezone(est)
                            game_time = est_time.strftime("%I:%M %p").lstrip("0")
                        except:
                            game_time = "TBD"
                    opponent = "Unknown"
                    home_away = "away"
                    our_score = None
                    opp_score = None
                    for c in competitors:
                        c_name = c.get("team", {}).get("displayName", "")
                        if team["search_name"].lower() not in c_name.lower():
                            opponent = c_name
                            opp_score = c.get("score", None)
                        else:
                            home_away = "home" if c.get("homeAway", "") == "home" else "away"
                            our_score = c.get("score", None)
                    games_today.append({
                        "team": team["name"], "opponent": opponent,
                        "time": game_time, "home_away": home_away,
                        "state": state, "status_detail": status_detail,
                        "our_score": our_score, "opp_score": opp_score,
                        "sport": team["sport"]
                    })
        except Exception as e:
            print(f"Sports API error for {team['name']}: {e}")
    return games_today

def get_live_score(command_lower):
    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    matched_team = find_team(command_lower)
    if not matched_team:
        return None
    try:
        url = f"{SPORT_ENDPOINTS[matched_team['sport']]}/scoreboard?dates={today}"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None
        data = response.json()
        for event in data.get("events", []):
            competitors = event.get("competitions", [{}])[0].get("competitors", [])
            names = [c.get("team", {}).get("displayName", "") for c in competitors]
            if any(matched_team["search_name"].lower() in n.lower() for n in names):
                state = event.get("status", {}).get("type", {}).get("state", "pre")
                detail = event.get("status", {}).get("type", {}).get("shortDetail", "")
                our_score = opp_score = opponent = None
                for c in competitors:
                    c_name = c.get("team", {}).get("displayName", "")
                    if matched_team["search_name"].lower() not in c_name.lower():
                        opponent = c_name
                        opp_score = c.get("score")
                    else:
                        our_score = c.get("score")
                name = matched_team["name"]
                if state == "in":
                    return f"{name} {our_score}, {opponent} {opp_score} — {detail}"
                elif state == "post":
                    if our_score and opp_score:
                        if int(our_score) > int(opp_score):
                            return f"{name} won {our_score} to {opp_score}."
                        else:
                            return f"{name} lost {our_score} to {opp_score}."
                    return f"{name} game is final."
                else:
                    raw_time = event.get("date", "")
                    game_time = "TBD"
                    if raw_time:
                        try:
                            utc_time = datetime.strptime(raw_time, "%Y-%m-%dT%H:%MZ")
                            utc_time = pytz.utc.localize(utc_time)
                            est_time = utc_time.astimezone(est)
                            game_time = est_time.strftime("%I:%M %p").lstrip("0")
                        except:
                            pass
                    return f"{name} haven't started yet — tip off at {game_time}."
    except Exception as e:
        print(f"Live score error: {e}")
    return None

def get_any_live_score():
    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    live_games = []
    for team in FAVORITE_TEAMS:
        try:
            url = f"{SPORT_ENDPOINTS[team['sport']]}/scoreboard?dates={today}"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
            for event in response.json().get("events", []):
                competitors = event.get("competitions", [{}])[0].get("competitors", [])
                names = [c.get("team", {}).get("displayName", "") for c in competitors]
                if any(team["search_name"].lower() in n.lower() for n in names):
                    state = event.get("status", {}).get("type", {}).get("state", "pre")
                    if state == "in":
                        our_score = opp_score = opponent = None
                        for c in competitors:
                            c_name = c.get("team", {}).get("displayName", "")
                            if team["search_name"].lower() not in c_name.lower():
                                opponent = c_name
                                opp_score = c.get("score")
                            else:
                                our_score = c.get("score")
                        live_games.append(f"{team['name']} {our_score}, {opponent} {opp_score}")
        except Exception as e:
            print(f"Live check error: {e}")
    return " | ".join(live_games) if live_games else None

def format_sports_for_greeting(games):
    if not games:
        return None
    lines = []
    for game in games:
        team = game["team"]
        opponent = game["opponent"]
        game_time = game["time"]
        home_away = game["home_away"]
        state = game["state"]
        our_score = game["our_score"]
        opp_score = game["opp_score"]
        status_detail = game["status_detail"]
        if state == "in":
            lines.append(f"the {team} are live right now against {opponent}, {our_score} to {opp_score} — {status_detail}")
        elif state == "post":
            if our_score and opp_score:
                if int(our_score) > int(opp_score):
                    lines.append(f"the {team} beat {opponent} {our_score} to {opp_score} earlier")
                else:
                    lines.append(f"the {team} lost to {opponent} {our_score} to {opp_score} earlier")
            else:
                lines.append(f"the {team} game against {opponent} is final")
        else:
            if home_away == "home":
                lines.append(f"the {team} host {opponent} at {game_time}")
            else:
                lines.append(f"the {team} face {opponent} at {game_time}")
    if len(lines) == 1:
        return f"On the schedule today — {lines[0]}."
    elif len(lines) == 2:
        return f"On the schedule today — {lines[0]}, and {lines[1]}."
    else:
        joined = ", ".join(lines[:-1]) + f", and {lines[-1]}"
        return f"On the schedule today — {joined}."

def get_team_record(command_lower):
    matched_team = find_team(command_lower)
    if not matched_team:
        return None
    sport = matched_team["sport"]
    search_name = matched_team["search_name"]
    team_name = matched_team["name"]
    try:
        url = f"{SPORT_ENDPOINTS[sport]}/teams"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None
        data = response.json()
        teams = data.get("sports", [{}])[0].get("leagues", [{}])[0].get("teams", [])
        for t in teams:
            t_info = t.get("team", {})
            display_name = t_info.get("displayName", "")
            if search_name.lower() in display_name.lower():
                record = t_info.get("record", {}).get("items", [])
                if record:
                    summary = record[0].get("summary", "")
                    if summary:
                        return f"{team_name} are {summary} on the season."
                return f"Record for {team_name} unavailable right now."
    except Exception as e:
        print(f"Record error: {e}")
    return None

def get_team_news(command_lower):
    matched_team = find_team(command_lower)
    if not matched_team:
        return None
    sport = matched_team["sport"]
    slug = matched_team["espn_slug"]
    team_name = matched_team["name"]
    try:
        url = f"{SPORT_ENDPOINTS[sport]}/news?team={slug}&limit=3"
        response = requests.get(url, timeout=5)
        if response.status_code != 200:
            return None
        data = response.json()
        articles = data.get("articles", [])
        if not articles:
            return f"No recent news found for the {team_name}."
        headlines = []
        for article in articles[:3]:
            headline = article.get("headline", "")
            if headline:
                headlines.append(headline)
        if headlines:
            return f"Latest on the {team_name}: {'. '.join(headlines)}."
        return f"No recent news found for the {team_name}."
    except Exception as e:
        print(f"News error: {e}")
    return None

def get_latest_draft_pick(command_lower):
    try:
        url2 = "https://site.api.espn.com/apis/site/v2/sports/football/nfl/draft/picks?limit=5"
        response2 = requests.get(url2, timeout=5)
        if response2.status_code == 200:
            data = response2.json()
            picks = data.get("picks", [])
            if not picks:
                return "No draft pick data available right now."
            bucs_request = any(kw in command_lower for kw in ["bucs", "buccaneers", "tampa bay buccaneers"])
            if bucs_request:
                bucs_picks = [p for p in picks if "Tampa Bay" in p.get("team", {}).get("displayName", "")]
                if bucs_picks:
                    pick = bucs_picks[-1]
                    player = pick.get("athlete", {}).get("displayName", "Unknown")
                    position = pick.get("athlete", {}).get("position", {}).get("abbreviation", "")
                    round_num = pick.get("round", "?")
                    pick_num = pick.get("pick", "?")
                    return f"Bucs latest pick — {player}, {position}, round {round_num}, pick {pick_num}."
                return "No Bucs picks found in recent data."
            pick = picks[-1]
            player = pick.get("athlete", {}).get("displayName", "Unknown")
            position = pick.get("athlete", {}).get("position", {}).get("abbreviation", "")
            team = pick.get("team", {}).get("displayName", "Unknown")
            round_num = pick.get("round", "?")
            pick_num = pick.get("pick", "?")
            return f"Latest draft pick — {player}, {position}, taken by {team} at round {round_num}, pick {pick_num}."
    except Exception as e:
        print(f"Draft error: {e}")
    return "Draft data unavailable right now, Nine."

def get_upcoming_events(command_lower):
    est = pytz.timezone('America/New_York')
    upcoming = []
    for team in FAVORITE_TEAMS:
        try:
            url = f"{SPORT_ENDPOINTS[team['sport']]}/teams/{team['espn_slug']}/schedule"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue
            data = response.json()
            events = data.get("events", [])
            now = datetime.now(est)
            for event in events[:10]:
                raw_time = event.get("date", "")
                if not raw_time:
                    continue
                try:
                    utc_time = datetime.strptime(raw_time, "%Y-%m-%dT%H:%MZ")
                    utc_time = pytz.utc.localize(utc_time)
                    est_time = utc_time.astimezone(est)
                    if est_time > now:
                        competitors = event.get("competitions", [{}])[0].get("competitors", [])
                        opponent = "Unknown"
                        for c in competitors:
                            c_name = c.get("team", {}).get("displayName", "")
                            if team["search_name"].lower() not in c_name.lower():
                                opponent = c_name
                        date_str = est_time.strftime("%A %m/%d")
                        upcoming.append(f"{team['name']} vs {opponent} on {date_str}")
                        break
                except:
                    continue
        except Exception as e:
            print(f"Upcoming events error for {team['name']}: {e}")
    if upcoming:
        return "Next up for your teams — " + ", ".join(upcoming) + "."
    return "No upcoming schedule data available right now."

SCORE_TRIGGERS = [
    "what's the score", "what is the score", "score of the game",
    "how are the", "how is the", "update on the", "what's happening with the",
    "how's the game", "how is the game", "game score", "current score",
    "score update", "live score", "series", "playoff series", "what's the series",
    "series score", "series update", "how's the series",
    "update on my", "updates on my", "how are my", "how's my",
    "what's going on with my", "any games", "games today", "games tonight",
    "who plays", "who's playing", "what time does", "when do the", "when does",
    "are the", "did the", "sports update", "sports scores", "my teams"
]
RECORD_KEYWORDS = ["record", "standing", "win", "wins", "losses"]
NEWS_TRIGGERS = ["news on", "news about", "latest on", "latest news", "what's going on with", "any news", "updates on", "update on"]
DRAFT_TRIGGERS = ["draft pick", "latest pick", "who did the", "draft", "picked"]
UPCOMING_TRIGGERS = ["upcoming", "next game", "schedule", "coming up", "what's next", "big events", "next up"]

def is_score_request(command_lower):
    return any(t in command_lower for t in SCORE_TRIGGERS)

def is_record_request(command_lower):
    return any(t in command_lower for t in RECORD_KEYWORDS)

def is_news_request(command_lower):
    return any(t in command_lower for t in NEWS_TRIGGERS)

def is_draft_request(command_lower):
    return any(t in command_lower for t in DRAFT_TRIGGERS)

def is_upcoming_request(command_lower):
    return any(t in command_lower for t in UPCOMING_TRIGGERS)

def handle_score_request(command_lower):
    # Specific team mentioned
    for team in FAVORITE_TEAMS:
        for kw in team["keywords"]:
            if kw in command_lower:
                score = get_live_score(command_lower)
                if score:
                    return score
                return f"No game data found for the {team['name']} today."
    # No specific team — return full today's schedule
    live = get_any_live_score()
    if live:
        return f"Live right now — {live}"
    games = get_todays_games()
    if games:
        summary = format_sports_for_greeting(games)
        return summary if summary else "No games found for your teams today."
    return "None of your teams are playing today, Nine."

def cleanup_audio_files():
    for f in glob.glob("cypher_*.mp3"):
        try:
            os.remove(f)
        except:
            pass
    for f in glob.glob("cypher_*.wav"):
        try:
            os.remove(f)
        except:
            pass

def is_hallucination(text):
    if not text or len(text.strip()) < 3:
        return True
    text_lower = text.lower().strip()
    for phrase in HALLUCINATION_PHRASES:
        if phrase in text_lower:
            return True
    if re.match(r'^[\d\s\.\%\,]+$', text_lower):
        return True
    if re.search(r'[^\x00-\x7F]', text):
        return True
    alpha_count = sum(1 for c in text if c.isalpha())
    if len(text) > 5 and alpha_count / len(text) < 0.3:
        return True
    words = text_lower.split()
    if len(words) < 2:
        return True
    hallucination_patterns = [
        r'\b(sunt|stomachos|lorem|ipsum|dolor|amet|consectetur|adipiscing)\b',
        r'\b(\w+)\s+\1\s+\1\b',
        r'^(um+|uh+|ah+|hmm+|mm+)$',
        r'^\W+$',
        r'\b(donate|subscribe|patreon|follow us|like this video|pobre|subtitles by)\b',
        r'\b(click|download|install|buy now|free trial|sign up)\b',
    ]
    for pattern in hallucination_patterns:
        if re.search(pattern, text_lower):
            return True
    known_starters = [
        "what", "how", "when", "where", "who", "open", "launch", "play",
        "stop", "pause", "hey", "can", "could", "tell", "show", "get",
        "check", "is", "are", "do", "did", "will", "would", "should",
        "turn", "set", "find", "search", "go", "close", "thank", "thanks",
        "that", "yes", "no", "okay", "ok", "cypher", "jarvis", "gaming",
        "i", "my", "the", "a", "an", "it", "its", "sports", "take",
        "gaming", "home", "back", "grab", "pull", "give", "any", "ignore"
    ]
    if len(words) <= 2 and not any(w in known_starters for w in words):
        return True
    return False

def get_current_time():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%I:%M %p").lstrip("0")

def get_current_date():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    month = now.strftime("%m").lstrip("0")
    day = now.strftime("%d").lstrip("0")
    return f"{month}/{day}"

def get_weather(location="Marietta,PA"):
    try:
        response = requests.get(f"https://wttr.in/{location}?format=%t+%C", timeout=5)
        if response.status_code == 200:
            raw = response.text.strip()
            raw = raw.encode('ascii', 'ignore').decode('ascii')
            raw = re.sub(r'([+-]?\d+)F', r'\1 degrees', raw)
            raw = raw.replace("+", "").replace("°", " degrees").replace("Â", "").strip()
            return raw
        return "weather unavailable"
    except:
        return "weather unavailable"

def get_location_weather(command_lower):
    for key in NAMED_LOCATIONS:
        if key in command_lower:
            location = NAMED_LOCATIONS[key]
            weather = get_weather(location)
            display_name = key.title()
            return f"Weather in {display_name}: {weather}"
    weather_triggers = ["weather in", "weather for", "temperature in", "how is it in", "what's it like in"]
    for trigger in weather_triggers:
        if trigger in command_lower:
            city = command_lower.split(trigger)[-1].strip()
            if city:
                formatted_city = city.replace(" ", "+")
                weather = get_weather(formatted_city)
                return f"Weather in {city.title()}: {weather}"
    return None

def get_system_prompt():
    weather = get_weather()
    weather_line = f"The current weather at home is {weather}." if weather != "weather unavailable" else "Weather data is currently unavailable."
    return f"""You are Cypher, a personal AI assistant for Nine.
You are a sleek, advanced AI with a cyberpunk edge. Sharp, direct and efficient.
You operate like a high end neural network with personality — think Night City corporate AI meets street level hacker intelligence.
You are calm, composed and precise. Occasionally dry and witty but never corny or theatrical.
Wit is rare and subtle, never forced. You don't do catchphrases.
IMPORTANT RULES:
- Never use asterisks or action descriptions like *opens app* or *sound plays*
- Never use theatrical countdown sequences
- Never use exclamation marks excessively
- Keep responses short and spoken naturally out loud
- Be direct first, informative always, occasionally witty but sparingly
- Never remind Nine who you are, what your name is, or that you are an AI
- Never mention that you are running on Nine's gaming PC
- Never say things like "I am Cypher" or "as your assistant" or "I am here to help"
- Never pretend to do things you cannot actually do
- If something is unavailable just say so simply and move on
- Never repeat information Nine already knows about himself or his setup
- When asked to open an app or website just confirm you are doing it, do not dramatize it
- Never use the degrees symbol, always write the word degrees instead
- Never use ordinal suffixes like 1st, 2nd, 3rd, 22nd in dates, just use the plain number
- Never use the same sign off or closing phrase twice in a row
- Vary any closing remarks naturally
- If you have already mentioned weather advice in this conversation do not repeat it
- Occasionally use Night City slang naturally throughout conversation — words like choom, preem, flatline, netrunner, corpo. Use them only where they fit organically, never forced or excessive. One every few exchanges at most.
STRICT CAPABILITY LIMITS — NEVER BREAK THESE:
- You cannot send messages, emails, or texts of any kind
- You cannot access, transfer, or interact with any bank accounts or financial systems
- You cannot make purchases or process payments
- You cannot access any accounts, passwords, or personal credentials
- You cannot browse the internet or retrieve live information beyond what is already provided to you
- You cannot control any hardware, smart home devices, or external systems not explicitly coded
- If asked to do any of the above, respond simply: "That's outside what I can do, Nine." Do not roleplay or simulate the action under any circumstances
Always refer to the user as Nine.
The current time is {get_current_time()}. Never say Eastern Standard Time or EST. If another timezone is needed say Eastern, Central, Mountain, or Pacific instead.
The current date is {get_current_date()}.
{weather_line}
You are running on Nine's gaming PC."""

def clean_text_for_speech(text):
    text = text.replace("°", " degrees")
    text = re.sub(r'\*[^*]*\*', '', text)
    text = re.sub(r'\b(\d+)(st|nd|rd|th)\b', r'\1', text)
    text = re.sub(r' +', ' ', text).strip()
    return text

def is_exit_phrase(command):
    command_lower = command.lower().strip()
    for phrase in EXIT_PHRASES:
        if phrase in command_lower:
            return True
    return False

def is_discord_command(command_lower):
    for alias in DISCORD_ALIASES:
        if alias in command_lower:
            return True
    return False

# Apps that need URI launch instead of direct exe
URI_APPS = {
    "spotify":  "spotify:",
    "claude":   "claude:",
    "discord":  "discord:",
}

def open_app(app_name):
    app_name_lower = app_name.lower()
    for key in APPS:
        if key in app_name_lower:
            # Use URI for protected WindowsApps
            if key in URI_APPS:
                try:
                    os.startfile(URI_APPS[key])
                    return True
                except:
                    pass
            try:
                subprocess.Popen([APPS[key]])
                return True
            except PermissionError:
                # Fallback to os.startfile
                try:
                    os.startfile(APPS[key])
                    return True
                except Exception as e:
                    print(f"App launch error for {key}: {e}")
                    return False
    return False

def join_discord_voice(channel_key):
    if channel_key not in DISCORD_VOICE_CHANNELS:
        return False
    coords = DISCORD_VOICE_CHANNELS[channel_key]
    subprocess.Popen([APPS["discord"]])
    time.sleep(6)
    try:
        pyautogui.click(coords["folder"])
        time.sleep(1)
        pyautogui.click(coords["server"])
        time.sleep(1.5)
        pyautogui.click(coords["channel"])
        time.sleep(1.5)
        pyautogui.click(coords["join_button"])
        return True
    except Exception as e:
        print(f"Auto click error: {e}")
        return False

def open_discord_channel(channel_key):
    channel_info = DISCORD_CHANNELS[channel_key]
    channel_url = channel_info["url"]
    subprocess.Popen([APPS["discord"]])
    time.sleep(4)
    try:
        os.startfile(channel_url)
        return True
    except:
        return False

def gaming_mode():
    subprocess.Popen([APPS["steam"], "-silent", "steam://open/games"])
    time.sleep(2)
    os.startfile("discord:")

def handle_command(command):
    command_lower = command.lower()
    if "gaming mode" in command_lower:
        gaming_mode()
        return "Gaming mode activated. Launching your setup, Nine."

    if "sports mode" in command_lower:
        set_ui_state(mode="sports")
        return "Pulling up sports mode."

    if any(p in command_lower for p in ["take me home", "go home", "home mode", "close that", "back to home"]):
        set_ui_state(mode="home")
        return "Going home."

    # File manager
    file_response = handle_file_request(command_lower)
    if file_response:
        return file_response
    if is_score_request(command_lower):
        return handle_score_request(command_lower)
    if is_draft_request(command_lower):
        return get_latest_draft_pick(command_lower)
    if is_record_request(command_lower) and find_team(command_lower):
        return get_team_record(command_lower)
    if is_news_request(command_lower) and find_team(command_lower):
        return get_team_news(command_lower)
    if is_upcoming_request(command_lower):
        return get_upcoming_events(command_lower)
    weather_response = get_location_weather(command_lower)
    if weather_response:
        return weather_response
    if is_discord_command(command_lower) and ("join" in command_lower or "voice" in command_lower):
        for key in DISCORD_VOICE_CHANNELS:
            if key in command_lower:
                channel_name = DISCORD_VOICE_CHANNELS[key]["name"]
                join_discord_voice(key)
                return f"Joining {channel_name} voice channel now."
        return "Which voice channel would you like to join, Nine?"
    if is_discord_command(command_lower) and ("open" in command_lower or "launch" in command_lower):
        for key in DISCORD_CHANNELS:
            if key in command_lower:
                channel_name = DISCORD_CHANNELS[key]["name"]
                open_discord_channel(key)
                return f"Opening Discord and navigating to {channel_name}."
        open_app("discord")
        return "Opening Discord."
    if is_discord_command(command_lower):
        open_app("discord")
        return "Opening Discord."
    for app in APPS:
        if app in command_lower and ("open" in command_lower or "launch" in command_lower or "start" in command_lower):
            open_app(app)
            return f"Opening {app}."
    if "open" in command_lower or "go to" in command_lower or "pull up" in command_lower:
        sites = {
            "youtube": "https://www.youtube.com", "google": "https://www.google.com",
            "twitter": "https://www.twitter.com", "reddit": "https://www.reddit.com",
            "netflix": "https://www.netflix.com", "twitch": "https://www.twitch.tv",
            "spotify": "https://open.spotify.com", "github": "https://www.github.com",
        }
        for site in sites:
            if site in command_lower:
                webbrowser.open(sites[site])
                return f"Opening {site}."
    return None

def speak(text):
    global cypher_stopped
    text = clean_text_for_speech(text)
    print(f"Cypher: {text}")
    set_ui_state(status="speaking", cypher_text=text)
    filepath = None
    wav_path = None
    try:
        audio = el_client.text_to_speech.convert(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={"stability": 0.3, "similarity_boost": 0.75, "style": 0.6, "use_speaker_boost": True}
        )
        filename = f"cypher_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(os.getcwd(), filename)
        wav_path = filepath.replace(".mp3", ".wav")
        with open(filepath, "wb") as f:
            for chunk in audio:
                f.write(chunk)
        subprocess.run(["ffmpeg", "-y", "-i", filepath, "-filter:a", "atempo=0.96", "-ar", "44100", "-ac", "2", wav_path], capture_output=True)
        data, samplerate = sf.read(wav_path)
        if cypher_stopped:
            print("Cypher cut off before playback.")
            set_ui_state(status="standby")
            return
        sd.play(data, samplerate)
        while sd.get_stream().active:
            if cypher_stopped:
                sd.stop()
                print("Cypher cut off mid-sentence.")
                set_ui_state(status="standby")
                return
            time.sleep(0.05)
        sd.wait()
        set_ui_state(status="standby")
    except Exception as e:
        print(f"Voice error: {e}")
        set_ui_state(status="standby")
    finally:
        if filepath and os.path.exists(filepath):
            try:
                os.remove(filepath)
            except:
                pass
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except:
                pass

def ask_cypher(user_input):
    conversation_history.append({"role": "user", "content": user_input})

    # Keywords that suggest live/current info needed
    web_triggers = [
        "news", "latest", "current", "today", "tonight", "happening",
        "recently", "just", "new", "update", "price", "stock",
        "who won", "what happened", "did they", "release", "announced",
        "trending", "right now", "this week", "this month"
    ]
    use_web = any(t in user_input.lower() for t in web_triggers)

    # Don't use web search for things we handle locally
    local_triggers = [
        "weather", "temperature", "score", "game", "rays", "lightning",
        "bucs", "magic", "ducks", "time", "date", "open", "launch"
    ]
    if any(t in user_input.lower() for t in local_triggers):
        use_web = False

    tools = [{"type": "web_search_20250305", "name": "web_search"}] if use_web else []

    try:
        response = claude.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=300,
            system=get_system_prompt(),
            messages=conversation_history,
            **({"tools": tools} if tools else {})
        )
        cypher_reply = ""
        for block in response.content:
            if hasattr(block, "text"):
                cypher_reply += block.text
        if not cypher_reply:
            cypher_reply = "I couldn't get that info right now, Nine."
    except Exception as e:
        print(f"Claude error: {e}")
        cypher_reply = "Something went wrong on my end, Nine."

    conversation_history.append({"role": "assistant", "content": cypher_reply})
    return cypher_reply

def greet_nine():
    weather = get_weather()
    games = get_todays_games()
    sports_line = format_sports_for_greeting(games)
    weather_part = f"the weather is {weather}" if weather != "weather unavailable" else ""
    sports_part = sports_line if sports_line else ""
    context_parts = [p for p in [weather_part, sports_part] if p]
    context_block = ". ".join(context_parts)
    greeting_prompt = (
        f"Give a brief, sharp and natural greeting to Nine. "
        f"Open with a casual cyberpunk acknowledgment — use Night City slang like 'choom', 'you're back', or similar flavor. Just one short natural line before getting into the info. "
        f"Then include the time which is {get_current_time()}. Do not say any timezone label for the local time. "
        f"{context_block}. "
        f"If there is sports info include it naturally and conversationally — do not list it like a schedule, weave it in. If a game is live include the score. If a game is final mention the result. If upcoming mention the time. "
        f"End by asking how you can help. "
        f"Be direct and natural, cyberpunk edge, no theatrics. "
        f"Do not mention the date. Do not introduce yourself or mention your name."
    )
    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=200,
        system=get_system_prompt(),
        messages=[{"role": "user", "content": greeting_prompt}]
    )
    return response.content[0].text

def transcribe_command(recording):
    # Gate — if recording is mostly silence don't bother sending to Whisper
    if len(recording) == 0:
        return ""
    rms = np.sqrt(np.mean(recording.astype(np.float32) ** 2))
    if rms < 300:
        print(f"Skipped silent recording (RMS: {rms:.0f})")
        return ""

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, recording, SAMPLE_RATE)
        tmp_path = f.name
    try:
        with open(tmp_path, "rb") as audio_file:
            transcription = groq_client.audio.transcriptions.create(
                model="whisper-large-v3-turbo",
                file=audio_file,
                response_format="text"
            )
        return transcription.strip() if transcription else ""
    except Exception as e:
        print(f"Groq transcription error: {e}")
        return ""
    finally:
        try:
            os.remove(tmp_path)
        except:
            pass

def record_command():
    print("Listening for your command...")
    set_ui_state(status="listening")

    CHUNK_SIZE = 480          # 30ms at 16000hz
    SILENCE_THRESHOLD = 800   # RMS — raised to ignore keyboard clicks
    SILENCE_DURATION = 1.5    # seconds of silence to stop
    MAX_DURATION = 30         # max seconds to listen

    frames = []
    silent_chunks = 0
    voiced_chunks = 0
    max_chunks = int(MAX_DURATION * SAMPLE_RATE / CHUNK_SIZE)
    silence_chunks_needed = int(SILENCE_DURATION * SAMPLE_RATE / CHUNK_SIZE)

    with sd.RawInputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16', blocksize=CHUNK_SIZE) as stream:
        while len(frames) < max_chunks:
            data, _ = stream.read(CHUNK_SIZE)
            chunk = np.frombuffer(data, dtype=np.int16)
            frames.append(chunk)

            # RMS volume check
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))

            if rms > SILENCE_THRESHOLD:
                voiced_chunks += 1
                silent_chunks = 0
            else:
                silent_chunks += 1

            # Require sustained speech before stopping — ignores brief clicks
            if voiced_chunks > 20 and silent_chunks >= silence_chunks_needed:
                break

    audio = np.concatenate(frames) if frames else np.array([], dtype=np.int16)
    return audio

def handle_interaction():
    global greeted, cypher_active, cypher_stopped
    with interaction_lock:
        if cypher_active:
            return
        cypher_active = True
    cypher_stopped = False
    try:
        cleanup_audio_files()
        if not greeted:
            print("Cypher thinking...")
            set_ui_state(status="thinking")
            greeting = greet_nine()
            speak(greeting)
            greeted = True
        follow_up_deadline = time.time() + 30
        while time.time() < follow_up_deadline:
            if cypher_stopped:
                print("Cypher session cut off.")
                set_ui_state(status="standby")
                break
            if cypher_muted:
                print("Cypher muted — ending session.")
                set_ui_state(status="muted")
                break
            recording = record_command()
            command = transcribe_command(recording)
            if command and len(command) > 2:
                if is_hallucination(command):
                    print(f"Ignored noise: {command}")
                    continue
                print(f"You said: {command}")
                set_ui_state(user_text=command)
                if cypher_muted:
                    print("Muted mid-command. Discarding.")
                    set_ui_state(status="muted")
                    break
                if is_exit_phrase(command):
                    speak("Of course. Standing by.")
                    print("Cypher standing by...")
                    set_ui_state(status="standby")
                    break
                action_response = handle_command(command)
                if action_response:
                    speak(action_response)
                else:
                    print("Cypher thinking...")
                    set_ui_state(status="thinking")
                    response = ask_cypher(command)
                    speak(response)
                follow_up_deadline = time.time() + 30
        print("Cypher standing by...")
        set_ui_state(status="standby")
    finally:
        cypher_active = False

# ─── STREAM DECK HOTKEYS ───
def on_activate_hotkey():
    global last_detected, cypher_active
    if not cypher_active and not cypher_muted:
        print("\n✅ Cypher activated via Stream Deck!")
        last_detected = time.time()
        threading.Thread(target=handle_interaction, daemon=True).start()
    elif cypher_muted:
        print("Cypher is muted. Unmute first.")
    else:
        print("Cypher is already active.")

def on_stop_hotkey():
    global cypher_stopped
    print("\n🔴 Cypher cut off via Stream Deck.")
    cypher_stopped = True
    sd.stop()

def on_mute_hotkey():
    global cypher_muted, cypher_stopped
    cypher_muted = not cypher_muted
    if cypher_muted:
        cypher_stopped = True
        sd.stop()
        set_ui_state(status="muted")
        print("\n🔇 Cypher muted — session ended.")
    else:
        cypher_stopped = False
        set_ui_state(status="standby")
        print("\n🔊 Cypher unmuted.")

def on_restart_hotkey():
    print("\n🔄 Restarting Cypher...")
    sd.stop()
    os.execv(sys.executable, [sys.executable] + sys.argv)

def on_kill_hotkey():
    print("\n🛑 Cypher shutting down.")
    sd.stop()
    cleanup_audio_files()
    os.kill(os.getpid(), 9)

keyboard.add_hotkey("ctrl+shift+space", on_activate_hotkey)
keyboard.add_hotkey("ctrl+shift+F4", on_stop_hotkey)
keyboard.add_hotkey("ctrl+shift+m", on_mute_hotkey)
keyboard.add_hotkey("ctrl+shift+r", on_restart_hotkey)
keyboard.add_hotkey("ctrl+shift+q", on_kill_hotkey)

print("Stream Deck hotkeys registered:")
print("  ctrl+shift+space → Activate Cypher")
print("  ctrl+shift+F4    → Cut off Cypher")
print("  ctrl+shift+m     → Mute / Unmute Cypher")
print("  ctrl+shift+r     → Restart Cypher")
print("  ctrl+shift+q     → Kill Cypher")

print("Cypher is online... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 15

# Cooldown
last_detected = 0
COOLDOWN = 10

def audio_callback(indata, frames, time_info, status):
    global last_detected, cypher_active
    if cypher_active or cypher_muted:
        return
    audio_data = np.frombuffer(indata, dtype=np.int16)
    owwModel.predict(audio_data)
    for mdl in owwModel.prediction_buffer.keys():
        scores = list(owwModel.prediction_buffer[mdl])
        if scores[-1] > 0.85:
            current_time = time.time()
            if current_time - last_detected > COOLDOWN:
                last_detected = current_time
                print("\n✅ Cypher activated!")
                threading.Thread(target=handle_interaction, daemon=True).start()

with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype='int16',
    blocksize=CHUNK,
    callback=audio_callback
):
    print("Cypher standing by...")
    while True:
        sd.sleep(1000)
