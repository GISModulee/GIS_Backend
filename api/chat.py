from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from database.database import get_db
from schemas.chatbot_schema import ChatRequest, ChatResponse
from services.chatbot.chat_service import ChatService
from utils.dependencies import get_current_user
from utils.logger import logger


router = APIRouter(tags=["Chatbot"])
chat_service = ChatService()


@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    logger.info(
        "POST /chat | user_id=%s | conversation_id=%s | case_id=%s | layer_id=%s",
        current_user["user_id"],
        request.conversation_id,
        request.context.case_id,
        request.context.layer_id,
    )
    return await chat_service.handle_chat(request, db, current_user)
