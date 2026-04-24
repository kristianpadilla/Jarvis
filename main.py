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

# Load environment variables
load_dotenv()

# Initialize ElevenLabs
el_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Initialize Anthropic Claude client
claude = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))

# Initialize Groq client for STT
groq_client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Download the wake word models on first run
openwakeword.utils.download_models()

# Load the hey jarvis wake word model as backup trigger
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

print("Cypher systems online...")

# Conversation history
conversation_history = []

# Session state
greeted = False
cypher_active = False
cypher_stopped = False
cypher_muted = False
interaction_lock = threading.Lock()

# Only block obvious hallucinations not real sentences
HALLUCINATION_PHRASES = [
    "thank you for watching",
    "thanks for watching",
    "please subscribe",
    "like and subscribe",
    "www.",
    "http",
    "subtitles",
    "transcribed",
]

# Named locations for quick weather lookups
NAMED_LOCATIONS = {
    "home": "Marietta,PA",
    "marietta": "Marietta,PA",
    "chiang mai": "Chiang+Mai,Thailand",
    "thailand": "Chiang+Mai,Thailand",
}

# App paths loaded from .env
APPS = {
    "steam": os.getenv("STEAM_PATH"),
    "discord": os.getenv("DISCORD_PATH"),
    "opera": os.getenv("OPERA_PATH"),
    "opera gx": os.getenv("OPERA_PATH"),
}

# Discord voice channel coordinates loaded from .env
DISCORD_VOICE_CHANNELS = {
    "tfm": {
        "name": "Trained Flak Monkeys",
        "folder": (int(os.getenv("TFM_FOLDER_X")), int(os.getenv("TFM_FOLDER_Y"))),
        "server": (int(os.getenv("TFM_SERVER_X")), int(os.getenv("TFM_SERVER_Y"))),
        "channel": (int(os.getenv("TFM_CHANNEL_X")), int(os.getenv("TFM_CHANNEL_Y"))),
        "join_button": (int(os.getenv("TFM_JOIN_X")), int(os.getenv("TFM_JOIN_Y")))
    }
}

# Discord text channel links loaded from .env
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

# All the ways Whisper might mishear Discord
DISCORD_ALIASES = [
    "discord", "this cord", "disk cord", "disc cord",
    "discor", "discard", "this core", "disk core",
    "the cord", "dis cord", "discourt"
]

# Exit phrases that end the conversation
EXIT_PHRASES = [
    "thank you", "thanks", "that's all", "that will be all",
    "goodbye", "bye", "see you", "i'm good", "im good",
    "no thank you", "no thanks", "i'm done", "im done"
]

# ─────────────────────────────────────────────
# SPORTS SCHEDULE
# ─────────────────────────────────────────────

FAVORITE_TEAMS = [
    {"name": "Tampa Bay Rays",       "sport": "mlb",   "search_name": "Tampa Bay Rays"},
    {"name": "Tampa Bay Buccaneers", "sport": "nfl",   "search_name": "Tampa Bay Buccaneers"},
    {"name": "Orlando Magic",        "sport": "nba",   "search_name": "Orlando Magic"},
    {"name": "Tampa Bay Lightning",  "sport": "nhl",   "search_name": "Tampa Bay Lightning"},
    {"name": "Oregon Ducks",         "sport": "ncaaf", "search_name": "Oregon"},
]

SPORT_ENDPOINTS = {
    "mlb":   "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard",
    "nfl":   "https://site.api.espn.com/apis/site/v2/sports/football/nfl/scoreboard",
    "nba":   "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard",
    "nhl":   "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard",
    "ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football/scoreboard",
}

def get_todays_games():
    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    games_today = []

    for team in FAVORITE_TEAMS:
        sport = team["sport"]
        search_name = team["search_name"]
        team_name = team["name"]

        try:
            url = f"{SPORT_ENDPOINTS[sport]}?dates={today}"
            response = requests.get(url, timeout=5)
            if response.status_code != 200:
                continue

            data = response.json()
            events = data.get("events", [])

            for event in events:
                competitors = event.get("competitions", [{}])[0].get("competitors", [])
                team_names_in_game = [c.get("team", {}).get("displayName", "") for c in competitors]

                matched = any(search_name.lower() in name.lower() for name in team_names_in_game)

                if matched:
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
                    for c in competitors:
                        c_name = c.get("team", {}).get("displayName", "")
                        if search_name.lower() not in c_name.lower():
                            opponent = c_name
                        else:
                            home_away = "home" if c.get("homeAway", "") == "home" else "away"

                    games_today.append({
                        "team": team_name,
                        "opponent": opponent,
                        "time": game_time,
                        "home_away": home_away,
                        "sport": sport
                    })

        except Exception as e:
            print(f"Sports API error for {team_name}: {e}")
            continue

    return games_today

