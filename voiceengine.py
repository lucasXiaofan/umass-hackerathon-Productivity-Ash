import requests
import os
import threading
from pathlib import Path
from datetime import datetime

# Configuration
ELEVENLABS_API_KEY = 'sk_a43a9c7a56739576655d5e373b5ca360453306d943cee40b'
VOICE_1_ID = 'kVBPcEMsUF1nsAO1oNWw'  # Replace with your first voice ID
VOICE_2_ID = 'XJ2fW4ybq7HouelYYGcL'  # Replace with your second voice ID

# Default voice selection
DEFAULT_VOICE_ID = VOICE_2_ID


def clean_text_for_speech(text):
    """Remove markdown formatting and clean text for speech"""
    import re
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    # Remove markdown bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # Remove markdown links
    text = re.sub(r'\[([^\]]+)\]\([^\)]+\)', r'\1', text)
    # Remove code blocks
    text = re.sub(r'```[^`]*```', '', text)
    text = re.sub(r'`([^`]+)`', r'\1', text)
    # Remove emojis and special formatting
    text = re.sub(r'[📄🕐⚙️💾📎✅❌💬🎯📚💡🎭🔊🎤🎨]', '', text)
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    return text


def text_to_speech(text, voice_id=None, output_file=None):
    """Convert text to speech using ElevenLabs API"""
    if voice_id is None:
        voice_id = DEFAULT_VOICE_ID
    
    if output_file is None:
        # Create audio directory if it doesn't exist
        audio_dir = Path("audio_outputs")
        audio_dir.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = audio_dir / f"speech_{timestamp}.mp3"
    
    # Clean text for better speech
    cleaned_text = clean_text_for_speech(text)
    
    # Limit text length to avoid API issues (ElevenLabs has limits)
    if len(cleaned_text) > 5000:
        cleaned_text = cleaned_text[:5000] + "..."
    
    if not cleaned_text.strip():
        return None
    
    url = f'https://api.elevenlabs.io/v1/text-to-speech/{voice_id}'
    
    headers = {
        'Accept': 'audio/mpeg',
        'Content-Type': 'application/json',
        'xi-api-key': ELEVENLABS_API_KEY
    }
    
    data = {
        'text': cleaned_text,
        'model_id': 'eleven_v3',
        'voice_settings': {
            'stability': 0.5,
            'similarity_boost': 0.5
        }
    }
    
    try:
        response = requests.post(url, json=data, headers=headers)
        
        if response.status_code != 200:
            raise Exception(f'ElevenLabs API error: {response.status_code} - {response.text}')
        
        # Save the audio file
        output_path = str(output_file)
        with open(output_path, 'wb') as f:
            f.write(response.content)
        
        print(f'Audio saved to {output_path}')
        return output_path
    except Exception as e:
        print(f'Error generating speech: {e}')
        return None


def play_audio(file_path):
    """Play audio file using macOS afplay command (non-blocking)"""
    if file_path and os.path.exists(file_path):
        # Play in background thread to avoid blocking
        def play():
            os.system(f'afplay "{file_path}"')
        threading.Thread(target=play, daemon=True).start()


def generate_speech_for_text(text, voice_id=None, auto_play=False):
    """
    Generate speech from text and optionally play it
    
    Args:
        text: Text to convert to speech
        voice_id: Voice ID to use (defaults to DEFAULT_VOICE_ID)
        auto_play: Whether to automatically play the audio
    
    Returns:
        Path to audio file or None if failed
    """
    audio_file = text_to_speech(text, voice_id)
    
    if audio_file and auto_play:
        play_audio(audio_file)
    
    return audio_file

