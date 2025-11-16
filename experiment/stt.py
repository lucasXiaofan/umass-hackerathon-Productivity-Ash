import whisper
import sounddevice as sd
import numpy as np
from pynput import keyboard
from scipy.io import wavfile
import tempfile
import os

# Configuration
SAMPLE_RATE = 16000  # Whisper expects 16kHz
SHORTCUT = {keyboard.Key.cmd_r, keyboard.Key.ctrl}  # Right CMD + CTRL

# Load Whisper model
print("Loading Whisper model...")
model = whisper.load_model("small")
print("Model loaded! Press Right CMD + CTRL to start recording.")

# Recording state
recording = False
audio_data = []
current_keys = set()

def on_press(key):
    global recording, audio_data, current_keys
    
    current_keys.add(key)
    
    # Check if shortcut is pressed
    if SHORTCUT.issubset(current_keys) and not recording:
        recording = True
        audio_data = []
        print("\n🎤 Recording... (release keys to stop)")

def on_release(key):
    global recording, audio_data, current_keys
    
    try:
        current_keys.remove(key)
    except KeyError:
        pass
    
    # Stop recording when any key is released during recording
    if recording and not SHORTCUT.issubset(current_keys):
        recording = False
        print("⏹️  Stopped recording. Transcribing...")
        
        if len(audio_data) > 0:
            transcribe_audio()

def audio_callback(indata, frames, time, status):
    if recording:
        audio_data.append(indata.copy())

def transcribe_audio():
    global audio_data
    
    # Convert to numpy array
    audio = np.concatenate(audio_data, axis=0)
    audio = audio.flatten()
    
    # Save to temporary file
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_file:
        temp_filename = temp_file.name
        wavfile.write(temp_filename, SAMPLE_RATE, (audio * 32767).astype(np.int16))
    
    try:
        # Transcribe - auto-detect language or use "zh" for Chinese
        # task="transcribe" keeps original language (don't translate to English)
        result = model.transcribe(temp_filename, language=None, task="transcribe", fp16=False)
        
        # Print result
        print("\n📝 Transcription:")
        print(result["text"])
        print("\n" + "="*50)
        
    finally:
        # Clean up temp file
        os.unlink(temp_filename)

# Start audio stream
with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, callback=audio_callback):
    # Start keyboard listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        listener.join()