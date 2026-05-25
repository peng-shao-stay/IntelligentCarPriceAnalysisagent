"""
聊天 API 路由 — 用户级会话隔离
"""
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.db.database import get_db
from app.db.models import User, ChatSession, ChatMessage
from app.schemas.chat import (
    ChatRequest,
    ChatResponse,
    ChatSessionResponse,
    ChatHistoryResponse,
    MessageResponse,
    SaveToKnowledgeBaseRequest,
    SaveToKnowledgeBaseResponse,
)
from app.utils.helpers import extract_car_info
from app.auth.dependencies import get_current_user
from app.agent.agent import get_agent
from app.memory.redis_memory import memory_manager
from app.core.logging import logger

router = APIRouter(
    prefix="/chat",
    tags=["聊天"],
    dependencies=[Depends(get_current_user)],
)


@router.post("/", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Send a message and get an AI reply. Session is scoped to the current user."""
    try:
        session_id = request.session_id

        if not session_id:
            # Create new session bound to current user
            session_id = uuid4().hex
            new_session = ChatSession(
                session_id=session_id,
                user_id=current_user.id,
                title=request.message[:50],
            )
            db.add(new_session)
            db.commit()
            logger.info(
                f"Created session {session_id} for user {current_user.username}"
            )
        else:
            # Validate session ownership
            session = db.query(ChatSession).filter(
                ChatSession.session_id == session_id,
                ChatSession.is_deleted == False,
            ).first()
            if not session:
                raise HTTPException(status_code=404, detail="会话不存在")
            if session.user_id != current_user.id:
                raise HTTPException(status_code=403, detail="无权访问此会话")

        # Save user message
        user_message = ChatMessage(
            session_id=session_id,
            role="user",
            content=request.message,
        )
        db.add(user_message)
        db.flush()

        # Load conversation context: try Redis first, then DB
        history = memory_manager.get_history(session_id)
        if not history:
            db_messages = (
                db.query(ChatMessage)
                .filter(
                    ChatMessage.session_id == session_id,
                    ChatMessage.is_deleted == False,
                )
                .order_by(ChatMessage.created_at.desc())
                .limit(20)
                .all()
            )
            history = [
                {"role": msg.role, "content": msg.content}
                for msg in reversed(db_messages)
            ]

        # Call Agent with per-session context (multi-agent orchestration)
        assistant_response = get_agent().process_message(
            message=request.message,
            history=history,
            web_search=request.web_search,
            db=db,
        )

        # Save AI reply
        assistant_message = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=assistant_response,
        )
        db.add(assistant_message)

        # Update session title from first exchange
        session_obj = db.query(ChatSession).filter(
            ChatSession.session_id == session_id
        ).first()
        if session_obj:
            if not session_obj.title or session_obj.title == request.message[:50]:
                session_obj.title = request.message[:50]

        db.commit()
        db.refresh(user_message)
        db.refresh(assistant_message)

        # Update Redis cache
        memory_manager.append(
            session_id, {"role": "user", "content": request.message}
        )
        memory_manager.append(
            session_id, {"role": "assistant", "content": assistant_response}
        )

        logger.info(f"Chat completed for session {session_id}")
        return ChatResponse(
            session_id=session_id,
            user_message=MessageResponse.from_orm(user_message),
            assistant_message=MessageResponse.from_orm(assistant_message),
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Chat error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.get("/sessions", response_model=List[ChatSessionResponse])
def get_sessions(
    offset: int = 0,
    limit: int = 50,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List chat sessions for the current user only (paginated)."""
    try:
        sessions = (
            db.query(ChatSession)
            .filter(
                ChatSession.user_id == current_user.id,
                ChatSession.is_deleted == False,
            )
            .order_by(ChatSession.created_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [ChatSessionResponse.from_orm(s) for s in sessions]
    except Exception as e:
        logger.error(f"Get sessions error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.get("/sessions/{session_id}", response_model=ChatHistoryResponse)
def get_session_history(
    session_id: str,
    offset: int = 0,
    limit: int = 200,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Get chat history for a session. Only the session owner can access."""
    try:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.is_deleted == False,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权访问此会话")

        messages = (
            db.query(ChatMessage)
            .filter(
                ChatMessage.session_id == session_id,
                ChatMessage.is_deleted == False,
            )
            .order_by(ChatMessage.created_at)
            .offset(offset)
            .limit(limit)
            .all()
        )
        return ChatHistoryResponse(
            session=ChatSessionResponse.from_orm(session),
            messages=[MessageResponse.from_orm(msg) for msg in messages],
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Get session history error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.delete("/sessions/{session_id}")
def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Soft-delete a session. Only the session owner can delete."""
    try:
        session = (
            db.query(ChatSession)
            .filter(
                ChatSession.session_id == session_id,
                ChatSession.is_deleted == False,
            )
            .first()
        )
        if not session:
            raise HTTPException(status_code=404, detail="会话不存在")
        if session.user_id != current_user.id:
            raise HTTPException(status_code=403, detail="无权删除此会话")

        session.is_deleted = True
        db.commit()

        # Clear Redis cache
        memory_manager.clear(session_id)

        logger.info(
            f"Session {session_id} soft-deleted by user {current_user.username}"
        )
        return {"message": "会话已删除"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Delete session error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")


@router.post("/knowledge-base", response_model=SaveToKnowledgeBaseResponse)
def save_to_knowledge_base(
    request: SaveToKnowledgeBaseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Save chat content to the RAG knowledge base for future retrieval."""
    try:
        from app.services.rag_service import rag_service

        # Auto-extract brand/model from content if not provided
        brand = request.brand
        model = request.model
        if not brand or not model:
            car_info = extract_car_info(request.content)
            if not brand:
                brand = car_info.get("brand")
            if not model:
                model = car_info.get("model")

        # Auto-generate title if not provided
        title = request.title
        if not title:
            # Use first line or first 100 chars as title
            title = request.content.strip().split("\n")[0][:100]

        doc_id = rag_service.ingest_free_text(
            db=db,
            content=request.content,
            title=title,
            brand=brand,
            model=model,
        )

        if doc_id is None:
            return SaveToKnowledgeBaseResponse(
                success=False,
                message="内容为空，无法保存",
            )

        # Count chunks
        from app.db.models import RagChunk
        chunk_count = (
            db.query(RagChunk)
            .filter(RagChunk.document_id == doc_id, RagChunk.is_deleted == False)
            .count()
        )

        logger.info(
            f"User {current_user.username} saved content to KB: "
            f"doc_id={doc_id}, title={title[:50]}, chunks={chunk_count}"
        )

        return SaveToKnowledgeBaseResponse(
            success=True,
            document_id=doc_id,
            title=title,
            chunk_count=chunk_count,
            message=f"内容已保存到知识库（文档ID: {doc_id}，分块数: {chunk_count}）",
        )

    except Exception as e:
        db.rollback()
        logger.error(f"Save to KB error: {str(e)}")
        raise HTTPException(status_code=500, detail="服务暂时不可用，请稍后重试")
