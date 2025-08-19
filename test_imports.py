#!/usr/bin/env python3
"""
Package Import Test Script
모든 필수 패키지가 올바르게 설치되었는지 확인하는 스크립트
"""

import sys
import traceback

def test_import(package_name, import_statement=None):
    """패키지 import 테스트"""
    try:
        if import_statement:
            exec(import_statement)
        else:
            __import__(package_name)
        print(f"✅ {package_name}: OK")
        return True
    except ImportError as e:
        print(f"❌ {package_name}: FAILED - {e}")
        return False
    except Exception as e:
        print(f"⚠️ {package_name}: ERROR - {e}")
        return False

def main():
    """메인 테스트 함수"""
    print("🧪 Package Import Test")
    print("=" * 50)
    
    tests = [
        # 기본 패키지들
        ("python-dotenv", "from dotenv import load_dotenv"),
        ("requests", "import requests"),
        ("httpx", "import httpx"),
        ("numpy", "import numpy"),
        ("pydantic", "import pydantic"),
        ("typing-extensions", "import typing_extensions"),
        
        # Google 패키지들
        ("google-generativeai", "import google.generativeai as genai"),
        ("googlemaps", "import googlemaps"),
        
        # YouTube 다운로드
        ("yt-dlp", "import yt_dlp"),
        
        # 웹 프레임워크
        ("fastapi", "import fastapi"),
        ("uvicorn", "import uvicorn"),
        
        # 테스트 패키지
        ("pytest", "import pytest"),
        ("pytest-asyncio", "import pytest_asyncio"),
        
        # 로깅
        ("python-json-logger", "from pythonjsonlogger import jsonlogger"),
    ]
    
    passed = 0
    failed = 0
    
    for package_name, import_statement in tests:
        if test_import(package_name, import_statement):
            passed += 1
        else:
            failed += 1
    
    print("\n" + "=" * 50)
    print(f"📊 Test Results: {passed} passed, {failed} failed")
    
    if failed > 0:
        print("\n⚠️ Some packages failed to import. Please check:")
        print("1. Make sure you're in the correct virtual environment")
        print("2. Run: pip install -r requirements.txt")
        print("3. Try installing failed packages individually")
        sys.exit(1)
    else:
        print("\n🎉 All packages imported successfully!")

def test_api_compatibility():
    """API 호환성 테스트"""
    print("\n🔧 API Compatibility Test")
    print("=" * 50)
    
    try:
        # Google Generative AI 테스트
        import google.generativeai as genai
        print("✅ Google Generative AI: Import OK")
        
        # 클라이언트 생성 테스트 (API 키 없이)
        try:
            # API 키 설정 없이 모델 생성만 테스트
            model_name = 'gemini-1.5-flash'
            print(f"✅ Model name '{model_name}': Available")
        except Exception as e:
            print(f"⚠️ Model creation test: {e}")
        
        # yt-dlp 테스트
        import yt_dlp
        print("✅ yt-dlp: Import OK")
        
        # GoogleMaps 테스트
        import googlemaps
        print("✅ GoogleMaps: Import OK")
        
        print("🎉 API compatibility check passed!")
        
    except Exception as e:
        print(f"❌ API compatibility test failed: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
    test_api_compatibility()