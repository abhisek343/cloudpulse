"""
CloudPulse AI - Cost Service
LLM Service for cost analysis and chat.
"""
import json
import logging
from typing import Any

import httpx
from litellm import completion
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class LLMService:
    """
    Service for interacting with LLM providers via litellm.
    Supports OpenAI, Anthropic, Gemini, OpenRouter, etc.
    """
    
    def __init__(self) -> None:
        self.provider = settings.llm_provider
        self.model = settings.llm_model
        self.api_key = settings.llm_api_key
        self.base_url = settings.llm_base_url
        
    def _get_model_name(self) -> str:
        """Get the full model name for litellm (e.g., 'gpt-3.5-turbo' or 'gemini/gemini-pro')."""
        # Some providers need a prefix in litellm if not already present
        if self.provider == "gemini" and not self.model.startswith("gemini"):
            return f"gemini/{self.model}"
        elif self.provider == "anthropic" and not self.model.startswith("claude"):
             return f"anthropic/{self.model}"
        elif self.provider == "openrouter" and self.model == "free":
            return "openrouter/free"
        return self.model

    def _get_openrouter_url(self) -> str:
        """Build the OpenRouter chat completions endpoint URL."""
        base_url = (self.base_url or "https://openrouter.ai/api/v1").rstrip("/")
        return f"{base_url}/chat/completions"

    async def _get_openrouter_response(self, prompt: str) -> str:
        """Call OpenRouter directly to avoid LiteLLM alias handling issues."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3005",
            "X-Title": "CloudPulse AI",
        }
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                self._get_openrouter_url(),
                headers=headers,
                json=payload,
            )
            response.raise_for_status()

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("OpenRouter returned an unexpected response payload") from exc

        if not isinstance(content, str):
            raise ValueError("OpenRouter response content was not text")

        return content.strip()

    def generate_cost_summary_prompt(self, data: dict[str, Any], user_query: str) -> str:
        """
        Convert cost data into a natural language prompt.
        """
        # Create a concise summary of the data context
        context_str = json.dumps(data, indent=2)
        
        prompt = f"""
You are CloudPulse AI, an expert FinOps analyst. 
Analyze the following cloud cost data and answer the user's question.

Context Data:
{context_str}

User Question: "{user_query}"

Instructions:
1. Be concise but insightful.
2. If costs are high, identify the service/resource driving it.
3. Suggest 1 actionable optimization if applicable.
4. Do not mention "JSON" or "data provided". Speak naturally.
5. If the data doesn't contain the answer, say "I don't have enough data to answer that."

Answer:
"""
        return prompt

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def get_chat_response(
        self,
        message: str,
        context_data: dict[str, Any] | None = None,
    ) -> str:
        """
        Get a response from the LLM.
        """
        if not self.api_key:
            return "LLM integration is not configured. Please set LLM_API_KEY environment variable."
            
        try:
            prompt = self.generate_cost_summary_prompt(context_data or {}, message)

            if self.provider == "openrouter":
                return await self._get_openrouter_response(prompt)

            # Prepare kwargs for litellm
            kwargs = {
                "model": self._get_model_name(),
                "messages": [{"role": "user", "content": prompt}],
                "api_key": self.api_key,
            }

            if self.base_url:
                kwargs["base_url"] = self.base_url

            # litellm handles the underlying API calls for us
            response = completion(**kwargs)

            content = response.choices[0].message.content
            return content.strip()
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return (
                "I apologize, but I'm having trouble connecting to the AI brain "
                "right now. Please check the logs or API configuration."
            )


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
