"""
Integrated Testing Module
세 가지 분석 모듈을 통합하여 테스트하는 모듈
"""

import json
import logging
import asyncio
from typing import List, Dict, Optional
from dotenv import load_dotenv
import os
from datetime import datetime

# 개별 모듈 import
from audio_analyzer import AudioSubtitleAnalyzer, LocationInfo as AudioLocationInfo
from visual_analyzer import VisualFrameAnalyzer, LocationInfo as VisualLocationInfo
from maps_verifier import (
    GoogleMapsVerifier,
    LocationInfo as MapsLocationInfo,
    VerificationResult,
)

logger = logging.getLogger(__name__)


class IntegratedLocationExtractor:
    """세 가지 분석 모듈을 통합하는 클래스"""

    def __init__(self, gemini_api_key: str, google_maps_api_key: Optional[str] = None):
        """
        Args:
            gemini_api_key: Gemini API 키
            google_maps_api_key: Google Maps API 키 (선택사항)
        """
        self.audio_analyzer = AudioSubtitleAnalyzer(gemini_api_key)
        self.visual_analyzer = VisualFrameAnalyzer(gemini_api_key)
        self.maps_verifier = (
            GoogleMapsVerifier(google_maps_api_key) if google_maps_api_key else None
        )

        logger.info("통합 위치 추출기 초기화 완료")
        if not google_maps_api_key:
            logger.warning("Google Maps API 키가 없어 검증 기능이 비활성화됩니다")

    def convert_to_maps_location(self, location) -> MapsLocationInfo:
        """다른 모듈의 LocationInfo를 MapsLocationInfo로 변환"""
        return MapsLocationInfo(
            name=location.name,
            lat=location.lat,
            lng=location.lng,
            confidence=location.confidence,
            source=location.source,
        )

    async def test_audio_analysis_only(self, youtube_url: str) -> Dict:
        """음성/자막 분석만 테스트"""
        logger.info("=== 음성/자막 분석 단독 테스트 ===")

        start_time = datetime.now()

        # 가용성 확인
        availability = self.audio_analyzer.check_audio_availability(youtube_url)

        # 장소 추출
        locations = await self.audio_analyzer.extract_locations_from_audio(youtube_url)

        # 통계 생성
        stats = self.audio_analyzer.get_analysis_stats(locations)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return {
            "test_type": "audio_only",
            "youtube_url": youtube_url,
            "processing_time_seconds": processing_time,
            "availability": availability,
            "locations": [loc.to_dict() for loc in locations],
            "stats": stats,
            "timestamp": start_time.isoformat(),
        }

    async def test_visual_analysis_only(self, youtube_url: str) -> Dict:
        """시각적 분석만 테스트"""
        logger.info("=== 시각적 분석 단독 테스트 ===")

        start_time = datetime.now()

        # 장소 추출
        locations = await self.visual_analyzer.extract_locations_from_frames(
            youtube_url
        )

        # 통계 생성
        stats = self.visual_analyzer.get_visual_analysis_stats(locations)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return {
            "test_type": "visual_only",
            "youtube_url": youtube_url,
            "processing_time_seconds": processing_time,
            "locations": [loc.to_dict() for loc in locations],
            "stats": stats,
            "timestamp": start_time.isoformat(),
        }

    async def test_maps_verification_only(self, test_locations: List[Dict]) -> Dict:
        """Google Maps 검증만 테스트"""
        if not self.maps_verifier:
            return {
                "test_type": "maps_verification_only",
                "error": "Google Maps API 키가 설정되지 않음",
                "timestamp": datetime.now().isoformat(),
            }

        logger.info("=== Google Maps 검증 단독 테스트 ===")

        start_time = datetime.now()

        # 테스트 데이터를 MapsLocationInfo로 변환
        locations = []
        for loc_data in test_locations:
            location = MapsLocationInfo(
                name=loc_data["name"],
                lat=loc_data.get("lat"),
                lng=loc_data.get("lng"),
                confidence=loc_data.get("confidence", 0.5),
                source=loc_data.get("source", "test"),
            )
            locations.append(location)

        # 검증 실행
        verification_results = await self.maps_verifier.verify_locations_batch(
            locations
        )

        # 통계 생성
        stats = self.maps_verifier.get_verification_stats(verification_results)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return {
            "test_type": "maps_verification_only",
            "processing_time_seconds": processing_time,
            "verification_results": [
                {
                    "original": result.original_location.to_dict(),
                    "verified": (
                        result.verified_location.to_dict()
                        if result.verified_location
                        else None
                    ),
                    "method": result.verification_method,
                    "confidence_change": result.confidence_change,
                    "distance_km": result.distance_km,
                }
                for result in verification_results
            ],
            "stats": stats,
            "timestamp": start_time.isoformat(),
        }

    async def test_audio_plus_visual(self, youtube_url: str) -> Dict:
        """음성 + 시각적 분석 조합 테스트"""
        logger.info("=== 음성 + 시각적 분석 조합 테스트 ===")

        start_time = datetime.now()

        # 병렬로 두 분석 실행
        audio_task = self.audio_analyzer.extract_locations_from_audio(youtube_url)
        visual_task = self.visual_analyzer.extract_locations_from_frames(youtube_url)

        audio_locations, visual_locations = await asyncio.gather(
            audio_task, visual_task
        )

        # 결과 통합 (단순 합치기)
        all_locations = audio_locations + visual_locations

        # 중복 제거 (이름이 유사한 장소들)
        unique_locations = []
        for location in all_locations:
            is_duplicate = False
            for existing in unique_locations:
                if self._are_similar_locations(location.name, existing.name):
                    # 더 높은 신뢰도를 가진 것을 유지
                    if location.confidence > existing.confidence:
                        unique_locations.remove(existing)
                        unique_locations.append(location)
                    is_duplicate = True
                    break

            if not is_duplicate:
                unique_locations.append(location)

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return {
            "test_type": "audio_plus_visual",
            "youtube_url": youtube_url,
            "processing_time_seconds": processing_time,
            "audio_locations": [loc.to_dict() for loc in audio_locations],
            "visual_locations": [loc.to_dict() for loc in visual_locations],
            "combined_locations": [loc.to_dict() for loc in unique_locations],
            "stats": {
                "audio_count": len(audio_locations),
                "visual_count": len(visual_locations),
                "combined_count": len(unique_locations),
                "duplicate_removed": len(all_locations) - len(unique_locations),
            },
            "timestamp": start_time.isoformat(),
        }

    async def test_full_pipeline(self, youtube_url: str) -> Dict:
        """전체 파이프라인 테스트 (음성 + 시각 + 검증)"""
        logger.info("=== 전체 파이프라인 테스트 ===")

        start_time = datetime.now()

        # 1단계: 음성 + 시각적 분석
        audio_visual_result = await self.test_audio_plus_visual(youtube_url)
        combined_locations = audio_visual_result["combined_locations"]

        # 2단계: Google Maps 검증 (가능한 경우)
        verification_result = None
        if self.maps_verifier and combined_locations:
            # LocationInfo 객체로 변환
            locations_for_verification = []
            for loc_data in combined_locations:
                location = MapsLocationInfo(
                    name=loc_data["name"],
                    lat=loc_data.get("lat"),
                    lng=loc_data.get("lng"),
                    confidence=loc_data.get("confidence", 0.5),
                    source=loc_data.get("source", "combined"),
                )
                locations_for_verification.append(location)

            verification_results = await self.maps_verifier.verify_locations_batch(
                locations_for_verification
            )
            verification_stats = self.maps_verifier.get_verification_stats(
                verification_results
            )

            # 최종 검증된 위치들
            final_locations = []
            for result in verification_results:
                if result.verified_location:
                    final_locations.append(result.verified_location.to_dict())

            verification_result = {
                "verification_results": [
                    {
                        "original": result.original_location.to_dict(),
                        "verified": (
                            result.verified_location.to_dict()
                            if result.verified_location
                            else None
                        ),
                        "method": result.verification_method,
                        "confidence_change": result.confidence_change,
                    }
                    for result in verification_results
                ],
                "stats": verification_stats,
                "final_locations": final_locations,
            }

        end_time = datetime.now()
        processing_time = (end_time - start_time).total_seconds()

        return {
            "test_type": "full_pipeline",
            "youtube_url": youtube_url,
            "processing_time_seconds": processing_time,
            "step1_audio_visual": audio_visual_result,
            "step2_verification": verification_result,
            "final_output": (
                verification_result["final_locations"]
                if verification_result
                else combined_locations
            ),
            "timestamp": start_time.isoformat(),
        }

    def _are_similar_locations(
        self, name1: str, name2: str, threshold: float = 0.8
    ) -> bool:
        """두 장소명이 유사한지 확인"""
        from difflib import SequenceMatcher

        similarity = SequenceMatcher(None, name1.lower(), name2.lower()).ratio()
        return similarity >= threshold

    async def compare_analysis_methods(self, youtube_url: str) -> Dict:
        """다양한 분석 방법 비교"""
        logger.info("=== 분석 방법 비교 테스트 ===")

        results = {}

        # 각 방법별로 테스트 실행
        results["audio_only"] = await self.test_audio_analysis_only(youtube_url)
        results["visual_only"] = await self.test_visual_analysis_only(youtube_url)
        results["audio_plus_visual"] = await self.test_audio_plus_visual(youtube_url)

        if self.maps_verifier:
            results["full_pipeline"] = await self.test_full_pipeline(youtube_url)

        # 비교 분석
        comparison = {
            "methods_tested": list(results.keys()),
            "processing_times": {
                method: result["processing_time_seconds"]
                for method, result in results.items()
            },
            "location_counts": {
                method: len(result.get("final_output", result.get("locations", [])))
                for method, result in results.items()
            },
            "best_method": self._determine_best_method(results),
            "timestamp": datetime.now().isoformat(),
        }

        return {"comparison_analysis": comparison, "detailed_results": results}

    def _determine_best_method(self, results: Dict) -> str:
        """최적의 분석 방법 결정"""
        scores = {}

        for method, result in results.items():
            if method == "full_pipeline":
                final_locations = result.get("final_output", [])
                verified_count = len(
                    [loc for loc in final_locations if loc.get("verified", False)]
                )
                total_count = len(final_locations)
                avg_confidence = sum(
                    loc.get("confidence", 0) for loc in final_locations
                ) / max(total_count, 1)
                processing_time = result["processing_time_seconds"]

                # 전체 파이프라인은 검증된 결과가 많을수록 높은 점수
                scores[method] = (
                    verified_count * 0.4
                    + avg_confidence * 0.4
                    + (1 / max(processing_time, 1)) * 0.2
                )

            else:
                locations = result.get("final_output", result.get("locations", []))
                total_count = len(locations)
                avg_confidence = sum(
                    loc.get("confidence", 0) for loc in locations
                ) / max(total_count, 1)
                processing_time = result["processing_time_seconds"]

                # 일반 방법들은 신뢰도와 속도 중심
                scores[method] = (
                    total_count * 0.3
                    + avg_confidence * 0.5
                    + (1 / max(processing_time, 1)) * 0.2
                )

        return max(scores.items(), key=lambda x: x[1])[0] if scores else "unknown"


