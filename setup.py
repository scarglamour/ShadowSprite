"""
setup.py

Setup script for installing ShadowDaemon as a Python package.

This file uses setuptools to define package metadata and discover
all sub-packages. Install in editable mode during development:

    pip install -e .
"""
from setuptools import setup, find_packages

setup(
  name="shadowdaemon",
  version="0.1.0",
  packages=find_packages(),
  install_requires=[
        "python-telegram-bot>=20.0",
        "discord.py>=2.0",
        "mysql-connector-python>=8.0",
  ],
  entry_points={
    "console_scripts": [
      # this creates `venv/bin/shadowdaemon`
      "shadowdaemon = shadowdaemon.run_all_bots:main",
    ],
  },
)