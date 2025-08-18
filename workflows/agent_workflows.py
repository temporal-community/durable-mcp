from datetime import timedelta
from temporalio import workflow
from temporalio.common import RetryPolicy
from shared.models import PDFInput, MDInput

# Reuse a retry policy consistent with other workflows
retry_policy = RetryPolicy(
    maximum_attempts=0,  # Infinite retries
    initial_interval=timedelta(seconds=2),
    maximum_interval=timedelta(minutes=1),
    backoff_coefficient=1.0,
)


# Import activities through the sandbox pass-through to avoid loading them in the workflow sandbox
with workflow.unsafe.imports_passed_through():
    from workflows.agent_activities import call_mcp_tool, convert_json_to_markdown
    from workflows.pdf_generation_activity import generate_pdf


@workflow.defn
class AmbientNewsAgent:
    @workflow.run
    async def start_news_agent(self) -> None:
        """Continuously invokes the MCP tool for latest stories, then sleeps for 5 minutes."""
        while True:
            # Invoke the MCP server tool "get_latest_stories" via an activity
            result = await workflow.execute_activity(
                call_mcp_tool,
                "get_latest_stories",
                schedule_to_close_timeout=timedelta(seconds=120),
                retry_policy=retry_policy,
            )

            # Ask LLM to convert JSON to markdown
            markdown_content = await workflow.execute_activity(
                convert_json_to_markdown,
                result,
                schedule_to_close_timeout=timedelta(seconds=120),
                retry_policy=retry_policy,
            )

            # Ask LLM to convert markdown to PDF
            pdf_content = await workflow.execute_activity(
                generate_pdf,
                markdown_content,
                schedule_to_close_timeout=timedelta(seconds=120),
                retry_policy=retry_policy,
            )

            # Sleep for 5 minutes
            await workflow.sleep(300)

