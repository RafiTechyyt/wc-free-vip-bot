from flask import Flask, render_template, request, redirect, session
from datetime import datetime
import os
from db import cursor, init_db

WEB_PASSWORD = os.getenv("WEB_PASSWORD")
SECRET_KEY = os.getenv("WEB_SECRET_KEY")

if not WEB_PASSWORD or not SECRET_KEY:
    raise ValueError("WEB_PASSWORD or WEB_SECRET_KEY missing.")

app = Flask(__name__)
app.secret_key = SECRET_KEY

init_db()

def log_action(action, uid=None):
    cursor.execute(
        "INSERT INTO activity_logs (action, target_uid, performed_by, timestamp) VALUES (%s, %s, %s, %s)",
        (action, uid, "WEB", datetime.now())
    )

@app.before_request
def require_login():
    if request.endpoint not in ["login", "static"]:
        if not session.get("logged_in"):
            return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        if request.form["password"] == WEB_PASSWORD:
            session["logged_in"] = True
            return redirect("/")
        else:
            return "Invalid password"
    return render_template("login.html")

@app.route("/")
def dashboard():
    page = int(request.args.get("page", 1))
    per_page = 20
    offset = (page - 1) * per_page

    cursor.execute(
        "SELECT uid, telegram_username, added_date FROM members ORDER BY id DESC LIMIT %s OFFSET %s",
        (per_page, offset)
    )
    members = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) FROM members")
    total = cursor.fetchone()[0]

    return render_template("dashboard.html", members=members, total=total, page=page)

@app.route("/delete/<uid>")
def delete(uid):
    cursor.execute("DELETE FROM members WHERE uid=%s", (uid,))
    log_action("DELETE_MEMBER", uid)
    return redirect("/")

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port)