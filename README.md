# AEM CLI

A command-line tool for Adobe Experience Manager (AEM) content management and cleanup operations.

## Overview

AEM CLI provides utilities for managing AEM content repositories, with a focus on cleaning and maintaining `.content.xml` files. The tool helps developers and content managers automate common AEM maintenance tasks.

## Features

### Content Cleanup
- **Remove AEM metadata properties** from `.content.xml` files
- **Flexible property selection** - use default AEM properties or specify custom ones
- **Recursive processing** - handles entire directory trees
- **Dry-run mode** - preview changes before applying them
- **Detailed reporting** - see exactly what properties are removed

#### Default Properties Removed
The tool removes common AEM system properties that are typically not needed in source control:

- `cq:isDelivered`, `cq:lastModified`, `cq:lastModifiedBy`
- `cq:lastReplicated*`, `cq:lastReplicatedBy*`, `cq:lastReplicationAction*`
- `jcr:isCheckedOut`, `jcr:lastModified`, `jcr:lastModifiedBy`, `jcr:uuid`

## Installation

### Prerequisites
- Python 3.8 or higher
- pip package manager

### Install from Source
```bash
# Clone the repository
git clone <repository-url>
cd aem-cli

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install the package in development mode
pip install -e .
```

## Usage

### Content Cleanup Command

#### Basic Usage
```bash
# Clean using default AEM properties
aemcli content-cleanup /path/to/content

# Preview changes without modifying files
aemcli content-cleanup /path/to/content --dry-run
```

#### Advanced Usage
```bash
# Use only custom properties
aemcli content-cleanup /path/to/content cq:customProp jcr:myProp

# Combine default and custom properties
aemcli content-cleanup /path/to/content --default cq:customProp

# Explicitly use default properties
aemcli content-cleanup /path/to/content --default
```

#### Options
- `--dry-run` - Show what would be changed without modifying files
- `--default` - Include default AEM properties in removal list
- `--help` - Show detailed help and examples

### Examples

#### Example 1: Clean AEM Project
```bash
# Clean all .content.xml files in an AEM project
aemcli content-cleanup content/sites-franklin-commerce --dry-run

# Apply the changes
aemcli content-cleanup content/sites-franklin-commerce
```

#### Example 2: Custom Properties
```bash
# Remove only specific custom properties
aemcli content-cleanup /path/to/content cq:myCustomProp jcr:tempData

# Remove default properties plus custom ones
aemcli content-cleanup /path/to/content --default cq:myCustomProp
```

#### Example 3: Preview Mode
```bash
# See what would be changed without modifying files
aemcli content-cleanup /path/to/content --dry-run
```

## Development

### Project Structure
```
aem-cli/
├── src/aemcli/           # Main package
│   ├── cli.py           # CLI entry point
│   └── commands/        # Command modules
│       └── content_cleanup.py
├── tests/               # Test suite
│   ├── test_content_cleanup.py
│   └── test_content/    # Test data
├── requirements.txt     # Dependencies
├── pyproject.toml      # Project configuration
└── README.md           # This file
```

### Running Tests
```bash
# Activate virtual environment
source .venv/bin/activate

# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage
python -m pytest --cov=aemcli
```

### Code Quality
```bash
# Format code
black src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Local Development Checks
Run the same checks locally that GitHub Actions will run:

```bash
# Quick checks (syntax and tests)
./scripts/run_checks.sh

# Full checks (includes linting, formatting, type checking, security)
./scripts/run_checks.sh --full
```

### Pre-commit Hooks (Optional)
Set up pre-commit hooks to run checks automatically before each commit:

```bash
# Install pre-commit hooks
pre-commit install

# Run hooks on all files (optional)
pre-commit run --all-files
```

## CI/CD

This project uses GitHub Actions for continuous integration and deployment. Two workflows are configured:

### Test Workflow (`test.yml`)
- **Triggers**: Every push and pull request
- **Purpose**: Quick feedback on test results and basic linting
- **Actions**:
  - Runs tests with pytest
  - Performs basic syntax and error checking with flake8
  - Uses Python 3.11 on Ubuntu

### CI Workflow (`ci.yml`)
- **Triggers**: Push/PR to main, master, or develop branches
- **Purpose**: Comprehensive testing and code quality checks
- **Actions**:
  - **Multi-version testing**: Tests against Python 3.8, 3.9, 3.10, 3.11, and 3.12
  - **Code quality**: Runs flake8, black, and mypy
  - **Test coverage**: Generates coverage reports and uploads to Codecov
  - **Security scanning**: Runs safety and bandit security checks
  - **Dependency caching**: Speeds up builds by caching pip dependencies

### Workflow Features
- **Parallel execution**: Test and security jobs run in parallel
- **Caching**: Pip dependencies are cached for faster builds
- **Coverage reporting**: Automatic upload to Codecov (optional)
- **Security checks**: Automated vulnerability scanning
- **Multi-Python support**: Ensures compatibility across Python versions

### Status Badges
Add these badges to your repository to show build status:
```markdown
![Tests](https://github.com/yourusername/aem-cli/workflows/Tests/badge.svg)
![CI](https://github.com/yourusername/aem-cli/workflows/CI/badge.svg)
```

## Dependencies

### Core Dependencies
- **click>=8.0** - Command-line interface framework

### Development Dependencies
- **pytest>=7.0** - Testing framework
- **pytest-cov>=4.0** - Test coverage reporting
- **black>=23.0** - Code formatting
- **flake8>=6.0** - Code linting
- **mypy>=1.0** - Static type checking

### Optional Dependencies
- **colorama>=0.4.6** - Cross-platform colored terminal text
- **rich>=13.0** - Rich text and beautiful formatting

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Make your changes
4. Add tests for new functionality
5. Run the test suite (`python -m pytest`)
6. Commit your changes (`git commit -m 'Add amazing feature'`)
7. Push to the branch (`git push origin feature/amazing-feature`)
8. Open a Pull Request

### Development Guidelines
- Follow PEP 8 style guidelines
- Add tests for new features
- Update documentation as needed
- Use type hints where appropriate

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For questions, issues, or contributions, please:
1. Check existing issues in the repository
2. Create a new issue with detailed information
3. Include steps to reproduce any bugs
4. Provide example files when relevant

## Changelog

### v0.1.0
- Initial release
- Content cleanup command with flexible property selection
- Support for default AEM properties
- Dry-run mode for safe testing
- Comprehensive test suite
