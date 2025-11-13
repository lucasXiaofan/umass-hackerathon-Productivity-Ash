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
from tool import *
import re
import warnings

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore')

load_dotenv()

# OpenAI/OpenRouter setup
model_name = "x-ai/grok-4-fast"
# model_name = "anthropic/claude-haiku-4.5"
# model_name = "qwen/qwen3-vl-235b-a22b-instruct"
# model_name = "openai/gpt-5-mini"
# model_name = "openrouter/polaris-alpha"
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)



def run_agent_with_image(task, image_base64=None, conversation_context="", max_iter=15):
    """Run agent with optional image input and conversation context"""
    # Build initial message
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")  # e.g., 2024-03-15
    current_time = now.strftime("%H:%M:%S")  # e.g., 14:30:45
    current_weekday = now.strftime("%A")     # e.g., Monday

    # Format datetime context
    datetime_context = f"Current Date: {current_date} ({current_weekday})\nCurrent Time: {current_time}"

    user_message = {
        "role": "user",
        "content": [{"type": "text", "text": f"current time: {datetime_context}, task: {task}"}]
    }

    if image_base64:
        user_message["content"].append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    messages = [
        {"role": "system", "content": f"""
            You are a helpful assistant with access to bash commands,
         memory management, and user instruction tracking.
         If unclear, or need more instruction use ask_user_question to ask clarify question to the user.
         make your message to user concise (3-5) sentences, trying to be cheerful and helpful

         current instruction from past:
         {read_instructions()}

         {conversation_context}
         """},
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
        tts_buffer = ""  # Buffer for TTS sentence accumulation

        for chunk in stream:
            delta = chunk.choices[0].delta

            if delta.content:
                print(delta.content, end="", flush=True)
                content += delta.content
                tts_buffer += delta.content

                # Check if we have complete sentences to speak
                # Look for sentence endings: . ! ? followed by space/newline
                # Also look for line breaks with content
                sentence_pattern = r'([.!?]+[\s\n]+|[\n]{2,})'
                matches = list(re.finditer(sentence_pattern, tts_buffer))

                if matches:
                    # Get all complete sentences up to the last match
                    last_match = matches[-1]
                    complete_text = tts_buffer[:last_match.end()].strip()

                    # Only queue if we have substantial content (avoid fragments)
                    if complete_text and len(complete_text) >= 15:
                        # Queue the complete sentence(s) for TTS playback
                        queue_tts(complete_text)

                        # Keep the remainder in buffer
                        tts_buffer = tts_buffer[last_match.end():]
                    elif len(tts_buffer) > 200:
                        # If buffer is getting too long without sentence markers, flush it
                        queue_tts(tts_buffer.strip())
                        tts_buffer = ""

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

        # Queue any remaining text in buffer
        if tts_buffer.strip():
            queue_tts(tts_buffer.strip())

        print()

        # Build message properly
        msg = {"role": "assistant"}
        if content: msg["content"] = content
        if tool_calls: msg["tool_calls"] = tool_calls
        messages.append(msg)

        if not tool_calls:
            # Save conversation before returning
            save_conversation(task, messages, content)
            return content

        # Execute tool calls
        for tc in tool_calls:
            args = json.loads(tc["function"]["arguments"])
            print(f"\n🔧 Tool: {tc['function']['name']}({args})")
            result = execute_tool(tc["function"]["name"], args)
            print(f"📤 Result: {result}")
            messages.append({"role": "tool", "tool_call_id": tc["id"], "content": str(result)})

    # Save conversation before returning (max iterations)
    final_result = "Max iterations reached"
    save_conversation(task, messages, final_result)
    return final_result

def process_screenshot_with_agent():
    """Capture screenshot and send to agent for analysis"""
    print("\n" + "="*60)
    print("🚀 Starting screenshot capture...")

    # Take screenshot
    img = take_screenshot()
    screenshot_path = save_screenshot(img)
    img_base64 = image_to_base64(img)

    # Send to agent with conversation context
    task = """Analyze this screenshot.
    1. First, read past user instructions to understand context
    2. Extract any deadlines, tasks, events, or important information
    3. If past instructions don't clearly define what to do with this information, ask the user for guidance
    4. Based on instructions or user response, decide what action to take (create memory file, update instructions, etc.)
    5. Take appropriate actions to track the information"""

    print("\n🤖 Sending to agent for analysis...")
    # Load recent conversation context
    recent_conversations = load_recent_conversations(count=5)
    conversation_context = format_conversation_context(recent_conversations)
    result = run_agent_with_image(task, img_base64, conversation_context=conversation_context)

    print("\n" + "="*60)
    return result

def process_text_input(text, conversation_context):
    """Process text input without screenshot"""
    print("\n" + "="*60)
    print(f"💬 Processing text: {text}")
    result = run_agent_with_image(text, conversation_context=conversation_context)
    print("\n" + "="*60)
    return result

def on_screenshot_hotkey():
    """Callback when screenshot hotkey is pressed"""
    thread = threading.Thread(target=process_screenshot_with_agent)
    thread.start()

def main():
    """Main entry point"""
    print("🎯 Streaming Agent with Screenshot Support Ready!")

    # Load recent conversation history to show status
    print("📚 Loading recent conversation history...")
    recent_conversations = load_recent_conversations(count=5)

    if recent_conversations:
        print(f"✓ Loaded {len(recent_conversations)} recent conversation(s)")
    else:
        print("✓ No previous conversation history found")

    print("\nCommands:")
    print("  - Press Cmd+Shift+L: Capture screenshot and analyze")
    print("  - Type message: Send text to agent")
    print("  - Type 'quit': Exit\n")

    # Start keyboard listener in background
    hotkey_listener = keyboard.GlobalHotKeys({
        '<cmd>+<shift>+l': on_screenshot_hotkey
    })
    hotkey_listener.start()

    try:
        while True:
            user_input = input("\n💬 You: ")
            if user_input.lower() in ['quit', 'exit', 'q']:
                break
            if user_input.strip():
                # Load fresh conversation context for each interaction
                recent_conversations = load_recent_conversations(count=5)
                conversation_context = format_conversation_context(recent_conversations)
                process_text_input(user_input, conversation_context)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
    finally:
        hotkey_listener.stop()
        # Stop TTS worker thread
        stop_tts_worker()
        tts_thread.join(timeout=2)

if __name__ == "__main__":
    main()
