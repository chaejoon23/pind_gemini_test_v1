"""
Audio/Subtitle Analysis Module
음성 및 자막에서 장소 정보를 추출하는 모듈
"""

import json
import logging
import os
import tempfile
from typing import List, Optional
from dataclasses import dataclass
import google.generativeai as genai
import yt_dlp
from openai import OpenAI

logger = logging.getLogger(__name__)


@dataclass
class LocationInfo:
    name: str
    lat: Optional[str]
    lng: Optional[str]
    confidence: float = 0.0
    source: str = "audio"

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "confidence": self.confidence,
            "source": self.source,
        }


class AudioSubtitleAnalyzer:
    """음성 및 자막 분석을 담당하는 클래스"""

    def __init__(self, gemini_api_key: str, openai_api_key: str = None):
        """
        Args:
            gemini_api_key: Gemini API 키
            openai_api_key: OpenAI API 키 (Whisper 사용)
        """
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        
        # OpenAI 클라이언트 초기화
        if openai_api_key:
            self.openai_client = OpenAI(api_key=openai_api_key)
        else:
            # 환경변수에서 API 키 가져오기
            openai_key = os.getenv("OPENAI_API_KEY")
            if openai_key:
                self.openai_client = OpenAI(api_key=openai_key)
            else:
                self.openai_client = None
                logger.warning("OpenAI API 키가 설정되지 않았습니다. 음성-텍스트 변환이 불가능합니다.")
        
        logger.info("Audio/Subtitle Analyzer 초기화 완료")

    def check_audio_availability(self, youtube_url: str) -> dict:
        """YouTube 영상의 음성/자막 가용성 확인"""
        try:
            ydl_opts = {
                "quiet": True,
                "no_warnings": True,
                "writesubtitles": False,
                "writeautomaticsub": False,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)

                # 자막 정보 확인
                subtitles = info.get("subtitles", {})
                automatic_captions = info.get("automatic_captions", {})

                # 음성 트랙 확인
                has_audio = info.get("acodec", "none") != "none"
                has_manual_subtitles = len(subtitles) > 0
                has_auto_subtitles = len(automatic_captions) > 0

                result = {
                    "has_audio": has_audio,
                    "has_manual_subtitles": has_manual_subtitles,
                    "has_auto_subtitles": has_auto_subtitles,
                    "available_subtitle_languages": list(subtitles.keys()),
                    "available_auto_caption_languages": list(automatic_captions.keys()),
                    "video_duration": info.get("duration", 0),
                    "video_title": info.get("title", ""),
                    "uploader": info.get("uploader", ""),
                }

                logger.info(f"음성/자막 가용성 확인 완료: {result}")
                return result

        except Exception as e:
            logger.error(f"음성/자막 가용성 확인 중 오류: {e}")
            return {
                "has_audio": True,  # 기본값으로 음성 있다고 가정
                "has_manual_subtitles": False,
                "has_auto_subtitles": False,
                "error": str(e),
            }

    def extract_audio_with_whisper(self, youtube_url: str) -> str:
        """YouTube 영상에서 오디오를 다운로드하고 Whisper로 텍스트 추출"""
        if not self.openai_client:
            logger.error("OpenAI 클라이언트가 설정되지 않았습니다.")
            return ""
            
        temp_audio_file = None
        try:
            # 임시 디렉토리에 오디오 파일 다운로드
            with tempfile.TemporaryDirectory() as temp_dir:
                ydl_opts = {
                    'format': 'bestaudio/best',
                    'extractaudio': True,
                    'audioformat': 'mp3',
                    'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
                    'quiet': True,
                    'no_warnings': True,
                    'postprocessors': [{
                        'key': 'FFmpegExtractAudio',
                        'preferredcodec': 'mp3',
                        'preferredquality': '192',
                    }],
                }
                
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    info = ydl.extract_info(youtube_url, download=True)
                    
                # 다운로드된 파일 찾기
                for file in os.listdir(temp_dir):
                    if file.endswith('.mp3'):
                        temp_audio_file = os.path.join(temp_dir, file)
                        break
                        
                if not temp_audio_file or not os.path.exists(temp_audio_file):
                    logger.error("오디오 파일 다운로드 실패")
                    return ""
                
                logger.info(f"오디오 파일 다운로드 완료: {temp_audio_file}")
                print(f"🎵 오디오 파일 크기: {os.path.getsize(temp_audio_file) / (1024*1024):.1f} MB")
                
                # OpenAI Whisper로 음성-텍스트 변환
                with open(temp_audio_file, 'rb') as audio_file:
                    print("🤖 Whisper로 음성-텍스트 변환 중...")
                    transcript = self.openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio_file,
                        language="ko",  # 한국어 우선, 자동 감지도 가능
                    )
                    
                transcribed_text = transcript.text
                logger.info(f"Whisper 변환 완료: {len(transcribed_text)} 문자")
                print(f"📝 변환된 텍스트 길이: {len(transcribed_text)} 문자")
                print(f"📝 텍스트 미리보기: {transcribed_text[:200]}..." if len(transcribed_text) > 200 else f"📝 전체 텍스트: {transcribed_text}")
                
                return transcribed_text
                
        except Exception as e:
            logger.error(f"Whisper 음성-텍스트 변환 중 오류: {e}")
            print(f"❌ Whisper 변환 오류: {e}")
            return ""
    
    def extract_subtitle_text(self, youtube_url: str) -> str:
        """YouTube 영상에서 자막 텍스트 추출 (후순위)"""
        try:
            ydl_opts = {
                "writesubtitles": True,
                "writeautomaticsub": True,
                "subtitleslangs": ["ko", "en"],
                "skip_download": True,
                "subtitlesformat": "vtt",
                "outtmpl": "/tmp/%(title)s.%(ext)s",
                "quiet": True,
                "no_warnings": True,
            }

            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)

                # 자막 추출 시도
                subtitle_text = ""

                # 수동 자막 우선
                subtitles = info.get("subtitles", {})
                automatic_captions = info.get("automatic_captions", {})

                # 한국어 자막 우선, 없으면 영어, 없으면 첫 번째
                languages_to_try = ["ko", "en"]

                for lang in languages_to_try:
                    if lang in subtitles:
                        # 수동 자막 사용
                        subtitle_url = subtitles[lang][0]["url"]
                        subtitle_text = self._download_subtitle_content(subtitle_url)
                        logger.info(f"수동 자막 사용 (언어: {lang})")
                        break
                    elif lang in automatic_captions:
                        # 자동 자막 사용
                        subtitle_url = automatic_captions[lang][0]["url"]
                        subtitle_text = self._download_subtitle_content(subtitle_url)
                        logger.info(f"자동 자막 사용 (언어: {lang})")
                        break

                # 위 언어들이 없으면 첫 번째 이용 가능한 자막 사용
                if not subtitle_text:
                    if subtitles:
                        first_lang = list(subtitles.keys())[0]
                        subtitle_url = subtitles[first_lang][0]["url"]
                        subtitle_text = self._download_subtitle_content(subtitle_url)
                        logger.info(f"첫 번째 수동 자막 사용 (언어: {first_lang})")
                    elif automatic_captions:
                        first_lang = list(automatic_captions.keys())[0]
                        subtitle_url = automatic_captions[first_lang][0]["url"]
                        subtitle_text = self._download_subtitle_content(subtitle_url)
                        logger.info(f"첫 번째 자동 자막 사용 (언어: {first_lang})")

                return subtitle_text

        except Exception as e:
            logger.error(f"자막 텍스트 추출 중 오류: {e}")
            return ""

    def _download_subtitle_content(self, subtitle_url: str) -> str:
        """자막 URL에서 실제 텍스트 내용 다운로드"""
        try:
            import urllib.request
            import re

            with urllib.request.urlopen(subtitle_url) as response:
                subtitle_content = response.read().decode("utf-8")

            # VTT 형식에서 텍스트만 추출
            lines = subtitle_content.split("\n")
            text_lines = []

            for line in lines:
                line = line.strip()
                # 시간 코드 라인 제거 (00:00:00.000 --> 00:00:05.000 형식)
                if (
                    "-->" in line
                    or line.startswith("WEBVTT")
                    or line.startswith("NOTE")
                ):
                    continue
                # 빈 라인 제거
                if not line:
                    continue
                # HTML 태그 제거
                line = re.sub(r"<[^>]+>", "", line)
                # 특수 문자 정리
                line = re.sub(r"&[a-zA-Z]+;", "", line)

                if line:
                    text_lines.append(line)

            return " ".join(text_lines)

        except Exception as e:
            logger.error(f"자막 내용 다운로드 중 오류: {e}")
            return ""

    async def extract_locations_from_audio(
        self, youtube_url: str
    ) -> List[LocationInfo]:
        """음성 및 자막에서 장소 정보 추출 - 자막이 있으면 자막 사용, 없으면 음성을 텍스트로 변환"""
        try:
            # 자막 가용성 확인
            availability = self.check_audio_availability(youtube_url)

            # Whisper를 우선으로 사용하여 텍스트 추출
            extracted_text = ""
            content_source = "none"

            # 먼저 Whisper로 오디오-텍스트 변환 시도
            if self.openai_client:
                logger.info("Whisper를 사용하여 오디오에서 텍스트 추출")
                extracted_text = self.extract_audio_with_whisper(youtube_url)
                content_source = "whisper"

            # Whisper가 실패하면 자막 사용
            if not extracted_text:
                if availability.get("has_manual_subtitles") or availability.get(
                    "has_auto_subtitles"
                ):
                    logger.info("자막을 사용하여 장소 정보 추출")
                    extracted_text = self.extract_subtitle_text(youtube_url)
                    content_source = "subtitles"
                    if extracted_text:
                        print(f"📝 추출된 자막 텍스트 길이: {len(extracted_text)} 문자")
                        print(
                            f"📝 자막 미리보기: {extracted_text[:200]}..."
                            if len(extracted_text) > 200
                            else f"📝 자막 전체: {extracted_text}"
                        )

            if not extracted_text:
                logger.warning("텍스트를 추출할 수 없습니다.")
                print("❌ 텍스트 추출 실패")
                return []

            prompt = f"""
You are an expert AI specializing in analyzing YouTube content to extract specific restaurant and cafe names.
Your task is to identify all the specific names of places like restaurants, cafes, bakeries, and food stalls that are mentioned in the provided transcript.

Instructions:
1. Focus only on specific, proper names of establishments (actual business names).
2. Exclude general locations like neighborhood names or "near X station" unless they are part of a specific store name.
3. Do not extract addresses or generic descriptions.
4. Return the results as a JSON array of objects. Each object must contain "name", "lat", and "lng" keys.
5. For "lat" and "lng", use null values (the coordinates will be filled later by a maps verification service).
6. If no specific establishment names are found, return an empty array [].
7. The final output must be only the JSON array, with no other text or explanations.

Analyze this transcript:
{extracted_text}

The output should be formatted as a JSON instance that conforms to the JSON schema below.
{{
  "type": "array",
  "items": {{
    "type": "object",
    "properties": {{
      "name": {{
        "type": "string"
      }},
      "lat": {{
        "type": ["string", "null"]
      }},
      "lng": {{
        "type": ["string", "null"]
      }}
    }},
    "required": [
      "name",
      "lat",
      "lng"
    ]
  }}
}}"""

            logger.info(f"음성/자막 분석 시작: {youtube_url} (소스: {content_source})")
            print(f"🔍 Audio Analyzer가 사용 중인 URL: {youtube_url}")

            # 실제 텍스트를 사용하여 Gemini API 호출
            response = self.model.generate_content(prompt)

            # JSON 응답 파싱
            response_text = response.text.strip()
            logger.info(f"Gemini 응답 (처음 500자): {response_text[:500]}")
            print(f"🤖 Audio Gemini API 응답 미리보기:\n{response_text[:500]}...")

            # 코드 블록 제거
            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            elif response_text.startswith("```"):
                response_text = response_text[3:-3].strip()

            try:
                locations_data = json.loads(response_text)
                print(f"✅ Audio JSON 파싱 성공: {len(locations_data)}개 항목")
            except json.JSONDecodeError as e:
                print(f"❌ Audio JSON 파싱 오류: {e}")
                print(f"📄 전체 응답 텍스트:\n{response_text}")
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
                        source=content_source,
                    )
                    locations.append(location)
                else:
                    logger.warning(f"잘못된 형식의 장소 데이터: {loc_data}")

            logger.info(f"음성/자막에서 {len(locations)}개 장소 추출 완료")
            return locations

        except Exception as e:
            logger.error(f"음성/자막 장소 추출 중 오류: {e}")
            return []

    async def analyze_with_transcript_only(
        self, youtube_url: str
    ) -> List[LocationInfo]:
        """자막만 사용하여 장소 정보 추출 (음성 제외)"""
        try:
            # 실제 자막 텍스트 추출
            subtitle_text = self.extract_subtitle_text(youtube_url)
            if not subtitle_text:
                logger.warning("자막 텍스트를 추출할 수 없습니다.")
                return []

            prompt = f"""
You are an expert AI specializing in analyzing YouTube content to extract specific restaurant and cafe names.
Your task is to identify all the specific names of places like restaurants, cafes, bakeries, and food stalls that are mentioned in the provided transcript.

Instructions:
1. Focus only on specific, proper names of establishments (actual business names).
2. Exclude general locations like neighborhood names or "near X station" unless they are part of a specific store name.
3. Do not extract addresses or generic descriptions.
4. Return the results as a JSON array of objects. Each object must contain "name", "lat", and "lng" keys.
5. For "lat" and "lng", use null values (the coordinates will be filled later by a maps verification service).
6. If no specific establishment names are found, return an empty array [].
7. The final output must be only the JSON array, with no other text or explanations.

Analyze this transcript:
{subtitle_text}

The output should be formatted as a JSON instance that conforms to the JSON schema below.
{{
  "type": "array",
  "items": {{
    "type": "object",
    "properties": {{
      "name": {{
        "type": "string"
      }},
      "lat": {{
        "type": ["string", "null"]
      }},
      "lng": {{
        "type": ["string", "null"]
      }}
    }},
    "required": [
      "name",
      "lat",
      "lng"
    ]
  }}
}}"""

            logger.info(f"자막 전용 분석 시작: {youtube_url}")
            response = self.model.generate_content(prompt)

            # JSON 응답 파싱
            response_text = response.text.strip()
            logger.debug(f"Gemini 응답: {response_text}")

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
                        source="subtitles",
                    )
                    locations.append(location)
                else:
                    logger.warning(f"잘못된 형식의 장소 데이터: {loc_data}")

            logger.info(f"자막에서 {len(locations)}개 장소 추출 완료")
            return locations

        except Exception as e:
            logger.error(f"자막 분석 중 오류: {e}")
            return []

    async def analyze_with_audio_only(self, youtube_url: str) -> List[LocationInfo]:
        """음성만 사용하여 장소 정보 추출 (자막 제외)"""
        try:
            if not self.openai_client:
                logger.error("OpenAI API 키가 설정되지 않았습니다.")
                print("❌ OpenAI API 키가 설정되지 않았습니다.")
                return []
                
            # Whisper로 오디오-텍스트 변환
            extracted_text = self.extract_audio_with_whisper(youtube_url)
            
            if not extracted_text:
                logger.warning("오디오에서 텍스트를 추출할 수 없습니다.")
                return []
            
            prompt = f"""
You are an expert AI specializing in analyzing YouTube content to extract specific restaurant and cafe names.
Your task is to identify all the specific names of places like restaurants, cafes, bakeries, and food stalls that are mentioned in the provided transcript.

Instructions:
1. Focus only on specific, proper names of establishments (actual business names).
2. Exclude general locations like neighborhood names or "near X station" unless they are part of a specific store name.
3. Do not extract addresses or generic descriptions.
4. Return the results as a JSON array of objects. Each object must contain "name", "lat", and "lng" keys.
5. For "lat" and "lng", use null values (the coordinates will be filled later by a maps verification service).
6. If no specific establishment names are found, return an empty array [].
7. The final output must be only the JSON array, with no other text or explanations.

Analyze this transcript:
{extracted_text}

The output should be formatted as a JSON instance that conforms to the JSON schema below.
{{
  "type": "array",
  "items": {{
    "type": "object",
    "properties": {{
      "name": {{
        "type": "string"
      }},
      "lat": {{
        "type": ["string", "null"]
      }},
      "lng": {{
        "type": ["string", "null"]
      }}
    }},
    "required": [
      "name",
      "lat",
      "lng"
    ]
  }}
}}"""
            
            logger.info(f"오디오 전용 분석 시작: {youtube_url}")
            response = self.model.generate_content(prompt)
            
            # JSON 응답 파싱
            response_text = response.text.strip()
            logger.debug(f"Gemini 응답: {response_text}")

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
                        source="whisper",
                    )
                    locations.append(location)
                else:
                    logger.warning(f"잘못된 형식의 장소 데이터: {loc_data}")

            logger.info(f"오디오에서 {len(locations)}개 장소 추출 완료")
            return locations
            
        except Exception as e:
            logger.error(f"음성 분석 중 오류: {e}")
            return []

    def get_analysis_stats(self, locations: List[LocationInfo]) -> dict:
        """분석 결과 통계 생성"""
        if not locations:
            return {
                "total_locations": 0,
                "with_coordinates": 0,
                "without_coordinates": 0,
                "average_confidence": 0.0,
                "confidence_distribution": {},
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
        }


