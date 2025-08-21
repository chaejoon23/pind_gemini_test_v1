"""
Visual Keyframe Analysis Module
영상의 키프레임을 분석하여 장소 정보를 추출하는 모듈
"""

import json
import logging
from typing import List, Optional, Dict
from dataclasses import dataclass
import google.generativeai as genai
import os
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class LocationInfo:
    name: str
    lat: Optional[str]
    lng: Optional[str]
    confidence: float = 0.0
    source: str = "visual"
    reasoning: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "source": self.source,
            "reasoning": self.reasoning,
        }


class VisualFrameAnalyzer:
    """시각적 프레임 분석을 담당하는 클래스"""

    def __init__(self, gemini_api_key: str):
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        logger.info("Visual Frame Analyzer 초기화 완료")

    

    async def extract_locations_from_frames(
        self,
        youtube_url: str,
        country_context: Optional[str] = None,
        custom_prompt: Optional[str] = None,
    ) -> List[LocationInfo]:
        """영상 프레임에서 장소 정보 추출 (국가 컨텍스트 사용)"""
        try:
            country_instruction = ""
            if country_context and country_context.lower() != "unknown":
                country_instruction = f'5. **Country Context:** This video takes place in **{country_context}**. All identified locations MUST be within this country. Do not suggest locations from other countries.'

            prompt = (
                custom_prompt
                or f'''
You are a highly precise visual analyst AI. Your mission is to meticulously analyze the provided YouTube video to identify the specific, primary locations the creator visits, such as cafes, restaurants, or shops.

**CRITICAL INSTRUCTIONS:**

1.  **Primary Focus Only:** Your main goal is to identify the **specific, named locations that are the primary subject** of a scene (e.g., where the creator sits down, eats, or shops). Do NOT list every sign visible in the background.
2.  **Avoid Generic & Chain Stores:** Do NOT identify large, common franchise stores (e.g., Olive Young, Starbucks, convenience stores) or general landmarks unless the creator spends significant time there as a main activity. Focus on unique, independent shops, cafes, and restaurants which are the likely purpose of the visit.
3.  **No Guessing:** If you cannot identify a specific name for a location from clear visual evidence (e.g., a sign, menu, or logo), do NOT include it. It is better to have fewer, accurate results than many speculative ones. Do not invent or hallucinate locations.
4.  **Mandatory Visual Evidence:** For every location you identify, you MUST describe the specific visual evidence (e.g., "The cafe\'s name \'Cafe De-ryu\' was clearly visible on a white sign above the entrance at 1:23," or "The logo \'Mamma Mia\' was printed on the coffee cup at 3:45.")
{country_instruction}

**OUTPUT FORMAT:**

Return the results as a JSON array of objects. The final output must be **only the JSON array**, with no other text or explanations. Each object must conform to the following schema:

{{
  "type": "array",
  "items": {{
    "type": "object",
    "properties": {{
      "name": {{
        "type": "string",
        "description": "The precise, proper name of the location."
      }},
      "lat": {{ "type": ["string", "null"] }},
      "lng": {{ "type": ["string", "null"] }},
      "confidence": {{
        "type": "number",
        "description": "A confidence score from 0.0 to 1.0 on how certain you are about the location\'s name based on the visual evidence. 0.9 or higher is preferred."
      }},
      "reasoning": {{
        "type": "string",
        "description": "A brief explanation of the visual evidence used for identification."
      }}
    }},
    "required": ["name", "lat", "lng", "confidence", "reasoning"]
  }}
}}
            '''
            )

            logger.info(f"시각적 프레임 분석 시작: {youtube_url} (국가: {country_context or 'N/A'})")
            print(f"🔍 Visual Analyzer가 사용 중인 URL: {youtube_url}")

            response = self.model.generate_content([prompt, youtube_url])
            response_text = response.text.strip()
            logger.info(f"Visual Gemini 응답 (처음 500자): {response_text[:500]}")
            print(f"🤖 Visual Gemini API 응답 미리보기:\n{response_text[:500]}...")

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

            locations = []
            for loc_data in locations_data:
                if isinstance(loc_data, dict) and "name" in loc_data:
                    locations.append(LocationInfo(
                        name=loc_data.get("name", ""),
                        lat=loc_data.get("lat"),
                        lng=loc_data.get("lng"),
                        confidence=loc_data.get("confidence", 0.5),
                        source="visual",
                        reasoning=loc_data.get("reasoning"),
                    ))
                else:
                    logger.warning(f"잘못된 형식의 장소 데이터: {loc_data}")

            logger.info(f"시각적 분석에서 {len(locations)}개 장소 추출 완료")
            return locations

        except Exception as e:
            logger.error(f"시각적 프레임 장소 추출 중 오류: {e}")
            return []

    

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
        avg_confidence = sum(loc.confidence for loc in locations) / len(locations) if locations else 0.0

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

    # 테스트용 YouTube URL (환경변수에서 가져와야 함)
    test_url = os.getenv("TEST_YOUTUBE_URL")
    if not test_url:
        print("❌ 테스트를 위한 TEST_YOUTUBE_URL 환경변수가 설정되지 않았습니다.")
        return

    print("🎬 2단계 컨텍스트 분석 시작...")
    locations = await analyzer.analyze_video_with_country_context(test_url)

    print(f"\n📊 분석 결과:")
    for i, loc in enumerate(locations, 1):
        print(f"{i}. {loc.name} (신뢰도: {loc.confidence:.2f})")
        print(f"   - 좌표: {loc.lat}, {loc.lng}")
        print(f"   - 근거: {loc.reasoning}")
        print()

    print("📈 통계:")
    stats = analyzer.get_visual_analysis_stats(locations)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_visual_analyzer())
