"""
Helper functions for focus sessions and time-based reminders
"""
import json
import os
import subprocess
import base64
from datetime import datetime, timedelta
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional, Literal, Dict
from google import genai
from dotenv import load_dotenv
# from playsound import playsound 
import threading
try:
    from pync import Notifier
    NOTIFICATIONS_AVAILABLE = True
except ImportError:
    NOTIFICATIONS_AVAILABLE = False
    print("Warning: pync not available, notifications disabled")

load_dotenv()

# Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY")
client = genai.Client(api_key=api_key)


# Pydantic models for structured output
class FocusSessionRequest(BaseModel):
    """Schema for detecting focus session requests"""
    action: Literal["add", "delete", "none"] = Field(description="Action: add new focus session, delete current session, or none")
    task_description: Optional[str] = Field(default=None, description="Task description be detail")
    duration_minutes: Optional[int] = Field(default=None, description="Duration in minutes (for add action)")


class TimeReminder(BaseModel):
    """Schema for time-based reminders"""
    type: Literal["health", "motivation", "productivity"] = Field(description="Type of reminder")
    message: str = Field(description="Reminder message")
    priority: Literal["low", "medium", "high"] = Field(description="Priority level")


class DistractionAnalysis(BaseModel):
    """Schema for screenshot distraction detection"""
    is_distraction: bool = Field(description="True if user is distracted (YouTube, games, Instagram, etc.)")
    description: str = Field(description="Detailed description of what's visible in the screenshot")
    distraction_type: Optional[str] = Field(default=None, description="Type of distraction if detected (e.g., 'YouTube', 'Instagram', 'Gaming', 'Social Media')")


def manage_focus_session(message):
    """
    Simple focus session manager: add or delete one focus session at a time

    Args:
        message: User's message

    Returns:
        dict: {"action": "add"|"delete", "data": {...}} or None if no focus action
    """
    try:
        # Use Gemini with JSON schema to parse the focus request
        prompt = f"""Analyze this message and determine what focus session action the user wants.

User message: {message}

Actions:
- "add": User wants to start/begin a focus session (e.g., "I want to lock in for doing rl for two hours", "focus on math for 1 hour")
- "delete": User is done and wants to stop/delete current focus session (e.g., "I am done", "stop focus", "I want to do something else")
- "none": Not related to focus sessions

For "add" action, extract:
- task_description: what they want to focus on (BE DESCRIPTIVE - expand abbreviations and provide full context)
  * "rl hw 3" -> "reinforcement learning homework 3"
  * "study cs" -> "studying computer science"
  * "math" -> "studying mathematics"
  * "coding project" -> "working on coding project"
- duration_minutes: duration in minutes (convert hours to minutes, default to 60 if not specified)

Examples:
- "I want to lock in for doing rl for two hours" -> action="add", task_description="reinforcement learning", duration_minutes=120
- "Focus on rl hw 3 for 30 min" -> action="add", task_description="reinforcement learning homework 3", duration_minutes=30
- "Study math" -> action="add", task_description="studying mathematics", duration_minutes=60
- "I am done, stop focus" -> action="delete"
- "What's the deadline?" -> action="none"
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt,
            config={
                "response_mime_type": "application/json",
                "response_json_schema": FocusSessionRequest.model_json_schema(),
            },
        )

        # Parse response using Pydantic
        data = FocusSessionRequest.model_validate_json(response.text)

        if data.action == "none":
            return None

        focus_file = Path("data/focus_session.json")  # Single session file
        focus_file.parent.mkdir(exist_ok=True)

        if data.action == "add":
            # Calculate start and end times
            now = datetime.now()
            start_time = now.isoformat()
            end_time = (now + timedelta(minutes=data.duration_minutes)).isoformat()

            # Create single focus session
            focus_session = {
                "task_description": data.task_description,
                "duration_minutes": data.duration_minutes,
                "start_time": start_time,
                "end_time": end_time
            }

            # Save (overwrites any existing session)
            with open(focus_file, 'w') as f:
                json.dump(focus_session, f, indent=2)

            print(f"✅ Added focus session: {focus_session['task_description']} for {focus_session['duration_minutes']} minutes")
            return {
                "action": "add",
                "data": focus_session
            }

        elif data.action == "delete":
            # Check if session exists
            if not focus_file.exists():
                print("ℹ️ No focus session to delete")
                return {
                    "action": "delete",
                    "data": None
                }

            # Read current session before deleting
            try:
                with open(focus_file, 'r') as f:
                    deleted_session = json.load(f)
            except:
                deleted_session = None

            # Delete the file
            focus_file.unlink()

            print(f"✅ Deleted focus session: {deleted_session.get('task_description', 'Unknown') if deleted_session else 'None'}")
            return {
                "action": "delete",
                "data": deleted_session
            }

        return None

    except Exception as e:
        print(f"Error managing focus session: {str(e)}")
        return None


def capture_and_analyze_screenshot() -> Dict:
    """
    Capture a screenshot and analyze it for distractions using Gemini Vision

    Returns:
        dict: {
            "is_distraction": bool,
            "description": str,
            "distraction_type": Optional[str],
            "screenshot_path": str
        }
    """
    try:
        # Create screenshots folder
        screenshot_folder = Path("screenshots")
        screenshot_folder.mkdir(exist_ok=True)

        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        screenshot_path = screenshot_folder / f"screenshot_{timestamp}.png"

        # Capture screenshot (macOS)
        subprocess.run(["screencapture", "-x", str(screenshot_path)], check=True)

        # Read screenshot as base64
        with open(screenshot_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode()

        # Analyze screenshot with Gemini Vision
        prompt = """Analyze this screenshot and determine if the user is engaged in distracting activities.

