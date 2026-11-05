# Student Result Management System

BCA Minor Project 2026-2027 · GNIOT Institute of Professional Studies, Greater Noida (CCSU, Meerut)
Team: Krishna Kumar Singh · Krish Pathak · Pradeep

A web application where faculty record students' minor project marks. It calculates the percentage, grade and Pass/Fail status, and publishes results to students. Students log in to see their own result and get notifications about results, exams and notices. It works on laptops and phones.

**Tech stack:** Python 3.10+ · Flask · MySQL 8 · mysql-connector-python (parameterised `%s` queries) · HTML/CSS/JS. There is no build step, and the app needs no internet connection once it is installed.

---

## 1. One-time setup

### Windows: one double-click (recommended)

1. Copy this folder to a simple place such as `C:\srms`. Avoid OneDrive folders, because the Desktop is often inside OneDrive. Do not copy the `.venv` folder from another computer.
   Use a Windows account that is an administrator, because the installer is set up for the account that runs it.
2. Double-click **`setup.bat`** and click **Yes** when Windows asks for administrator permission.
3. Wait while it works through five steps. It needs an internet connection and takes about 5 to 15 minutes the first time:
   - installs **Python 3.12** if no Python 3.10+ is found;
   - creates the `.venv` folder and installs the app libraries;
   - installs **MySQL Server 8.4** if MySQL is not already on the laptop, and sets it up as a Windows service that starts automatically;
   - asks you to **choose a MySQL root password** (new MySQL) or **type the existing one** (MySQL already installed; XAMPP usually has none, so just press Enter);
   - writes `.env` for you and creates the database with the demo data.
4. When it asks *Start the app now?*, press Enter. Your browser opens the login page.

From then on, double-click **`start.bat`** to open the app. Keep its black window open while you use the app, and close it to stop the app.

It is safe to run `setup.bat` again at any time, for example after moving the folder. It keeps the existing data and the saved settings.

The installer uses **winget**, which is built into Windows 10 (version 1809 or later) and Windows 11. If Windows says winget is missing, install *App Installer* from the Microsoft Store, or follow the manual steps below.

### Manual setup (macOS, Linux, or if setup.bat cannot be used)

You need **Python 3.10 or newer** and **MySQL 8.0 or newer** (MySQL Installer on Windows includes MySQL Workbench). Remember the MySQL `root` password you choose during installation.

Open a terminal (Windows: *Command Prompt* or *PowerShell*) inside this folder and run:

**Windows**
```bat
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

**macOS / Linux**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Open `.env` in a text editor and set:

| Setting | What to put |
|---|---|
| `DB_PASSWORD` | your MySQL root password |
| `SECRET_KEY` | any long random text. Generate one with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `DB_HOST`, `DB_PORT`, `DB_USER` | leave as `localhost`, `3306`, `root` for a normal MySQL install |

Then create the database, tables and demo data:

```bash
python setup_db.py
```

This step creates the `internship_result_db` database. If you run it again, your existing data stays as it is.

> **Do not have MySQL installed?** If you have Docker, run `docker compose up -d` and set `DB_HOST=127.0.0.1` and `DB_PORT=3307` in `.env`.

## 2. Start the app

On Windows, double-click **`start.bat`**. Otherwise:

```bash
# activate the virtual environment first (see above), then:
python run.py
```

Open **http://localhost:5000** in your browser. Press `Ctrl+C` in the terminal to stop the app.

**To open it on a phone:** set `APP_HOST=0.0.0.0` in `.env`, restart the app, connect the phone to the same Wi-Fi as the laptop, and open `http://<laptop-IP>:5000`. To find the laptop's IP address, run `ipconfig` on Windows or `ipconfig getifaddr en0` on a Mac.

## 3. Demo accounts

| Role | Username | Password | What they can do |
|---|---|---|---|
| Admin | `admin` | `Admin@123` | Everything faculty can do, plus create, deactivate and reset staff accounts |
| Faculty | `faculty` | `Faculty@123` | Add, edit and delete students, enter results, post announcements, export CSV |
| Faculty | `faculty2` | `Faculty@123` | Same as above (a second evaluator) |
| Student | `241203106130` (Krishna) | `Student@123` | See own result, project details and notifications |
| Student | any roll number from the list, e.g. `241203106105` (result pending) | `Student@123` | Same as above |

While `SHOW_DEMO_ACCOUNTS=true` is set in `.env`, the login page shows one-click buttons that fill in these logins. Set it to `false` to hide them.
The demo data has 12 students (9 results published, 3 pending) and several exam notices and announcements.

To reset everything back to the demo data before a presentation:

```bash
python setup_db.py --reset
```

For a clean install without demo data, run `python setup_db.py --no-demo`. It asks you for an admin password.

## 4. Features