# 테스트 실행 함수들
async def run_individual_tests():
    """개별 모듈 테스트 실행"""
    load_dotenv()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    extractor = IntegratedLocationExtractor(GEMINI_API_KEY, GOOGLE_MAPS_API_KEY)

    # 테스트용 YouTube URL (환경변수에서 가져오거나 기본값 사용)
    test_url = os.getenv("TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=example")

    print("🎵 음성/자막 분석 테스트...")
    print(f"🔍 Integrated Tester가 사용 중인 URL: {test_url}")
    audio_result = await extractor.test_audio_analysis_only(test_url)
    print(
        f"음성 분석 결과: {len(audio_result['locations'])}개 장소, {audio_result['processing_time_seconds']:.2f}초"
    )

    print("\n🎬 시각적 분석 테스트...")
    visual_result = await extractor.test_visual_analysis_only(test_url)
    print(
        f"시각 분석 결과: {len(visual_result['locations'])}개 장소, {visual_result['processing_time_seconds']:.2f}초"
    )

    if GOOGLE_MAPS_API_KEY:
        print("\n🗺️ Google Maps 검증 테스트...")
        test_locations = [
            {"name": "에펠탑", "lat": "48.8584", "lng": "2.2945", "confidence": 0.8},
            {"name": "도쿄타워", "confidence": 0.6},
            {
                "name": "서울타워",
                "lat": "37.5512",
                "lng": "126.9882",
                "confidence": 0.7,
            },
        ]
        maps_result = await extractor.test_maps_verification_only(test_locations)
        if "error" not in maps_result:
            print(f"Maps 검증 결과: {maps_result['stats']['verified_count']}개 검증됨")

    return {
        "audio_result": audio_result,
        "visual_result": visual_result,
        "maps_result": maps_result if GOOGLE_MAPS_API_KEY else None,
    }


