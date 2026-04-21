import openwakeword
import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import time
import whisper
import tempfile
import soundfile as sf

# Download the wake word models on first run
openwakeword.utils.download_models()

# Load the hey jarvis wake word model
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

# Load Whisper model
print("Loading Whisper model...")
whisper_model = whisper.load_model("base")
print("Whisper ready!")

print("Jarvis is listening... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000
RECORD_SECONDS = 5

# Cooldown settings
last_detected = 0
COOLDOWN = 10

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

def transcribe_command(recording):
    # Save recording to temp file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, recording, SAMPLE_RATE)
        result = whisper_model.transcribe(f.name)
        return result["text"].strip()

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

                # Record and transcribe command
                recording = record_command()
                command = transcribe_command(recording)
                print(f"You said: {command}")

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