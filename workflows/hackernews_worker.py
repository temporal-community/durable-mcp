# hackernews_worker.py

import asyncio
from temporalio.client import Client
from temporalio.worker import Worker

from workflows.workflows import GetLatestStories
from workflows.activities import make_hackernews_request, fetch_url_content, render_url_content

async def main():
    client = await Client.connect("localhost:7233")

    worker = Worker(
        client,
        task_queue="hackernews-task-queue",
        workflows=[GetLatestStories],
        activities=[make_hackernews_request, fetch_url_content, render_url_content],
    )
    print("Hacker News worker started. Listening for workflows...")
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main()) 