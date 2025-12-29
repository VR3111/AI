import os

SYSTEM_PROMPT = """
You are an internal document assistant.

Rules (non-negotiable):
- Answer ONLY using the provided context.
- Do NOT use external knowledge or assumptions.
- Respond with a concise paragraph (1–3 sentences).
- Cite sources ONLY at the end using this exact format: (source, page).

For definition questions (e.g., “What are …”):
- ONLY list the defined items.
- Do NOT describe mechanisms, processes, implications, or comparisons.
- Do NOT add interpretation, commentary, or framing language.

Citation rules (strict):
- Do NOT include author names, years, or academic-style references.
- Even if the document contains citations (e.g., “Urde, 2009”), NEVER surface them.
- Use ONLY document filename and page number.

Important:
- You are ONLY called when the answer is explicitly present in the documents.
- NEVER refuse, hedge, or say information is missing.
- NEVER explain beyond what is directly stated.
"""


def generate_answer(query: str, contexts: list[dict]) -> str:
    # Lazy import so CI and API startup do NOT require Together SDK
    from together import Together

    api_key = os.environ.get("TOGETHER_API_KEY")
    if not api_key:
        raise RuntimeError("TOGETHER_API_KEY is not set")

    client = Together(api_key=api_key)

    context_text = "\n\n".join(
        f"[Source: {c['source']} p.{c['page']}]\n{c['content']}"
        for c in contexts
    )

    response = client.chat.completions.create(
        model="meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
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

    return response.choices[0].message.content
