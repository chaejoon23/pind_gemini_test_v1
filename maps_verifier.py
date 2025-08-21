"""
Google Maps Verification Module
Google Maps API를 사용하여 장소 정보를 검증하고 전체 파이프라인을 실행하는 모듈
"""

import json
import logging
import math
import os
import asyncio
from typing import List, Optional, Dict
from dataclasses import dataclass
from dotenv import load_dotenv

import googlemaps

# 다른 모듈 import
from audio_analyzer import AudioSubtitleAnalyzer, LocationInfo as AudioLocationInfo
from visual_analyzer import VisualFrameAnalyzer, LocationInfo as VisualLocationInfo


logger = logging.getLogger(__name__)


@dataclass
class LocationInfo:
    name: str
    lat: Optional[str]
    lng: Optional[str]
    confidence: float = 0.0
    source: str = "unknown"
    verified: bool = False
    place_id: Optional[str] = None
    formatted_address: Optional[str] = None
    google_rating: Optional[float] = None
    place_types: Optional[List[str]] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "source": self.source,
            "verified": self.verified,
            "place_id": self.place_id,
            "formatted_address": self.formatted_address,
            "google_rating": self.google_rating,
            "place_types": self.place_types,
        }


@dataclass
class VerificationResult:
    """검증 결과를 담는 데이터 클래스"""

    original_location: LocationInfo
    verified_location: Optional[LocationInfo]
    verification_method: str
    confidence_change: float
    distance_km: Optional[float] = None
    verification_details: Optional[Dict] = None


