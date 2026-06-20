"""
rag/llm_caller.py
-----------------
Job: send the assembled messages to Groq and return the report as a string.

One function. No chains, no complexity.
LangChain comes in Week 3 when we need multi-step pipelines.
"""

import os
from groq import Groq
from dotenv import load_dotenv

# Load GROQ_API_KEY from .env file at project root
from pathlib import Path
load_dotenv(dotenv_path=Path(__file__).parent.parent / ".env", override=True)

# Groq client — initialized once at module level
_client = Groq(api_key=os.environ.get("GROQ_API_KEY"))

# Model choice: llama-3.1-8b-instant
# Fast, free, 131k context window — more than enough for 10 chunks (~2k tokens)
# Swap to "llama-3.3-70b-versatile" here if you want higher quality later
MODEL = "llama-3.1-8b-instant"


def generate_report(messages: list[dict]) -> str:
    """
    Sends messages to Groq and returns the LLM response as a plain string.

    Args:
        messages: list of {"role": ..., "content": ...} dicts
                  built by prompt_builder.build_messages()

    Returns:
        The LLM's response text as a string.

    Raises:
        Exception if the API call fails (network error, invalid key, etc.)
    """
    response = _client.chat.completions.create(
        model=MODEL,
        messages=messages,
        temperature=0.2,        # low = consistent, factual, not creative
        max_completion_tokens=1000,  # enough for a structured 4-section report
    )

    return response.choices[0].message.content