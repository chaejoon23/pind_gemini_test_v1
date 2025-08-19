# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a YouTube Location Extractor system that analyzes YouTube videos to extract geographical location information using multiple AI-powered approaches:

1. **Audio/Subtitle Analysis** (`audio_analyzer.py`) - Extracts location mentions from spoken content and captions
2. **Visual Frame Analysis** (`visual_analyzer.py`) - Identifies locations from video frames using GeoGuessr-style visual clues
3. **Maps Verification** (`maps_verifier.py`) - Validates and enriches extracted locations using Google Maps API
4. **Integrated Pipeline** (`intergrated_tester.py`) - Combines all three approaches for comprehensive analysis

## Architecture

### Core Modules

- **AudioSubtitleAnalyzer**: Uses Gemini API to analyze audio/subtitles for location references
- **VisualFrameAnalyzer**: Uses Gemini API to analyze video frames for visual location clues (architecture, signs, landscapes)
- **GoogleMapsVerifier**: Validates locations using Google Places/Maps API, provides coordinates and detailed place information
- **IntegratedLocationExtractor**: Orchestrates all analyzers, removes duplicates, and produces final results

### Data Flow

```
YouTube URL → Audio Analysis → Location Candidates
              ↓
YouTube URL → Visual Analysis → Location Candidates
              ↓
Combined Candidates → Maps Verification → Verified Locations
```

### LocationInfo Data Structure

Each module uses a `LocationInfo` dataclass with fields:

- `name`: Location name as extracted/mentioned
- `lat`/`lng`: Coordinates (optional initially, filled by Maps verification)
- `confidence`: Float 0-1 indicating extraction confidence
- `source`: "audio", "visual", or "verified"
- Additional verification fields for Maps results

## Environment Configuration

Required environment variables (`.env` file):

```bash
# Required
GEMINI_API_KEY=your_gemini_api_key
GOOGLE_CLOUD_PROJECT_ID=your_project_id

# Optional (Maps verification)
GOOGLE_MAPS_API_KEY=your_maps_api_key
```

## Common Development Tasks

### Setup Environment

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp .env.example .env  # Edit with your API keys
```

### Run Individual Tests

```bash
# Interactive test runner
python run_test.py

# Audio analysis only
python audio_analyzer.py

# Visual analysis only
python visual_analyzer.py

# Maps verification only
python maps_verifier.py

# Full integrated pipeline
python integrated_tester.py
```

### Test Specific Scenarios

```bash
# Test with custom YouTube URL
python run_test.py all https://www.youtube.com/watch?v=VIDEO_ID

# Run comparison analysis
python integrated_tester.py --test comparison --url YOUR_URL

# Save results to specific file
python integrated_tester.py --save results.json
```

### Build and Test

```bash
# Run all tests
python run_test.py all

# Run specific module tests
python run_test.py audio
python run_test.py visual
python run_test.py maps
python run_test.py integrated

# Batch mode with URL
python run_test.py all https://www.youtube.com/watch?v=VIDEO_ID
```

## Key Implementation Details

### Gemini API Integration

- Uses `google.genai.Client` for both audio and visual analysis
- Model: "gemini-2.5-flash" for all requests
- Structured JSON responses with confidence scoring
- Custom prompts optimized for location extraction vs visual geolocation

### Visual Analysis Approaches

- **General Analysis**: Comprehensive frame analysis
- **Architectural Focus**: Building styles and regional characteristics
- **Signage Analysis**: Text, signs, and language detection
- **Environmental Analysis**: Natural features and climate indicators
- **High-precision Mode**: More frames sampled for critical accuracy

### Maps Verification Pipeline

1. **Name Search**: Google Places API text search
2. **Coordinate Verification**: Reverse geocoding for provided coordinates
3. **Distance Calculation**: Haversine formula for coordinate comparison
4. **Confidence Adjustment**: Boost/reduce confidence based on verification results
5. **Data Enrichment**: Add place IDs, addresses, ratings, and place types

### Error Handling Patterns

- Graceful degradation when APIs are unavailable
- JSON parsing with fallback for malformed responses
- Distance thresholds for coordinate validation (default 10km)
- Confidence scoring adjustments based on verification success

### Testing Framework

- Individual module testing with mock data
- Integration testing with real YouTube URLs
- Performance comparison between analysis methods
- Automated result validation and statistics generation
- JSON output format for result persistence

## API Dependencies

### Google APIs Required

1. **Gemini API**: For AI-powered content analysis
2. **Google Places API**: For location name verification
3. **Google Geocoding API**: For coordinate validation
4. **Google Maps API**: For place details and nearby search

### External Dependencies

- `yt-dlp`: YouTube metadata extraction
- `googlemaps`: Google Maps API client
- `google-generativeai`: Gemini API client
- `fastapi`/`uvicorn`: Web framework (not actively used in current implementation)

## Performance Considerations

- Audio analysis typically faster than visual analysis
- Visual analysis with higher FPS sampling increases accuracy but processing time
- Maps verification adds latency but significantly improves result reliability
- Parallel execution of audio + visual analysis recommended
- Results caching beneficial for repeated analyses

## Known Limitations

- Requires valid API keys for full functionality
- Visual analysis accuracy depends on video quality and distinctive landmarks
- Audio analysis limited by speech clarity and subtitle availability
- Maps API has usage quotas and rate limits
- Processing time scales with video length and complexity

## Replys

- Answer in Korean unless I say "in English"
- when I just put error code, analyz it and solve it
