#!/usr/bin/env python3
"""
Standalone menu bar countdown timer
Run this as a separate process to show countdown in menu bar
"""

import sys
import rumps
from datetime import datetime, timedelta
import time

class CountdownTimer(rumps.App):
    def __init__(self, duration_minutes, session_name, motivation):
        super().__init__("⏱")
        self.duration = duration_minutes
        self.session_name = session_name
        self.motivation = motivation
        self.end_time = datetime.now() + timedelta(minutes=duration_minutes)
        self.alerted_2min = False

        # Start countdown
        self.timer = rumps.Timer(self.update_countdown, 1)
        self.timer.start()

    def update_countdown(self, _):
        remaining = self.end_time - datetime.now()

        if remaining.total_seconds() <= 0:
            # Timer complete
            self.title = "✅"

            # TTS announcement
            try:
                from tts_pipeline import queue_tts
                queue_tts(f"Your {self.session_name} session is complete. Time to take a break!")
            except:
                pass

            # Notification
            try:
                from pync import Notifier
                Notifier.notify(
                    "Time to take a break!",
                    title=f"✅ {self.session_name} Complete",
                    sound="Glass"
                )
            except:
                pass

            # Quit after 3 seconds
            time.sleep(3)
            rumps.quit_application()
            return

        # Check if 2 minutes left (only alert once)
        if 115 <= remaining.total_seconds() <= 125 and not self.alerted_2min:
            self.alerted_2min = True

            # TTS announcement
            try:
                from tts_pipeline import queue_tts
                queue_tts(f"You have 2 minutes left in your {self.session_name} session. {self.motivation}")
            except:
                pass

            # Notification
            try:
                from pync import Notifier
                Notifier.notify(
                    f"{self.motivation}",
                    title=f"⏰ {self.session_name} - 2 minutes left",
                    sound="Glass"
                )
            except:
                pass

        # Update menu bar display
        minutes = int(remaining.total_seconds() // 60)
        seconds = int(remaining.total_seconds() % 60)
        self.title = f"⏱ {minutes}:{seconds:02d}"

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: menubar_timer.py <duration_minutes> <session_name> <motivation>")
        sys.exit(1)

    duration = int(sys.argv[1])
    session_name = sys.argv[2]
    motivation = sys.argv[3]

    app = CountdownTimer(duration, session_name, motivation)
    app.run()
