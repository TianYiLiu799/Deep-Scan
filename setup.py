#!/usr/bin/env python
"""Setup script for Deep-Scan project."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setup(
    name="deep-scan",
    version="1.0.0",
    author="Your Name",
    author_email="your.email@example.com",
    description="A professional web scraping framework",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/yourusername/deep-scan",
    packages=find_packages(),
    classifiers=[
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Internet :: WWW/HTTP :: Dynamic Content",
        "Topic :: Software Development :: Libraries :: Python Modules",
    ],
    python_requires=">=3.8",
    install_requires=[
        "requests>=2.31.0",
        "beautifulsoup4>=4.12.2",
        "lxml>=4.9.3",
        "pandas>=2.1.3",
        "matplotlib>=3.8.0",
        "pyyaml>=6.0.1",
        "python-dotenv>=1.0.0",
    ],
    extras_require={
        "dev": [
            "pytest>=7.4.3",
            "pytest-cov>=4.1.0",
            "black>=23.12.0",
            "flake8>=6.1.0",
        ],
        "browser": [
            "playwright>=1.48.0",
            "playwright-stealth>=1.0.6",
        ],
    },
)
