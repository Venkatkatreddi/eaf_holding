"""
Test script to verify the Job Site Auto-Reporting System setup
"""

import sys
import os

def test_python_version():
    """Test if Python version is compatible"""
    print("Testing Python version...")
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} is compatible")
    return True

def test_required_packages():
    """Test if required packages are installed"""
    print("\nTesting required packages...")
    
    required_packages = [
        ('flask', 'Flask'),
        ('cv2', 'OpenCV'), 
        ('PIL', 'Pillow'),
        ('numpy', 'NumPy'),
        ('torch', 'PyTorch'),
        ('whisper', 'OpenAI Whisper'),
        ('moviepy.editor', 'MoviePy'),
        ('transformers', 'Transformers')
    ]
    
    missing_packages = []
    
    for package, name in required_packages:
        try:
            __import__(package)
            print(f"✅ {name} is installed")
        except ImportError:
            print(f"❌ {name} is missing")
            missing_packages.append(name)
    
    if missing_packages:
        print(f"\nMissing packages: {', '.join(missing_packages)}")
        print("Run: pip install -r requirements.txt")
        return False
    
    return True

def test_directories():
    """Test if required directories exist"""
    print("\nTesting directory structure...")
    
    required_dirs = [
        'templates',
        'static',
        'static/reports',
        'uploads'
    ]
    
    for directory in required_dirs:
        if os.path.exists(directory):
            print(f"✅ {directory}/ exists")
        else:
            print(f"❌ {directory}/ is missing")
            os.makedirs(directory, exist_ok=True)
            print(f"✅ Created {directory}/")
    
    return True

def test_files():
    """Test if required files exist"""
    print("\nTesting required files...")
    
    required_files = [
        'app.py',
        'requirements.txt',
        'templates/index.html',
        'templates/report.html',
        'config.py'
    ]
    
    missing_files = []
    
    for file_path in required_files:
        if os.path.exists(file_path):
            print(f"✅ {file_path} exists")
        else:
            print(f"❌ {file_path} is missing")
            missing_files.append(file_path)
    
    if missing_files:
        print(f"\nMissing files: {', '.join(missing_files)}")
        return False
    
    return True

def test_ai_models():
    """Test if AI models can be loaded (optional)"""
    print("\nTesting AI model availability...")
    
    try:
        import torch
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"✅ PyTorch device: {device}")
    except Exception as e:
        print(f"❌ PyTorch error: {e}")
    
    try:
        import whisper
        print("✅ Whisper models available")
    except Exception as e:
        print(f"❌ Whisper error: {e}")
    
    try:
        import clip
        print("✅ CLIP model available")
    except Exception as e:
        print(f"❌ CLIP error: {e}")

def test_flask_app():
    """Test if Flask app can be imported"""
    print("\nTesting Flask application...")
    
    try:
        from app import app, AIProcessor
        print("✅ Flask app can be imported")
        print("✅ AIProcessor class available")
        return True
    except Exception as e:
        print(f"❌ Flask app error: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("=== Job Site Auto-Reporting System - Setup Test ===\n")
    
    tests = [
        test_python_version,
        test_required_packages,
        test_directories,
        test_files,
        test_ai_models,
        test_flask_app
    ]
    
    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)
    
    print("\n" + "="*50)
    print("TEST SUMMARY")
    print("="*50)
    
    passed = sum(1 for r in results if r)
    total = len(results)
    
    if all(results):
        print("🎉 All tests passed! The system is ready to use.")
        print("\nTo start the application:")
        print("1. Run: python app.py")
        print("2. Open: http://localhost:5000")
    else:
        print(f"⚠️  {passed}/{total} tests passed. Please fix the issues above.")
        
        if not results[0]:  # Python version
            print("\n🔧 Install Python 3.8+: https://python.org")
        if not results[1]:  # Packages
            print("\n🔧 Install packages: pip install -r requirements.txt")
        if not results[3]:  # Files
            print("\n🔧 Ensure all project files are present")
    
    print("\n" + "="*50)
    return all(results)

if __name__ == "__main__":
    run_all_tests()
