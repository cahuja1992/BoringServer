# How to Add Docker Hub Workflow - Quick Guide

## Overview

The Docker Hub CI/CD workflow is ready but needs to be added manually due to GitHub App permissions. This is a **2-minute process**.

## Workflow File Location

The complete workflow file is located at: `.github/workflows/docker-hub.yml`

## Option 1: Quick Copy (Recommended) ⚡

### On Your Local Machine

```bash
# 1. Clone the repository (if not already cloned)
git clone https://github.com/cahuja1992/BoringServer.git
cd BoringServer

# 2. The workflow file already exists locally
ls -la .github/workflows/docker-hub.yml

# 3. Add it to git manually (from a machine with proper permissions)
git add .github/workflows/docker-hub.yml
git commit -m "ci: Add Docker Hub workflow"
git push origin main
```

## Option 2: GitHub Web UI (No Git Required) 🌐

### Step 1: Navigate to Workflows

1. Go to: https://github.com/cahuja1992/BoringServer
2. Click the **"Actions"** tab
3. Click **"New workflow"**
4. Click **"set up a workflow yourself"**

### Step 2: Create Workflow File

1. Name the file: `docker-hub.yml`
2. Copy the content below
3. Click **"Commit changes"**

### Step 3: Workflow Content to Copy

```yaml
name: Build and Push to Docker Hub

on:
  push:
    branches: [ "main" ]
    tags: [ 'v*.*.*' ]
  pull_request:
    branches: [ "main" ]
  workflow_dispatch:

env:
  DOCKER_HUB_REPOSITORY: boringserver/inference-engine
  IMAGE_NAME: inference-engine

jobs:
  test:
    name: Run Tests
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
          cache: 'pip'

      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip
          pip install -e ".[dev]"

      - name: Run linting
        run: |
          flake8 engine service.py --max-line-length=120 --exclude=__pycache__

      - name: Run unit tests
        run: |
          pytest tests/unit/ -v --cov=engine --cov-report=term

  build-and-push:
    name: Build and Push Docker Image
    needs: test
    runs-on: ubuntu-latest
    if: github.event_name != 'pull_request'
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_HUB_USERNAME }}
          password: ${{ secrets.DOCKER_HUB_TOKEN }}

      - name: Extract metadata
        id: meta
        uses: docker/metadata-action@v5
        with:
          images: ${{ env.DOCKER_HUB_REPOSITORY }}
          tags: |
            type=ref,event=branch
            type=ref,event=pr
            type=semver,pattern={{version}}
            type=semver,pattern={{major}}.{{minor}}
            type=semver,pattern={{major}}
            type=sha,prefix={{branch}}-
            type=raw,value=latest,enable={{is_default_branch}}

      - name: Build and push Docker image
        id: build-and-push
        uses: docker/build-push-action@v5
        with:
          context: .
          file: ./Dockerfile
          push: true
          tags: ${{ steps.meta.outputs.tags }}
          labels: ${{ steps.meta.outputs.labels }}
          cache-from: type=gha
          cache-to: type=gha,mode=max
          platforms: linux/amd64
          build-args: |
            BUILDKIT_INLINE_CACHE=1

      - name: Image digest
        run: echo "Image pushed with digest ${{ steps.build-and-push.outputs.digest }}"

  test-docker-image:
    name: Test Docker Image
    needs: build-and-push
    runs-on: ubuntu-latest
    
    steps:
      - name: Log in to Docker Hub
        uses: docker/login-action@v3
        with:
          username: ${{ secrets.DOCKER_HUB_USERNAME }}
          password: ${{ secrets.DOCKER_HUB_TOKEN }}

      - name: Pull and test image
        run: |
          docker pull ${{ env.DOCKER_HUB_REPOSITORY }}:main
          docker run --rm ${{ env.DOCKER_HUB_REPOSITORY }}:main python -c "import torch; import transformers; print('Dependencies OK')"
          echo "✅ Docker image tested successfully"

  create-release:
    name: Create GitHub Release
    needs: build-and-push
    runs-on: ubuntu-latest
    if: startsWith(github.ref, 'refs/tags/v')
    
    steps:
      - name: Checkout repository
        uses: actions/checkout@v4

      - name: Create Release
        uses: actions/create-release@v1
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tag_name: ${{ github.ref }}
          release_name: Release ${{ github.ref }}
          body: |
            ## BoringServer Release ${{ github.ref }}
            
            ### Docker Image
            ```bash
            docker pull ${{ env.DOCKER_HUB_REPOSITORY }}:${{ github.ref_name }}
            ```
            
            ### Quick Start
            ```bash
            docker run -p 8000:8000 ${{ env.DOCKER_HUB_REPOSITORY }}:${{ github.ref_name }}
            ```
            
            See [DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md) for detailed instructions.
          draft: false
          prerelease: false
```

