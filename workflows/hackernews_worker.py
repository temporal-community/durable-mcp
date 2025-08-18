# hackernews_worker.py

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.workflows import GetLatestStories
from workflows.agent_workflows import AmbientNewsAgent
from workflows.activities import make_hackernews_request, fetch_url_content, render_url_content
from workflows.agent_activities import call_mcp_tool, convert_json_to_markdown
from workflows.pdf_generation_activity import generate_pdf

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="hackernews-task-queue",
        workflows=[GetLatestStories, AmbientNewsAgent],
        activities=[make_hackernews_request, fetch_url_content, render_url_content, call_mcp_tool, generate_pdf, convert_json_to_markdown],
    )
    print("Hacker News worker started. Listening for workflows...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 