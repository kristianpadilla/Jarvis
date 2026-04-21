import openwakeword
import sounddevice as sd
import numpy as np
from openwakeword.model import Model
import time

# Download the wake word models on first run
openwakeword.utils.download_models()

# Load the hey jarvis wake word model
owwModel = Model(wakeword_models=["hey_jarvis"], inference_framework="onnx")

print("Jarvis is listening... Say 'Hey Jarvis' to activate!")

# Audio settings
CHUNK = 1280
SAMPLE_RATE = 16000

# Cooldown settings
last_detected = 0
COOLDOWN = 3  # seconds between detections

def audio_callback(indata, frames, time_info, status):
    global last_detected
    
    # Convert audio to the right format
    audio_data = np.frombuffer(indata, dtype=np.int16)
    
    # Feed audio to wake word model
    owwModel.predict(audio_data)
    
    # Check if hey jarvis was detected
    for mdl in owwModel.prediction_buffer.keys():
        scores = list(owwModel.prediction_buffer[mdl])
        if scores[-1] > 0.5:
            current_time = time.time()
            if current_time - last_detected > COOLDOWN:
                last_detected = current_time
                print("\n✅ Wake word detected! Jarvis activated!")

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