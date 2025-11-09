import gradio as gr
import base64
import os
import threading
import time
from datetime import datetime
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv
from docling_extractor import extract_pdf_to_markdown
from focus_helper import (
    manage_focus_session,
    load_current_task,
    monitor_focus_and_notify,
    send_focus_notification,
    capture_and_analyze_screenshot
)
from voiceengine import generate_speech_for_text, text_to_speech

# Load environment variables
load_dotenv()

# Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY")
client = genai.Client(api_key=api_key)

def process_pdf_direct(pdf_file):
    """Send PDF directly to Gemini vision"""
    try:
        # Handle different file input types
        if hasattr(pdf_file, 'name'):
            # If it's a file object with a name attribute
            file_path = pdf_file.name
        else:
            # If it's already a path string
            file_path = pdf_file

        with open(file_path, 'rb') as f:
            pdf_data = base64.b64encode(f.read()).decode()

        response = client.models.generate_content(
            model="gemini-2.0-flash-exp",
            contents=[
                {"text": """Extract all important information from this PDF and format it as clean markdown. Include:
                - Main topics and key points
                - Any deadlines, dates, or time-sensitive information
                - Important names, numbers, or data
                - Action items or requirements

                Format the response using proper markdown formatting with headers (##, ###), bullet points, and emphasis where appropriate."""},
                {
                    "inline_data": {
                        "mime_type": "application/pdf",
                        "data": pdf_data
                    }
                }
            ]
        )

        return response.text
    except Exception as e:
        return f"Error processing PDF: {str(e)}"


def process_pdf_docling(pdf_file):
    """Extract PDF using Docling"""
    try:
        # Handle different file input types
        if hasattr(pdf_file, 'name'):
            file_path = pdf_file.name
        else:
            file_path = pdf_file

        # Use docling to extract markdown
        markdown_content = extract_pdf_to_markdown(file_path)

        return markdown_content
    except Exception as e:
        return f"Error processing PDF with Docling: {str(e)}"



def chat_with_context(message, history, pdf_content, auto_play_voice=False):
    """Handle chat with PDF context"""
    if not message.strip():
        return history, history, pdf_content, None

    # Get current date and time information
    now = datetime.now()
    current_date = now.strftime("%Y-%m-%d")  # e.g., 2024-03-15
    current_time = now.strftime("%H:%M:%S")  # e.g., 14:30:45
    current_weekday = now.strftime("%A")     # e.g., Monday

    # Format datetime context
    datetime_context = f"Current Date: {current_date} ({current_weekday})\nCurrent Time: {current_time}"

    # Check if user wants to manage a focus session (add or delete)
    focus_result = manage_focus_session(f"{history} user current message: {message} ")
    # Get relevant context from memory
    relevant_context = ""
    try:
        relevant_context = rag_query(message)
    except:
        print(f"failed to get relevant context")

    prompt = f"""
You are Ash, a friendly and helpful personal assistant for students.
Your job is to help students manage their time, deadlines, and reminders in a casual, supportive way.
Be conversational, encouraging, and use phrases like "we got this!" and "I'm here to help".
Keep responses concise (3-5 sentences max) and actionable.
{datetime_context}

if time is during 11pm - 4am remind user to take a sleep

{focus_result}


relevant context: {relevant_context}

User question: {message}

Please provide a helpful response."""

    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )
        bot_response = response.text
    except Exception as e:
        bot_response = f"Error: {str(e)}"

    history.append((message, bot_response))
    
    # Generate audio for the bot response
    audio_file = None
    try:
        audio_file = generate_speech_for_text(bot_response, auto_play=auto_play_voice)
    except Exception as e:
        print(f"Error generating speech: {e}")
    
    return history, history, pdf_content, audio_file