# 독립 실행 및 테스트 함수들
async def test_audio_analyzer():
    """음성/자막 분석기 테스트 함수"""
    from dotenv import load_dotenv
    import os

    load_dotenv()

    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    
    if not GEMINI_API_KEY:
        print("❌ GEMINI_API_KEY가 설정되지 않았습니다.")
        return
        
    if not OPENAI_API_KEY:
        print("⚠️ OPENAI_API_KEY가 설정되지 않았습니다. Whisper 기능이 비활성화됩니다.")

    analyzer = AudioSubtitleAnalyzer(GEMINI_API_KEY, OPENAI_API_KEY)

    # 테스트용 YouTube URL (환경변수에서 가져오거나 기본값 사용)
    test_url = os.getenv(
        "TEST_YOUTUBE_URL", "https://www.youtube.com/watch?v=kXbrLk_aqvs"
    )

    print("🔍 음성/자막 가용성 확인...")
    availability = analyzer.check_audio_availability(test_url)
    print(f"가용성 정보: {json.dumps(availability, indent=2, ensure_ascii=False)}")

    print("\n🎵 음성/자막 장소 분석...")
    locations = await analyzer.extract_locations_from_audio(test_url)

    print(f"\n📊 분석 결과:")
    for i, loc in enumerate(locations, 1):
        print(f"{i}. {loc.name}")
        print(f"좌표: {loc.lat}, {loc.lng}")
        print(f"신뢰도: {loc.confidence}")
        print()

    print("📈 통계:")
    stats = analyzer.get_analysis_stats(locations)
    print(json.dumps(stats, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    import asyncio

    asyncio.run(test_audio_analyzer())
