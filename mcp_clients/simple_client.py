#!/usr/bin/env python3
"""
Simple MCP Client using fastmcp

This client demonstrates how to connect to MCP servers and interact with them.
"""

import asyncio
import json
from typing import Dict, Any, List
from mcp.client import Client as FastMCPClient


class SimpleMCPClient:
    """A simple MCP client that can connect to MCP servers."""
    
    def __init__(self, server_name: str, server_command: List[str]):
        """
        Initialize the MCP client.
        
        Args:
            server_name: Name of the server for identification
            server_command: Command to start the MCP server
        """
        self.server_name = server_name
        self.server_command = server_command
        self.client = FastMCPClient()
        
    async def connect(self):
        """Connect to the MCP server."""
        try:
            await self.client.connect(self.server_command)
            print(f"✅ Connected to {self.server_name} server")
        except Exception as e:
            print(f"❌ Failed to connect to {self.server_name} server: {e}")
            raise
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all available tools from the server."""
        try:
            tools = await self.client.list_tools()
            print(f"🔧 Available tools from {self.server_name}:")
            for tool in tools:
                print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
            return tools
        except Exception as e:
            print(f"❌ Failed to list tools from {self.server_name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """Call a specific tool on the server."""
        try:
            result = await self.client.call_tool(tool_name, arguments)
            print(f"✅ Successfully called {tool_name} on {self.server_name}")
            return result
        except Exception as e:
            print(f"❌ Failed to call {tool_name} on {self.server_name}: {e}")
            raise
    
    async def get_weather(self, latitude: float, longitude: float) -> Dict[str, Any]:
        """Get weather forecast for a location."""
        return await self.call_tool("get_forecast", {"latitude": latitude, "longitude": longitude})
    
    async def get_alerts(self, state: str) -> Dict[str, Any]:
        """Get weather alerts for a US state."""
        return await self.call_tool("get_alerts", {"state": state})
    
    async def get_news(self, limit: int = 5) -> Dict[str, Any]:
        """Get news articles."""
        return await self.call_tool("get_news", {"limit": limit})
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            await self.client.disconnect()
            print(f"🔌 Disconnected from {self.server_name} server")
        except Exception as e:
            print(f"❌ Error disconnecting from {self.server_name}: {e}")


async def demo_weather_client():
    """Demonstrate the weather MCP client."""
    print("🌤️  Weather MCP Client Demo")
    print("=" * 40)
    
    # Create weather client
    weather_client = SimpleMCPClient(
        "Weather",
        ["python", "mcp_servers/weather.py"]
    )
    
    try:
        # Connect to server
        await weather_client.connect()
        
        # List available tools
        await weather_client.list_tools()
        
        # Get weather for a location
        print("\n🌡️  Getting weather information...")
        weather_result = await weather_client.get_weather(37.7749, -122.4194)  # San Francisco coordinates
        print(f"Weather result: {json.dumps(weather_result, indent=2)}")
        
        # Get weather alerts
        print("\n⚠️  Getting weather alerts...")
        alerts_result = await weather_client.get_alerts("CA")
        print(f"Alerts result: {json.dumps(alerts_result, indent=2)}")
        
    except Exception as e:
        print(f"Demo failed: {e}")
    finally:
        await weather_client.disconnect()


async def demo_news_client():
    """Demonstrate the HackerNews MCP client."""
    print("\n📰 HackerNews MCP Client Demo")
    print("=" * 40)
    
    # Create news client
    news_client = SimpleMCPClient(
        "HackerNews",
        ["python", "mcp_servers/hackernews.py"]
    )
    
    try:
        # Connect to server
        await news_client.connect()
        
        # List available tools
        await news_client.list_tools()
        
        # Get news articles
        print("\n📰 Getting news articles...")
        news_result = await news_client.get_news(limit=3)
        print(f"News result: {json.dumps(news_result, indent=2)}")
        
    except Exception as e:
        print(f"Demo failed: {e}")
    finally:
        await news_client.disconnect()


async def main():
    """Main function to run the MCP client demos."""
    print("🚀 Starting MCP Client Demos")
    print("=" * 50)
    
    # Run weather demo
    await demo_weather_client()
    
    # Run news demo
    await demo_news_client()
    
    print("\n✅ All demos completed!")


if __name__ == "__main__":
    asyncio.run(main()) 