"""LLM gateway with Gemini primary and OpenRouter fallback.

Manages LLM API calls with retry logic, fallback chain, and performance tracking.
"""

import base64
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import google.generativeai as genai
from openai import OpenAI

# =============================================================================
# CONFIGURATION
# =============================================================================

@dataclass
class GeminiConfig:
    """Configuration for Gemini 2.0 Flash via Vertex AI.

    Attributes:
        model: Gemini model name
        project_id: GCP project ID (optional, uses default if None)
        region: GCP region for Vertex AI
        max_retries: Maximum retry attempts on failure
        timeout: Request timeout in seconds
    """
    model: str = "gemini-2.0-flash"
    project_id: str | None = None
    region: str = "us-central1"
    max_retries: int = 2
    timeout: int = 30


@dataclass
class OpenRouterConfig:
    """Configuration for OpenRouter fallback.

    Attributes:
        api_key: OpenRouter API key
        model: Model to use (default: Claude 3.5 Sonnet)
        max_retries: Maximum retry attempts on failure
        timeout: Request timeout in seconds
    """
    api_key: str
    model: str = "anthropic/claude-3.5-sonnet"
    max_retries: int = 2
    timeout: int = 30


@dataclass
class LLMResponse:
    """Response from LLM API call.

    Attributes:
        success: Whether the call succeeded
        content: Extracted text response
        provider: Which provider was used
        latency_ms: Request latency in milliseconds
        tokens_used: Token count (if available)
        error_message: Error details if failed
    """
    success: bool
    content: str | None
    provider: Literal["gemini", "openrouter"]
    latency_ms: int
    tokens_used: int | None = None
    error_message: str | None = None


# =============================================================================
# IMAGE ENCODING
# =============================================================================

def encode_image_base64(image_path: Path) -> str:
    """Encode image file to base64 string.

    Args:
        image_path: Path to image file

    Returns:
        Base64-encoded string of image bytes

    Example:
        >>> img_b64 = encode_image_base64(Path("invoice.png"))
        >>> # Use in API calls requiring base64 images
    """
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


# =============================================================================
# GEMINI CALLS
# =============================================================================