async def run_combined_tests():
    """조합 테스트 실행"""
    load_dotenv()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    extractor = IntegratedLocationExtractor(GEMINI_API_KEY, GOOGLE_MAPS_API_KEY)

    # 테스트용 YouTube URL (환경변수에서 가져오거나 기본값 사용)
    test_url = os.getenv("TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=example")

    print("🔄 음성 + 시각적 분석 조합 테스트...")
    combined_result = await extractor.test_audio_plus_visual(test_url)
    print(f"조합 결과: {combined_result['stats']['combined_count']}개 장소")
    print(f"  - 음성: {combined_result['stats']['audio_count']}개")
    print(f"  - 시각: {combined_result['stats']['visual_count']}개")
    print(f"  - 중복 제거: {combined_result['stats']['duplicate_removed']}개")

    if GOOGLE_MAPS_API_KEY:
        print("\n🚀 전체 파이프라인 테스트...")
        pipeline_result = await extractor.test_full_pipeline(test_url)
        final_count = len(pipeline_result["final_output"])
        print(f"최종 결과: {final_count}개 장소")

        if pipeline_result["step2_verification"]:
            verified_count = pipeline_result["step2_verification"]["stats"][
                "verified_count"
            ]
            print(f"검증된 장소: {verified_count}개")

    return combined_result


