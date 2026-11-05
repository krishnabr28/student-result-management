"""Demo logins created by `python setup_db.py`. For demonstration only, never for real data.

A DEMO_<ROLE>_PASSWORD setting replaces the default password for that role. Only accounts still on their
default password are offered as one-click logins, so a custom password is never shown on the login page.
"""

import os

DEFAULT_PASSWORDS = {"admin": "Admin@123", "faculty": "Faculty@123", "student": "Student@123"}

DEMO_PASSWORDS = {
    role: os.environ.get(f"DEMO_{role.upper()}_PASSWORD") or default for role, default in DEFAULT_PASSWORDS.items()
}

DEMO_ACCOUNTS = [
    (label, username, DEMO_PASSWORDS[role])
    for label, username, role in (
        ("Admin", "admin", "admin"),
        ("Faculty", "faculty", "faculty"),
        ("Student", "241203106130", "student"),
    )
    if DEMO_PASSWORDS[role] == DEFAULT_PASSWORDS[role]
]
