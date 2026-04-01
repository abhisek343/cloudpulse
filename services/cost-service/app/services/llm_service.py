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
        self.timeout_seconds = settings.llm_timeout_seconds
        self.fallback_models = settings.llm_fallback_models
        
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

    def _get_openrouter_candidate_models(self) -> list[str]:
        """Prefer the configured model first, then try concrete free-model fallbacks."""
        candidates = [self.model]
        if self.model == "openrouter/free":
            candidates.extend(self.fallback_models)

        deduped: list[str] = []
        for candidate in candidates:
            if candidate and candidate not in deduped:
                deduped.append(candidate)
        return deduped

    @staticmethod
    def _extract_openrouter_error_detail(response: httpx.Response) -> str:
        """Format a concise provider error from an OpenRouter HTTP response."""
        try:
            payload = response.json()
        except ValueError:
            payload = None

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                code = error.get("code")
                if message and code:
                    return f"{code}: {message}"
                if message:
                    return str(message)
            message = payload.get("message")
            if message:
                return str(message)

        body = response.text.strip()
        if body:
            return body[:300]
        return f"HTTP {response.status_code}"

    async def _get_openrouter_response(self, prompt: str) -> str:
        """Call OpenRouter directly to avoid LiteLLM alias handling issues."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "http://localhost:3005",
            "X-Title": "CloudPulse AI",
        }
        errors: list[str] = []

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            for model_name in self._get_openrouter_candidate_models():
                payload = {
                    "model": model_name,
                    "messages": [{"role": "user", "content": prompt}],
                }

                try:
                    response = await client.post(
                        self._get_openrouter_url(),
                        headers=headers,
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if not isinstance(content, str):
                        raise ValueError("response content was not text")
                    return content.strip()
                except httpx.TimeoutException:
                    errors.append(f"{model_name}: request timed out after {self.timeout_seconds:.0f}s")
                except httpx.HTTPStatusError as exc:
                    detail = self._extract_openrouter_error_detail(exc.response)
                    errors.append(f"{model_name}: {detail}")
                except (KeyError, IndexError, TypeError, ValueError) as exc:
                    errors.append(f"{model_name}: invalid response payload ({exc})")
                except httpx.HTTPError as exc:
                    errors.append(f"{model_name}: network error ({exc})")

        attempted_models = ", ".join(self._get_openrouter_candidate_models())
        details = "; ".join(errors) if errors else "unknown provider failure"
        raise RuntimeError(
            f"OpenRouter failed after trying free models [{attempted_models}]. {details}"
        )

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
            logger.exception("LLM call failed")
            return (
                "The configured LLM provider failed. "
                f"{e}"
            )


# Singleton instance
_llm_service: LLMService | None = None


def get_llm_service() -> LLMService:
    """Get or create the LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
