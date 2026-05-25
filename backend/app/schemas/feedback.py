"""Pydantic schemas for the feedback submission endpoint."""

from typing import Literal

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    feedback_type: Literal["bug", "feature"]
    title: str = Field(..., min_length=5, max_length=100)
    description: str = Field(..., min_length=20)


class FeedbackResponse(BaseModel):
    issue_number: int
    issue_url: str
