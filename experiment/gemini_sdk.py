# from dotenv import load_dotenv
# import os
# from google import genai


# """
# 1. enable the ai to use tools to 
#     1. add info to the context
#     2. load the info from the context 
#     3. making reminder
#     4. 
# """
# load_dotenv()  # Loads environment variables from .env

# client = genai.Client()  # Automatically finds GEMINI_API_KEY from env
# response = client.models.generate_content(
#     model="gemini-2.0-flash", contents="answer questions about what is AI like you are luffy"
# )
# print(response.text)

from dotenv import load_dotenv
import os
from google import genai
from pynput import keyboard
import mss
from PIL import Image
import base64
from io import BytesIO
import json
from datetime import datetime
import threading

load_dotenv()

# Initialize Gemini client
client = genai.Client()

# Create directories for storage
os.makedirs("screenshots", exist_ok=True)
os.makedirs("data", exist_ok=True)

def take_screenshot():
    """Capture full screenshot"""
    with mss.mss() as sct:
        # Capture primary monitor
        monitor = sct.monitors[1]
        screenshot = sct.grab(monitor)
        
        # Convert to PIL Image
        img = Image.frombytes('RGB', screenshot.size, screenshot.rgb)
        return img

def save_screenshot(img):
    """Save screenshot to file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = f"screenshots/capture_{timestamp}.png"
    img.save(filepath)
    print(f"📸 Screenshot saved: {filepath}")
    return filepath

def image_to_base64(img):
    """Convert PIL Image to base64 string"""
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_bytes = buffered.getvalue()
    return base64.b64encode(img_bytes).decode('utf-8')

def analyze_screenshot_with_gemini(img):
    """Send screenshot to Gemini for analysis"""
    print("🤔 Analyzing with Gemini 2.5 Flash...")
    
    # Convert image to base64
    img_base64 = image_to_base64(img)
    
    prompt = """Analyze this screenshot and extract any deadlines, events, appointments, or important dates.

Return ONLY valid JSON in this exact format (no markdown, no code blocks):
{
    "items": [
        {
            "title": "event name",
            "description": "brief description, try to extract the context from screenshot",
            "date": "YYYY-MM-DD or extracted date",
            "time": "HH:MM or null if not specified",
            "remind_before": "suggested reminder time, be mindful, if it is midterm should remind weeks before, hw few days before "
        }
    ]
}

If no events/dates found, return: {"items": []}"""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=[
                {
                    "role": "user",
                    "parts": [
                        {"text": prompt},
                        {
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": img_base64
                            }
                        }
                    ]
                }
            ]
        )
        
        # Extract text and clean it
        result_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if result_text.startswith("```"):
            result_text = result_text.split("```")[1]
            if result_text.startswith("json"):
                result_text = result_text[4:]
            result_text = result_text.strip()
        
        # Parse JSON
        data = json.loads(result_text)
        return data
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON parsing error: {e}")
        print(f"Raw response: {response.text}")
        return {"items": []}
    except Exception as e:
        print(f"❌ Error analyzing screenshot: {e}")
        return {"items": []}

def save_to_json(extracted_data, screenshot_path):
    """Save extracted data to JSON file"""
    json_file = "data/reminders.json"
    
    # Load existing data
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        data = {"reminders": []}
    
    # Add metadata to each item
    timestamp = datetime.now().isoformat()
    for item in extracted_data.get("items", []):
        item["captured_at"] = timestamp
        item["screenshot_path"] = screenshot_path
    
    # Append new items
    data["reminders"].extend(extracted_data.get("items", []))
    
    # Save back
    with open(json_file, 'w') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Saved {len(extracted_data.get('items', []))} items to {json_file}")
    return len(extracted_data.get("items", []))

def process_screenshot():
    """Main processing function"""
    print("\n" + "="*50)
    print("🚀 Starting screenshot capture...")
    
    # Step 1: Take screenshot
    img = take_screenshot()
    
    # Step 2: Save screenshot
    screenshot_path = save_screenshot(img)
    
    # Step 3: Analyze with Gemini
    extracted_data = analyze_screenshot_with_gemini(img)
    
    # Step 4: Save to JSON
    count = save_to_json(extracted_data, screenshot_path)
    
    if count > 0:
        print(f"🎉 Success! Extracted {count} event(s)")
        for item in extracted_data["items"]:
            print(f"   • {item['title']} - {item['date']}")
    else:
        print("ℹ️  No events found in screenshot")
    
    print("="*50 + "\n")

def on_activate():
    """Callback when hotkey is pressed"""
    # Run in separate thread to avoid blocking
    thread = threading.Thread(target=process_screenshot)
    thread.start()

# Setup keyboard listener
print("🎯 Screenshot Analyzer Ready!")
print("Press Cmd+Shift+C to capture and analyze")
print("Press Cmd+C to quit\n")

# Listen for Cmd+Shift+C
try:
    with keyboard.GlobalHotKeys({
        '<cmd>+<shift>+c': on_activate
    }) as h:
        h.join()
except KeyboardInterrupt:
    print("\n👋 Shutting down...")