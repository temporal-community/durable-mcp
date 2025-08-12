#!/usr/bin/env python3
"""
Runner script for the MCP client demo.
"""

import asyncio
from mcp_clients.simple_client import main

if __name__ == "__main__":
    asyncio.run(main()) 