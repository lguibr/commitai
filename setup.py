# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

__version__ = "0.2.0"  # Updated version

with open("README.md", "r") as fh:
    long_description = fh.read()
repo_url = "https://github.com/lguibr/commitai"
setup(
    name="commitai",
    version=__version__,
    author="Luis Guilherme",
    author_email="lgpelin92@gmail.com",
    packages=find_packages(),
    description="Commitai helps you generate git commit messages using AI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url=repo_url,
    project_urls={
        "Bug Tracker": f"{repo_url}/issues",
        "Documentation": f"{repo_url}/blob/main/README.md",
        "Source Code": repo_url,
    },
    classifiers=[
        "Development Status :: 4 - Beta",  # Updated status
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.8",  # Updated Python requirement
    install_requires=[
        "click>=8.0,<9.0",  # Specify a compatible range
        "langchain>=0.1.0,<0.3.0",  # Use recent Langchain range
        "langchain-community>=0.0.20,<0.2.0",
        "langchain-anthropic>=0.1.0,<0.3.0",
        "langchain-openai>=0.1.0,<0.3.0",
        "langchain-google-genai~=0.0.9",  # Use compatible range
        "setuptools", # Keep setuptools for compatibility
    ],
    entry_points={
        "console_scripts": [
            "commitai = commitai.cli:commitai",
            "commitai-create-template = commitai.cli:commitai_create_template",
        ],
    },
)
