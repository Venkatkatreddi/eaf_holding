from flask import Flask, render_template, request, jsonify, send_file, flash, redirect, url_for
import os
import cv2
import openai
from dotenv import load_dotenv
from PIL import Image
import numpy as np
import torch
from moviepy.editor import VideoFileClip
from moviepy.config import change_settings
import imageio_ffmpeg
import json
from datetime import datetime
import pytz
import io
import base64
from werkzeug.utils import secure_filename
import logging
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader
from pydub import AudioSegment
from pydub.utils import mediainfo

# Setup and config
load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')
change_settings({"FFMPEG_BINARY": imageio_ffmpeg.get_ffmpeg_exe()})
os.environ["PATH"] = os.path.dirname(imageio_ffmpeg.get_ffmpeg_exe()) + os.pathsep + os.environ.get("PATH", "")

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static/reports', exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import requests

def get_weather_toronto():
    try:
        response = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": 43.65107,
                "longitude": -79.347015,
                "current_weather": True
            }
        )
        data = response.json()
        weather = data.get("current_weather", {})

        temperature = f"{weather.get('temperature', 'N/A')}°C"
        wind_speed = f"{weather.get('windspeed', 'N/A')} km/h"

        weather_code = weather.get("weathercode", -1)
        condition_map = {
            0: "Clear sky",
            1: "Mainly clear",
            2: "Partly cloudy",
            3: "Overcast",
            45: "Fog",
            48: "Rime fog",
            51: "Light drizzle",
            53: "Moderate drizzle",
            55: "Dense drizzle",
            61: "Light rain",
            63: "Moderate rain",
            65: "Heavy rain",
            80: "Light showers",
            81: "Moderate showers",
            82: "Heavy showers",
        }
        conditions = condition_map.get(weather_code, "Unknown")

        return {
            "temperature": temperature,
            "wind_speed": wind_speed,
            "conditions": conditions,
            "location": "Toronto, Canada"
        }

    except Exception as e:
        return {
            "temperature": "N/A",
            "wind_speed": "N/A",
            "conditions": "Error fetching weather",
            "location": "Toronto, Canada"
        }

def split_audio_by_size(file_path, max_size_bytes=25 * 1024 * 1024):
    audio = AudioSegment.from_file(file_path)
    bitrate_kbps = int(float(mediainfo(file_path)['bit_rate']) / 1000)
    duration_seconds = len(audio) / 1000
    file_size = os.path.getsize(file_path)

    if file_size <= max_size_bytes:
        return [file_path]

    max_duration_per_chunk = (max_size_bytes * 8) / (bitrate_kbps * 1000)
    chunks = []
    start_ms = 0
    chunk_index = 0

    while start_ms < len(audio):
        end_ms = start_ms + int(max_duration_per_chunk * 1000)
        chunk = audio[start_ms:end_ms]
        # export as compressed MP3 to keep chunk size under limit
        chunk_path = f"{os.path.splitext(file_path)[0]}_chunk{chunk_index}.mp3"
        chunk.export(chunk_path, format="mp3", bitrate="192k")
        chunks.append(chunk_path)
        start_ms = end_ms
        chunk_index += 1

    return chunks

class AIProcessor:
    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() else "cpu"

    def extract_audio_from_video(self, video_path):
        video = VideoFileClip(video_path)
        if video.audio is None:
            raise Exception("Video file has no audio track")
        audio_path = os.path.splitext(video_path)[0] + '_audio.wav'
        video.audio.write_audiofile(audio_path, verbose=False, logger=None)
        video.close()
        return audio_path

    def speech_to_text(self, audio_path):
        try:
            audio_chunks = split_audio_by_size(audio_path)
            full_text = ""

            for chunk_path in audio_chunks:
                with open(chunk_path, "rb") as audio_file:
                    transcription = openai.Audio.transcribe(model="whisper-1", file=audio_file)
                    full_text += transcription['text'] + "\n"

            # debug: print the full transcription result
            logger.info(f"Full transcription text: {full_text.strip()}")
            return {
                'full_text': full_text.strip(),
                'language': 'en',
                'segments': [],
                'words': [],
                'stats': {
                    'total_duration': 0,
                    'word_count': len(full_text.split()),
                    'segment_count': len(audio_chunks),
                    'average_words_per_minute': 0
                }
            }
        except Exception as e:
            logger.error(f"Transcription failed: {str(e)}")
            return {
                'full_text': "Error: API transcription failed",
                'language': 'unknown',
                'segments': [],
                'words': [],
                'stats': {'total_duration': 0, 'word_count': 0, 'segment_count': 0, 'average_words_per_minute': 0},
                'error': str(e)
            }

    def summarize_text(self, text):
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "You are an assistant that analyzes construction site transcripts and returns ONLY a valid JSON object with these keys:\n"
                        "- completed_work: array of strings (specific completed tasks)\n"
                        "- pending_tasks: array of strings\n"
                        "- issues_concerns: array of strings (delays, safety issues, etc.)\n"
                        "- materials_equipment: array of materials, tools, or equipment mentioned or implied (e.g., piping, hangers, drills)\n"
                        "- next_steps: array of strings (planned actions)\n\n"
                        "Extract even implied materials from phrases like 'installation of piping'. Return raw JSON only. Do not include any explanations or markdown."
                    )

                },
                {"role": "user", "content": f"Transcript: {text}"}
            ]
            response = openai.ChatCompletion.create(model="gpt-4", messages=messages, temperature=0)
            raw = response['choices'][0]['message']['content']
            return json.loads(raw)
        except Exception as e:
            logger.error(f"Summarization failed: {str(e)}")
            return {
                "completed_work": [],
                "pending_tasks": [],
                "issues_concerns": [],
                "materials_equipment": [],
                "next_steps": []
            }

    def extract_key_frames(self, video_path, timestamps, max_frames=10):
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = []
        if len(timestamps) < max_frames:
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = total_frames / fps
            timestamps = [i * duration / max_frames for i in range(max_frames)]
        for timestamp in timestamps[:max_frames]:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(timestamp * fps))
            ret, frame = cap.read()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append({'timestamp': timestamp, 'frame': rgb})
        cap.release()
        return frames

    def frames_to_base64(self, frames):
        base64_frames = []
        for frame_data in frames:
            img = Image.fromarray(frame_data['frame'])
            buf = io.BytesIO()
            img.save(buf, format='JPEG')
            img_str = base64.b64encode(buf.getvalue()).decode()
            base64_frames.append({'timestamp': frame_data['timestamp'], 'image_data': f"data:image/jpeg;base64,{img_str}"})
        return base64_frames