def handle_pdf_upload(pdf_file, chat_history, extraction_method, auto_play_voice=False):
    """Process uploaded PDF, save markdown, and post to chat"""
    if pdf_file is None:
        return None, "No PDF uploaded", chat_history, chat_history, None

    # Extract content from PDF based on selected method
    if extraction_method == "Docling (Fast, Local)":
        extracted_content = process_pdf_docling(pdf_file)
        method_label = "Docling"
    else:  # LLM extraction
        extracted_content = process_pdf_direct(pdf_file)
        method_label = "LLM (Gemini)"

    # Create markdown folder if it doesn't exist
    markdown_folder = Path("memory")
    markdown_folder.mkdir(exist_ok=True)

    # Generate descriptive filename with timestamp
    timestamp = datetime.now()
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    pdf_filename = Path(pdf_file.name).stem
    markdown_filename = f"{pdf_filename}_{timestamp_str}.md"
    markdown_path = markdown_folder / markdown_filename

    # Save markdown file
    audio_file = None
    try:
        with open(markdown_path, 'w', encoding='utf-8') as f:
            f.write(f"# PDF Extraction: {pdf_filename}\n\n")
            f.write(f"**Processed on:** {timestamp.strftime('%Y-%m-%d at %I:%M:%S %p')}\n\n")
            f.write("---\n\n")
            f.write(extracted_content)

        # Format message for chat with timestamp
        chat_message = f"**📄 PDF Processed:** {pdf_filename}\n\n"
        chat_message += f"**🕐 Time:** {timestamp.strftime('%Y-%m-%d at %I:%M:%S %p')}\n\n"
        chat_message += f"**⚙️ Method:** {method_label}\n\n"
        chat_message += f"**💾 Saved to:** `{markdown_path}`\n\n"
        chat_message += "---\n\n"
        chat_message += extracted_content

        # Add to chat history
        chat_history.append((f"📎 Uploaded: {pdf_filename}", chat_message))

        status_msg = f"✅ PDF processed and saved to {markdown_path}"
        
        # Generate voice for status message if auto-play is enabled
        if auto_play_voice:
            try:
                status_text = f"PDF {pdf_filename} processed and saved successfully"
                audio_file = generate_speech_for_text(status_text, auto_play=True)
            except Exception as e:
                print(f"Error generating speech for PDF status: {e}")

    except Exception as e:
        status_msg = f"❌ Error saving markdown: {str(e)}"
        chat_history.append((f"📎 Uploaded: {pdf_filename}", f"Error: {str(e)}"))

    return extracted_content, status_msg, chat_history, chat_history, audio_file

def rag_query(query):
    """
    RAG function using Gemini to retrieve relevant content from memory folder

    Args:
        query: Current query string

    Returns:
        str: Relevant content from markdown files
    """
    memory_folder = Path("memory")

    # Get all markdown files
    md_files = list(memory_folder.glob("*.md"))

    if not md_files:
        return "No markdown files found in memory folder."

    # Read all markdown files
    all_content = []
    total_chars = 0

    for md_file in md_files:
        try:
            with open(md_file, 'r', encoding='utf-8') as f:
                content = f.read()
                total_chars += len(content)
                all_content.append({
                    'filename': md_file.name,
                    'content': content
                })
        except Exception as e:
            print(f"Error reading {md_file}: {str(e)}")
    print(f"total character is {total_chars}")
    # If total characters less than 700,000, return everything
    if total_chars < 700000:
        result = ""
        for item in all_content:
            result += f"\n\n## From {item['filename']}\n\n{item['content']}\n\n---\n"
        # print(f"raw context: {result.strip()}")
        return result.strip()

    # If 700,000 or more characters, use Gemini RAG to find relevant content
    try:
        # Prepare context with all files
        context_parts = []
        for idx, item in enumerate(all_content):
            context_parts.append(f"### Document {idx+1}: {item['filename']}\n{item['content']}\n")

        full_context = "\n\n".join(context_parts)

        # Use Gemini to extract relevant information
        prompt = f"""Based on the following documents and the user's query, extract and return ONLY the relevant content that answers or relates to the query.

User Query: {query}

Documents:
{full_context}

Instructions:
1. Identify which documents or sections are most relevant to the query
2. Return the relevant content with proper attribution (mention which document it came from)
3. If multiple documents are relevant, include all relevant parts
4. Format the response clearly with document names as headers
5. If no documents are directly relevant, return the most potentially useful information

Return only the relevant extracted content, properly formatted."""

        response = client.models.generate_content(
            model="gemini-2.5-flash-lite",
            contents=prompt
        )

        return response.text

    except Exception as e:
        # Fallback to returning all content if RAG fails
        print(f"RAG error: {str(e)}, returning all content")
        result = ""
        for item in all_content:
            result += f"\n\n## From {item['filename']}\n\n{item['content']}\n\n---\n"
        # print(f"raged context: {result.strip()}")

        return result.strip()


