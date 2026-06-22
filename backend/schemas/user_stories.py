from pydantic import BaseModel


class UserStoryOut(BaseModel):
    """
    Historia de Usuario asociada a un proyecto. Solo los campos relevantes para
    la consulta y el contexto de IA (id, título, descripción y criterios).
    """
    id: str
    issue_key: str
    summary: str
    status: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None


class UserStoriesResponse(BaseModel):
    stories: list[UserStoryOut]
    total: int
