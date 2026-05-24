"""Shim so `pip install -e .` works on older pip too; all metadata is in
pyproject.toml. (The .app bundle is built with setup_py2app.py, not this file.)"""

from setuptools import setup

setup()