def generate_voice_response(text):
    """Generate voice response using voiceengine"""
    try:
        audio_file = generate_speech_for_text(text, auto_play=False)
        return audio_file
    except Exception as e:
        print(f"Error generating voice response: {e}")
        return None


def list_knowledge_sources():
    """
    List all available knowledge sources in the memory folder

    Returns:
        str: Formatted markdown string listing all sources
    """
    memory_folder = Path("memory")

    if not memory_folder.exists():
        return "📂 No knowledge sources available yet. Upload some PDFs to get started!"

    md_files = sorted(memory_folder.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)

    if not md_files:
        return "📂 No knowledge sources available yet. Upload some PDFs to get started!"

    # Build formatted list
    output = f"## 📚 Available Knowledge Sources ({len(md_files)} files)\n\n"

    for idx, md_file in enumerate(md_files, 1):
        # Get file stats
        stat = md_file.stat()
        size_kb = stat.st_size / 1024
        modified_time = datetime.fromtimestamp(stat.st_mtime)

        # Format modification time
        time_str = modified_time.strftime("%Y-%m-%d %I:%M %p")

        # Add to output
        output += f"**{idx}. {md_file.stem}**\n"
        output += f"   - 📅 Added: {time_str}\n"
        output += f"   - 💾 Size: {size_kb:.1f} KB\n"
        output += f"   - 📁 File: `{md_file.name}`\n\n"

    output += "\n---\n\n"
    output += "💡 **Tip:** All these sources are automatically used when you ask questions!"

    return output


# Background monitoring thread
monitoring_active = True

def background_focus_monitor():
    """
    Background thread that monitors for distractions every 25 seconds
    Only runs when there is an active focus task
    """
    global monitoring_active
    print("🎯 Focus monitoring started (checking every 25 seconds)...")

    while monitoring_active:
        try:
            # Check if there's an active focus task
            current_task = load_current_task()

            if current_task:
                # Only monitor if there's an active task
                print(f"📋 Active task: {current_task['task_description']} ({current_task['remaining_minutes']} min remaining)")

                # Run the monitoring and notification function
                result = monitor_focus_and_notify()

                # Log result
                if result.get("notification_sent"):
                    print(f"📬 Notification sent for distraction: {result.get('distraction_type')}")
                else:
                    print(f"✅ Monitoring check complete - Status: {'Distracted' if result.get('is_distraction') else 'Focused'}")
            else:
                # No active task, skip monitoring
                print("💤 No active focus task - monitoring paused")

        except Exception as e:
            print(f"❌ Error in background monitor: {str(e)}")

        # Wait 25 seconds before next check
        time.sleep(10)

    print("🛑 Focus monitoring stopped")


# Start background monitoring thread
monitor_thread = threading.Thread(target=background_focus_monitor, daemon=True)
monitor_thread.start()


# Helper function to convert image to base64 for CSS (defined early for use in component initialization)
def image_to_base64(image_path):
    """Convert image file to base64 data URL for use in CSS"""
    if not image_path or not os.path.exists(image_path):
        return None
    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
            base64_data = base64.b64encode(image_data).decode('utf-8')
            # Determine MIME type from file extension
            ext = Path(image_path).suffix.lower()
            mime_types = {
                '.jpg': 'image/jpeg',
                '.jpeg': 'image/jpeg',
                '.png': 'image/png',
                '.webp': 'image/webp',
                '.gif': 'image/gif'
            }
            mime_type = mime_types.get(ext, 'image/jpeg')
            return f"data:{mime_type};base64,{base64_data}"
    except Exception as e:
        print(f"Error converting image to base64: {e}")
        return None


