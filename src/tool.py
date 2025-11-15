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
                    "note_directory": {
                        "type": "string",
                        "description": "Path to related notes file or directory"
                    },
                    "comments": {
                        "type": "string",
                        "description": "Explanation of task importance, context, or additional details"
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
    {
        "type": "function",
        "function": {
            "name": "delegate_to_agent",
            "description": "Delegate a specialized task to a worker agent. Pack ALL needed context into task_description (dates, names, details from conversation).",
            "parameters": {
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "description": "Name of worker agent to delegate to",
                        "enum": ["paper_agent", "task_agent", "session_agent"]
                    },
                    "task_description": {
                        "type": "string",
                        "description": "Complete task with ALL context worker needs: what to do, relevant details from conversation, dates, names, paths, etc. Be specific and detailed."
                    }
                },
                "required": ["agent_name", "task_description"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": "Ask the user a clarifying question when instructions are unclear or need confirmation",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {
                        "type": "string",
                        "description": "Clear question to ask the user"
                    }
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "log_activity",
            "description": "Log completed work or agent activity to track what has been done",
            "parameters": {
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "One-line description of what was done"
                    },
                    "files_changed": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional list of file paths that were modified"
                    }
                },
                "required": ["summary"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "start_session_timer",
            "description": "Start a work session with countdown timer and motivational notifications. Sends reminder 2 minutes before time is up.",
            "parameters": {
                "type": "object",
                "properties": {
                    "duration_minutes": {
                        "type": "integer",
                        "description": "Session duration in minutes (e.g., 25 for Pomodoro, 45 for deep work)"
                    },
                    "session_name": {
                        "type": "string",
                        "description": "Name of the work session (e.g., 'Writing', 'Coding', 'Research')"
                    }
                },
                "required": ["duration_minutes", "session_name"]
            }
        }
    }

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

def describe_image_with_vision(image_base64, model_name="google/gemini-2.0-flash-exp:free", prompt="Describe this image in detail."):
    """
    Use a vision model to describe an image

    Args:
        image_base64: Base64 encoded image string
        model_name: Vision model to use (default: gemini-2.0-flash-exp)
        prompt: What to ask about the image

    Returns:
        Text description from the model
    """
    from openai import OpenAI

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=os.getenv("OPENROUTER_API_KEY"),
    )

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"}
                    }
                ]
            }]
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Vision model error: {str(e)}"

def transcribe_audio(audio_path, model_name="openai/whisper-large-v3"):
    """
    Transcribe audio file using OpenRouter

    Args:
        audio_path: Path to audio file
        model_name: Transcription model to use

    Returns:
        Transcription text

    Note: Currently OpenRouter doesn't support audio files directly.
          This would need to use OpenAI Whisper API directly or convert audio to text another way.
    """
    # OpenRouter doesn't support audio transcription endpoints yet
    # This is a placeholder for when they add support or for direct OpenAI API usage
    try:
        import whisper
        model = whisper.load_model("base")
        result = model.transcribe(audio_path)
        return result["text"]
    except ImportError:
        return "Error: whisper library not installed. Install with: pip install openai-whisper"
    except Exception as e:
        return f"Transcription error: {str(e)}"

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

def get_datetime_context():
    """Return current date/time context as formatted string"""
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")  # e.g., 2025-11-15
    current_time = now.strftime("%H:%M:%S")  # e.g., 14:30:45
    current_weekday = now.strftime("%A")     # e.g., Friday

    return f"Current Date: {current_date} ({current_weekday})\nCurrent Time: {current_time}"

