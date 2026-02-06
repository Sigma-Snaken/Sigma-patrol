"""
AI Service - VLM integration for inspection analysis.
Supports Google Gemini and NVIDIA VILA as providers.
"""

import base64
import io
import json
import re
import time

import requests
from PIL import Image as PILImage
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

import settings_service
from logger import get_logger

logger = get_logger("ai_service", "ai_service.log")


class InspectionResult(BaseModel):
    """Structured schema for inspection results."""
    is_NG: bool = Field(description="True if abnormal/NG, False if normal/OK")
    Description: str = Field(description="Issue description if NG, empty if OK")


def _extract_json_from_text(text):
    """Extract a JSON object from text that may contain markdown fences or surrounding text."""
    if not text or not text.strip():
        return None

    text = text.strip()

    # 1. Direct parse
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        pass

    # 2. Extract from ```json ... ``` fence
    m = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except (json.JSONDecodeError, ValueError):
            pass

    # 3. Find first { ... } in text
    m = re.search(r'\{[^{}]*\}', text)
    if m:
        try:
            return json.loads(m.group(0))
        except (json.JSONDecodeError, ValueError):
            pass

    return None


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
            - input_tokens: int
            - output_tokens: int
            - total_tokens: int
            - usage_json: str (JSON string of usage data)
    """
    result = {
        'result_text': '',
        'is_ng': False,
        'description': '',
        'input_tokens': 0,
        'output_tokens': 0,
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
        result['input_tokens'] = usage_data.get("prompt_token_count", 0)
        result['output_tokens'] = usage_data.get("candidates_token_count", 0)
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


# ---------------------------------------------------------------------------
# Gemini Provider
# ---------------------------------------------------------------------------
class _GeminiProvider:
    """Google Gemini VLM provider."""

    def __init__(self):
        self.client = None
        self.api_key = None
        self.model_name = "gemini-2.0-flash"

    def configure(self, settings):
        new_api_key = settings.get("gemini_api_key")
        new_model_name = settings.get("gemini_model", "gemini-2.0-flash")

        if new_api_key != self.api_key or new_model_name != self.model_name or self.client is None:
            logger.info(f"Configuring Gemini with model: {new_model_name}")
            self.api_key = new_api_key
            self.model_name = new_model_name

            if self.api_key:
                try:
                    self.client = genai.Client(api_key=self.api_key)
                    logger.info("Gemini configured successfully.")
                except Exception as e:
                    logger.error(f"Gemini Configuration Error: {e}")
                    self.client = None
            else:
                logger.warning("Gemini configured without API Key.")
                self.client = None

    def get_model_name(self):
        return self.model_name

    def is_configured(self):
        return self.client is not None

    def _extract_usage(self, response):
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
        if not self.client:
            raise Exception("AI Model not configured. Check API Key in settings.")

        contents = []
        if system_prompt:
            contents.append(system_prompt)
        contents.append(user_prompt)
        contents.append(image)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=InspectionResult
        )

        try:
            logger.info(f"Gemini inspection request to {self.model_name}")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=contents,
                config=config
            )
            usage_data = self._extract_usage(response)
            logger.info(f"Token Usage: {usage_data}")
            result_data = json.loads(response.text) if response.text else {}
            return {"result": result_data, "usage": usage_data}
        except Exception as e:
            logger.error(f"Gemini Generation Error: {e}")
            raise

    def generate_report(self, report_prompt):
        if not self.client:
            raise Exception("AI Model not configured.")

        try:
            logger.info(f"Gemini report request to {self.model_name}")
            prompt = report_prompt or "Generate a summary report of the patrol."
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=prompt
            )
            usage_data = self._extract_usage(response)
            logger.info(f"Report Token Usage: {usage_data}")
            return {"result": response.text, "usage": usage_data}
        except Exception as e:
            logger.error(f"Gemini Report Error: {e}")
            raise

    def analyze_video(self, video_path, user_prompt):
        if not self.client:
            raise Exception("AI Model not configured.")

        try:
            logger.info(f"Uploading video {video_path}...")
            video_file = self.client.files.upload(file=video_path)

            while video_file.state.name == "PROCESSING":
                time.sleep(2)
                video_file = self.client.files.get(name=video_file.name)

            if video_file.state.name == "FAILED":
                raise Exception("Video processing failed.")

            logger.info(f"Video ready. Analyzing with prompt: {user_prompt}")
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[video_file, user_prompt]
            )
            usage_data = self._extract_usage(response)
            return {"result": response.text, "usage": usage_data}
        except Exception as e:
            logger.error(f"Video Analysis Error: {e}")
            raise


# ---------------------------------------------------------------------------
# VILA Provider
# ---------------------------------------------------------------------------
_ZERO_USAGE = {"prompt_token_count": 0, "candidates_token_count": 0, "total_token_count": 0}


class _VilaProvider:
    """NVIDIA VILA VLM provider (via HTTP microservice)."""

    def __init__(self):
        self.server_url = "http://localhost:9000"
        self.model_name = "VILA1.5-3B"
        self.alert_url = ""

    def configure(self, settings):
        url = (settings.get("vila_server_url") or "http://localhost:9000").strip().rstrip("/")
        if url and not url.startswith(("http://", "https://")):
            url = f"http://{url}"
        self.server_url = url
        self.model_name = settings.get("vila_model") or "VILA1.5-3B"

        alert_url = (settings.get("vila_alert_url") or "").strip().rstrip("/")
        if alert_url and not alert_url.startswith(("http://", "https://")):
            alert_url = f"http://{alert_url}"
        self.alert_url = alert_url

    def get_model_name(self):
        return self.model_name

    def is_configured(self):
        return bool(self.server_url)

    def _call_alert(self, image_b64_list, user_prompts, system_prompt="", max_tokens=128):
        """GET to VILA alert/completions endpoint."""
        url = f"{self.alert_url}/v1/alert/completions"
        body = {
            "system_prompt": system_prompt,
            "images": image_b64_list,
            "user_prompts": user_prompts,
            "max_tokens": max_tokens,
            "min_tokens": 1,
        }
        logger.info(f"VILA alert request to {url} (max_tokens={max_tokens})")
        resp = requests.get(url, json=body, timeout=120)
        resp.raise_for_status()
        data = resp.json()
        return data["alert_response"]  # list of strings

    def _call_chat(self, messages, max_tokens=512):
        """POST to VILA microservice /v1/chat/completions."""
        url = f"{self.server_url}/v1/chat/completions"
        body = {
            "messages": messages,
            "max_tokens": max_tokens,
        }

        logger.info(f"VILA request to {url} (max_tokens={max_tokens})")
        resp = requests.post(url, json=body, timeout=120)
        resp.raise_for_status()

        data = resp.json()
        content = data["choices"][0]["message"]["content"]

        # content is a plain string from the microservice
        if isinstance(content, list):
            # handle [{"type":"text","text":"..."}] just in case
            content = " ".join(
                item.get("text", "") if isinstance(item, dict) else str(item)
                for item in content
            )

        return content

    def generate_inspection(self, image, user_prompt, system_prompt=None):
        # PIL Image → base64 JPEG
        buf = io.BytesIO()
        image.save(buf, format="JPEG")
        b64 = base64.b64encode(buf.getvalue()).decode()
        data_url = f"data:image/jpeg;base64,{b64}"

        if self.alert_url:
            # Alert API — optimized for yes/no answers
            alert_system = (
                "You are a building safety inspector. "
                "Evaluate the image based on the question. "
                "Your response MUST be 'yes' if there is a problem/abnormality, or 'no' if everything is normal."
            )
            try:
                responses = self._call_alert(
                    [data_url],
                    [user_prompt],
                    system_prompt=alert_system,
                    max_tokens=64,
                )
                answer = responses[0].strip().lower() if responses else ""
                logger.info(f"VILA alert raw: {answer}")
                # Handle both English and Chinese yes/no
                _YES = ("yes", "是", "有", "異常", "异常")
                _NO = ("no", "不", "没", "沒", "否", "正常")
                if any(answer.startswith(w) for w in _YES):
                    is_ng = True
                elif any(answer.startswith(w) for w in _NO):
                    is_ng = False
                else:
                    # Fallback keyword heuristic
                    is_ng = any(kw in answer for kw in [
                        "yes", "abnormal", "problem", "issue", "hazard",
                        "是", "異常", "问题", "問題", "危險",
                    ])
                description = f"{user_prompt} → {responses[0].strip()}" if responses else "No response"
                return {
                    "result": {"is_NG": is_ng, "Description": description},
                    "usage": _ZERO_USAGE,
                }
            except Exception as e:
                logger.error(f"VILA Alert Error: {e}")
                raise

        # Fallback: Chat API
        prompt = (
            f"Question: {user_prompt}\n"
            "Look at the image and answer the question. "
            "First say YES or NO, then describe what you see in one sentence."
        )

        messages = [{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": data_url}},
                {"type": "text", "text": prompt},
            ]
        }]

        try:
            text = self._call_chat(messages, max_tokens=256)
            logger.info(f"VILA inspection raw: {text[:300]}")

            # Try to extract JSON if model happens to return it
            parsed = _extract_json_from_text(text)
            if parsed and "is_NG" in parsed:
                return {"result": parsed, "usage": _ZERO_USAGE}

            # Keyword heuristic on the free-text response
            text_lower = text.lower()
            is_ng = any(kw in text_lower for kw in [
                "yes", "abnormal", "hazard", "issue", "damage", "risk", "problem", "ng",
                "異常", "問題", "危險", "損壞",
            ])
            return {
                "result": {"is_NG": is_ng, "Description": text.strip()},
                "usage": _ZERO_USAGE,
            }
        except Exception as e:
            logger.error(f"VILA Inspection Error: {e}")
            raise

    def generate_report(self, report_prompt):
        prompt = report_prompt or "Generate a summary report of the patrol."
        messages = [{"role": "user", "content": prompt}]

        try:
            text = self._call_chat(messages, max_tokens=512)
            return {"result": text, "usage": _ZERO_USAGE}
        except Exception as e:
            logger.error(f"VILA Report Error: {e}")
            raise

    def analyze_video(self, video_path, user_prompt):
        try:
            with open(video_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            data_url = f"data:video/mp4;base64,{b64}"
            logger.warning(f"VILA video base64 size: {len(b64)} chars")

            messages = [{
                "role": "user",
                "content": [
                    {"type": "video_url", "video_url": {"url": data_url}},
                    {"type": "text", "text": user_prompt},
                ]
            }]

            text = self._call_chat(messages, max_tokens=512)
            return {"result": text, "usage": _ZERO_USAGE}
        except Exception as e:
            logger.error(f"VILA Video Error: {e}")
            raise


# ---------------------------------------------------------------------------
# AIService Facade
# ---------------------------------------------------------------------------
class AIService:
    """VLM service facade — delegates to the active provider (Gemini or VILA)."""

    def __init__(self):
        self._gemini = _GeminiProvider()
        self._vila = _VilaProvider()
        self._active_provider_name = "gemini"
        self._configure()

    def _configure(self):
        settings = settings_service.get_all()
        self._active_provider_name = settings.get("vlm_provider", "gemini")
        self._gemini.configure(settings)
        self._vila.configure(settings)

    @property
    def _provider(self):
        providers = {"gemini": self._gemini, "vila": self._vila}
        return providers.get(self._active_provider_name, self._gemini)

    def get_model_name(self):
        self._configure()
        return self._provider.get_model_name()

    def is_configured(self):
        self._configure()
        return self._provider.is_configured()

    def generate_inspection(self, image, user_prompt, system_prompt=None):
        self._configure()
        return self._provider.generate_inspection(image, user_prompt, system_prompt)

    def generate_report(self, report_prompt):
        self._configure()
        return self._provider.generate_report(report_prompt)

    def analyze_video(self, video_path, user_prompt):
        self._configure()
        return self._provider.analyze_video(video_path, user_prompt)


ai_service = AIService()
