"""
LLM client for GPT-5 via OpenAI.

This project uses GPT-5 exclusively for all LLM operations.
No other models or providers are supported.

Environment:
    OPENAI_API_KEY must be set

Usage:
    from src.llm.client import LLMClient

    client = LLMClient()
    response = client.chat([
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Hello!"}
    ])
"""

import os
import logging
from typing import List, Dict

from openai import OpenAI


logger = logging.getLogger(__name__)


class LLMClient:
    """
    GPT-5 client via OpenAI API.

    This is intentionally simple with no provider switching or model selection.
    The entire system is built around GPT-5.
    """

    def __init__(self, model: str = "gpt-4o-mini"):
        """
        Initialize GPT client.

        Args:
            model: OpenAI model name (default: "gpt-5-mini")

        Raises:
            ValueError: If OPENAI_API_KEY not set
        """
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY environment variable not set. "
                "Get your key from: https://platform.openai.com/api-keys"
            )

        self.client = OpenAI(api_key=api_key)
        self.model = model

        logger.info(f"LLM client initialized: {self.model}")

    def chat(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 1500,
    ) -> str:
        """
        Send chat completion request to GPT.

        Args:
            messages: List of message dicts with "role" and "content"
                     Role must be "system", "user", or "assistant"
            temperature: Sampling temperature (0.0-2.0, lower = more focused)
                        Note: GPT-5 models only support temperature=1
            max_tokens: Maximum tokens in response

        Returns:
            Response text from GPT

        Raises:
            Exception: If API call fails
        """
        try:
            # GPT-5 models use max_completion_tokens instead of max_tokens
            # and only support temperature=1 (default)
            if self.model.startswith("gpt-5"):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    # GPT-5 only supports default temperature of 1
                    max_completion_tokens=max_tokens,
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )

            # Debug: check response structure
            choice = response.choices[0]
            message = choice.message
            logger.info(f"Finish reason: {choice.finish_reason}")
            logger.info(f"Response message content type: {type(message.content)}")
            logger.info(f"Response message content value: |{message.content}|")
            logger.info(f"Response message refusal: {getattr(message, 'refusal', None)}")

            # Handle refusal (GPT-5 feature)
            if hasattr(message, 'refusal') and message.refusal:
                logger.warning(f"GPT refused to respond: {message.refusal}")
                return ""

            content = message.content
            if content is None:
                logger.warning("GPT returned None content")
                return ""

            return content.strip()

        except Exception as e:
            logger.error(f"GPT API call failed: {e}")
            raise

    def chat_stream(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.4,
        max_tokens: int = 800,
    ):
        """
        Stream a chat completion response token-by-token.

        Yields chunks of text as they arrive from OpenAI.

        Args:
            messages: List of message dicts with "role" and "content"
            temperature: Sampling temperature (Note: GPT-5 only supports temperature=1)
            max_tokens: Maximum tokens in response

        Yields:
            String chunks as they arrive

        Raises:
            Exception: If API call fails
        """
        try:
            # GPT-5 models use max_completion_tokens and don't support custom temperature
            if self.model.startswith("gpt-5"):
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_completion_tokens=max_tokens,
                    stream=True,
                )
            else:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=True,
                )

            for chunk in response:
                delta = chunk.choices[0].delta
                if delta and delta.content:
                    yield delta.content

        except Exception as e:
            logger.error(f"GPT streaming call failed: {e}")
            raise
