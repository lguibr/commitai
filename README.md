# CommitAi - Your AI-Powered Commit Assistant

[![CI](https://github.com/lguibr/commitai/workflows/CI/badge.svg)](https://github.com/lguibr/commitai/actions)
[![codecov](https://codecov.io/gh/lguibr/commitai/graph/badge.svg?token=MXZKCXO6LA)](https://codecov.io/gh/lguibr/commitai)
[![PyPI](https://img.shields.io/pypi/v/CommitAi.svg)](https://pypi.org/project/CommitAi/)
[![Python Version](https://img.shields.io/pypi/pyversions/CommitAi.svg)](https://pypi.org/project/CommitAi/)
[![License](https://img.shields.io/pypi/l/CommitAi.svg)](https://github.com/lguibr/CommitAi/blob/main/LICENSE)

**CommitAi** simplifies the Git commit message creation process by leveraging AI technologies, including GPT-4 and Claude. Designed for developers who value clarity and precision in commit histories, **CommitAi** offers a streamlined workflow that transforms your staged changes and high-level explanations into informative commit messages. Enhance your project documentation and streamline your development process with commit messages that truly reflect your changes.

## Features

- **Intelligent Commit Generation**: Leverages state-of-the-art AI models to generate meaningful commit messages from your changes.
- **Pre-commit Checks**: Automatically runs configured pre-commit hooks to ensure quality and consistency before generating messages.
- **Template Support**: Utilizes both global and repository-specific commit message templates to maintain a consistent style across your projects.
- **AI Model Integration**: Supports multiple AI models, including GPT-4 by OpenAI and Claude by Anthropic, ensuring versatility in natural language processing capabilities.

## Getting Started

### Prerequisites

- Python 3.6 or later
- API keys for GPT-4 and Claude, as required

### Installation

Install **CommitAi** directly from PyPI:

```bash
pip install commitai
```

### Configuration

#### API Keys

Set the necessary API keys as environment variables:

```bash
export OPENAI_API_KEY="your_openai_api_key"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

#### Commit Templates

Set a global commit template environment variable:

```bash
export TEMPLATE_COMMIT="My global custom template: {message}"
```

Or, create a repository-specific template using:

```bash
commitai-create-template "My repository-specific template: {message}"
```

This creates a hidden template file within the `.git` directory of your repository.

## Usage

To generate a commit message, provide a high-level explanation of your changes:

```bash
commitai "This is a high-level explanation of my commit"
```

#### Options

- `-a, --add`: Stage all changes before generating the commit message.
- `-c, --commit`: Automatically create the commit using the generated message.
- `-t, --template`: Specify a commit template. Defaults to the global template if available.
- `-m, --model`: Choose the AI model (`gpt-4` by default).

### Additional Commands

- `commitai-create-template`: Set a custom template specific to your repository.

## Contributing

Contributions are welcome! Feel free to fork the repository, push your changes to a branch, and open a pull request. For bugs, questions, or feature requests, please open an issue through the GitHub issue tracker.

## License

**CommitAi** is open-source software licensed under the MIT License. See the [LICENSE](https://github.com/lguibr/CommitAi/blob/main/LICENSE) file for more details.
