"""
CivicLoop Open-Weight Model Wrapper
===================================
HARD CONSTRAINTS ENFORCED:
1. Use ONLY open-weight models (e.g. DeepSeek V4, Qwen 3.6 VL, BGE-M3).
2. NEVER import or call proprietary closed model APIs (OpenAI, Anthropic, Gemini).
3. All model access goes through this single client wrapper.
4. Swappable via environment variables (LLM_BASE_URL, LLM_API_KEY, LLM_AGENT_MODEL, etc.)

Provides: chat(), structured_chat(), vision_chat(), embed(), health_check()
Every call is logged to the ai_calls table for auditability.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional, Type

import httpx
from pydantic import BaseModel, ValidationError
from backend.app.core.config import settings

logger = logging.getLogger(__name__)

FORBIDDEN_ENDPOINTS = [
    "api.openai.com",
    "api.anthropic.com",
    "generativelanguage.googleapis.com",
]

# Default timeout and retry budget
DEFAULT_TIMEOUT_S = 90.0
MAX_RETRIES = 2


def _validate_open_weight_endpoint(base_url: str):
    for forbidden in FORBIDDEN_ENDPOINTS:
        if forbidden in base_url.lower():
            raise ValueError(
                f"HARD CONSTRAINT VIOLATION: Closed proprietary model endpoint '{forbidden}' "
                f"is strictly prohibited in CivicLoop. Use an open-weight host (vLLM, Ollama, etc.)."
            )


def _log_ai_call(
    model: str,
    purpose: str,
    latency_ms: float,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    total_tokens: Optional[int] = None,
    validated: bool = True,
    error: Optional[str] = None,
):
    """
    Write a row to the ai_calls table. Uses a fresh session to avoid
    polluting the caller's transaction scope.
    """
    try:
        from backend.app.core.database import SessionLocal
        from backend.app.models.ai_call import AICall

        db = SessionLocal()
        try:
            row = AICall(
                model=model,
                purpose=purpose,
                latency_ms=latency_ms,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                validated=validated,
                error=error[:500] if error else None,
            )
            db.add(row)
            db.commit()
        except Exception as exc:
            db.rollback()
            logger.warning(f"Failed to log ai_call: {exc}")
        finally:
            db.close()
    except Exception:
        pass  # Silently skip if DB is not available (e.g. during testing without DB)


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

    # ------------------------------------------------------------------
    # chat() — general completion with optional tools / function calling
    # ------------------------------------------------------------------
    async def chat(
        self,
        messages: List[Dict[str, Any]],
        model: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 2048,
        tools: Optional[List[Dict[str, Any]]] = None,
        response_format: Optional[Dict[str, str]] = None,
        purpose: str = "chat",
        timeout: float = DEFAULT_TIMEOUT_S,
    ) -> Dict[str, Any]:
        """
        General-purpose chat completion against the open-weight agent model.
        Supports native OpenAI-style tool/function-calling.
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

        last_err: Optional[Exception] = None
        for attempt in range(MAX_RETRIES + 1):
            t0 = time.monotonic()
            try:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers=self._get_headers(),
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()

                latency_ms = (time.monotonic() - t0) * 1000
                usage = data.get("usage", {})
                _log_ai_call(
                    model=target_model,
                    purpose=purpose,
                    latency_ms=latency_ms,
                    prompt_tokens=usage.get("prompt_tokens"),
                    completion_tokens=usage.get("completion_tokens"),
                    total_tokens=usage.get("total_tokens"),
                    validated=True,
                )
                return data

            except httpx.HTTPError as err:
                latency_ms = (time.monotonic() - t0) * 1000
                last_err = err
                _log_ai_call(
                    model=target_model,
                    purpose=purpose,
                    latency_ms=latency_ms,
                    validated=False,
                    error=str(err),
                )
                if attempt < MAX_RETRIES:
                    logger.warning(
                        f"chat() attempt {attempt + 1} failed ({target_model}): {err}. Retrying..."
                    )
                    continue
                logger.error(f"chat() permanently failed ({target_model}): {err}")
                raise

        raise last_err  # type: ignore[misc]

    # ------------------------------------------------------------------
    # structured_chat() — JSON-schema constrained with Pydantic validation
    #                      + one automatic repair retry
    # ------------------------------------------------------------------
    async def structured_chat(
        self,
        messages: List[Dict[str, Any]],
        response_model: Type[BaseModel],
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        purpose: str = "structured_chat",
    ) -> BaseModel:
        """
        Calls the open-weight model requesting JSON output, validates against
        the provided Pydantic response_model, and performs one automatic repair
        retry if validation fails.
        """
        # Build JSON schema instruction
        schema = response_model.model_json_schema()
        schema_instruction = (
            "You MUST respond with ONLY a valid JSON object that matches this schema. "
            "Do not include any other text, markdown fences, or explanations.\n"
            f"Schema: {json.dumps(schema)}"
        )

        augmented_messages = list(messages) + [
            {"role": "system", "content": schema_instruction},
        ]

        data = await self.chat(
            messages=augmented_messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
            purpose=purpose,
        )

        raw_content = data["choices"][0]["message"]["content"]

        # Parse and validate
        try:
            parsed = json.loads(raw_content)
            result = response_model.model_validate(parsed)
            return result
        except (json.JSONDecodeError, ValidationError) as first_err:
            logger.warning(f"structured_chat() first validation failed: {first_err}. Attempting repair...")

            # One repair retry: send original response + error back for correction
            repair_messages = augmented_messages + [
                {"role": "assistant", "content": raw_content},
                {
                    "role": "user",
                    "content": (
                        f"Your previous JSON was invalid. Error: {str(first_err)}\n"
                        "Please fix and return ONLY valid JSON matching the schema."
                    ),
                },
            ]

            repair_data = await self.chat(
                messages=repair_messages,
                model=model,
                temperature=0.05,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                purpose=f"{purpose}_repair",
            )

            repair_content = repair_data["choices"][0]["message"]["content"]

            try:
                repair_parsed = json.loads(repair_content)
                result = response_model.model_validate(repair_parsed)
                return result
            except (json.JSONDecodeError, ValidationError) as second_err:
                _log_ai_call(
                    model=model or self.agent_model,
                    purpose=f"{purpose}_repair_failed",
                    latency_ms=0,
                    validated=False,
                    error=str(second_err),
                )
                raise ValueError(
                    f"structured_chat() failed after repair retry. "
                    f"First error: {first_err}. Second error: {second_err}"
                ) from second_err

    # ------------------------------------------------------------------
    # vision_chat() — open-weight vision model for evidence / screenshot OCR
    # ------------------------------------------------------------------
    async def vision_chat(
        self,
        prompt: str,
        image_url: str,
        model: Optional[str] = None,
        temperature: float = 0.1,
        max_tokens: int = 2048,
        purpose: str = "vision",
    ) -> Dict[str, Any]:
        """
        Calls open-weight vision model (default: Qwen 3.6 VL) for
        screenshot OCR, evidence verification, and image analysis.
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

        return await self.chat(
            messages=messages,
            model=target_model,
            temperature=temperature,
            max_tokens=max_tokens,
            purpose=purpose,
        )

    # ------------------------------------------------------------------
    # embed() — embedding via open-weight model (BGE-M3 / Qwen3-Embedding)
    # ------------------------------------------------------------------
    async def embed(
        self,
        text: str,
        model: Optional[str] = None,
        purpose: str = "embedding",
    ) -> List[float]:
        """
        Generates embedding using open-weight embedding model.
        """
        target_model = model or self.embed_model
        payload = {
            "model": target_model,
            "input": text,
        }

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.base_url}/embeddings",
                    headers=self._get_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

            latency_ms = (time.monotonic() - t0) * 1000
            usage = data.get("usage", {})
            _log_ai_call(
                model=target_model,
                purpose=purpose,
                latency_ms=latency_ms,
                prompt_tokens=usage.get("prompt_tokens"),
                total_tokens=usage.get("total_tokens"),
                validated=True,
            )
            return data["data"][0]["embedding"]

        except httpx.HTTPError as err:
            latency_ms = (time.monotonic() - t0) * 1000
            _log_ai_call(
                model=target_model,
                purpose=purpose,
                latency_ms=latency_ms,
                validated=False,
                error=str(err),
            )
            logger.error(f"embed() failed ({target_model}): {err}")
            raise

    # ------------------------------------------------------------------
    # health_check() — verify open-weight endpoint reachability
    # ------------------------------------------------------------------
    async def health_check(self) -> Dict[str, Any]:
        """
        Pings the open-weight model endpoint's /models list to verify
        connectivity and reports active model configuration.
        """
        result: Dict[str, Any] = {
            "status": "unknown",
            "base_url": self.base_url,
            "agent_model": self.agent_model,
            "vision_model": self.vision_model,
            "embed_model": self.embed_model,
        }
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{self.base_url}/models",
                    headers=self._get_headers(),
                )
                if response.status_code == 200:
                    models_data = response.json()
                    available = [
                        m.get("id", "unknown")
                        for m in models_data.get("data", [])
                    ]
                    result["status"] = "healthy"
                    result["available_models"] = available
                else:
                    result["status"] = "degraded"
                    result["http_status"] = response.status_code
        except Exception as exc:
            result["status"] = "unreachable"
            result["error"] = str(exc)

        return result


# Default singleton client instance configured from environment variables
llm_client = OpenWeightLLMClient()
