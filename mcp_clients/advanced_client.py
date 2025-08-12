#!/usr/bin/env python3
"""
Advanced MCP Client using fastmcp

This client demonstrates more advanced patterns for working with MCP servers.
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager
from mcp.client import Client as FastMCPClient


# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedMCPClient:
    """An advanced MCP client with better error handling and connection management."""
    
    def __init__(self, server_name: str, server_command: List[str]):
        """
        Initialize the advanced MCP client.
        
        Args:
            server_name: Name of the server for identification
            server_command: Command to start the MCP server
        """
        self.server_name = server_name
        self.server_command = server_command
        self.client = FastMCPClient()
        self._connected = False
        
    @property
    def is_connected(self) -> bool:
        """Check if the client is connected."""
        return self._connected
    
    async def connect(self, timeout: float = 30.0) -> bool:
        """
        Connect to the MCP server with timeout.
        
        Args:
            timeout: Connection timeout in seconds
            
        Returns:
            True if connection successful, False otherwise
        """
        try:
            await asyncio.wait_for(
                self.client.connect(self.server_command),
                timeout=timeout
            )
            self._connected = True
            logger.info(f"✅ Connected to {self.server_name} server")
            return True
        except asyncio.TimeoutError:
            logger.error(f"⏰ Connection to {self.server_name} timed out after {timeout}s")
            return False
        except Exception as e:
            logger.error(f"❌ Failed to connect to {self.server_name} server: {e}")
            return False
    
    async def disconnect(self) -> bool:
        """
        Disconnect from the MCP server.
        
        Returns:
            True if disconnection successful, False otherwise
        """
        if not self._connected:
            return True
            
        try:
            await self.client.disconnect()
            self._connected = False
            logger.info(f"🔌 Disconnected from {self.server_name} server")
            return True
        except Exception as e:
            logger.error(f"❌ Error disconnecting from {self.server_name}: {e}")
            return False
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all available tools from the server.
        
        Returns:
            List of available tools
        """
        if not self._connected:
            raise RuntimeError(f"Not connected to {self.server_name} server")
            
        try:
            tools = await self.client.list_tools()
            logger.info(f"🔧 Found {len(tools)} tools from {self.server_name}")
            return tools
        except Exception as e:
            logger.error(f"❌ Failed to list tools from {self.server_name}: {e}")
            raise
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Call a specific tool on the server.
        
        Args:
            tool_name: Name of the tool to call
            arguments: Arguments to pass to the tool
            
        Returns:
            Tool execution result
        """
        if not self._connected:
            raise RuntimeError(f"Not connected to {self.server_name} server")
            
        try:
            result = await self.client.call_tool(tool_name, arguments)
            logger.info(f"✅ Successfully called {tool_name} on {self.server_name}")
            return result
        except Exception as e:
            logger.error(f"❌ Failed to call {tool_name} on {self.server_name}: {e}")
            raise
    
    async def get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        try:
            # This would depend on the specific MCP server implementation
            # For now, we'll return basic info
            return {
                "name": self.server_name,
                "connected": self._connected,
                "command": " ".join(self.server_command)
            }
        except Exception as e:
            logger.error(f"❌ Failed to get server info: {e}")
            return {}
    
    @asynccontextmanager
    async def connection(self):
        """Context manager for automatic connection/disconnection."""
        try:
            if await self.connect():
                yield self
            else:
                raise RuntimeError(f"Failed to connect to {self.server_name}")
        finally:
            await self.disconnect()


class MCPClientManager:
    """Manager for multiple MCP clients."""
    
    def __init__(self):
        self.clients: Dict[str, AdvancedMCPClient] = {}
    
    def add_client(self, name: str, server_command: List[str]) -> AdvancedMCPClient:
        """Add a new MCP client."""
        client = AdvancedMCPClient(name, server_command)
        self.clients[name] = client
        return client
    
    async def connect_all(self) -> Dict[str, bool]:
        """Connect to all registered clients."""
        results = {}
        for name, client in self.clients.items():
            results[name] = await client.connect()
        return results
    
    async def disconnect_all(self) -> Dict[str, bool]:
        """Disconnect from all registered clients."""
        results = {}
        for name, client in self.clients.items():
            results[name] = await client.disconnect()
        return results
    
    def get_client(self, name: str) -> Optional[AdvancedMCPClient]:
        """Get a specific client by name."""
        return self.clients.get(name)
    
    async def call_tool_on_all(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Call a tool on all connected clients."""
        results = {}
        for name, client in self.clients.items():
            if client.is_connected:
                try:
                    results[name] = await client.call_tool(tool_name, arguments)
                except Exception as e:
                    results[name] = {"error": str(e)}
            else:
                results[name] = {"error": "Not connected"}
        return results