Distracting activities include:
- Watching YouTube videos (especially entertainment, not educational)
- Playing games
- Browsing social media (Instagram, Facebook, Twitter, TikTok, Reddit for entertainment)
- Shopping websites
- Entertainment news or gossip sites
- Streaming services (Netflix, Hulu, etc.)
- Chat applications used casually (not work-related)

NOT distractions:
- Code editors, IDEs, terminals
- Educational content or documentation
- Work-related applications (Slack for work, emails, spreadsheets)
- Study materials, academic papers
- Note-taking apps

Provide:
1. is_distraction: true/false based on whether this appears to be a distraction
2. description: Detailed description of what's visible in the screenshot
3. distraction_type: If it's a distraction, specify the type (e.g., "YouTube", "Instagram", "Gaming", "Social Media")
"""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=[
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": "image/png",
                        "data": image_data
                    }
                }
            ],
            config={
                "response_mime_type": "application/json",
                "response_json_schema": DistractionAnalysis.model_json_schema(),
            },
        )

        # Parse response
        analysis = DistractionAnalysis.model_validate_json(response.text)

        result = {
            "is_distraction": analysis.is_distraction,
            "description": analysis.description,
            "distraction_type": analysis.distraction_type,
            "screenshot_path": str(screenshot_path)
        }

        # Delete screenshot immediately after analysis
        try:
            screenshot_path.unlink()
            print(f"🗑️ Screenshot deleted: {screenshot_path}")
        except Exception as del_error:
            print(f"Warning: Could not delete screenshot: {del_error}")

        return result

    except Exception as e:
        print(f"Error capturing/analyzing screenshot: {str(e)}")
        # Try to clean up screenshot if it exists
        try:
            if 'screenshot_path' in locals() and screenshot_path.exists():
                screenshot_path.unlink()
        except:
            pass

        return {
            "is_distraction": False,
            "description": f"Error: {str(e)}",
            "distraction_type": None,
            "screenshot_path": None
        }


def load_current_task():
    """
    Load current focus task from JSON file (single session)

    Returns:
        dict: Current task info with remaining time, or None if no session
    """
    focus_file = Path("data/focus_session.json")

    if not focus_file.exists():
        return None

    try:
        with open(focus_file, 'r') as f:
            session = json.load(f)

        now = datetime.now()
        end_time = datetime.fromisoformat(session["end_time"])

        # Calculate remaining time
        remaining = end_time - now
        remaining_minutes = int(remaining.total_seconds() / 60)

        # If session has expired, auto-delete it
        if remaining_minutes <= 0:
            focus_file.unlink()
            print("ℹ️ Focus session expired and was auto-deleted")
            return None

        return {
            "task_description": session["task_description"],
            "remaining_minutes": remaining_minutes,
            "end_time": session["end_time"],
            "start_time": session["start_time"]
        }

    except Exception as e:
        print(f"Error loading current task: {str(e)}")
        return None


def send_focus_notification(task_description: str, distraction_type: str = None):
    if not NOTIFICATIONS_AVAILABLE:
        print(f"📢 [Notification] Stay focused on: {task_description}")
        return

    avatar_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'avatars', 'happy_cat.png'))
    audio_path = os.path.abspath(os.path.join(os.path.dirname(__file__), 'voice', 'stayfocus.mp3'))

    if distraction_type:
        message = f"Focus on {task_description}!"
        title = f"🚨 Distraction Alert: {distraction_type}"
    else:
        message = f"Stay focused on {task_description}"
        title = "🎯 Focus Reminder"

    try:
        Notifier.notify(
            message,
            title=title,
            contentImage=avatar_path if os.path.exists(avatar_path) else None,
        )
        print(f"📬 Notification sent: {title} - {message}")

        # 🔊 Play sound asynchronously
        if os.path.exists(audio_path):
            threading.Thread(
                target=lambda: subprocess.run(["afplay", audio_path]),
                daemon=True
            ).start()

    except Exception as e:
        print(f"Error sending notification: {str(e)}")


def monitor_focus_and_notify():
    """
    Main monitoring function: captures screenshot, analyzes for distractions,
    and sends notification if user is distracted during a focus session

    Returns:
        dict: Analysis result with notification status
    """
    # Check if user has an active focus session
    current_task = load_current_task()

    # Capture and analyze screenshot
    analysis = capture_and_analyze_screenshot()

    # If both distraction detected AND active focus session exists
    if analysis["is_distraction"] and current_task:
        print(f"🚨 Distraction detected: {analysis['distraction_type']} while focusing on {current_task['task_description']}")

        # Send notification
        send_focus_notification(
            task_description=current_task['task_description'],
            distraction_type=analysis['distraction_type']
        )

        return {
            **analysis,
            "notification_sent": True,
            "current_task": current_task
        }
    elif analysis["is_distraction"]:
        print(f"ℹ️ Distraction detected but no active focus session")
        return {
            **analysis,
            "notification_sent": False,
            "current_task": None
        }
    else:
        print(f"✅ User appears focused: {analysis['description'][:100]}")
        return {
            **analysis,
            "notification_sent": False,
            "current_task": current_task
        }


if __name__ == "__main__":
    # print(manage_focus_session("do you want to have a rl focus session? do a 1 hour focus, user: yes"))
    # print(manage_focus_session("do you want to have a reinforcement learning how focus session? do a 1 hour focus, user: yes"))
    print(load_current_task())
