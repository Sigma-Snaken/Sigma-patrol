import google.generativeai as genai
from config import SETTINGS_FILE, DEFAULT_SETTINGS
from utils import load_json
from logger import get_logger
from pydantic import BaseModel, Field
import json

logger = get_logger("ai_service", "ai_service.log")

class InspectionResult(BaseModel):
    is_NG: bool = Field(description="True if the inspection result is NG (Not Good) or abnormal, False otherwise.")
    Description: str = Field(description="Description of the issue if NG, or an empty string if OK.")

class AIService:
    def __init__(self):
        self.model = None
        self.api_key = None
        self.model_name = "gemini-1.5-flash" # Default fallback
        # Initial config attempt
        self._configure()

    def _configure(self):
        settings = load_json(SETTINGS_FILE, DEFAULT_SETTINGS)
        new_api_key = settings.get("gemini_api_key")
        new_model_name = settings.get("gemini_model", "gemini-2.5-flash")

        # Re-configure only if necessary or if not yet configured
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
        self._configure()
        return self.model_name

    def is_configured(self):
        self._configure()
        return self.model is not None

    def generate_inspection(self, image, user_prompt, system_prompt=None):
        """
        Generates content based on an image and prompts.
        image: PIL Image object
        Returns: dict {is_NG: bool, Description: str}
        """
        self._configure()
        
        if not self.model:
            logger.error("Attempted inspection without configured model.")
            raise Exception("AI Model not configured. Please check your API Key in settings.")

        final_parts = []
        if system_prompt:
            final_parts.append(system_prompt)
        final_parts.append(user_prompt)
        final_parts.append(image)

        generation_config = genai.GenerationConfig(
            response_mime_type="application/json",
            response_schema=InspectionResult
        )

        try:
            logger.info(f"Sending inspection request to Gemini (Model: {self.model_name})")
            response = self.model.generate_content(
                final_parts,
                generation_config=generation_config
            )
            logger.info("Inspection response received.")
            
            # Log Token Usage
            usage_data = {}
            try:
                usage = response.usage_metadata
                usage_data = {
                    "prompt_token_count": usage.prompt_token_count,
                    "candidates_token_count": usage.candidates_token_count,
                    "total_token_count": usage.total_token_count
                }
                logger.info(f"Token Usage: {usage_data}")
            except Exception as e:
                logger.warning(f"Could not log token usage: {e}")

            return {
                "result": json.loads(response.text),
                "usage": usage_data
            }
        except Exception as e:
            logger.error(f"Gemini Generation Error: {e}")
            raise Exception(f"Gemini Generation Error: {e}")

    def generate_report(self, report_prompt):
        """
        Generates a text report.
        """
        self._configure()
        
        if not self.model:
            logger.error("Attempted report generation without configured model.")
            raise Exception("AI Model not configured.")

        try:
            logger.info(f"Sending report generation request to Gemini (Model: {self.model_name})")
            if not report_prompt:
                 report_prompt = "Generate a summary report of the patrol." # Default fallback
            
            response = self.model.generate_content(report_prompt)
            logger.info("Report response received.")
            
            # Log Token Usage
            usage_data = {}
            try:
                usage = response.usage_metadata
                usage_data = {
                    "prompt_token_count": usage.prompt_token_count,
                    "candidates_token_count": usage.candidates_token_count,
                    "total_token_count": usage.total_token_count
                }
                logger.info(f"Report Token Usage: {usage_data}")
            except Exception as e:
                logger.warning(f"Could not log report token usage: {e}")
                
            return {
                "result": response.text,
                "usage": usage_data
            }
        except Exception as e:
            logger.error(f"Gemini Report Error: {e}")
            raise Exception(f"Gemini Report Error: {e}")

ai_service = AIService()
