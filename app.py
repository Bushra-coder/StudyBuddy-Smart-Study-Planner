from flask import Flask, render_template, request, redirect, url_for, session
import sqlite3
import smtplib
import matplotlib.pyplot as plt
import pandas as pd
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from apscheduler.schedulers.background import BackgroundScheduler

load_dotenv()
MAIL_USERNAME = os.getenv("MAIL_USERNAME")
MAIL_PASSWORD = os.getenv("MAIL_PASSWORD")
MAIL_RECEIVER = os.getenv("MAIL_RECEIVER")

# Connect to SQLite database
def get_db_connection():
    connection = sqlite3.connect("studybuddy.db")
    connection.row_factory = sqlite3.Row
    return connection

def send_email(subject, message, receiver=None):
    sender = MAIL_USERNAME
    receiver = receiver or MAIL_RECEIVER

    email_message = f"""Subject: {subject}
From: {sender}
To: {receiver}

{message}"""

    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(MAIL_USERNAME, MAIL_PASSWORD)
            server.sendmail(sender, receiver, email_message)

        print("Email sent successfully to:", receiver)
        return True

    except Exception as e:
        print("Email sending failed:", e)
        return False  
    

def send_daily_summary():
    today = datetime.now().strftime("%Y-%m-%d")

    connection = get_db_connection()

    students = connection.execute("""
        SELECT id, email
        FROM users
        WHERE role = 'student'
    """).fetchall()

    for student in students:
        tasks = connection.execute("""
            SELECT *
            FROM tasks
            WHERE user_id = ? AND task_date = ?
        """, (student["id"], today)).fetchall()

        total_tasks = len(tasks)
        completed_tasks = sum(
            1 for task in tasks if task["completed"] == 1
        )
        pending_tasks = total_tasks - completed_tasks

        study_minutes = 0

        for task in tasks:
            try:
                start_hour, start_minute = map(
                    int, task["start_time"].split(":")
                )
                end_hour, end_minute = map(
                    int, task["end_time"].split(":")
                )

                duration = (
                    (end_hour * 60 + end_minute)
                    - (start_hour * 60 + start_minute)
                )

                if duration > 0:
                    study_minutes += duration

            except (ValueError, AttributeError):
                continue

        study_hours = round(study_minutes / 60, 1)

        message = f"""StudyBuddy Daily Summary

Date: {today}

Total Tasks: {total_tasks}
Completed Tasks: {completed_tasks}
Pending Tasks: {pending_tasks}
Study Hours: {study_hours} hours

Keep going and stay consistent with your study plan!

StudyBuddy"""

        send_email(
            "StudyBuddy - Daily Summary",
            message,
            student["email"]
        )

    connection.close()
    print("Daily summaries processed successfully.")



def check_reminders():
    current_time = datetime.now().strftime("%H:%M")
    today = datetime.now().strftime("%Y-%m-%d")

    connection = get_db_connection()

    connection.execute("""
        CREATE TABLE IF NOT EXISTS reminder_logs (
            task_id INTEGER,
            reminder_time TEXT,
            PRIMARY KEY (task_id, reminder_time)
        )
    """)

    tasks = connection.execute("""
        SELECT tasks.*, users.email
        FROM tasks
        JOIN users ON tasks.user_id = users.id
        LEFT JOIN reminder_logs
            ON tasks.id = reminder_logs.task_id
            AND tasks.reminder_time = reminder_logs.reminder_time
        WHERE tasks.task_date = ?
          AND tasks.reminder_time = ?
          AND tasks.completed = 0
          AND reminder_logs.task_id IS NULL
    """, (today, current_time)).fetchall()

    for task in tasks:
        subject = "StudyBuddy - Study Reminder"

        message = (
            f"Hello!\n\n"
            f"This is a reminder for your study task:\n"
            f"Subject: {task['subject']}\n"
            f"Topic: {task['topic']}\n"
            f"Time: {task['start_time']} - {task['end_time']}\n\n"
            f"Good luck with your studies!\n"
            f"StudyBuddy"
        )

        if send_email(subject, message, task["email"]):
            connection.execute("""
                INSERT OR IGNORE INTO reminder_logs
                (task_id, reminder_time)
                VALUES (?, ?)
            """, (task["id"], task["reminder_time"]))

            connection.commit()

    connection.close()

# Create Flask application
app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY")

