import logging
from pathlib import Path
from sqlite3 import Error as SQLiteError
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field
import database


app = FastAPI(title="nejya guessing API", version="1.0.0")
logger = logging.getLogger(__name__)

# Resolve the website from this file, regardless of the terminal's directory.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/static", StaticFiles(directory=FRONTEND_DIR / "static"), name="static")


@app.get("/", response_class=FileResponse, include_in_schema=False)
def homepage():
    """Serve the quiz website; the API routes below keep doing the scoring."""
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/topics")
def list_topics():
    """Return the available quiz topics."""
    try:
        topics = database.get_topics()
    except SQLiteError as error:
        logger.exception("Could not retrieve topics")
        raise HTTPException(
            status_code=503,
            detail="Quiz service temporarily unavailable.",
        ) from error

    return {"topics": topics}


@app.get("/quizzes/{topic}")
def read_quiz(topic: str):
    """Return a topic's questions without revealing correct answers."""
    try:
        quiz = database.get_quiz(topic)
    except SQLiteError as error:
        logger.exception("Could not retrieve quiz")
        raise HTTPException(
            status_code=503,
            detail="Quiz service temporarily unavailable.",
        ) from error

    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found.",
        )

    return quiz

class SubmittedAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    question_id: int = Field(gt=0)
    selected_option: Literal["A", "B", "C", "D"]


class QuizSubmission(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    topic_slug: str = Field(
        min_length=1,
        max_length=32,
        pattern=r"^[a-z]+(?:-[a-z]+)*$",
    )
    quiz_version: int = Field(gt=0)
    answers: list[SubmittedAnswer] = Field(
        min_length=5,
        max_length=5,
    )


@app.post("/submissions")
def submit_quiz(submission: QuizSubmission):
    """Validate submitted answers and return a score without saving them."""

    # Reject repeated question IDs before converting answers to a dictionary.
    submitted_ids = [
        answer.question_id
        for answer in submission.answers
    ]

    if len(submitted_ids) != len(set(submitted_ids)):
        raise HTTPException(
            status_code=422,
            detail="Each question must be answered exactly once.",
        )

    try:
        quiz = database.get_answer_key(submission.topic_slug)
    except SQLiteError as error:
        logger.exception("Could not retrieve the quiz answer key")
        raise HTTPException(
            status_code=503,
            detail="Quiz service temporarily unavailable.",
        ) from error

    if quiz is None:
        raise HTTPException(
            status_code=404,
            detail="Topic not found.",
        )

    if submission.quiz_version != quiz["quiz_version"]:
        raise HTTPException(
            status_code=409,
            detail="This quiz has changed. Reload it before submitting.",
        )

    questions = quiz["questions"]

    # An incomplete quiz in the database is a server-side problem.
    if len(questions) != 5:
        logger.error(
            "Quiz %s contains %s questions instead of five",
            submission.topic_slug,
            len(questions),
        )
        raise HTTPException(
            status_code=503,
            detail="This quiz is temporarily unavailable.",
        )

    expected_ids = {
        question["question_id"]
        for question in questions
    }

    if set(submitted_ids) != expected_ids:
        raise HTTPException(
            status_code=422,
            detail="Submit exactly the five questions from this topic.",
        )

    # Match choices by question ID, regardless of submission order.
    selected_answers = {
        answer.question_id: answer.selected_option
        for answer in submission.answers
    }

    results = []

    for question in questions:
        question_id = question["question_id"]
        selected_option = selected_answers[question_id]
        correct_option = question["correct_option"]

        results.append({
            "question_id": question_id,
            "selected_option": selected_option,
            "correct_option": correct_option,
            "is_correct": selected_option == correct_option,
            "explanation": question["explanation"],
        })

    score = sum(result["is_correct"] for result in results)
    total = len(questions)

    return {
        "topic_slug": quiz["topic_slug"],
        "quiz_version": quiz["quiz_version"],
        "score": score,
        "total": total,
        "percentage": round(score / total * 100, 2),
        "results": results,
    }


