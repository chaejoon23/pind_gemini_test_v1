"""
Audio/Subtitle Analysis Module
음성 및 자막에서 장소 정보를 추출하는 모듈
"""

import json
import logging
import os
import tempfile
from typing import List, Optional, Tuple
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
        genai.configure(api_key=gemini_api_key)
        self.model = genai.GenerativeModel("gemini-2.5-flash")
        self.openai_client = OpenAI(api_key=openai_api_key) if openai_api_key else None
        if not self.openai_client:
            logger.warning("OpenAI API 키가 설정되지 않았습니다. 음성-텍스트 변환이 불가능합니다.")
        logger.info("Audio/Subtitle Analyzer 초기화 완료")

    def _get_transcript(self, youtube_url: str) -> str:
        """Whisper 또는 자막을 통해 스크립트를 추출합니다."""
        if self.openai_client:
            logger.info("Whisper를 사용하여 오디오에서 텍스트 추출")
            try:
                return self._extract_audio_with_whisper(youtube_url)
            except Exception as e:
                logger.error(f"Whisper 처리 중 오류, 자막으로 대체: {e}")
        
        logger.info("자막을 사용하여 텍스트 추출")
        return self._extract_subtitle_text(youtube_url)

    def _extract_audio_with_whisper(self, youtube_url: str) -> str:
        """YouTube 영상에서 오디오를 다운로드하고 Whisper로 텍스트 추출"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': os.path.join(temp_dir, 'audio.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                }],
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(youtube_url, download=True)
            
            audio_file_path = os.path.join(temp_dir, 'audio.mp3')
            if not os.path.exists(audio_file_path):
                raise FileNotFoundError("오디오 파일 다운로드 실패")

            with open(audio_file_path, 'rb') as audio_file:
                transcript = self.openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio_file,
                )
            return transcript.text

    def _extract_subtitle_text(self, youtube_url: str) -> str:
        """YouTube 영상에서 사용 가능한 첫 번째 자막 텍스트 추출"""
        with tempfile.TemporaryDirectory() as temp_dir:
            ydl_opts = {
                'writesubtitles': True,
                'writeautomaticsub': True,
                'skip_download': True,
                'subtitlesformat': 'vtt',
                'outtmpl': os.path.join(temp_dir, 'subtitle.%(ext)s'),
                'quiet': True,
                'no_warnings': True,
            }
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(youtube_url, download=False)

            subtitles = info.get('subtitles', {})
            auto_captions = info.get('automatic_captions', {})
            
            subtitle_info = subtitles or auto_captions
            if not subtitle_info:
                return ""

            lang = list(subtitle_info.keys())[0]
            subtitle_url = subtitle_info[lang][0]["url"]
            
            import requests
            response = requests.get(subtitle_url)
            response.raise_for_status()
            
            import re
            lines = response.text.splitlines()
            text_lines = [re.sub(r'<[^>]+>', '', line) for line in lines if line and '-->' not in line and not line.startswith(("WEBVTT", "NOTE"))]
            return " ".join(text_lines)

    async def extract_locations_and_area_from_audio(
        self, youtube_url: str
    ) -> Tuple[str, List[LocationInfo]]:
        """음성/자막에서 장소 정보와 주요 지역을 함께 추출"""
        try:
            extracted_text = self._get_transcript(youtube_url)
            if not extracted_text:
                logger.warning("텍스트를 추출할 수 없습니다.")
                return "Unknown", []

            prompt = f'''
You are an expert AI analyzing a transcript from a YouTube video. Your task is to perform two actions:
1. Identify the primary geographic area discussed, such as the Country and City. 
2. Extract all specific names of places like restaurants, cafes, and shops mentioned in the transcript.

OUTPUT FORMAT:
Return a single JSON object with two keys: "search_area" and "locations".
- The "search_area" value should be a string like "Country, City" (e.g., "South Korea, Seoul" or "Japan, Tokyo"). If no specific area is mentioned, use the most likely area based on context or return "Unknown".
- The "locations" value should be a JSON array of objects, where each object has "name", "lat": null, "lng": null.

Analyze this transcript:
{extracted_text}

The output must be a single JSON object conforming to this schema:
{{
  "type": "object",
  "properties": {{
    "search_area": {{ "type": "string" }},
    "locations": {{
      "type": "array",
      "items": {{
        "type": "object",
        "properties": {{
          "name": {{ "type": "string" }},
          "lat": {{ "type": ["string", "null"] }},
          "lng": {{ "type": ["string", "null"] }}
        }},
        "required": ["name", "lat", "lng"]
      }}
    }}
  }},
  "required": ["search_area", "locations"]
}}
            '''

            response = self.model.generate_content(prompt)
            response_text = response.text.strip()

            if response_text.startswith("```json"):
                response_text = response_text[7:-3].strip()
            
            result_data = json.loads(response_text)
            search_area = result_data.get("search_area", "Unknown")
            locations_data = result_data.get("locations", [])

            locations = [
                LocationInfo(
                    name=loc.get("name", ""),
                    lat=loc.get("lat"),
                    lng=loc.get("lng"),
                    source="audio"
                )
                for loc in locations_data if isinstance(loc, dict) and "name" in loc
            ]

            logger.info(f"음성/자막에서 {len(locations)}개 장소와 지역 '{search_area}' 추출 완료")
            return search_area, locations

        except Exception as e:
            logger.error(f"음성/자막 장소 및 지역 추출 중 오류: {e}")
            return "Unknown", []