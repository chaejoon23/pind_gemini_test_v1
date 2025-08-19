#!/usr/bin/env python3
"""
테스트 실행 스크립트
각 모듈을 개별적으로 또는 통합적으로 테스트할 수 있는 편리한 스크립트
"""

import asyncio
import os
import sys
import json
from datetime import datetime
from dotenv import load_dotenv


def print_banner():
    """배너 출력"""
    print("🎯 YouTube Location Extractor - 모듈별 테스트")
    print("=" * 60)
    print("1. 음성/자막 분석 모듈 테스트")
    print("2. 시각적 키프레임 분석 모듈 테스트")
    print("3. Google Maps 검증 모듈 테스트")
    print("4. 통합 파이프라인 테스트")
    print("5. 모든 테스트 실행")
    print("0. 종료")
    print("=" * 60)


async def test_audio_module():
    """음성/자막 분석 모듈 테스트"""
    try:
        from audio_analyzer import test_audio_analyzer

        print("\n🎵 음성/자막 분석 모듈 테스트 시작...")
        await test_audio_analyzer()
    except ImportError as e:
        print(f"❌ 모듈 import 오류: {e}")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")


async def test_visual_module():
    """시각적 분석 모듈 테스트"""
    try:
        from visual_analyzer import test_visual_analyzer

        print("\n🎬 시각적 분석 모듈 테스트 시작...")
        await test_visual_analyzer()
    except ImportError as e:
        print(f"❌ 모듈 import 오류: {e}")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")


async def test_maps_module():
    """Google Maps 검증 모듈 테스트"""
    try:
        from maps_verifier import test_maps_verifier

        print("\n🗺️ Google Maps 검증 모듈 테스트 시작...")
        await test_maps_verifier()
    except ImportError as e:
        print(f"❌ 모듈 import 오류: {e}")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")


async def test_integrated_pipeline():
    """통합 파이프라인 테스트"""
    try:
        from intergrated_tester import run_all_tests

        print("\n🚀 통합 파이프라인 테스트 시작...")
        results = await run_all_tests()

        # 결과 요약 출력
        print("\n📊 테스트 결과 요약:")
        if "comparison_analysis" in results:
            comparison = results["comparison_analysis"]["comparison_analysis"]
            print(f"최적 방법: {comparison['best_method']}")
            print("처리 시간:")
            for method, time in comparison["processing_times"].items():
                print(f"  - {method}: {time:.2f}초")

    except ImportError as e:
        print(f"❌ 모듈 import 오류: {e}")
    except Exception as e:
        print(f"❌ 테스트 실행 오류: {e}")


def check_environment():
    """환경 설정 확인"""
    load_dotenv()

    required_vars = ["GEMINI_API_KEY"]
    optional_vars = ["GOOGLE_MAPS_API_KEY", "GOOGLE_CLOUD_PROJECT_ID"]

    missing_required = []
    missing_optional = []

    for var in required_vars:
        if not os.getenv(var):
            missing_required.append(var)

    for var in optional_vars:
        if not os.getenv(var):
            missing_optional.append(var)

    if missing_required:
        print("❌ 필수 환경 변수가 누락되었습니다:")
        for var in missing_required:
            print(f"   - {var}")
        print("\n.env 파일을 확인하세요.")
        return False

    if missing_optional:
        print("⚠️ 선택적 환경 변수가 누락되었습니다:")
        for var in missing_optional:
            print(f"   - {var}")
        print("일부 기능이 제한될 수 있습니다.\n")

    print("✅ 환경 설정 확인 완료\n")
    return True


def get_test_url():
    """테스트용 YouTube URL 입력받기"""
    print("\n📎 테스트할 YouTube URL을 입력하세요:")
    print("예시: https://www.youtube.com/watch?v=example")
    url = input("URL: ").strip()

    if not url:
        print("⚠️ URL이 입력되지 않았습니다. 기본 테스트 데이터를 사용합니다.")
        return None

    if "youtube.com" not in url and "youtu.be" not in url:
        print("⚠️ 유효한 YouTube URL이 아닙니다. 기본 테스트 데이터를 사용합니다.")
        return None

    # 환경 변수로 설정하여 테스트 모듈들이 사용할 수 있도록 함
    os.environ["TEST_YOUTUBE_URL"] = url
    return url


