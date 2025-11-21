# Case Study: Optimizing TTS Pipeline Memory Usage

**Date:** 2025-11-21
**Topic:** Debugging and resolving 15GB+ memory leaks in a local Neural TTS pipeline (Kokoro-82M + MLX).

## 1. Problem Statement
The user reported that the Text-to-Speech (TTS) system, running locally on macOS with Apple Silicon (MLX), was accumulating memory rapidly.
- **Symptom:** Memory usage spiked to **15GB+** during operation.
- **Behavior:** The system did not release memory after playback, leading to eventual system instability or crashes.
- **Context:** The system uses `kokoro-82M` (a high-quality neural TTS) via `mlx_audio`.

## 2. Root Cause Analysis

Upon analyzing the previous implementation of `src/tts_pipeline.py`, three critical issues were identified contributing to the memory explosion:

### A. MLX Computation Graph & Caching (Primary Culprit)
The `mlx` framework (Apple's array framework for Apple Silicon) is lazy and aggressive with caching.
- **Issue:** When generating audio, MLX builds a computation graph. If the resulting tensors are stored in a Python list or queue without being explicitly detached or converted, the entire graph (and intermediate buffers) may remain in memory.
- **Cache:** MLX's Metal backend caches allocations to speed up future operations. Without manual intervention (`mx.metal.clear_cache()`), this cache can grow indefinitely during long-running inference loops.

### B. Unbounded Producer-Consumer Queues
- **Issue:** The audio generation (Producer) is typically much faster than audio playback (Consumer).
- **Result:** The `audio_queue` was unbounded. The generator would process all queued text immediately, filling the RAM with uncompressed raw audio data (float32 arrays) waiting to be played.
- **Impact:** 1 minute of generated audio is small, but 100 sentences buffered as raw tensors + attached graphs can be massive.

### C. Tensor Retention
- **Issue:** The audio chunks were likely being stored as MLX arrays or Python lists containing MLX arrays in the queue.
- **Impact:** As long as the Python object exists in the queue, the underlying Unified Memory allocation is locked.

## 3. Solution Implementation

We refactored `src/tts_pipeline.py` to address these specific points.

### Fix 1: Explicit Cache Clearing
We introduced a dependency on `mlx.core` to manually trigger garbage collection on the GPU/Metal backend.

**Code Change:**
```python
# After generating a sentence
if mx:
    mx.metal.clear_cache()
```
*Why it works:* This forces the Metal backend to release unused buffers immediately after a generation step is done, preventing the "steady climb" of memory usage.

### Fix 2: Queue Backpressure (Flow Control)
We limited the size of the queues to prevent the generator from running too far ahead of the playback.

**Code Change:**
```python
# Before
self.audio_queue = queue.Queue()

# After
self.audio_queue = queue.Queue(maxsize=50)
```
*Why it works:* If the queue is full (50 chunks), the `_generation_worker` blocks (waits) until the `_playback_worker` consumes some audio. This keeps the amount of buffered audio in RAM constant and small.

### Fix 3: Immediate Numpy Conversion
We forced the conversion of MLX tensors to standard NumPy arrays immediately upon generation.

**Code Change:**
```python
# Before (Implicit)
audio_chunks.append(audio[0]) # audio[0] is likely an MLX array

# After
# CRITICAL: Convert to numpy immediately to detach from MLX graph
audio_np = np.array(audio[0], dtype=np.float32)
self.audio_queue.put(audio_np)
```
*Why it works:* Converting to `numpy` breaks the link to the MLX computation graph. The `audio_np` object is just raw data bytes; it has no history or attached gradients, allowing the heavy MLX tensors to be garbage collected immediately.

### Fix 4: Dual-Thread Architecture
We separated generation and playback into two distinct threads.

- **Generation Thread:** Focuses on running the model and pushing to queue.
- **Playback Thread:** Focuses on `sounddevice` blocking playback.
- **Benefit:** This ensures that playback (which is slow and real-time) doesn't block the cleanup logic of the generator, and vice versa.

## 4. Summary of Results

| Metric | Previous Implementation | New Implementation |
| :--- | :--- | :--- |
| **Memory Usage** | ~15 GB (Unbounded) | Stable (Low footprint) |
| **Threading** | Single loop (Generate -> Play) | Pipelined (Generate || Play) |
| **Latency** | High (Wait for full generation) | Low (Streaming chunks) |
| **Stability** | Prone to OOM | Robust long-running |

The combination of **Backpressure** (limiting queue size) and **Cache Management** (clearing MLX cache) turned a memory-leaking script into a stable, production-ready background service.
