from flask import Flask, render_template, request, send_file, flash, redirect, url_for
import os, cv2, json, io, base64, logging
from datetime import datetime
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
from openai import OpenAI, __version__ as openai_version
from PIL import Image
from moviepy import VideoFileClip  # MoviePy 2.x import
import imageio_ffmpeg
import pytz
import requests

# ---------- Torch (optional; avoid DLL crash on Windows) ----------
try:
    import torch  # noqa: F401
    HAS_TORCH = True
except Exception as _e:
    HAS_TORCH = False
    TORCH_IMPORT_ERROR = _e  # used in a warning below

# ---------- ReportLab base64 shim (old reportlab expects these) ----------
import base64 as _b64shim
if not hasattr(_b64shim, "decodestring"):
    _b64shim.decodestring = _b64shim.decodebytes  # type: ignore[attr-defined]
if not hasattr(_b64shim, "encodestring"):
    _b64shim.encodestring = _b64shim.encodebytes  # type: ignore[attr-defined]

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from reportlab.lib.utils import ImageReader

from pydub import AudioSegment
from pydub.utils import mediainfo

# ------------------------------ Setup ------------------------------
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY missing. Put it in .env or set environment variable.")

# OpenAI v1 client
client = OpenAI(api_key=OPENAI_API_KEY)
print(f"[BOOT] OpenAI SDK ver={openai_version}")

# --- ffmpeg wiring for MoviePy 2.x + pydub ---
FFMPEG_EXE = imageio_ffmpeg.get_ffmpeg_exe()
os.environ["IMAGEIO_FFMPEG_EXE"] = FFMPEG_EXE  # MoviePy 2.x reads this
os.environ["PATH"] = os.path.dirname(FFMPEG_EXE) + os.pathsep + os.environ.get("PATH", "")
# pydub needs converter path set explicitly on Windows
AudioSegment.converter = FFMPEG_EXE

# Flask
app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "your-secret-key-here")
app.config["UPLOAD_FOLDER"] = "uploads"
app.config["MAX_CONTENT_LENGTH"] = 500 * 1024 * 1024
os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs("static/reports", exist_ok=True)

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------------ Helpers ------------------------------
def get_weather_toronto():
    try:
        r = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": 43.65107, "longitude": -79.347015, "current_weather": True},
            timeout=10,
        )
        w = r.json().get("current_weather", {})
        temp = f"{w.get('temperature', 'N/A')}°C"
        wind = f"{w.get('windspeed', 'N/A')} km/h"
        code = w.get("weathercode", -1)
        names = {
            0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
            45: "Fog", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
            61: "Light rain", 63: "Moderate rain", 65: "Heavy rain",
            80: "Light showers", 81: "Moderate showers", 82: "Heavy showers",
        }
        return {"temperature": temp, "wind_speed": wind, "conditions": names.get(code, "Unknown"), "location": "Toronto, Canada"}
    except Exception:
        return {"temperature": "N/A", "wind_speed": "N/A", "conditions": "Error fetching weather", "location": "Toronto, Canada"}

# def split_audio_by_size(file_path, max_size_bytes=25 * 1024 * 1024):
#     audio = AudioSegment.from_file(file_path)
#     bitrate = mediainfo(file_path).get("bit_rate")
#     bitrate_kbps = int(float(bitrate) / 1000) if bitrate else 192
#     if os.path.getsize(file_path) <= max_size_bytes:
#         return [file_path]
#     max_secs = (max_size_bytes * 8) / (bitrate_kbps * 1000)
#     chunks, start_ms, idx = [], 0, 0
#     while start_ms < len(audio):
#         end_ms = start_ms + int(max_secs * 1000)
#         chunk = audio[start_ms:end_ms]
#         out = f"{os.path.splitext(file_path)[0]}_chunk{idx}.mp3"
#         chunk.export(out, format="mp3", bitrate="192k")
#         chunks.append(out)
#         start_ms = end_ms
#         idx += 1
#     return chunks

