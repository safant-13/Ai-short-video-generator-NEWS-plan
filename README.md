# NEWS Flash App (Alpha Version)

Welcome to the **NEWS Flash App**, an innovative tool designed to generate 30-second news shorts (like reels or TikTok videos) based on trending topics or user-specified subjects. This app fetches the latest news, processes it into an engaging script using an LLM (e.g., Groq), and creates an AI-generated video using D-ID's avatar technology. The alpha version includes two implementations: a basic Tkinter-based prototype (`test.py`) and an enhanced Flask-based web application (`app.py`) with an HTML UI.

## Table of Contents
1. [Overview](#overview)
2. [Features](#features)
3. [Project Structure](#project-structure)
4. [Requirements](#requirements)
5. [Installation](#installation)
6. [Configuration](#configuration)
7. [Usage](#usage)
   - [Basic Version (`test.py`)](#basic-version-testpy)
   - [Advanced Version (`app.py`)](#advanced-version-apppy)
8. [API Integrations](#api-integrations)
9. [Troubleshooting](#troubleshooting)
10. [Future Improvements](#future-improvements)
11. [License](#license)

https://github.com/user-attachments/assets/439342a9-ee94-44a7-9b75-34399758a17c

![image](https://github.com/user-attachments/assets/a4247861-e3df-4e7f-8bee-0718dd510abd)
![image](https://github.com/user-attachments/assets/dc1dffc3-b2e1-40dd-894a-27a4556cc4ad)

## Overview
The NEWS Flash App automates the creation of short, engaging news videos. Here's the workflow:
1. **Input**: A user provides a topic, or the app fetches trending news using the NewsAPI.
2. **Script Generation**: The news is passed to an LLM (e.g., Groq) to create a concise 30-second anchor-style script.
3. **Video Creation**: The script is sent to D-ID to generate an AI avatar video.
4. **Output**: The app saves the script and video files, which can be shared on platforms like Twitter or TikTok.

The alpha version includes:
- `test.py`: A minimal Tkinter-based GUI for testing the core concept.
- `app.py`: A Flask-based web app with an HTML template for a more polished UI and additional features.

## Features
- **Topic-Based News Fetching**: Retrieve the latest news on a specified topic or trending category via NewsAPI.
- **Script Generation**: Automatically rephrase news into a 30-second anchor-style script using Groq.
- **AI Video Generation**: Create avatar-based news videos using D-ID.
- **Web Interface**: Manage the process via a Flask web app with real-time progress updates.
- **Configurable Settings**: Customize API keys, content categories, and output directories.
- **Logging**: Track app activity and errors in `shorts_generator.log`.

![image](https://github.com/user-attachments/assets/ef72a0bf-d308-4428-8d23-35fcc9daa1b0)


## Requirements
- Python 3.8+
- Required Python packages (install via `pip`):
  ```bash
  pip install flask requests tweepy groq newsapi-python subprocess logging json os datetime threading
  External Tools:
FFmpeg: For video export (install separately: FFmpeg Installation Guide). (optional)

API Keys:
NewsAPI (news_api_key)

Groq (groq_api_key)

D-ID (d_id_api_key)

Optional: ElevenLabs (elevenlabs_api_key), Unsplash (unsplash_api_key), Twitter (twitter_api_key, etc.)

Installation
Clone the Repository:
`git clone https://github.com/yourusername/NEWS-Flash-App.git`
`cd NEWS-Flash-App`
Install Dependencies:
`pip install -r requirements.txt`
## Configuration
The app uses config/settings.json to store API keys and settings. If the file doesn't exist, it will be created with defaults on first run. Example structure:

`{
    "api_keys": {
        "groq_api_key": "your_groq_api_key",
        "news_api_key": "your_newsapi_key",
        "d_id_api_key": "your_did_api_key",
        "elevenlabs_api_key": "",
        "unsplash_api_key": "",
        "twitter_api_key": "",
        "twitter_api_secret": "",
        "twitter_access_token": "",
        "twitter_access_secret": ""
    },
    "settings": {
        "content_niche": "technology",
        "voice_id": "21m00Tcm4TlvDq8ikWAM",
        "output_directory": "./media"
    }
}`

To run Test.py:
`python test.py`
To run app.py
`python app.py`


## Future Improvements
Add audio narration using ElevenLabs.
Enhance UI with video previews and more interactive controls.
Integrate social media posting directly (e.g., Twitter API).
Optimize video generation speed and quality.
Support multiple news categories simultaneously.
Add error recovery and retry mechanisms.