- **Login and roles**: admin, faculty and student accounts. Passwords are stored as salted hashes, and each role can only open its own pages.
- **Students**: add, edit and delete students (roll no., name, course, company, project topic). Duplicate roll numbers are blocked, and every delete asks for confirmation first.
- **Results**: enter marks obtained and total marks. The page previews the percentage and grade as you type, and the server recalculates and validates them when you save. Saving a second time updates the same result instead of creating a duplicate (`ON DUPLICATE KEY UPDATE`).
- **Search and filters**: search by name or roll number, and filter by Pass, Fail, Pending or course. You can export what you see to CSV.
- **Dashboard**: total, published and pending results, pass rate, average score, grade distribution, top performers and a list of students waiting for marks.
- **Notifications**:
  - When a result is published or updated, the student gets an automatic notification.
  - Faculty can post exam notices, deadlines and announcements to everyone, to students only or to faculty only, and can mark them as important.
  - The bell icon shows how many are unread and updates every 30 seconds.
  - Each notification can be marked read or unread, and there is a "mark all as read" button.
  - The full notifications page can be filtered by read status and by category.
- **Student portal**:
  - a profile header with the student's initials, roll number, course, company and result status, plus quick actions (download PDF, view and print, notifications, change password);
  - the result as a score ring, marks, Pass/Fail, a grade-band bar that marks where the student sits, how far they are from the next grade (or from the pass mark), and the faculty remarks;
  - while the result is pending, a three-step progress tracker (registered, evaluation in progress, published) replaces the result and the download button;
  - project details, the latest notifications and the grading scheme with the student's grade highlighted.
- **Result card (PDF and print)**: students download their own official-style result card as `result-<roll no>.pdf` (college and university logos, student and project details, marks, percentage, grade, Pass/Fail, remarks, publish date, grading scale, and a "computer-generated" footer with the time it was made). A printable page with a *Print* button gives the same card on paper. Faculty and admin can download any student's card from the students list. Students can only ever get their own card, and a pending result gives a friendly message instead of a file. The PDF is made with `fpdf2` (pure Python, works offline on Windows).
- **Interface**: dark glass theme by default, plus a light theme for projectors (toggle with the sun/moon button), and layouts for both laptop and phone.
- **Errors and empty screens**: every list shows a helpful message when it is empty, every form explains what is wrong when input is invalid, and a clear page appears if MySQL is not running.
- **Security**: all queries use `%s` parameters to stop SQL injection, every form has a CSRF token, roles are checked on the server, and the app sends security headers. Unsafe redirects are blocked, and a user who is deactivated is logged out on their next click.

### Grading rules (`app/rules.py`)

| Percentage | Grade | Status |
|---|---|---|
| 90 – 100 | A+ | Pass |
| 80 – 89.99 | A | Pass |
| 70 – 79.99 | B | Pass |
| 60 – 69.99 | C | Pass |
| 40 – 59.99 | D | Pass |
| below 40 | F | Fail |

The percentage is rounded half-up to two decimals before the grade is chosen, so the grade always matches the number shown. The app rejects marks such as `101/100`, `5/0`, `-1/100`, `abc`, `nan` and `inf`, and a MySQL `CHECK` constraint rejects them again in the database.

## 5. Suggested demo script (about 8 minutes)

1. **Login page**: point out the roles. Try a wrong password to show the error message.
2. **Faculty dashboard** (`faculty`): walk through the statistics, the grade distribution and the "Waiting for marks" list.
3. **Search**: type `pathak`, then filter by **Pending**.
4. **Add a student**: use a new roll number and password and click *Save & enter result*. Then:
   - enter `45` out of `60` and show the live preview (75.00%, Grade B, Pass) before publishing;
   - try `70` out of `60` to show the validation message.
5. **Post an announcement**: for example "Viva on Monday", sent to all students and marked important.
6. **Log out and log in as the new student** (roll number and password):
   - the bell shows unread notifications: welcome, result published and your announcement;
   - open one to mark it read, then use *Mark all read*;
   - show the result card on the dashboard, click *Download PDF* and open the file, then click *View & print* and *Print*.
   - log in as `241203106105` to show the pending tracker (no download button).
7. **Back as faculty**: update the result and show that the student gets a "result updated" notification. Export to CSV, and download a student's result card with the download icon in the students list. Delete a student and show the confirmation dialog.
8. **Admin** (`admin`): create a faculty account, deactivate it, and show that it can no longer log in.
9. Toggle the light/dark theme, open the app on a phone, and mention the automated tests (`pytest`).

## Put it online for free (Render + Aiven)

This gives the app a public link like `https://student-result-management.onrender.com`, with no credit card.

- **Render** runs the app. Its free plan puts the app to sleep after 15 minutes with no visitors, and the next visit takes about a minute to wake it up. Open the link a minute before a demo.
- **Aiven** provides the free MySQL database. If the database sits unused for a long time, Aiven may switch it off. Switch it back on in the Aiven console.

Steps:

