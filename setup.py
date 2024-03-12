# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()
repo_url = "https://github.com/lguibr/commitai"
setup(
    name="commitai",
    version="0.1.12",
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
        "Development Status :: 3 - Alpha",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
    ],
    python_requires=">=3.6",
    install_requires=[
        "langchain",
        "click",
        "langchain-community",
        "langchain-anthropic",
        "langchain-openai",
        "setuptools",
    ],
    entry_points={
        "console_scripts": [
            "commitai = commitai.cli:main",
        ],
    },
)
