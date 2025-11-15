import os
import subprocess
import mss
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
import requests
from dotenv import load_dotenv
from pynput import keyboard
import sounddevice as sd
from mlx_audio.tts.models.kokoro import KokoroPipeline
from mlx_audio.tts.utils import load_model
import threading
import queue
import warnings
import logging
import numpy as np
import json
import time

# Suppress phonemizer and other TTS warnings
warnings.filterwarnings('ignore', category=UserWarning, module='phonemizer')
warnings.filterwarnings('ignore', module='mlx_audio')
logging.getLogger('phonemizer').setLevel(logging.ERROR)

load_dotenv()
# Paths
INSTRUCTION_FILE = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory/user_instruction.md"
MEMORY_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory"
SCREENSHOT_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/screenshots"
CONVERSATION_HISTORY_FILE = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory/conversation_history.json"

# Ensure directories exist
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Configure sounddevice for better audio performance
sd.default.latency = 'low'
sd.default.blocksize = 2048
sd.default.prime_output_buffers_using_stream_callback = True

# Initialize TTS model
print("Loading TTS model...")
model_id = 'prince-canuma/Kokoro-82M'
tts_model = load_model(model_id)
tts_pipeline = KokoroPipeline(lang_code='a', model=tts_model, repo_id=model_id)
tts_voice = "af_heart"
# tts_voice = "bf_emma"
print("TTS model loaded successfully")

# TTS Queue System
tts_queue = queue.Queue()
tts_stop_event = threading.Event()

def tts_worker():
    """Dedicated worker thread for TTS playback"""
    print("🔊 TTS worker thread started")
    import warnings
    import sys

    # Suppress phonemizer warnings for cleaner output
    warnings.filterwarnings('ignore', category=UserWarning, module='phonemizer')

    # Set thread priority on macOS
    try:
        import ctypes
        if sys.platform == 'darwin':
            # Set thread to higher priority on macOS
            libc = ctypes.CDLL('/usr/lib/libc.dylib')
            libc.pthread_setname_np(b'TTS_Audio_Worker')
    except:
        pass  # Ignore if priority setting fails

    while not tts_stop_event.is_set():
        try:
            # Get text from queue with timeout
            item = tts_queue.get(timeout=0.05)
            if item is None:  # Poison pill to stop
                break

            text, voice, speed = item

            # Skip empty or very short text
            if not text or len(text) < 5:
                tts_queue.task_done()
                continue

            # Generate and play audio
            try:
                audio_chunks = []

                # Collect all audio chunks first
                for _, _, audio in tts_pipeline(text, voice=voice, speed=speed):
                    if tts_stop_event.is_set():
                        break
                    audio_chunks.append(audio[0])

                # Concatenate all chunks into one buffer for smoother playback
                if audio_chunks and not tts_stop_event.is_set():
                    full_audio = np.concatenate(audio_chunks, axis=0)

                    # Play the complete audio buffer in blocking mode
                    # This prevents glitches from chunked playback
                    sd.play(
                        full_audio,
                        samplerate=24000,
                        blocksize=2048,
                        blocking=True
                    )

                    # Small delay to ensure audio device is ready for next
                    sd.sleep(5)

            except Exception as tts_error:
                # Log TTS generation errors but continue
                print(f"\n⚠️ TTS generation error: {tts_error}")

            tts_queue.task_done()
        except queue.Empty:
            continue
        except Exception as e:
            print(f"\n⚠️ TTS worker error: {e}")
            try:
                tts_queue.task_done()
            except:
                pass

    print("🔊 TTS worker thread stopped")

def sanitize_text_for_tts(text):
    """Clean text for TTS to avoid phonemizer errors"""
    import re

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

def queue_tts(text, voice=None, speed=1.1):
    """Add text to TTS queue for playback"""
    cleaned_text = sanitize_text_for_tts(text)

    # Only queue if text is substantial enough (at least 10 characters)
    if cleaned_text and len(cleaned_text) >= 10:
        v = voice if voice else tts_voice
        tts_queue.put((cleaned_text, v, speed))

def stop_tts_worker():
    """Stop the TTS worker thread"""
    tts_stop_event.set()
    tts_queue.put(None)  # Poison pill

# Start TTS worker thread
tts_thread = threading.Thread(target=tts_worker, daemon=True)
tts_thread.start()

