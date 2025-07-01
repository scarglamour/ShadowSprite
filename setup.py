"""
setup.py

Setup script for installing ShadowSprite as a Python package.

This file uses setuptools to define package metadata and discover
all sub-packages. Install in editable mode during development:

    pip install -e .
"""
from setuptools import setup, find_packages

setup(
  name="shadowsprite",
  version="0.1.0",
  packages=find_packages(),
  install_requires=[
        "anyio>=4.9.0",
        "certifi>=2025.4.26",
        "discord.py>=2.0",
        "h11>=0.16.0",
        "httpcore>=1.0.9",
        "httpx>=0.28.1",
        "idna>=3.10",
        "mysql-connector-python>=9.3.0",
        "python-dotenv>=1.1.0",
        "python-telegram-bot>=22.0",
        "sniffio>=1.3.1",
        "typing_extensions>=4.13.2",
  ],
  entry_points={
    "console_scripts": [
      # this creates `venv/bin/shadowsprite`
      "shadowsprite = shadowsprite.run_all_bots:main",
    ],
  },
)