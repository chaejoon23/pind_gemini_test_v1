"""
Google Maps Verification Module
Google Maps API를 사용하여 장소 정보를 검증하는 모듈
"""

import json
import logging
import math
from typing import List, Optional, Dict, Tuple
from dataclasses import dataclass, asdict
import googlemaps

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
        self, lat1: float, lng1: float, lat2: float, lng2: float
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
        self, location_name: str, language: str = "en"
    ) -> Optional[Dict]:
        """장소명으로 Google Places API 검색"""
        try:
            logger.info(f"장소명 검색: {location_name}")

            # Places API Text Search 사용
            places_result = self.gmaps.places(
                query=location_name,
                language=language,
                type="establishment|point_of_interest|natural_feature",
            )

            if places_result["results"]:
                best_match = places_result["results"][0]  # 가장 관련성 높은 결과

                result = {
                    "place_id": best_match.get("place_id"),
                    "name": best_match.get("name"),
                    "formatted_address": best_match.get("formatted_address"),
                    "lat": best_match["geometry"]["location"]["lat"],
                    "lng": best_match["geometry"]["location"]["lng"],
                    "types": best_match.get("types", []),
                    "rating": best_match.get("rating"),
                    "user_ratings_total": best_match.get("user_ratings_total"),
                    "price_level": best_match.get("price_level"),
                    "verified": True,
                    "search_query": location_name,
                }

                logger.info(
                    f"장소 검색 성공: {result['name']} at {result['lat']}, {result['lng']}"
                )
                return result

            logger.warning(f"장소를 찾을 수 없음: {location_name}")
            return None

        except Exception as e:
            logger.error(f"Places API 검색 오류: {e}")
            return None

    async def verify_by_coordinates(
        self, lat: float, lng: float, language: str = "en"
    ) -> Optional[Dict]:
        """좌표로 역지오코딩하여 실제 장소 확인"""
        try:
            logger.info(f"좌표 검증: {lat}, {lng}")

            # Reverse Geocoding API 사용
            reverse_result = self.gmaps.reverse_geocode((lat, lng), language=language)

            if reverse_result:
                result = reverse_result[0]

                return {
                    "place_id": result.get("place_id"),
                    "formatted_address": result.get("formatted_address"),
                    "lat": lat,
                    "lng": lng,
                    "address_components": result.get("address_components", []),
                    "types": result.get("types", []),
                    "verified": True,
                    "original_coordinates": f"{lat}, {lng}",
                }

            logger.warning(f"좌표에 해당하는 주소를 찾을 수 없음: {lat}, {lng}")
            return None

        except Exception as e:
            logger.error(f"역지오코딩 오류: {e}")
            return None

    async def get_place_details(
        self, place_id: str, fields: List[str] = None
    ) -> Optional[Dict]:
        """Place ID로 상세 정보 조회"""
        try:
            default_fields = [
                "name",
                "formatted_address",
                "geometry",
                "types",
                "rating",
                "user_ratings_total",
                "price_level",
                "photos",
                "opening_hours",
                "website",
                "international_phone_number",
            ]

            fields_to_use = fields or default_fields

            place_details = self.gmaps.place(
                place_id=place_id, fields=fields_to_use, language="en"
            )

            if place_details["status"] == "OK":
                result = place_details["result"]
                return {
                    "place_id": place_id,
                    "name": result.get("name"),
                    "formatted_address": result.get("formatted_address"),
                    "lat": result["geometry"]["location"]["lat"],
                    "lng": result["geometry"]["location"]["lng"],
                    "types": result.get("types", []),
                    "rating": result.get("rating"),
                    "user_ratings_total": result.get("user_ratings_total"),
                    "price_level": result.get("price_level"),
                    "photos": result.get("photos", []),
                    "opening_hours": result.get("opening_hours"),
                    "website": result.get("website"),
                    "phone": result.get("international_phone_number"),
                    "verified": True,
                }

            logger.warning(f"Place Details 조회 실패: {place_details['status']}")
            return None

        except Exception as e:
            logger.error(f"Place Details API 오류: {e}")
            return None

    async def verify_location(
        self, location: LocationInfo, distance_threshold_km: float = 10.0
    ) -> VerificationResult:
        """단일 장소 검증"""
        logger.info(f"장소 검증 시작: {location.name}")

        # 검증 결과 초기화
        verification_result = VerificationResult(
            original_location=location,
            verified_location=None,
            verification_method="none",
            confidence_change=0.0,
        )

        try:
            # 1. 장소명으로 검색
            name_verification = await self.verify_by_name(location.name)

            # 2. 좌표가 있는 경우 좌표 검증
            coord_verification = None
            if location.lat and location.lng:
                try:
                    lat, lng = float(location.lat), float(location.lng)
                    coord_verification = await self.verify_by_coordinates(lat, lng)
                except ValueError:
                    logger.warning(
                        f"유효하지 않은 좌표: {location.lat}, {location.lng}"
                    )

            # 3. 검증 결과 분석 및 통합
            verified_location = LocationInfo(
                name=location.name,
                lat=location.lat,
                lng=location.lng,
                confidence=location.confidence,
                source=location.source,
                verified=False,
            )

            if name_verification and coord_verification:
                # 두 검증 모두 성공한 경우
                maps_lat, maps_lng = name_verification["lat"], name_verification["lng"]
                orig_lat, orig_lng = float(location.lat), float(location.lng)

                distance = self.calculate_distance(
                    orig_lat, orig_lng, maps_lat, maps_lng
                )
                verification_result.distance_km = distance

                if distance <= distance_threshold_km:
                    # 좌표가 일치하는 경우 - 최고 신뢰도
                    verified_location.verified = True
                    verified_location.place_id = name_verification["place_id"]
                    verified_location.formatted_address = name_verification[
                        "formatted_address"
                    ]
                    verified_location.google_rating = name_verification.get("rating")
                    verified_location.place_types = name_verification.get("types")
                    verified_location.confidence = min(location.confidence + 0.3, 1.0)
                    verification_result.verification_method = (
                        "name_and_coordinates_match"
                    )
                    verification_result.confidence_change = 0.3
                else:
                    # 좌표가 많이 다른 경우 - Maps API 좌표 사용
                    verified_location.lat = str(maps_lat)
                    verified_location.lng = str(maps_lng)
                    verified_location.verified = True
                    verified_location.place_id = name_verification["place_id"]
                    verified_location.formatted_address = name_verification[
                        "formatted_address"
                    ]
                    verified_location.google_rating = name_verification.get("rating")
                    verified_location.place_types = name_verification.get("types")
                    verified_location.confidence = min(location.confidence + 0.2, 1.0)
                    verification_result.verification_method = (
                        "name_match_coordinates_corrected"
                    )
                    verification_result.confidence_change = 0.2

            elif name_verification:
                # 장소명 검증만 성공한 경우
                verified_location.verified = True
                verified_location.place_id = name_verification["place_id"]
                verified_location.formatted_address = name_verification[
                    "formatted_address"
                ]
                verified_location.google_rating = name_verification.get("rating")
                verified_location.place_types = name_verification.get("types")

                # 좌표가 없었던 경우 Maps API에서 가져온 좌표 사용
                if not location.lat or not location.lng:
                    verified_location.lat = str(name_verification["lat"])
                    verified_location.lng = str(name_verification["lng"])
                    verified_location.confidence = min(location.confidence + 0.25, 1.0)
                    verification_result.verification_method = (
                        "name_match_coordinates_added"
                    )
                    verification_result.confidence_change = 0.25
                else:
                    verified_location.confidence = min(location.confidence + 0.15, 1.0)
                    verification_result.verification_method = "name_match_only"
                    verification_result.confidence_change = 0.15

            elif coord_verification:
                # 좌표 검증만 성공한 경우
                verified_location.verified = True
                verified_location.place_id = coord_verification.get("place_id")
                verified_location.formatted_address = coord_verification[
                    "formatted_address"
                ]
                verified_location.confidence = min(location.confidence + 0.1, 1.0)
                verification_result.verification_method = "coordinates_only"
                verification_result.confidence_change = 0.1

            else:
                # 검증 실패
                verified_location.verified = False
                verified_location.confidence = max(location.confidence - 0.15, 0.0)
                verification_result.verification_method = "verification_failed"
                verification_result.confidence_change = -0.15

            verification_result.verified_location = verified_location
            verification_result.verification_details = {
                "name_verification": name_verification,
                "coord_verification": coord_verification,
            }

            logger.info(
                f"장소 검증 완료: {location.name} -> 검증됨: {verified_location.verified}"
            )
            return verification_result

        except Exception as e:
            logger.error(f"장소 검증 중 오류 ({location.name}): {e}")
            verification_result.verified_location = location
            verification_result.verification_method = "error"
            return verification_result

    async def verify_locations_batch(
        self, locations: List[LocationInfo], distance_threshold_km: float = 10.0
    ) -> List[VerificationResult]:
        """여러 장소 일괄 검증"""
        logger.info(f"{len(locations)}개 장소 일괄 검증 시작")

        verification_results = []

        for i, location in enumerate(locations, 1):
            logger.info(f"검증 진행률: {i}/{len(locations)}")
            result = await self.verify_location(location, distance_threshold_km)
            verification_results.append(result)

        # 검증 결과 통계
        verified_count = len(
            [
                r
                for r in verification_results
                if r.verified_location and r.verified_location.verified
            ]
        )
        failed_count = len(verification_results) - verified_count

        logger.info(f"일괄 검증 완료: {verified_count}개 성공, {failed_count}개 실패")

        return verification_results

    def get_verification_stats(
        self, verification_results: List[VerificationResult]
    ) -> Dict:
        """검증 결과 통계 생성"""
        if not verification_results:
            return {
                "total_locations": 0,
                "verified_count": 0,
                "failed_count": 0,
                "verification_methods": {},
                "average_confidence_change": 0.0,
            }

        verified_count = len(
            [
                r
                for r in verification_results
                if r.verified_location and r.verified_location.verified
            ]
        )
        failed_count = len(verification_results) - verified_count

        # 검증 방법별 통계
        method_counts = {}
        for result in verification_results:
            method = result.verification_method
            method_counts[method] = method_counts.get(method, 0) + 1

        # 신뢰도 변화 평균
        confidence_changes = [r.confidence_change for r in verification_results]
        avg_confidence_change = (
            sum(confidence_changes) / len(confidence_changes)
            if confidence_changes
            else 0.0
        )

        return {
            "total_locations": len(verification_results),
            "verified_count": verified_count,
            "failed_count": failed_count,
            "verification_rate": round(
                verified_count / len(verification_results) * 100, 2
            ),
            "verification_methods": method_counts,
            "average_confidence_change": round(avg_confidence_change, 3),
            "distance_corrections": len(
                [
                    r
                    for r in verification_results
                    if r.distance_km and r.distance_km > 1.0
                ]
            ),
        }

    async def search_nearby_places(
        self, lat: float, lng: float, radius: int = 1000, place_type: str = None
    ) -> List[Dict]:
        """주변 장소 검색"""
        try:
            logger.info(f"주변 장소 검색: {lat}, {lng} (반경 {radius}m)")

            nearby_search = self.gmaps.places_nearby(
                location=(lat, lng), radius=radius, type=place_type
            )

            places = []
            for place in nearby_search.get("results", []):
                places.append(
                    {
                        "name": place.get("name"),
                        "place_id": place.get("place_id"),
                        "lat": place["geometry"]["location"]["lat"],
                        "lng": place["geometry"]["location"]["lng"],
                        "types": place.get("types", []),
                        "rating": place.get("rating"),
                        "vicinity": place.get("vicinity"),
                    }
                )

            logger.info(f"주변에서 {len(places)}개 장소 발견")
            return places

        except Exception as e:
            logger.error(f"주변 장소 검색 오류: {e}")
            return []


