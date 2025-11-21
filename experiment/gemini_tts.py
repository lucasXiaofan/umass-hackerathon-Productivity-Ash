import os
from dotenv import load_dotenv
from google import genai
from google.genai import types
import pyaudio

# Load API key from .env file
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

# Initialize client
client = genai.Client(api_key=api_key)

def tts_stream_play(text: str, voice: str = "Kore"):
    """Stream TTS and play audio in real-time (no file saving)"""
    
    # Initialize PyAudio for playback
    p = pyaudio.PyAudio()
    stream = p.open(
        format=pyaudio.paInt16,  # 16-bit audio
        channels=1,              # Mono
        rate=24000,              # 24kHz sample rate
        output=True
    )
    
    try:
        # Stream audio chunks as they arrive
        for chunk in client.models.generate_content_stream(
            model="gemini-2.5-flash-preview-tts",  # Cheaper option
            # model="gemini-2.5-pro-preview-tts",  # Higher quality, 2x cost
            contents=text,
            config=types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    voice_config=types.VoiceConfig(
                        prebuilt_voice_config=types.PrebuiltVoiceConfig(
                            voice_name=voice
                        )
                    )
                )
            )
        ):
            # Play each chunk immediately
            if (chunk.candidates and 
                chunk.candidates[0].content and 
                chunk.candidates[0].content.parts):
                for part in chunk.candidates[0].content.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        stream.write(part.inline_data.data)
                        
    finally:
        stream.stop_stream()
        stream.close()
        p.terminate()

if __name__ == "__main__":
    # Example usage
    tts_stream_play(
        "Breaking news just in! flow released and user is growing, company start to making profts",
        voice="Achernar"  # Try: Kore, Puck, Charon, Zephyr, Fenrir, etc.
    )