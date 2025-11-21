import subprocess

def tts_play(text: str, voice: str = "Zoe (Premium)", rate: int = 180):
    """Play TTS using macOS premium voices"""
    subprocess.run([
        "say", 
        "-v", voice, 
        "-r", str(rate),
        "--quality", "127",  # Highest quality
        text
    ])

# Premium voices (must download first)
tts_play("We can only be said to be alive in those moments when our hearts are conscious of our treasures.", voice="Zoe (Premium)", rate=180)
