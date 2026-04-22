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

def get_current_time():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%I:%M %p")

def get_current_date():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%A, %B %d").replace(" 0", " ")

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
- When asked to open an app or website just confirm you are doing it, do not dramatize it
- Never use the degrees symbol, always write the word degrees instead
- Never use ordinal suffixes like 1st, 2nd, 3rd, 22nd in dates, just use the plain number
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
        # Always clean up files no matter what
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
    greeting_prompt = f"Give a brief, sharp and natural greeting to Nine. Include the time which is {get_current_time()} Eastern Standard Time, todays date which is {get_current_date()}, and the weather which is {get_weather()}. End by asking how you can help. Be direct and natural, no theatrics. Do not use ordinal suffixes in the date, just plain numbers."

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
        # Clean up any leftover files from previous runs
        cleanup_audio_files()

        if not greeted:
            print("Jarvis thinking...")
            greeting = greet_nine()
            speak(greeting)
            greeted = True

        # Keep listening for follow up commands for 30 seconds
        follow_up_deadline = time.time() + 30

        while time.time() < follow_up_deadline:
            recording = record_command()
            command = transcribe_command(recording)

            if command and len(command) > 2:
                print(f"You said: {command}")
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

    # Hard block — don't even process audio if Jarvis is active
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