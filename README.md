# CommitAi - Commit Message AI

[![CI](https://github.com/lguibr/commitai/workflows/CI/badge.svg)](https://github.com/lguibr/commitai/actions)
[![PyPI](https://img.shields.io/pypi/v/CommitAi.svg)](https://pypi.org/project/CommitAi/)
[![Python Version](https://img.shields.io/pypi/pyversions/CommitAi.svg)](https://pypi.org/project/CommitAi/)
[![License](https://img.shields.io/pypi/l/CommitAi.svg)](https://github.com/lguibr/CommitAi/blob/main/LICENSE)

commitai is a command-line tool that helps you generate informative and relevant commit messages for your Git repositories using AI language models like GPT-4 and Claude. It analyzes your staged changes, combines them with a high-level explanation provided by you, and creates a commit message based on this information. Additionally, it supports custom commit message templates. This not only saves you time and effort but also ensures a consistent and meaningful commit history.

## Features

- Automatically runs the repository's pre-commit hook (if it exists) before generating the commit message to avoid discarded commit costs.
- Generates informative and relevant commit messages based on staged changes and user-provided explanations.
- Supports custom commit message templates.
- Integrates with AI language models like GPT-4 and Claude for intelligent commit message generation.

## Prerequisites

- Python 3.x
- API keys for the desired language models (e.g., OpenAI API key for GPT-4, Anthropic API key for Claude)

## Installation

You can install commitai using pip:

pip install commitai

## Configuration

### Environment Variables

Before using commitai, you need to set the API key environment variables for the language models you want to use. For example:

export OPENAI_API_KEY="your_openai_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"

You can also set the `TEMPLATE_COMMIT` environment variable to define a global template for your commit messages:

export TEMPLATE_COMMIT="My global custom template: {message}"

### Template Configuration

#### Creating a Template for the Repository

You can create a custom template specific to the repository using the `create-template` command. This template will override the global template set in the `TEMPLATE_COMMIT` environment variable if present.

commitai create-template "My repository-specific template: {message}"

This command will create a hidden file inside the `.git` directory to store the template.

## Usage

### Generating Commit Messages

commitai generate "This is a high-level explanation of my commit"

- Use the `-a` or `--add` flag to stage all changes.
- Use the `-c` or `--commit` flag to automatically create the commit.
- Use the `-t` or `--template` flag for custom templates or utilize the `TEMPLATE_COMMIT` environment variable. If no template is provided, a default or global template will be used.
- Use the `-m` or `--model` flag to specify the language model to use (default: `gpt-4`).

## Contributing

We welcome contributions to the commitai project! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is released under the MIT License.