1. **Database:** sign up at [aiven.io](https://aiven.io) and create a service: **MySQL**, plan **Free**. Wait until it shows *Running*, then open it. Keep the *Host*, *Port*, *User* and *Password* from the *Connection information* box handy for step 2.
2. **App:** sign up at [render.com](https://render.com) with GitHub. Choose **New → Blueprint**, pick this repository, and click **Apply**. Render reads `render.yaml` and asks for four values:
   - `DB_HOST`, `DB_PORT`, `DB_USER`, `DB_PASSWORD`: paste them from Aiven.
   - Everything else is set automatically. The secret key is generated by Render.
3. Wait for the deploy to show *Live*, then open the `onrender.com` link. The first start creates the tables and the demo data.

To reset the online demo data, open the service in Render, choose **Shell** if your plan has it, or run `python setup_db.py --reset --yes` once with the same `DB_*` values from your own computer.

Anyone with the link can use the demo logins. Before you share the link widely, set `SHOW_DEMO_ACCOUNTS` to `false` in Render, or change the demo passwords.

## 6. Project structure

```
app/
  __init__.py        app factory, CSRF check, security headers, error pages
  config.py          reads settings from .env
  db.py              get_connection / execute_query / transaction helpers
  rules.py           percentage, grade, status and input validation (no GUI or DB)
  auth.py            login, logout, change password, role checks
  faculty.py         dashboard, students, results, CSV export
  admin.py           staff accounts
  student.py         student portal, result card page and PDF download
  result_card.py     builds the PDF result card (fpdf2)
  notifications.py   notifications, read state, announcements
  templates/         HTML pages (Jinja2)
  static/            CSS (tokens.css holds all colours and sizes), JS, images
schema.sql           MySQL tables, keys, constraints
setup_db.py          creates database, tables and demo data
run.py               starts the web server
setup.bat            Windows one-click setup (runs scripts/windows-setup.ps1)
start.bat            Windows: starts the app and opens the browser
scripts/             setup helpers used by setup.bat
tests/               automated tests
```

### Database (`internship_result_db`)

- `users`: login accounts (`username` UNIQUE, hashed password, role admin / faculty / student)
- `students`: student details (`roll_no` UNIQUE). It links to the student's login, which is deleted along with the student.
- `results`: one result per student (`student_id` UNIQUE). It has a `CHECK (0 <= marks <= total, total > 0)` constraint and records who entered the result.
- `notifications`: title, message, category, priority, audience (all / students / faculty / one user)
- `notification_reads`: which user has read which notification (read/unread state)

## 7. Running the tests

```bash
pip install -r requirements-dev.txt
pytest          # 98 tests: grading rules, plus full flows against a temporary "srms_test" database
ruff check .    # lint
```

The flow tests create and then drop a separate `srms_test` database using the MySQL login in `.env`, so your real data is not touched. If MySQL is not running, only those tests are skipped.

## 8. Troubleshooting

| Problem | Fix |
|---|---|
| Windows says *"Windows protected your PC"* when you open `setup.bat` | Click **More info**, then **Run anyway**. This happens with files copied from a USB stick or a download. |
| `setup.bat` stops with a red message | Read the message, fix what it says, and double-click `setup.bat` again. It continues from where it stopped. |
| You forgot the MySQL root password | If `setup.bat` installed MySQL, start fresh. **This deletes the app data**:<br>1. Open *Command Prompt* as administrator and run `net stop MySQL84` and then `sc delete MySQL84`.<br>2. Delete the folder `C:\ProgramData\MySQL\MySQL Server 8.4\Data`.<br>3. Run `setup.bat` again. It asks for a new password.<br>If you installed MySQL yourself, use *MySQL Installer* → **Reconfigure** to set a new password instead. |
| XAMPP MySQL and the new MySQL both want port 3306 | Use only one of them. Stop MySQL in the XAMPP control panel, or stop the `MySQL84` service in the *Services* app. |
| `Missing setting DB_USER` | You have not created `.env` yet. Copy `.env.example` to `.env`. |
| `Could not connect to MySQL` / "Database not reachable" page | Start the MySQL service (Windows: *Services → MySQL84 (or MySQL80) → Start*). Then check `DB_PASSWORD` and `DB_PORT` in `.env`. |
| `Access denied for user 'root'` | `DB_PASSWORD` in `.env` is wrong. |
| `Port 5000 is in use` | Set `APP_PORT=5050` in `.env` and open http://localhost:5050 instead. |
| You get logged out every time the app restarts | Set a fixed `SECRET_KEY` in `.env`. |
| `python` not found (Windows) | Reinstall Python and tick **"Add Python to PATH"**, or use `py` instead of `python`. |
| The app prints "running" but the page never loads | Some networks make the computer's own name lookup very slow. Set `APP_HOST=127.0.0.1` (the default) and try again, or turn off the VPN or Wi-Fi briefly. |

## 9. Limitations and future scope

- It uses Flask's built-in development server, which is fine for a local demo but not for a public deployment.
- There is one result per student and the grade bands are fixed. Grading rules set by each department are planned as a future improvement.
- There are no failed-login limits, audit trail or automatic backups yet. Do not use it for real student data until these are added.
