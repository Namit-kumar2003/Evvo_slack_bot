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

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("slack-ai-bot")

# ---------------------------------------------------------------------------
# Slack app initialisation
# ---------------------------------------------------------------------------
app = App(
    token=os.environ["SLACK_BOT_TOKEN"],
    signing_secret=os.environ["SLACK_SIGNING_SECRET"],
)

# WebClient for file uploads (uses the same bot token)
client = WebClient(token=os.environ["SLACK_BOT_TOKEN"])

# ---------------------------------------------------------------------------
# /ask-data slash command
# ---------------------------------------------------------------------------

@app.command("/ask-data")
def handle_ask_data(ack, body, respond):
    # Acknowledge immediately — satisfies Slack's 3s rule
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

    # Let the user know we're working on it
    respond(
        f":hourglass_flowing_sand: Working on it, <@{user_id}>..."
        f" _(first request may take ~15s due to model cold start)_"
    )

    logger.info(f"User {user_id} asked: {question}")

    # -----------------------------------------------------------------------
    # Everything below runs in a background thread so ack() can flush first
    # -----------------------------------------------------------------------
    def process():
        # Step 1 — NL → SQL
        try:
            sql = question_to_sql(question)
            logger.info(f"Generated SQL: {sql}")
        except Exception as exc:
            logger.error(f"LLM error: {exc}")
            respond(
                text="Data Query Result",
                attachments=[{
                    "color": "#E01E5A",   # red left border for errors
                    "blocks": [
                        {"type": "header", "text": {"type": "plain_text", "text": "🔍  Data Query Result", "emoji": True}},
                        {"type": "section", "fields": [
                            {"type": "mrkdwn", "text": f"*👤 Requested by:*\n<@{user_id}>"},
                            {"type": "mrkdwn", "text": "*🗂️ Task Name:*\nask-data query"},
                        ]},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📋 Query:*\n>{question}"}},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": "*🧠 Inference:*\n❌  Failed to generate SQL."}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🪲 Error:*\n```{exc}```"}},
                        {"type": "context", "elements": [{"type": "mrkdwn", "text": "🤖 Powered by *Llama 3* via Groq  •  DB: *analytics.sales_daily*"}]},
                    ]
                }]
            )
            return

        # Step 2 — Execute SQL on Postgres
        try:
            columns, rows, total = execute_query(sql)
        except Exception as exc:
            logger.error(f"DB error: {exc}")
            respond(
                text="Data Query Result",
                attachments=[{
                    "color": "#E01E5A",   # red left border for errors
                    "blocks": [
                        {"type": "header", "text": {"type": "plain_text", "text": "🔍  Data Query Result", "emoji": True}},
                        {"type": "section", "fields": [
                            {"type": "mrkdwn", "text": f"*👤 Requested by:*\n<@{user_id}>"},
                            {"type": "mrkdwn", "text": "*🗂️ Task Name:*\nask-data query"},
                        ]},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*📋 Query:*\n>{question}"}},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*⚙️ Generated SQL:*\n```{sql}```"}},
                        {"type": "divider"},
                        {"type": "section", "text": {"type": "mrkdwn", "text": "*🧠 Inference:*\n❌  Query execution failed."}},
                        {"type": "section", "text": {"type": "mrkdwn", "text": f"*🪲 Error:*\n```{exc}```"}},
                        {"type": "context", "elements": [{"type": "mrkdwn", "text": "🤖 Powered by *Llama 3* via Groq  •  DB: *analytics.sales_daily*"}]},
                    ]
                }]
            )
            return

        # Step 3 — Format and post result as a rich bordered card
        table = format_slack_table(columns, rows, total)

        # Build inference line
        if total == 0:
            inference_text = "⚠️  Query returned *no rows*."
        elif total == 1:
            inference_text = "✅  Query executed successfully — *1 row* returned."
        else:
            shown = min(total, 10)
            inference_text = (
                f"✅  Query executed successfully — "
                f"*{total} rows* returned"
                + (f" _(showing {shown})_" if total > shown else "") + "."
            )

        respond(
            text="Data Query Result",
            attachments=[{
                "color": "#2EB67D",   # green left border for success
                "blocks": [
                    # ── Header ──────────────────────────────────────────
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "🔍  Data Query Result",
                            "emoji": True,
                        },
                    },
                    # ── Asked by + Task Name ─────────────────────────────
                    {
                        "type": "section",
                        "fields": [
                            {"type": "mrkdwn", "text": f"*👤 Requested by:*\n<@{user_id}>"},
                            {"type": "mrkdwn", "text": "*🗂️ Task Name:*\nask-data query"},
                        ],
                    },
                    {"type": "divider"},
                    # ── Question ─────────────────────────────────────────
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*📋 Query:*\n>{question}"},
                    },
                    {"type": "divider"},
                    # ── Generated SQL ────────────────────────────────────
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*⚙️ Generated SQL:*\n```{sql}```"},
                    },
                    {"type": "divider"},
                    # ── Inference ────────────────────────────────────────
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*🧠 Inference:*\n{inference_text}"},
                    },
                    {"type": "divider"},
                    # ── Results ──────────────────────────────────────────
                    {
                        "type": "section",
                        "text": {"type": "mrkdwn", "text": f"*📊 Results:*\n```{table}```"},
                    },
                    # ── Footer ───────────────────────────────────────────
                    {
                        "type": "context",
                        "elements": [
                            {
                                "type": "mrkdwn",
                                "text": "🤖 Powered by *Llama 3* via Groq  •  DB: *analytics.sales_daily*",
                            }
                        ],
                    },
                ]
            }]
        )
        logger.info(f"Replied to {user_id} with {total} rows.")

        # Step 4 — Chart (only for date range queries)
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


# ---------------------------------------------------------------------------
# Global error handler
# ---------------------------------------------------------------------------

@app.error
def global_error_handler(error, body):
    logger.error(f"Unhandled error: {error}\nBody: {body}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

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