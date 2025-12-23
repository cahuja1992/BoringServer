# Docker Hub Setup Guide

This guide explains how to set up automated Docker image publishing to Docker Hub for the BoringServer inference engine.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Docker Hub Setup](#docker-hub-setup)
- [GitHub Secrets Configuration](#github-secrets-configuration)
- [Workflow Overview](#workflow-overview)
- [Usage](#usage)
- [Troubleshooting](#troubleshooting)

## Prerequisites

1. **Docker Hub Account**: Create a free account at [hub.docker.com](https://hub.docker.com)
2. **GitHub Repository**: Your BoringServer repository with admin access
3. **GitHub Actions**: Enabled in your repository

## Docker Hub Setup

### 1. Create Docker Hub Repository

1. Log in to [Docker Hub](https://hub.docker.com)
2. Click **"Create Repository"**
3. Configure the repository:
   - **Name**: `inference-engine` (or your preferred name)
   - **Namespace**: Your Docker Hub username (e.g., `boringserver`)
   - **Visibility**: Public or Private
   - **Description**: "Production-grade inference engine for embedding models"
4. Click **"Create"**

Your repository will be available at: `docker.io/<your-username>/inference-engine`

### 2. Create Access Token

1. Go to [Account Settings → Security](https://hub.docker.com/settings/security)
2. Click **"New Access Token"**
3. Configure the token:
   - **Description**: "GitHub Actions - BoringServer"
   - **Permissions**: "Read, Write, Delete"
4. Click **"Generate"**
5. **IMPORTANT**: Copy the token immediately (it won't be shown again)

## GitHub Secrets Configuration

Add your Docker Hub credentials to GitHub repository secrets:

### Method 1: GitHub Web UI

1. Go to your repository: `https://github.com/<username>/BoringServer`
2. Navigate to **Settings** → **Secrets and variables** → **Actions**
3. Click **"New repository secret"**
4. Add these two secrets:

   **Secret 1:**
   - Name: `DOCKER_HUB_USERNAME`
   - Value: Your Docker Hub username (e.g., `boringserver`)

   **Secret 2:**
   - Name: `DOCKER_HUB_TOKEN`
   - Value: The access token you generated

### Method 2: GitHub CLI

```bash
# Install GitHub CLI if needed
# brew install gh  # macOS
# sudo apt install gh  # Ubuntu/Debian

# Authenticate
gh auth login

# Add secrets
gh secret set DOCKER_HUB_USERNAME --body "your-dockerhub-username"
gh secret set DOCKER_HUB_TOKEN --body "your-access-token"
```

### Verify Secrets

```bash
gh secret list
# Should show:
# DOCKER_HUB_USERNAME
# DOCKER_HUB_TOKEN
```

## Workflow Overview

The workflow (`.github/workflows/docker-hub.yml`) consists of 4 jobs:

### Job 1: Test (Always runs)
- Sets up Python 3.10
- Installs dependencies
- Runs linting with flake8
- Runs unit tests with pytest
- Generates coverage report

### Job 2: Build and Push (Only on push to main or tags)
- Builds multi-architecture Docker image
- Pushes to Docker Hub with multiple tags
- Uses build cache for faster builds

### Job 3: Test Docker Image (After successful push)
- Pulls the newly pushed image
- Runs basic validation tests
- Verifies dependencies

### Job 4: Create Release (Only on version tags)
- Creates GitHub release
- Includes Docker pull commands
- Adds quick start instructions

## Workflow Triggers

The workflow runs on:

1. **Push to main branch**:
   ```bash
   git push origin main
   ```
   Creates tags: `latest`, `main`, `main-<sha>`

2. **Version tags**:
   ```bash
   git tag v1.0.0
   git push origin v1.0.0
   ```
   Creates tags: `v1.0.0`, `1.0`, `1`, `latest`

3. **Pull requests** (tests only, no push):
   ```bash
   # Automatically runs on PR creation
   ```

4. **Manual trigger**:
   - Go to Actions → "Build and Push to Docker Hub" → Run workflow

## Docker Image Tags

The workflow automatically creates these tags:

| Tag | When Created | Example |
|-----|-------------|---------|
| `latest` | Push to main branch | `boringserver/inference-engine:latest` |
| `main` | Push to main branch | `boringserver/inference-engine:main` |
| `v1.2.3` | Version tag | `boringserver/inference-engine:v1.2.3` |
| `1.2` | Version tag | `boringserver/inference-engine:1.2` |
| `1` | Version tag | `boringserver/inference-engine:1` |
| `main-abc1234` | Commit SHA | `boringserver/inference-engine:main-abc1234` |

## Usage

### Update Repository Name (if needed)

If your Docker Hub username is different, update the workflow:

```yaml
# .github/workflows/docker-hub.yml
env:
  DOCKER_HUB_REPOSITORY: <your-dockerhub-username>/inference-engine
```

### Verify Workflow

1. Push a change to main:
   ```bash
   git add .
   git commit -m "test: Verify Docker Hub workflow"
   git push origin main
   ```

2. Check the workflow:
   - Go to **Actions** tab in GitHub
   - Click on the running workflow
   - Monitor progress of all 4 jobs

3. Verify on Docker Hub:
   - Go to `https://hub.docker.com/r/<username>/inference-engine/tags`
   - You should see the new tags

### Pull and Test Image

```bash
# Pull latest image
docker pull boringserver/inference-engine:latest

# Run the server
docker run -p 8000:8000 boringserver/inference-engine:latest

# Test health endpoint
curl http://localhost:8000/health
```

### Create a Release

```bash
# Create and push version tag
git tag -a v1.0.0 -m "Release v1.0.0: Production-grade inference engine"
git push origin v1.0.0
```

This will:
1. Run all tests
2. Build and push Docker image with version tags
3. Create GitHub release with Docker instructions

## Troubleshooting

### Issue: Workflow fails with "unauthorized: authentication required"

**Solution**: Verify Docker Hub credentials
```bash
# Check secrets are set
gh secret list

# Re-add the token if needed
gh secret set DOCKER_HUB_TOKEN --body "your-new-token"
```

### Issue: "repository does not exist"

**Solution**: Update repository name in workflow
1. Check your Docker Hub repository name
2. Update `DOCKER_HUB_REPOSITORY` in `.github/workflows/docker-hub.yml`

### Issue: Build fails with "insufficient memory"

**Solution**: Optimize Dockerfile
- Multi-stage builds are already implemented
- Consider reducing dependencies
- Use `--no-cache-dir` for pip

### Issue: Tests pass locally but fail in CI

**Solution**: Check environment differences
```bash
# Run tests locally with same Python version
python3.10 -m pytest tests/unit/ -v

# Check dependencies
pip list
```

### Issue: Docker image too large

**Solution**: Optimize image size
```bash
# Check current size
docker images boringserver/inference-engine:latest

# Use dive to analyze layers
docker run --rm -it -v /var/run/docker.sock:/var/run/docker.sock \
  wagoodman/dive:latest boringserver/inference-engine:latest
```

Current image size: ~2.5GB (includes PyTorch, CUDA base, transformers)

## CI/CD Pipeline Status

After setup, you'll have:

✅ Automated testing on every push  
✅ Docker image building and publishing  
✅ Multi-tag support for versioning  
✅ Automatic GitHub releases  
✅ Image validation tests  
✅ Build caching for faster builds  

## Best Practices

1. **Use semantic versioning**: `v1.2.3` (major.minor.patch)
2. **Test before tagging**: Always push to main and verify before creating release tags
3. **Keep secrets secure**: Never commit tokens to repository
4. **Monitor workflow runs**: Check Actions tab regularly
5. **Update documentation**: Keep version numbers in README updated

## Additional Resources

- [Docker Hub Documentation](https://docs.docker.com/docker-hub/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Docker Build Push Action](https://github.com/docker/build-push-action)
- [BoringServer Documentation](../README.md)

## Security Notes

⚠️ **Important Security Practices:**

1. Use access tokens instead of passwords
2. Set minimum required permissions for tokens
3. Rotate tokens regularly (every 6-12 months)
4. Use repository secrets, never commit credentials
5. Enable Docker Hub 2FA for additional security
6. Monitor access logs in Docker Hub

## Next Steps

After successful setup:

1. ✅ Verify workflow runs successfully
2. ✅ Pull and test the Docker image
3. ✅ Create your first release tag
4. ✅ Update README with Docker Hub badge
5. ✅ Set up monitoring and alerts
6. ✅ Document your CI/CD pipeline

For deployment instructions, see [DOCKER_DEPLOYMENT.md](DOCKER_DEPLOYMENT.md).