def split_audio_by_size(file_path, max_size_bytes=25 * 1024 * 1024):
    audio = AudioSegment.from_file(file_path)

    # No splitting needed if the file is below the API limit
    if os.path.getsize(file_path) <= max_size_bytes:
        return [file_path]

    # Estimate a safe chunk duration for MP3 at 128 kbps
    bitrate = 128 * 1000
    max_secs = (max_size_bytes * 8 * 0.85) / bitrate

    chunks = []
    start_ms = 0
    idx = 0
    chunk_duration_ms = int(max_secs * 1000)

    while start_ms < len(audio):
        end_ms = min(start_ms + chunk_duration_ms, len(audio))
        chunk = audio[start_ms:end_ms]

        out = f"{os.path.splitext(file_path)[0]}_chunk{idx}.mp3"
        chunk.export(out, format="mp3", bitrate="128k")

        chunks.append(out)
        start_ms = end_ms
        idx += 1

    return chunks

# ------------------------------ AI Processor ------------------------------
class AIProcessor:
    def __init__(self):
        self.device = "cuda" if HAS_TORCH and getattr(torch, "cuda", None) and torch.cuda.is_available() else "cpu"
        if not HAS_TORCH:
            logger.warning("Torch not available; proceeding on CPU only. (%s)", TORCH_IMPORT_ERROR if 'TORCH_IMPORT_ERROR' in globals() else "")

    def extract_audio_from_video(self, video_path):
        video = VideoFileClip(video_path)
        if video.audio is None:
            video.close()
            raise Exception("Video file has no audio track")
        audio_path = os.path.splitext(video_path)[0] + "_audio.wav"
        video.audio.write_audiofile(audio_path, fps=16000)
        video.close()
        return audio_path

    def speech_to_text(self, audio_path):
        """Transcribe using OpenAI v1; supports chunked files."""
        try:
            chunks = split_audio_by_size(audio_path)
            full_text, all_segments = "", []
            for p in chunks:
                with open(p, "rb") as f:
                    tr = client.audio.transcriptions.create(
                        model="whisper-1",
                        file=f,
                        response_format="verbose_json",
                    )
                # text
                chunk_text = getattr(tr, "text", None) or (tr.get("text") if isinstance(tr, dict) else "")
                if chunk_text:
                    full_text += chunk_text + "\n"
                # segments
                segs = getattr(tr, "segments", None) or (tr.get("segments") if isinstance(tr, dict) else None) or []
                for s in segs:
                    all_segments.append({"id": s.get("id"), "start": s.get("start"), "end": s.get("end"), "text": s.get("text")})
            full_text = full_text.strip()
            logger.info("Full transcription text length: %d chars", len(full_text))
            return {
                "full_text": full_text or "",
                "language": "en",
                "segments": all_segments,
                "words": [],
                "stats": {
                    "total_duration": 0,
                    "word_count": len(full_text.split()) if full_text else 0,
                    "segment_count": len(chunks),
                    "average_words_per_minute": 0,
                },
            }
        except Exception:
            logger.exception("Transcription failed")
            return {
                "full_text": "Error: API transcription failed",
                "language": "unknown",
                "segments": [],
                "words": [],
                "stats": {"total_duration": 0, "word_count": 0, "segment_count": 0, "average_words_per_minute": 0},
                "error": "transcription_failed",
            }

    def summarize_text(self, text):
        """Summarize via Chat Completions (OpenAI v1)."""
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
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
                        ),
                    },
                    {"role": "user", "content": f"Transcript: {text}"},
                ],
                temperature=0.0,
            )
            raw = resp.choices[0].message.content
            return json.loads(raw)
        except Exception:
            logger.exception("Summarization failed")
            return {"completed_work": [], "pending_tasks": [], "issues_concerns": [], "materials_equipment": [], "next_steps": []}

    def extract_key_frames(self, video_path, timestamps, max_frames=10):
        cap = cv2.VideoCapture(video_path)
        fps = cap.get(cv2.CAP_PROP_FPS)
        frames = []
        if not timestamps or len(timestamps) < max_frames:
            total_frames = cap.get(cv2.CAP_PROP_FRAME_COUNT)
            duration = (total_frames / fps) if fps else 0
            if duration <= 0:
                cap.release()
                return frames
            timestamps = [i * duration / max_frames for i in range(max_frames)]
        for t in timestamps[:max_frames]:
            if fps:
                cap.set(cv2.CAP_PROP_POS_FRAMES, int(t * fps))
            ret, frame = cap.read()
            if ret:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                frames.append({"timestamp": t, "frame": rgb})
        cap.release()
        return frames

    def frames_to_base64(self, frames):
        out = []
        for f in frames:
            img = Image.fromarray(f["frame"])
            buf = io.BytesIO()
            img.save(buf, format="JPEG")
            img_str = base64.b64encode(buf.getvalue()).decode()
            out.append({"timestamp": f["timestamp"], "image_data": f"data:image/jpeg;base64,{img_str}"})
        return out

