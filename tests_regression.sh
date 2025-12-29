#!/bin/bash

set -e  # Exit immediately if any assertion fails

BASE_URL="http://127.0.0.1:8001/query"
HEADER="Content-Type: application/json"

echo "===== TEST 1: Direct Answer ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "What are Volvo’s core values?",
    "conversation_id": "t_direct"
  }')

echo "$RESP"

echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null
echo "$RESP" | jq -e '.citations | length == 0' > /dev/null


echo "===== TEST 2: Guided Fallback (Explanatory) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "How are Volvo’s values communicated to customers?",
    "conversation_id": "t_fallback"
  }')

echo "$RESP"

echo "$RESP" | jq -e '.mode == "guided_fallback"' > /dev/null
echo "$RESP" | jq -e '.related_highlights | length > 0' > /dev/null
echo "$RESP" | jq -e 'has("answer") | not' > /dev/null


echo "===== TEST 3: Hard Refusal (External Comparison) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "Is Volvo better than BMW?",
    "conversation_id": "t_external"
  }')

echo "$RESP"

echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null
echo "$RESP" | jq -e '.citations | length == 0' > /dev/null


echo "===== TEST 4: Hard Refusal (Vague Query) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "Tell me more",
    "conversation_id": "t_vague"
  }')

echo "$RESP"

echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null
echo "$RESP" | jq -e '.answer | test("context")' > /dev/null


echo "✅ ALL TESTS PASSED"
