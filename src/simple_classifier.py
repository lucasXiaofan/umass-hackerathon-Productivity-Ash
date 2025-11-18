"""
Simple Classifier - Minimal version for research and diary
"""

import os
import json
import base64
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

# Paths
FLOW_DIR = "/Users/xiaofanlu/Documents/road/FLOW"
DIARY_DIR = os.path.join(FLOW_DIR, "diary")
RESEARCH_FILE = os.path.join(FLOW_DIR, "projects/research-uncertainty-reasoning-agentic-path-01-10-25.md")
DIARY_TEMPLATE = "/Users/xiaofanlu/Documents/road/template/diary.md"
PAPERS_DIR = os.path.join(FLOW_DIR, "areas/papers")

# OpenRouter client
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY"),
)


def get_diary_path():
    """Get today's diary file path"""
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(DIARY_DIR, f"{today}.md")


def get_assets_dir():
    """Get assets directory under diary folder (for all images)"""
    today = datetime.now().strftime("%Y-%m-%d")
    assets_dir = os.path.join(DIARY_DIR, "assets", today)
    os.makedirs(assets_dir, exist_ok=True)
    return assets_dir


def load_all_papers():
    """Load all paper markdown files as a single string context

    Returns:
        str: Concatenated content of all paper markdown files
    """
    os.makedirs(PAPERS_DIR, exist_ok=True)

    papers_content = []

    if os.path.exists(PAPERS_DIR):
        for filename in sorted(os.listdir(PAPERS_DIR)):
            if filename.endswith('.md'):
                filepath = os.path.join(PAPERS_DIR, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                        papers_content.append(f"=== {filename} ===\n{content}\n")
                except Exception as e:
                    print(f"⚠️ Error reading {filename}: {e}")

    if papers_content:
        return "\n".join(papers_content)
    else:
        return "No papers tracked yet."


def ensure_diary():
    """Create today's diary if it doesn't exist using template"""
    diary_path = get_diary_path()

    if not os.path.exists(diary_path):
        os.makedirs(os.path.dirname(diary_path), exist_ok=True)

        # Read template
        if os.path.exists(DIARY_TEMPLATE):
            with open(DIARY_TEMPLATE, 'r', encoding='utf-8') as f:
                template = f.read()
        else:
            template = "# Daily Journal\n\n"

        with open(diary_path, 'w', encoding='utf-8') as f:
            f.write(template)

        print(f"📔 Created diary: {diary_path}")

    return diary_path


def save_image(image_base64):
    """Save image to diary assets (all images go here), return relative path"""
    assets_dir = get_assets_dir()
    today = datetime.now().strftime("%Y-%m-%d")
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]  # milliseconds
    filename = f"file-{timestamp}.png"

    filepath = os.path.join(assets_dir, filename)

    # Save image
    img_data = base64.b64decode(image_base64)
    with open(filepath, 'wb') as f:
        f.write(img_data)

    # Return relative path from diary folder: assets/YYYY-MM-DD/file-xxx.png
    rel_path = f"assets/{today}/{filename}"
    print(f"📸 Image saved: {filepath}")
    return rel_path


def classify(text_input=None, image_base64=None, model="qwen/qwen3-vl-235b-a22b-instruct"):
    """
    Classify: research or diary? Detect if new paper.

    Returns:
        dict: {
            "target": "research" or "diary",
            "content": "OCR text + description"
        }
    """

    prompt = """Classify this as 'research' or 'diary'.

If about uncertainty paper reading, experiment result, my current research relevant to medical diagonsis, so medical stuff also relevant to research → target='research'
Otherwise → target='diary'

For content:  provide 1-2 sentences of brief description of what you see. if user ask for information extraction from image, extract the markdown format of the table, latex of math formula that can fit in obsidian,
"""

    message_content = [{"type": "text", "text": prompt}]

    if text_input:
        message_content.append({"type": "text", "text": f"\nText: {text_input}"})

    if image_base64:
        message_content.append({
            "type": "image_url",
            "image_url": {"url": f"data:image/png;base64,{image_base64}"}
        })

    # JSON Schema
    response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "classification",
            "strict": True,
            "schema": {
                "type": "object",
                "properties": {
                    "target": {"type": "string", "enum": ["research", "diary"]},
                    "content": {"type": "string"}
                },
                "required": ["target", "content"],
                "additionalProperties": False
            }
        }
    }

    print("🤖 Classifying...")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": message_content}],
            response_format=response_format,
            temperature=0.3
        )

        return json.loads(response.choices[0].message.content)

    except Exception as e:
        print(f"⚠️  Error: {e}")
        return {
            "target": "diary",
            "content": text_input or "Classification error"
        }


def append_to_file(file_path, user_comment, ai_content, image_path=None):
    """Append content to file with separated user comment and AI output"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    append_text = f"\n### {timestamp}\n"

    # User comment section
    if user_comment:
        append_text += f"{user_comment}\n"

    # AI analysis section (only if provided)
    if ai_content:
        append_text += f"**AI Analysis:**\n{ai_content}\n"

    # Image attachment
    if image_path:
        append_text += f"![]({image_path})\n"

    with open(file_path, 'a', encoding='utf-8') as f:
        f.write(append_text)

    print(f"✅ Updated: {file_path}")


def process(text_input=None, image_base64=None):
    """
    Main function: classify and append

    Args:
        text_input: User text (optional)
        image_base64: Screenshot (optional)

    Returns:
        dict: Result
    """

    print("\n" + "="*60)
    print("🎯 SIMPLE CLASSIFIER")
    print("="*60)

    # If text-only (no image), skip AI and just append text directly
    if text_input and not image_base64:
        print("📝 Text-only input - skipping AI classification")

        # Simple heuristic: if mentions research/paper/uncertainty, go to research
        if any(word in text_input.lower() for word in ['research', 'paper', 'uncertainty', 'experiment', 'ml', 'ai']):
            file_path = RESEARCH_FILE
            target = 'research'
        else:
            file_path = ensure_diary()
            target = 'diary'

        print(f"📋 Target: {target}")

        # Append just the user text, no AI analysis
        append_to_file(file_path, text_input, None, None)

        return {
            "target": target,
            "file": file_path,
            "user_comment": text_input,
            "ai_content": None,
            "image": None
        }

    # For images, use AI classification
    result = classify(text_input, image_base64,model="x-ai/grok-4-fast")
    print(f"📋 Target: {result['target']}")

    # Save image if provided (always to diary assets)
    image_rel_path = None
    if image_base64:
        image_rel_path = save_image(image_base64)

    # Determine file
    if result['target'] == 'research':
        file_path = RESEARCH_FILE
    else:
        file_path = ensure_diary()

    # Append with separated user comment and AI analysis
    append_to_file(file_path, text_input, result['content'], image_rel_path)

    return {
        "target": result['target'],
        "file": file_path,
        "user_comment": text_input,
        "ai_content": result['content'],
        "image": image_rel_path
    }


# Shortcuts
def shortcut_text(text):
    """Text only"""
    return process(text_input=text)


def shortcut_screenshot(image_base64, comment=""):
    """Screenshot + optional comment"""
    return process(text_input=comment if comment else None, image_base64=image_base64)


if __name__ == "__main__":
    print("Testing...")
    result = shortcut_text("Working on uncertainty reasoning in LLMs")
    print(f"\n{json.dumps(result, indent=2)}")