async def run_selected_test(choice: str, url: str = None):
    """선택된 테스트 실행"""
    if url:
        print(f"테스트 URL: {url}")
        # 환경변수에 URL 설정하여 모든 모듈에서 사용할 수 있도록 함
        os.environ["TEST_YOUTUBE_URL"] = url

    if choice == "1":
        await test_audio_module()
    elif choice == "2":
        await test_visual_module()
    elif choice == "3":
        await test_maps_module()
    elif choice == "4":
        await test_integrated_pipeline()
    elif choice == "5":
        print("\n🔄 모든 테스트를 순차적으로 실행합니다...")
        await test_audio_module()
        await test_visual_module()
        await test_maps_module()
        await test_integrated_pipeline()
    else:
        print("❌ 잘못된 선택입니다.")


def save_test_log():
    """테스트 로그 저장 여부 확인"""
    choice = (
        input("\n💾 테스트 로그를 파일로 저장하시겠습니까? (y/N): ").strip().lower()
    )

    if choice in ["y", "yes"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f"test_log_{timestamp}.txt"

        # 현재까지의 출력을 파일로 저장하는 로직이 필요하다면 여기에 구현
        print(f"📁 로그가 {log_filename}에 저장될 예정입니다.")
        return log_filename

    return None


async def interactive_mode():
    """대화형 모드"""
    while True:
        print_banner()
        choice = input("선택하세요 (0-5): ").strip()

        if choice == "0":
            print("👋 테스트를 종료합니다.")
            break

        if choice in ["1", "2", "3", "4", "5"]:
            # YouTube URL 입력 (선택사항)
            url = None
            if choice in ["1", "2", "4", "5"]:  # YouTube URL이 필요한 테스트들
                get_url = (
                    input("\nYouTube URL을 입력하시겠습니까? (y/N): ").strip().lower()
                )
                if get_url in ["y", "yes"]:
                    url = get_test_url()

            # 선택된 테스트 실행
            try:
                start_time = datetime.now()
                await run_selected_test(choice, url)
                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                print(f"\n⏱️ 실행 시간: {duration:.2f}초")

            except KeyboardInterrupt:
                print("\n⚠️ 사용자에 의해 중단되었습니다.")
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")

            # 로그 저장 옵션
            save_test_log()

            input("\n계속하려면 Enter를 누르세요...")
        else:
            print("❌ 0-5 사이의 번호를 입력하세요.")


async def batch_mode(test_type: str = "all"):
    """배치 모드 (명령행 인자로 실행)"""
    print(f"🚀 배치 모드로 {test_type} 테스트를 실행합니다...")

    url = os.getenv("TEST_YOUTUBE_URL")
    if url:
        print(f"테스트 URL: {url}")

    start_time = datetime.now()

    try:
        if test_type == "audio":
            await test_audio_module()
        elif test_type == "visual":
            await test_visual_module()
        elif test_type == "maps":
            await test_maps_module()
        elif test_type == "integrated":
            await test_integrated_pipeline()
        elif test_type == "all":
            await test_audio_module()
            await test_visual_module()
            await test_maps_module()
            await test_integrated_pipeline()
        else:
            print(f"❌ 알 수 없는 테스트 타입: {test_type}")
            return

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        print(f"\n✅ 배치 테스트 완료! 총 실행 시간: {duration:.2f}초")

    except Exception as e:
        print(f"❌ 배치 테스트 오류: {e}")


def main():
    """메인 함수"""
    # 환경 설정 확인
    if not check_environment():
        sys.exit(1)

    # 명령행 인자 확인
    if len(sys.argv) > 1:
        test_type = sys.argv[1]
        if len(sys.argv) > 2:
            os.environ["TEST_YOUTUBE_URL"] = sys.argv[2]
        asyncio.run(batch_mode(test_type))
    else:
        # 대화형 모드
        asyncio.run(interactive_mode())


if __name__ == "__main__":
    main()
