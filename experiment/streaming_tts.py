import os
from openai import OpenAI
from dotenv import load_dotenv
import sounddevice as sd
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model

# Load environment variables and configure client
load_dotenv()
# model_name = "minimax/minimax-m2:free"
model_name = "deepseek/deepseek-chat-v3"
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

voice = "af_heart"

# Load TTS model
model_id = 'prince-canuma/Kokoro-82M'
tts_model = load_model(model_id)
pipeline = KokoroPipeline(lang_code='a', model=tts_model, repo_id=model_id)

# Streaming text from OpenAI and converting to audio
stream = client.chat.completions.create(
    model=model_name,
    messages=[{"role": "user", "content": "Tell me a short story about league of legend"}],
    stream=True
)

text_buffer = ""
for chunk in stream:
    if chunk.choices[0].delta.content:
        text_chunk = chunk.choices[0].delta.content
        text_buffer += text_chunk

        # Convert accumulated text to speech when we have enough (e.g., sentence end)
        if any(punct in text_chunk for punct in ['.', '!', '?', '\n']):
            print(f"Speaking: {text_buffer.strip()}")

            # Generate and play audio directly without saving
            for _, _, audio in pipeline(text_buffer.strip(), voice=voice, speed=1):
                # Play audio chunk directly (audio is numpy array)
                sd.play(audio[0], samplerate=24000)
                sd.wait()  # Wait for playback to finish

            text_buffer = ""  # Clear buffer after speaking

# Handle any remaining text``
if text_buffer.strip():
    print(f"Speaking: {text_buffer.strip()}")
    for _, _, audio in pipeline(text_buffer.strip(), voice=voice, speed=1):
        sd.play(audio[0], samplerate=24000)
        sd.wait()
