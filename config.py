# Configuration file for the Job Site Auto-Reporting System
import os

class Config:
    """Application configuration"""

    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'

    # Folders & uploads
    UPLOAD_FOLDER = 'uploads'
    REPORTS_FOLDER = 'static/reports'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}

    # AI model settings
    WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')  # tiny, base, small, medium, large
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4o-mini')

    # Processing
    DEVICE_PREFERENCE = os.environ.get('DEVICE_PREFERENCE', 'auto')  # auto, cpu, cuda
    CLEANUP_TEMP_FILES = os.environ.get('CLEANUP_TEMP_FILES', 'True').lower() == 'true'

    # Video/audio
    VIDEO_QUALITY = os.environ.get('VIDEO_QUALITY', 'medium')  # low, medium, high
    AUDIO_SAMPLE_RATE = int(os.environ.get('AUDIO_SAMPLE_RATE', 16000))

    # Reports
    REPORT_FORMAT = os.environ.get('REPORT_FORMAT', 'json')  # json, pdf
    INCLUDE_FULL_TRANSCRIPT = os.environ.get('INCLUDE_FULL_TRANSCRIPT', 'True').lower() == 'true'

    @staticmethod
    def init_app(app):
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
        app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
        app.config['SECRET_KEY'] = Config.SECRET_KEY


class DevelopmentConfig(Config):
    DEBUG = True
    WHISPER_MODEL_SIZE = 'tiny'
    MAX_FRAMES_EXTRACT = 5


class ProductionConfig(Config):
    DEBUG = False
    WHISPER_MODEL_SIZE = 'base'
    MAX_FRAMES_EXTRACT = 15
    CLEANUP_TEMP_FILES = True


class TestingConfig(Config):
    TESTING = True
    WHISPER_MODEL_SIZE = 'tiny'
    MAX_FRAMES_EXTRACT = 3
    UPLOAD_FOLDER = 'test_uploads'
    REPORTS_FOLDER = 'test_reports'


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
