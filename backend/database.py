import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "quiz.db"
SEED_DIR = BASE_DIR / "seed_data"


@contextmanager
def _connection(read_only=False):
    """Open a connection, save successful writes, and always close it."""
    if read_only:
        connection = sqlite3.connect(
            DB_PATH.as_uri() + "?mode=ro",
            uri=True,
            timeout=5,
        )
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DB_PATH, timeout=5)

    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    """Create the database and its tables if they do not exist."""
    with _connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS topics (
                slug TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                position INTEGER NOT NULL UNIQUE
                    CHECK (position > 0),
                quiz_version INTEGER NOT NULL
                    CHECK (quiz_version > 0)
            );

            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY
                    CHECK (question_id > 0),
                topic_slug TEXT NOT NULL,
                position INTEGER NOT NULL
                    CHECK (position BETWEEN 1 AND 5),
                prompt TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL
                    CHECK (correct_option IN ('A', 'B', 'C', 'D')),
                explanation TEXT NOT NULL,

                FOREIGN KEY (topic_slug) REFERENCES topics (slug),
                UNIQUE (topic_slug, position)
            );
        """)


def seed_database():
    """Import the JSON files. Identical repeated imports do nothing."""
    with (SEED_DIR / "topics.json").open(encoding="utf-8") as file:
        topics = json.load(file)

    with (SEED_DIR / "questions.json").open(encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(topics, list) or not isinstance(questions, list):
        raise ValueError("Both JSON files must contain a list.")

    if not topics or not questions:
        raise ValueError("The seed files must not be empty.")

    for topic in topics:
        count = sum(
            question["topic_slug"] == topic["slug"]
            for question in questions
        )
        if count != 5:
            raise ValueError(
                f"Topic {topic['slug']!r} must have exactly five questions."
            )

    initialize_database()

    with _connection() as connection:
        # Keep the import together: either every insert succeeds or none do.
        connection.execute("BEGIN IMMEDIATE")

        existing_topics = [
            dict(row)
            for row in connection.execute("SELECT * FROM topics")
        ]
        existing_questions = [
            dict(row)
            for row in connection.execute("SELECT * FROM questions")
        ]

        if existing_topics or existing_questions:
            same_topics = (
                sorted(existing_topics, key=lambda row: row["slug"])
                == sorted(topics, key=lambda row: row["slug"])
            )
            same_questions = (
                sorted(
                    existing_questions,
                    key=lambda row: row["question_id"],
                )
                == sorted(
                    questions,
                    key=lambda row: row["question_id"],
                )
            )

            if same_topics and same_questions:
                return

            raise ValueError(
                "The database already contains different data. "
                "This initial-import function does not overwrite it."
            )

        connection.executemany("""
            INSERT INTO topics (
                slug, name, description, position, quiz_version
            )
            VALUES (
                :slug, :name, :description, :position, :quiz_version
            )
        """, topics)

        connection.executemany("""
            INSERT INTO questions (
                question_id,
                topic_slug,
                position,
                prompt,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_option,
                explanation
            )
            VALUES (
                :question_id,
                :topic_slug,
                :position,
                :prompt,
                :option_a,
                :option_b,
                :option_c,
                :option_d,
                :correct_option,
                :explanation
            )
        """, questions)


def get_topics():
    """Return topic details and question counts as a list of dictionaries."""
    with _connection(read_only=True) as connection:
        rows = connection.execute("""
            SELECT
                t.slug,
                t.name,
                t.description,
                t.quiz_version,
                COUNT(q.question_id) AS question_count
            FROM topics AS t
            LEFT JOIN questions AS q ON q.topic_slug = t.slug
            GROUP BY
                t.slug,
                t.name,
                t.description,
                t.quiz_version,
                t.position
            ORDER BY t.position
        """).fetchall()

    return [dict(row) for row in rows]


def get_quiz(topic_slug):
    """Return a public quiz, or None when the topic does not exist."""
    with _connection(read_only=True) as connection:
        topic = connection.execute("""
            SELECT slug, name, quiz_version
            FROM topics
            WHERE slug = ?
        """, (topic_slug,)).fetchone()

        if topic is None:
            return None

        
        rows = connection.execute("""
            SELECT
                question_id,
                prompt,
                option_a,
                option_b,
                option_c,
                option_d
            FROM questions
            WHERE topic_slug = ?
            ORDER BY position
        """, (topic_slug,)).fetchall()

    questions = [
        {
            "question_id": row["question_id"],
            "prompt": row["prompt"],
            "options": [
                {"key": "A", "text": row["option_a"]},
                {"key": "B", "text": row["option_b"]},
                {"key": "C", "text": row["option_c"]},
                {"key": "D", "text": row["option_d"]},
            ],
        }
        for row in rows
    ]

    return {
        "topic_slug": topic["slug"],
        "topic_name": topic["name"],
        "quiz_version": topic["quiz_version"],
        "question_count": len(questions),
        "questions": questions,
    }
def get_answer_key(topic_slug):
    """Read the quiz version and correct answers for backend grading."""
    with _connection(read_only=True) as connection:
        connection.execute("BEGIN")

        topic = connection.execute("""
            SELECT slug, quiz_version
            FROM topics
            WHERE slug = ?
        """, (topic_slug,)).fetchone()

        if topic is None:
            return None

        questions = connection.execute("""
            SELECT question_id, correct_option, explanation
            FROM questions
            WHERE topic_slug = ?
            ORDER BY position
        """, (topic_slug,)).fetchall()

    return {
        "topic_slug": topic["slug"],
        "quiz_version": topic["quiz_version"],
        "questions": [dict(question) for question in questions],
    }


if __name__ == "__main__":
    seed_database()
    print("Quiz database ready.")import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "quiz.db"
SEED_DIR = BASE_DIR / "seed_data"


@contextmanager
def _connection(read_only=False):
    """Open a connection, save successful writes, and always close it."""
    if read_only:
        connection = sqlite3.connect(
            DB_PATH.as_uri() + "?mode=ro",
            uri=True,
            timeout=5,
        )
    else:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(DB_PATH, timeout=5)

    connection.row_factory = sqlite3.Row

    try:
        connection.execute("PRAGMA foreign_keys = ON")
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_database():
    """Create the database and its tables if they do not exist."""
    with _connection() as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS topics (
                slug TEXT PRIMARY KEY NOT NULL,
                name TEXT NOT NULL,
                description TEXT NOT NULL,
                position INTEGER NOT NULL UNIQUE
                    CHECK (position > 0),
                quiz_version INTEGER NOT NULL
                    CHECK (quiz_version > 0)
            );

            CREATE TABLE IF NOT EXISTS questions (
                question_id INTEGER PRIMARY KEY
                    CHECK (question_id > 0),
                topic_slug TEXT NOT NULL,
                position INTEGER NOT NULL
                    CHECK (position BETWEEN 1 AND 5),
                prompt TEXT NOT NULL,
                option_a TEXT NOT NULL,
                option_b TEXT NOT NULL,
                option_c TEXT NOT NULL,
                option_d TEXT NOT NULL,
                correct_option TEXT NOT NULL
                    CHECK (correct_option IN ('A', 'B', 'C', 'D')),
                explanation TEXT NOT NULL,

                FOREIGN KEY (topic_slug) REFERENCES topics (slug),
                UNIQUE (topic_slug, position)
            );
        """)


