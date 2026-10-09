"""
CivicLoop Open-Weight Model Wrapper
===================================
HARD CONSTRAINTS ENFORCED:
1. Use ONLY open-weight models (e.g. DeepSeek V4, Qwen 3.6 VL, BGE-M3).
2. NEVER import or call proprietary closed model APIs (OpenAI, Anthropic, Gemini).
3. All model access goes through this single client wrapper.
4. Swappable via environment variables (LLM_BASE_URL, LLM_API_KEY, LLM_AGENT_MODEL, etc.)
"""

import logging
from typing import Any, Dict, List, Optional
import httpx
from pydantic import BaseModel
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

FORBIDDEN_ENDPOINTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
]


def _validate_open_weight_endpoint(base_url: str):
    for forbidden in FORBIDDEN_ENDPOINTS:
        if forbidden in base_url.lower():
            raise ValueError(
                f"HARD CONSTRAINT VIOLATION: Closed proprietary model endpoint '{forbidden}' "
                f"is strictly prohibited in CivicLoop. Use an open-weight host (vLLM, Ollama, etc.)."
            )


class OpenWeightLLMClient:
    """
    OpenAI-compatible client wrapper specifically targeting self-hosted / open-weight
    model runners (vLLM, Ollama, TGI, SGLang, or hosted open-weight providers).
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        agent_model: Optional[str] = None,
        vision_model: Optional[str] = None,
        embed_model: Optional[str] = None,
    ):
        self.base_url = (base_url or settings.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or settings.LLM_API_KEY
        self.agent_model = agent_model or settings.LLM_AGENT_MODEL
        self.vision_model = vision_model or settings.LLM_VISION_MODEL
        self.embed_model = embed_model or settings.EMBED_MODEL

        _validate_open_weight_endpoint(self.base_url)

    def _get_headers(self) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def chat_completion(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        max_tokens: int = 2048,
    ) -> Dict[str, Any]:
        """
        Calls open-weight agent model (default: DeepSeek V4) for reasoning and tool proposal.
        """
        target_model = model or self.agent_model
        payload: Dict[str, Any] = {
            "model": target_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
        if response_format:
            payload["response_format"] = response_format

        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/chat/completions",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as err:
                logger.error(f"Open-weight LLM call failed ({target_model}): {err}")
                raise

    async def analyze_vision(
        self,
        prompt: str,
        image_url: str,
        model: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Calls open-weight vision model (default: Qwen 3.6 VL) for evidence verification.
        """
        target_model = model or self.vision_model
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}},
                ],
            }
        ]

        return await self.chat_completion(
            messages=messages,
            model=target_model,
            temperature=0.1,
        )

    async def get_embedding(
        self,
        text: str,
        model: Optional[str] = None,
    ) -> List[float]:
        """
        Generates embedding using open-weight embedding model (default: BGE-M3 or Qwen3-Embedding).
        """
        target_model = model or self.embed_model
        payload = {
            "model": target_model,
            "input": text,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()
                return data["data"][0]["embedding"]
            except httpx.HTTPError as err:
                logger.error(f"Open-weight embedding call failed ({target_model}): {err}")
                raise


# Default singleton client instance configured from environment variables
llm_client = OpenWeightLLMClient()