## Before You Start

### 1. Update Repository Name (if needed)

If your Docker Hub username is NOT `boringserver`, update this line in the workflow:

```yaml
env:
  DOCKER_HUB_REPOSITORY: <your-dockerhub-username>/inference-engine
```

### 2. Set Up Docker Hub Secrets

You must add these secrets to GitHub:

1. Go to: https://github.com/cahuja1992/BoringServer/settings/secrets/actions
2. Add **DOCKER_HUB_USERNAME**: Your Docker Hub username
3. Add **DOCKER_HUB_TOKEN**: Your Docker Hub access token

See [DOCKER_HUB_SETUP.md](docs/DOCKER_HUB_SETUP.md) for detailed instructions.

## After Adding the Workflow

### Test the Workflow

```bash
# Trigger the workflow
git commit --allow-empty -m "ci: Test Docker Hub workflow"
git push origin main
```

### Monitor Progress

1. Go to: https://github.com/cahuja1992/BoringServer/actions
2. Click on the running workflow
3. Watch the 4 jobs execute:
   - ✅ Run Tests (2-3 min)
   - ✅ Build and Push Docker Image (5-8 min)
   - ✅ Test Docker Image (1-2 min)
   - ✅ Create Release (only on tags)

### Verify Docker Hub

After successful workflow:

1. Check tags: https://hub.docker.com/r/boringserver/inference-engine/tags
2. Expected tags: `latest`, `main`, `main-<commit-sha>`

### Pull and Test

```bash
# Pull the image
docker pull boringserver/inference-engine:latest

# Run the container
docker run -p 8000:8000 boringserver/inference-engine:latest

# Test API (in another terminal)
curl http://localhost:8000/health
```

## What the Workflow Does

### On Every Push to Main:
1. Runs 78 unit tests
2. Builds Docker image
3. Pushes to Docker Hub with tags: `latest`, `main`, `main-<sha>`
4. Tests the pushed image

### On Version Tags (e.g., v1.0.0):
1. Runs all tests
2. Builds and pushes with multiple tags: `v1.0.0`, `1.0`, `1`, `latest`
3. Creates GitHub release with Docker instructions

### On Pull Requests:
1. Runs tests only (no Docker push)

## Troubleshooting

### Issue: "DOCKER_HUB_USERNAME not found"

**Fix:** Add the secret in GitHub repository settings
```
Settings → Secrets and variables → Actions → New repository secret
```

### Issue: "unauthorized: authentication required"

**Fix:** Regenerate Docker Hub token with Read/Write permissions

### Issue: Workflow doesn't appear in Actions

**Fix:** Ensure file is at `.github/workflows/docker-hub.yml` (exact path)

## Complete Documentation

For detailed setup instructions, see:

- **Setup Guide**: [docs/DOCKER_HUB_SETUP.md](docs/DOCKER_HUB_SETUP.md)
- **Pipeline Overview**: [docs/DOCKER_HUB_SUMMARY.md](docs/DOCKER_HUB_SUMMARY.md)
- **Docker Deployment**: [docs/DOCKER_DEPLOYMENT.md](docs/DOCKER_DEPLOYMENT.md)

## Quick Links

- **Repository**: https://github.com/cahuja1992/BoringServer
- **GitHub Actions**: https://github.com/cahuja1992/BoringServer/actions
- **Docker Hub**: https://hub.docker.com (create your repository here)
- **Secrets Settings**: https://github.com/cahuja1992/BoringServer/settings/secrets/actions

## Estimated Time

- **Adding workflow**: 2 minutes
- **First build**: 8-12 minutes
- **Subsequent builds**: 5-7 minutes (cached)

---

**Need Help?** See the troubleshooting section in [DOCKER_HUB_SETUP.md](docs/DOCKER_HUB_SETUP.md)
