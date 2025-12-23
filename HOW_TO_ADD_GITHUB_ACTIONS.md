# How to Add GitHub Actions Workflow

The GitHub Actions CI/CD workflow cannot be pushed via the automated system due to GitHub App permission restrictions. Here's how to add it manually:

## Option 1: Add via GitHub Web UI (Easiest)

1. **Go to your repository**: https://github.com/cahuja1992/BoringServer

2. **Navigate to Actions**:
   - Click on the "Actions" tab
   - Click "set up a workflow yourself"

3. **Create the workflow file**:
   - GitHub will create `.github/workflows/main.yml`
   - Replace the filename with `ci.yml`

4. **Copy the workflow content** from below or from the local file at `.github/workflows/ci.yml`

5. **Commit the file** directly to the main branch

## Option 2: Add via Git CLI (From Your Local Machine)

If you have Git installed locally (not through this automated system):

```bash
# Clone the repo
git clone https://github.com/cahuja1992/BoringServer.git
cd BoringServer

# Create the workflow directory
mkdir -p .github/workflows

# Copy or create the ci.yml file (content below)
# Then commit and push
git add .github/workflows/ci.yml
git commit -m "feat: Add GitHub Actions CI/CD workflow"
git push origin main
```

## Workflow File Content

Create `.github/workflows/ci.yml` with this content:

```yaml
name: CI

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main, develop ]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11"]

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python ${{ matrix.python-version }}
      uses: actions/setup-python@v4
      with:
        python-version: ${{ matrix.python-version }}
    
    - name: Cache pip dependencies
      uses: actions/cache@v3
      with:
        path: ~/.cache/pip
        key: ${{ runner.os }}-pip-${{ hashFiles('pyproject.toml') }}
        restore-keys: |
          ${{ runner.os }}-pip-
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -e ".[dev]"
    
    - name: Lint with flake8
      run: |
        # Stop the build if there are Python syntax errors or undefined names
        flake8 engine/ --count --select=E9,F63,F7,F82 --show-source --statistics
        # Exit-zero treats all errors as warnings
        flake8 engine/ --count --exit-zero --max-complexity=10 --max-line-length=100 --statistics
    
    - name: Check code formatting with black
      run: |
        black --check engine/ tests/
    
    - name: Check import sorting with isort
      run: |
        isort --check-only engine/ tests/
    
    - name: Type check with mypy
      run: |
        mypy engine/ --ignore-missing-imports
      continue-on-error: true
    
    - name: Run unit tests
      run: |
        pytest tests/unit/ -v --cov=engine --cov-report=xml --cov-report=term-missing
    
    - name: Upload coverage to Codecov
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml
        flags: unittests
        name: codecov-umbrella
        fail_ci_if_error: false

  build:
    runs-on: ubuntu-latest
    needs: test
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Docker Buildx
      uses: docker/setup-buildx-action@v2
    
    - name: Build Docker image
      run: |
        docker build -t inference-engine:test .
    
    - name: Test Docker image
      run: |
        docker run --rm inference-engine:test --help
```

## What the Workflow Does

Once added, this workflow will automatically:

✅ **Run on every push and PR** to main/develop branches
✅ **Test on Python 3.10 and 3.11**
✅ **Check code quality**:
   - flake8 for linting
   - black for formatting
   - isort for import sorting
   - mypy for type checking
✅ **Run all unit tests** with coverage reporting
✅ **Build Docker image** to ensure it builds correctly
✅ **Upload coverage** to Codecov (optional)

## Verification

After adding the workflow:

1. Go to the "Actions" tab in your repository
2. You should see the CI workflow running
3. Click on it to see the build progress
4. Green checkmarks mean all tests passed!

## Troubleshooting

If the workflow fails:
- Check the logs in the Actions tab
- Common issues:
  - Missing dependencies (already configured in pyproject.toml)
  - Code formatting issues (run `black engine/ tests/` locally)
  - Import sorting issues (run `isort engine/ tests/` locally)
  - Test failures (run `pytest tests/unit/` locally)

## Current Status

- ✅ All production code is on GitHub
- ✅ All tests are written and passing locally
- ✅ Docker support is implemented
- ⏳ GitHub Actions workflow needs manual addition (this guide)

Once you add the workflow file, your repository will have complete CI/CD automation!
