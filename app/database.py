from sqlalchemy import create_engine, UniqueConstraint, Column, String, Text, DateTime, ForeignKey, Integer, Boolean, JSON, ARRAY, text, Index, and_
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

# PostgreSQL 연결 URL
DATABASE_URL = os.getenv("DATABASE_URL")

# SQLAlchemy 설정
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Users 테이블
class User(Base):
    __tablename__ = "users"

    user_idx = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(100), nullable=False)
    nickname = Column(String(100), nullable=False)
    password = Column(String(255), nullable=False)
    profile_img = Column(String(255), nullable=True)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

# Characters 테이블
class Character(Base):
    __tablename__ = "characters"

    char_idx = Column(Integer, primary_key=True, autoincrement=True)
    character_owner = Column(Integer, ForeignKey("users.user_idx"), nullable=True)
    field_idx = Column(Integer, ForeignKey("fields.field_idx"), nullable=False)
    voice_idx = Column(String(50), ForeignKey("voice.voice_idx"), nullable=False)
    char_name = Column(String(50), nullable=False)
    char_description = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    nicknames = Column(
        JSON,
        nullable=False,
        default=lambda: {30: "stranger", 70: "friend", 100: "best friend"}
)

# Scenario 테이블
class Scenario(Base):
    __tablename__ = "scenario"

    scenario_id = Column(Integer, primary_key=True, autoincrement=True)
    chat_id = Column(String(50), ForeignKey("chat_rooms.chat_id"), nullable=False)
    scenario_title = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)

# Fields 테이블
class Field(Base):
    __tablename__ = "fields"

    field_idx = Column(Integer, primary_key=True, autoincrement=True)
    field_category = Column(String(50), nullable=False)

# Tags 테이블
class Tag(Base):
    __tablename__ = "tags"

    tag_idx = Column(Integer, primary_key=True, autoincrement=True)
    char_idx = Column(Integer, ForeignKey("characters.char_idx"), nullable=False)
    tag_name = Column(String(50), nullable=False)
    tag_description = Column(Text, nullable=True)
    is_deleted = Column(Boolean, server_default=text("false"), nullable=False)

# Voice 테이블
class Voice(Base):
    __tablename__ = "voice"

    voice_idx = Column(String(50), primary_key=True)
    voice_path = Column(String(255), nullable=False)
    voice_speaker = Column(String(100), nullable=False)

# ChatLogs 테이블
class ChatLog(Base):
    __tablename__ = "chat_logs"

    session_id = Column(String(50), primary_key=True)
    chat_id = Column(String(50), ForeignKey("chat_rooms.chat_id"), nullable=False)
    log = Column(Text, nullable=False)
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

# Images 테이블
class Image(Base):
    __tablename__ = "images"

    img_idx = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(255), nullable=False)

# Chats 테이블
class ChatRoom(Base):
    __tablename__ = "chat_rooms"

    chat_id = Column(String(50), primary_key=True)
    user_idx = Column(Integer, ForeignKey("users.user_idx"), nullable=False)
    char_prompt_id = Column(Integer, ForeignKey("char_prompts.char_prompt_id"), nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)
    favorability = Column(Integer, server_default=text("0"), nullable=False)
    user_unique_name = Column(String(50), nullable=True)
    user_introduction = Column(Text, nullable=True)

# 파셜 인덱스 정의
# is_active가 true일 경우에만, user_idx와 char_prompt_id 조합 유니크 적용
# 이렇게 하면 채팅방 삭제(is_active = false)하더라도 새로운 채팅방 생성 가능
Index(
    "uq_user_char_prompt_active",
    ChatRoom.user_idx,
    ChatRoom.char_prompt_id,
    postgresql_where=and_(ChatRoom.is_active == True)
)

# ImageMapping 테이블
class ImageMapping(Base):
    __tablename__ = "image_mapping"

    char_idx = Column(Integer, ForeignKey("characters.char_idx"), primary_key=True, nullable=False)
    img_idx = Column(Integer, ForeignKey("images.img_idx"), primary_key=True, nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)

# CharacterPrompts 테이블
class CharacterPrompt(Base):
    __tablename__ = "char_prompts"

    char_prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    char_idx = Column(Integer, ForeignKey("characters.char_idx"), nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    character_appearance = Column(Text, nullable=False)
    character_personality = Column(Text, nullable=False)
    character_background = Column(Text, nullable=False)
    character_speech_style = Column(Text, nullable=False)
    example_dialogues = Column(ARRAY(Text), nullable=True)

# GroupChats 테이블
class GroupChat(Base):
    __tablename__ = "group_chats"

    group_chat_idx = Column(Integer, primary_key=True, autoincrement=True)
    user_idx = Column(Integer, ForeignKey("users.user_idx"), nullable=True)
    chat_title = Column(String(50), nullable=True)
    chat_prompt = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=True)
    is_deleted = Column(Boolean, server_default=text("false"), nullable=False)

# ScenarioPrompts 테이블
class ScenarioPrompt(Base):
    __tablename__ = "scenario_prompts"

    scenario_prompt_id = Column(Integer, primary_key=True, autoincrement=True)
    scenario_id = Column(Integer, ForeignKey("scenario.scenario_id"), nullable=False)
    prompt_text = Column(JSON, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

# Friends 테이블
class Friend(Base):
    __tablename__ = "friends"

    friend_idx = Column(Integer, primary_key=True, autoincrement=True)
    user_idx = Column(Integer, ForeignKey("users.user_idx"), nullable=False)
    char_idx = Column(Integer, ForeignKey("characters.char_idx"), nullable=False)
    is_active = Column(Boolean, server_default=text("true"), nullable=False)

# SecretDiary 테이블
class SecretDiary(Base):
    __tablename__ = "secret_diary"

    diary_idx = Column(Integer, primary_key=True, autoincrement=True)
    session = Column(String(50), ForeignKey("chat_logs.session_id"), nullable=False)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)

# GroupChatCharacters 테이블
class GroupChatCharacter(Base):
    __tablename__ = "group_chat_characters"

    group_chars_idx = Column(Integer, primary_key=True, autoincrement=True)
    group_chat_idx = Column(Integer, ForeignKey("group_chats.group_chat_idx"), nullable=False)
    char_idx = Column(Integer, ForeignKey("characters.char_idx"), nullable=False)
    

# 캐릭터 이미지 생성 프롬프트
class ImagePrompt(Base):
    __tablename__ = "images_prompts"

    images_prompts_idx = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(Text, nullable=False)
    prompt_content = Column(Text, nullable=False)
    created_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    updated_at = Column(DateTime, server_default=text("CURRENT_TIMESTAMP"), nullable=False)
    version = Column(Integer, nullable=False)

# 테이블 생성
Base.metadata.create_all(bind=engine)
