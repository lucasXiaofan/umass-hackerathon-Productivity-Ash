"""
Single-Thread TTS Pipeline System
==================================

This module implements a simple single-threaded TTS system:
1. TTS Worker Thread: Converts text to audio AND plays it sequentially

This prevents race conditions and memory issues from multi-threading.

Architecture:
    text_queue → [TTS Worker Thread: Generate → Play → Cleanup] → Speaker
"""

import queue
import threading
import numpy as np
import sounddevice as sd
import warnings
import logging
import re
import sys
import gc
import time
try:
    import mlx.core as mx
except ImportError:
    mx = None
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
    """
    Optimized TTS pipeline with separate generation and playback threads.
    Loads model ONCE and keeps it in memory.
    """

    def __init__(self, model_id='prince-canuma/Kokoro-82M', default_voice='af_heart'):
        """
        Initialize the TTS pipeline
        """
        print("🎤 Loading TTS model (Singleton)...")
        self.model_id = model_id
        self.model = load_model(model_id)
        self.pipeline = KokoroPipeline(lang_code='a', model=self.model, repo_id=model_id)
        self.default_voice = default_voice
        
        print("✓ TTS model loaded successfully")

        # Queues
        # Limit queue sizes to prevent memory explosion if generation > playback
        self.text_queue = queue.Queue(maxsize=20) 
        self.audio_queue = queue.Queue(maxsize=50) 

        # Stop event
        self.stop_event = threading.Event()

        # Threads
        self.gen_thread = None
        self.play_thread = None

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

    def _generation_worker(self):
        """Worker 1: Consumes text, generates audio, puts into audio_queue"""
        print("🎤 TTS Generation worker started")
        
        while not self.stop_event.is_set():
            try:
                # Get text (blocking if empty)
                item = self.text_queue.get(timeout=0.1)
                
                if item is None: # Poison pill
                    self.audio_queue.put(None) # Propagate poison pill
                    break
                    
                text, voice, speed = item
                
                if not text:
                    self.text_queue.task_done()
                    continue

                # Generate audio (streaming chunks)
                for _, _, audio in self.pipeline(text, voice=voice, speed=speed):
                    if self.stop_event.is_set():
                        break
                    
                    # audio is [wav], get the array
                    if len(audio) > 0:
                        # CRITICAL: Convert to numpy immediately to detach from MLX graph
                        # and ensure it's a standard float32 array
                        audio_np = np.array(audio[0], dtype=np.float32)
                        
                        # Put in queue (blocking if full, providing backpressure)
                        self.audio_queue.put(audio_np)
                
                # Clear MLX cache after each sentence to free GPU memory
                if mx:
                    mx.metal.clear_cache()
                    
                self.text_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ TTS Gen Error: {e}")
                import traceback
                traceback.print_exc()

        print("🎤 TTS Generation worker stopped")

    def _playback_worker(self):
        """Worker 2: Consumes audio chunks and plays them"""
        print("🔊 TTS Playback worker started")
        
        while not self.stop_event.is_set():
            try:
                audio_chunk = self.audio_queue.get(timeout=0.1)
                
                if audio_chunk is None: # Poison pill
                    break
                
                # Play audio (blocking for this chunk)
                sd.play(audio_chunk, samplerate=24000, blocking=True)
                
                # Explicit cleanup
                del audio_chunk
                
                self.audio_queue.task_done()
                
            except queue.Empty:
                continue
            except Exception as e:
                print(f"⚠️ TTS Play Error: {e}")

        print("🔊 TTS Playback worker stopped")

    def start(self):
        """Start worker threads"""
        if self.gen_thread is None or not self.gen_thread.is_alive():
            self.gen_thread = threading.Thread(
                target=self._generation_worker, 
                daemon=True, 
                name='TTS-Gen'
            )
            self.gen_thread.start()
            
        if self.play_thread is None or not self.play_thread.is_alive():
            self.play_thread = threading.Thread(
                target=self._playback_worker, 
                daemon=True, 
                name='TTS-Play'
            )
            self.play_thread.start()
            
        print("✓ TTS pipeline started (Dual-thread mode)")

    def queue_text(self, text, voice=None, speed=1.1):
        """Add text to queue"""
        cleaned_text = self.sanitize_text(text)
        if cleaned_text and len(cleaned_text) >= 2: 
            v = voice if voice else self.default_voice
            # Put in queue (non-blocking, might raise Full if overloaded)
            try:
                self.text_queue.put((cleaned_text, v, speed), block=False)
            except queue.Full:
                print("⚠️ TTS Text Queue Full - dropping text")

    def stop(self):
        """Stop pipeline"""
        print("🛑 Stopping TTS pipeline...")
        self.stop_event.set()
        try:
            self.text_queue.put(None, block=False) # Poison pill
        except:
            pass
        
        if self.gen_thread: self.gen_thread.join(timeout=2)
        if self.play_thread: self.play_thread.join(timeout=2)
        
        print("✓ TTS pipeline stopped")

    def wait_until_done(self):
        """Wait for queues to empty"""
        self.text_queue.join()
        self.audio_queue.join()


# Global instance (singleton pattern)
_tts_pipeline = None
_tts_pipeline_lock = threading.Lock()


def get_tts_pipeline():
    """Get or create the global TTS pipeline instance (thread-safe singleton)"""
    global _tts_pipeline

    if _tts_pipeline is None:
        with _tts_pipeline_lock:
            if _tts_pipeline is None:
                _tts_pipeline = TTSPipeline()
                _tts_pipeline.start()

    return _tts_pipeline


def queue_tts(text, voice=None, speed=1.1):
    """Convenience function to queue text for TTS"""
    try:
        pipeline = get_tts_pipeline()
        pipeline.queue_text(text, voice, speed)
    except Exception as e:
        print(f"TTS Queue Error: {e}")


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