def call_gemini(
    prompt: str,
    image_paths: list[Path],
    config: GeminiConfig
) -> LLMResponse:
    """Call Gemini 2.0 Flash with image(s) and extraction prompt.

    Args:
        prompt: Extraction prompt with schema
        image_paths: List of image file paths (PNG/JPEG)
        config: Gemini configuration

    Returns:
        LLMResponse with extraction result or error

    Retry Logic:
        - Retries up to config.max_retries times
        - Exponential backoff: 1s, 2s, 4s
        - Fails over to OpenRouter after retries exhausted
    """
    start_time = time.time()

    # Configure Gemini API
    if config.project_id:
        # Use Vertex AI
        genai.configure(api_key=None)  # Will use ADC
    else:
        # Use API key (for local development)
        # Requires GOOGLE_API_KEY environment variable
        pass

    retry_count = 0
    last_error = None

    while retry_count <= config.max_retries:
        try:
            # Load model
            model = genai.GenerativeModel(config.model)

            # Prepare content parts
            content_parts = []

            # Add images
            for img_path in image_paths:
                with open(img_path, "rb") as img_file:
                    img_data = img_file.read()
                    content_parts.append({
                        "mime_type": "image/png",
                        "data": img_data
                    })

            # Add text prompt
            content_parts.append(prompt)

            # Generate content
            response = model.generate_content(
                content_parts,
                generation_config={
                    "temperature": 0.1,
                    "max_output_tokens": 4096,
                }
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract text
            if response.text:
                return LLMResponse(
                    success=True,
                    content=response.text,
                    provider="gemini",
                    latency_ms=latency_ms,
                    tokens_used=None  # Gemini doesn't return token count easily
                )
            else:
                raise ValueError("Empty response from Gemini")

        except Exception as e:
            last_error = str(e)
            retry_count += 1

            if retry_count <= config.max_retries:
                # Exponential backoff
                wait_time = 2 ** (retry_count - 1)
                time.sleep(wait_time)
            else:
                # All retries exhausted
                latency_ms = int((time.time() - start_time) * 1000)
                return LLMResponse(
                    success=False,
                    content=None,
                    provider="gemini",
                    latency_ms=latency_ms,
                    error_message=f"Gemini failed after {config.max_retries} retries: {last_error}"
                )

    # Should never reach here
    latency_ms = int((time.time() - start_time) * 1000)
    return LLMResponse(
        success=False,
        content=None,
        provider="gemini",
        latency_ms=latency_ms,
        error_message="Unexpected error in call_gemini"
    )


# =============================================================================
# OPENROUTER CALLS
# =============================================================================

def call_openrouter(
    prompt: str,
    image_paths: list[Path],
    config: OpenRouterConfig
) -> LLMResponse:
    """Call OpenRouter (Claude 3.5 Sonnet) as fallback.

    Args:
        prompt: Extraction prompt with schema
        image_paths: List of image file paths
        config: OpenRouter configuration

    Returns:
        LLMResponse with extraction result or error

    Note:
        Uses OpenAI-compatible API via OpenRouter.
        Images are base64-encoded per Claude vision API requirements.
    """
    start_time = time.time()

    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=config.api_key
    )

    retry_count = 0
    last_error = None

    while retry_count <= config.max_retries:
        try:
            # Build messages with vision
            content_parts = []

            # Add images
            for img_path in image_paths:
                img_b64 = encode_image_base64(img_path)
                content_parts.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:image/png;base64,{img_b64}"
                    }
                })

            # Add text prompt
            content_parts.append({
                "type": "text",
                "text": prompt
            })

            # Call API
            response = client.chat.completions.create(
                model=config.model,
                messages=[{
                    "role": "user",
                    "content": content_parts
                }],
                temperature=0.1,
                max_tokens=4096,
                timeout=config.timeout
            )

            # Calculate latency
            latency_ms = int((time.time() - start_time) * 1000)

            # Extract response
            if response.choices and response.choices[0].message.content:
                return LLMResponse(
                    success=True,
                    content=response.choices[0].message.content,
                    provider="openrouter",
                    latency_ms=latency_ms,
                    tokens_used=response.usage.total_tokens if response.usage else None
                )
            else:
                raise ValueError("Empty response from OpenRouter")

        except Exception as e:
            last_error = str(e)
            retry_count += 1

            if retry_count <= config.max_retries:
                # Exponential backoff
                wait_time = 2 ** (retry_count - 1)
                time.sleep(wait_time)
            else:
                # All retries exhausted
                latency_ms = int((time.time() - start_time) * 1000)
                return LLMResponse(
                    success=False,
                    content=None,
                    provider="openrouter",
                    latency_ms=latency_ms,
                    error_message=f"OpenRouter failed after {config.max_retries} retries: {last_error}"
                )

    # Should never reach here
    latency_ms = int((time.time() - start_time) * 1000)
    return LLMResponse(
        success=False,
        content=None,
        provider="openrouter",
        latency_ms=latency_ms,
        error_message="Unexpected error in call_openrouter"
    )


# =============================================================================
# FALLBACK ORCHESTRATION
# =============================================================================

def extract_with_fallback(
    prompt: str,
    image_paths: list[Path],
    gemini_config: GeminiConfig,
    openrouter_config: OpenRouterConfig
) -> LLMResponse:
    """Try Gemini first, fallback to OpenRouter on failure.

    Args:
        prompt: Extraction prompt with JSON schema
        image_paths: List of processed image paths
        gemini_config: Gemini configuration
        openrouter_config: OpenRouter configuration

    Returns:
        LLMResponse from first successful provider

    Fallback Chain:
        1. Try Gemini 2.0 Flash (with retries)
        2. If Gemini fails: Try OpenRouter Claude 3.5 Sonnet (with retries)
        3. If both fail: Return last error

    Example:
        >>> gemini_cfg = GeminiConfig(project_id="my-project")
        >>> openrouter_cfg = OpenRouterConfig(api_key="sk-...")
        >>> response = extract_with_fallback(
        ...     prompt="Extract invoice data...",
        ...     image_paths=[Path("invoice.png")],
        ...     gemini_config=gemini_cfg,
        ...     openrouter_config=openrouter_cfg
        ... )
        >>> if response.success:
        ...     print(f"Extracted via {response.provider}")
    """
    # Try Gemini first
    gemini_response = call_gemini(prompt, image_paths, gemini_config)

    if gemini_response.success:
        return gemini_response

    # Gemini failed, try OpenRouter
    print(f"Gemini failed: {gemini_response.error_message}")
    print("Falling back to OpenRouter...")

    openrouter_response = call_openrouter(prompt, image_paths, openrouter_config)

    if openrouter_response.success:
        return openrouter_response

    # Both failed
    print(f"OpenRouter also failed: {openrouter_response.error_message}")
    return openrouter_response  # Return last error
