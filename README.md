# Job Site Auto-Reporting System

## Overview
This is an AI-powered construction site reporting system that automatically processes video uploads to generate structured reports. The system uses multiple AI models to analyze both audio narration and visual content.

## Features

### AI Processing Pipeline
- **Speech-to-Text (Whisper)**: Transcribes video audio with precise timestamps
- **Text Summarization (GPT-4)**: Organizes transcribed speech into structured reports
- **Frame Extraction**: Extracts key frames from video at meaningful timestamps
- **Object Detection (YOLO)**: Identifies relevant objects in frames (planned)
- **Scene Understanding (CLIP)**: Matches narration to visual frames
- **Action Recognition**: Detects gestures and pointing (planned)
- **Image Captioning**: Generates descriptions for ambiguous frames (optional)

### Report Sections
- **Completed Work**: Tasks that have been finished
- **Pending Tasks**: Work that needs to be done
- **Issues/Concerns**: Problems or safety concerns
- **Materials/Equipment**: Materials and equipment mentioned
- **Next Steps**: Suggested actions based on the report

### Web Interface
- Drag-and-drop video upload
- Video preview with play/pause controls
- Real-time processing status
- Interactive report display
- Download reports as JSON
- Responsive design for mobile/desktop

## Installation

### Prerequisites
- Python 3.8 or higher
- FFmpeg (for video processing)
- CUDA (optional, for GPU acceleration)

### Setup Instructions

1. **Clone the repository**
   ```bash
   cd "c:\Users\sneha\OneDrive\Desktop\EAF Holding"
   ```

2. **Create a virtual environment**
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Install FFmpeg**
   - Download from https://ffmpeg.org/download.html
   - Add to your system PATH

5. **Set up OpenAI API Key** (optional, for GPT-4 features)
   ```bash
   set OPENAI_API_KEY=your_api_key_here
   ```

6. **Run the application**
   ```bash
   python app.py
   ```

7. **Access the web interface**
   Open your browser to `http://localhost:5000`

## Usage

1. **Upload Video**: Drag and drop or select a construction site video
2. **Preview**: Review the video using built-in controls
3. **Process**: Click "Generate AI Report" to start processing
4. **View Report**: See the structured report with visual evidence
5. **Download**: Save the report as JSON for your records

## File Structure
```
EAF Holding/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── README.md             # This file
├── templates/
│   ├── index.html        # Upload page
│   └── report.html       # Report display page
├── static/
│   └── reports/          # Generated reports
├── uploads/              # Uploaded videos (temporary)
└── venv/                # Virtual environment
```

## AI Models Used

### Whisper (Speech-to-Text)
- Model: OpenAI Whisper Base
- Purpose: Transcribe audio with timestamps
- Features: Multi-language support, high accuracy

### CLIP (Scene Understanding)
- Model: ViT-B/32
- Purpose: Match visual content with text descriptions
- Features: Joint image-text understanding

### GPT-4 (Text Summarization)
- Model: OpenAI GPT-4
- Purpose: Structure and summarize transcriptions
- Features: Context-aware report generation

## Configuration

### Model Settings
```python
# In app.py, you can modify:
WHISPER_MODEL_SIZE = "base"  # tiny, base, small, medium, large
MAX_FRAMES = 10              # Maximum frames to extract
MAX_FILE_SIZE = 500 * 1024 * 1024  # 500MB
```

### API Keys
Set environment variables:
```bash
set OPENAI_API_KEY=your_openai_api_key
```

## Troubleshooting

### Common Issues

1. **FFmpeg not found**
   - Install FFmpeg and add to PATH
   - Restart command prompt after installation

2. **CUDA out of memory**
   - Use CPU mode: Set `device = "cpu"` in AIProcessor.__init__()
   - Use smaller Whisper model: Change to "tiny" or "small"

3. **Large file upload fails**
   - Increase MAX_CONTENT_LENGTH in app.py
   - Check available disk space

4. **Slow processing**
   - Use GPU acceleration if available
   - Process shorter videos for testing
   - Reduce number of extracted frames

### Performance Optimization

1. **Use GPU acceleration**
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu118
   ```

2. **Optimize video preprocessing**
   - Compress videos before upload
   - Use standard formats (MP4, AVI)
   - Limit video length for faster processing

## Development

### Adding New AI Models

1. **Implement in AIProcessor class**
   ```python
   def new_ai_function(self, input_data):
       # Your AI model implementation
       return processed_data
   ```

2. **Add to processing pipeline**
   ```python
   # In process_video function
   new_result = ai_processor.new_ai_function(input_data)
   ```

3. **Update report template**
   - Add new section in report.html
   - Style appropriately

### Testing
- Use sample construction videos
- Test with different video formats
- Verify report accuracy
- Check download functionality

## Security Considerations

1. **File Upload Security**
   - Only allow video file types
   - Scan uploads for malware
   - Limit file sizes

2. **API Key Security**
   - Store API keys in environment variables
   - Never commit keys to version control
   - Use secure key management in production

3. **Data Privacy**
   - Clear uploaded files after processing
   - Secure report storage
   - Implement user authentication if needed

## Future Enhancements

1. **Advanced AI Features**
   - YOLO object detection
   - Action recognition (I3D/C3D)
   - Automated image captioning
   - Safety violation detection

2. **User Interface**
   - Real-time processing progress
   - Video annotation tools
   - Report editing capabilities
   - Multi-user support

3. **Integration**
   - Database storage
   - Cloud deployment
   - API endpoints
   - Mobile app support

## License
This project is for educational and demonstration purposes.

## Support
For issues and questions, check the troubleshooting section or create an issue in the project repository.
