from pydantic import BaseModel, Field, field_validator

class AskRequest(BaseModel):
    question: str = Field(
        min_length=1,
        max_length=4000,
        description="User question for the multi-agent assistant."
    )

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Question cannot be empty.")

        return value

class AskResponse(BaseModel):
    answer: str
    routes: list[str]
    selected_specialists: list[str]

class HealthResponse(BaseModel):
    status: str
