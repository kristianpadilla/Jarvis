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
import dateparser
from cypher_ui import start_ui, set_ui_state

load_dotenv()

# User home directory — set CYPHER_USER_HOME in .env to your Windows username path
USER_HOME = os.getenv('CYPHER_USER_HOME', r'C:\Users\krist')

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

# ─── SESSION LOG ─────────────────────────────────────────────────────────────
def log_session(text):
    """Post an entry to the UI session log widget."""
    try:
        requests.post("http://localhost:5000/session-log/add",
                      json={"text": text}, timeout=2)
    except:
        pass

# ─── FILE MANAGER ─────────────────────────────────────────────────────────────

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
    for team in FAVORITE_TEAMS:
        for kw in team["keywords"]:
            if kw in command_lower:
                score = get_live_score(command_lower)
                if score:
                    return score
                return f"No game data found for the {team['name']} today."
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
        "gaming", "home", "back", "grab", "pull", "give", "any", "ignore",
        "add", "schedule", "remind", "delete", "cancel", "timer",
        "one", "two", "three", "four", "five", "six", "seven", "eight",
        "nine", "ten", "fifteen", "twenty", "thirty", "forty", "fifty",
        "sixty", "ninety", "minute", "minutes", "hour", "hours", "second", "seconds",
        "count", "countdown", "goal", "goals", "clear", "mark", "complete",
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

URI_APPS = {
    "spotify":  "spotify:",
    "claude":   "claude:",
    "discord":  "discord:",
}

def open_app(app_name):
    app_name_lower = app_name.lower()
    for key in APPS:
        if key in app_name_lower:
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

# ─── TIMER HELPERS ───────────────────────────────────────────────────────────
WORD_TO_NUM = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5,
    'six': 6, 'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10,
    'eleven': 11, 'twelve': 12, 'thirteen': 13, 'fourteen': 14, 'fifteen': 15,
    'sixteen': 16, 'seventeen': 17, 'eighteen': 18, 'nineteen': 19, 'twenty': 20,
    'twenty-one': 21, 'twenty one': 21, 'twenty-two': 22, 'twenty two': 22,
    'twenty-three': 23, 'twenty three': 23, 'twenty-four': 24, 'twenty four': 24,
    'twenty-five': 25, 'twenty five': 25, 'twenty-six': 26, 'twenty six': 26,
    'twenty-seven': 27, 'twenty seven': 27, 'twenty-eight': 28, 'twenty eight': 28,
    'twenty-nine': 29, 'twenty nine': 29, 'thirty': 30, 'forty': 40, 'forty-five': 45,
    'forty five': 45, 'fifty': 50, 'sixty': 60, 'ninety': 90, 'a': 1, 'an': 1,
}

def words_to_digits(text):
    result = text
    for word, num in sorted(WORD_TO_NUM.items(), key=lambda x: len(x[0]), reverse=True):
        result = re.sub(r'\b' + word + r'\b', str(num), result)
    return result

def parse_timer_seconds(command_lower):
    normalized = words_to_digits(command_lower)
    patterns = [
        r'timer\s+for\s+(\d+)\s*(hour|hr|minute|min|second|sec)s?',
        r'(\d+)\s*(hour|hr|minute|min|second|sec)s?\s+timer',
        r'remind\s+me\s+in\s+(\d+)\s*(hour|hr|minute|min|second|sec)s?',
        r'(\d+)\s*(hour|hr|minute|min|second|sec)s?\s+(?:from\s+now|countdown)',
        r'set\s+(?:a\s+)?(\d+)\s*(hour|hr|minute|min|second|sec)s?',
        r'for\s+(\d+)\s*(hour|hr|minute|min|second|sec)s?',
        r'(\d+)\s*(hour|hr|minute|min|second|sec)s?',
    ]
    for pattern in patterns:
        m = re.search(pattern, normalized)
        if m:
            amount = int(m.group(1))
            unit = m.group(2).lower()
            if unit in ('hour', 'hr'):
                return amount * 3600
            elif unit in ('minute', 'min'):
                return amount * 60
            else:
                return amount
    return None

def format_timer_label(seconds):
    if seconds >= 3600:
        h = seconds // 3600
        return f"{h} HOUR TIMER"
    elif seconds >= 60:
        m = seconds // 60
        return f"{m} MINUTE TIMER"
    else:
        return f"{seconds} SECOND TIMER"

