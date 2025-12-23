#!/bin/bash

# Quick test script for the inference engine API

set -e

BASE_URL="${BASE_URL:-http://localhost:8000}"

echo "Testing Inference Engine API at ${BASE_URL}"
echo ""

# Test health endpoint
echo "1. Testing /health endpoint..."
HEALTH=$(curl -s "${BASE_URL}/health")
echo "   Response: ${HEALTH}"
echo ""

# Test ready endpoint
echo "2. Testing /ready endpoint..."
READY=$(curl -s "${BASE_URL}/ready" || echo '{"status":"not ready"}')
echo "   Response: ${READY}"
echo ""

# Test info endpoint
echo "3. Testing /info endpoint..."
INFO=$(curl -s "${BASE_URL}/info" || echo '{"error":"not available"}')
echo "   Response: ${INFO}"
echo ""

# Create a test image
echo "4. Creating test image..."
python3 << 'EOF'
from PIL import Image
import random

# Create a simple test image
img = Image.new('RGB', (224, 224), color=(random.randint(0,255), random.randint(0,255), random.randint(0,255)))
img.save('/tmp/test_image.jpg')
print("   Test image created at /tmp/test_image.jpg")
EOF

# Test inference endpoint
if [ -f "/tmp/test_image.jpg" ]; then
    echo ""
    echo "5. Testing /infer endpoint with test image..."
    INFER=$(curl -s -X POST "${BASE_URL}/infer" \
        -F "image=@/tmp/test_image.jpg" \
        -F "text=a test image" \
        2>/dev/null || echo '{"error":"inference failed"}')
    
    echo "   Response (first 500 chars):"
    echo "   ${INFER}" | cut -c1-500
    echo ""
fi

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                         API Test Complete                                  ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
