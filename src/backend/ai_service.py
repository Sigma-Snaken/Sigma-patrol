"""
AI Service - Google Gemini Vision integration for inspection analysis.
"""

import json
import google.generativeai as genai
from pydantic import BaseModel, Field

from config import SETTINGS_FILE, DEFAULT_SETTINGS
from utils import load_json
from logger import get_logger

logger = get_logger("ai_service", "ai_service.log")


class InspectionResult(BaseModel):
    """Structured schema for inspection results."""
    is_NG: bool = Field(description="True if abnormal/NG, False if normal/OK")
    Description: str = Field(description="Issue description if NG, empty if OK")


def parse_ai_response(response_obj):
    """
    Parse AI service response into standardized format.

    Args:
        response_obj: Response from generate_inspection or generate_report

    Returns:
        dict with keys:
            - result_text: JSON string or text result
            - is_ng: bool (True if NG)
            - description: str (issue description)
            - prompt_tokens: int
            - candidate_tokens: int
            - total_tokens: int
            - usage_json: str (JSON string of usage data)
    """
    result = {
        'result_text': '',
        'is_ng': False,
        'description': '',
        'prompt_tokens': 0,
        'candidate_tokens': 0,
        'total_tokens': 0,
        'usage_json': '{}'
    }

    if not response_obj:
        return result

    # Handle dict response from AIService
    if isinstance(response_obj, dict) and "result" in response_obj:
        result_data = response_obj["result"]
        usage_data = response_obj.get("usage", {})

        result['usage_json'] = json.dumps(usage_data)
        result['prompt_tokens'] = usage_data.get("prompt_token_count", 0)
        result['candidate_tokens'] = usage_data.get("candidates_token_count", 0)
        result['total_tokens'] = usage_data.get("total_token_count", 0)
    else:
        result_data = response_obj

    # Parse result data
    if isinstance(result_data, dict):
        result['is_ng'] = result_data.get("is_NG", False)
        result['description'] = result_data.get("Description", "")
        result['result_text'] = json.dumps(result_data, ensure_ascii=False)
    elif isinstance(result_data, str):
        result['result_text'] = result_data
        result['description'] = result_data
        # Simple heuristic for string responses
        result['is_ng'] = 'ng' in result_data.lower()
    else:
        result['result_text'] = str(result_data)
        result['description'] = result['result_text']

    return result


class AIService:
    """Gemini AI service for visual inspection and report generation."""

    def __init__(self):
        self.model = None
        self.api_key = None
        self.model_name = "gemini-2.5-flash"
        self._configure()

    def _configure(self):
        """Load settings and configure Gemini client."""
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        new_api_key = settings.get("gemini_api_key")
        new_model_name = settings.get("gemini_model", "gemini-2.5-flash")

        if new_api_key != self.api_key or new_model_name != self.model_name or self.model is None:
            logger.info(f"Configuring AI Service with model: {new_model_name}")
            self.api_key = new_api_key
            self.model_name = new_model_name

            if self.api_key:
                try:
                    genai.configure(api_key=self.api_key)
                    self.model = genai.GenerativeModel(self.model_name)
                    logger.info("AI Service configured successfully.")
                except Exception as e:
                    logger.error(f"AI Service Configuration Error: {e}")
                    self.model = None
            else:
                logger.warning("AI Service configured without API Key.")
                self.model = None

    def get_model_name(self):
        """Get current model name."""
        self._configure()
        return self.model_name

    def is_configured(self):
        """Check if AI service is ready."""
        self._configure()
        return self.model is not None

    def _extract_usage(self, response):
        """Extract token usage from response."""
        try:
            usage = response.usage_metadata
            return {
                "prompt_token_count": usage.prompt_token_count,
                "candidates_token_count": usage.candidates_token_count,
                "total_token_count": usage.total_token_count
            }
        except Exception as e:
            logger.warning(f"Could not extract token usage: {e}")
            return {}

    def generate_inspection(self, image, user_prompt, system_prompt=None):
        """
        Analyze image with structured JSON response.

        Args:
            image: PIL Image object
            user_prompt: User's inspection question
            system_prompt: Optional system context

        Returns:
            dict with 'result' (parsed JSON) and 'usage' (token counts)
        """
        self._configure()

        if not self.model:
            raise Exception("AI Model not configured. Check API Key in settings.")

        parts = []
        if system_prompt:
            parts.append(system_prompt)
        parts.append(user_prompt)
        parts.append(image)

        config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=InspectionResult
        )

        try:
            logger.info(f"Inspection request to {self.model_name}")
            response = self.model.generate_content(parts, generation_config=config)
            usage_data = self._extract_usage(response)
            logger.info(f"Token Usage: {usage_data}")

            return {
                "result": json.loads(response.text),
                "usage": usage_data
            }
        except Exception as e:
            logger.error(f"Gemini Generation Error: {e}")
            raise

    def generate_report(self, report_prompt):
        """
        Generate text report from inspection results.

        Args:
            report_prompt: Prompt with inspection data

        Returns:
            dict with 'result' (text) and 'usage' (token counts)
        """
        self._configure()

        if not self.model:
            raise Exception("AI Model not configured.")

        try:
            logger.info(f"Report generation request to {self.model_name}")
            prompt = report_prompt or "Generate a summary report of the patrol."
            response = self.model.generate_content(prompt)
            usage_data = self._extract_usage(response)
            logger.info(f"Report Token Usage: {usage_data}")

            return {
                "result": response.text,
                "usage": usage_data
            }
        except Exception as e:
            logger.error(f"Gemini Report Error: {e}")
            raise

    def analyze_video(self, video_path, user_prompt):
        """
        Analyze video content using Gemini.
        
        Args:
            video_path: Path to video file
            user_prompt: Analysis prompt
            
        Returns:
            dict with 'result' (text) and 'usage' (token counts)
        """
        self._configure()
        
        if not self.model:
             raise Exception("AI Model not configured.")
             
        try:
            logger.info(f"Uploading video {video_path}...")
            video_file = genai.upload_file(path=video_path)
            
            # Wait for processing
            import time
            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = genai.get_file(video_file.name)
                
            if video_file.state.name == "FAILED":
                raise Exception("Video processing failed.")
                
            logger.info(f"Video ready. Analyzing with prompt: {user_prompt}")
            
            parts = [video_file, user_prompt]
            response = self.model.generate_content(parts)
            usage_data = self._extract_usage(response)
            
            # Cleanup? genai files persist for 48h. Maybe we want to keep it or let it expire.
            # We will let it expire for now or explicit delete if needed.
            
            return {
                "result": response.text,
                "usage": usage_data
            }
            
        except Exception as e:
            logger.error(f"Video Analysis Error: {e}")
            raise
ai_service = AIService()
