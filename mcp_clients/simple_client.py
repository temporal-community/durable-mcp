#!/usr/bin/env python3
"""
Simple MCP Client using fastmcp

This client demonstrates how to connect to MCP servers and interact with them.
"""

import asyncio
import os
import json
from typing import Dict, Any
from fastmcp import Client
from dotenv import load_dotenv
from litellm import acompletion


class SimpleMCPClient:
    """A simple MCP client that can connect to MCP servers."""
    
    def __init__(self, server_name: str, server_script: str):
        """
        Initialize the MCP client.
        
        Args:
            server_name: Name of the server for identification
            server_script: Path to the MCP server script (.py)
        """
        self.server_name = server_name
        self.server_script = server_script
        self.client = Client(self.server_script)
        self._entered = False
        
    async def connect(self):
        """Connect to the MCP server."""
        try:
            await self.client.__aenter__()
            self._entered = True
            print(f"✅ Connected to {self.server_name} server")
        except Exception as e:
            print(f"❌ Failed to connect to {self.server_name} server: {e}")
            raise
    
    async def list_tools(self):
        """List all available tools from the server."""
        try:
            tools = await self.client.list_tools()
            print(f"🔧 Available tools from {self.server_name}:")
            for tool in tools:
                name = tool.get("name") if isinstance(tool, dict) else getattr(tool, "name", str(tool))
                desc = tool.get("description") if isinstance(tool, dict) else getattr(tool, "description", "No description")
                print(f"  - {name}: {desc}")
            return tools
        except Exception as e:
            print(f"❌ Failed to list tools from {self.server_name}: {e}")
            return []
    
    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]):
        """Call a specific tool on the server."""
        try:
            result = await self.client.call_tool(tool_name, arguments)
            print(f"✅ Successfully called {tool_name} on {self.server_name}")
            return result
        except Exception as e:
            print(f"❌ Failed to call {tool_name} on {self.server_name}: {e}")
            raise
    
    async def get_weather(self, latitude: float, longitude: float):
        """Get weather forecast for a location."""
        return await self.call_tool("get_forecast", {"latitude": latitude, "longitude": longitude})
    
    async def get_alerts(self, state: str):
        """Get weather alerts for a US state."""
        return await self.call_tool("get_alerts", {"state": state})
    
    async def get_news(self):
        """Get newest HackerNews stories summary."""
        return await self.call_tool("get_latest_stories", {})
    
    async def disconnect(self):
        """Disconnect from the MCP server."""
        try:
            if self._entered:
                await self.client.__aexit__(None, None, None)
                self._entered = False
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
        "mcp_servers/weather.py"
    )
    
    try:
        # Connect to server
        await weather_client.connect()
        
        # List available tools
        await weather_client.list_tools()
        
        # Get weather for a location
        print("\n🌡️  Getting weather information...")
        weather_result = await weather_client.get_weather(37.7749, -122.4194)  # San Francisco coordinates
        print(f"Weather result: {weather_result}")
        
        # Get weather alerts
        print("\n⚠️  Getting weather alerts...")
        alerts_result = await weather_client.get_alerts("CA")
        print(f"Alerts result: {alerts_result}")
        
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
        "mcp_servers/hackernews.py"
    )
    
    try:
        # Connect to server
        await news_client.connect()
        
        # List available tools
        await news_client.list_tools()
        
        # Get news articles
        print("\n📰 Getting news articles...")
        news_result = await news_client.get_news()
        print(f"News result: {news_result}")
        
    except Exception as e:
        print(f"Demo failed: {e}")
    finally:
        await news_client.disconnect()


def serialize_tool(tool: Any) -> dict[str, Any]:
    """Serialize tool metadata into a consistent shape for prompting."""
    if isinstance(tool, dict):
        return {
            "name": tool.get("name"),
            "description": tool.get("description"),
            "input_schema": tool.get("input_schema"),
        }
    return {
        "name": getattr(tool, "name", str(tool)),
        "description": getattr(tool, "description", ""),
        "input_schema": getattr(tool, "input_schema", None),
    }


def extract_json(text: str) -> str | None:
    """Attempt to extract a JSON object from model output."""
    text = text.strip()
    if text.startswith("```"):
        lines = [ln for ln in text.splitlines() if not ln.strip().startswith("```")]
        text = "\n".join(lines).strip()
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
        return text[start:end]
    except ValueError:
        return None


