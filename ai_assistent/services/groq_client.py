import logging
import requests

from greenai_hub.env import credentials

logger = logging.getLogger(__name__)

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"
DEFAULT_MODEL = "llama-3.3-70b-versatile"


class GroqClient:
    """Minimal client for the Groq chat completions API."""

    def __init__(self, model: str = DEFAULT_MODEL):
        self.api_key = credentials.get("groq_api_key", "")
        self.model = model

    def chat(self, messages: list[dict], temperature: float = 0.4, max_tokens: int = 2048) -> str:
        """Send messages to Groq and return the assistant reply text."""
        if not self.api_key:
            logger.error("Groq API key is not configured in .env.json")
            return "Error: Groq API key is not configured."

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        try:
            resp = requests.post(GROQ_API_URL, json=payload, headers=headers, timeout=60)
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
        except requests.exceptions.Timeout:
            logger.exception("Groq API timeout")
            return "Error: The AI service timed out. Please try again."
        except requests.exceptions.RequestException as exc:
            logger.exception("Groq API request failed: %s", exc)
            return f"Error: Could not reach the AI service — {exc}"
        except (KeyError, IndexError):
            logger.exception("Unexpected Groq API response format")
            return "Error: Unexpected response from the AI service."
