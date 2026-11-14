# StudyBuddy – Smart Study Planner & Reminder System

StudyBuddy is a web-based study planner designed to help students organize their study schedules, manage tasks, track progress, and stay on top of deadlines.

## Features

- User registration, login, and logout
- Secure password hashing
- Personalized student dashboard
- Daily, weekly, and monthly study plans
- Task creation, editing, deletion, and completion
- Task priorities: High, Medium, and Low
- Study progress and completion tracking
- Study notes management
- Email reminders for upcoming tasks
- Daily study summary emails
- Admin dashboard

## Technologies Used

- **Backend:** Python, Flask
- **Database:** SQLite
- **Frontend:** HTML, CSS, Jinja2
- **Libraries:** APScheduler, Pandas, Matplotlib, Werkzeug
- **Environment Management:** python-dotenv
- 
*Note: The local database file is not included in this public repository.*

## Installation and Setup

1. Clone the repository:

```bash
git clone https://github.com/Bushra-coder/StudyBuddy-Smart-Study-Planner.git
```

2. Open the project folder:


cd StudyBuddy-Smart-Study-Planner
```

3. Create a virtual environment:

```bash
python -m venv venv
```

4. Activate the virtual environment on Windows:

```bash
venv\Scripts\activate
```

5. Install dependencies:

```bash
pip install -r requirements.txt
```

6. Create a `.env` file using `.env.example` as a template and configure your own email credentials and secret key.

7. Run the application:

```bash
python app.py
```

8. Open your browser and visit:

```text
http://127.0.0.1:5000
```

## Developer

**Bushra Ibrahim**

Web Developer | IT Student

GitHub: [Bushra-coder](https://github.com/Bushra-coder)

---

*Developed as an academic project to make study planning and task management easier for students.*
