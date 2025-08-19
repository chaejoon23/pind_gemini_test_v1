"""
Visual Keyframe Analysis Module
영상의 키프레임을 분석하여 장소 정보를 추출하는 모듈
"""

import json
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
import google.generativeai as genai

logger = logging.getLogger(__name__)


@dataclass
class LocationInfo:
    name: str
    lat: Optional[str]
    lng: Optional[str]
    confidence: float = 0.0
    source: str = "visual"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "source": self.source,
        }


class VisualFrameAnalyzer:
    """시각적 프레임 분석을 담당하는 클래스"""

    def __init__(self, gemini_api_key: str):
        """
        Args:
            gemini_api_key: Gemini API 키
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Visual Frame Analyzer 초기화 완료")

    async def extract_locations_from_frames(
        self,
        youtube_url: str,
        fps_sampling: float = 0.5,
        custom_prompt: Optional[str] = None,
    ) -> List[LocationInfo]:
        """영상 프레임에서 장소 정보 추출"""
        try:
            # 기본 프롬프트 또는 커스텀 프롬프트 사용
            prompt = (
                custom_prompt
                or """
            You are an expert travel vlog analyst, similar to a GeoGuessr pro specializing in urban exploration. 
            Your goal is to analyze this YouTube vlog to identify and extract specific points of interest (POIs) that the creator visits.

            ## Key Locations to Identify (Prioritize these):
            1.  **Cafes & Restaurants**: Look for storefronts, signs with names, menus, unique interior designs, logos on cups or packaging.
            2.  **Shops & Stores**: Identify brand names, product displays, or specific store names mentioned or shown.
            3.  **Exhibition Spaces & Cultural Venues**: Find the names of galleries, museums, theaters, or specific exhibition posters and artworks shown.
            4.  **Notable Landmarks & Parks**: Well-known tourist spots, monuments, or parks that are clearly identifiable.

            ## Visual Clues to Examine for Evidence:
            - **Signage and Text**: This is CRUCIAL. Meticulously read shop names, cafe menus, street signs, and posters.
            - **Storefronts and Interior Design**: Note the unique style, decor, and branding of interiors and exteriors.
            - **Products and Logos**: Look for branded items like coffee cups, shopping bags, or specific products.
            - **Architectural Styles**: Identify unique building characteristics.
            - **Surrounding Environment**: Use nearby street signs, landmarks, or landscape to pinpoint the location.

            ## Output Instructions:
            - For each specific location found, provide its precise name. Avoid generic descriptions like "a street in Seoul".
            - For each location, add a 'category' based on the list above.
            - Explain the visual clues that led to your identification.
            
            Correct Output:
