"""
Simple Background Handler with Two Shortcuts

Shortcut 1 (Cmd+Shift+T): Text input → Classify → Append
Shortcut 2 (Cmd+Shift+4): Screenshot → Text input → Classify → Append with image

Modes:
- simple (default): Uses simple_classifier for quick classification
- agent: Uses manager_agent for full agent system with delegation
"""

import os
import sys
import base64
import threading
import queue
import subprocess
import logging
from pynput import keyboard
from pync import Notifier
import rumps
import argparse

# Suppress pynput keyboard errors (F11/F12 volume keys cause KeyError)
# logging.getLogger('pynput').setLevel(logging.CRITICAL)


class SimpleBackgroundHandler(rumps.App):
    """Background handler with two shortcuts"""

    def __init__(self, mode='simple'):
        super().__init__("📝" if mode == 'simple' else "🤖")
        self.mode = mode
        self.avatar_path = os.path.abspath(
            "/Users/xiaofanlu/Documents/github_repos/hackathon-umass/avatars/melina 2/melina-cute-256.png"
        )

        # Imports are now lazy-loaded to save memory
        # from simple_classifier import shortcut_text as simple_text, shortcut_screenshot as simple_screenshot
        # from manager_agent import shortcut_text as agent_text, shortcut_screenshot as agent_screenshot
        
        # self.simple_text = simple_text
        # self.simple_screenshot = simple_screenshot
        # self.agent_text = agent_text
        # self.agent_screenshot = agent_screenshot
        
        mode_name = "Hybrid (Simple Default)"

        # Queues for both shortcuts
        self.text_queue = queue.Queue()
        self.screenshot_queue = queue.Queue()

        # Start hotkey listeners
        self.start_hotkeys()

        # Timer to check queues
        self.timer = rumps.Timer(self.check_queues, 0.1)
        self.timer.start()

        self.notify("Ready", f"{mode_name} | Cmd+Shift+E: Note | Cmd+Shift+4: Screenshot")
        print(f"✅ Shortcuts ready ({mode_name} mode):")
        print("   Cmd+Shift+E: Quick text note (type 'C' for 40min timer)")
        print("   Cmd+Shift+4: Regional screenshot + comment")

    def start_hotkeys(self):
        """Start hotkey listeners using HotKey class for better compatibility"""
        
        def on_text_shortcut():
            try:
                print("\n🔤 TEXT SHORTCUT PRESSED!")
                self.text_queue.put(True)
            except Exception as e:
                print(f"⚠️  Text shortcut error: {e}")

        def on_screenshot_shortcut():
            try:
                print("\n📸 SCREENSHOT SHORTCUT PRESSED!")
                screenshot = self.capture_screenshot()
                if screenshot:
                    self.screenshot_queue.put(screenshot)
                else:
                    print("Screenshot cancelled by user")
            except Exception as e:
                print(f"⚠️  Screenshot error: {e}")

        # Create HotKey instances
        text_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<cmd>+<shift>+e'),
            on_text_shortcut
        )
        screenshot_hotkey = keyboard.HotKey(
            keyboard.HotKey.parse('<cmd>+<shift>+2'),
            on_screenshot_shortcut
        )

        def for_canonical(f):
            return lambda k, injected=False: f(listener.canonical(k))

        def on_press(key, injected=False):
            for_canonical(text_hotkey.press)(key, injected)
            for_canonical(screenshot_hotkey.press)(key, injected)

        def on_release(key, injected=False):
            for_canonical(text_hotkey.release)(key, injected)
            for_canonical(screenshot_hotkey.release)(key, injected)

        listener = keyboard.Listener(
            on_press=on_press,
            on_release=on_release
        )
        
        threading.Thread(target=listener.start, daemon=True).start()

    def check_queues(self, _):
        """Check both queues on main thread"""

        # Check text queue
        try:
            self.text_queue.get_nowait()
            print("💬 Showing text input dialog...")
            text = self.show_input_dialog("Enter your notes:")
            if text and text.strip():
                self.process_text(text)
        except queue.Empty:
            pass

        # Check screenshot queue
        try:
            screenshot = self.screenshot_queue.get_nowait()
            print("💬 Showing screenshot comment dialog...")
            comment = self.show_input_dialog("Add comment for screenshot (optional):")
            self.process_screenshot(screenshot, comment)
        except queue.Empty:
            pass

    def show_input_dialog(self, prompt_text):
        """Show AppleScript input dialog"""
        applescript = f'''
        set userInput to text returned of (display dialog "{prompt_text}" default answer "" buttons {{"Cancel", "OK"}} default button "OK")
        return userInput
        '''

        try:
            result = subprocess.run(
                ['osascript', '-e', applescript],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            if result.returncode == 0:
                return result.stdout.strip()
            return None

        except Exception as e:
            print(f"❌ Dialog error: {e}")
            return None

    def capture_screenshot(self):
        """Capture regional screenshot (like Cmd+Shift+4) and return base64"""
        import tempfile
        import time

        # Create temp file
        temp_file = tempfile.NamedTemporaryFile(suffix='.png', delete=False)
        temp_path = temp_file.name
        temp_file.close()

        try:
            # Use macOS screencapture with interactive selection (-i)
            subprocess.run(['screencapture', '-i', temp_path], check=True)

            # Small delay to ensure file is written
            time.sleep(0.1)

            # Check if user cancelled (file will be empty or very small)
            if os.path.getsize(temp_path) < 100:
                return None

            # Read and encode
            with open(temp_path, 'rb') as f:
                img_bytes = f.read()

            # Copy to clipboard using pbcopy
            try:
                proc = subprocess.Popen(
                    ['osascript', '-e', f'set the clipboard to (read (POSIX file "{temp_path}") as «class PNGf»)'],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE
                )
                proc.wait()
                print("📋 Screenshot copied to clipboard")
            except Exception as e:
                print(f"⚠️  Clipboard copy failed: {e}")

            img_base64 = base64.b64encode(img_bytes).decode('utf-8')
            return img_base64

        except subprocess.CalledProcessError:
            # User cancelled
            return None
        finally:
            # Clean up temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)

    def process_text(self, text):
        """Process text shortcut"""
        threading.Thread(
            target=self._process_text_async,
            args=(text,),
            daemon=True
        ).start()

    def _process_text_async(self, text):
        """Async text processing with timer shortcuts"""
        try:
            # Check for timer shortcuts (C = 40min countdown) - only in simple mode
            if self.mode == 'simple' and text.strip().upper() == 'C':
                print("⏱️  Starting 40-minute countdown...")
                self.start_countdown_timer(40, "Focus Session")
                self.notify("⏱️ 40-min countdown started", "Check menu bar")
                return

            # Check for S shortcut (25min Pomodoro) - only in simple mode
            if self.mode == 'simple' and text.strip().upper() == 'S':
                print("⏱️  Starting 25-minute Pomodoro...")
                self.start_countdown_timer(25, "Pomodoro")
                self.notify("⏱️ 25-min countdown started", "Check menu bar")
                return

            # Normal text processing
            # Check for Agent Mode (starts with >)
            if text.strip().startswith('>'):
                real_text = text.strip()[1:].strip()
                self.notify("Processing (Agent)...", real_text[:50])
                # Lazy import
                from manager_agent import shortcut_text as agent_text
                result = agent_text(real_text)
            else:
                # Default: Simple Mode
                self.notify("Processing (Simple)...", text[:50])
                # Lazy import
                from simple_classifier import shortcut_text as simple_text
                result = simple_text(text)
            
            self.notify("✅ Saved", f"{result['target']}")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.notify("Error", str(e))

    def process_screenshot(self, screenshot_base64, comment):
        """Process screenshot shortcut"""
        threading.Thread(
            target=self._process_screenshot_async,
            args=(screenshot_base64, comment),
            daemon=True
        ).start()

    def _process_screenshot_async(self, screenshot_base64, comment):
        """Async screenshot processing"""
        try:
            # Check for Agent Mode (comment starts with >)
            if comment and comment.strip().startswith('>'):
                real_comment = comment.strip()[1:].strip()
                self.notify("Processing screenshot (Agent)...", real_comment[:50])
                # Lazy import
                from manager_agent import shortcut_screenshot as agent_screenshot
                result = agent_screenshot(screenshot_base64, real_comment)
            else:
                # Default: Simple Mode
                self.notify("Processing screenshot (Simple)...", comment[:50] if comment else "")
                # Lazy import
                from simple_classifier import shortcut_screenshot as simple_screenshot
                result = simple_screenshot(screenshot_base64, comment or "")
                
            self.notify("✅ Saved", f"{result['target']}: {result['file']}")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()
            self.notify("Error", str(e))

    def start_countdown_timer(self, duration_minutes, session_name):
        """Start countdown timer in menu bar"""
        timer_script = os.path.join(os.path.dirname(__file__), "menubar_timer.py")
        motivation = "Stay focused!"

        try:
            subprocess.Popen([
                "python3",
                timer_script,
                str(duration_minutes),
                session_name,
                motivation
            ], start_new_session=True)
            print(f"✅ Timer started: {duration_minutes} minutes")
        except Exception as e:
            print(f"❌ Timer error: {e}")

    def notify(self, message, title="Classifier"):
        """Send notification with subtle sound"""
        try:
            Notifier.notify(
                message,
                title=title,
                contentImage=self.avatar_path if os.path.exists(self.avatar_path) else None,
                sound="Tink"  # Subtle, natural sound
            )
        except Exception as e:
            print(f"⚠️  Notification failed: {e}")


def main():
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description="Background handler with keyboard shortcuts",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python background_handler_simple.py              # Use simple classifier (default)
  python background_handler_simple.py --mode simple   # Use simple classifier
  python background_handler_simple.py --mode agent    # Use manager agent system

Shortcuts:
  Cmd+Shift+E  → Quick text note (type 'C' for 40min timer, 'S' for 25min timer)
  Cmd+Shift+4  → Regional screenshot + comment
        """
    )
    parser.add_argument(
        '--mode',
        choices=['simple', 'agent'],
        default='simple',
        help='Processing mode: simple (fast classifier) or agent (full agent system)'
    )

    args = parser.parse_args()

    mode_icon = "📝" if args.mode == 'simple' else "🤖"
    mode_name = "Simple Classifier" if args.mode == 'simple' else "Manager Agent"

    print(f"""
╔══════════════════════════════════════════════════════════╗
║         📝 HYBRID MODE (Simple Default)                  ║
╚══════════════════════════════════════════════════════════╝

Shortcuts:
1. Cmd+Shift+E  → Quick text note
                  (type '>' at start for Agent mode)
                  (type 'C' for 40min timer, 'S' for 25min timer)
2. Cmd+Shift+4  → Regional screenshot + comment
                  (type '>' in comment for Agent mode)

Starting...
""")
    SimpleBackgroundHandler(mode='simple').run()


if __name__ == "__main__":
    main()
