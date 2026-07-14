import os
from typing import Optional

import click
from langchain_core.language_models.chat_models import BaseChatModel

try:
    from langchain_google_genai import ChatGoogleGenerativeAI
except ImportError:
    ChatGoogleGenerativeAI = None  # type: ignore


def _get_google_api_key() -> Optional[str]:
    """Gets the Google API key from environment variables in priority order."""
    return (
        os.getenv("GOOGLE_API_KEY")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_GENERATIVE_AI_API_KEY")
    )


def _initialize_llm(model: str) -> BaseChatModel:
    """Initializes and returns the LangChain chat model based on the model name."""
    google_api_key_str = _get_google_api_key()

    try:
        allowed_models = ["gemini-flash-latest", "gemini-pro-latest"]
        if model not in allowed_models:
            raise click.ClickException(
                f"🚫 Unsupported model: {model}. "
                f"Only Google Gemini models are allowed: {', '.join(allowed_models)}"
            )

        if ChatGoogleGenerativeAI is None:
            raise click.ClickException(
                "Error: 'langchain-google-genai' is not installed. "
                "Run 'pip install commitai[test]' or "
                "'pip install langchain-google-genai'"
            )
        if not google_api_key_str:
            raise click.ClickException(
                "Error: Google API Key not found. Set GOOGLE_API_KEY, "
                "GEMINI_API_KEY, or GOOGLE_GENERATIVE_AI_API_KEY."
            )
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=google_api_key_str,
            streaming=True,
        )

    except Exception as e:
        raise click.ClickException(f"Error initializing AI model: {e}") from e