# Tool definitions
tools = [
    {
        "type": "function",
        "function": {
            "name": "bash_command",
            "description": "Execute bash commands to modify files, create new files, or perform system operations",
            "parameters": {
                "type": "object",
                "properties": {"command": {"type": "string"}},
                "required": ["command"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "update_instructions",
            "description": "Update or append to the user instruction file",
            "parameters": {
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Content to append to instructions"}
                },
                "required": ["content"]
            }
        }
    },
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "ask_user_question",
    #         "description": "Ask the user a question when instructions are unclear",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "question": {"type": "string", "description": "Question to ask the user"}
    #             },
    #             "required": ["question"]
    #         }
    #     }
    # },
    # # only grok fast use ask question tool other llm just don't use this tool, but grok fast vision is trash
    # {
    #     "type": "function",
    #     "function": {
    #         "name": "create_memory_file",
    #         "description": "Create a new file in memory folder to track specific information",
    #         "parameters": {
    #             "type": "object",
    #             "properties": {
    #                 "filename": {"type": "string", "description": "Name of the file to create"},
    #                 "content": {"type": "string", "description": "Content to write to the file"}
    #             },
    #             "required": ["filename", "content"]
    #         }
    #     }
    # },
    {
        "type": "function",
        "function": {
            "name": "brave_search",
            "description": "Search the web using Brave Search API. Returns web search results with titles, descriptions, and URLs.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query string"
                    },
                    "count": {
                        "type": "integer",
                        "description": "Number of results to return (default: 10, max: 20)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a time-dependent task. Tags: hw (homework, removed if overdue), paper_review (auto-extends 2 days), meeting/office_hour (recurrent weekly until deadline), research (standard task)",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {
                        "type": "string",
                        "description": "Task name/description"
                    },
                    "tag": {
                        "type": "string",
                        "description": "Task type: hw, paper_review, meeting, office_hour, research",
                        "enum": ["hw", "paper_review", "meeting", "office_hour", "research"]
                    },
                    "due_date": {
                        "type": "string",
                        "description": "Due date in YYYY-MM-DD format"
                    },
                    "done": {
                        "type": "boolean",
                        "description": "Completion status (default False)",
                        "default": False
                    },
                    "notes": {
                        "type": "string",
                        "description": "Path to related notes file"
                    },
                    "deadline": {
                        "type": "string",
                        "description": "For recurring tasks (meeting/office_hour), final deadline in YYYY-MM-DD format"
                    }
                },
                "required": ["name", "tag", "due_date"]
            }
        }
    },

]


def macos_region_screenshot():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"{SCREENSHOT_DIR}/capture_{timestamp}.png"
    
    # Run macOS's native interactive region capture
    subprocess.run(["screencapture", "-i", filepath])
    
    # Load it as a PIL image
    img = Image.open(filepath)
    return img

