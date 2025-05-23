#!/usr/bin/env python3
"""
Quick verification script to ensure YouTube Summarizer is working correctly.
Run with: python verify_setup.py
"""

import sys
from pathlib import Path

# Add src to path so we can import without installing
sys.path.insert(0, str(Path(__file__).parent / "src"))

def test_basic_imports():
    """Test that all core modules can be imported."""
    print("Testing imports...")
    try:
        from yt_summarizer.transcript import extract_video_id
        from yt_summarizer.utils import slugify, format_file_size
        from yt_summarizer.config import Config
        from yt_summarizer.llm import get_chunk_prompt_template
        print("✅ All core modules imported successfully")
        return True
    except Exception as e:
        print(f"❌ Import failed: {e}")
        return False

def test_video_id_extraction():
    """Test video ID extraction from YouTube URLs."""
    print("\nTesting video ID extraction...")
    try:
        from yt_summarizer.transcript import extract_video_id
        
        test_cases = [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("dQw4w9WgXcQ", "dQw4w9WgXcQ"),
        ]
        
        for url, expected in test_cases:
            result = extract_video_id(url)
            if result == expected:
                print(f"✅ {url} → {result}")
            else:
                print(f"❌ {url} → {result} (expected {expected})")
                return False
        
        return True
    except Exception as e:
        print(f"❌ Video ID extraction failed: {e}")
        return False

def main():
    """Run all verification tests."""
    print("🧪 Verifying YouTube Summarizer setup...\n")
    
    tests = [test_basic_imports, test_video_id_extraction]
    passed = 0
    
    for test in tests:
        if test():
            passed += 1
        else:
            break
    
    print(f"\n📊 Verification: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 YouTube Summarizer is ready to use!")
        print("\nNext steps:")
        print("1. Run tests: poetry run pytest")
        print("2. Start summarizing: ./run")
        return 0
    else:
        print("❌ Setup verification failed. Check the output above.")
        return 1

if __name__ == "__main__":
    sys.exit(main())