def trigger_ui_timer(seconds, label):
    try:
        requests.post("http://localhost:5000/timer/set",
                      json={"seconds": seconds, "label": label}, timeout=3)
    except Exception as e:
        print(f"Timer UI error: {e}")

def reset_ui_timer():
    try:
        requests.post("http://localhost:5000/timer/reset", timeout=3)
    except Exception as e:
        print(f"Timer reset error: {e}")

# ─── CALENDAR HELPERS ─────────────────────────────────────────────────────────
def parse_calendar_add(command_lower):
    try:
        est = pytz.timezone('America/New_York')
        now = datetime.now(est)
        trigger_words = [
            'can you', 'could you', 'please', 'i want to', 'i need to', 'i would like to',
            'on my calendar', 'to my calendar', 'on the calendar', 'to the calendar',
            'remind me about', 'set up', 'create', 'add to', 'put on',
            'add a', 'add an', 'add the', 'add',
            'schedule a', 'schedule an', 'schedule the', 'schedule',
            'book a', 'book an', 'book the', 'book',
            'put a', 'put an', 'put the', 'put',
        ]
        clean = command_lower
        for t in sorted(trigger_words, key=len, reverse=True):
            clean = clean.replace(t, ' ')
        clean = ' '.join(clean.split()).strip()
        time_str = "09:00"
        time_match = re.search(r'at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)?)', clean)
        if time_match:
            time_raw = time_match.group(1).strip()
            if not re.search(r'am|pm', time_raw):
                hour = int(re.match(r'(\d{1,2})', time_raw).group(1))
                if hour <= 8:
                    time_raw = time_raw + ' pm'
            parsed_time = dateparser.parse(time_raw)
            if parsed_time:
                time_str = parsed_time.strftime("%H:%M")
            clean = clean.replace(time_match.group(0), ' ')
        date_str = f"{now.month}/{now.day}/{now.year}"
        day_match = re.search(
            r'(tomorrow|today|monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
            r'next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|week)|'
            r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}|'
            r'\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
            clean
        )
        if day_match:
            parsed_date = dateparser.parse(day_match.group(0), settings={
                'PREFER_DATES_FROM': 'future',
                'RETURN_AS_TIMEZONE_AWARE': True,
                'TIMEZONE': 'America/New_York'
            })
            if parsed_date:
                date_str = f"{parsed_date.month}/{parsed_date.day}/{parsed_date.year}"
            clean = clean.replace(day_match.group(0), ' ')
        filler = ['the', 'a', 'an', 'for', 'my', 'me', 'in', 'this',
                  'calendar', 'event', 'appointment', 'reminder', 'am', 'pm',
                  'game', 'match', 'tonight', 'today', 'tomorrow', 'on', 'at']
        title = clean
        for f in filler:
            title = re.sub(r'\b' + f + r'\b', ' ', title)
        title = ' '.join(title.split()).strip().title()
        original = command_lower
        team_titles = {
            'lightning': 'Lightning Game', 'rays': 'Rays Game',
            'magic': 'Magic Game', 'bucs': 'Bucs Game',
            'buccaneers': 'Buccaneers Game', 'ducks': 'Ducks Game',
        }
        for keyword, team_title in team_titles.items():
            if keyword in original:
                title = team_title
                break
        if 'phone interview' in original or 'phone screen' in original:
            title = 'Phone Interview'
        elif 'interview' in original:
            title = 'Interview'
        if len(title) < 2:
            title = "Event"
        return date_str, time_str, title
    except Exception as e:
        print(f"Calendar parse error: {e}")
        return None

CALENDAR_DELETE_TRIGGERS = ["delete", "remove", "cancel the", "clear"]

def add_calendar_event_from_voice(date_str, time_str, title):
    try:
        r = requests.post("http://localhost:5000/calendar/add",
                          json={"date": date_str, "time": time_str, "title": title},
                          timeout=3)
        return r.json().get("status") == "ok"
    except Exception as e:
        print(f"Calendar add error: {e}")
        return False