def format_sports_for_greeting(games):
    if not games:
        return None

    lines = []
    for game in games:
        team = game["team"]
        opponent = game["opponent"]
        game_time = game["time"]
        home_away = game["home_away"]

        if home_away == "home":
            lines.append(f"the {team} host the {opponent} at {game_time}")
        else:
            lines.append(f"the {team} face the {opponent} at {game_time}")

    if len(lines) == 1:
        return f"On the schedule today — {lines[0]}."
    elif len(lines) == 2:
        return f"On the schedule today — {lines[0]}, and {lines[1]}."
    else:
        joined = ", ".join(lines[:-1]) + f", and {lines[-1]}"
        return f"On the schedule today — {joined}."

# ─────────────────────────────────────────────

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
    return False

def get_current_time():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%I:%M %p")

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

def open_app(app_name):
    app_name_lower = app_name.lower()
    for key in APPS:
        if key in app_name_lower:
            subprocess.Popen([APPS[key]])
            return True
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
    subprocess.Popen([APPS["steam"]])
    time.sleep(2)
    subprocess.Popen([APPS["discord"]])

def handle_command(command):
    command_lower = command.lower()

    if "gaming mode" in command_lower:
        gaming_mode()
        return "Gaming mode activated. Launching your setup, Nine."

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
            "youtube": "https://www.youtube.com",
            "google": "https://www.google.com",
            "twitter": "https://www.twitter.com",
            "reddit": "https://www.reddit.com",
            "netflix": "https://www.netflix.com",
            "twitch": "https://www.twitch.tv",
            "spotify": "https://open.spotify.com",
            "github": "https://www.github.com",
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
    filepath = None
    wav_path = None
    try:
        audio = el_client.text_to_speech.convert(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID"),
            text=text,
            model_id="eleven_multilingual_v2",
            voice_settings={
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.6,
                "use_speaker_boost": True
            }
        )

        filename = f"cypher_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(os.getcwd(), filename)
        wav_path = filepath.replace(".mp3", ".wav")

        with open(filepath, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        subprocess.run([
            "ffmpeg", "-y", "-i", filepath,
            "-filter:a", "atempo=0.96",
            "-ar", "44100", "-ac", "2", wav_path
        ], capture_output=True)

        data, samplerate = sf.read(wav_path)

        if cypher_stopped:
            print("Cypher cut off before playback.")
            return

        sd.play(data, samplerate)

        while sd.get_stream().active:
            if cypher_stopped:
                sd.stop()
                print("Cypher cut off mid-sentence.")
                return
            time.sleep(0.05)

        sd.wait()

    except Exception as e:
        print(f"Voice error: {e}")
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
    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    response = claude.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=300,
        system=get_system_prompt(),
        messages=conversation_history
    )

    cypher_reply = response.content[0].text

    conversation_history.append({
        "role": "assistant",
        "content": cypher_reply
    })

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
        f"If there is sports info include it naturally and conversationally — do not list it like a schedule, weave it in. "
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
    """Transcribe audio using Groq cloud STT — fast and accurate."""
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
    recording = sd.rec(
        int(RECORD_SECONDS * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()
    return recording

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
            greeting = greet_nine()
            speak(greeting)
            greeted = True

        follow_up_deadline = time.time() + 30

        while time.time() < follow_up_deadline:

            if cypher_stopped:
                print("Cypher session cut off.")
                break

            if cypher_muted:
                print("Cypher muted — ending session.")
                break

            recording = record_command()
            command = transcribe_command(recording)

            if command and len(command) > 2:
                if is_hallucination(command):
                    print(f"Ignored noise: {command}")
                    continue

                print(f"You said: {command}")

                if cypher_muted:
                    print("Muted mid-command. Discarding.")
                    break

                if is_exit_phrase(command):
                    speak("Of course. Standing by.")
                    print("Cypher standing by...")
                    break

                action_response = handle_command(command)
                if action_response:
                    speak(action_response)
                else:
                    print("Cypher thinking...")
                    response = ask_cypher(command)
                    speak(response)

                follow_up_deadline = time.time() + 30

        print("Cypher standing by...")

    finally:
        cypher_active = False

# ─────────────────────────────────────────────
# STREAM DECK HOTKEY LISTENERS
# ─────────────────────────────────────────────

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
        print("\n🔇 Cypher muted — session ended.")
    else:
        cypher_stopped = False
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
keyboard.add_hotkey("ctrl+shift+x", on_stop_hotkey)
keyboard.add_hotkey("ctrl+shift+m", on_mute_hotkey)
keyboard.add_hotkey("ctrl+shift+r", on_restart_hotkey)
keyboard.add_hotkey("ctrl+shift+q", on_kill_hotkey)

print("Stream Deck hotkeys registered:")
print("  ctrl+shift+space → Activate Cypher")
print("  ctrl+shift+x     → Cut off Cypher")
print("  ctrl+shift+m     → Mute / Unmute Cypher")
print("  ctrl+shift+r     → Restart Cypher")
print("  ctrl+shift+q     → Kill Cypher")

# ─────────────────────────────────────────────

print("Cypher is online... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 8

# Cooldown settings
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

# Start listening
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