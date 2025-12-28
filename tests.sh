#!/bin/bash

BASE_URL="http://127.0.0.1:8001/query"
HEADER="Content-Type: application/json"

echo "===== TEST 1: Direct Answer ====="
curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "What are Volvo’s core values?",
    "conversation_id": "t_direct"
  }'
echo -e "\n"

echo "===== TEST 2: Guided Fallback (Explanatory) ====="
curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "How are Volvo’s values communicated to customers?",
    "conversation_id": "t_fallback"
  }'
echo -e "\n"

echo "===== TEST 3: Hard Refusal (External Comparison) ====="
curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "Is Volvo better than BMW?",
    "conversation_id": "t_external"
  }'
echo -e "\n"

echo "===== TEST 4: Hard Refusal (Vague) ====="
curl -s -X POST $BASE_URL \
  -H "$HEADER" \
  -d '{
    "query": "Tell me more",
    "conversation_id": "t_vague"
  }'
echo -e "\n"