class GoogleMapsVerifier:
    """Google Maps API를 사용한 장소 정보 검증 클래스"""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Google Maps API 키
        """
        self.gmaps = googlemaps.Client(key=api_key)
        self.api_key = api_key
        logger.info("Google Maps Verifier 초기화 완료")

    def calculate_distance(
        self,
        lat1: float,
        lng1: float,
        lat2: float,
        lng2: float,
    ) -> float:
        """두 좌표 간의 거리 계산 (킬로미터) - Haversine 공식"""
        R = 6371  # 지구 반지름 (km)

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lng = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_lat / 2) ** 2
            + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    async def verify_by_name(
        self,
        location_name: str,
        language: str = "en",
    ) -> Optional[Dict]:
        """장소명으로 Google Places API 검색"""
        try:
            logger.info(f"장소명 검색: {location_name}")
            places_result = self.gmaps.places(
                query=location_name,
                language=language,
                type="establishment|point_of_interest|natural_feature",
            )

            if places_result["results"]:
                best_match = places_result["results"][0]
                result = {
                    "place_id": best_match.get("place_id"),
                    "name": best_match.get("name"),
                    "formatted_address": best_match.get("formatted_address"),
                    "lat": best_match["geometry"]["location"]["lat"],
                    "lng": best_match["geometry"]["location"]["lng"],
                    "types": best_match.get("types", []),
                    "rating": best_match.get("rating"),
                    "verified": True,
                }
                logger.info(f"장소 검색 성공: {result['name']}")
                return result
            logger.warning(f"장소를 찾을 수 없음: {location_name}")
            return None
        except Exception as e:
            logger.error(f"Places API 검색 오류: {e}")
            return None

    async def verify_location(
        self,
        location: LocationInfo,
        distance_threshold_km: float = 1.0,
    ) -> VerificationResult:
        """단일 장소 검증"""
        logger.info(f"장소 검증 시작: {location.name}")
        name_verification = await self.verify_by_name(location.name)
        verified_location = LocationInfo(**location.to_dict()) # 복사본 생성
        verification_result = VerificationResult(
            original_location=location,
            verified_location=None,
            verification_method="none",
            confidence_change=0.0,
        )

        if name_verification:
            verified_location.verified = True
            verified_location.place_id = name_verification["place_id"]
            verified_location.formatted_address = name_verification["formatted_address"]
            verified_location.google_rating = name_verification.get("rating")
            verified_location.place_types = name_verification.get("types")
            
            maps_lat, maps_lng = name_verification["lat"], name_verification["lng"]

            if location.lat and location.lng:
                orig_lat, orig_lng = float(location.lat), float(location.lng)
                distance = self.calculate_distance(orig_lat, orig_lng, maps_lat, maps_lng)
                verification_result.distance_km = distance
                if distance <= distance_threshold_km:
                    verified_location.confidence = min(location.confidence + 0.2, 1.0)
                    verification_result.verification_method = "name_and_coordinates_match"
                    verification_result.confidence_change = 0.2
                else:
                    verified_location.lat = str(maps_lat)
                    verified_location.lng = str(maps_lng)
                    verified_location.confidence = min(location.confidence + 0.1, 1.0)
                    verification_result.verification_method = "name_match_coordinates_corrected"
                    verification_result.confidence_change = 0.1
            else:
                verified_location.lat = str(maps_lat)
                verified_location.lng = str(maps_lng)
                verified_location.confidence = min(location.confidence + 0.15, 1.0)
                verification_result.verification_method = "name_match_coordinates_added"
                verification_result.confidence_change = 0.15
        else:
            verified_location.verified = False
            verified_location.confidence = max(location.confidence - 0.2, 0.0)
            verification_result.verification_method = "verification_failed"
            verification_result.confidence_change = -0.2

        verification_result.verified_location = verified_location
        logger.info(f"장소 검증 완료: {location.name} -> 검증됨: {verified_location.verified}")
        return verification_result

    async def verify_locations_batch(
        self,
        locations: List[LocationInfo],
    ) -> List[VerificationResult]:
        """여러 장소 일괄 검증"""
        logger.info(f"{len(locations)}개 장소 일괄 검증 시작")
        tasks = [self.verify_location(loc) for loc in locations]
        results = await asyncio.gather(*tasks)
        logger.info(f"일괄 검증 완료")
        return results

    def get_verification_stats(self, verification_results: List[VerificationResult]) -> Dict:
        """검증 결과 통계 생성"""
        if not verification_results:
            return {}
        verified_count = len([r for r in verification_results if r.verified_location and r.verified_location.verified])
        method_counts = {}
        for result in verification_results:
            method = result.verification_method
            method_counts[method] = method_counts.get(method, 0) + 1
        return {
            "total_locations": len(verification_results),
            "verified_count": verified_count,
            "failed_count": len(verification_results) - verified_count,
            "verification_rate": round(verified_count / len(verification_results) * 100, 2) if verification_results else 0,
            "verification_methods": method_counts,
        }


# --- 새로운 전체 파이프라인 실행 함수 ---
async def run_full_pipeline(youtube_url: str):
    """전체 분석 및 검증 파이프라인을 실행합니다."""
    load_dotenv()
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")

    if not all([GEMINI_API_KEY, OPENAI_API_KEY, GOOGLE_MAPS_API_KEY]):
        print("❌ 하나 이상의 API 키가 .env 파일에 설정되지 않았습니다.")
        return

    # 1. 각 분석기 초기화
    print("- (1/5) 분석 모듈 초기화 중...")
    audio_analyzer = AudioSubtitleAnalyzer(GEMINI_API_KEY, OPENAI_API_KEY)
    visual_analyzer = VisualFrameAnalyzer(GEMINI_API_KEY)
    maps_verifier = GoogleMapsVerifier(GOOGLE_MAPS_API_KEY)

    # 2. 음성 분석을 통해 지역 정보 추출
    print(f"- (2/5) 음성 분석 및 지역 식별 중: {youtube_url}")
    search_area, audio_locations = await audio_analyzer.extract_locations_and_area_from_audio(youtube_url)
    print(f"🔊 식별된 주요 지역: {search_area}")
    print(f"🔊 음성 분석 결과: {len(audio_locations)}개")

    # 3. 시각 분석 (음성 분석에서 얻은 지역 컨텍스트 사용)
    print(f"- (3/5) 시각 분석 실행 (지역 컨텍스트: {search_area})")
    visual_locations = await visual_analyzer.extract_locations_from_frames(
        youtube_url, country_context=search_area
    )
    print(f"🎬 시각 분석 결과: {len(visual_locations)}개")

    # 4. 결과 통합 및 변환
    print("- (4/5) 분석 결과 통합 중...")
    combined_locations = []
    all_results = audio_locations + visual_locations
    
    for loc in all_results:
        # 각기 다른 LocationInfo 타입을 maps_verifier의 LocationInfo로 변환
        combined_locations.append(LocationInfo(
            name=loc.name,
            lat=loc.lat,
            lng=loc.lng,
            confidence=loc.confidence,
            source=loc.source
        ))

    # 이름 기준으로 중복 제거 (신뢰도 높은 것 유지)
    unique_locations = {}
    for loc in combined_locations:
        if loc.name not in unique_locations or loc.confidence > unique_locations[loc.name].confidence:
            unique_locations[loc.name] = loc
    
    final_locations_to_verify = list(unique_locations.values())
    print(f"✨ 통합 및 중복 제거 후 최종 {len(final_locations_to_verify)}개 장소 후보 선정")

    # 5. Google Maps 검증 실행
    print("- (5/5) Google Maps로 장소 검증 실행...")
    verification_results = await maps_verifier.verify_locations_batch(final_locations_to_verify)

    # 최종 결과 출력
    print("\n" + "="*50)
    print("🎉 최종 검증 완료된 장소 목록 🎉")
    print("="*50)
    verified_count = 0
    for result in verification_results:
        if result.verified_location and result.verified_location.verified:
            verified_count += 1
            loc = result.verified_location
            orig_loc = result.original_location
            print(f"📍 {verified_count}. {loc.name}")
            print(f"  - 주소: {loc.formatted_address}")
            print(f"  - 좌표: {loc.lat}, {loc.lng}")
            print(f"  - 신뢰도: {loc.confidence:.2f} (원본: {orig_loc.confidence:.2f}, 출처: {orig_loc.source})")
            print(f"  - 검증 방법: {result.verification_method}")
    
    if verified_count == 0:
        print("검증에 성공한 장소를 찾지 못했습니다.")

    print("\n" + "-"*20)
    print("📊 검증 통계")
    stats = maps_verifier.get_verification_stats(verification_results)
    print(json.dumps(stats, indent=2, ensure_ascii=False))
    print("-"*20 + "\n")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🎬 YouTube 영상 분석 및 검증 파이프라인")
    print("="*50)
    
    # 사용자로부터 URL 입력받기
    test_url = input("분석할 YouTube 영상의 URL을 입력하세요: ").strip()

    # 간단한 URL 유효성 검사
    if "youtube.com/" in test_url or "youtu.be/" in test_url:
        print("\n🚀 전체 파이프라인 테스트 시작 🚀")
        asyncio.run(run_full_pipeline(test_url))
    else:
        print("❌ 유효한 YouTube URL이 아닙니다. 프로그램을 종료합니다.")