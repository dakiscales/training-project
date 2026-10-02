import logging
from sqlite3 import Error as SQLiteError

from fastapi import FastAPI, HTTPException

import database


app = FastAPI(title="Quiz API", version="1.0.0")
logger = logging.getLogger(__name__)


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


