from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import json
import time
import logging
import requests
import tweepy
from groq import Groq
from datetime import datetime
import threading
import re
from newsapi import NewsApiClient
import subprocess

app = Flask(__name__)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler("shorts_generator.log"), logging.StreamHandler()]
)
logger = logging.getLogger("shorts_generator")

# Default configuration
CONFIG_FILE = "config/settings.json"
DEFAULT_CONFIG = {
    "api_keys": {
        "groq_api_key": "",
        "twitter_api_key": "",
        "twitter_api_secret": "",
        "twitter_access_token": "",
        "twitter_access_secret": "",
        "elevenlabs_api_key": "",
        "unsplash_api_key": "",
        "news_api_key": "",
        "d_id_api_key": ""
    },
    "settings": {
        "content_niche": "technology",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",  # Default ElevenLabs voice
        "output_directory": "./media"
    }
}

# Ensure directories exist
for directory in ['config', 'media', 'logs', 'temp', 'scripts']:
    os.makedirs(directory, exist_ok=True)

# Load configuration
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            logger.error("Error loading config, using default")
            return DEFAULT_CONFIG
    else:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

config = load_config()

# Global state for progress and control
progress = {"step": "Idle", "message": "Ready", "files": {}, "topic": ""}
stop_event = threading.Event()

# API Functions

def fetch_trending_news():
    """Fetch a trending topic and a related news post from NewsAPI"""
    newsapi = NewsApiClient(api_key=config["api_keys"]["news_api_key"])
    category = config.get("settings", {}).get("content_category", "technology")
    response = newsapi.get_top_headlines(category=category, language='en', page_size=1)
    if response['status'] == 'ok' and response['articles']:
        article = response['articles'][0]
        trending_topic = f"{category.capitalize()} News"
        news_text = article['title'] + " - " + article['description']
    else:
        trending_topic = f"{category.capitalize()} News"
        news_text = f"No recent news found for {category}. Reporting trending topic instead."
    return trending_topic, news_text

def rephrase_as_anchor(topic, news_text):
    """Rephrase news text into a 30-second anchor-style script using Groq"""
    client = Groq(api_key=config["api_keys"]["groq_api_key"])
    prompt = (
        f"Rephrase the following news text into a concise, engaging 30-second script (3-4 sentences) i do not want placeholders for music/narrators, ONLY GIVE TEXT TO BE SPOKEN. also dont say Here is your consise segment,ONLY TALK ABOUT NEWS DIRECTLY"
        f"as if a news anchor is reporting it on air. Topic: {topic}\n\nText: {news_text}"
    )
    response = client.chat.completions.create(
        messages=[{"role": "user", "content": prompt}],
        model="llama3-8b-8192",
        max_tokens=100
    )
    return response.choices[0].message.content.strip()

def generate_audio(script, output_path):
    """Generate audio from script using ElevenLabs"""
    response = requests.post(
        f"https://api.elevenlabs.io/v1/text-to-speech/{config['settings']['voice_id']}",
        headers={"xi-api-key": config["api_keys"]["elevenlabs_api_key"]},
        json={"text": script}
    )
    if response.status_code == 200:
        with open(output_path, "wb") as f:
            f.write(response.content)
        return True
    raise Exception(f"ElevenLabs error: {response.status_code} - {response.text}")

def track_api_usage(api_name):
    """Track API usage and check if we're within limits"""
    today = datetime.now().strftime("%Y-%m-%d")
    if "api_limits" not in config:
        config["api_limits"] = {
            "groq": {"daily": 100, "used": 0, "reset_date": ""},
            "elevenlabs": {"daily": 50, "used": 0, "reset_date": ""},
            "unsplash": {"daily": 50, "used": 0, "reset_date": ""}
        }
    if config["api_limits"][api_name]["reset_date"] != today:
        config["api_limits"][api_name]["used"] = 0
        config["api_limits"][api_name]["reset_date"] = today
    if config["api_limits"][api_name]["used"] >= config["api_limits"][api_name]["daily"]:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        raise Exception(f"{api_name.capitalize()} API daily limit reached ({config['api_limits'][api_name]['daily']} calls)")
    config["api_limits"][api_name]["used"] += 1
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    return config["api_limits"][api_name]

