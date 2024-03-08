from setuptools import setup, find_packages

setup(
    name='comai',
    version='0.1.0',
    packages=find_packages(),
    install_requires=[
        'langchain',
        'openai',
        'anthropic',
        'click',
        'langchain-community',
        'langchain-anthropic',
        'langchain-openai',
    ],
    entry_points={
        'console_scripts': [
            'comai = comai.cli:main',
        ],
    },
)

