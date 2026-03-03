from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
import os
from psycopg.errors import UniqueViolation
from db import cursor, init_db, conn

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")

if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("Environment variables not set properly.")

ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS.split(",")]

init_db()

def is_admin(update):
    return update.effective_user.id in ADMIN_IDS

async def admin_only(update: Update):
    await update.message.reply_text("Access denied.")

def log_action(action, uid=None, admin=None):
    cursor.execute(
        "INSERT INTO activity_logs (action, target_uid, performed_by, timestamp) VALUES (%s, %s, %s, %s)",
        (action, uid, admin, datetime.now())
    )

async def add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 2:
        return await update.message.reply_text("Usage: /add UID @username")

    uid = context.args[0]

    if not uid.isdigit():
        return await update.message.reply_text("UID must be numeric.")

    username = context.args[1]

    try:
        cursor.execute(
            "INSERT INTO members (uid, telegram_username, added_date) VALUES (%s, %s, %s)",
            (uid, username, datetime.now())
        )
        log_action("ADD_MEMBER", uid, str(update.effective_user.id))
        await update.message.reply_text("Member added successfully.")
    except UniqueViolation:
        conn.rollback()
        await update.message.reply_text("Duplicate UID detected.")

async def count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]
    await update.message.reply_text(f"Total members: {total}")

app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("add", add))
app.add_handler(CommandHandler("count", count))

print("Bot is running...")
app.run_polling(drop_pending_updates=True)