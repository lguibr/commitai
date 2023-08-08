# Comai - Commit Message AI

Comai is a command-line tool that helps you generate informative and relevant commit messages for your Git repositories using GPT-4 by OpenAI. It analyzes your staged changes, combines it with a high-level explanation provided by you, and creates a commit message based on this information. Additionally, it supports custom commit message templates and a back command to reset to previous commits. This not only saves you time and effort but also ensures a consistent and meaningful commit history.

![ScreenShoot](comai.gif)

# Prerequisites

- Go 1.20 or later
- An OpenAI API key (get one at https://beta.openai.com/signup/)

## Installation

1. Clone the repository:

```bash
git clone https://github.com/yourusername/comai.git

```

2. Change to the project directory:

```bash
cd comai
```

3. Run the installation script:

```bash
chmod +x install.sh && ./install.sh
```

The install.sh script will build and install the comai binary to /usr/local/bin. If prompted for your password, enter it to grant sudo access.

# Configuration

## Environment Variables

Before using Comai, you need to set the **OPENAI_API_KEY** and optionally the **TEMPLATE_COMMIT** environment variables. The TEMPLATE_COMMIT variable allows you to define a global template for your commit messages.

```bash
export OPENAI_API_KEY="your_api_key"
export TEMPLATE_COMMIT="My global custom template: {message}"
```

## Template Configuration

### Creating a Template for the Repository

You can create a custom template specific to the repository using the `create-template` command. This template will override the global template set in the TEMPLATE_COMMIT environment variable if present.

```bash
comai create-template "My repository-specific template: {message}"
```

This command will create a hidden file inside the `.git` directory to store the template.

## Usage

### Generating Commit Messages

```bash
comai "This is a high level explanation of my commit"
```

- Use the -a or --add flag to stage all changes.
- Use the -c or --commit flag to automatically create the commit.
- Use the -t or --template flag for custom templates or utilize the TEMPLATE_COMMIT environment variable. If no template is provided, a default or global template will be used.

### Resetting Commits

Use the `back` command to reset to previous commits. This is equivalent to `git reset HEAD~n`, where `n` is the number of commits to reset.

```bash
comai back 1 # Resets one commit back
comai back 2 # Resets two commits back
```

## Contributing

We welcome contributions to the Comai project! Please feel free to submit issues, feature requests, or pull requests.

## License

This project is released under the MIT License.