@app.template_filter("pretty_date")
def pretty_date(value):
    if not value:
        return "Date not set"

    try:
        return datetime.strptime(
            value, "%Y-%m-%d"
        ).strftime("%A, %d %B %Y")
    except (ValueError, TypeError):
        return value



def create_database():
    connection = get_db_connection()

    # Create users table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'student'
        )
    """)

    # Create tasks table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            subject TEXT NOT NULL,
            topic TEXT NOT NULL,
            priority TEXT NOT NULL,
            start_time TEXT NOT NULL,
            end_time TEXT NOT NULL,
            plan_type TEXT NOT NULL,
            completed INTEGER DEFAULT 0,
            reminder_time TEXT,
            task_date TEXT
        )
    """)

    # Create notes table
    connection.execute("""
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            content TEXT NOT NULL
        )
    """)

    # Check users columns
    user_columns = [
        column["name"]
        for column in connection.execute(
            "PRAGMA table_info(users)"
        ).fetchall()
    ]

    if "role" not in user_columns:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN role TEXT DEFAULT 'student'
        """)

    if "full_name" not in user_columns:
        connection.execute("""
            ALTER TABLE users
            ADD COLUMN full_name TEXT NOT NULL DEFAULT ''
        """)
        print("full_name column added!")

    # Check tasks columns
    task_columns = [
        column["name"]
        for column in connection.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()
    ]

    if "task_date" not in task_columns:
        connection.execute("""
            ALTER TABLE tasks
            ADD COLUMN task_date TEXT
        """)
        print("task_date column added!")

    connection.commit()
    connection.close()

    print("Database created and upgraded successfully!")



def create_study_chart(tasks, chart_filename):
    today = datetime.now().date()
    today_tasks=[
    task for task in tasks
    if task["task_date"] == today.strftime("%Y-%m-%d")
]

    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    weekly_tasks = [
        task for task in tasks
        if week_start.strftime("%Y-%m-%d")
        <= task["task_date"]
        <= week_end.strftime("%Y-%m-%d")
    ]

    data = pd.DataFrame([dict(task) for task in tasks])

    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    daily_hours = {day: 0 for day in weekdays}

    if not data.empty:
        data["task_date"] = pd.to_datetime(
            data["task_date"], errors="coerce"
        )

        weekly_data = data[
            (data["task_date"].dt.date >= week_start) &
            (data["task_date"].dt.date <= week_end)
        ]

        for _, task in weekly_data.iterrows():
            try:
                start = datetime.strptime(task["start_time"], "%H:%M")
                end = datetime.strptime(task["end_time"], "%H:%M")

                duration = (end - start).total_seconds() / 3600

                if duration > 0:
                    day = task["task_date"].day_name()[:3]
                    daily_hours[day] += duration

            except (ValueError, TypeError):
                continue

    fig, ax = plt.subplots(figsize=(8, 3.5), facecolor="none")
    ax.set_facecolor("none")

    ax.bar(
        weekdays,
        [round(daily_hours[day], 1) for day in weekdays],
        width=0.45,
        color="#7851A9",
        edgecolor="none"
    )

    ax.set_ylabel("Hours", color="#5A5A72", fontsize=10)
    ax.tick_params(colors="#5A5A72", labelsize=10)

    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_color("#DDD8E6")
    ax.spines["bottom"].set_color("#DDD8E6")

    ax.grid(axis="y", linestyle="--", alpha=0.3, color="#B0A8C0")

    plt.tight_layout()
    os.makedirs("static/charts", exist_ok=True)

    plt.savefig(
        os.path.join("static/charts", chart_filename),
        transparent=True,
        dpi=300
    )

    plt.close()


# Registration route

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        full_name = request.form.get('full_name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')

        if not full_name or not email or not password:
            return "Please fill in all fields."

        if len(password) < 8:
            return "Password must be at least 8 characters."

        hashed_password = generate_password_hash(password)

        connection = get_db_connection()

        try:
            connection.execute("""
                INSERT INTO users (full_name, email, password)
                VALUES (?, ?, ?)
            """, (full_name, email, hashed_password))

            connection.commit()
            return redirect(url_for('login'))

        except sqlite3.IntegrityError:
            return "This email is already registered."

        finally:
            connection.close()

    return render_template('register.html')


# Login route
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"]
        password = request.form["password"]

        connection = get_db_connection()
        user = connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()
        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["role"] = user["role"] if "role" in user.keys() else "student"
            return redirect(url_for("home"))

        return "Invalid email or password."

    return render_template("login.html")

# Logout route
@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

# Profile route
@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    if request.method == "POST":
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not full_name or not email:
            connection.close()
            return "Please fill in all fields."

        try:
            connection.execute(
                """
                UPDATE users
                SET full_name = ?, email = ?
                WHERE id = ?
                """,
                (full_name, email, session["user_id"])
            )
            connection.commit()

        except sqlite3.IntegrityError:
            connection.close()
            return "This email is already registered."

    user = connection.execute(
        "SELECT * FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    connection.close()

    return render_template("profile.html", user=user)

# Change password route
@app.route("/change-password", methods=["POST"])
def change_password():
    if "user_id" not in session:
        return redirect(url_for("login"))

    current_password = request.form["current_password"]
    new_password = request.form["new_password"]
    confirm_password = request.form["confirm_password"]

    connection = get_db_connection()
    user = connection.execute(
        "SELECT * FROM users WHERE id = ?", (session["user_id"],)
    ).fetchone()

    if not check_password_hash(user["password"], current_password):
        connection.close()
        return "Current password is incorrect."

    if new_password != confirm_password:
        connection.close()
        return "New passwords do not match."

    hashed_password = generate_password_hash(new_password)
    connection.execute(
        "UPDATE users SET password = ? WHERE id = ?",
        (hashed_password, session["user_id"])
    )
    connection.commit()
    connection.close()

    return redirect(url_for("profile"))

# Forgot password route
@app.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    if request.method == "POST":
        email = request.form["email"]
        new_password = request.form["new_password"]

        hashed_password = generate_password_hash(new_password)
        connection = get_db_connection()

        user = connection.execute(
            "SELECT * FROM users WHERE email = ?", (email,)
        ).fetchone()

        if not user:
            connection.close()
            return "Email not registered."

        connection.execute(
            "UPDATE users SET password = ? WHERE email = ?",
            (hashed_password, email)
        )
        connection.commit()
        connection.close()

        return redirect(url_for("login"))

    return render_template("forgot_password.html")

# Study plans
@app.route("/study-plans")
def study_plans():
    if "user_id" not in session:
        return redirect(url_for("login"))

    search = request.args.get("search", "").strip()
    priority = request.args.get("priority", "")
    status = request.args.get("status", "")
    task_date = request.args.get("task_date", "")
    subject = request.args.get("subject", "").strip()

    connection = get_db_connection()

    user = connection.execute(
        "SELECT full_name FROM users WHERE id = ?",
        (session["user_id"],)
    ).fetchone()

    sql = "SELECT * FROM tasks WHERE user_id = ?"
    params = [session["user_id"]]

    if subject:
       sql += " AND subject LIKE ?"
       params.append(f"%{subject}%")

    if search:
        sql += " AND (subject LIKE ? OR topic LIKE ?)"
        params.extend([f"%{search}%", f"%{search}%"])

    if priority in ["High", "Medium", "Low"]:
        sql += " AND priority = ?"
        params.append(priority)

    if status == "Pending":
        sql += " AND completed = 0"
    elif status == "Completed":
        sql += " AND completed = 1"

    if task_date:
        sql += " AND task_date = ?"
        params.append(task_date)

    sql += " ORDER BY task_date ASC, start_time ASC"

    tasks = connection.execute(sql, params).fetchall()
    connection.close()

    full_name = user["full_name"] if user else "Student"

    return render_template(
        "study_plans.html",
        tasks=tasks,
        search=search,
        subject=subject,
        priority=priority,
        status=status,
        task_date=task_date,
        full_name=full_name
    )

# Add task route
@app.route("/add-task", methods=["GET", "POST"])
def add_task():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        subject = request.form["subject"]
        topic = request.form["topic"]
        priority = request.form["priority"]
        task_date = request.form["task_date"]
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        plan_type = request.form["plan_type"]
        reminder_time = request.form["reminder_time"]

        connection = get_db_connection()
        connection.execute(
            """
            INSERT INTO tasks
            (user_id, subject, topic, priority, task_date,
             start_time, end_time, plan_type, reminder_time)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session["user_id"], subject, topic, priority,
                task_date, start_time, end_time, plan_type,
                reminder_time
            )
        )
        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    return render_template("add_task.html")

