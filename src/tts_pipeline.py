"""
Two-Thread TTS Pipeline System
================================

This module implements a pipelined TTS system with two worker threads:
1. Audio Generator Thread: Converts text to audio (CPU-intensive)
2. Audio Playback Thread: Plays pre-generated audio (I/O-bound)

This eliminates gaps between audio playback by generating the next audio
while the current one is playing.

Architecture:
    text_queue → [Generator Thread] → audio_queue → [Playback Thread] → Speaker
"""

import queue
import threading
import numpy as np
import sounddevice as sd
import warnings
import logging
import re
import sys
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model

# Suppress phonemizer and TTS warnings
warnings.filterwarnings('ignore', category=UserWarning, module='phonemizer')
warnings.filterwarnings('ignore', module='mlx_audio')
logging.getLogger('phonemizer').setLevel(logging.ERROR)

# Configure sounddevice for low latency
sd.default.latency = 'low'
sd.default.blocksize = 2048
sd.default.prime_output_buffers_using_stream_callback = True


class TTSPipeline:
    """Two-thread TTS pipeline with separate generation and playback"""

    def __init__(self, model_id='prince-canuma/Kokoro-82M', default_voice='af_heart'):
        """
        Initialize the TTS pipeline

        Args:
            model_id: HuggingFace model ID for TTS
            default_voice: Default voice to use for TTS
        """
        print("🎤 Loading TTS model...")
        self.model = load_model(model_id)
        self.pipeline = KokoroPipeline(lang_code='a', model=self.model, repo_id=model_id)
        self.default_voice = default_voice
        print("✓ TTS model loaded successfully")

        # Two separate queues
        self.text_queue = queue.Queue()           # Raw text to process
        self.audio_queue = queue.Queue(maxsize=3) # Pre-generated audio ready to play

        # Stop event for graceful shutdown
        self.stop_event = threading.Event()

        # Worker threads
        self.generator_thread = None
        self.playback_thread = None

    def sanitize_text(self, text):
        """Clean text for TTS to avoid phonemizer errors"""
        # Remove URLs
        text = re.sub(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\\(\\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', '', text)

        # Remove markdown code blocks and inline code
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = re.sub(r'`[^`]+`', '', text)

        # Remove emojis and special unicode characters
        text = re.sub(r'[^\w\s.,!?;:\'-]', '', text)

        # Remove multiple spaces
        text = re.sub(r'\s+', ' ', text)

        # Remove very short words (likely artifacts)
        text = ' '.join(word for word in text.split() if len(word) > 1 or word in ['I', 'a', 'A'])

        return text.strip()

    def _audio_generator_worker(self):
        """Thread 1: Generate audio from text"""
        print("🎤 Audio generator thread started")

        # Set thread priority on macOS
        try:
            import ctypes
            if sys.platform == 'darwin':
                libc = ctypes.CDLL('/usr/lib/libc.dylib')
                libc.pthread_setname_np(b'TTS_Generator')
        except:
            pass

        while not self.stop_event.is_set():
            try:
                # Get text from queue with timeout
                item = self.text_queue.get(timeout=0.05)

                if item is None:  # Poison pill
                    self.audio_queue.put(None)
                    break

                text, voice, speed = item

                # Skip empty text
                if not text or len(text) < 5:
                    self.text_queue.task_done()
                    continue

                # Generate audio (this takes time)
                audio_chunks = []
                for _, _, audio in self.pipeline(text, voice=voice, speed=speed):
                    if self.stop_event.is_set():
                        break
                    audio_chunks.append(audio[0])

                # Concatenate and queue for playback
                if audio_chunks and not self.stop_event.is_set():
                    full_audio = np.concatenate(audio_chunks, axis=0)
                    # Put generated audio in playback queue
                    self.audio_queue.put(full_audio)

                self.text_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Generator error: {e}")
                try:
                    self.text_queue.task_done()
                except:
                    pass

        print("🎤 Audio generator thread stopped")

    def _audio_playback_worker(self):
        """Thread 2: Play pre-generated audio"""
        print("🔊 Audio playback thread started")

        # Set thread priority on macOS
        try:
            import ctypes
            if sys.platform == 'darwin':
                libc = ctypes.CDLL('/usr/lib/libc.dylib')
                libc.pthread_setname_np(b'TTS_Playback')
        except:
            pass

        while not self.stop_event.is_set():
            try:
                # Get pre-generated audio (this is fast)
                audio = self.audio_queue.get(timeout=0.05)

                if audio is None:  # Poison pill
                    break

                # Play immediately (while next audio is being generated)
                sd.play(
                    audio,
                    samplerate=24000,
                    blocksize=2048,
                    blocking=True  # Block only playback thread
                )
                sd.sleep(5)  # Small delay for device readiness

                self.audio_queue.task_done()

            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ Playback error: {e}")
                try:
                    self.audio_queue.task_done()
                except:
                    pass

        print("🔊 Audio playback thread stopped")

    def start(self):
        """Start both worker threads"""
        if self.generator_thread is None or not self.generator_thread.is_alive():
            self.generator_thread = threading.Thread(
                target=self._audio_generator_worker,
                daemon=True,
                name='TTS-Generator'
            )
            self.generator_thread.start()

        if self.playback_thread is None or not self.playback_thread.is_alive():
            self.playback_thread = threading.Thread(
                target=self._audio_playback_worker,
                daemon=True,
                name='TTS-Playback'
            )
            self.playback_thread.start()

        print("✓ TTS pipeline started")

    def queue_text(self, text, voice=None, speed=1.1):
        """
        Public API: Add text to generation queue

        Args:
            text: Text to convert to speech
            voice: Voice to use (defaults to default_voice)
            speed: Speed multiplier (default 1.1)
        """
        cleaned_text = self.sanitize_text(text)

        # Only queue if text is substantial enough (at least 10 characters)
        if cleaned_text and len(cleaned_text) >= 10:
            v = voice if voice else self.default_voice
            self.text_queue.put((cleaned_text, v, speed))

    def stop(self):
        """Stop both worker threads gracefully"""
        print("🛑 Stopping TTS pipeline...")
        self.stop_event.set()

        # Send poison pills
        self.text_queue.put(None)
        self.audio_queue.put(None)

        # Wait for threads to finish
        if self.generator_thread:
            self.generator_thread.join(timeout=2)
        if self.playback_thread:
            self.playback_thread.join(timeout=2)

        print("✓ TTS pipeline stopped")

    def wait_until_done(self):
        """Wait until all queued audio has been played"""
        self.text_queue.join()
        self.audio_queue.join()


# Global instance (singleton pattern)
_tts_pipeline = None


def get_tts_pipeline():
    """Get or create the global TTS pipeline instance"""
    global _tts_pipeline
    if _tts_pipeline is None:
        _tts_pipeline = TTSPipeline()
        _tts_pipeline.start()
    return _tts_pipeline


def queue_tts(text, voice=None, speed=1.1):
    """Convenience function to queue text for TTS"""
    pipeline = get_tts_pipeline()
    pipeline.queue_text(text, voice, speed)


def stop_tts():
    """Stop the TTS pipeline"""
    global _tts_pipeline
    if _tts_pipeline:
        _tts_pipeline.stop()
        _tts_pipeline = None


def wait_tts_done():
    """Wait until all TTS playback is complete"""
    global _tts_pipeline
    if _tts_pipeline:
        _tts_pipeline.wait_until_done()


# Auto-start on import (optional, can be removed if you prefer manual start)
if __name__ != "__main__":
    # Auto-initialize when imported as a module
    get_tts_pipeline()