# Create custom CSS with background image support
custom_css = """
.chat-container {
    border-radius: 10px;
    padding: 10px;
}
.anime-container {
    border-radius: 10px;
    padding: 10px;
    background-size: cover;
    background-position: center;
    background-repeat: no-repeat;
    transition: background-image 0.5s ease-in-out;
    min-height: 600px;
    position: relative;
}
.character-image-wrapper {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
.character-image-wrapper img {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    margin: 0 !important;
}
#character-image-container {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
#character-image-container > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
#character-image-container > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
/* Remove all Gradio default styling from image component */
[data-testid="image"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="image"] > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
[data-testid="image"] img {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    display: block !important;
    margin: 0 !important;
}
/* Remove backgrounds from all possible Gradio containers */
.gradio-image, .gradio-image > div, .gradio-image > div > div {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
    margin: 0 !important;
}
/* Target any divs inside the character container */
#character-image-container * {
    background: transparent !important;
}
#character-image-container *:not(#character-image-container) {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
/* Ensure the image itself has no background */
#character-image-container img,
#character-image-container > * img,
#character-image-container > * > * img {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
}
"""

# Create the Gradio interface
with gr.Blocks(theme=gr.themes.Soft(), css=custom_css) as demo:
    gr.Markdown(
        """
        # 🎯 Proactive Companion Ash
        Your friendly AI assistant for managing tasks, deadlines, and staying focused!
        Upload PDFs to build your knowledge base and chat about anything.
        """
    )
    
    # Hidden state to store PDF content and voice settings
    pdf_content_state = gr.State("")
    last_audio_file = gr.State(None)
    
    with gr.Row():
        # Left column: Chat section
        with gr.Column(scale=3, elem_classes="chat-container"):
            gr.Markdown("### 💬 Chat Interface")
            
            chatbot = gr.Chatbot(
                height=500,
                label="Conversation"
            )
            
            with gr.Row():
                msg = gr.Textbox(
                    label="Your Message",
                    placeholder="Ask anything about the uploaded PDF...",
                    scale=5,
                    lines=2
                )
                send_btn = gr.Button("📤 Send", scale=1, variant="primary")
            
            with gr.Row():
                pdf_upload = gr.File(
                    label="📎 Upload PDF Document",
                    file_types=[".pdf"]
                )
                clear_btn = gr.Button("🗑️ Clear Chat", scale=1)

            extraction_method = gr.Radio(
                label="⚙️ Extraction Method",
                choices=["Docling (Fast, Local)", "LLM (Gemini - AI Powered)"],
                value="Docling (Fast, Local)",
                info="Choose how to extract content from PDF"
            )

            pdf_status = gr.Textbox(
                label="Status",
                interactive=False,
                lines=2
            )

            # Knowledge sources section
            with gr.Accordion("📚 Knowledge Base Sources", open=False):
                knowledge_sources_display = gr.Markdown(
                    value=list_knowledge_sources(),
                    label="Available Sources"
                )
                refresh_sources_btn = gr.Button("🔄 Refresh Sources", size="sm")
        
        # Right column: Anime display section
        with gr.Column(scale=2, elem_classes="anime-container", elem_id="anime-container"):
            # Use absolute path for initial image and background
            base_dir = Path(__file__).parent
            initial_image = str(base_dir / "images" / "A_1.png")
            initial_bg = str(base_dir / "images" / "happy landscape.jpg")
            
            # Convert initial background to base64 for CSS
            def get_initial_bg_css():
                bg_data_url = image_to_base64(initial_bg)
                if bg_data_url:
                    bg_url = bg_data_url
                else:
                    # Fallback to relative path
                    try:
                        initial_bg_path = Path(initial_bg)
                        initial_bg_abs = initial_bg_path.resolve()
                        initial_bg_rel = str(initial_bg_abs.relative_to(base_dir.resolve())).replace('\\', '/')
                        bg_url = f"/{initial_bg_rel}"
                    except:
                        bg_url = "/images/happy landscape.jpg"
                
                return f"""
                <style>
                #character-image-container {{
                    background-image: url('{bg_url}');
                    background-size: cover;
                    background-position: center;
                    background-repeat: no-repeat;
                    transition: background-image 0.5s ease-in-out;
                    border-radius: 10px;
                    padding: 20px;
                    min-height: 400px;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                }}
                #character-image-container img {{
                    background: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                    display: block !important;
                }}
                #character-image-container > div {{
                    background: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                }}
                #character-image-container > div > div {{
                    background: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                }}
                /* Remove all backgrounds from nested elements */
                #character-image-container * {{
                    background: transparent !important;
                }}
                #character-image-container *:not(#character-image-container) {{
                    background: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                }}
                /* Ensure image has no background */
                #character-image-container img,
                #character-image-container > * img,
                #character-image-container > * > * img {{
                    background: transparent !important;
                    border: none !important;
                    box-shadow: none !important;
                }}
                </style>
                """
            
            # HTML component to hold dynamic CSS for background
            background_style = gr.HTML(
                value=get_initial_bg_css(),
                visible=False
            )
            
            gr.Markdown("### 🎭 AI Companion")
            
            # Character image container with background
            with gr.Column(elem_id="character-image-container", elem_classes="character-image-wrapper"):
                anime_image = gr.Image(
                    label="Character Display",
                    height=400,
                    value=initial_image,
                    show_label=False,
                    type="filepath",
                    container=False
                )
            
            # Hidden component to store background image path
            background_state = gr.State(value=initial_bg)
            
            gr.Markdown("#### 🔊 Voice Features")
            
            audio_output = gr.Audio(
                label="Assistant Voice",
                autoplay=False,
                visible=True
            )
            
            with gr.Row():
                tts_btn = gr.Button("🔊 Speak Last Response", scale=2)
                voice_toggle = gr.Checkbox(label="Auto-play voice", value=False, scale=1)
            
            voice_input = gr.Audio(
                label="🎤 Voice Input (Coming Soon)",
                visible=False  # Hide until implemented
            )
            
            # Character selection (optional feature)
            gr.Markdown("#### 🎨 Companion Settings")
            character_image_upload = gr.Image(
                label="Upload Custom Character Image",
                height=150
            )
    
    # State to maintain chat history
    chat_state = gr.State([])
    
    # Event handlers
    def send_message(message, history, pdf_content, auto_play):
        return chat_with_context(message, history, pdf_content, auto_play)
    
    # Helper function to convert absolute path to relative path for Gradio
    def get_relative_bg_path(absolute_path):
        """Convert absolute path to relative path that Gradio can serve"""
        if not absolute_path:
            return None
        base_dir = Path(__file__).parent
        try:
            abs_path = Path(absolute_path).resolve()
            rel_path = abs_path.relative_to(base_dir)
            return str(rel_path).replace('\\', '/')
        except:
            # If relative path calculation fails, try to extract from absolute
            if 'images' in absolute_path:
                parts = absolute_path.split('images')
                if len(parts) > 1:
                    return f"images{parts[1]}"
            return None
    
    def update_background_wrapper(chat_history, state, pdf_content, char_image, bg_image):
        # Convert image to base64 data URL for reliable CSS background
        bg_data_url = image_to_base64(bg_image)
        
        if not bg_data_url:
            # Fallback to relative path if base64 conversion fails
            rel_bg = get_relative_bg_path(bg_image)
            bg_url = f"/{rel_bg}" if rel_bg else bg_image
        else:
            bg_url = bg_data_url
        
        # Create CSS style tag to update background (pure Python, no JavaScript)
        css_html = f"""
        <style>
        #character-image-container {{
            background-image: url('{bg_url}');
            background-size: cover;
            background-position: center;
            background-repeat: no-repeat;
            transition: background-image 0.5s ease-in-out;
            border-radius: 10px;
            padding: 20px;
            min-height: 400px;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        #character-image-container img {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
            display: block !important;
        }}
        #character-image-container > div {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        #character-image-container > div > div {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        /* Remove all backgrounds from nested elements */
        #character-image-container * {{
            background: transparent !important;
        }}
        #character-image-container *:not(#character-image-container) {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        /* Ensure image has no background */
        #character-image-container img,
        #character-image-container > * img,
        #character-image-container > * > * img {{
            background: transparent !important;
            border: none !important;
            box-shadow: none !important;
        }}
        </style>
        """
        
        return chat_history, state, pdf_content, char_image, bg_image, css_html
    
    send_btn.click(
        send_message,
        inputs=[msg, chat_state, pdf_content_state, voice_toggle],
        outputs=[chatbot, chat_state, pdf_content_state, last_audio_file]
    ).then(
        lambda: "",
        outputs=[msg]
    ).then(
        lambda audio_file: audio_file if audio_file else gr.update(),
        inputs=[last_audio_file],
        outputs=[audio_output]
    )
    
    msg.submit(
        send_message,
        inputs=[msg, chat_state, pdf_content_state, voice_toggle],
        outputs=[chatbot, chat_state, pdf_content_state, last_audio_file]
    ).then(
        lambda: "",
        outputs=[msg]
    ).then(
        lambda audio_file: audio_file if audio_file else gr.update(),
        inputs=[last_audio_file],
        outputs=[audio_output]
    )
    
    pdf_upload.change(
        handle_pdf_upload,
        inputs=[pdf_upload, chat_state, extraction_method, voice_toggle],
        outputs=[pdf_content_state, pdf_status, chatbot, chat_state, last_audio_file]
    ).then(
        list_knowledge_sources,
        outputs=[knowledge_sources_display]
    ).then(
        lambda audio_file: audio_file if audio_file else gr.update(),
        inputs=[last_audio_file],
        outputs=[audio_output]
    )
    
    clear_btn.click(
        lambda: ([], [], "", None),
        outputs=[chatbot, chat_state, pdf_content_state, last_audio_file]
    ).then(
        lambda: "Chat cleared!",
        outputs=[pdf_status]
    )
    
    character_image_upload.change(
        lambda img: img,
        inputs=[character_image_upload],
        outputs=[anime_image]
    )
    
    # TTS button handler - speak last response
    def speak_last_response(history):
        """Generate speech for the last bot response"""
        if not history or len(history) == 0:
            return None
        
        # Get the last bot response
        last_message_pair = history[-1]
        if len(last_message_pair) >= 2:
            last_bot_response = last_message_pair[1]
            try:
                audio_file = generate_voice_response(last_bot_response)
                return audio_file
            except Exception as e:
                print(f"Error generating speech: {e}")
                return None
        return None
    
    tts_btn.click(
        speak_last_response,
        inputs=[chat_state],
        outputs=[audio_output]
    )

    # Refresh knowledge sources button
    refresh_sources_btn.click(
        list_knowledge_sources,
        outputs=[knowledge_sources_display]
    )

if __name__ == "__main__":
    import socket
    
    def find_free_port(start_port=7860, max_attempts=10):
        """Find an available port starting from start_port"""
        for i in range(max_attempts):
            port = start_port + i
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.bind(('', port))
                    return port
            except OSError:
                continue
        return None
    
    print("🚀 Starting Gradio app...")
    print("📝 Make sure to set your GEMINI_API_KEY in .env file or environment variables")
    
    # Try to find an available port
    port = find_free_port(7860)
    if port is None:
        print("⚠️ Could not find an available port, using default 7860")
        port = 7860
    else:
        print(f"📡 Using port {port}")
    
    demo.launch(
        share=False,
        server_name="0.0.0.0",
        server_port=port,
        show_error=True
    )