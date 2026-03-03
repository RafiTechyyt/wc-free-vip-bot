import os
import psycopg

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL not set.")

conn = psycopg.connect(DATABASE_URL)
conn.autocommit = True
cursor = conn.cursor()

def init_db():
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS members (
        id SERIAL PRIMARY KEY,
        uid TEXT UNIQUE NOT NULL,
        telegram_username TEXT,
        added_date TIMESTAMP NOT NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS activity_logs (
        id SERIAL PRIMARY KEY,
        action TEXT NOT NULL,
        target_uid TEXT,
        performed_by TEXT,
        timestamp TIMESTAMP NOT NULL
    )
    """)