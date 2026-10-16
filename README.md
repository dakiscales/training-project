nejya guessing

A self-hosted quiz website at **[dakiscales.online](https://dakiscales.online)**.
Choose Space, Everyday Maths, or Web Basics, answer five questions, and review
your score and explanations. The red frontend supports mobile screens and
keyboard navigation. No account is required, and submissions are not saved.

## How data moves

```text
Visitor's browser (HTML, CSS, JavaScript)
    | HTTPS
Cloudflare
    | Encrypted tunnel to cloudflared inside Debian
Nginx (127.0.0.1:80)
    | Local HTTP
Uvicorn / FastAPI (127.0.0.1:8001)
    | SQL queries
SQLite (backend/data/quiz.db)
```

1. JavaScript requests topics from `GET /topics` and questions from
   `GET /quizzes/{topic}`. Correct answers are excluded from these responses.
2. The browser sends the five selected answers to `POST /submissions`.
3. FastAPI validates the submission, reads the answer key from SQLite, and returns
   the score and explanations. JavaScript displays the results.

The initial import reads `backend/seed_data/topics.json` and `questions.json`
into SQLite. The generated database is excluded from Git; answers selected during
a quiz stay in the browser until submission or the page is cleared.

## Integrations

| Component | Role |
| --- | --- |
| HTML, CSS, JavaScript | Display the quiz and request backend data; no frontend build tools. |
| Python, FastAPI, Uvicorn | Serve the website and API; validate and score answers. |
| SQLite | Store topics, questions, correct answers, and explanations in one file. |
| Windows, VirtualBox, Debian | Windows hosts the Debian VM running the website. |
| Nginx | Reverse proxy forwarding local website requests to FastAPI. |
| systemd | Manage startup and recovery through `nejya-guessing.service`, `nginx`, and `cloudflared`. |
| Git and GitHub | Track Windows development changes and deliver updates to Debian. |
| Namecheap | Register and renew `dakiscales.online`. |
| Cloudflare DNS, Tunnel, Universal SSL | Resolve the domain, route visitors to Debian without router port forwarding, and provide automatically renewed public HTTPS.