ai_processor = AIProcessor()

# ------------------------------ PDF Generator ------------------------------
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
    for item in report_data.get("tasks_completed", []):
        c.setFont("Helvetica", 12)
        c.drawString(60, y, f"- {item['description']}")
        y -= 16
        if item.get("photo"):
            try:
                header, b64 = item["photo"].split(",", 1)
                img_data = io.BytesIO(base64.b64decode(b64))
                img = ImageReader(img_data)
                c.drawImage(img, 60, y - 100, width=200, height=100)
                y -= 110
            except Exception:
                pass
        if y < 100:
            c.showPage(); y = height - 40
    for section, title in [
        ("pending_tasks", "Pending Tasks"),
        ("next_steps", "Next Steps"),
        ("delays", "Delays/Issues"),
        ("materials", "Materials & Equipment"),
    ]:
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

# ------------------------------ Routes ------------------------------
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/upload", methods=["POST"])
def upload_video():
    try:
        if "video" not in request.files or request.files["video"].filename == "":
            flash("No video file selected")
            return redirect(url_for("index"))

        file = request.files["video"]
        filename = secure_filename(file.filename)
        ts = datetime.now(pytz.timezone("US/Eastern")).strftime("%Y%m%d_%H%M%S")
        filename = f"{ts}_{filename}"
        video_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
        file.save(video_path)

        report_data = process_video(video_path)

        report_filename = f"report_{ts}.json"
        report_path = os.path.join("static/reports", report_filename)
        with open(report_path, "w") as f:
            json.dump(report_data, f, indent=2)

        return render_template("report.html", report=report_data, report_filename=report_filename)
    except Exception:
        logger.exception("Upload error")
        flash("Error processing video")
        return redirect(url_for("index"))

def process_video(video_path):
    try:
        weather = get_weather_toronto()
        audio_path = ai_processor.extract_audio_from_video(video_path)
        transcription = ai_processor.speech_to_text(audio_path)
        summary = ai_processor.summarize_text(transcription["full_text"])

        def normalize(v):
            if isinstance(v, str): return [v]
            if not isinstance(v, list): return []
            return v

        completed = normalize(summary.get("completed_work"))
        pending = normalize(summary.get("pending_tasks"))
        next_steps = normalize(summary.get("next_steps"))
        delays = normalize(summary.get("issues_concerns")) or ["NA"]
        materials = normalize(summary.get("materials_equipment"))

        timestamps = [seg.get("start", 0) for seg in transcription.get("segments", [])]
        frames = ai_processor.extract_key_frames(video_path, timestamps)
        b64_frames = ai_processor.frames_to_base64(frames)

        tasks_completed = []
        for i, desc in enumerate(completed):
            photo = b64_frames[i]["image_data"] if i < len(b64_frames) else None
            tasks_completed.append({"description": desc, "photo": photo})

        report_data = {
            "timestamp": datetime.now(pytz.timezone("US/Eastern")).isoformat(),
            "video_filename": os.path.basename(video_path),
            "weather": weather,
            "transcription": transcription,
            "tasks_completed": tasks_completed,
            "pending_tasks": pending,
            "next_steps": next_steps,
            "delays": delays,
            "materials": materials,
            "processing_status": "completed",
        }
        if os.path.exists(audio_path):
            os.remove(audio_path)
        return report_data
    except Exception:
        logger.exception("Video processing failed")
        return {"error": "processing_failed", "processing_status": "failed"}

@app.route("/download_pdf/<filename>")
def download_pdf(filename):
    json_path = os.path.join("static/reports", filename)
    pdf_path = os.path.join("static/reports", filename.replace(".json", ".pdf"))
    with open(json_path) as f:
        report_data = json.load(f)
    generate_pdf(report_data, pdf_path)
    return send_file(pdf_path, as_attachment=True)

@app.route("/download_report/<filename>")
def download_report(filename):
    path = os.path.join("static/reports", filename)
    return send_file(path, as_attachment=True)

# ------------------------------ Main ------------------------------
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
