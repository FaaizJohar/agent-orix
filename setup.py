"""
Setup script for agent-orix / cavrix_cie.
"""

from setuptools import setup, find_packages

setup(
    name="agent-orix",
    version="1.0.0",
    description="Agent Orix: Interactive Terminal AI & Multi-Action Engine",
    author="Cavrix Team",
    packages=find_packages(),
    python_requires=">=3.10",
    install_requires=[
        "pydantic>=2.0.0",
        "fastapi>=0.110.0",
        "uvicorn>=0.28.0",
        "httpx>=0.27.0",
        "psutil>=5.9.0",
        "click>=8.0.0",
        "rich>=13.0.0",
    ],
    entry_points={
        "console_scripts": [
            "orix=cie.cli.main:cli",
            "agent-orix=cie.cli.main:cli",
        ],
    },
)
