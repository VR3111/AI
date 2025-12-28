# Internal Document Assistant

A document-faithful internal Q&A system designed to **never hallucinate**, **never infer**, and **never leak document content**.  
The system answers questions strictly based on explicit statements found in uploaded documents.

---

## Response Modes

The API operates in **three deterministic response modes**.

---

## 1. Direct Answer

Returned **only when the document explicitly states the answer**.

### Used when:
- The question is definition-style (e.g., “What are …”)
- The answer appears verbatim in the document

### Behavior:
- Lists facts only
- No explanation, interpretation, or mechanism
- No inference or synthesis
- Citations are always included

### Example:
```json
{
  "mode": "direct_answer",
  "answer": "Volvo's core values are quality, safety, and environmental care.",
  "citations": [
    { "source": "docs/volvo.pdf", "page": 18 }
  ]
}
```

---

## 2. Guided Fallback

Used when the **topic exists in the documents**, but **no explicit answer is stated**.

### Used when:
- The question asks *how*, *why*, or *in what way*
- The concept appears, but no direct statement answers the question

### Behavior:
- Clearly states that no direct answer was found
- Provides extractive, document-faithful highlights
- Never framed as an answer
- No synthesis or inference
- Fully cited

### Example:
```json
{
  "mode": "guided_fallback",
  "no_direct_answer_reason": "No direct answer was found in the documents for this question.",
  "related_highlights": [
    {
      "highlight": "Volvo cars traditionally have a strong reputation for safety.",
      "source": "docs/volvo.pdf",
      "page": 12
    }
  ],
  "citations": [
    { "source": "docs/volvo.pdf", "page": 12 }
  ]
}
```

---

## 3. Hard Refusal

Used when **answering would be misleading or unsafe**.

### Used when:
- The question is vague (e.g., “Tell me more”)
- The question compares external entities
- No meaningful retrieval is possible

### Behavior:
- No answer is provided
- No highlights or citations are shown
- A deterministic refusal message is returned
- No document content is leaked

### Example:
```json
{
  "mode": "hard_refusal",
  "answer": "Please provide more context so I can answer accurately."
}
```

---

## Design Principles

- Explicit statements only
- Zero hallucination tolerance
- Deterministic routing
- Document-faithful citations
- No synthesis unless explicitly allowed

---

## Status

Current implementation supports:
- Direct Answer gating
- Guided Fallback extraction
- Hard Refusal safety checks
- Citation deduplication

Future enhancements are intentionally scoped and disabled by default.