def seed_database():
    """Import the JSON files. Identical repeated imports do nothing."""
    with (SEED_DIR / "topics.json").open(encoding="utf-8") as file:
        topics = json.load(file)

    with (SEED_DIR / "questions.json").open(encoding="utf-8") as file:
        questions = json.load(file)

    if not isinstance(topics, list) or not isinstance(questions, list):
        raise ValueError("Both JSON files must contain a list.")

    if not topics or not questions:
        raise ValueError("The seed files must not be empty.")

    for topic in topics:
        count = sum(
            question["topic_slug"] == topic["slug"]
            for question in questions
        )
        if count != 5:
            raise ValueError(
                f"Topic {topic['slug']!r} must have exactly five questions."
            )

    initialize_database()

    with _connection() as connection:
        # Keep the import together: either every insert succeeds or none do.
        connection.execute("BEGIN IMMEDIATE")

        existing_topics = [
            dict(row)
            for row in connection.execute("SELECT * FROM topics")
        ]
        existing_questions = [
            dict(row)
            for row in connection.execute("SELECT * FROM questions")
        ]

        if existing_topics or existing_questions:
            same_topics = (
                sorted(existing_topics, key=lambda row: row["slug"])
                == sorted(topics, key=lambda row: row["slug"])
            )
            same_questions = (
                sorted(
                    existing_questions,
                    key=lambda row: row["question_id"],
                )
                == sorted(
                    questions,
                    key=lambda row: row["question_id"],
                )
            )

            if same_topics and same_questions:
                return

            raise ValueError(
                "The database already contains different data. "
                "This initial-import function does not overwrite it."
            )

        connection.executemany("""
            INSERT INTO topics (
                slug, name, description, position, quiz_version
            )
            VALUES (
                :slug, :name, :description, :position, :quiz_version
            )
        """, topics)

        connection.executemany("""
            INSERT INTO questions (
                question_id,
                topic_slug,
                position,
                prompt,
                option_a,
                option_b,
                option_c,
                option_d,
                correct_option,
                explanation
            )
            VALUES (
                :question_id,
                :topic_slug,
                :position,
                :prompt,
                :option_a,
                :option_b,
                :option_c,
                :option_d,
                :correct_option,
                :explanation
            )
        """, questions)


def get_topics():
    """Return topic details and question counts as a list of dictionaries."""
    with _connection(read_only=True) as connection:
        rows = connection.execute("""
            SELECT
                t.slug,
                t.name,
                t.description,
                t.quiz_version,
                COUNT(q.question_id) AS question_count
            FROM topics AS t
            LEFT JOIN questions AS q ON q.topic_slug = t.slug
            GROUP BY
                t.slug,
                t.name,
                t.description,
                t.quiz_version,
                t.position
            ORDER BY t.position
        """).fetchall()

    return [dict(row) for row in rows]


def get_quiz(topic_slug):
    """Return a public quiz, or None when the topic does not exist."""
    with _connection(read_only=True) as connection:
        topic = connection.execute("""
            SELECT slug, name, quiz_version
            FROM topics
            WHERE slug = ?
        """, (topic_slug,)).fetchone()

        if topic is None:
            return None

        # This query deliberately excludes the answer key and explanations.
        rows = connection.execute("""
            SELECT
                question_id,
                prompt,
                option_a,
                option_b,
                option_c,
                option_d
            FROM questions
            WHERE topic_slug = ?
            ORDER BY position
        """, (topic_slug,)).fetchall()

    questions = [
        {
            "question_id": row["question_id"],
            "prompt": row["prompt"],
            "options": [
                {"key": "A", "text": row["option_a"]},
                {"key": "B", "text": row["option_b"]},
                {"key": "C", "text": row["option_c"]},
                {"key": "D", "text": row["option_d"]},
            ],
        }
        for row in rows
    ]

    return {
        "topic_slug": topic["slug"],
        "topic_name": topic["name"],
        "quiz_version": topic["quiz_version"],
        "question_count": len(questions),
        "questions": questions,
    }


if __name__ == "__main__":
    seed_database()
    print("Quiz database ready.")