The output should be formatted as a JSON instance that conforms to the JSON schema below.
{
  type: 'array',
  $schema: 'http://json-schema.org/draft-04/schema#',
  description: '',
  minItems: 1,
  uniqueItems: true,
  items: {
    type: 'object',
    required: [
      'name',
      'lat',
      'lng',
    ],
    properties: {
      name: {
        type: 'string',
        minLength: 1,
      },
      lat: {
        type: 'string',
      },
      lng: {
        type: 'string',
      },
    },
  },
}
            """
            )

            logger.info(f"시각적 프레임 분석 시작: {youtube_url} (FPS: {fps_sampling})")
            print(f"🔍 Visual Analyzer가 사용 중인 URL: {youtube_url}")

            # Gemini의 비디오 처리
            response = self.model.generate_content([prompt, youtube_url])

            # JSON 응답 파싱
            response_text = response.text.strip()
            logger.info(f"Visual Gemini 응답 (처음 500자): {response_text[:500]}")
            print(f"🤖 Visual Gemini API 응답 미리보기:\n{response_text[:500]}...")

            # 코드 블록 제거
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()

            try:
                locations_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.error(f"JSON 파싱 오류: {e}")
                logger.error(f"응답 텍스트: {response_text}")
                return []

            # LocationInfo 객체 생성
            locations = []
            for loc_data in locations_data:
                if isinstance(loc_data, dict) and "name" in loc_data:
                    location = LocationInfo(
                        name=loc_data.get("name", ""),
                        lat=loc_data.get("lat"),
                        lng=loc_data.get("lng"),
                        confidence=loc_data.get("confidence", 0.5),
                        source="visual",
                    )
                    locations.append(location)
                else:
                    logger.warning(f"잘못된 형식의 장소 데이터: {loc_data}")

            logger.info(f"시각적 분석에서 {len(locations)}개 장소 추출 완료")
            return locations

        except Exception as e:
            logger.error(f"시각적 프레임 장소 추출 중 오류: {e}")
            return []

    async def analyze_architectural_style(self, youtube_url: str) -> List[LocationInfo]:
        """건축 양식에 중점을 둔 분석"""
        prompt = """
        Focus specifically on architectural styles visible in this video to determine the location.
        
        Look for:
        - Building materials (wood, stone, brick, concrete)
        - Roof styles and construction methods
        - Window and door designs
        - Architectural periods and influences
        - Regional building characteristics
        - Traditional vs modern architecture
        
        Respond ONLY in JSON array format:
        [{"name": "location_based_on_architecture", "lat": "latitude", "lng": "longitude", "confidence": 0.7}]
        """

        return await self.extract_locations_from_frames(
            youtube_url, fps_sampling=0.3, custom_prompt=prompt
        )

    async def analyze_signage_and_text(self, youtube_url: str) -> List[LocationInfo]:
        """간판과 텍스트에 중점을 둔 분석"""
        prompt = """
        Focus specifically on visible text, signs, and written language in this video.
        
        Look for:
        - Street signs and road signs
        - Shop names and business signs
        - Advertisements and billboards
        - License plates and vehicle markings
        - Government or official signage
        - Language characteristics and scripts
        
        Respond ONLY in JSON array format:
        [{"name": "location_based_on_signage", "lat": "latitude", "lng": "longitude", "confidence": 0.8}]
        """

        return await self.extract_locations_from_frames(
            youtube_url, fps_sampling=0.7, custom_prompt=prompt
        )

    async def analyze_natural_environment(self, youtube_url: str) -> List[LocationInfo]:
        """자연환경에 중점을 둔 분석"""
        prompt = """
        Focus specifically on natural environment and geographical features visible in this video.
        
        Look for:
        - Vegetation types and plant species
        - Terrain and landscape characteristics
        - Climate indicators
        - Ocean, mountains, or distinctive geographical features
        - Weather patterns and seasonal indicators
        - Natural landmarks
        
        Respond ONLY in JSON array format:
        [{"name": "location_based_on_environment", "lat": "latitude", "lng": "longitude", "confidence": 0.6}]
        """

        return await self.extract_locations_from_frames(
            youtube_url, fps_sampling=0.4, custom_prompt=prompt
        )

    async def analyze_with_high_precision(self, youtube_url: str) -> List[LocationInfo]:
        """고정밀 분석 (더 많은 프레임 샘플링)"""
        prompt = """
        Perform a high-precision analysis of this video for location identification.
        Take extra care to identify subtle clues and cross-reference multiple visual elements.
        
        Only include locations you are highly confident about (confidence > 0.7).
        
        Respond ONLY in JSON array format:
        [{"name": "high_confidence_location", "lat": "latitude", "lng": "longitude", "confidence": 0.85}]
        """

        return await self.extract_locations_from_frames(
            youtube_url, fps_sampling=1.0, custom_prompt=prompt
        )

    def get_visual_analysis_stats(self, locations: List[LocationInfo]) -> dict:
        """시각적 분석 결과 통계 생성"""
        if not locations:
            return {
                "total_locations": 0,
                "with_coordinates": 0,
                "without_coordinates": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
                "analysis_type": "visual",
            }

        with_coords = len([loc for loc in locations if loc.lat and loc.lng])
        without_coords = len(locations) - with_coords
        avg_confidence = sum(loc.confidence for loc in locations) / len(locations)

        # 신뢰도 분포 계산
        confidence_ranges = {
            "high (0.8-1.0)": len([loc for loc in locations if loc.confidence >= 0.8]),
            "medium (0.5-0.8)": len(
                [loc for loc in locations if 0.5 <= loc.confidence < 0.8]
            ),
            "low (0.0-0.5)": len([loc for loc in locations if loc.confidence < 0.5]),
        }

        return {
            "total_locations": len(locations),
            "with_coordinates": with_coords,
            "without_coordinates": without_coords,
            "average_confidence": round(avg_confidence, 3),
            "confidence_distribution": confidence_ranges,
            "location_names": [loc.name for loc in locations],
            "analysis_type": "visual",
        }

    async def compare_analysis_methods(
        self, youtube_url: str
    ) -> Dict[str, List[LocationInfo]]:
        """다양한 분석 방법 비교"""
        logger.info("다양한 시각적 분석 방법 비교 시작...")

        results = {}

        # 일반 분석
        results["general"] = await self.extract_locations_from_frames(youtube_url)

        # 건축 중심 분석
        results["architectural"] = await self.analyze_architectural_style(youtube_url)

        # 간판/텍스트 중심 분석
        results["signage"] = await self.analyze_signage_and_text(youtube_url)

        # 자연환경 중심 분석
        results["environment"] = await self.analyze_natural_environment(youtube_url)

        # 고정밀 분석
        results["high_precision"] = await self.analyze_with_high_precision(youtube_url)

        logger.info("시각적 분석 방법 비교 완료")
        return results


# 독립 실행 및 테스트 함수들
async def test_visual_analyzer():
    """시각적 분석기 테스트 함수"""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return

    analyzer = VisualFrameAnalyzer(GEMINI_API_KEY)

    # 테스트용 YouTube URL (환경변수에서 가져오거나 기본값 사용)
    test_url = os.getenv(
        "TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=kXbrLk_aqvs"
    )

    print("🎬 시각적 프레임 장소 분석...")
    locations = await analyzer.extract_locations_from_frames(test_url)

    print(f"\n📊 분석 결과:")
    for i, loc in enumerate(locations, 1):
        print(f"{i}. {loc.name}")
        print(f"   좌표: {loc.lat}, {loc.lng}")
        print(f"   신뢰도: {loc.confidence}")
        print()

    print("📈 통계:")
    stats = analyzer.get_visual_analysis_stats(locations)
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    print("\n🔍 분석 방법 비교 테스트...")
    comparison = await analyzer.compare_analysis_methods(test_url)

    for method, method_locations in comparison.items():
        print(f"\n{method.upper()} 분석:")
        print(f"  - 추출된 장소 수: {len(method_locations)}")
        if method_locations:
            avg_conf = sum(loc.confidence for loc in method_locations) / len(
                method_locations
            )
            print(f"  - 평균 신뢰도: {avg_conf:.3f}")
            print(f"  - 장소들: {', '.join([loc.name for loc in method_locations])}")


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_visual_analyzer())
