import json
import os
import re
from typing import Any

SYSTEM_PROMPT = """
You are an internal document assistant.

Rules (non-negotiable):
- Answer ONLY using the provided context.
- Do NOT use external knowledge or assumptions.
- Respond with a concise paragraph (1–3 sentences).
- Do NOT include citations, filenames, page numbers, or placeholder text in the answer.

For definition questions (e.g., “What are …”):
- ONLY list the defined items.
- Do NOT describe mechanisms, processes, implications, or comparisons.
- Do NOT add interpretation, commentary, or framing language.

Citation rules (strict):
- Do NOT include author names, years, or academic-style references.
- Even if the document contains citations (e.g., “Urde, 2009”), NEVER surface them.

Important:
- You are ONLY called when the answer is explicitly present in the documents.
- NEVER refuse, hedge, or say information is missing.
- NEVER explain beyond what is directly stated.
"""

DEFAULT_MODEL = "meta-llama/Meta-Llama-3-8B-Instruct-Lite"


def get_chat_model() -> str:
    return os.environ.get("P1_TOGETHER_CHAT_MODEL", DEFAULT_MODEL)


def _build_client():
    # Lazy import so CI and API startup do NOT require Together SDK
    from together import Together

    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set")

    return Together(api_key=api_key)


def _chat_completion(*, messages: list[dict[str, str]], temperature: float = 0) -> str:
    client = _build_client()
    response = client.chat.completions.create(
        model=get_chat_model(),
        messages=messages,
        temperature=temperature,
    )
    return response.choices[0].message.content or ""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return stripped


def _extract_json_object(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start:end + 1]
    return text


def _clean_answer_text(text: str) -> str:
    cleaned = re.sub(r"\s*\(\s*source\s*,\s*page\s*\)", "", text, flags=re.I)
    return cleaned.strip()


def generate_structured_output(
    *,
    system_prompt: str,
    user_prompt: str,
) -> dict[str, Any]:
    raw = _chat_completion(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0,
    )
    cleaned = _strip_json_fence(raw)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        extracted = _extract_json_object(cleaned)
        try:
            payload = json.loads(extracted)
        except json.JSONDecodeError:
            raise ValueError(f"Model did not return valid JSON: {cleaned[:200]}") from exc

    if not isinstance(payload, dict):
        raise ValueError("Structured output must be a JSON object")

    return payload


def generate_answer(query: str, contexts: list[dict]) -> str:
    context_text = "\n\n".join(
        f"[Source: {c['source']} p.{c['page']}]\n{c['content']}"
        for c in contexts
    )

    answer = _chat_completion(
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    f"Question:\n{query}\n\n"
                    f"Context:\n{context_text}"
                ),
            },
        ],
        temperature=0,
    )
    return _clean_answer_text(answer)
