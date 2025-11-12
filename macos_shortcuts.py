#!/usr/bin/env python3
import sys
import shutil
from pathlib import Path
from datetime import datetime

def main():
    if len(sys.argv) < 3:
        print("Usage: script.py <screenshot_path> <user_input>")
        sys.exit(1)
    
    screenshot_path = sys.argv[1]
    user_input = sys.argv[2]
    
    # Replace spaces with underscores
    filename = user_input.replace(' ', '_')
    
    # Add timestamp (optional)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    
    # Set your save directory
    save_dir = Path.home() / "Pictures" / "Screenshots"
    save_dir.mkdir(exist_ok=True)
    
    # Create final filename
    final_path = save_dir / f"{filename}_{timestamp}.png"
    
    # Copy/move the screenshot
    shutil.copy(screenshot_path, final_path)
    
    print(f"Saved: {final_path}")

if __name__ == "__main__":
    main()