def save_screenshot(img):
    """Save screenshot to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"{SCREENSHOT_DIR}/capture_{timestamp}.png"
    img.save(filepath)
    print(f"\n📸 Screenshot saved: {filepath}")
    return filepath

def image_to_base64(img):
    """Convert PIL Image to base64 string"""
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

def read_instructions():
    try:
        with open(INSTRUCTION_FILE, 'r') as f:
            content = f.read()
        return content if content.strip() else "No instructions found. File is empty."
    except Exception as e:
        return f"Error reading instructions: {e}"

def save_conversation(task, messages, result):
    """Save conversation history to JSON file"""
    try:
        # Load existing history
        history = []
        if os.path.exists(CONVERSATION_HISTORY_FILE):
            try:
                with open(CONVERSATION_HISTORY_FILE, 'r') as f:
                    history = json.load(f)
            except json.JSONDecodeError:
                history = []

        # Create conversation entry
        conversation = {
            "timestamp": datetime.now().isoformat(),
            "task": task,
            "messages": messages,
            "result": result
        }

        # Add to history (keep most recent at the end)
        history.append(conversation)

        # Keep only last 50 conversations to avoid file bloat
        if len(history) > 50:
            history = history[-50:]

        # Save updated history
        with open(CONVERSATION_HISTORY_FILE, 'w') as f:
            json.dump(history, f, indent=2)

        return True
    except Exception as e:
        print(f"⚠️ Error saving conversation: {e}")
        return False

def load_recent_conversations(count=5):
    """Load recent N conversations from history"""
    try:
        if not os.path.exists(CONVERSATION_HISTORY_FILE):
            return []

        with open(CONVERSATION_HISTORY_FILE, 'r') as f:
            history = json.load(f)

        # Return last N conversations
        return history[-count:] if len(history) > count else history
    except Exception as e:
        print(f"⚠️ Error loading conversation history: {e}")
        return []

def format_conversation_context(conversations):
    """Format recent conversations into a readable context string"""
    if not conversations:
        return "No previous conversation history."

    context_parts = ["=== Recent Conversation History ===\n"]

    for i, conv in enumerate(conversations, 1):
        timestamp = conv.get("timestamp", "Unknown time")
        task = conv.get("task", "Unknown task")
        result = conv.get("result", "No result")

        # Format timestamp nicely
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except:
            time_str = timestamp

        context_parts.append(f"\n[{i}] {time_str}")
        context_parts.append(f"Task: {task[:150]}{'...' if len(task) > 150 else ''}")
        context_parts.append(f"Result: {result[:150]}{'...' if len(result) > 150 else ''}")
        context_parts.append("-" * 60)

    return "\n".join(context_parts)

def execute_tool(name, args):
    """Execute tool calls"""
    if name == "bash_command":
        result = subprocess.run(args["command"], shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"

    elif name == "create_task":
        from time_depends_tasks import create_task
        from agent_log import log_activity

        result = create_task(
            name=args["name"],
            tag=args["tag"],
            due_date=args["due_date"],
            done=args.get("done", False),
            notes=args.get("notes", ""),
            deadline=args.get("deadline")
        )

        # Auto-log task creation
        log_activity(f"Created task: {args['name']} (due {args['due_date']}) notes: {args.get('notes', '')}")

        return str(result)

    elif name == "get_tasks_summary":
        from time_depends_tasks import get_tasks_summary
        return get_tasks_summary()

    elif name == "update_task":
        from time_depends_tasks import update_task
        # Remove 'name' from args to get only the updates
        task_name = args.pop("name")
        result = update_task(task_name, **args)
        return str(result)

    elif name == "log_activity":
        from agent_log import log_activity
        result = log_activity(
            summary=args["summary"],
            files_changed=args.get("files_changed")
        )
        return result

    elif name == "update_instructions":
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(INSTRUCTION_FILE, 'a') as f:
                f.write(f"\n\n## [{timestamp}]\n{args['content']}\n")
            return "Instructions updated successfully"
        except Exception as e:
            return f"Error updating instructions: {e}"

    elif name == "ask_user_question":
        question = args['question']
        print(f"\n❓ Agent Question: {question}")

        # Queue TTS audio for the question
        print("🔊 Speaking question...")
        queue_tts(question)

        # Wait for the TTS queue to be empty before asking for input
        tts_queue.join()

        user_response = input("Your answer: ")
        return user_response

    elif name == "create_memory_file":
        try:
            filepath = os.path.join(MEMORY_DIR, args['filename'])
            with open(filepath, 'w') as f:
                f.write(args['content'])
            return f"Memory file created at {filepath}"
        except Exception as e:
            return f"Error creating memory file: {e}"

    elif name == "brave_search":
        try:
            api_key = os.getenv("BRAVE_API_KEY")
            if not api_key:
                return "Error: BRAVE_API_KEY not found in environment variables"

            query = args["query"]
            count = args.get("count", 10)
            time.sleep(1)
            # Brave Search API endpoint
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": api_key
            }
            params = {
                "q": query,
                "count": min(count, 20)  # Max 20 results
            }

            response = requests.get(url, headers=headers, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()
                results = []

                # Extract web results
                if "web" in data and "results" in data["web"]:
                    for idx, result in enumerate(data["web"]["results"][:count], 1):
                        results.append({
                            "position": idx,
                            "title": result.get("title", ""),
                            "url": result.get("url", ""),
                            "description": result.get("description", "")
                        })

                if results:
                    formatted_results = "\n\n".join([
                        f"{r['position']}. {r['title']}\n   URL: {r['url']}\n   {r['description']}"
                        for r in results
                    ])
                    return f"Search Results for '{query}':\n\n{formatted_results}"
                else:
                    return f"No results found for query: {query}"
            else:
                return f"Error: Brave API returned status code {response.status_code}\n{response.text}"

        except requests.exceptions.Timeout:
            return "Error: Search request timeout"
        except Exception as e:
            return f"Error during search: {str(e)}"

    return "Unknown tool"