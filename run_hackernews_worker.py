#!/usr/bin/env python3
"""
Script to run the hackernews worker from the project root.
"""

import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from workflows.hackernews_worker import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main()) 