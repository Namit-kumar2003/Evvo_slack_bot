# 🤖 Slack AI Data Bot

<div align="center">

![Slack](https://img.shields.io/badge/Slack-4A154B?style=for-the-badge&logo=slack&logoColor=white)
![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=for-the-badge&logo=postgresql&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1C3C3C?style=for-the-badge&logo=chainlink&logoColor=white)


**Ask your database questions in plain English — right from Slack.**

📽️ Demo



https://github.com/user-attachments/assets/b20498ac-64aa-4ad6-b0f6-eabfafb3b350


## ✨ What Is This?

This is a **Slack slash-command bot** that lets anyone on your team query a PostgreSQL database using **plain English** — no SQL knowledge required. You just type your question, and the bot:

1. 🧠 Converts your question into SQL using an LLM (Llama 3 via Groq)
2. 🗄️ Runs the SQL on your PostgreSQL database
3. 📊 Replies with a formatted results table in Slack
4. 📈 **[Stretch Goal]** Automatically generates and uploads a **bar chart** for date range queries

---

## 🏗️ Architecture

```
User types /ask-data <question>
            │
            ▼
    ┌─────────────────┐
    │  Slack Bolt App │  ← app.py
    │  (Socket Mode)  │
    └────────┬────────┘
             │  ack() → instant 200 to Slack (< 1s)
             │
     ┌───────▼────────────────────────────┐
     │         Background Thread           │
     │                                     │
     │  ┌─────────────────────────────┐   │
     │  │     LangChain Pipeline      │   │
     │  │  prompts.py + llm.py        │   │
     │  │                             │   │
     │  │  System Prompt + Question   │   │
     │  │           │                 │   │
     │  │           ▼                 │   │
     │  │   Llama 3 (via Groq API)    │   │
     │  │           │                 │   │
     │  │           ▼                 │   │
     │  │    Clean SQL SELECT         │   │
     │  └──────────┬──────────────────┘   │
     │             │                       │
     │  ┌──────────▼──────────────────┐   │
     │  │       PostgreSQL            │   │
     │  │  db.py — execute query      │   │
     │  │  returns rows + columns     │   │
     │  └──────────┬──────────────────┘   │
     │             │                       │
     │  ┌──────────▼──────────────────┐   │
     │  │     Slack Response          │   │
     │  │  • Formatted ASCII table    │   │
     │  │  • [If date range query]    │   │
     │  │    Bar chart PNG uploaded   │   │  ← chart.py (Stretch Goal ✅)
     │  └─────────────────────────────┘   │
     └─────────────────────────────────────┘
```

---

## 🚀 Features

| Feature | Status |
|---|---|
| `/ask-data` slash command | ✅ |
| Natural Language → SQL conversion | ✅ |
| LangChain NL→SQL pipeline | ✅ |
| PostgreSQL query execution | ✅ |
| Formatted table reply in Slack | ✅ |
| Instant ACK + background threading (no timeout) | ✅ |
| Error handling with descriptive messages | ✅ |
| **[Stretch Goal] Auto chart for date range queries** | ✅ |

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Slack Integration** | [Slack Bolt for Python](https://slack.dev/bolt-python/) + Socket Mode |
| **LLM** | [Llama 3 8B](https://groq.com/) via Groq free API |
| **LLM Orchestration** | [LangChain Core](https://python.langchain.com/) (LCEL pipeline) |
| **Database** | PostgreSQL 13+ with psycopg2 connection pool |
| **Chart Generation** | Matplotlib (dark-themed bar charts) |
| **Language** | Python 3.10+ |

---

## 📁 Project Structure

```
slack-ai-bot/
│
├── app.py           # 🎯 Slack Bolt app — slash command handler, threading, chart upload
├── llm.py           # 🧠 LangChain chain: prompt → Llama 3 (Groq) → clean SQL
├── db.py            # 🗄️  PostgreSQL connection pool, query execution, table formatter
├── prompts.py       # 📝 System prompt and human message template for NL→SQL
├── chart.py         # 📈 Chart generation using matplotlib (Stretch Goal ✅)
├── requirements.txt # 📦 Python dependencies
├── .env.example     # 🔑 Environment variable template
├── .gitignore       # 🙈 Git ignore rules
└── README.md        # 📖 This file
```

---

## ⚙️ How It Works — Step by Step

### 1️⃣ User sends a slash command
```
/ask-data show revenue by region for 2025-09-01
```

### 2️⃣ Bot instantly acknowledges
Slack requires a response within 3 seconds. The bot calls `ack()` immediately and sends a *"Working on it..."* message, then hands off to a background thread — so Slack never times out regardless of how long the LLM takes.

### 3️⃣ LangChain converts question → SQL
The system prompt describes the exact database schema to the model. LangChain's LCEL pipeline sends it to **Llama 3 8B on Groq** and gets back a SQL SELECT statement. A regex cleaner strips any markdown fences the model might add.

```
"show revenue by region for 2025-09-01"
        ↓  Llama 3 via Groq
"SELECT region, SUM(revenue) AS total_revenue
 FROM public.sales_daily
 WHERE date = '2025-09-01'
 GROUP BY region
 ORDER BY total_revenue DESC;"
```

### 4️⃣ SQL runs on PostgreSQL
`db.py` uses a `psycopg2` connection pool (1–5 connections). Results are fetched and capped at 10 preview rows. Always calls `rollback()` after a SELECT for read-only safety.

### 5️⃣ Results posted to Slack
A fixed-width ASCII table is rendered inside a Slack code block using Block Kit sections.

```
+---------+---------------+
| region  | total_revenue |
+---------+---------------+
| North   | 125000.50     |
| South   | 54000.00      |
| West    | 40500.00      |
+---------+---------------+
```

### 6️⃣ 📈 Chart generated and uploaded [Stretch Goal ✅]
If the SQL contains a date range (`BETWEEN`, `>=`, `GROUP BY date` etc.), `chart.py` automatically generates a dark-themed bar chart using matplotlib and uploads it to the Slack channel via `files_upload_v2`.

---

## 🗄️ Database Schema

```sql
CREATE DATABASE analytics;
\c analytics

CREATE TABLE IF NOT EXISTS public.sales_daily (
    date        DATE           NOT NULL,
    region      TEXT           NOT NULL,
    category    TEXT           NOT NULL,
    revenue     NUMERIC(12,2)  NOT NULL,
    orders      INTEGER        NOT NULL,
    created_at  TIMESTAMPTZ    NOT NULL DEFAULT now(),
    PRIMARY KEY (date, region, category)
);

-- Seed data
INSERT INTO public.sales_daily (date, region, category, revenue, orders) VALUES
    ('2025-09-01','North','Electronics',125000.50,310),
    ('2025-09-01','South','Grocery',54000.00,820),
    ('2025-09-01','West','Fashion',40500.00,190),
    ('2025-09-02','North','Electronics',132500.00,332),
    ('2025-09-02','West','Fashion',45500.00,210),
    ('2025-09-02','East','Grocery',62000.00,870);
```

---

## 🔧 Setup & Installation

### Prerequisites

- Python 3.10+
- PostgreSQL 13+
- A Slack workspace (with admin rights)
- Free [HuggingFace] API key

### 1. Clone the repo

```bash
git clone https://github.com/your-username/slack-ai-bot.git
cd slack-ai-bot
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up PostgreSQL

```bash
psql -U postgres
```
```sql
CREATE DATABASE analytics;
\c analytics
-- Paste the CREATE TABLE and INSERT statements from above
```

### 5. Set up the Slack App

1. Go to [api.slack.com/apps](https://api.slack.com/apps) → **Create New App** → From scratch
2. **Settings → Socket Mode** → Enable → Generate App-Level Token (`xapp-...`) with scope `connections:write`
3. **Features → Slash Commands** → Create `/ask-data`
4. **OAuth & Permissions → Bot Token Scopes** → Add `chat:write`, `commands`, `files:write`
5. **Install to Workspace** → copy the Bot Token (`xoxb-...`)
6. Copy the **Signing Secret** from Basic Information

### 6. Get a free HuggingFace API key

1. Go to [huggingface] website
2. Sign up — no credit card needed
3. API Keys → Create Key → copy it

### 7. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:
```env
SLACK_BOT_TOKEN=xoxb-...
SLACK_SIGNING_SECRET=...
SLACK_APP_TOKEN=xapp-...

GROQ_API_KEY=gsk_...

DB_HOST=localhost
DB_PORT=5432
DB_NAME=analytics
DB_USER=postgres
DB_PASSWORD=your_password
```

### 8. Run the bot

```bash
python app.py
```

You should see:
```
⚡️ Bolt app is running in Socket Mode!
```

---

## 💬 Usage

Invite the bot to a channel first:
```
/invite @YourBotName
```

Then ask anything in plain English:

```
/ask-data show revenue by region for 2025-09-01
/ask-data which category had the most orders?
/ask-data total revenue per day
/ask-data top 3 regions by total revenue
/ask-data show all data between 2025-09-01 and 2025-09-02
```

> 💡 Queries with date ranges automatically get a chart too!

---

## 📈 Stretch Goal — Auto Chart Generation

For any query involving a **date range** (e.g. `BETWEEN`, `GROUP BY date`, `WHERE date >=`), the bot automatically:

1. Detects the date range pattern in the generated SQL using regex
2. Generates a **dark-themed bar chart** using `matplotlib`
3. Uploads it directly to Slack as a PNG image alongside the results table

**Queries that trigger a chart:**
```
/ask-data revenue per day for all dates
/ask-data orders between 2025-09-01 and 2025-09-02
/ask-data show daily revenue grouped by category
```

**Queries that only return a table (single point in time):**
```
/ask-data show revenue by region for 2025-09-01
```

---

## 🧯 Troubleshooting

| Error | Fix |
|---|---|
| `SLACK_BOT_TOKEN` KeyError | Make sure `.env` is in the project root and `load_dotenv()` is at the top of `app.py` |
| `GROQ_API_KEY is not set` | Add it to `.env` and restart the bot |
| `Could not connect to PostgreSQL` | Check all `DB_*` values in `.env` |
| Slack shows `dispatch_failed` | Make sure `SLACK_APP_TOKEN` is set and Socket Mode is enabled in your Slack app dashboard |
| Model returns non-SQL text | `_clean_sql()` in `llm.py` handles this automatically — check terminal logs |
| Chart not appearing | Make sure `files:write` scope is added and the app is reinstalled to your workspace |

---

## 📦 Dependencies

```
slack-bolt          # Slack app framework
slack-sdk           # Slack Web API client  
langchain-core      # LLM pipeline (LCEL)
huggingfaceendpoint                # Groq API client (Llama 3)
psycopg2-binary     # PostgreSQL driver
matplotlib          # Chart generation
python-dotenv       # .env file loader
```

---

## 🙌 Acknowledgements

- [Slack Bolt for Python](https://slack.dev/bolt-python/) — clean, modern Slack app framework
- [Groq](https://groq.com/) — blazing fast free LLM inference
- [LangChain](https://python.langchain.com/) — LLM orchestration
- [Meta Llama 3](https://llama.meta.com/) — the underlying open-source language model

---

<div align="center">

Built with ❤️ as an internship assignment project.

</div>
