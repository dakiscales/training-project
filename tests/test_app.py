"""Run from the project root: python -m unittest discover -s tests -v."""
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
import database
import endpoints


class WebsiteIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.original_db = database.DB_PATH
        database.DB_PATH = Path(cls.temporary.name) / "quiz.db"
        database.seed_database()
        cls.client = TestClient(endpoints.app)
        cls.seed_questions = json.loads(
            (database.SEED_DIR / "questions.json").read_text(encoding="utf-8")
        )

    @classmethod
    def tearDownClass(cls):
        cls.client.close()
        database.DB_PATH = cls.original_db
        cls.temporary.cleanup()

    def submission(self, slug="space"):
        return {
            "topic_slug": slug,
            "quiz_version": 1,
            "answers": [
                {"question_id": q["question_id"], "selected_option": q["correct_option"]}
                for q in self.seed_questions if q["topic_slug"] == slug
            ],
        }

    def test_website_and_assets_from_another_working_directory(self):
        previous = Path.cwd()
        try:
            os.chdir(self.temporary.name)
            for path, expected in [
                ("/", "Welcome to nejya guessing"),
                ("/static/style.css", "prefers-reduced-motion"),
                ("/static/app.js", "/submissions"),
                ("/static/favicon.svg", "<svg"),
            ]:
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertIn(expected, response.text)
        finally:
            os.chdir(previous)

    def test_topics_and_questions_do_not_expose_answer_keys(self):
        response = self.client.get("/topics")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["topics"]), 3)
        for topic in response.json()["topics"]:
            response = self.client.get(f"/quizzes/{topic['slug']}")
            self.assertEqual(response.status_code, 200)
            quiz = response.json()
            self.assertEqual(len(quiz["questions"]), 5)
            self.assertNotIn("correct_option", response.text)
            self.assertNotIn("explanation", response.text)

    def test_full_score_for_every_topic(self):
        for slug in ["space", "maths", "web"]:
            with self.subTest(topic=slug):
                payload = self.submission(slug)
                payload["answers"].reverse()
                response = self.client.post("/submissions", json=payload)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()["score"], 5)
                self.assertEqual(response.json()["percentage"], 100)
                self.assertTrue(all(row["explanation"] for row in response.json()["results"]))

    def test_wrong_answer_is_graded_by_backend(self):
        payload = self.submission()
        first = payload["answers"][0]
        first["selected_option"] = "A" if first["selected_option"] != "A" else "B"
        response = self.client.post("/submissions", json=payload)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["score"], 4)
        self.assertEqual(response.json()["percentage"], 80)
        self.assertFalse(response.json()["results"][0]["is_correct"])

    def test_stale_version(self):
        payload = self.submission()
        payload["quiz_version"] = 999
        self.assertEqual(self.client.post("/submissions", json=payload).status_code, 409)

    def test_invalid_submissions(self):
        mutations = [
            lambda p: p["answers"].pop(),
            lambda p: p["answers"].__setitem__(0, p["answers"][1]),
            lambda p: p["answers"][0].__setitem__("selected_option", "E"),
            lambda p: p["answers"][0].__setitem__("question_id", 9999),
        ]
        for mutate in mutations:
            payload = self.submission()
            mutate(payload)
            self.assertEqual(self.client.post("/submissions", json=payload).status_code, 422)

    def test_unknown_topic_and_docs(self):
        self.assertEqual(self.client.get("/quizzes/missing").status_code, 404)
        self.assertEqual(self.client.get("/docs").status_code, 200)
        self.assertIn("/submissions", self.client.get("/openapi.json").json()["paths"])

    def test_private_files_are_not_served(self):
        for path in ["/backend/seed_data/questions.json", "/static/seed_data/questions.json",
                     "/static/../backend/database.py", "/static/%2e%2e/../backend/database.py"]:
            with self.subTest(path=path):
                self.assertEqual(self.client.get(path).status_code, 404)

    def test_missing_database_returns_error_and_page_still_loads(self):
        with patch.object(database, "DB_PATH", Path(self.temporary.name) / "missing.db"):
            with self.assertLogs("endpoints", level="ERROR"):
                self.assertEqual(self.client.get("/topics").status_code, 503)
            self.assertEqual(self.client.get("/").status_code, 200)


if __name__ == "__main__":
    unittest.main()