async def setup_tool_selection() -> tuple[str, dict[str, SimpleMCPClient], list[SimpleMCPClient]]:
    """Connect to MCP servers, collect tools, and craft a system prompt.

    Returns a tuple of (system_prompt, tool_name_to_client, clients).
    """
    weather_client = SimpleMCPClient("Weather", "mcp_servers/weather.py")
    news_client = SimpleMCPClient("HackerNews", "mcp_servers/hackernews.py")
    clients: list[SimpleMCPClient] = [weather_client, news_client]

    # Connect and gather tools from both servers
    await weather_client.connect()
    await news_client.connect()
    weather_tools = await weather_client.list_tools()
    news_tools = await news_client.list_tools()

    # Build mapping from tool name to the appropriate client and shape tool metadata
    tool_name_to_client: dict[str, SimpleMCPClient] = {}
    combined_tools: list[dict[str, Any]] = []

    for t in weather_tools:
        shaped = serialize_tool(t)
        if shaped.get("name"):
            tool_name_to_client[shaped["name"]] = weather_client
            combined_tools.append(shaped)
    for t in news_tools:
        shaped = serialize_tool(t)
        if shaped.get("name"):
            tool_name_to_client[shaped["name"]] = news_client
            combined_tools.append(shaped)

    # Craft system prompt with available tools
    tool_lines: list[str] = []
    for t in combined_tools:
        schema_str = json.dumps(t.get("input_schema"), indent=2) if t.get("input_schema") else "{}"
        tool_lines.append(
            f"- name: {t.get('name')}\n  description: {t.get('description')}\n  input_schema: {schema_str}"
        )
    tools_block = "\n".join(tool_lines) if tool_lines else "(no tools available)"

    system_prompt = (
        "You are a tool-selection agent. Given the user's request and the available MCP tools, "
        "decide whether a tool should be invoked. If a tool is appropriate, reply ONLY with a JSON object "
        "with the following exact structure (no extra text, no code fences):\n\n"
        "{\n"
        "  \"tool_call\": {\n"
        "    \"tool_name\": \"<tool_name>\",\n"
        "    \"parameters\": { }\n"
        "  }\n"
        "}\n\n"
        "Parameters must conform to the tool's input_schema. If no tool should be invoked, respond with a "
        "helpful natural-language answer and do NOT return JSON.\n\n"
        "Available tools (name, description, input_schema):\n" + tools_block
    )

    return system_prompt, tool_name_to_client, clients


async def handle_model_output(content: str, tool_name_to_client: dict[str, SimpleMCPClient]) -> None:
    """Process the model output: parse tool call JSON and invoke the tool or print response."""
    json_text = extract_json(content)
    tool_call = None
    if json_text:
        try:
            parsed = json.loads(json_text)
            tool_call = parsed.get("tool_call") if isinstance(parsed, dict) else None
        except Exception:
            tool_call = None

    if tool_call and isinstance(tool_call, dict):
        tool_name = tool_call.get("tool_name")
        parameters = tool_call.get("parameters") or {}
        if not isinstance(parameters, dict):
            parameters = {}
        client_for_tool = tool_name_to_client.get(tool_name)
        if not client_for_tool:
            print(f"⚠️ Chosen tool '{tool_name}' not found. Model output below:\n{content}")
            return
        print(f"🛠️ Invoking tool '{tool_name}' with parameters: {parameters}")
        try:
            result = await client_for_tool.call_tool(tool_name, parameters)
            print("\n🔎 Tool result:")
            print(result)
        except Exception as e:
            print(f"❌ Tool invocation failed: {e}")
    else:
        print("\n🧠 LLM response:")
        print(content)


async def prompt_user_and_invoke_llm() -> None:
    """Prompt the user, let the LLM decide which MCP tool to call (if any), and print the result."""
    # Module-level helpers are used for setup and post-processing
    # Prepare environment and tool selection setup
    clients: list[SimpleMCPClient] = []

    try:
        load_dotenv()
        user_prompt = input("\n💬 Enter a prompt for the LLM (OpenAI via LiteLLM): ")
        if not user_prompt or not user_prompt.strip():
            print("No input provided. Skipping LLM call.")
            return

        system_prompt, tool_name_to_client, clients = await setup_tool_selection()

        model_name = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        print(f"🤖 Querying {model_name} for tool selection...")
        response = await acompletion(
            model=model_name,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=800,
        )
        content = response["choices"][0]["message"].get("content", "").strip()

        await handle_model_output(content, tool_name_to_client)

    except Exception as e:
        print(f"❌ LLM invocation failed: {e}")
    finally:
        # Always disconnect clients that were initialized
        for client in clients:
            try:
                await client.disconnect()
            except Exception:
                pass


async def main():
    """Main function to run the MCP client demos."""
    print("🚀 Starting MCP Client Demos")
    print("=" * 50)
    
    # Run weather demo
    # await demo_weather_client()
    
    # Run news demo
    # await demo_news_client()
    
    # After demos, prompt the user and invoke an LLM via LiteLLM/OpenAI
    await prompt_user_and_invoke_llm()

    print("\n✅ All demos completed!")


if __name__ == "__main__":
    asyncio.run(main()) 