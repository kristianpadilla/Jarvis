import sounddevice as sd
import soundfile as sf
import os
import time
import numpy as np

# Settings
SAMPLE_RATE = 16000
DURATION = 2
NUM_RECORDINGS = 200
OUTPUT_FOLDER = "wake_word_samples"

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

print("=" * 50)
print("Cypher Wake Word Training — Recording Session")
print("=" * 50)
print(f"\nWe need {NUM_RECORDINGS} recordings of you saying 'Hey Cypher'")
print("Tips:")
print("  - Say it naturally, how you actually would")
print("  - Vary your speed slightly each time")
print("  - Some closer to mic, some slightly further")
print("  - Stay in your normal gaming position")
print("\nPress Enter when you are ready to start...")
input()

recorded = 0
skipped = 0

while recorded < NUM_RECORDINGS:
    remaining = NUM_RECORDINGS - recorded
    print(f"\n[{recorded + 1}/{NUM_RECORDINGS}] Get ready... saying in 2 seconds")
    time.sleep(1)
    print("🎙️  Say 'Hey Cypher' NOW!")

    # Record
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()

    # Check if audio has enough energy to be a real recording
    audio_np = np.frombuffer(audio, dtype=np.int16)
    energy = np.sqrt(np.mean(audio_np.astype(np.float32) ** 2))

    if energy < 100:
        print("⚠️  Too quiet, skipping that one...")
        skipped += 1
        continue

    # Save recording
    filename = f"{OUTPUT_FOLDER}/hey_cypher_{recorded + 1:03d}.wav"
    sf.write(filename, audio, SAMPLE_RATE)
    print(f"✅ Saved!")
    recorded += 1

    # Short break every 50 recordings
    if recorded % 50 == 0 and recorded < NUM_RECORDINGS:
        print(f"\n--- Take a 30 second break! {recorded}/{NUM_RECORDINGS} done ---")
        time.sleep(30)

print(f"\n{'=' * 50}")
print(f"Recording complete!")
print(f"Saved: {recorded} clips")
print(f"Skipped: {skipped} clips")
print(f"Files saved to: {OUTPUT_FOLDER}/")
print("=" * 50)
print("\nNow run the training script to build your wake word model!")import sounddevice as sd
import soundfile as sf
import os
import time
import numpy as np

# Settings
SAMPLE_RATE = 16000
DURATION = 2
NUM_RECORDINGS = 200
OUTPUT_FOLDER = "wake_word_samples"

# Create output folder
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

print("=" * 50)
print("Cypher Wake Word Training — Recording Session")
print("=" * 50)
print(f"\nWe need {NUM_RECORDINGS} recordings of you saying 'Hey Cypher'")
print("Tips:")
print("  - Say it naturally, how you actually would")
print("  - Vary your speed slightly each time")
print("  - Some closer to mic, some slightly further")
print("  - Stay in your normal gaming position")
print("\nPress Enter when you are ready to start...")
input()

recorded = 0
skipped = 0

while recorded < NUM_RECORDINGS:
    remaining = NUM_RECORDINGS - recorded
    print(f"\n[{recorded + 1}/{NUM_RECORDINGS}] Get ready... saying in 2 seconds")
    time.sleep(1)
    print("🎙️  Say 'Hey Cypher' NOW!")

    # Record
    audio = sd.rec(
        int(DURATION * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=1,
        dtype='int16'
    )
    sd.wait()

    # Check if audio has enough energy to be a real recording
    audio_np = np.frombuffer(audio, dtype=np.int16)
    energy = np.sqrt(np.mean(audio_np.astype(np.float32) ** 2))

    if energy < 100:
        print("⚠️  Too quiet, skipping that one...")
        skipped += 1
        continue

    # Save recording
    filename = f"{OUTPUT_FOLDER}/hey_cypher_{recorded + 1:03d}.wav"
    sf.write(filename, audio, SAMPLE_RATE)
    print(f"✅ Saved!")
    recorded += 1

    # Short break every 50 recordings
    if recorded % 50 == 0 and recorded < NUM_RECORDINGS:
        print(f"\n--- Take a 30 second break! {recorded}/{NUM_RECORDINGS} done ---")
        time.sleep(30)

print(f"\n{'=' * 50}")
print(f"Recording complete!")
print(f"Saved: {recorded} clips")
print(f"Skipped: {skipped} clips")
print(f"Files saved to: {OUTPUT_FOLDER}/")
print("=" * 50)
print("\nNow run the training script to build your wake word model!")