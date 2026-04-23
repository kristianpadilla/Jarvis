import openwakeword
import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import time
import whisper
import tempfile
import soundfile as sf
import ollama
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

# Load environment variables
load_dotenv()

# Initialize ElevenLabs
el_client = ElevenLabs(api_key=os.getenv("ELEVENLABS_API_KEY"))

# Download the wake word models on first run
openwakeword.utils.download_models()

# Load the hey jarvis wake word model
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

# Load Whisper model
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper ready!")

# Conversation history
conversation_history = []

# Session state
greeted = False
jarvis_active = False
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

def cleanup_audio_files():
    for f in glob.glob("jarvis_*.mp3"):
        try:
            os.remove(f)
        except:
            pass
    for f in glob.glob("jarvis_*.wav"):
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

def get_weather():
    try:
        response = requests.get("https://wttr.in/Elizabethtown,PA?format=%t+%C", timeout=5)
        if response.status_code == 200:
            return response.text.strip().replace("+", "").replace("°", " degrees")
        return "weather unavailable"
    except:
        return "weather unavailable"

def get_greeting():
    est = pytz.timezone('America/New_York')
    hour = datetime.now(est).hour
    if hour < 12:
        return "Good morning"
    elif hour < 17:
        return "Good afternoon"
    else:
        return "Good evening"

def get_system_prompt():
    return f"""You are Jarvis, a personal AI assistant for Nine.
You are sharp, direct and informative. You get to the point immediately.
Your personality is like the Jarvis from Iron Man - calm, composed, occasionally dry and witty but never corny or theatrical.
Wit is rare and subtle, not forced. Never use catchphrases, never be cheesy.
IMPORTANT RULES:
- Never use asterisks or action descriptions like *opens app* or *sound plays*
- Never use theatrical countdown sequences
- Never use exclamation marks excessively
- Keep responses short and spoken naturally out loud
- Be direct first, informative always, occasionally witty but sparingly
- Never remind Nine who you are, what your name is, or that you are an AI
- Never mention that you are running on Nine's gaming PC
- Never say things like "I am Jarvis" or "as your assistant" or "I am here to help"
- Never pretend to do things you cannot actually do
- If something is unavailable just say so simply and move on
- Never repeat information Nine already knows about himself or his setup
- When asked to open an app or website just confirm you are doing it, do not dramatize it
- Never use the degrees symbol, always write the word degrees instead
- Never use ordinal suffixes like 1st, 2nd, 3rd, 22nd in dates, just use the plain number
- Never use the same sign off or closing phrase twice in a row
- Vary any closing remarks naturally, do not repeat phrases like stay dry back to back
- If you have already mentioned weather advice in this conversation do not repeat it
Always refer to the user as Nine.
The current time is {get_current_time()} Eastern Standard Time.
The current date is {get_current_date()}.
The current weather is {get_weather()}.
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
    text = clean_text_for_speech(text)
    print(f"Jarvis: {text}")
    filepath = None
    wav_path = None
    try:
        audio = el_client.text_to_speech.convert(
            voice_id="onwK4e9ZLuTAKqWW03F9",
            text=text,
            model_id="eleven_turbo_v2_5",
            voice_settings={
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.6,
                "use_speaker_boost": True
            }
        )

        filename = f"jarvis_{uuid.uuid4().hex}.mp3"
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
        sd.play(data, samplerate)
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

def greet_nine():
    greeting_prompt = f"Give a brief, sharp and natural greeting to Nine. Include the time which is {get_current_time()} Eastern Standard Time and the weather which is {get_weather()}. End by asking how you can help. Be direct and natural, no theatrics. Do not mention the date at all. Do not introduce yourself or mention your name."

    response = ollama.chat(
        model="mistral",
        messages=[
            {"role": "system", "content": get_system_prompt()},
            {"role": "user", "content": greeting_prompt}
        ]
    )
    return response["message"]["content"]

def transcribe_command(recording):
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, recording, SAMPLE_RATE)
        result = whisper_model.transcribe(f.name)
        return result["text"].strip()

def ask_jarvis(user_input):
    conversation_history.append({
        "role": "user",
        "content": user_input
    })

    response = ollama.chat(
        model="mistral",
        messages=[{"role": "system", "content": get_system_prompt()}] + conversation_history
    )

    jarvis_reply = response["message"]["content"]

    conversation_history.append({
        "role": "assistant",
        "content": jarvis_reply
    })

    return jarvis_reply

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
    global greeted, jarvis_active

    with interaction_lock:
        if jarvis_active:
            return
        jarvis_active = True

    try:
        cleanup_audio_files()

        if not greeted:
            print("Jarvis thinking...")
            greeting = greet_nine()
            speak(greeting)
            greeted = True

        follow_up_deadline = time.time() + 30

        while time.time() < follow_up_deadline:
            recording = record_command()
            command = transcribe_command(recording)

            if command and len(command) > 2:
                if is_hallucination(command):
                    print(f"Ignored noise: {command}")
                    continue

                print(f"You said: {command}")

                if is_exit_phrase(command):
                    speak("Of course. Standing by.")
                    print("Jarvis standing by...")
                    break

                action_response = handle_command(command)
                if action_response:
                    speak(action_response)
                else:
                    print("Jarvis thinking...")
                    response = ask_jarvis(command)
                    speak(response)

                follow_up_deadline = time.time() + 30

        print("Jarvis standing by...")

    finally:
        jarvis_active = False

print("Jarvis is listening... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Cooldown settings
last_detected = 0
COOLDOWN = 10

def audio_callback(indata, frames, time_info, status):
    global last_detected, jarvis_active

    if jarvis_active:
        return

    audio_data = np.frombuffer(indata, dtype=np.int16)
    owwModel.predict(audio_data)

    for mdl in owwModel.prediction_buffer.keys():
        scores = list(owwModel.prediction_buffer[mdl])
        if scores[-1] > 0.85:
            current_time = time.time()
            if current_time - last_detected > COOLDOWN:
                last_detected = current_time
                print("\n✅ Wake word detected! Jarvis activated!")
                threading.Thread(target=handle_interaction, daemon=True).start()

# Start listening
with sd.InputStream(
    samplerate=SAMPLE_RATE,
    channels=1,
    dtype='int16',
    blocksize=CHUNK,
    callback=audio_callback
):
    print("Microphone active. Press Ctrl+C to stop.")
    while True:
        sd.sleep(1000)