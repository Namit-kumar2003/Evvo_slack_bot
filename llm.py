"""
llm.py — NL→SQL using Meta Llama 3.1 8B Instruct via HuggingFace InferenceClient.

Uses HuggingFace's free Inference Providers (routed through Sambanova).
Only your existing HF token is needed — no new accounts or keys.

Model: meta-llama/Meta-Llama-3.1-8B-Instruct
"""

import os
import re
from huggingface_hub import InferenceClient
from prompts import SYSTEM_PROMPT, HUMAN_TEMPLATE


HF_MODEL_ID = "meta-llama/Meta-Llama-3.1-8B-Instruct"


_client = None


def _get_client() -> InferenceClient:
    global _client
    if _client is None:
        hf_token = os.environ.get("HUGGINGFACE_API_TOKEN")
        if not hf_token:
            raise EnvironmentError(
                "HUGGINGFACE_API_TOKEN is not set. "
                "Get your free token at https://huggingface.co/settings/tokens"
            )
        _client = InferenceClient(
            provider="sambanova",   
            api_key=hf_token,       
        )
    return _client


def _clean_sql(raw: str) -> str:
    """Strip markdown fences and extract the first SELECT statement."""
    
    raw = re.sub(r"```(?:sql)?", "", raw, flags=re.IGNORECASE).replace("```", "")

    
    match = re.search(r"(SELECT\b.+?;)", raw, flags=re.IGNORECASE | re.DOTALL)
    if match:
        return match.group(1).strip()

    return raw.strip()


def question_to_sql(question: str) -> str:
    """
    Convert a natural language question into a SQL SELECT statement.

    Args:
        question: The user's natural language question.

    Returns:
        A clean SQL SELECT statement as a string.

    Raises:
        ValueError: If the model output does not contain a SELECT statement.
        EnvironmentError: If HUGGINGFACE_API_TOKEN is missing.
    """
    client = _get_client()

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": HUMAN_TEMPLATE.format(question=question)},
    ]

    response = client.chat.completions.create(
        model=HF_MODEL_ID,
        messages=messages,
        max_tokens=256,
        temperature=0.01,
    )

    raw_output = response.choices[0].message.content
    sql = _clean_sql(raw_output)

    if not sql.lower().startswith("select"):
        raise ValueError(
            f"Model did not return a valid SELECT statement.\nRaw output:\n{raw_output}"
        )

    return sql