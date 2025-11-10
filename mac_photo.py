import os
import base64
from openai import OpenAI
import osxphotos
from PIL import Image
from pillow_heif import register_heif_opener
import tempfile

# Register HEIF opener for PIL
register_heif_opener()

# Get photos database
from dotenv import load_dotenv
load_dotenv()
photosdb = osxphotos.PhotosDB()
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)

# Get all downloaded photos and sort by date
downloaded_photos = [photo for photo in photosdb.photos() if not photo.ismissing]

if not downloaded_photos:
    print("No locally downloaded photos found!")
    exit()

# Sort by date (newest first) and get the latest
downloaded_photos.sort(key=lambda x: x.date, reverse=True)
latest_photo = downloaded_photos[0]

print(f"Found latest downloaded photo: {latest_photo.original_filename}")
print(f"Date: {latest_photo.date}")
print(f"Is screenshot: {latest_photo.screenshot}")

# Use a temporary directory that will be cleaned up
with tempfile.TemporaryDirectory() as export_path:
    try:
        # Export with overwrite to avoid duplicates
        exported_files = latest_photo.export(export_path, overwrite=True)
        
        if not exported_files:
            print("Export failed!")
            exit()
        
        photo_path = exported_files[0]
        print(f"Exported to: {photo_path}")
        
        # Open image with PIL
        img = Image.open(photo_path)
        
        # Convert HEIC to JPEG in memory
        if photo_path.lower().endswith('.heic'):
            jpeg_path = os.path.join(export_path, "converted.jpg")
            img.save(jpeg_path, 'JPEG')
            photo_path = jpeg_path
            print(f"Converted to JPEG")
        
        img.show()
        print(f"Image size: {img.size}")
        
        # Encode image
        with open(photo_path, "rb") as f:
            base64_image = base64.b64encode(f.read()).decode('utf-8')
        
        # Send to LLM
        response = client.chat.completions.create(
            model="openrouter/polaris-alpha",
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Describe this image in a paragraph with key details, if the photo is a screenshot and have text, extract the text"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}}
                ]
            }]
        )
        
        print(f"\nDescription:\n{response.choices[0].message.content}")
        
    except Exception as e:
        print(f"Error: {e}")
    
    # Temporary directory and all files are automatically deleted here