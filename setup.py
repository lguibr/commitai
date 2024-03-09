# -*- coding: utf-8 -*-
from setuptools import find_packages, setup

setup(
    name="comai",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "langchain",
        "openai",
        "anthropic",
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