def delete_calendar_event_from_voice(command_lower):
    try:
        r = requests.get("http://localhost:5000/calendar", timeout=3)
        all_events = r.json().get("events", [])
        if not all_events:
            return "Nothing on the calendar to delete, Nine."
        target_date = None
        try:
            est = pytz.timezone('America/New_York')
            day_match = re.search(
                r'(today|tomorrow|monday|tuesday|wednesday|thursday|friday|saturday|sunday|'
                r'next\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|'
                r'(?:january|february|march|april|may|june|july|august|september|october|november|december)\s+\d{1,2}|'
                r'\d{1,2}/\d{1,2}(?:/\d{2,4})?)',
                command_lower
            )
            if day_match:
                parsed = dateparser.parse(day_match.group(0), settings={
                    'PREFER_DATES_FROM': 'future',
                    'RETURN_AS_TIMEZONE_AWARE': True,
                    'TIMEZONE': 'America/New_York'
                })
                if parsed:
                    target_date = f"{parsed.month}/{parsed.day}/{parsed.year}"
        except:
            pass
        if target_date:
            filtered = [(i, e) for i, e in enumerate(all_events) if e.get('date') == target_date]
            if not filtered:
                return f"No events found on {target_date}, Nine."
        else:
            est = pytz.timezone('America/New_York')
            today_dt = datetime.now(est)
            today = f"{today_dt.month}/{today_dt.day}/{today_dt.year}"
            filtered = [(i, e) for i, e in enumerate(all_events) if e.get('date') == today]
            if not filtered:
                filtered = [(i, e) for i, e in enumerate(all_events)]
        filtered.sort(key=lambda x: x[1].get('time', ''))
        position = 1
        word_nums = {
            'first': 1, 'one': 1, '1': 1,
            'second': 2, 'two': 2, '2': 2,
            'third': 3, 'three': 3, '3': 3,
            'fourth': 4, 'four': 4, '4': 4,
            'fifth': 5, 'five': 5, '5': 5,
        }
        hash_match = re.search(r'#(\d+)', command_lower)
        if hash_match:
            position = int(hash_match.group(1))
        else:
            for word, num in word_nums.items():
                if re.search(r'\b' + word + r'\b', command_lower):
                    position = num
                    break
        if position > len(filtered):
            return f"There are only {len(filtered)} events there, Nine."
        actual_idx, event = filtered[position - 1]
        r = requests.post("http://localhost:5000/calendar/delete",
                          json={"index": actual_idx}, timeout=3)
        if r.json().get("status") == "ok":
            return f"Deleted — {event.get('title')} at {event.get('time')}."
        return "Couldn't delete that, Nine."
    except Exception as e:
        print(f"Calendar delete error: {e}")
        return "Something went wrong with the calendar, Nine."

def get_todays_calendar_events():
    try:
        r = requests.get("http://localhost:5000/calendar/today", timeout=3)
        return r.json().get("events", [])
    except:
        return []

# ─── GOALS & COUNTDOWN HANDLERS ───────────────────────────────────────────────
def handle_goals_command(cmd):
    """Handle all goal-related voice commands. Returns response string or None."""

    # Add a goal — "add a goal: finish the report"
    if re.search(r'add (a )?goal[s]?\s*[:\-]\s*', cmd):
        match = re.search(r'add (a )?goal[s]?\s*[:\-]\s*(.+)', cmd, re.IGNORECASE)
        if match:
            goal_text = match.group(2).strip()
            try:
                r = requests.post("http://localhost:5000/goals/add",
                                  json={"text": goal_text}, timeout=3)
                if r.json().get("status") == "ok":
                    log_session(f"Goal added: {goal_text}")
                    return f"Goal added — {goal_text}."
                else:
                    return "You've already got three goals set for today, Nine. Clear them first."
            except Exception as e:
                return f"Couldn't reach the goal system."

    # Toggle goal done — "mark goal 1 done" / "check off goal 2"
    if re.search(r'(mark|check off|complete|finish|done)\s+goal\s+\d', cmd):
        match = re.search(r'(\d)', cmd)
        if match:
            idx = int(match.group(1)) - 1
            try:
                r = requests.post("http://localhost:5000/goals/toggle",
                                  json={"index": idx}, timeout=3)
                if r.json().get("status") == "ok":
                    log_session(f"Goal {idx+1} toggled")
                    return f"Goal {idx+1} updated."
                else:
                    return f"No goal at position {idx+1}, Nine."
            except:
                return "Couldn't update that goal."

    # Clear goals — "clear my goals" / "reset goals"
    if re.search(r'(clear|reset|wipe|delete)\s+(my\s+)?goals', cmd):
        try:
            requests.post("http://localhost:5000/goals/clear", timeout=3)
            log_session("Daily goals cleared")
            return "Goals cleared. Fresh slate."
        except:
            return "Couldn't clear goals right now."

    # Read goals — "what are my goals"
    if re.search(r'(what|show|list).*(my\s+)?goals', cmd):
        try:
            r = requests.get("http://localhost:5000/goals", timeout=3)
            goals = r.json().get("goals", [])
            if not goals:
                return "No goals set for today. Say 'add a goal' followed by what you want to get done."
            done = sum(1 for g in goals if g["done"])
            lines = []
            for i, g in enumerate(goals):
                status = "done" if g["done"] else "pending"
                lines.append(f"{i+1}. {g['text']} — {status}")
            return f"Goals for today, {done} of {len(goals)} done. " + ". ".join(lines) + "."
        except:
            return "Couldn't pull your goals right now."

    return None

