from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
import os
import psycopg
from psycopg.errors import UniqueViolation
from flask import Flask, render_template_string, request, redirect
import threading

# ==============================
# CONFIG
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")
DATABASE_URL = os.getenv("DATABASE_URL")
WEB_PASSWORD = os.getenv("WEB_PASSWORD")

if not BOT_TOKEN or not ADMIN_IDS or not DATABASE_URL or not WEB_PASSWORD:
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
# TELEGRAM COMMANDS
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
# FLASK DASHBOARD
# ==============================

web_app = Flask(__name__)

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Bot Dashboard</title>
</head>
<body>
    <h2>Member Dashboard</h2>
    <p>Total Members: {{ total }}</p>

    <form method="POST" action="/search?password={{ password }}">
        <input type="text" name="query" placeholder="Search UID">
        <button type="submit">Search</button>
    </form>

    <table border="1">
        <tr>
            <th>UID</th>
            <th>Telegram</th>
            <th>Added</th>
            <th>Action</th>
        </tr>
        {% for row in members %}
        <tr>
            <td>{{ row[0] }}</td>
            <td>{{ row[1] }}</td>
            <td>{{ row[2] }}</td>
            <td>
                <a href="/delete/{{ row[0] }}?password={{ password }}">Delete</a>
            </td>
        </tr>
        {% endfor %}
    </table>
</body>
</html>
"""

@web_app.before_request
def check_password():
    if request.args.get("password") != WEB_PASSWORD:
        return "Unauthorized", 401

@web_app.route("/")
def dashboard():
    cursor.execute("SELECT uid, telegram_username, added_date FROM members ORDER BY id DESC LIMIT 50")
    members = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]

    return render_template_string(DASHBOARD_HTML, members=members, total=total, password=WEB_PASSWORD)

@web_app.route("/search", methods=["POST"])
def search():
    query = request.form["query"]
    cursor.execute(
        "SELECT uid, telegram_username, added_date FROM members WHERE uid=%s",
        (query,)
    )
    members = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]

    return render_template_string(DASHBOARD_HTML, members=members, total=total, password=WEB_PASSWORD)

@web_app.route("/delete/<uid>")
def delete(uid):
    cursor.execute("DELETE FROM members WHERE uid=%s", (uid,))
    return redirect(f"/?password={WEB_PASSWORD}")

# ==============================
# START SERVICES
# ==============================

def run_web():
    port = int(os.getenv("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("get", get_member))
app.add_handler(CommandHandler("count", count))

print("Bot is running...")

app.run_polling(drop_pending_updates=True)