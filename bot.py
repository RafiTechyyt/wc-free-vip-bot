import sqlite3
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime

# ==============================
# CONFIG
# ==============================

import os
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

if not BOT_TOKEN or not ADMIN_ID:
    raise ValueError("Environment variables not set properly.")
# ==============================
# DATABASE SETUP
# ==============================

conn = sqlite3.connect('members.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uid TEXT UNIQUE,
    telegram_username TEXT,
    added_date TEXT
)
""")
conn.commit()

# ==============================
# ADMIN CHECK
# ==============================

def is_admin(update: Update):
    return update.effective_user.id == ADMIN_ID

async def admin_only(update: Update):
    await update.message.reply_text("Access denied.")

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
            "INSERT INTO members (uid, telegram_username, added_date) VALUES (?, ?, ?)",
            (uid, username, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
        conn.commit()
        await update.message.reply_text("Member added successfully.")
    except sqlite3.IntegrityError:
        await update.message.reply_text("Duplicate UID detected.")

async def get_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /get UID or /get @username")

    query = context.args[0]

    cursor.execute(
        "SELECT uid, telegram_username, added_date FROM members WHERE uid=? OR telegram_username=?",
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
app.run_polling()