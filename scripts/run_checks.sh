#!/bin/bash

# Local development script to run the same checks as CI
# This helps catch issues before pushing to GitHub

set -e  # Exit on any error

echo "🔍 Running local development checks..."
echo

# Check if virtual environment is activated
if [[ "$VIRTUAL_ENV" == "" ]]; then
    echo "⚠️  Warning: No virtual environment detected. Consider activating .venv"
    echo "   Run: source .venv/bin/activate"
    echo
fi

# Install dependencies if needed
echo "📦 Installing dependencies..."
pip install -r requirements.txt
pip install -e .
echo

# Run syntax and error checks
echo "🔍 Running flake8 syntax checks..."
flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics
echo "✅ Syntax checks passed"
echo

# Run tests
echo "🧪 Running tests..."
pytest tests/ -v
echo "✅ Tests passed"
echo

# Run full linting (if requested)
if [[ "$1" == "--full" ]]; then
    echo "🔍 Running full code quality checks..."
    
    echo "  - Full flake8 linting..."
    flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics
    
    echo "  - Black code formatting check..."
    black --check --diff . || echo "⚠️  Code formatting issues found. Run 'black .' to fix."
    
    echo "  - MyPy type checking..."
    mypy src/ --ignore-missing-imports || echo "⚠️  Type checking issues found."
    
    echo "  - Safety security check..."
    safety check || echo "⚠️  Security vulnerabilities found."
    
    echo "  - Bandit security check..."
    bandit -r src/ || echo "⚠️  Security issues found."
    
    echo "✅ Full checks completed"
fi

echo
echo "🎉 All checks completed successfully!"
echo
echo "💡 Tips:"
echo "   - Run './scripts/run_checks.sh --full' for comprehensive checks"
echo "   - Run 'black .' to auto-format code"
echo "   - Run 'pytest --cov=src' for test coverage" 