ai_processor = AIProcessor()

def generate_pdf(report_data, pdf_path):
    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter
    y = height - 40
    c.setFont("Helvetica-Bold", 16)
    c.drawString(40, y, "Construction Site Auto-Report")
    y -= 30
    c.setFont("Helvetica", 10)
    c.drawString(40, y, f"Timestamp: {report_data['timestamp']}")
    y -= 20
    c.drawString(40, y, f"Video File: {report_data['video_filename']}")
    y -= 30
    c.setFont("Helvetica-Bold", 14)
    c.drawString(40, y, "Tasks Completed:")
    y -= 20
    for item in report_data.get('tasks_completed', []):
        c.setFont("Helvetica", 12)
        c.drawString(60, y, f"- {item['description']}")
        y -= 16
        if item.get('photo'):
            try:
                header, b64 = item['photo'].split(',', 1)
                img_data = io.BytesIO(base64.b64decode(b64))
                img = ImageReader(img_data)
                c.drawImage(img, 60, y - 100, width=200, height=100)
                y -= 110
            except:
                pass
        if y < 100:
            c.showPage(); y = height - 40
    for section, title in [('pending_tasks', 'Pending Tasks'), ('next_steps', 'Next Steps'), ('delays', 'Delays/Issues'), ('materials', 'Materials & Equipment')]:
        c.setFont("Helvetica-Bold", 14)
        c.drawString(40, y, f"{title}:")
        y -= 20
        c.setFont("Helvetica", 12)
        for val in report_data.get(section, []):
            c.drawString(60, y, f"- {val}")
            y -= 16
            if y < 60:
                c.showPage(); y = height - 40
        y -= 20
    c.save()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    try:
        if 'video' not in request.files or request.files['video'].filename == '':
            flash('No video file selected')
            return redirect(url_for('index'))
        file = request.files['video']
        filename = secure_filename(file.filename)
        timestamp = datetime.now(pytz.timezone('US/Eastern')).strftime('%Y%m%d_%H%M%S')
        filename = f"{timestamp}_{filename}"
        video_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(video_path)
        report_data = process_video(video_path)
        report_filename = f"report_{timestamp}.json"
        report_path = os.path.join('static/reports', report_filename)
        with open(report_path, 'w') as f:
            json.dump(report_data, f, indent=2)
        return render_template('report.html', report=report_data, report_filename=report_filename)
    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        flash(f'Error processing video: {str(e)}')
        return redirect(url_for('index'))

def process_video(video_path):
    try:
        weather = get_weather_toronto()

        audio_path = ai_processor.extract_audio_from_video(video_path)
        transcription = ai_processor.speech_to_text(audio_path)
        summary = ai_processor.summarize_text(transcription['full_text'])

        def normalize(val):
            if isinstance(val, str): return [val]
            if not isinstance(val, list): return []
            return val

        completed_items = normalize(summary.get('completed_work'))
        pending_tasks = normalize(summary.get('pending_tasks'))
        next_steps = normalize(summary.get('next_steps'))
        delays = normalize(summary.get('issues_concerns')) or ['NA']
        materials = normalize(summary.get('materials_equipment'))

        timestamps = [seg.get('start', 0) for seg in transcription.get('segments', [])]
        frames = ai_processor.extract_key_frames(video_path, timestamps)
        base64_frames = ai_processor.frames_to_base64(frames)

        tasks_completed = []
        for idx, desc in enumerate(completed_items):
            photo = base64_frames[idx]['image_data'] if idx < len(base64_frames) else None
            tasks_completed.append({'description': desc, 'photo': photo})

        report_data = {
            'timestamp': datetime.now(pytz.timezone('US/Eastern')).isoformat(),
            'video_filename': os.path.basename(video_path),
            'weather': weather,  # ✅ added
            'transcription': transcription,
            'tasks_completed': tasks_completed,
            'pending_tasks': pending_tasks,
            'next_steps': next_steps,
            'delays': delays,
            'materials': materials,
            'processing_status': 'completed'
        }
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return report_data
    except Exception as e:
        logger.error(f"Video processing failed: {str(e)}")
        return {'error': str(e), 'processing_status': 'failed'}

@app.route('/download_pdf/<filename>')
def download_pdf(filename):
    json_path = os.path.join('static/reports', filename)
    pdf_path = os.path.join('static/reports', filename.replace('.json', '.pdf'))
    with open(json_path) as f:
        report_data = json.load(f)
    generate_pdf(report_data, pdf_path)
    return send_file(pdf_path, as_attachment=True)

@app.route('/download_report/<filename>')
def download_report(filename):
    path = os.path.join('static/reports', filename)
    return send_file(path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
