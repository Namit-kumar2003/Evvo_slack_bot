"""
app.py — Slack Bolt app entry point.

Slash command: /ask-data <natural language question>

Flow:
  1. Receive slash command payload from Slack.
  2. Immediately ACK (Slack requires < 3s response).
  3. Send a "thinking" message so user isn't staring at nothing.
  4. Background thread:
       NL→SQL (LangChain + Llama) → Postgres → reply with table
       If date range query → also upload a chart image.
"""

import os
import logging
from threading import Thread
from dotenv import load_dotenv

load_dotenv()

from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from slack_sdk import WebClient

from llm import question_to_sql
from db import execute_query, format_slack_table
from chart import is_date_range_query, generate_chart, cleanup_chart


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("slack-ai-bot")


app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)


client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])



@app.command("/ask-data")
def handle_ask_data(ack, body, respond):
    
    ack()

    question   = (body.get("text") or "").strip()
    user_id    = body.get("user_id")
    channel_id = body.get("channel_id")

    if not question:
        respond(
            ":warning: Please provide a question.\n"
            "Usage: `/ask-data show revenue by region for 2025-09-01`"
        )
        return

   
    respond(
        f":hourglass_flowing_sand: Working on it, <@{user_id}>..."
        f" _(first request may take ~15s due to model cold start)_"
    )

    logger.info(f"User {user_id} asked: {question}")

    
    def process():
        
        try:
            sql = question_to_sql(question)
            logger.info(f"Generated SQL: {sql}")
        except Exception as exc:
            logger.error(f"LLM error: {exc}")
            respond(f":x: *Failed to generate SQL.*\n```{exc}```")
            return

        
        try:
            columns, rows, total = execute_query(sql)
        except Exception as exc:
            logger.error(f"DB error: {exc}")
            respond(
                f":x: *Query execution failed.*\n```{exc}```\n\n"
                f"*Generated SQL was:*\n```{sql}```"
            )
            return

        
        table = format_slack_table(columns, rows, total)

        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":mag: *Query from <@{user_id}>*\n>{question}",
                },
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Generated SQL:*\n```{sql}```",
                },
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Results:*\n```{table}```",
                },
            },
        ]

        respond(blocks=blocks)
        logger.info(f"Replied to {user_id} with {total} rows.")

        
        if is_date_range_query(sql) and rows:
            chart_path = None
            try:
                chart_path = generate_chart(columns, rows, question)
                if chart_path:
                    client.files_upload_v2(
                        channel=channel_id,
                        file=chart_path,
                        filename="chart.png",
                        title=f"Chart: {question[:50]}",
                        initial_comment=f":bar_chart: Here's a chart for your query, <@{user_id}>!",
                    )
                    logger.info("Chart uploaded successfully.")
                else:
                    logger.info("Chart skipped — not enough numeric data.")
            except Exception as exc:
                logger.warning(f"Chart upload failed (non-critical): {exc}")
            finally:
                if chart_path:
                    cleanup_chart(chart_path)

    Thread(target=process, daemon=True).start()




@app.error
def global_error_handler(error, body):
    logger.error(f"Unhandled error: {error}\nBody: {body}")




if __name__ == "__main__":
    app_token = os.environ.get("SLACK_APP_TOKEN")

    if app_token:
        logger.info("Starting in Socket Mode...")
        handler = SocketModeHandler(app, app_token)
        handler.start()
    else:
        port = int(os.environ.get("PORT", 3000))
        logger.info(f"Starting in HTTP mode on port {port}...")
        app.start(port=port)