cd /home/daki/training-project &&
git stash push -m "Save Debian database edits" -- backend/database.py &&
git pull --ff-only &&
git stash pop &&
cd backend &&
/home/daki/.venv/bin/python -m uvicorn endpoints:app --reload --port 8001