# Delete study task
@app.route("/delete-task/<int:task_id>")
def delete_task(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    connection.execute(
        "DELETE FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )
    connection.commit()
    connection.close()

    return redirect(url_for("home"))

# Mark task complete
@app.route("/complete-task/<int:task_id>")
def complete_task(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    connection.execute(
        "UPDATE tasks SET completed = 1 WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    )
    connection.commit()
    connection.close()

    return redirect(url_for("home"))

# Edit study task
@app.route("/edit-task/<int:task_id>", methods=["GET", "POST"])
def edit_task(task_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    task = connection.execute(
        "SELECT * FROM tasks WHERE id = ? AND user_id = ?",
        (task_id, session["user_id"])
    ).fetchone()

    if not task:
        connection.close()
        return "Task not found."

    if request.method == "POST":
        subject = request.form["subject"]
        topic = request.form["topic"]
        priority = request.form["priority"]
        task_date = request.form["task_date"]
        print("SELECTED TASK DATE:", repr(task_date))
        start_time = request.form["start_time"]
        end_time = request.form["end_time"]
        plan_type = request.form["plan_type"]
        reminder_time = request.form.get("reminder_time", "")

        connection.execute(
            """
            UPDATE tasks
            SET subject = ?, topic = ?, priority = ?, task_date = ?,
                start_time = ?, end_time = ?, plan_type = ?, reminder_time = ?
            WHERE id = ? AND user_id = ?
            """,
            (
                subject, topic, priority, task_date,
                start_time, end_time, plan_type, reminder_time,
                task_id, session["user_id"]
            )
        )

        connection.commit()
        connection.close()

        return redirect(url_for("home"))

    connection.close()

    return render_template("edit_task.html", task=task)



@app.route('/')
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user_id = session["user_id"]
    connection = get_db_connection()

    # Get student's name
    user_data = connection.execute(
        "SELECT full_name FROM users WHERE id = ?",
        (user_id,)
    ).fetchone()

    # Get this student's tasks
    tasks = connection.execute(
        "SELECT * FROM tasks WHERE user_id = ?",
        (user_id,)
    ).fetchall()

    # Get upcoming deadlines
    now = datetime.now()
    deadline_today = now.strftime("%Y-%m-%d")
    current_time = now.strftime("%H:%M")

    upcoming_deadlines = connection.execute("""
        SELECT subject, topic, task_date, end_time
        FROM tasks
        WHERE user_id = ?
          AND completed = 0
          AND (
              task_date > ?
              OR (task_date = ? AND end_time >= ?)
          )
        ORDER BY task_date ASC, end_time ASC
        LIMIT 3
    """, (user_id, deadline_today, deadline_today, current_time)).fetchall()

    # Close database connection once
    connection.close()

    full_name = user_data["full_name"] if user_data else "Student"

    # Generate individual chart for this user
    chart_filename = f"study_hours_{user_id}.png"
    create_study_chart(tasks, chart_filename)

    # Calculate task statistics
    total_tasks = len(tasks)

    completed_tasks = sum(
        1 for task in tasks if task["completed"] == 1
    )

    # Calculate study hours using Pandas
    data = pd.DataFrame([dict(task) for task in tasks])

    # Get today's date
    today = datetime.now().date()

    today_tasks = [
        task for task in tasks
        if task["task_date"] == today.strftime("%Y-%m-%d")
    ]

    # Get this week's tasks
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)

    weekly_tasks = [
        task for task in tasks
        if task["task_date"]
        and week_start.strftime("%Y-%m-%d")
        <= task["task_date"]
        <= week_end.strftime("%Y-%m-%d")
    ]

    # Initialize study hours
    study_hours = 0
    today_study_hours = 0
    weekly_study_hours = 0

    if not data.empty:
        data["task_date"] = pd.to_datetime(
            data["task_date"], errors="coerce"
        )

        data["start_datetime"] = pd.to_datetime(
            data["task_date"].dt.strftime("%Y-%m-%d") + " " +
            data["start_time"].astype(str),
            errors="coerce"
        )

        data["end_datetime"] = pd.to_datetime(
            data["task_date"].dt.strftime("%Y-%m-%d") + " " +
            data["end_time"].astype(str),
            errors="coerce"
        )

        data["hours"] = (
            data["end_datetime"] - data["start_datetime"]
        ).dt.total_seconds() / 3600

        data.loc[data["hours"] < 0, "hours"] = 0
        data["hours"] = data["hours"].fillna(0)

        study_hours = round(data["hours"].sum(), 1)

        today_data = data[data["task_date"].dt.date == today]
        today_study_hours = round(today_data["hours"].sum(), 1)

        weekly_data = data[
            (data["task_date"].dt.date >= week_start) &
            (data["task_date"].dt.date <= week_end)
        ]

        weekly_study_hours = round(weekly_data["hours"].sum(), 1)

    # Calculate completion percentage
    completion_percentage = (
        int((completed_tasks / total_tasks) * 100)
        if total_tasks > 0 else 0
    )

    return render_template(
        "index.html",
        tasks=tasks,
        today_tasks=today_tasks,
        weekly_tasks=weekly_tasks,
        upcoming_deadlines=upcoming_deadlines,
        completion_percentage=completion_percentage,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        study_hours=study_hours,
        today_study_hours=today_study_hours,
        weekly_study_hours=weekly_study_hours,
        chart_filename=chart_filename,
        full_name=full_name
    )




# Notes Management

@app.route("/notes")
def notes():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    user_notes = connection.execute(
        "SELECT * FROM notes WHERE user_id = ? ORDER BY id DESC",
        (session["user_id"],)
    ).fetchall()

    connection.close()

    return render_template("notes.html", notes=user_notes)


@app.route("/add-note", methods=["GET", "POST"])
def add_note():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            return "Please fill in all fields."

        connection = get_db_connection()

        connection.execute(
            "INSERT INTO notes (user_id, title, content) VALUES (?, ?, ?)",
            (session["user_id"], title, content)
        )

        connection.commit()
        connection.close()

        return redirect(url_for("notes"))

    return render_template("note_form.html", note=None)


@app.route("/edit-note/<int:note_id>", methods=["GET", "POST"])
def edit_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    note = connection.execute(
        "SELECT * FROM notes WHERE id = ? AND user_id = ?",
        (note_id, session["user_id"])
    ).fetchone()

    if not note:
        connection.close()
        return "Note not found."

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        content = request.form.get("content", "").strip()

        if not title or not content:
            connection.close()
            return "Please fill in all fields."

        connection.execute(
            """
            UPDATE notes
            SET title = ?, content = ?
            WHERE id = ? AND user_id = ?
            """,
            (title, content, note_id, session["user_id"])
        )

        connection.commit()
        connection.close()

        return redirect(url_for("notes"))

    connection.close()

    return render_template("note_form.html", note=note)


@app.route("/delete-note/<int:note_id>", methods=["POST"])
def delete_note(note_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()

    connection.execute(
        "DELETE FROM notes WHERE id = ? AND user_id = ?",
        (note_id, session["user_id"])
    )

    connection.commit()
    connection.close()

    return redirect(url_for("notes"))


# Admin Dashboard

@app.route("/admin")
def admin_dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Access denied. Admin only.", 403

    connection = get_db_connection()

    total_users = connection.execute(
        "SELECT COUNT(*) FROM users WHERE role = 'student'"
    ).fetchone()[0]

    total_tasks = connection.execute(
        "SELECT COUNT(*) FROM tasks"
    ).fetchone()[0]

    completed_tasks = connection.execute(
        "SELECT COUNT(*) FROM tasks WHERE completed = 1"
    ).fetchone()[0]

    pending_tasks = total_tasks - completed_tasks

    users = connection.execute("""
    SELECT
        users.id,
        users.full_name,
        users.email,
        COUNT(tasks.id) AS task_count
    FROM users
    LEFT JOIN tasks ON users.id = tasks.user_id
    WHERE users.role = 'student'
    GROUP BY users.id
    ORDER BY users.id  ASC
""").fetchall()
    

    connection.close()

    return render_template(
        "admin.html",
        users=users,
        total_users=total_users,
        total_tasks=total_tasks,
        completed_tasks=completed_tasks,
        pending_tasks=pending_tasks
    )
if __name__ == "__main__":
    create_database()

    scheduler = BackgroundScheduler()

    scheduler.add_job(
        send_daily_summary,
        "cron",
        hour=21,
        minute=0
    )

    scheduler.add_job(
        check_reminders,
        "cron",
        minute="*"
    )

    scheduler.start()

    app.run(debug=True, use_reloader=False)