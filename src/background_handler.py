import os
import base64
import threading
import queue
import subprocess
from io import BytesIO
from datetime import datetime
from pynput import keyboard
from PIL import ImageGrab
from pync import Notifier
import rumps
from streaming_agent import run_agent_with_image

# ============================================
# PSEUDO FUNCTIONS
# ============================================

def load_recent_conversations(*args, **kwargs):
    """Mock function - accepts any arguments"""
    print(f"📚 load_recent_conversations called with: args={args}, kwargs={kwargs}")
    return [
        {"timestamp": "2025-11-15 10:30", "content": "Previous conversation 1"},
        {"timestamp": "2025-11-15 09:15", "content": "Previous conversation 2"}
    ]


def format_conversation_context(*args, **kwargs):
    """Mock function - accepts any arguments"""
    print(f"📝 format_conversation_context called with: args={args}, kwargs={kwargs}")
    return "Context: User has been working on AI agent project..."


# def run_agent_with_image(*args, **kwargs):
#     """Mock function - accepts any arguments and returns formatted result"""
#     print(f"🤖 run_agent_with_image called with:")
#     print(f"   args length: {len(args)}")
#     print(f"   kwargs keys: {kwargs.keys()}")
    
#     # Extract what we can from args/kwargs
#     prompt = args[0] if args else kwargs.get('prompt', 'No prompt')
#     image = args[1] if len(args) > 1 else kwargs.get('image_base64', 'No image')
    
#     # Show we captured the data
#     result = f"""✓ Successfully captured:
# - Text command: {prompt[:100]}...
# - Screenshot: {len(image)} characters (base64)
# - Timestamp: {datetime.now().strftime('%H:%M:%S')}

# Mock agent processed your request!"""
    
#     return result


# ============================================
# MINIMAL AGENT CODE
# ============================================

class MinimalAgent(rumps.App):
    """Minimal background agent with hotkey support"""
    
    def __init__(self):
        super().__init__("🤖")
        self.avatar_path = os.path.abspath("images/A_1.png")
        
        # Queue for communicating between threads
        self.screenshot_queue = queue.Queue()
        
        # Start hotkey listener
        self.start_hotkey_listener()
        
        # Start timer to check queue (runs on main thread)
        self.timer = rumps.Timer(self.check_screenshot_queue, 0.1)
        self.timer.start()
        
        self.notify("Ready", "Press Cmd+Shift+Space to interact")
    
    def start_hotkey_listener(self):
        """Listen for global hotkey"""
        def on_activate():
            print("\n" + "="*60)
            print("🔥 HOTKEY PRESSED!")
            
            # Capture screenshot in background thread (this is OK)
            print("📸 Capturing screenshot...")
            screenshot = self.capture_screenshot()
            print(f"✓ Screenshot captured: {len(screenshot)} chars")
            
            # Put screenshot in queue for main thread to handle
            self.screenshot_queue.put(screenshot)
            print("✓ Screenshot queued for main thread")
            print("="*60 + "\n")
        
        # Background thread for hotkey
        hotkey = keyboard.GlobalHotKeys({
            '<cmd>+<shift>+<space>': on_activate
        })
        threading.Thread(target=hotkey.start, daemon=True).start()
    
    def check_screenshot_queue(self, _):
        """Check queue for screenshots (runs on main thread)"""
        try:
            # Non-blocking check
            screenshot = self.screenshot_queue.get_nowait()
            
            # Use AppleScript for text input (more reliable on macOS)
            print("💬 Showing input dialog via AppleScript...")
            text = self.show_input_dialog()
            
            if text and text.strip():
                print(f"✓ User text: {text}")
                self.process_command(text, screenshot)
            else:
                print("✗ User cancelled or empty input")
                
        except queue.Empty:
            # No screenshot in queue, that's fine
            pass
    
    def show_input_dialog(self):
        """Show input dialog using AppleScript (more reliable than rumps.Window)"""
        applescript = '''
        set userInput to text returned of (display dialog "What do you want me to do with this screenshot?" default answer "" buttons {"Cancel", "Send"} default button "Send" with title "Agent Command")
        return userInput
        '''
        
        try:
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=60  # Wait up to 60 seconds for user input
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                # User clicked Cancel
                return None
                
        except subprocess.TimeoutExpired:
            print("⚠️  Input dialog timed out")
            return None
        except Exception as e:
            print(f"❌ Error showing dialog: {e}")
            return None
    
    def capture_screenshot(self):
        """Capture full screen and return base64"""
        img = ImageGrab.grab()  # Full screenshot
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
        return img_base64
    
    def process_command(self, text, screenshot_base64):
        """Process command + screenshot in background"""
        threading.Thread(
            target=self._process_async,
            args=(text, screenshot_base64),
            daemon=True
        ).start()
    
    def _process_async(self, text, screenshot_base64):
        """Async agent processing"""
        try:
            self.notify("Processing...", text[:50])
            
            # Load conversation context
            recent_conversations = load_recent_conversations(count=5)
            context = format_conversation_context(recent_conversations)
            
            # Enhanced prompt with screenshot context
            full_prompt = f"""User command: {text}

A screenshot is provided showing the current context.

image analysis instructions:
1. describe what is inside the image
2. if image has text, makesure to output the text content as accurate as possible
"""
            
            # Send to agent with both text and image
            result = run_agent_with_image(
                full_prompt, 
                screenshot_base64,
                conversation_context=context
            )
            
            # Show result notification
            self.notify_result(result)
            
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.notify("Error", str(e))
    
    def notify(self, message, title="Agent"):
        """Send notification"""
        try:
            Notifier.notify(
                message,
                title=title,
                contentImage=self.avatar_path if os.path.exists(self.avatar_path) else None,
                sound="Glass"
            )
        except Exception as e:
            print(f"⚠️  Notification failed: {e}")
            print(f"   Title: {title}")
            print(f"   Message: {message}")
    
    def notify_result(self, result):
        """Show result with summary"""
        # Keep notification concise
        summary = result[:200] + "..." if len(result) > 200 else result
        self.notify(summary, "✓ Done")
        print(f"\n📢 NOTIFICATION SENT:\n{result}\n")


def main():
    print("""
╔══════════════════════════════════════════════════════════╗
║         🤖 MINIMAL AGENT TEST                            ║
╚══════════════════════════════════════════════════════════╝

Instructions:
1. Look at this terminal window
2. Press: Cmd+Shift+Space
3. A native macOS dialog will appear - type your command
4. Click "Send" or press Enter
5. Check terminal output to see everything captured!

Starting agent...
""")
    MinimalAgent().run()


if __name__ == "__main__":
    main()