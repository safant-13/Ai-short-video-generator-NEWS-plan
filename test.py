import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, simpledialog
import threading
import json
import os
import time
import logging
import requests
from datetime import datetime
import sys
import subprocess
import webbrowser
import tweepy
from groq import Groq

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("shorts_generator.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("shorts_generator")

# Default configuration
DEFAULT_CONFIG = {
    "api_keys": {
        "groq_api_key": "",
        "twitter_api_key": "",
        "twitter_api_secret": "",
        "twitter_access_token": "",
        "twitter_access_secret": "",
        "elevenlabs_api_key": "",
        "unsplash_api_key": ""
    },
    "settings": {
        "content_niche": "technology",
        "trend_analysis_interval_minutes": 60,
        "topics_per_run": 3,
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "video_format": "mp4",
        "output_directory": "./output"
    }
}

# Ensure directories exist
for directory in ['config', 'output', 'logs', 'temp', 'scripts', 'media']:
    os.makedirs(directory, exist_ok=True)

CONFIG_FILE = "config/settings.json"

# Load configuration or create default
def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            logger.error(f"Error loading config, using default")
            return DEFAULT_CONFIG
    else:
        # Save default config
        with open(CONFIG_FILE, 'w') as f:
            json.dump(DEFAULT_CONFIG, f, indent=4)
        return DEFAULT_CONFIG

# Save configuration
def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=4)
    logger.info("Configuration saved")

# Check for required Python packages
def check_dependencies():
    required_packages = [
        "requests", "tweepy", "bs4", "groq", "elevenlabs", 
        "pandas", "pillow", "moviepy", "schedule"
    ]
    
    missing_packages = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing_packages.append(package)
    
    if missing_packages:
        return False, missing_packages
    return True, []

# Install missing dependencies
def install_dependencies(missing_packages):
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing_packages)
        return True
    except subprocess.CalledProcessError:
        return False

