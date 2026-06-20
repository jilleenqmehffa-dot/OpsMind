from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.schemas.wiki_qa import WikiAnswerResponse, WikiQuestionRequest
from app.services.wiki_qa import WikiQuestionError, answer_wiki_question


router = APIRouter(prefix="/api/v1/wiki", tags=["wiki-qa"])


@router.post("/questions", response_model=WikiAnswerResponse)
def create_wiki_answer(
    payload: WikiQuestionRequest,
    db: Session = Depends(get_db),
    _current_user: User = Depends(get_current_user),
) -> WikiAnswerResponse:
    try:
        return answer_wiki_question(
            db,
            payload.question,
            page_ids=payload.page_ids,
        )
    except WikiQuestionError as error:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Wiki answer generation failed",
        ) from error
