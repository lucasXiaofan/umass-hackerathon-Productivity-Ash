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
load_dotenv()
# Paths
INSTRUCTION_FILE = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory/user_instruction.md"
MEMORY_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory"
SCREENSHOT_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/screenshots"

# Ensure directories exist
os.makedirs(MEMORY_DIR, exist_ok=True)
os.makedirs(SCREENSHOT_DIR, exist_ok=True)

# Initialize TTS model
print("Loading TTS model...")
model_id = 'prince-canuma/Kokoro-82M'
tts_model = load_model(model_id)
tts_pipeline = KokoroPipeline(lang_code='a', model=tts_model, repo_id=model_id)
tts_voice = "af_heart"
print("TTS model loaded successfully")

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
    {
        "type": "function",
        "function": {
            "name": "ask_user_question",
            "description": "Ask the user a question when instructions are unclear",
            "parameters": {
                "type": "object",
                "properties": {
                    "question": {"type": "string", "description": "Question to ask the user"}
                },
                "required": ["question"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_memory_file",
            "description": "Create a new file in memory folder to track specific information",
            "parameters": {
                "type": "object",
                "properties": {
                    "filename": {"type": "string", "description": "Name of the file to create"},
                    "content": {"type": "string", "description": "Content to write to the file"}
                },
                "required": ["filename", "content"]
            }
        }
    },
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
    }
]

def take_screenshot():
    """Capture full screenshot"""
    with mss.mss() as sct:
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
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

def execute_tool(name, args):
    """Execute tool calls"""
    if name == "bash_command":
        result = subprocess.run(args["command"], shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"

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

        # Generate and play TTS audio for the question (blocking)
        print("🔊 Speaking question...")
        for _, _, audio in tts_pipeline(question, voice=tts_voice, speed=1):
            sd.play(audio[0], samplerate=24000)
            sd.wait()  # Block until audio finishes playing

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