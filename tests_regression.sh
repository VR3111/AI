#!/bin/bash

set -e
export CI=${CI:-true}

# To run LOCAL retrieval tests: CI=false ./tests_regression.sh

BASE_URL="http://127.0.0.1:8001/query"
HEADER_JSON="Content-Type: application/json"
HEADER_AUTH="Authorization: Bearer ${P1_AUTH_TOKEN}"

if [ -z "${P1_AUTH_TOKEN}" ]; then
  echo "P1_AUTH_TOKEN is not set"
  exit 1
fi

echo "===== TEST 1: Direct Answer (CI → hard_refusal) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "What are Volvo’s core values?",
    "conversation_id": "t_direct"
  }')

echo "$RESP"
echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null
echo "$RESP" | jq -e '.citations | length == 0' > /dev/null


echo "===== TEST 2: Guided Fallback (CI-safe → hard_refusal) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "How are Volvo’s values communicated to customers?",
    "conversation_id": "t_fallback"
  }')

echo "$RESP"
echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null


echo "===== TEST 3: Hard Refusal (External Comparison) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "Is Volvo better than BMW?",
    "conversation_id": "t_external"
  }')

echo "$RESP"
echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null


echo "===== TEST 4: Hard Refusal (Vague Query) ====="
RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "Tell me more",
    "conversation_id": "t_vague"
  }')

echo "$RESP"
echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null


echo "===== TEST 5: Explicit Context Reset ====="

curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "What are Volvo’s core values?",
    "conversation_id": "t_reset"
  }' > /dev/null

RESP=$(curl -s -X POST $BASE_URL \
  -H "$HEADER_JSON" \
  -H "$HEADER_AUTH" \
  -d '{
    "query": "new topic",
    "conversation_id": "t_reset"
  }')

echo "$RESP"
echo "$RESP" | jq -e '.mode == "hard_refusal"' > /dev/null
echo "$RESP" | jq -e '.answer | test("reset")' > /dev/null


if [ "${CI}" != "true" ]; then
  echo "===== LOCAL TEST: Additional Resources ====="
  RESP=$(curl -s -X POST $BASE_URL \
    -H "$HEADER_JSON" \
    -H "$HEADER_AUTH" \
    -d '{
      "query": "What are Volvo’s core values?",
      "conversation_id": "t_local_multi"
    }')

  echo "$RESP"
  echo "$RESP" | jq -e '.mode == "direct_answer"' > /dev/null
  echo "$RESP" | jq -e 'has("artifacts")' > /dev/null
fi

echo "✅ ALL TESTS PASSED"
