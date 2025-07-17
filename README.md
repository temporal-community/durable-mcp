# durable-mcp

This repository contains an implementation of a very simple MCP server - the one that is included in the [MCP Server Developers Quickstart](https://modelcontextprotocol.io/quickstart/server). 

The main branch has an implementation that extends the initial sample with durability, using Temporal. The original implementation can be found in the nondurable branch. Each branch has its own 
version of this README, guiding you through the demonstration.

# Demo 

## Overview

We will use Claude Desktop as the UX for the application; this means that the MCP Client is that which in included therein.

## Prerequisites

In order to run the demo that can be found in this recording (link coming soon) you must have the following:

- Claude Desktop
- Python with uv installed
- A local Temporal server
- pfctl - simple firewall for Mac (PRs for other OSes welcome). We will use this to simulate network outages. You will need to be able to run this with `sudo`

## Setting up

Run a local Temporal service
```
temporal server start-dev
```

Configure Claude Desktop with MCP Server
This is done by placing the `clade_desktop_config.json` file into the `~/Library/Application Support/Claude` directory, inserting the appropriate path.
Restart Claude Desktop if already running. Verify that the MCP server is available:

## Running the MCP server

You can now ask Claude for the weather for a particular location. For example: `What is the weather in Honolulu, HI?`

Claude will ask you for confirmation before it invokes the weather MCP server.

The `get_forecast` tool makes two downstream HTTP requests to National Weather Service (NWS) API - one taking a lat and long and returning a "gridpoint" (a region that has a weather forcast associated with it), and a second that retrieves the forcast for that gridpoint. After tool execution, Claude Desktop will send the result over to the LLM (with other context) for human formating, and then returns that result to the user.

You can see these and other MCP-related actions in the `mcp_server.log`.

Now, play with this a bit so see how it holds up against some of the challenges that plague distributed systems.

## Simulating a network outage

The implementation of the `get_forecast` tool includes a 10 second sleep between the two HTTP requests. Experiment with the following:
- Run it with no firewall rules
- Add the firewall rules and enable the firewall
- Disable the firewall, accept the MCP tool execution and then enable the firewall within 10 seconds. Disable the firewall on the 11th second and see what happens.


### Using `pfctl` on a Mac

We will simulate a network outage by adding firewall rules using `pfctl`. This repository includes a `pf.rules` file that has URLs I am currently seeing for the NWS API. You can check what these are right now with the following command:
```
dig +short api.weather.gov
```

The following commands are used to set and delete the rules, and enable and disable the firewall.

To set rules
```
sudo pfctl -f pf.rules
```

To remove the rules. WARNING: this will delete all rules - you are using pfctl for real, use with caution.
```
sudo pfctl -F all
```

To see the current list of rules:
```
sudo pfctl -s rules
```

To enable the firewall
```
sudo pfctl -e
```

To enable the firewall
```
sudo pfctl -d
```