def handle_countdown_command(cmd):
    """Handle countdown voice commands. Returns response string or None."""

    # Add countdown — "count down to graduation on June 15th"
    countdown_match = re.search(
        r'(count down to|countdown to|add a? countdown to)\s+(.+?)\s+on\s+(.+)',
        cmd, re.IGNORECASE
    )
    if not countdown_match:
        countdown_match = re.search(
            r'(count down to|countdown to)\s+(.+?)\s+(january|february|march|april|may|june|'
            r'july|august|september|october|november|december|\d{1,2}/\d{1,2})',
            cmd, re.IGNORECASE
        )
        if countdown_match:
            label    = countdown_match.group(2).strip().title()
            date_str = cmd[countdown_match.start(3):]
        else:
            label = date_str = None
    else:
        label    = countdown_match.group(2).strip().title()
        date_str = countdown_match.group(3).strip()

    if label and date_str:
        parsed_date = dateparser.parse(date_str, settings={"PREFER_DATES_FROM": "future"})
        if parsed_date:
            from datetime import date as _date
            iso_date  = parsed_date.strftime("%Y-%m-%d")
            friendly  = parsed_date.strftime("%B %d, %Y")
            days_left = (_date.fromisoformat(iso_date) - _date.today()).days
            try:
                r = requests.post("http://localhost:5000/countdown/add",
                                  json={"label": label, "date": iso_date}, timeout=3)
                if r.json().get("status") == "ok":
                    log_session(f"Countdown: {label} → {friendly}")
                    return f"Countdown set. {label} is {days_left} days away on {friendly}."
                return "Couldn't add that countdown."
            except:
                return "Countdown system unavailable right now."
        return "Couldn't parse that date, Nine. Try something like 'count down to graduation on June 15'."

    # Delete countdown — "delete countdown 1"
    del_match = re.search(r'(delete|remove|cancel)\s+countdown\s+(\d+)', cmd)
    if del_match:
        idx = int(del_match.group(2)) - 1
        try:
            r = requests.post("http://localhost:5000/countdown/delete",
                              json={"index": idx}, timeout=3)
            if r.json().get("status") == "ok":
                log_session(f"Countdown {idx+1} deleted")
                return f"Countdown {idx+1} removed."
            return f"No countdown at that position."
        except:
            return "Couldn't delete that countdown."

    return None

# ─── COMMAND TRIGGERS ─────────────────────────────────────────────────────────
TIMER_TRIGGERS = ["set a timer", "set timer", "timer for", "start a timer",
                  "remind me in", "countdown", "count down"]
TIMER_CANCEL_TRIGGERS = ["cancel the timer", "stop the timer", "clear the timer",
                          "cancel timer", "stop timer", "reset timer"]
CALENDAR_ADD_TRIGGERS = [
    "add to my calendar", "add to the calendar", "on the calendar",
    "on my calendar", "add a meeting", "add an appointment", "add appointment",
    "schedule a", "schedule an", "put on my calendar", "put it on",
    "add an event", "add event", "schedule meeting", "remind me about",
    "book a", "add a", "add an", "calendar for", "calendar tomorrow",
    "calendar today", "calendar on", "meeting on", "meeting tomorrow",
    "meeting today", "appointment on", "appointment tomorrow",
    "add an interview", "add a phone", "schedule an interview", "schedule a phone",
    "interview on", "interview tomorrow", "interview at", "phone interview",
    "phone screen", "add interview",
    "add the game", "add a game", "magic game", "lightning game", "rays game",
    "bucs game", "ducks game", "watch party", "add the match",
]
CALENDAR_TODAY_TRIGGERS = ["what's on my calendar", "what is on my calendar",
                            "my calendar today", "what do i have today",
                            "what's today's schedule", "any events today",
                            "calendar today", "do i have anything"]