async def run_comparison_analysis():
    """분석 방법 비교"""
    load_dotenv()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    extractor = IntegratedLocationExtractor(GEMINI_API_KEY, GOOGLE_MAPS_API_KEY)

    # 테스트용 YouTube URL (환경변수에서 가져오거나 기본값 사용)
    test_url = os.getenv("TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=example")

    print("📊 분석 방법 비교 테스트...")
    comparison_result = await extractor.compare_analysis_methods(test_url)

    print("\n=== 비교 결과 ===")
    comparison = comparison_result["comparison_analysis"]

    print("처리 시간:")
    for method, time in comparison["processing_times"].items():
        print(f"  - {method}: {time:.2f}초")

    print("\n추출된 장소 수:")
    for method, count in comparison["location_counts"].items():
        print(f"  - {method}: {count}개")

    print(f"\n최적 방법: {comparison['best_method']}")

    return comparison_result


def save_test_results(results: Dict, filename: str = None):
    """테스트 결과를 파일로 저장"""
    if not filename:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"test_results_{timestamp}.json"

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"📁 테스트 결과가 {filename}에 저장되었습니다.")


async def run_all_tests():
    """모든 테스트 실행"""
    print("🧪 YouTube Location Extractor 통합 테스트 시작")
    print("=" * 50)

    all_results = {}

    # 개별 테스트
    print("\n1️⃣ 개별 모듈 테스트")
    individual_results = await run_individual_tests()
    all_results["individual_tests"] = individual_results

    # 조합 테스트
    print("\n2️⃣ 조합 테스트")
    combined_results = await run_combined_tests()
    all_results["combined_tests"] = combined_results

    # 비교 분석
    print("\n3️⃣ 비교 분석")
    comparison_results = await run_comparison_analysis()
    all_results["comparison_analysis"] = comparison_results

    # 결과 저장
    save_test_results(all_results)

    print("\n✅ 모든 테스트 완료!")
    return all_results


# 메인 실행 부분
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="YouTube Location Extractor 통합 테스트"
    )
    parser.add_argument(
        "--test",
        choices=["individual", "combined", "comparison", "all"],
        default="all",
        help="실행할 테스트 유형",
    )
    parser.add_argument("--url", type=str, help="테스트할 YouTube URL")
    parser.add_argument("--save", type=str, help="결과 저장 파일명")

    args = parser.parse_args()

    # 로깅 설정
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # URL이 제공된 경우 환경변수로 설정 (테스트용)
    if args.url:
        os.environ["TEST_YOUTUBE_URL"] = args.url

    # 테스트 실행
    if args.test == "individual":
        asyncio.run(run_individual_tests())
    elif args.test == "combined":
        asyncio.run(run_combined_tests())
    elif args.test == "comparison":
        asyncio.run(run_comparison_analysis())
    else:  # 'all'
        results = asyncio.run(run_all_tests())
        if args.save:
            save_test_results(results, args.save)
