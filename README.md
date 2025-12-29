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
- The answer appears **verbatim** in the document
- Retrieved text meets strict relevance and distance thresholds
- No interpretation is required to answer

### Behavior:
- Lists facts only
- No explanation, interpretation, or mechanism
- No inference or synthesis
- Answer text is extracted directly from the document
- Citations are always included
- Citations are deduplicated by `(source, page)`

### Output rules:
- If any part of the answer requires inference → **Direct Answer is not allowed**
- If no explicit statement exists → **Guided Fallback is triggered**

### Example:
```json
{
  "mode": "direct_answer",
  "answer": "Volvo's core values are quality, safety, and environmental care.",
  "citations": [
    { "source": "docs/volvo.pdf", "page": 18 }
  ]
}

---

## 2. Guided Fallback

Returned **only when the topic exists in the documents, but no explicit answer is stated**.

This mode provides **context without answering**.

### Used when:
- The question asks *how*, *why*, or *in what way*
- The topic appears in the documents
- No single sentence explicitly answers the question
- Answering directly would require inference or synthesis

### Behavior:
- Clearly states that **no direct answer was found**
- Provides **extractive, document-faithful highlights only**
- Highlights are **not framed as answers**
- No synthesis or interpretation
- No inferred relationships
- Fully cited using document source and page

### Output rules:
- Highlights must be copied **verbatim** from the document
- Only displayed highlights may be cited
- No additional explanation or reasoning is allowed
- If an explicit answer is later found → **Direct Answer must be used instead**

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

---

## 3. Hard Refusal

Returned **only when answering would be misleading, unsafe, or unsupported by the documents**.

No document content is returned in this mode.

### Used when:
- The question is vague or underspecified (e.g., “Tell me more”, “Explain this”)
- The question compares external entities (e.g., “Volvo vs BMW”)
- The question references information not present in the documents
- No meaningful or safe retrieval is possible
- Responding would require speculation, inference, or external knowledge

### Behavior:
- No answer is provided
- No highlights are shown
- No citations are included
- A deterministic refusal message is returned
- No document content is leaked

### Output rules:
- Refusal messages are **fixed and deterministic**
- No additional explanation or guidance is provided
- The system must not rephrase, summarize, or interpret documents
- If sufficient context is later provided → request may be reprocessed

### Example:
```json
{
  "mode": "hard_refusal",
  "answer": "Please provide more context so I can answer accurately."
}


---
## Query Classification Rules

All incoming queries are classified **before answering**.

Classification determines the **only valid response mode**.

### Classification logic:
- Definition-style queries (`what is`, `what are`, `means`, `refers to`) are eligible for **Direct Answer**
- Explanatory queries (`how`, `why`, `in what way`) are routed to **Guided Fallback**
- Vague queries are routed to **Hard Refusal**
- Comparative queries involving external entities are routed to **Hard Refusal**

### Enforcement rules:
- Classification happens **before generation**
- The system must not override the classification result
- If classification is ambiguous → **safer mode is chosen**
- Direct Answer is the **most restricted** mode and must be earned

---

## Retrieval and Safety Controls

All answers are constrained by **document retrieval and distance thresholds**.

### Retrieval rules:
- Only chunks retrieved from indexed documents are eligible
- Retrieved text must meet strict similarity and distance thresholds
- Results are deduplicated before use

### Safety controls:
- If no chunks pass thresholds → **Hard Refusal**
- If chunks exist but do not explicitly answer → **Guided Fallback**
- Generated answers must not introduce new facts
- Output may only reference retrieved content

### Citation rules:
- Citations are derived from `(source, page)`
- Citations are deduplicated
- Guided Fallback citations must map **only** to displayed highlights

---

## Design Principles

This system is intentionally conservative by design.

### Core principles:
- Explicit statements only
- Zero hallucination tolerance
- No inference, synthesis, or reasoning
- Deterministic routing and outputs
- Document content is never paraphrased in Direct Answer
- Context is allowed **only** in Guided Fallback

### Non-goals:
- Answering beyond the document
- Explaining intent or meaning
- Combining multiple sources into conclusions
- Acting as a general-purpose assistant

---

## Status

### Current capabilities:
- Deterministic query classification
- Strict Direct Answer gating
- Guided Fallback with extractive highlights
- Hard Refusal safety enforcement
- Citation deduplication by `(source, page)`
- CI-safe, regression-tested behavior

### Intentionally disabled:
- Multi-document synthesis
- Answer expansion or explanation
- External knowledge lookup
- Speculative or probabilistic responses

Future enhancements are **explicitly opt-in** and disabled by default.

---
