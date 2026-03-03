from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
import os
import psycopg
from psycopg.errors import UniqueViolation

# ==============================
# CONFIG
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN or not ADMIN_IDS or not DATABASE_URL:
    raise ValueError("Environment variables not set properly.")

ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS.split(",")]

def is_admin(update):
    return update.effective_user.id in ADMIN_IDS

async def admin_only(update: Update):
    await update.message.reply_text("Access denied.")

# ==============================
# DATABASE SETUP
# ==============================

conn = psycopg.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS members (
    id SERIAL PRIMARY KEY,
    uid TEXT UNIQUE NOT NULL,
    telegram_username TEXT,
    added_date TIMESTAMP NOT NULL
)
""")

# ==============================
# COMMANDS
# ==============================

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /add UID @username")

    uid = context.args[0]
    username = context.args[1]

    try:
        cursor.execute(
            "INSERT INTO members (uid, telegram_username, added_date) VALUES (%s, %s, %s)",
            (uid, username, datetime.now())
        )
        await update.message.reply_text("Member added successfully.")

    except UniqueViolation:
        conn.rollback()
        await update.message.reply_text("Duplicate UID detected.")

async def get_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /get UID or /get @username")

    query = context.args[0]

    cursor.execute(
        "SELECT uid, telegram_username, added_date FROM members WHERE uid=%s OR telegram_username=%s",
        (query, query)
    )

    result = cursor.fetchone()

    if result:
        await update.message.reply_text(
            f"UID: {result[0]}\nTelegram: {result[1]}\nAdded: {result[2]}"
        )
    else:
        await update.message.reply_text("Member not found.")

async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]

    await update.message.reply_text(f"Total members: {total}")

# ==============================
# MAIN
# ==============================

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("get", get_member))
app.add_handler(CommandHandler("count", count))

print("Bot is running...")
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")

def run_health_server():
    port = int(os.getenv("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

threading.Thread(target=run_health_server, daemon=True).start()

app.run_polling()