def get_conversation_summary(count=5):
    """Get concise summary of last N conversations"""
    conversations = load_recent_conversations(count)

    if not conversations:
        return "No recent conversations."

    summary_parts = []
    for conv in conversations:
        timestamp = conv.get("timestamp", "Unknown time")
        task = conv.get("task", "Unknown task")

        # Format timestamp
        try:
            dt = datetime.fromisoformat(timestamp)
            time_str = dt.strftime("%m-%d %H:%M")
        except:
            time_str = timestamp

        # Keep it concise
        # task_short = task[:80] + "..." if len(task) > 80 else task
        summary_parts.append(f"[{time_str}] {task}")

    return "\n".join(summary_parts)

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
            note_directory=args.get("note_directory", ""),
            comments=args.get("comments", ""),
            deadline=args.get("deadline")
        )

        # Auto-log task creation
        log_activity(f"Created task: {args['name']} (due {args['due_date']}) notes: {args.get('note_directory', '')}")

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

    elif name == "delegate_to_agent":
        # This will be called by manager_agent.py
        # Return a marker that the manager will handle
        return {
            "delegation": True,
            "agent_name": args["agent_name"],
            "task_description": args["task_description"],
            "extra_context": args.get("extra_context", "")
        }

    elif name == "ask_user_question":
        # Interactive question - manager will handle this
        print(f"\n❓ Agent question: {args['question']}")
        user_response = input("Your answer: ")
        return f"User answered: {user_response}"

    elif name == "start_session_timer":
        import random

        duration = args["duration_minutes"]
        session_name = args["session_name"]

        # Motivational messages inspired by productivity principles
        motivational_messages = [
            "Remember to take a break. Sustained focus requires regular rest.",
            "Balance is key. Even a short pause can refresh your mind.",
            "Your wellbeing matters. Regular breaks improve long-term productivity.",
            "Sharpen the saw. Taking time to recharge makes you more effective.",
            "Quality over quantity. Rest is part of the creative process.",
            "Protect your energy. Short breaks prevent burnout.",
            "Self-care isn't selfish. It's essential for sustained excellence.",
            "Listen to your body. Breaks are investments, not interruptions."
        ]

        motivation = random.choice(motivational_messages)

        # Launch standalone menu bar timer as separate process
        timer_script = os.path.join(os.path.dirname(__file__), "menubar_timer.py")

        try:
            # Run timer in background process (detached)
            subprocess.Popen([
                "python3",
                timer_script,
                str(duration),
                session_name,
                motivation
            ], start_new_session=True)

            print(f"✅ Menu bar timer started: {duration} minutes")

        except Exception as e:
            print(f"Could not start menu bar timer: {e}")

        # TTS announcement at start
        try:
            from tts_pipeline import queue_tts
            queue_tts(f"Starting your {duration} minute {session_name} session. I'll remind you when you have 2 minutes left.")
        except:
            pass

        # Send immediate notification
        try:
            from pync import Notifier
            Notifier.notify(
                f"{duration} minutes - Check your menu bar!",
                title=f"⏱️ {session_name} Session Started",
                sound="Glass"
            )
        except:
            pass

        return f"✅ Started {duration}-minute session: {session_name}. Check your menu bar for the countdown!"

    return "Unknown tool"


# ============================================================================
# Test Functions
# ============================================================================

def test_countdown_timer(duration_minutes=1, session_name="Test Session"):
    """
    Test the countdown timer without LLM

    Usage:
        from tool import test_countdown_timer
        test_countdown_timer(1, "Quick Test")  # 1 minute timer
    """
    print(f"\n🧪 Testing countdown timer: {duration_minutes} min - {session_name}")

    # Simulate the tool call
    result = execute_tool("start_session_timer", {
        "duration_minutes": duration_minutes,
        "session_name": session_name
    })

    print(f"Result: {result}")
    print("\n👀 Check your menu bar for: ⏱ MM:SS")
    print(f"Timer will notify you at {duration_minutes-2} min mark (if >2 min)")

    return result


if __name__ == "__main__":
    # Quick test when running tool.py directly
    print("=== COUNTDOWN TIMER TEST ===\n")
    print("Testing 1-minute countdown...")
    test_countdown_timer(duration_minutes=1, session_name="Quick Test")

    print("\n✅ Timer launched! Check your menu bar.")
    print("The timer icon (⏱) should appear in ~1 second.")
    print("\nTo test longer sessions:")
    print("  python -c 'from tool import test_countdown_timer; test_countdown_timer(3, \"Test\")'")
