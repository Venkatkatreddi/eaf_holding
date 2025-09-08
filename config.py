# Configuration file for the Job Site Auto-Reporting System

import os

class Config:
    """Application configuration"""
    
    # Flask settings
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-secret-key-change-this-in-production'
    DEBUG = os.environ.get('FLASK_DEBUG', 'False').lower() == 'true'
    
    # File upload settings
    UPLOAD_FOLDER = 'uploads'
    REPORTS_FOLDER = 'static/reports'
    MAX_CONTENT_LENGTH = 500 * 1024 * 1024  # 500MB max file size
    ALLOWED_EXTENSIONS = {'mp4', 'avi', 'mov', 'mkv', 'wmv', 'flv', 'webm'}
    
    # AI Model settings
    WHISPER_MODEL_SIZE = os.environ.get('WHISPER_MODEL_SIZE', 'base')  # tiny, base, small, medium, large
    CLIP_MODEL_NAME = os.environ.get('CLIP_MODEL_NAME', 'ViT-B/32')
    MAX_FRAMES_EXTRACT = int(os.environ.get('MAX_FRAMES_EXTRACT', 10))
    
    # OpenAI settings
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY')
    OPENAI_MODEL = os.environ.get('OPENAI_MODEL', 'gpt-4')
    
    # Processing settings
    DEVICE_PREFERENCE = os.environ.get('DEVICE_PREFERENCE', 'auto')  # auto, cpu, cuda
    CLEANUP_TEMP_FILES = os.environ.get('CLEANUP_TEMP_FILES', 'True').lower() == 'true'
    
    # Video processing settings
    VIDEO_QUALITY = os.environ.get('VIDEO_QUALITY', 'medium')  # low, medium, high
    AUDIO_SAMPLE_RATE = int(os.environ.get('AUDIO_SAMPLE_RATE', 16000))
    
    # Report settings
    REPORT_FORMAT = os.environ.get('REPORT_FORMAT', 'json')  # json, pdf (future)
    INCLUDE_FULL_TRANSCRIPT = os.environ.get('INCLUDE_FULL_TRANSCRIPT', 'True').lower() == 'true'
    
    @staticmethod
    def init_app(app):
        """Initialize application with configuration"""
        # Create required directories
        os.makedirs(Config.UPLOAD_FOLDER, exist_ok=True)
        os.makedirs(Config.REPORTS_FOLDER, exist_ok=True)
        
        # Set Flask config
        app.config['UPLOAD_FOLDER'] = Config.UPLOAD_FOLDER
        app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
        app.config['SECRET_KEY'] = Config.SECRET_KEY


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    WHISPER_MODEL_SIZE = 'tiny'  # Faster for development
    MAX_FRAMES_EXTRACT = 5       # Fewer frames for faster processing


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    WHISPER_MODEL_SIZE = 'base'
    MAX_FRAMES_EXTRACT = 15
    CLEANUP_TEMP_FILES = True


class TestingConfig(Config):
    """Testing configuration"""
    TESTING = True
    WHISPER_MODEL_SIZE = 'tiny'
    MAX_FRAMES_EXTRACT = 3
    UPLOAD_FOLDER = 'test_uploads'
    REPORTS_FOLDER = 'test_reports'


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}