# 독립 실행 및 테스트 함수들
async def test_maps_verifier():
    """Google Maps 검증기 테스트 함수"""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    GOOGLE_MAPS_API_KEY = os.getenv("GOOGLE_MAPS_API_KEY")
    if not GOOGLE_MAPS_API_KEY:
        print("❌ GOOGLE_MAPS_API_KEY가 설정되지 않았습니다.")
        return

    verifier = GoogleMapsVerifier(GOOGLE_MAPS_API_KEY)

    # 테스트용 장소 데이터
    test_locations = [
        LocationInfo(
            name="에펠탑", lat="48.8584", lng="2.2945", confidence=0.8, source="test"
        ),
        LocationInfo(
            name="도쿄타워", lat=None, lng=None, confidence=0.6, source="test"
        ),
        LocationInfo(
            name="존재하지않는장소", lat="0.0", lng="0.0", confidence=0.3, source="test"
        ),
        LocationInfo(
            name="서울타워",
            lat="37.5512",
            lng="126.9882",
            confidence=0.7,
            source="test",
        ),
    ]

    print("🗺️ Google Maps 검증 테스트...")

    # 개별 검증 테스트
    print("\n=== 개별 장소 검증 ===")
    for location in test_locations:
        print(f"\n📍 검증 중: {location.name}")
        result = await verifier.verify_location(location)

        print(f"원본: {location.name} (신뢰도: {location.confidence})")
        if result.verified_location:
            verified = result.verified_location
            print(f"검증결과: {verified.name}")
            print(f"  - 검증됨: {verified.verified}")
            print(
                f"  - 신뢰도: {verified.confidence} (변화: {result.confidence_change:+.2f})"
            )
            print(f"  - 방법: {result.verification_method}")
            if verified.formatted_address:
                print(f"  - 주소: {verified.formatted_address}")
            if result.distance_km:
                print(f"  - 좌표 거리: {result.distance_km:.2f}km")

    # 일괄 검증 테스트
    print("\n=== 일괄 검증 ===")
    batch_results = await verifier.verify_locations_batch(test_locations)

    print("📊 검증 통계:")
    stats = verifier.get_verification_stats(batch_results)
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # 주변 장소 검색 테스트
    print("\n=== 주변 장소 검색 테스트 ===")
    nearby_places = await verifier.search_nearby_places(
        37.5665, 126.9780, radius=1000
    )  # 서울 시청 주변
    print(f"서울 시청 주변 {len(nearby_places)}개 장소:")
    for place in nearby_places[:5]:  # 상위 5개만 출력
        print(f"  - {place['name']} ({place.get('rating', 'N/A')}⭐)")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_maps_verifier())