def fetch_image(topic, output_path, source="unsplash", custom_image_path=None):
    """Get an image from various sources"""
    if source == "custom" and custom_image_path:
        with open(custom_image_path, "rb") as src, open(output_path, "wb") as dst:
            dst.write(src.read())
        return True
    elif source == "unsplash":
        response = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": topic, "client_id": config["api_keys"]["unsplash_api_key"]}
        )
        if response.status_code == 200:
            image_url = response.json()["urls"]["regular"]
            image_data = requests.get(image_url).content
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True
        raise Exception(f"Unsplash error: {response.status_code} - {response.text}")
    elif source == "ai":
        placeholder_url = f"https://via.placeholder.com/800x600.png?text={topic.replace(' ', '+')}"
        image_data = requests.get(placeholder_url).content
        with open(output_path, "wb") as f:
            f.write(image_data)
        return True

def generate_avatar_video(script_content, video_path):
    """Generate avatar video using D-ID API."""
    did_api_key = config["api_keys"]["d_id_api_key"]
    did_api_url = "https://api.d-id.com/talks"
    headers = {
        "Authorization": f"Basic {did_api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "script": {
            "type": "text",
            "input": script_content
        },
        "presenter_id": "rian-lZC6MmWfC6",
        "config": {
            "stitch": True
        }
    }

    try:
        logger.info(f"D-ID API Request: {json.dumps(data, indent=2)}")
        response = requests.post(did_api_url, headers=headers, json=data)
        logger.info(f"D-ID API Response Status: {response.status_code}")
        if response.status_code != 201:
            logger.error(f"D-ID Response Body: {response.text}")
        response.raise_for_status()
        response_data = response.json()
        logger.info(f"D-ID API Response: {json.dumps(response_data, indent=2)}")
        
        video_id = response_data.get("id")
        if not video_id:
            logger.error("Missing 'id' in D-ID response")
            return False
        
        status_url = f"https://api.d-id.com/talks/{video_id}"
        for attempt in range(30):
            time.sleep(10)
            status_response = requests.get(status_url, headers=headers)
            logger.info(f"D-ID Status (Attempt {attempt + 1}): {status_response.status_code}")
            if status_response.status_code != 200:
                logger.error(f"D-ID Status Response Body: {status_response.text}")
            status_response.raise_for_status()
            status_data = status_response.json()
            logger.info(f"D-ID Status Data: {json.dumps(status_data, indent=2)}")
            if status_data["status"] == "done":
                video_url = status_data.get("result_url")
                if not video_url:
                    logger.error("Missing 'result_url' in D-ID status")
                    return False
                logger.info(f"Downloading video from {video_url}")
                video_data = requests.get(video_url).content
                with open(video_path, "wb") as f:
                    f.write(video_data)
                return True
            elif status_data["status"] in ["error", "rejected"]:
                logger.error(f"D-ID processing failed: {status_data.get('error', 'Unknown error')}")
                return False
        logger.error("D-ID video generation timed out after 5 minutes")
        return False
    
    except requests.exceptions.RequestException as e:
        logger.error(f"D-ID API error: {e} - Response: {e.response.text if e.response else 'No response'}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return False

# Process for generating assets
def generate_assets(topic=None):
    global progress
    try:
        progress["step"] = "Fetching News"
        progress["message"] = "Fetching trending news from X..."
        trending_topic, news_text = fetch_trending_news() if not topic else (topic, f"Manual topic: {topic}")
        progress["topic"] = trending_topic
        progress["message"] = f"Found news for topic: {trending_topic}"
        time.sleep(1)

        if stop_event.is_set():
            return

        timestamp = int(time.time())
        base_filename = f"{trending_topic.lower().replace(' ', '_')}_{timestamp}"
        news_folder = os.path.join(config["settings"]["output_directory"], re.sub(r'[^\w\s-]', '', trending_topic).strip().replace(' ', '_'))
        os.makedirs(news_folder, exist_ok=True)

        progress["step"] = "Script"
        progress["message"] = "Rephrasing as news anchor script with Groq..."
        script_content = rephrase_as_anchor(trending_topic, news_text)
        script_path = os.path.join(news_folder, f"{base_filename}.txt")
        with open(script_path, "w", encoding="utf-8") as f:
            f.write(script_content)
        progress["message"] = f"Script saved to {script_path}"
        progress["files"]["script"] = os.path.relpath(script_path, '.')
        time.sleep(1)

        if stop_event.is_set():
            return

        progress["step"] = "Video"
        progress["message"] = "Generating avatar video with D-ID..."
        video_path = os.path.join(news_folder, f"{base_filename}.mp4")
        if generate_avatar_video(script_content, video_path):
            progress["message"] = f"Video saved to {video_path}"
            progress["files"]["video"] = os.path.relpath(video_path, '.')  # Ensure video path is stored
        else:
            progress["message"] = "Video generation failed."
            raise Exception("Video generation failed.")

        progress["step"] = "Done"
        progress["message"] = f"News report assets for '{trending_topic}' stored successfully."

    except Exception as e:
        progress["message"] = f"Error: {str(e)}"
        logger.error(f"Asset generation error: {e}")
    finally:
        stop_event.clear()

# Routes
@app.route('/')
def index():
    return render_template('index.html', progress=progress)

@app.route('/update_category', methods=['POST'])
def update_category():
    category = request.form.get('category', 'technology')
    if category not in ["business", "entertainment", "general", "health", "science", "sports", "technology"]:
        return jsonify({"error": "Invalid category"}), 400
    config["settings"]["content_category"] = category
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    return jsonify({"message": f"Category updated to {category}"})

@app.route('/start', methods=['POST'])
def start():
    global progress
    topic = request.form.get('topic', '').strip()
    if stop_event.is_set():
        return jsonify({"error": "Process already running"}), 400
    progress = {"step": "Starting", "message": "Initializing...", "files": {}, "topic": ""}
    stop_event.clear()
    threading.Thread(target=generate_assets, args=(topic,), daemon=True).start()
    return jsonify({"message": "Started"})

@app.route('/share', methods=['POST'])
def share_content():
    platform = request.form.get('platform', '')
    image_path = request.form.get('image', '')
    audio_path = request.form.get('audio', '')
    script_path = request.form.get('script', '')

    if not all([platform, image_path, audio_path, script_path]):
        return jsonify({"error": "Missing required files"}), 400

    try:
        with open(script_path, 'r') as f:
            script_content = f.read()

        if platform == 'twitter':
            return jsonify({
                "message": "Copy this text to share on Twitter",
                "text": script_content[:280]
            })
        elif platform == 'tiktok':
            return jsonify({
                "message": "Export as MP4 first, then upload to TikTok"
            })
    except Exception as e:
        logger.error(f"Error sharing to {platform}: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "No image file provided"}), 400
    file = request.files['image']
    if file.filename == '':
        return jsonify({"error": "No image selected"}), 400
    if file:
        filename = f"custom_{int(time.time())}.jpg"
        folder = os.path.join(config["settings"]["output_directory"], "custom_images")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, filename)
        file.save(filepath)
        return jsonify({
            "message": "Image uploaded successfully",
            "path": os.path.relpath(filepath, '.')
        })

@app.route('/stop', methods=['POST'])
def stop():
    stop_event.set()
    progress["message"] = "Stopping..."
    return jsonify({"message": "Stopping"})

@app.route('/progress')
def get_progress():
    return jsonify(progress)

@app.route('/files/<path:filename>')
def serve_file(filename):
    file_path = os.path.join(app.root_path, filename)
    base_dir = os.path.dirname(file_path)
    file_name = os.path.basename(file_path)
    if os.path.exists(file_path):
        return send_from_directory(base_dir, file_name)
    return "File not found", 404

@app.route('/export_mp4', methods=['POST'])
def export_mp4():
    image_path = request.form.get('image', '')
    audio_path = request.form.get('audio', '')

    if not all([image_path, audio_path]):
        return jsonify({"error": "Missing required files"}), 400

    try:
        timestamp = int(time.time())
        output_filename = f"news_short_{timestamp}.mp4"
        output_path = os.path.join(config["settings"]["output_directory"], output_filename)
        ffmpeg_cmd = [
            "ffmpeg", "-y",
            "-loop", "1", "-i", image_path,
            "-i", audio_path,
            "-c:v", "libx264", "-tune", "stillimage", "-c:a", "aac",
            "-b:a", "192k", "-pix_fmt", "yuv420p",
            "-shortest", output_path
        ]
        subprocess.run(ffmpeg_cmd, check=True)
        progress["files"]["video"] = os.path.relpath(output_path, '.')  # Update progress with video path
        return jsonify({
            "message": "MP4 created successfully",
            "path": output_path
        })
    except Exception as e:
        logger.error(f"Error creating MP4: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)