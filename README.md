# Internal Document Assistant (RAG)

This repository contains a **document-faithful internal assistant** designed for regulated and enterprise environments.

The system answers questions **only from locally provided documents** and is intentionally constrained to avoid hallucinations, inference, or external knowledge.

---

## Core Guarantees

- Reads **only local PDFs**
- No internet access
- No general knowledge
- No guessing or inference
- Deterministic, auditable behavior
- Citations always point to document source + page

This is **not a chatbot**.  
It behaves like an internal SME who knows *only* the provided documents.

---

## Response Modes

The API operates in exactly **three modes**.

### 1. Direct Answer
Returned **only when the document explicitly states the answer**.

- Used mainly for definition-style questions (e.g., “What are …”)
- Lists facts only
- No explanation, interpretation, or mechanism
- Includes citations

Example:
```json
{
  "mode": "direct_answer",
  "answer": "Volvo's core values are quality, safety, and environmental care.",
  "citations": [{ "source": "docs/volvo.pdf", "page": 18 }]
}

## 2. Guided Fallback

Used when:
- The topic exists in the documents
- But no explicit answer is stated

Behavior:
- Clearly states that no direct answer was found
- Provides **extractive, document-faithful highlights**
- Never framed as an answer
- No synthesis or inference
- Fully cited

Example:

{
  "mode": "guided_fallback",
  "no_direct_answer_reason": "No direct answer was found in the documents for this question.",
  "related_highlights": [
    {
      "highlight": "Safety is one of the company’s core values.",
      "source": "docs/volvo.pdf",
      "page": 12
    }
  ],
  "citations": [
    { "source": "docs/volvo.pdf", "page": 12 }
  ]
}

### 3. Hard Refusal

Used when:
- The question is vague (e.g., “Tell me more”)
- The question compares external entities
- No meaningful retrieval is possible

Behavior:
- No answer is provided
- No highlights or citations are shown
- A deterministic refusal message is returned
- No document content is leaked

Example:
```json
{
  "mode": "hard_refusal",
  "answer": "Please provide more context so I can answer accurately."
}


---

## ✅ **What the System Will NEVER Do (fixed Markdown)**

```md
## What the System Will NEVER Do

- Use external or pretrained knowledge
- Infer intent beyond what is explicitly asked
- Speculate or fill missing information
- Answer cross-company or external comparisons
- Explain mechanisms unless explicitly stated in the document
- Turn uncertainty into confident language

If the document does not state something explicitly, the system will not invent it.


## Versioning & Trust

- `v1` — First trusted, locked behavior
- Each version tag represents a **verified trust checkpoint**

Any behavioral change requires:
- Updated behavior tests
- A new version tag


## Next Steps

Planned future improvements (not implemented yet):

- Sentence-level explicit answer gating
- Multi-document scoping and document selection
- Conversation reset and topic-boundary controls
- CI-based pytest execution

These will only be added after corresponding behavior tests are defined.


