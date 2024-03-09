# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

with open("README.md", "r") as fh:
    long_description = fh.read()

setup(
    name="comai",
    version="0.1.0",
    packages=find_packages(),
    long_description=long_description,
    long_description_content_type="text/markdown",
    install_requires=[
        "langchain",
        "click",
        "langchain-community",
        "langchain-anthropic",
        "langchain-openai",
    ],
    entry_points={
        "console_scripts": [
            "comai = comai.cli:main",
        ],
    },
)
