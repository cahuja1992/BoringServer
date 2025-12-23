#!/bin/bash

# Script to build and run the inference engine with Docker

set -e

echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║         Building and Running Production Inference Engine                   ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
IMAGE_NAME="inference-engine"
IMAGE_TAG="latest"
CONTAINER_NAME="inference-engine-cpu"
MODEL_DIR="models/clip"
PORT=8000
METRICS_PORT=9090

echo -e "${BLUE}Step 1: Building Docker image...${NC}"
docker build -t ${IMAGE_NAME}:${IMAGE_TAG} .

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Docker image built successfully${NC}"
else
    echo "✗ Docker build failed"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 2: Stopping any existing containers...${NC}"
docker stop ${CONTAINER_NAME} 2>/dev/null || true
docker rm ${CONTAINER_NAME} 2>/dev/null || true

echo ""
echo -e "${BLUE}Step 3: Starting inference engine (CPU mode)...${NC}"
docker run -d \
    --name ${CONTAINER_NAME} \
    -p ${PORT}:8000 \
    -p ${METRICS_PORT}:9090 \
    -e ENVIRONMENT=prod \
    -e INFERENCE_RAY__NUM_GPUS=0 \
    ${IMAGE_NAME}:${IMAGE_TAG} \
    --model_directory ${MODEL_DIR} --env prod

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Container started successfully${NC}"
else
    echo "✗ Failed to start container"
    exit 1
fi

echo ""
echo -e "${BLUE}Step 4: Waiting for service to be ready...${NC}"
echo "This may take 1-2 minutes as the model downloads and initializes..."

# Wait for health check
MAX_ATTEMPTS=60
ATTEMPT=0
while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
    if curl -s http://localhost:${PORT}/health > /dev/null 2>&1; then
        echo -e "${GREEN}✓ Service is healthy!${NC}"
        break
    fi
    ATTEMPT=$((ATTEMPT + 1))
    echo -n "."
    sleep 2
done

if [ $ATTEMPT -eq $MAX_ATTEMPTS ]; then
    echo ""
    echo -e "${YELLOW}⚠ Service health check timeout${NC}"
    echo "Checking container logs:"
    docker logs ${CONTAINER_NAME} --tail 50
    exit 1
fi

echo ""
echo "╔════════════════════════════════════════════════════════════════════════════╗"
echo "║                    🎉 Service is running! 🎉                               ║"
echo "╚════════════════════════════════════════════════════════════════════════════╝"
echo ""
echo -e "${GREEN}API Endpoints:${NC}"
echo "  • Health:  http://localhost:${PORT}/health"
echo "  • Ready:   http://localhost:${PORT}/ready"
echo "  • Info:    http://localhost:${PORT}/info"
echo "  • Metrics: http://localhost:${METRICS_PORT}/metrics"
echo "  • Infer:   http://localhost:${PORT}/infer (POST)"
echo ""
echo -e "${GREEN}Useful Commands:${NC}"
echo "  • View logs:    docker logs -f ${CONTAINER_NAME}"
echo "  • Stop service: docker stop ${CONTAINER_NAME}"
echo "  • Restart:      docker restart ${CONTAINER_NAME}"
echo "  • Remove:       docker rm -f ${CONTAINER_NAME}"
echo ""
echo -e "${YELLOW}Testing the API:${NC}"
echo "  curl http://localhost:${PORT}/health"
echo "  curl http://localhost:${PORT}/info"
echo ""
echo -e "${YELLOW}Example inference (requires image file):${NC}"
echo "  curl -X POST http://localhost:${PORT}/infer \\"
echo "    -F \"image=@your_image.jpg\" \\"
echo "    -F \"text=optional text\""
echo ""
