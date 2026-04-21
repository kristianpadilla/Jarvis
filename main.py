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
import httpx
import subprocess

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

def get_current_time():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%I:%M %p")

def get_current_date():
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    return now.strftime("%A, %B %d %Y")

def get_weather():
    try:
        response = requests.get("https://wttr.in/Elizabethtown,PA?format=%t+%C", timeout=5)
        if response.status_code == 200:
            return response.text.strip().replace("+", "")
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
    return f"""You are Jarvis, a personal AI assistant for Kristian.
You are helpful, smart, and have a slightly witty personality like the Jarvis from Iron Man.
Keep responses concise and conversational since they will be spoken out loud.
The current time is {get_current_time()} EST.
The current date is {get_current_date()}.
The current weather is {get_weather()}.
You are running on Kristian's gaming PC."""

def speak(text):
    print(f"Jarvis: {text}")
    try:
        audio = el_client.text_to_speech.convert(
            voice_id="onwK4e9ZLuTAKqWW03F9",
            text=text,
            model_id="eleven_turbo_v2_5"
        )

        # Write mp3 to file
        filename = f"jarvis_{uuid.uuid4().hex}.mp3"
        filepath = os.path.join(os.getcwd(), filename)

        with open(filepath, "wb") as f:
            for chunk in audio:
                f.write(chunk)

        # Convert mp3 to wav using ffmpeg then play with sounddevice
        wav_path = filepath.replace(".mp3", ".wav")
        subprocess.run([
            "ffmpeg", "-y", "-i", filepath,
            "-ar", "22050", "-ac", "1", wav_path
        ], capture_output=True)

        # Play wav with sounddevice
        data, samplerate = sf.read(wav_path)
        sd.play(data, samplerate)
        sd.wait()

        # Clean up
        os.remove(filepath)
        os.remove(wav_path)

    except Exception as e:
        print(f"Voice error: {e}")

def greet_kristian():
    greeting_prompt = f"{get_greeting()} Kristian! Give a friendly intro that includes the current time which is {get_current_time()}, todays date which is {get_current_date()}, and the weather which is {get_weather()}. End with asking how you can assist today. Keep it natural and conversational."

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

print("Jarvis is listening... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Cooldown settings
last_detected = 0
COOLDOWN = 10

def audio_callback(indata, frames, time_info, status):
    global last_detected

    audio_data = np.frombuffer(indata, dtype=np.int16)
    owwModel.predict(audio_data)

    for mdl in owwModel.prediction_buffer.keys():
        scores = list(owwModel.prediction_buffer[mdl])
        if scores[-1] > 0.7:
            current_time = time.time()
            if current_time - last_detected > COOLDOWN:
                last_detected = current_time
                print("\n✅ Wake word detected! Jarvis activated!")

                # Greet Kristian
                print("Jarvis thinking...")
                greeting = greet_kristian()
                speak(greeting)

                # Record and transcribe command
                recording = record_command()
                command = transcribe_command(recording)

                if command:
                    print(f"You said: {command}")
                    print("Jarvis thinking...")
                    response = ask_jarvis(command)
                    speak(response)

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