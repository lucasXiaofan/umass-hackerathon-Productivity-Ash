import os
import json
from openai import OpenAI
from dotenv import load_dotenv
import subprocess
import mss
from PIL import Image
import base64
from io import BytesIO
from datetime import datetime
import threading
from pynput import keyboard

load_dotenv()

# OpenAI/OpenRouter setup
model_name = "x-ai/grok-4-fast"
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Paths
INSTRUCTION_FILE = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory/user_instruction.md"
MEMORY_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/memory"
SCREENSHOT_DIR = "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/screenshots"

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
            "name": "read_instructions",
            "description": "Read past user instructions from the instruction file",
            "parameters": {"type": "object", "properties": {}}
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

def execute_tool(name, args):
    """Execute tool calls"""
    if name == "bash_command":
        result = subprocess.run(args["command"], shell=True, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"

    elif name == "read_instructions":
        try:
            with open(INSTRUCTION_FILE, 'r') as f:
                content = f.read()
            return content if content.strip() else "No instructions found. File is empty."
        except Exception as e:
            return f"Error reading instructions: {e}"

    elif name == "update_instructions":
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            with open(INSTRUCTION_FILE, 'a') as f:
                f.write(f"\n\n## [{timestamp}]\n{args['content']}\n")
            return "Instructions updated successfully"
        except Exception as e:
            return f"Error updating instructions: {e}"

    elif name == "ask_user_question":
        print(f"\n❓ Agent Question: {args['question']}")
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

    return "Unknown tool"

def run_agent_with_image(task, image_base64=None, max_iter=15):
    """Run agent with optional image input"""
    # Build initial message
    user_message = {
        "role": "user",
        "content": [{"type": "text", "text": task}]
    }

    if image_base64:
        user_message["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    messages = [
        {"role": "system", "content": "You are a helpful assistant with access to bash commands, memory management, and user instruction tracking. Always check past instructions before taking action. If unclear, ask questions to the user."},
        user_message
    ]

    for i in range(max_iter):
        print(f"\n{'='*50}\nITER {i+1}\n{'='*50}")

        stream = client.chat.completions.create(
            model=model_name,
            messages=messages,
            tools=tools,
            stream=True
        )

        content = ""
        tool_calls = []

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content

            if delta.tool_calls:
                for tc in delta.tool_calls:
                    while len(tool_calls) <= tc.index:
                        tool_calls.append({
                            "id": "",
                            "type": "function",
                            "function": {"name": "", "arguments": ""}
                        })

                    if tc.id: tool_calls[tc.index]["id"] = tc.id
                    if tc.function.name: tool_calls[tc.index]["function"]["name"] = tc.function.name
                    if tc.function.arguments: tool_calls[tc.index]["function"]["arguments"] += tc.function.arguments

        print()

        # Build message properly
        msg = {"role": "assistant"}
        if content: msg["content"] = content
        if tool_calls: msg["tool_calls"] = tool_calls
        messages.append(msg)

        if not tool_calls:
            return content

        # Execute tool calls
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            print(f"\n🔧 Tool: {tc['function']['name']}({args})")
            result = execute_tool(tc["function"]["name"], args)
            print(f"📤 Result: {result}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

    return "Max iterations reached"

def process_screenshot_with_agent():
    """Capture screenshot and send to agent for analysis"""
    print("\n" + "="*60)
    print("🚀 Starting screenshot capture...")

    # Take screenshot
    img = take_screenshot()
    screenshot_path = save_screenshot(img)
    img_base64 = image_to_base64(img)

    # Send to agent
    task = """Analyze this screenshot.
    1. First, read past user instructions to understand context
    2. Extract any deadlines, tasks, events, or important information
    3. If past instructions don't clearly define what to do with this information, ask the user for guidance
    4. Based on instructions or user response, decide what action to take (create memory file, update instructions, etc.)
    5. Take appropriate actions to track the information"""

    print("\n🤖 Sending to agent for analysis...")
    result = run_agent_with_image(task, img_base64)

    print("\n" + "="*60)
    return result

def process_text_input(text):
    """Process text input without screenshot"""
    print("\n" + "="*60)
    print(f"💬 Processing text: {text}")
    result = run_agent_with_image(text)
    print("\n" + "="*60)
    return result

def on_screenshot_hotkey():
    """Callback when screenshot hotkey is pressed"""
    thread = threading.Thread(target=process_screenshot_with_agent)
    thread.start()

def main():
    """Main entry point"""
    print("🎯 Streaming Agent with Screenshot Support Ready!")
    print("Commands:")
    print("  - Press Cmd+Shift+S: Capture screenshot and analyze")
    print("  - Type message: Send text to agent")
    print("  - Type 'quit': Exit\n")

    # Start keyboard listener in background
    hotkey_listener = keyboard.GlobalHotKeys({
        '<cmd>+<shift>+s': on_screenshot_hotkey
    })
    hotkey_listener.start()

    try:
        while True:
            user_input = input("\n💬 You: ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            if user_input.strip():
                process_text_input(user_input)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        hotkey_listener.stop()

if __name__ == "__main__":
    main()