# Main application class
class ShortsGeneratorApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Automated Shorts Generator")
        self.root.geometry("900x700")
        self.root.minsize(800, 600)
        
        # Load configuration
        self.config = load_config()
        
        # Create the notebook (tabs)
        self.notebook = ttk.Notebook(root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create tabs
        self.setup_dashboard_tab()
        self.setup_api_keys_tab()
        self.setup_settings_tab()
        self.setup_logs_tab()
        
        # Initialize status
        self.status_var = tk.StringVar()
        self.status_var.set("Ready")
        self.status_bar = ttk.Label(root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
        # Add some styling
        style = ttk.Style()
        style.configure("TButton", padding=6, relief="flat", background="#ccc")
        
        # Check dependencies on startup
        self.check_and_install_dependencies()
        
        # Bind closing event
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        
        # Generator thread
        self.generator_thread = None
        self.stop_event = threading.Event()

    def check_and_install_dependencies(self):
        """Check for required dependencies and offer to install missing ones"""
        deps_ok, missing = check_dependencies()
        if not deps_ok:
            missing_str = ", ".join(missing)
            response = messagebox.askyesno(
                "Missing Dependencies", 
                f"The following packages are missing: {missing_str}\n\nDo you want to install them now?"
            )
            if response:
                self.status_var.set("Installing dependencies...")
                self.root.update()
                
                success = install_dependencies(missing)
                if success:
                    self.status_var.set("Dependencies installed successfully!")
                    messagebox.showinfo("Success", "All dependencies installed successfully!")
                else:
                    self.status_var.set("Failed to install dependencies.")
                    messagebox.showerror("Error", "Failed to install dependencies. Please install them manually.")
            else:
                messagebox.showwarning("Warning", "The application may not function correctly without required dependencies.")

    def setup_dashboard_tab(self):
        """Create the dashboard tab"""
        dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(dashboard_frame, text="Dashboard")
        
        # Header
        header_frame = ttk.Frame(dashboard_frame)
        header_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(header_frame, text="Shorts Generator Dashboard", font=("Helvetica", 16, "bold")).pack(side=tk.LEFT)
        
        # Controls frame
        controls_frame = ttk.LabelFrame(dashboard_frame, text="Generator Controls")
        controls_frame.pack(fill=tk.X, padx=10, pady=5)
        
        # Buttons
        button_frame = ttk.Frame(controls_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.start_button = ttk.Button(button_frame, text="Start Generator", command=self.start_generator)
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.stop_button = ttk.Button(button_frame, text="Stop Generator", command=self.stop_generator, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(button_frame, text="Generate Single Video", command=self.generate_single_video).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Open Output Folder", command=self.open_output_folder).pack(side=tk.RIGHT, padx=5)
        
        # Status frame
        status_frame = ttk.LabelFrame(dashboard_frame, text="Status")
        status_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add a progress area (Text widget with scrollbar)
        self.progress_text = scrolledtext.ScrolledText(status_frame, wrap=tk.WORD, height=10)
        self.progress_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        self.progress_text.config(state=tk.DISABLED)
        
        # Recent videos frame
        videos_frame = ttk.LabelFrame(dashboard_frame, text="Recent Videos")
        videos_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Add a treeview for recent videos
        columns = ("Title", "Duration", "Created", "File")
        self.videos_tree = ttk.Treeview(videos_frame, columns=columns, show="headings")
        
        # Set column headings
        for col in columns:
            self.videos_tree.heading(col, text=col)
            if col == "Title":
                self.videos_tree.column(col, width=250, minwidth=150)
            elif col == "File":
                self.videos_tree.column(col, width=250, minwidth=100)
            else:
                self.videos_tree.column(col, width=100, minwidth=80)
        
        self.videos_tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add right-click menu for videos
        self.video_menu = tk.Menu(self.root, tearoff=0)
        self.video_menu.add_command(label="Open Video", command=self.open_selected_video)
        self.video_menu.add_command(label="Open Folder", command=self.open_video_folder)
        self.video_menu.add_separator()
        self.video_menu.add_command(label="Delete", command=self.delete_selected_video)
        
        self.videos_tree.bind("<Button-3>", self.show_video_menu)
        
        # Load recent videos
        self.load_recent_videos()
    def fetch_trending_topic(self):
        """Fetch a trending topic from X using the Twitter API"""
        api_key = self.config["api_keys"]["twitter_api_key"]
        api_secret = self.config["api_keys"]["twitter_api_secret"]
        access_token = self.config["api_keys"]["twitter_access_token"]
        access_secret = self.config["api_keys"]["twitter_access_secret"]
        
        if not all([api_key, api_secret, access_token, access_secret]):
            raise Exception("Twitter API credentials incomplete.")
        
        auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
        api = tweepy.API(auth)
        
        # Fetch trends for a specific location (WOEID 1 is worldwide)
        trends = api.get_place_trends(1)[0]["trends"]
        # Pick the top trend with a tweet volume
        for trend in trends:
            if trend["tweet_volume"]:
                return trend["name"]
        return "Technology News"  # Fallback topic
    def generate_script(self, topic):
        """Generate a 30-second script using Groq"""
        client = Groq(api_key=self.config["api_keys"]["groq_api_key"])
        prompt = (
            f"Write a concise script for a 30-second video about '{topic}'. "
            f"Keep it engaging, with 3-4 sentences suitable for narration."
        )
        response = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            max_tokens=100
        )
        return response.choices[0].message.content.strip()
    def generate_audio(self, script, output_path):
        """Generate audio from script using ElevenLabs"""
        voice_id = self.config["settings"]["voice_id"]
        api_key = self.config["api_keys"]["elevenlabs_api_key"]
        
        response = requests.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
            headers={"xi-api-key": api_key},
            json={"text": script}
        )
        if response.status_code == 200:
            with open(output_path, "wb") as f:
                f.write(response.content)
            return True
        else:
            raise Exception(f"ElevenLabs API error: {response.status_code} - {response.text}")

    def fetch_image(self, topic, output_path):
        """Fetch an image from Unsplash"""
        api_key = self.config["api_keys"]["unsplash_api_key"]
        response = requests.get(
            "https://api.unsplash.com/photos/random",
            params={"query": topic, "client_id": api_key}
        )
        if response.status_code == 200:
            image_url = response.json()["urls"]["regular"]
            image_data = requests.get(image_url).content
            with open(output_path, "wb") as f:
                f.write(image_data)
            return True
        else:
            raise Exception(f"Unsplash API error: {response.status_code} - {response.text}")

        
    def setup_api_keys_tab(self):
        """Create the API keys configuration tab"""
        keys_frame = ttk.Frame(self.notebook)
        self.notebook.add(keys_frame, text="API Keys")
        
        # Create a form for API keys
        form_frame = ttk.Frame(keys_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Groq API Key
        ttk.Label(form_frame, text="Groq API Key:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.groq_api_key = ttk.Entry(form_frame, width=50, show="*")
        self.groq_api_key.grid(row=0, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["groq_api_key"]:
            self.groq_api_key.insert(0, self.config["api_keys"]["groq_api_key"])
        
        # Twitter API Keys
        ttk.Label(form_frame, text="Twitter API Key:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.twitter_api_key = ttk.Entry(form_frame, width=50, show="*")
        self.twitter_api_key.grid(row=1, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["twitter_api_key"]:
            self.twitter_api_key.insert(0, self.config["api_keys"]["twitter_api_key"])
        
        ttk.Label(form_frame, text="Twitter API Secret:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.twitter_api_secret = ttk.Entry(form_frame, width=50, show="*")
        self.twitter_api_secret.grid(row=2, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["twitter_api_secret"]:
            self.twitter_api_secret.insert(0, self.config["api_keys"]["twitter_api_secret"])
        
        ttk.Label(form_frame, text="Twitter Access Token:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.twitter_access_token = ttk.Entry(form_frame, width=50, show="*")
        self.twitter_access_token.grid(row=3, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["twitter_access_token"]:
            self.twitter_access_token.insert(0, self.config["api_keys"]["twitter_access_token"])
        
        ttk.Label(form_frame, text="Twitter Access Secret:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.twitter_access_secret = ttk.Entry(form_frame, width=50, show="*")
        self.twitter_access_secret.grid(row=4, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["twitter_access_secret"]:
            self.twitter_access_secret.insert(0, self.config["api_keys"]["twitter_access_secret"])
        
        # ElevenLabs API Key
        ttk.Label(form_frame, text="ElevenLabs API Key:").grid(row=5, column=0, sticky=tk.W, pady=5)
        self.elevenlabs_api_key = ttk.Entry(form_frame, width=50, show="*")
        self.elevenlabs_api_key.grid(row=5, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["elevenlabs_api_key"]:
            self.elevenlabs_api_key.insert(0, self.config["api_keys"]["elevenlabs_api_key"])
        
        # Unsplash API Key
        ttk.Label(form_frame, text="Unsplash API Key:").grid(row=6, column=0, sticky=tk.W, pady=5)
        self.unsplash_api_key = ttk.Entry(form_frame, width=50, show="*")
        self.unsplash_api_key.grid(row=6, column=1, sticky=tk.W, pady=5)
        if self.config["api_keys"]["unsplash_api_key"]:
            self.unsplash_api_key.insert(0, self.config["api_keys"]["unsplash_api_key"])
        
        # API Link buttons
        ttk.Button(form_frame, text="Get Groq API Key", command=lambda: webbrowser.open("https://console.groq.com/keys")).grid(row=0, column=2, padx=5, pady=5)
        ttk.Button(form_frame, text="Get Twitter API", command=lambda: webbrowser.open("https://developer.twitter.com/en/portal/dashboard")).grid(row=1, column=2, padx=5, pady=5)
        ttk.Button(form_frame, text="Get ElevenLabs API", command=lambda: webbrowser.open("https://elevenlabs.io/subscription")).grid(row=5, column=2, padx=5, pady=5)
        ttk.Button(form_frame, text="Get Unsplash API", command=lambda: webbrowser.open("https://unsplash.com/developers")).grid(row=6, column=2, padx=5, pady=5)
        
        # Test buttons
        ttk.Button(form_frame, text="Test Groq API", command=self.test_groq_api).grid(row=0, column=3, padx=5, pady=5)
        ttk.Button(form_frame, text="Test Twitter API", command=self.test_twitter_api).grid(row=1, column=3, padx=5, pady=5)
        ttk.Button(form_frame, text="Test ElevenLabs API", command=self.test_elevenlabs_api).grid(row=5, column=3, padx=5, pady=5)
        ttk.Button(form_frame, text="Test Unsplash API", command=self.test_unsplash_api).grid(row=6, column=3, padx=5, pady=5)
        
        # Save button
        ttk.Button(form_frame, text="Save API Keys", command=self.save_api_keys, style="Accent.TButton").grid(row=7, column=1, sticky=tk.E, pady=20)
        
        # Notes and instructions
        note_frame = ttk.LabelFrame(keys_frame, text="Notes")
        note_frame.pack(fill=tk.X, padx=20, pady=10)
        
        note_text = """
        • API keys are stored locally in the config directory
        • Keys are required for different components of the generator
        • At minimum, you need the Groq API key for script generation
        • Click the "Get API Key" buttons to visit the provider websites
        • Use "Test API" buttons to verify your keys work correctly
        """
        
        note_label = ttk.Label(note_frame, text=note_text, justify=tk.LEFT, wraplength=800)
        note_label.pack(padx=10, pady=10)

    def setup_settings_tab(self):
        """Create the settings configuration tab"""
        settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(settings_frame, text="Settings")
        
        # Create a form for settings
        form_frame = ttk.Frame(settings_frame)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Content niche
        ttk.Label(form_frame, text="Content Niche:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.content_niche = ttk.Combobox(form_frame, width=30, values=[
            "technology", "news", "finance", "entertainment", "health", "sports", 
            "education", "gaming", "fashion", "food", "travel", "science"
        ])
        self.content_niche.grid(row=0, column=1, sticky=tk.W, pady=5)
        self.content_niche.set(self.config["settings"]["content_niche"])
        
        # Analysis interval
        ttk.Label(form_frame, text="Trend Analysis Interval (minutes):").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.interval = ttk.Spinbox(form_frame, width=10, from_=15, to=1440, increment=15)
        self.interval.grid(row=1, column=1, sticky=tk.W, pady=5)
        self.interval.set(self.config["settings"]["trend_analysis_interval_minutes"])
        
        # Topics per run
        ttk.Label(form_frame, text="Topics Per Run:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.topics_per_run = ttk.Spinbox(form_frame, width=10, from_=1, to=10, increment=1)
        self.topics_per_run.grid(row=2, column=1, sticky=tk.W, pady=5)
        self.topics_per_run.set(self.config["settings"]["topics_per_run"])
        
        # Voice ID
        ttk.Label(form_frame, text="ElevenLabs Voice ID:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.voice_id = ttk.Entry(form_frame, width=40)
        self.voice_id.grid(row=3, column=1, sticky=tk.W, pady=5)
        self.voice_id.insert(0, self.config["settings"]["voice_id"])
        
        # Video format
        ttk.Label(form_frame, text="Video Format:").grid(row=4, column=0, sticky=tk.W, pady=5)
        self.video_format = ttk.Combobox(form_frame, width=10, values=["mp4", "mov", "avi"])
        self.video_format.grid(row=4, column=1, sticky=tk.W, pady=5)
        self.video_format.set(self.config["settings"]["video_format"])
        
        # Output directory
        ttk.Label(form_frame, text="Output Directory:").grid(row=5, column=0, sticky=tk.W, pady=5)
        
        dir_frame = ttk.Frame(form_frame)
        dir_frame.grid(row=5, column=1, sticky=tk.W, pady=5)
        
        self.output_dir = ttk.Entry(dir_frame, width=40)
        self.output_dir.pack(side=tk.LEFT, padx=(0, 5))
        self.output_dir.insert(0, self.config["settings"]["output_directory"])
        
        ttk.Button(dir_frame, text="Browse...", command=self.browse_output_dir).pack(side=tk.LEFT)
        
        # Save button
        ttk.Button(form_frame, text="Save Settings", command=self.save_settings, style="Accent.TButton").grid(row=6, column=1, sticky=tk.E, pady=20)
        
        # Advanced settings frame
        advanced_frame = ttk.LabelFrame(settings_frame, text="Advanced Settings")
        advanced_frame.pack(fill=tk.X, padx=20, pady=10)
        
        # Checkboxes for advanced options
        self.auto_startup = tk.BooleanVar(value=False)
        ttk.Checkbutton(advanced_frame, text="Start generator on application launch", variable=self.auto_startup).pack(anchor=tk.W, padx=10, pady=5)
        
        self.enable_logging = tk.BooleanVar(value=True)
        ttk.Checkbutton(advanced_frame, text="Enable detailed logging", variable=self.enable_logging).pack(anchor=tk.W, padx=10, pady=5)
        
        # Reset button
        ttk.Button(advanced_frame, text="Reset to Default Settings", command=self.reset_to_defaults).pack(anchor=tk.W, padx=10, pady=10)

    def setup_logs_tab(self):
        """Create the logs tab"""
        logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(logs_frame, text="Logs")
        
        # Create a scrolled text widget for logs
        self.log_text = scrolledtext.ScrolledText(logs_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Buttons
        button_frame = ttk.Frame(logs_frame)
        button_frame.pack(fill=tk.X, padx=10, pady=5)
        
        ttk.Button(button_frame, text="Refresh Logs", command=self.load_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Clear Logs", command=self.clear_logs).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="Export Logs", command=self.export_logs).pack(side=tk.RIGHT, padx=5)
        
        # Load initial logs
        self.load_logs()

    def save_api_keys(self):
        """Save API keys to configuration"""
        self.config["api_keys"]["groq_api_key"] = self.groq_api_key.get()
        self.config["api_keys"]["twitter_api_key"] = self.twitter_api_key.get()
        self.config["api_keys"]["twitter_api_secret"] = self.twitter_api_secret.get()
        self.config["api_keys"]["twitter_access_token"] = self.twitter_access_token.get()
        self.config["api_keys"]["twitter_access_secret"] = self.twitter_access_secret.get()
        self.config["api_keys"]["elevenlabs_api_key"] = self.elevenlabs_api_key.get()
        self.config["api_keys"]["unsplash_api_key"] = self.unsplash_api_key.get()
        
        save_config(self.config)
        messagebox.showinfo("Success", "API keys saved successfully!")

    def save_settings(self):
        """Save application settings to configuration"""
        self.config["settings"]["content_niche"] = self.content_niche.get()
        self.config["settings"]["trend_analysis_interval_minutes"] = int(self.interval.get())
        self.config["settings"]["topics_per_run"] = int(self.topics_per_run.get())
        self.config["settings"]["voice_id"] = self.voice_id.get()
        self.config["settings"]["video_format"] = self.video_format.get()
        self.config["settings"]["output_directory"] = self.output_dir.get()
        
        save_config(self.config)
        messagebox.showinfo("Success", "Settings saved successfully!")

    def browse_output_dir(self):
        """Open directory browser to select output directory"""
        directory = filedialog.askdirectory(initialdir=self.output_dir.get())
        if directory:
            self.output_dir.delete(0, tk.END)
            self.output_dir.insert(0, directory)

    def reset_to_defaults(self):
        """Reset settings to default values"""
        if messagebox.askyesno("Confirm Reset", "Are you sure you want to reset all settings to default values?"):
            self.config["settings"] = DEFAULT_CONFIG["settings"]
            save_config(self.config)
            
            # Update UI
            self.content_niche.set(self.config["settings"]["content_niche"])
            self.interval.set(self.config["settings"]["trend_analysis_interval_minutes"])
            self.topics_per_run.set(self.config["settings"]["topics_per_run"])
            self.voice_id.delete(0, tk.END)
            self.voice_id.insert(0, self.config["settings"]["voice_id"])
            self.video_format.set(self.config["settings"]["video_format"])
            self.output_dir.delete(0, tk.END)
            self.output_dir.insert(0, self.config["settings"]["output_directory"])
            
            messagebox.showinfo("Success", "Settings reset to defaults!")

    def load_logs(self):
        """Load and display logs"""
        self.log_text.config(state=tk.NORMAL)
        self.log_text.delete(1.0, tk.END)
        
        if os.path.exists("shorts_generator.log"):
            try:
                with open("shorts_generator.log", 'r') as f:
                    logs = f.read()
                    self.log_text.insert(tk.END, logs)
            except:
                self.log_text.insert(tk.END, "Error reading log file.")
        else:
            self.log_text.insert(tk.END, "No log file found.")
        
        self.log_text.config(state=tk.DISABLED)
        # Scroll to the end
        self.log_text.see(tk.END)

    def clear_logs(self):
        """Clear log file and display"""
        if messagebox.askyesno("Confirm Clear", "Are you sure you want to clear the logs?"):
            try:
                open("shorts_generator.log", 'w').close()
                self.log_text.config(state=tk.NORMAL)
                self.log_text.delete(1.0, tk.END)
                self.log_text.insert(tk.END, "Logs cleared.")
                self.log_text.config(state=tk.DISABLED)
            except:
                messagebox.showerror("Error", "Failed to clear logs.")

    def export_logs(self):
        """Export logs to a file"""
        filename = filedialog.asksaveasfilename(
            defaultextension=".log",
            filetypes=[("Log files", "*.log"), ("Text files", "*.txt"), ("All files", "*.*")],
            initialfile=f"shorts_generator_logs_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        )
        
        if filename:
            try:
                if os.path.exists("shorts_generator.log"):
                    import shutil
                    shutil.copy2("shorts_generator.log", filename)
                    messagebox.showinfo("Success", f"Logs exported to {filename}")
                else:
                    messagebox.showwarning("Warning", "No log file to export.")
            except:
                messagebox.showerror("Error", "Failed to export logs.")

    def load_recent_videos(self):
        """Load and display recent videos"""
        # Clear existing items
        for item in self.videos_tree.get_children():
            self.videos_tree.delete(item)
        
        # Look for videos in the output directory
        output_dir = self.config["settings"]["output_directory"]
        if not os.path.exists(output_dir):
            return
        
        try:
            # Get video files
            video_files = []
            for file in os.listdir(output_dir):
                if file.endswith((".mp4", ".mov", ".avi")):
                    file_path = os.path.join(output_dir, file)
                    created_time = os.path.getctime(file_path)
                    # For a real application, you would get actual duration from the video file
                    # For this example, we'll just use a placeholder
                    duration = "30s"
                    title = file.replace("short_", "").replace(".mp4", "").replace("_", " ")
                    video_files.append((title, duration, datetime.fromtimestamp(created_time), file))
            
            # Sort by creation time (newest first)
            video_files.sort(key=lambda x: x[2], reverse=True)
            
            # Add to treeview
            for video in video_files:
                self.videos_tree.insert("", tk.END, values=(
                    video[0],
                    video[1],
                    video[2].strftime("%Y-%m-%d %H:%M"),
                    video[3]
                ))
        except Exception as e:
            logger.error(f"Error loading videos: {e}")

    def show_video_menu(self, event):
        """Show right-click menu for videos"""
        # Select the row first
        iid = self.videos_tree.identify_row(event.y)
        if iid:
            self.videos_tree.selection_set(iid)
            self.video_menu.post(event.x_root, event.y_root)

    def open_selected_video(self):
        """Open the selected video"""
        selection = self.videos_tree.selection()
        if not selection:
            return
        
        item = self.videos_tree.item(selection[0])
        filename = item['values'][3]
        file_path = os.path.join(self.config["settings"]["output_directory"], filename)
        
        if os.path.exists(file_path):
            try:
                # Use the default application to open the video
                if sys.platform == "win32":
                    os.startfile(file_path)
                else:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, file_path])
            except:
                messagebox.showerror("Error", "Could not open video file.")
        else:
            messagebox.showerror("Error", "File not found.")

    def open_video_folder(self):
        """Open the folder containing the selected video"""
        output_dir = self.config["settings"]["output_directory"]
        if os.path.exists(output_dir):
            try:
                if sys.platform == "win32":
                    os.startfile(output_dir)
                else:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, output_dir])
            except:
                messagebox.showerror("Error", "Could not open output directory.")
        else:
            messagebox.showerror("Error", "Output directory not found.")

    def delete_selected_video(self):
        """Delete the selected video"""
        selection = self.videos_tree.selection()
        if not selection:
            return
        
        item = self.videos_tree.item(selection[0])
        filename = item['values'][3]
        file_path = os.path.join(self.config["settings"]["output_directory"], filename)
        
        if messagebox.askyesno("Confirm Delete", f"Are you sure you want to delete '{filename}'?"):
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
                    self.videos_tree.delete(selection[0])
                    messagebox.showinfo("Success", "Video deleted successfully!")
                else:
                    messagebox.showerror("Error", "File not found.")
            except Exception as e:
                messagebox.showerror("Error", f"Could not delete video: {str(e)}")

    def open_output_folder(self):
        """Open the output folder in file explorer"""
        output_dir = self.config["settings"]["output_directory"]
        if os.path.exists(output_dir):
            try:
                if sys.platform == "win32":
                    os.startfile(output_dir)
                else:
                    import subprocess
                    opener = "open" if sys.platform == "darwin" else "xdg-open"
                    subprocess.call([opener, output_dir])
            except:
                messagebox.showerror("Error", "Could not open output directory.")
        else:
            os.makedirs(output_dir, exist_ok=True)
            self.open_output_folder()

    def update_progress(self, message):
        """Update the progress text area"""
        self.progress_text.config(state=tk.NORMAL)
        self.progress_text.insert(tk.END, f"[{datetime.now().strftime('%H:%M:%S')}] {message}\n")
        self.progress_text.see(tk.END)
        self.progress_text.config(state=tk.DISABLED)
        self.root.update_idletasks()

    def start_generator(self):
        """Start the generator process in a separate thread"""
        if self.generator_thread and self.generator_thread.is_alive():
            messagebox.showinfo("Info", "Generator is already running.")
            return
        
        # Reset stop event
        self.stop_event.clear()
        
        # Update UI
        self.start_button.config(state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL)
        self.status_var.set("Generator running...")
        
        # Start the generator thread
        self.generator_thread = threading.Thread(target=self.generator_process)
        self.generator_thread.daemon = True
        self.generator_thread.start()
        
        self.update_progress("Generator started...")

    def stop_generator(self):
        """Stop the generator process"""
        if self.generator_thread and self.generator_thread.is_alive():
            self.stop_event.set()
            self.update_progress("Stopping generator...")
            self.status_var.set("Stopping...")
        else:
            messagebox.showinfo("Info", "Generator is not running.")

    def generator_process(self):
        """Main generator process to analyze trends and store assets"""
        try:
            required_keys = ["groq_api_key", "elevenlabs_api_key", "unsplash_api_key", 
                           "twitter_api_key", "twitter_api_secret", "twitter_access_token", 
                           "twitter_access_secret"]
            if not all(self.config["api_keys"][key] for key in required_keys):
                self.update_progress("ERROR: Missing API keys.")
                messagebox.showerror("Error", "All API keys (X, Groq, ElevenLabs, Unsplash) are required.")
                self.reset_generator_ui()
                return

            while not self.stop_event.is_set():
                self.update_progress("Fetching trending topic from X...")
                topic = self.fetch_trending_topic()
                self.update_progress(f"Selected trending topic: {topic}")

                timestamp = int(time.time())
                base_filename = f"{topic.lower().replace(' ', '_')}_{timestamp}"

                # Generate and save script
                self.update_progress("Generating script with Groq...")
                script_content = self.generate_script(topic)
                script_path = os.path.join("scripts", f"{base_filename}.txt")
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(script_content)
                self.update_progress(f"Script saved to {script_path}")

                # Generate and save audio
                self.update_progress("Converting script to audio with ElevenLabs...")
                audio_path = os.path.join("temp", f"{base_filename}.mp3")
                self.generate_audio(script_content, audio_path)
                self.update_progress(f"Audio saved to {audio_path}")

                # Fetch and save image
                self.update_progress("Fetching image from Unsplash...")
                image_path = os.path.join("media", f"{base_filename}.jpg")
                self.fetch_image(topic, image_path)
                self.update_progress(f"Image saved to {image_path}")

                self.update_progress(f"Assets for '{topic}' stored locally.")

                interval_seconds = int(self.config["settings"]["trend_analysis_interval_minutes"]) * 60
                self.update_progress(f"Waiting for next cycle in {interval_seconds//60} minutes...")
                for _ in range(interval_seconds // 5):
                    if self.stop_event.is_set():
                        break
                    time.sleep(5)

            self.update_progress("Generator stopped.")

        except Exception as e:
            self.update_progress(f"Error in generator process: {str(e)}")
            logger.error(f"Generator error: {e}")
            time.sleep(10)

        finally:
            self.root.after(0, self.reset_generator_ui)

    def reset_generator_ui(self):
        """Reset the UI after generator stops"""
        self.start_button.config(state=tk.NORMAL)
        self.stop_button.config(state=tk.DISABLED)
        self.status_var.set("Ready")

    def generate_single_video(self):
        """Generate a single video on demand"""
        try:
            # Check for required API key
            if not self.config["api_keys"]["groq_api_key"]:
                messagebox.showerror("Error", "Groq API key is required for content generation.")
                return
            
            # Ask for a topic
            topic = simpledialog.askstring("Generate Video", "Enter a topic for your short video:")
            if not topic:
                return
            
            # Disable UI during generation
            self.status_var.set("Generating video...")
            self.root.update_idletasks()
            
            # Start a thread for generation
            generate_thread = threading.Thread(target=self.generate_single_video_task, args=(topic,))
            generate_thread.daemon = True
            generate_thread.start()
            
        except Exception as e:
            messagebox.showerror("Error", f"Failed to start video generation: {str(e)}")
            self.status_var.set("Ready")

    def generate_single_video_task(self, topic=None):
        """Task to generate and store script, audio, and images for a single topic"""
        try:
            if not topic:
                topic = simpledialog.askstring("Generate Video", "Enter a topic (or leave blank for trending):")
                if not topic:
                    topic = self.fetch_trending_topic()
            
            self.update_progress(f"Generating content for topic: {topic}")
            timestamp = int(time.time())
            base_filename = f"{topic.lower().replace(' ', '_')}_{timestamp}"

            # Step 1: Generate and save script
            self.update_progress("Generating script with Groq...")
            script_content = self.generate_script(topic)
            script_path = os.path.join("scripts", f"{base_filename}.txt")
            with open(script_path, "w", encoding="utf-8") as f:
                f.write(script_content)
            self.update_progress(f"Script saved to {script_path}")

            # Step 2: Generate and save audio
            self.update_progress("Converting script to audio with ElevenLabs...")
            audio_path = os.path.join("temp", f"{base_filename}.mp3")
            self.generate_audio(script_content, audio_path)
            self.update_progress(f"Audio saved to {audio_path}")

            # Step 3: Fetch and save image
            self.update_progress("Fetching image from Unsplash...")
            image_path = os.path.join("media", f"{base_filename}.jpg")
            self.fetch_image(topic, image_path)
            self.update_progress(f"Image saved to {image_path}")

            self.update_progress(f"Assets for '{topic}' prepared and stored locally.")
            self.root.after(0, lambda: messagebox.showinfo("Success", f"Assets generated!\n\nScript: {script_path}\nAudio: {audio_path}\nImage: {image_path}"))

        except Exception as e:
            self.update_progress(f"Error generating assets: {str(e)}")
            logger.error(f"Asset generation error: {e}")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to generate assets: {str(e)}"))

        finally:
            self.root.after(0, lambda: self.status_var.set("Ready"))

    def test_groq_api(self):
        """Test Groq API connection"""
        api_key = self.groq_api_key.get()
        if not api_key:
            messagebox.showerror("Error", "Please enter a Groq API key first.")
            return
        
        self.status_var.set("Testing Groq API...")
        self.root.update_idletasks()
        
        try:
            import groq
            client = groq.Client(api_key=api_key)
            response = client.chat.completions.create(
                messages=[{"role": "user", "content": "Hello, testing connection"}],
                model="llama3-8b-8192"
            )
            
            if response:
                messagebox.showinfo("Success", "Groq API connection successful!")
            else:
                messagebox.showerror("Error", "Failed to get a valid response from Groq API.")
        except ImportError:
            messagebox.showerror("Error", "Groq Python package not installed. Please install it with 'pip install groq'.")
        except Exception as e:
            messagebox.showerror("Error", f"Groq API test failed: {str(e)}")
        
        self.status_var.set("Ready")

    def test_twitter_api(self):
        """Test Twitter API connection"""
        api_key = self.twitter_api_key.get()
        api_secret = self.twitter_api_secret.get()
        access_token = self.twitter_access_token.get()
        access_secret = self.twitter_access_secret.get()
        
        if not all([api_key, api_secret, access_token, access_secret]):
            messagebox.showerror("Error", "Please fill in all Twitter API fields.")
            return
        
        self.status_var.set("Testing Twitter API...")
        self.root.update_idletasks()
        
        try:
            import tweepy
            auth = tweepy.OAuth1UserHandler(api_key, api_secret, access_token, access_secret)
            api = tweepy.API(auth)
            
            # Test by getting user data
            user = api.verify_credentials()
            
            if user:
                messagebox.showinfo("Success", f"Twitter API connection successful!\nConnected as: @{user.screen_name}")
            else:
                messagebox.showerror("Error", "Failed to verify Twitter credentials.")
                
        except ImportError:
            messagebox.showerror("Error", "Tweepy package not installed. Please install it with 'pip install tweepy'.")
        except Exception as e:
            messagebox.showerror("Error", f"Twitter API test failed: {str(e)}")
        
        self.status_var.set("Ready")

    def test_elevenlabs_api(self):
        """Test ElevenLabs API connection"""
        api_key = self.elevenlabs_api_key.get()
        if not api_key:
            messagebox.showerror("Error", "Please enter an ElevenLabs API key first.")
            return
        
        self.status_var.set("Testing ElevenLabs API...")
        self.root.update_idletasks()
        
        try:
            import requests
            response = requests.get(
                "https://api.elevenlabs.io/v1/voices",
                headers={"xi-api-key": api_key}
            )
            
            if response.status_code == 200:
                voices = response.json().get("voices", [])
                voice_count = len(voices)
                messagebox.showinfo("Success", f"ElevenLabs API connection successful!\nFound {voice_count} available voices.")
            else:
                messagebox.showerror("Error", f"ElevenLabs API test failed: {response.status_code} - {response.text}")
                
        except ImportError:
            messagebox.showerror("Error", "Requests package not installed. Please install it with 'pip install requests'.")
        except Exception as e:
            messagebox.showerror("Error", f"ElevenLabs API test failed: {str(e)}")
        
        self.status_var.set("Ready")

    def test_unsplash_api(self):
        """Test Unsplash API connection"""
        api_key = self.unsplash_api_key.get()
        if not api_key:
            messagebox.showerror("Error", "Please enter an Unsplash API key first.")
            return
        
        self.status_var.set("Testing Unsplash API...")
        self.root.update_idletasks()
        
        try:
            import requests
            response = requests.get(
                "https://api.unsplash.com/photos/random",
                params={"client_id": api_key}
            )
            
            if response.status_code == 200:
                photo_data = response.json()
                photographer = photo_data.get("user", {}).get("name", "Unknown")
                messagebox.showinfo("Success", f"Unsplash API connection successful!\nRetrieved a random photo by {photographer}.")
            else:
                messagebox.showerror("Error", f"Unsplash API test failed: {response.status_code} - {response.text}")
                
        except ImportError:
            messagebox.showerror("Error", "Requests package not installed. Please install it with 'pip install requests'.")
        except Exception as e:
            messagebox.showerror("Error", f"Unsplash API test failed: {str(e)}")
        
        self.status_var.set("Ready")

    def on_closing(self):
        """Handle window closing event"""
        if self.generator_thread and self.generator_thread.is_alive():
            if messagebox.askyesno("Quit", "Generator is running. Stop it and exit?"):
                self.stop_event.set()
                self.root.after(1000, self.root.destroy)
            else:
                return
        else:
            self.root.destroy()


# Add a simple dialog for topic input
class TopicDialog(tk.simpledialog.Dialog):
    def __init__(self, parent, title=None):
        self.topic = ""
        super().__init__(parent, title)

    def body(self, master):
        ttk.Label(master, text="Enter a topic for your video:").grid(row=0, column=0, sticky=tk.W, pady=10, padx=10)
        
        self.entry = ttk.Entry(master, width=40)
        self.entry.grid(row=0, column=1, sticky=tk.W, pady=10, padx=10)
        return self.entry  # initial focus
    
    def apply(self):
        self.topic = self.entry.get()


# Main function
def main():
    # Setup the GUI theme
    try:
        # Try to use a modern theme if available
        import tkinter.ttk as ttk
        try:
            from ttkthemes import ThemedTk
            root = ThemedTk(theme="arc")
        except ImportError:
            root = tk.Tk()
            style = ttk.Style()
            available_themes = style.theme_names()
            if 'clam' in available_themes:
                style.theme_use('clam')
    except:
        root = tk.Tk()
    
    app = ShortsGeneratorApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()