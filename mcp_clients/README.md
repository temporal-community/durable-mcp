# MCP Clients

This directory contains MCP (Model Context Protocol) clients built using `fastmcp` for connecting to and interacting with MCP servers.

## Overview

The MCP clients provide a simple and advanced interface for connecting to MCP servers and calling their tools. They demonstrate best practices for:

- Connection management
- Error handling
- Tool discovery and invocation
- Multiple client management

## Files

- `simple_client.py` - Basic MCP client with straightforward usage
- `advanced_client.py` - Advanced client with better error handling, connection management, and context managers
- `__init__.py` - Package initialization

## Quick Start

### Simple Client

```python
import asyncio
from mcp_clients.simple_client import SimpleMCPClient

async def main():
    # Create a client for the weather server
    client = SimpleMCPClient("Weather", ["python", "-m", "mcp_servers.weather"])
    
    try:
        # Connect to the server
        await client.connect()
        
        # List available tools
        tools = await client.list_tools()
        print(f"Available tools: {tools}")
        
        # Call a tool
        result = await client.call_tool("get_weather", {"location": "San Francisco"})
        print(f"Weather result: {result}")
        
    finally:
        # Disconnect
        await client.disconnect()

asyncio.run(main())
```

### Advanced Client

```python
import asyncio
from mcp_clients.advanced_client import AdvancedMCPClient, MCPClientManager

async def main():
    # Using the advanced client with context manager
    client = AdvancedMCPClient("Weather", ["python", "-m", "mcp_servers.weather"])
    
    async with client.connection() as connected_client:
        # Automatically connected and will disconnect when done
        tools = await connected_client.list_tools()
        result = await connected_client.call_tool("get_weather", {"location": "New York"})
        print(f"Result: {result}")

    # Using the client manager for multiple servers
    manager = MCPClientManager()
    manager.add_client("Weather", ["python", "-m", "mcp_servers.weather"])
    manager.add_client("News", ["python", "-m", "mcp_servers.hackernews"])
    
    await manager.connect_all()
    # ... use the clients
    await manager.disconnect_all()

asyncio.run(main())
```

## Running the Demos

### Simple Demo

```bash
python run_mcp_client.py
```

### Advanced Demo

```bash
python -m mcp_clients.advanced_client
```

## Features

### Simple Client
- Basic connection management
- Tool listing and invocation
- Simple error handling
- Pre-built methods for common operations

### Advanced Client
- Connection timeout handling
- Context manager support
- Multiple client management
- Comprehensive error handling and logging
- Connection state tracking
- Server information retrieval

## Dependencies

The clients require the following dependencies (already included in `pyproject.toml`):

- `fastmcp>=0.1.0` - The MCP client library
- `asyncio` - For async/await support
- `logging` - For advanced logging (advanced client only)

## Error Handling

Both clients include comprehensive error handling:

- Connection failures
- Tool invocation errors
- Timeout handling
- Graceful disconnection

## Best Practices

1. **Always disconnect**: Use try/finally blocks or context managers to ensure proper cleanup
2. **Handle errors**: Check connection status before making tool calls
3. **Use timeouts**: Set appropriate timeouts for long-running operations
4. **Log operations**: Use the logging features in the advanced client for debugging

## Integration with Existing Servers

The clients are designed to work with the existing MCP servers in this project:

- Weather server (`mcp_servers.weather`)
- HackerNews server (`mcp_servers.hackernews`)

You can easily extend them to work with other MCP servers by updating the server commands and tool names. 