GOALS_TRIGGERS = [
    "add a goal", "add goal", "my goals", "what are my goals",
    "show my goals", "list my goals", "mark goal", "check off goal",
    "complete goal", "finish goal", "done goal", "clear my goals",
    "reset goals", "wipe goals", "delete my goals",
]
COUNTDOWN_TRIGGERS = [
    "count down to", "countdown to", "add a countdown", "add countdown",
    "delete countdown", "remove countdown", "cancel countdown",
]

# ─── MAIN COMMAND HANDLER ─────────────────────────────────────────────────────
def handle_command(command):
    command_lower = command.lower()

    # ── GOALS ──
    if any(t in command_lower for t in GOALS_TRIGGERS):
        result = handle_goals_command(command_lower)
        if result:
            return result

    # ── COUNTDOWN ──
    if any(t in command_lower for t in COUNTDOWN_TRIGGERS):
        result = handle_countdown_command(command_lower)
        if result:
            return result

    # ── MODES ──
    if "gaming mode" in command_lower:
        gaming_mode()
        log_session("Mode → GAMING")
        return "Gaming mode activated. Launching your setup, Nine."

    if "sports mode" in command_lower or "take me to sports" in command_lower:
        set_ui_state(mode="sports")
        log_session("Mode → SPORTS")
        return "Pulling up sports mode."

    if any(p in command_lower for p in ["take me home", "go home", "home mode", "back to home"]):
        set_ui_state(mode="home")
        log_session("Mode → HOME")
        return "Going home."

    # ── TIMER ──
    if any(t in command_lower for t in TIMER_CANCEL_TRIGGERS):
        reset_ui_timer()
        log_session("Timer cancelled")
        return "Timer cleared."

    if any(t in command_lower for t in TIMER_TRIGGERS):
        # Guard: don't treat "count down to X" as timer
        if any(t in command_lower for t in ["count down to", "countdown to"]):
            result = handle_countdown_command(command_lower)
            if result:
                return result
        seconds = parse_timer_seconds(command_lower)
        if seconds and seconds > 0:
            label = format_timer_label(seconds)
            trigger_ui_timer(seconds, label)
            if seconds >= 3600:
                h = seconds // 3600
                duration = f"{h} hour{'s' if h > 1 else ''}"
            elif seconds >= 60:
                m = seconds // 60
                duration = f"{m} minute{'s' if m > 1 else ''}"
            else:
                duration = f"{seconds} second{'s' if seconds > 1 else ''}"
            log_session(f"Timer set — {duration}")
            return f"Timer set for {duration}."
        return "How long do you want the timer for, Nine?"

    # ── CALENDAR ──
    if any(t in command_lower for t in CALENDAR_TODAY_TRIGGERS):
        try:
            r = requests.get("http://localhost:5000/calendar/today", timeout=3)
            events = r.json().get("events", [])
            if not events:
                return "Nothing on the calendar today, Nine."
            lines = [f"{e['time']} — {e['title']}" for e in events]
            if len(lines) == 1:
                return f"You've got one thing today — {lines[0]}."
            return f"You've got {len(lines)} things today — {', '.join(lines)}."
        except:
            return "Couldn't pull the calendar right now."

    CALENDAR_CONTEXT = ["calendar", "meeting", "appointment", "schedule", "event",
                        "reminder", "book", "tomorrow", "friday", "monday", "tuesday",
                        "wednesday", "thursday", "saturday", "sunday", "tonight",
                        "today", "next week", "at noon", "at 9", "at 10", "at 11",
                        "at 12", "pm", "am",
                        "magic", "lightning", "rays", "buccaneers", "bucs", "ducks",
                        "game", "match", "watch party",
                        "interview", "phone interview", "phone screen", "job interview",
                        "technical interview", "screening",
                        ]
    has_calendar_context = any(w in command_lower for w in CALENDAR_CONTEXT)

    if has_calendar_context and any(t in command_lower for t in CALENDAR_ADD_TRIGGERS):
        result = parse_calendar_add(command_lower)
        if result:
            date_str, time_str, title = result
            success = add_calendar_event_from_voice(date_str, time_str, title)
            if success:
                try:
                    t_obj = datetime.strptime(time_str, "%H:%M")
                    spoken_time = t_obj.strftime("%I:%M %p").lstrip("0")
                except:
                    spoken_time = time_str
                log_session(f"Event added: {title} on {date_str}")
                return f"Done. {title} added for {date_str} at {spoken_time}."
            return "Couldn't save that to the calendar, Nine."
        return "Didn't catch the details on that — when and what's the event?"

    # ── CALENDAR DELETE ──
    if any(t in command_lower for t in CALENDAR_DELETE_TRIGGERS):
        return delete_calendar_event_from_voice(command_lower)

    # ── FILE MANAGER ──
    file_response = handle_file_request(command_lower)
    if file_response:
        return file_response

    # ── SPORTS ──
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

    # ── WEATHER ──
    weather_response = get_location_weather(command_lower)
    if weather_response:
        return weather_response

    # ── DISCORD ──
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

    # ── APPS ──
    for app in APPS:
        if app in command_lower and ("open" in command_lower or "launch" in command_lower or "start" in command_lower):
            open_app(app)
            log_session(f"Opened {app}")
            return f"Opening {app}."

    # ── WEBSITES ──
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
    if not text or len(text.strip()) < 3:
        print("Speak skipped — empty text.")
        set_ui_state(status="standby")
        return
    if not any(c.isalpha() for c in text):
        print(f"Speak skipped — no alphabetic content: {text}")
        set_ui_state(status="standby")
        return
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
    web_triggers = [
        "news", "latest", "current", "today", "tonight", "happening",
        "recently", "just", "new", "update", "price", "stock",
        "who won", "what happened", "did they", "release", "announced",
        "trending", "right now", "this week", "this month"
    ]
    use_web = any(t in user_input.lower() for t in web_triggers)
    local_triggers = [
        "weather", "temperature", "score", "game", "rays", "lightning",
        "bucs", "magic", "ducks", "time", "date", "open", "launch",
        "timer", "calendar", "remind",
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
    calendar_line = ""
    try:
        r = requests.get("http://localhost:5000/calendar/today", timeout=3)
        events = r.json().get("events", [])
        if events:
            def fmt_time(t):
                try:
                    return datetime.strptime(t, "%H:%M").strftime("%I:%M %p").lstrip("0")
                except:
                    return t
            if len(events) == 1:
                e = events[0]
                calendar_line = f"You've got {e['title']} at {fmt_time(e['time'])} today."
            else:
                items = ", ".join([f"{e['title']} at {fmt_time(e['time'])}" for e in events])
                calendar_line = f"You've got {len(events)} things today — {items}."
    except:
        pass
    weather_part = f"the weather is {weather}" if weather != "weather unavailable" else ""
    sports_part = sports_line if sports_line else ""
    calendar_part = calendar_line if calendar_line else ""
    context_parts = [p for p in [weather_part, sports_part, calendar_part] if p]
    context_block = ". ".join(context_parts)
    greeting_prompt = (
        f"Give a brief, sharp and natural greeting to Nine. "
        f"Open with a casual cyberpunk acknowledgment — use Night City slang like 'choom', 'you're back', or similar flavor. Just one short natural line before getting into the info. "
        f"Then include the time which is {get_current_time()}. Do not say any timezone label for the local time. "
        f"{context_block}. "
        f"If there is sports info include it naturally and conversationally — do not list it like a schedule, weave it in. If a game is live include the score. If a game is final mention the result. If upcoming mention the time. "
        f"If there is calendar info mention it briefly. "
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
    CHUNK_SIZE = 480
    SILENCE_THRESHOLD = 800
    SILENCE_DURATION = 1.5
    MAX_DURATION = 30
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
            rms = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
            if rms > SILENCE_THRESHOLD:
                voiced_chunks += 1
                silent_chunks = 0
            else:
                silent_chunks += 1
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
                    if len(action_response.strip()) > 2 and any(c.isalpha() for c in action_response):
                        speak(action_response)
                    else:
                        print(f"Skipped bad response: {action_response}")
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

# ─── STREAM DECK HOTKEYS ──────────────────────────────────────────────────────
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

CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 15

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
