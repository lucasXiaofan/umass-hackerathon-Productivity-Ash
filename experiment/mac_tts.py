from mlx_audio.tts.generate import generate_audio

# Example: Generate an audiobook chapter as mp3 audio
voice = "af_heart" #af_bella, af_heart, bf_emma, af_nova
generate_audio(
    text=("""Right now, Future You is watching. Give them something to be grateful for. 
          Do just 30 minutes of anything real. """),
    model_path="prince-canuma/Kokoro-82M",
    voice=voice,
    speed=1.1,
    lang_code="a", # Kokoro: (a)f_heart, or comment out for auto
    file_prefix=f"audiobook_chapter1_{voice}",
    audio_format="wav",
    sample_rate=24000,
    join_audio=True,
    verbose=True  # Set to False to disable print messages
)

print("Audiobook chapter successfully generated!")
