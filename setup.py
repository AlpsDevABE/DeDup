#!/usr/bin/env python3
"""
Setup script for DeDup - Python Duplicate File Finder
"""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="dedup",
    version="0.1.0",
    author="DeDup Development Team",
    description="A Python duplicate file finder with GUI",
    long_description=long_description,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "License :: OSI Approved :: GNU General Public License v3 (GPLv3)",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.12",
    ],
    python_requires=">=3.12",
    install_requires=[
        "PyQt6>=6.5.0",
        "xxhash>=3.2.0",
    ],
    entry_points={
        "console_scripts": [
            "dedup=dedup.main:main",
        ],
    },
)