from sqlalchemy import create_engine, Column, String, Text, DateTime, ForeignKey, Integer, Boolean, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, declarative_base
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# PostgreSQL 연결 URL
DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 캐릭터 모델
class Character(Base):
    __tablename__ = "characters"

    character_index = Column(Integer, primary_key=True)  # 캐릭터 고유 ID
    character_field = Column(String(255), nullable=False)  # 캐릭터 필드(장르)
    character_name = Column(String(255), nullable=False)  # 캐릭터 이름
    character_description = Column(Text, nullable=False)  # 캐릭터 설명
    character_status_message = Column(ARRAY(String), nullable=False)  # 상태 메시지 (리스트 형식)
    character_prompt = Column(Text, nullable=False)  # 캐릭터 프롬프트
    character_image = Column(Text, nullable=False)  # 이미지 URL
    character_likes = Column(Integer, default=0)  # 캐릭터 호감도
    character_thumbs = Column(Integer, default=0)  # 캐릭터 좋아요 수
    is_active = Column(Boolean, default=True)  # 활성화 여부
    character_created_at = Column(DateTime, default=datetime.utcnow)  # 생성 날짜

# 채팅방 모델
class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    id = Column(String, primary_key=True) # 채팅방 고유 ID
    character_prompt = Column(Text, nullable=False) # 캐릭터 프롬프트
    character_id = Column(Integer, ForeignKey("characters.character_index")) # 캐릭터 고유 ID (characters db 참조)
    character_name = Column(String(255), nullable=False) # 캐릭터 이름
    character_image = Column(Text, nullable=False) # 캐릭터 이미지
    character_status_message = Column(ARRAY(String), nullable=False)  # 캐릭터 상태 메시지 (리스트 형식)
    character_likes = Column(Integer, nullable=False)  # 캐릭터 호감도
    character_emotion = Column(String, default="보통")  # 캐릭터 기분
    created_at = Column(DateTime, default=datetime.utcnow) # 캐릭터 생성 일자

# 메시지 모델
class Message(Base):
    __tablename__ = "messages"

    id = Column(String, primary_key=True) # 메시지 고유 ID
    room_id = Column(String, ForeignKey("chat_rooms.id")) # 채팅방 ID (chat_rooms db 참조)
    sender = Column(String) # 송신자 이름
    content = Column(Text) # 메시지 내용
    timestamp = Column(DateTime, default=datetime.utcnow) # 메시지 전송 시각

# 테이블 생성
Base.metadata.create_all(bind=engine)
