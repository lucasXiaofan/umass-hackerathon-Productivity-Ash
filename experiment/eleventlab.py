from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from elevenlabs.play import play
import os

client = ElevenLabs(
    api_key="sk_a43a9c7a56739576655d5e373b5ca360453306d943cee40b"
)

text_to_speak = "Hello! This is a simple test of the ElevenLabs API."
voice_id = "JBFqnCBsd6RMkjVDRZzb" # This is a public voice ID from their docs

print("Connecting to ElevenLabs and generating audio...")

audio = client.text_to_speech.convert(
    text=text_to_speak,
    voice_id=voice_id
)

print("Playing audio...")
play(audio)
print("Done.")