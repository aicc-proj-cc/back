from sqlalchemy import Column, String, ForeignKey, PrimaryKeyConstraint
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.future import select
from fastapi import APIRouter, Depends, HTTPException, Body
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
from jose import jwt, JWTError
from database import SessionLocal, Friend, Character, User

# .env 파일 로드
load_dotenv()

# 환경 변수 설정
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "default_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30
if not DATABASE_URL:
    raise RuntimeError("DATABASE_URL 환경 변수를 설정하세요.")

Base = declarative_base()
router = APIRouter()

# DB 세션 관리
def get_db():
    """
    데이터베이스 세션을 생성하고 반환.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

class FollowRequest(BaseModel):
    user_idx: int
    char_idx: int

@router.post("/users/{user_idx}/follow", response_model=dict)
async def add_character_to_user(
    user_idx: int,
    request: FollowRequest = Body(...),
    db: Session = Depends(get_db)
):
    if user_idx != request.user_idx:
        raise HTTPException(
            status_code=400,
            detail=f"경로의 user_idx({user_idx})와 본문의 user_idx({request.user_idx})가 일치하지 않습니다."
        )

    try:
        existing_entry = db.query(Follow).filter(
            Follow.user_idx == request.user_idx,
            Follow.char_idx == request.char_idx
        ).first()

        if existing_entry:
            raise HTTPException(status_code=400, detail="이미 추가된 캐릭터입니다.")

        new_follow = Follow(user_idx=request.user_idx, char_idx=request.char_idx)
        db.add(new_follow)
        db.commit()
        return {"message": f"캐릭터 {request.char_idx}가 유저 {request.user_idx}에게 추가되었습니다."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")


@router.get("/users/{user_idx}/follow", response_model=dict)
async def get_characters_for_user(
    user_idx: int,
    db: Session = Depends(get_db)
):
    """
    특정 유저가 팔로우한 캐릭터 목록 반환.
    """
    try:
        result = db.query(Follow).filter(Follow.user_idx == user_idx).all()
        char_idx = [row.char_idx for row in result]

        return {"user_id": user_idx, "characters": char_idx}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")
