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
from database import SessionLocal, Character, User


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


@router.get("/api/characters/search/{character_idx}", response_model=dict)
def get_character_by_index(character_idx: int, db: Session = Depends(get_db)):
    print(f"Requested character_idx: {character_idx}")
    character = db.query(
        Character.char_idx, Character.char_name, Character.char_description
    ).filter(Character.char_idx == character_idx).first()

    if not character:
        raise HTTPException(status_code=404, detail=f"캐릭터 '{character_idx}'를 찾을 수 없습니다.")

    return {"id": character[0], "name": character[1], "description": character[2]}


@router.get("/api/characters/search", response_model=list)
def search_characters(query: str, db: Session = Depends(get_db)):
    """
    캐릭터 이름과 설명으로 검색해서 목록을 반환하는 API.
    """
    # 캐릭터 이름 또는 설명에 검색어가 포함된 캐릭터 찾기
    characters = db.query(Character).filter(
        (Character.char_name.like(f"%{query}%")) | 
        (Character.char_description.like(f"%{query}%"))
    ).all()

    if not characters:
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

    return [
        {"id": char.char_idx, "name": char.char_name, "description": char.char_description}
        for char in characters
    ]
