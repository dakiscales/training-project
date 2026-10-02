# nejya guessing

A red-themed quiz website with three topics: Space, Everyday Maths, and Web Basics.
Pick a topic, answer five questions, then review your score and the explanations.
There is no timer, account, or stored submission history.

## How the pieces fit

```text
training-project/
├── backend/
│   ├── endpoints.py       # FastAPI: serves the website and grades submissions
│   ├── database.py        # SQLite queries and the initial JSON import
│   ├── seed_data/
│   │   ├── topics.json
│   │   └── questions.json
│   └── data/quiz.db       # Created by the import; excluded from Git
├── frontend/
│   ├── index.html         # Page structure and visible text
│   └── static/
│       ├── style.css      # Red theme, mobile layout, keyboard focus
│       ├── app.js         # Loads questions and handles the quiz screens
│       └── favicon.svg    # Browser-tab icon
├── tests/test_app.py      # API and website integration checks
├── requirements.txt      # Python packages needed to run the app
└── requirements-dev.txt  # Adds the test dependency
```

**HTML** gives the page its structure. **CSS** controls its appearance.
**JavaScript** reacts to clicks and requests data from Python. **FastAPI** serves
the files and calculates scores. **SQLite** stores the topics and questions.
Correct answers stay in the backend until a quiz is submitted.

## Run on your existing Debian setup

First commit and push the Windows changes to GitHub. Then stop your old quiz
development server with **Ctrl+C** and run this in the Debian terminal:

```bash
cd /home/daki/training-project &&
git pull --ff-only &&
/home/daki/.venv/bin/python -m pip install -r requirements.txt &&
/home/daki/.venv/bin/python backend/database.py &&
/home/daki/.venv/bin/python -m uvicorn endpoints:app --app-dir /home/daki/training-project/backend --host 127.0.0.1 --port 8001
```

Open **http://127.0.0.1:8001/** in the **Debian browser** for the website.
The API documentation remains at **http://127.0.0.1:8001/docs**.
The command binds to Debian's own loopback address. Access from Windows requires
the VM networking you choose to configure; Windows's `127.0.0.1` is a different machine.

The JSON import creates the database on a fresh installation. Repeating the import
with the same data is safe; it does not overwrite a database containing different
data. If Git reports conflicting local edits, stop and resolve them before retrying
the pull; do not discard changes blindly.

## Fresh installation (Windows or Debian)

Use Python 3.10 or newer. From the project folder:

```bash
python -m venv .venv
```

Activate the environment:

- Debian: `source .venv/bin/activate`
- Windows PowerShell: `.\.venv\Scripts\Activate.ps1`

Then run:

```bash
python -m pip install -r requirements.txt
python backend/database.py
python -m uvicorn endpoints:app --app-dir backend --host 127.0.0.1 --port 8001
```

An **environment** is a private folder for this project's Python packages.
**Uvicorn** runs the FastAPI application. Keep its terminal running while testing.
You can add `--reload` during development to reload Python after edits.

## API used by the page

| Request | Purpose |
| --- | --- |
| `GET /` | Open the website |
| `GET /static/style.css` | Load the appearance |
| `GET /static/app.js` | Load the browser behavior |
| `GET /topics` | Get available topics and question counts |
| `GET /quizzes/{topic}` | Get five questions and their options, without answers |
| `POST /submissions` | Send five choices and receive a score plus explanations |
| `GET /docs` | Explore the existing API |

The page uses relative URLs, so the frontend and backend use the same address.
No frontend package installation or build step is needed. Serve the page through
FastAPI; double-clicking `index.html` will not connect it to the API.

Selections stay in the current browser page while you move between questions.
A failed submission keeps them for retrying. Refreshing or leaving the quiz clears
them. If the backend says the quiz changed, the page offers a fresh copy rather
than showing an invented score.

## Checks

With the environment active, run these from the project folder:

```bash
python -m pip install -r requirements-dev.txt
python -m unittest discover -s tests -v
```

Tests create a separate temporary database and never change your normal quiz data.
They check the website and assets, API routes, scoring, invalid submissions, stale
quiz versions, and that seed files are not available through the website.