async def demo_advanced_client():
    """Demonstrate the advanced MCP client features."""
    print("🚀 Advanced MCP Client Demo")
    print("=" * 50)
    
    # Create client manager
    manager = MCPClientManager()
    
    # Add clients
    weather_client = manager.add_client("Weather", ["python", "mcp_servers/weather.py"])
    news_client = manager.add_client("HackerNews", ["python", "mcp_servers/hackernews.py"])
    
    try:
        # Connect to all clients
        print("🔌 Connecting to all clients...")
        connection_results = await manager.connect_all()
        print(f"Connection results: {connection_results}")
        
        # Get server info for all clients
        print("\n📊 Server Information:")
        for name, client in manager.clients.items():
            info = await client.get_server_info()
            print(f"  {name}: {json.dumps(info, indent=2)}")
        
        # List tools from weather client
        print("\n🔧 Weather Server Tools:")
        weather_tools = await weather_client.list_tools()
        for tool in weather_tools:
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        
        # List tools from news client
        print("\n🔧 News Server Tools:")
        news_tools = await news_client.list_tools()
        for tool in news_tools:
            print(f"  - {tool['name']}: {tool.get('description', 'No description')}")
        
        # Test weather functionality
        print("\n🌤️  Testing Weather Functionality:")
        try:
            weather_result = await weather_client.call_tool("get_forecast", {"latitude": 40.7128, "longitude": -74.0060})  # New York
            print(f"Weather result: {json.dumps(weather_result, indent=2)}")
        except Exception as e:
            print(f"Weather test failed: {e}")
        
        # Test news functionality
        print("\n📰 Testing News Functionality:")
        try:
            news_result = await news_client.call_tool("get_news", {"limit": 2})
            print(f"News result: {json.dumps(news_result, indent=2)}")
        except Exception as e:
            print(f"News test failed: {e}")
        
    except Exception as e:
        print(f"Demo failed: {e}")
    finally:
        # Disconnect from all clients
        print("\n🔌 Disconnecting from all clients...")
        disconnect_results = await manager.disconnect_all()
        print(f"Disconnect results: {disconnect_results}")


async def demo_context_manager():
    """Demonstrate using the context manager pattern."""
    print("\n🔄 Context Manager Demo")
    print("=" * 30)
    
    weather_client = AdvancedMCPClient("Weather", ["python", "mcp_servers/weather.py"])
    
    async with weather_client.connection() as client:
        print("✅ Connected via context manager")
        
        # List tools
        tools = await client.list_tools()
        print(f"Found {len(tools)} tools")
        
        # Test a tool call
        try:
            result = await client.call_tool("get_forecast", {"latitude": 51.5074, "longitude": -0.1278})  # London
            print(f"Weather result: {json.dumps(result, indent=2)}")
        except Exception as e:
            print(f"Tool call failed: {e}")
    
    print("✅ Automatically disconnected via context manager")


async def main():
    """Main function to run the advanced MCP client demos."""
    print("🚀 Starting Advanced MCP Client Demos")
    print("=" * 60)
    
    # Run advanced client demo
    await demo_advanced_client()
    
    # Run context manager demo
    await demo_context_manager()
    
    print("\n✅ All advanced demos completed!")


if __name__ == "__main__":
    asyncio.run(main()) 