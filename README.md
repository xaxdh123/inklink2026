PySide6 Demo App

Features
- Starts quickly and displays a login view immediately (avoids blocking on heavy resource loads).
- Uses MAC address as the login identifier.
- On login failure: shows retry and copy-MAC buttons.
- On login success: hides login window and shows a topmost floating panel with feature buttons.
- System tray icon provides the same actions.

Run
1. Create a Python environment and install dependencies:

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1; pip install -r requirements.txt
```

2. Run the app:

```powershell
python main.py
```

Optional: to use a real login endpoint, set the `LOGIN_URL` environment variable to an API that accepts POST JSON {"mac": "..."} and returns `{{"token": "..."}}`.

Notes
- This is a minimal demo. Replace the mock login in `main.py` with your real authentication logic.
- The floating window is frameless and draggable; the system tray contains the same menu entries.
