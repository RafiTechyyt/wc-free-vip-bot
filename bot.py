from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from datetime import datetime
import os
from psycopg.errors import UniqueViolation
from db import cursor, init_db, conn

# ==============================
# CONFIG
# ==============================

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = os.getenv("ADMIN_IDS")

if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("Environment variables not set properly.")

ADMIN_IDS = [int(x.strip()) for x in ADMIN_IDS.split(",")]

init_db()

# ==============================
# HELPERS
# ==============================

def is_admin(update):
    return update.effective_user.id in ADMIN_IDS

async def admin_only(update: Update):
    await update.message.reply_text("Access denied.")

def log_action(action, uid=None, admin=None):
    cursor.execute(
        "INSERT INTO activity_logs (action, target_uid, performed_by, timestamp) VALUES (%s, %s, %s, %s)",
        (action, uid, admin, datetime.now())
    )

# ==============================
# COMMANDS
# ==============================

# ADD MEMBER
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


# BULK ADD (TEXT FORMAT)
async def bulk_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    lines = update.message.text.split("\n")[1:]  # Skip first line (/bulkadd)

    if not lines:
        return await update.message.reply_text(
            "Usage:\n/bulkadd\nUID @username\nUID @username"
        )

    added = 0
    duplicates = 0
    invalid = 0

    for line in lines:
        parts = line.strip().split()

        if len(parts) != 2:
            invalid += 1
            continue

        uid, username = parts

        if not uid.isdigit():
            invalid += 1
            continue

        try:
            cursor.execute(
                "INSERT INTO members (uid, telegram_username, added_date) VALUES (%s, %s, %s)",
                (uid, username, datetime.now())
            )
            log_action("BULK_ADD", uid, str(update.effective_user.id))
            added += 1
        except UniqueViolation:
            conn.rollback()
            duplicates += 1

    await update.message.reply_text(
        f"Bulk Add Complete:\n\n"
        f"Added: {added}\n"
        f"Duplicates: {duplicates}\n"
        f"Invalid: {invalid}"
    )


# GET MEMBER
async def get_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /get UID")

    uid = context.args[0]

    cursor.execute(
        "SELECT uid, telegram_username, added_date FROM members WHERE uid=%s",
        (uid,)
    )

    result = cursor.fetchone()

    if result:
        await update.message.reply_text(
            f"UID: {result[0]}\nTelegram: {result[1]}\nAdded: {result[2]}"
        )
    else:
        await update.message.reply_text("Member not found.")


# DELETE MEMBER
async def delete_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /delete UID")

    uid = context.args[0]

    cursor.execute("DELETE FROM members WHERE uid=%s RETURNING uid", (uid,))
    deleted = cursor.fetchone()

    if deleted:
        log_action("DELETE_MEMBER", uid, str(update.effective_user.id))
        await update.message.reply_text(f"Deleted UID: {uid}")
    else:
        await update.message.reply_text("Member not found.")


# SEARCH MEMBER
async def search_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update):
        return await admin_only(update)

    if len(context.args) != 1:
        return await update.message.reply_text("Usage: /search keyword")

    keyword = f"%{context.args[0]}%"

    cursor.execute(
        """
        SELECT uid, telegram_username
        FROM members
        WHERE uid LIKE %s OR telegram_username ILIKE %s
        LIMIT 10
        """,
        (keyword, keyword)
    )

    results = cursor.fetchall()

    if not results:
        return await update.message.reply_text("No matching members found.")

    message = "Search Results:\n\n"
    for row in results:
        message += f"UID: {row[0]} | {row[1]}\n"

    await update.message.reply_text(message)


# COUNT MEMBERS
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
app.add_handler(CommandHandler("bulkadd", bulk_add))
app.add_handler(CommandHandler("get", get_member))
app.add_handler(CommandHandler("delete", delete_member))
app.add_handler(CommandHandler("search", search_member))
app.add_handler(CommandHandler("count", count))

print("Bot is running...")
app.run_polling(drop_pending_updates=True)