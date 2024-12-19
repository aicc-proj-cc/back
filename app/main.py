# 캐릭터 생성시, 첫 대사 1가지를 입력해야함.

from fastapi import FastAPI, Depends, HTTPException # FastAPI 프레임워크 및 종속성 주입 도구
from sqlalchemy.orm import Session # SQLAlchemy 세션 관리
from database import SessionLocal, ChatRoom, Message, Character # DB 세션과 모델 가져오기
from openai_api import get_openai_response  # OpenAI API / 캐릭터 챗봇 응답 반환
from typing import List # 데이터 타입 리스트 지원
from pydantic import BaseModel, Field # 데이터 검증 및 스키마 생성용 Pydantic 모델
import uuid # 고유 ID 생성을 위한 UUID 라이브러리
from datetime import datetime # 날짜 및 시간 처리
from fastapi.middleware.cors import CORSMiddleware # CORS 설정용 미들웨어


# FastAPI 앱 초기화
app = FastAPI()

# CORS 설정: 모든 도메인, 메서드, 헤더를 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 모든 도메인 허용
    allow_credentials=True, # 자격 증명 허용 (쿠키 등)
    allow_methods=["*"], # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"], # 모든 HTTP 헤더 허용
)


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

# ====== Pydantic 스키마 ======
## 스키마 사용 이유


# 채팅방 생성 요청 스키마
class CreateRoomSchema(BaseModel):
    """
    채팅방 생성을 위한 Pydantic 스키마.
    클라이언트가 전송해야 하는 필드를 정의.
    """
    character_id: int  # 캐릭터 ID (character_index)


# 메시지 전송 스키마
class MessageSchema(BaseModel):
    """
    메시지 전송을 위한 Pydantic 스키마.
    클라이언트가 전송해야 하는 필드를 정의
    """
    sender: str # 메세지 전송자 ( user 또는 캐릭터 이름 )
    content: str # 메세지 내용

# 캐릭터 생성 스키마
class CreateCharacterSchema(BaseModel):
    """
    캐릭터 등록을 위한 Pydantic 스키마.
    """
    character_field: str  # 캐릭터 필드(장르)
    character_name: str  # 캐릭터 이름
    character_description: str  # 캐릭터 설명
    character_status_message: List[str]  # 캐릭터 상태 메시지 (리스트 형식)
    character_prompt: str  # 캐릭터 프롬프트
    character_image: str  # 캐릭터 이미지 URL

# 캐릭터 응답 스키마
class CharacterResponseSchema(BaseModel):
    """
    클라이언트에 반환되는 캐릭터 정보 스키마.
    """
    character_index: int # 캐릭터 번호
    character_field: str # 캐릭터 필드
    character_name: str # 캐릭터 이름
    character_description: str # 캐릭터 설명
    character_status_message: List[str] # 캐릭터 상태 메시지
    character_created_at: str  # 문자열로 변환
    character_likes: int # 좋아요 수
    is_active: bool # 캐릭터 숨김 여부
    character_prompt: str # 캐릭터 프롬프트
    character_image: str # 캐릭터 이미지

    class Config:
        orm_mode = True  # SQLAlchemy 객체 변환 지원
        json_encoders = {
            datetime: lambda v: v.isoformat()  # datetime 문자열로 변환
        }


# ====== API 엔드포인트 ======

# 채팅방 생성 API
@app.post("/api/chat-room/", response_model=dict)
def create_chat_room(room: CreateRoomSchema, db: Session = Depends(get_db)):
    """
    새로운 채팅방을 생성하는 API 엔드포인트.
    요청에서 제공된 캐릭터 ID를 기반으로 캐릭터 데이터를 불러와 채팅방을 생성.
    """
    # 캐릭터 정보 가져오기
    character = db.query(Character).filter(
        Character.character_index == room.character_id, 
        Character.is_active == True
    ).first()
    
    if not character:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
    
    
    # 채팅방 ID 생성
    room_id = str(uuid.uuid4())

    # 채팅방 생성
    new_room = ChatRoom(
        id=room_id,
        character_prompt=character.character_prompt,
        character_id=character.character_index,
        character_name=character.character_name,
        character_image=character.character_image,
        character_status_message=character.character_status_message,  # ARRAY로 저장
    )
    db.add(new_room)
    db.commit()

    return {
        "id": room_id,
        "character_prompt": character.character_prompt,
        "character_name": character.character_name,
        "character_image": character.character_image,
        "character_status_message": character.character_status_message,
    }

# 채팅방 목록 조회 API
@app.get("/api/chat-room/")
def get_chat_rooms(db: Session = Depends(get_db)):
    """
    모든 채팅방 목록을 반환하는 API 엔드포인트.
    각 채팅방에 연결된 캐릭터 정보를 포함.
    """
    rooms = db.query(ChatRoom).all()
    result = []
    for room in rooms:
        character = db.query(Character).filter(Character.character_index == room.character_id).first()
        if character:
            result.append({
                "room_id": room.id,
                "character_name": character.character_name,
                "character_image": character.character_image,
                "character_status_message": character.character_status_message,
                "character_prompt": character.character_prompt,
                "created_at": room.created_at,
            })
    return result
# rooms 반환 예시
# [ room01, room02, ... ]

# room01 반환 내용
# room_id : "채팅방 id (uuid)"
# character_name : "캐릭터 이름" 
# character_image : "이미지 url"
# character_status_message : "캐릭터 상태 메세지?"
# character_prompt : "캐릭터 프롬프트"
# created_at : "생성날짜"


# 채팅 메시지 불러오기
@app.get("/api/chat/{room_id}")
def get_chat_logs(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방의 메시지 로그를 반환하는 API 엔드포인트.
    """
    logs = db.query(Message).filter(Message.room_id == room_id).all() # 채팅방 ID에 맞는 메시지 가져오기
    return [{"sender": log.sender, "content": log.content, "timestamp": log.timestamp} for log in logs]

# 메시지 전송 및 OpenAI 응답
@app.post("/api/chat/{room_id}/{character}")
def send_message(room_id: str, character: str, message: MessageSchema, db: Session = Depends(get_db)):
    """
    사용자의 메시지를 저장하고, OpenAI API로부터 캐릭터의 응답을 받아 저장.
    """

    # 채팅방 정보 가져오기
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    
    # 사용자 메시지 생성
    message_id = str(uuid.uuid4())  # 고유 메시지 ID 생성
    user_message = Message(
        id=message_id, 
        room_id=room_id, 
        sender="user", 
        content=message.content # 사용자 메시지 내용
        )
    db.add(user_message) # 사용자 메시지 DB에 추가
    db.commit() # 변경사항 저장

    # OpenAI API를 통해 캐릭터의 응답 생성
    bot_response = get_openai_response(
        prompt=room.character_prompt,
        user_message=message.content,
        character_name=room.character_name
        ) # 캐릭터 응답 생성 - 상단의 get_openai_response 라이브러리 참조
    bot_message_id = str(uuid.uuid4()) # 고유 메시지 ID 생성

    # 캐릭터 응답 메세지 생성
    bot_message = Message(
        id=bot_message_id, 
        room_id=room_id, 
        sender=character, # 캐릭터 이름
        content=bot_response # OpenAI로부터 받은 응답
        )
    db.add(bot_message) # 캐릭터 응답 메시지 DB에 추가
    db.commit() # 변경사항 저장

    return {"user": message.content, "bot": bot_response} # 사용자와 봇의 메시지 반환



# 캐릭터 생성 API
@app.post("/api/characters/", response_model=CharacterResponseSchema)
def create_character(character: CreateCharacterSchema, db: Session = Depends(get_db)):
    """
    새로운 캐릭터를 생성하는 API 엔드포인트.
    클라이언트가 전달한 데이터를 기반으로 캐릭터를 데이터베이스에 저장하고, 생성된 캐릭터 정보를 반환.
    """

    # 새 캐릭터 객체 생성
    new_character = Character(
        character_field=character.character_field, # 캐릭터 장르 또는 카테고리
        character_name=character.character_name, # 캐릭터 이름
        character_description=character.character_description, # 캐릭터 설명
        character_status_message=character.character_status_message, # 캐릭터 상태 메시지 (리스트)
        character_prompt=character.character_prompt, # 캐릭터 프롬프트
        character_image=character.character_image, # 캐릭터 이미지 주소
    )

    # DB에 저장 및 갱신
    db.add(new_character)
    db.commit()
    db.refresh(new_character)

    # 생성된 캐릭터 정보를 응답 형식으로 반환
    return CharacterResponseSchema(
        character_index=new_character.character_index,
        character_field=new_character.character_field,
        character_name=new_character.character_name,
        character_description=new_character.character_description,
        character_status_message=new_character.character_status_message,
        character_created_at=new_character.character_created_at.isoformat(),
        character_likes=new_character.character_likes, # 캐릭터 좋아요 수
        is_active=new_character.is_active, # 캐릭터 숨김 여부
        character_prompt=new_character.character_prompt,
        character_image=new_character.character_image,
    )


# 캐릭터 목록 조회 API
@app.get("/api/characters/", response_model=List[CharacterResponseSchema])
def get_characters(db: Session = Depends(get_db)):
    """
    활성화된 모든 캐릭터 목록을 반환하는 API 엔드포인트.
    데이터베이스에서 is_active=True 상태인 캐릭터를 필터링하여 반환.
    """

    # 활성화된 캐릭터를 데이터베이스에서 조회
    characters = db.query(Character).filter(Character.is_active == True).all()

    # 응답 데이터 변환
    return [
        {
            "character_index": char.character_index,
            "character_field": char.character_field,
            "character_name": char.character_name,
            "character_description": char.character_description,
            "character_status_message": char.character_status_message,
            "character_created_at": char.character_created_at.isoformat(),  # datetime -> string 변환
            "character_likes": char.character_likes,
            "is_active": char.is_active,
            "character_prompt": char.character_prompt,
            "character_image": char.character_image,
        }
        for char in characters
    ]

# 캐릭터 삭제 API
@app.delete("/api/characters/{character_index}")
def delete_character(character_index: int, db: Session = Depends(get_db)):
    """
    특정 캐릭터를 삭제(숨김처리)하는 API 엔드포인트.
    TODO : 현재는 실제로 삭제함. 위에 내용 처럼 변경해야함..
    """
    # 캐릭터 인덱스를 기준으로 데이터베이스에서 검색
    character = db.query(Character).filter(Character.character_index == character_index).first()
    if not character:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")

    # 캐릭터 삭제 (비활성화 처리)
    db.delete(character)
    db.commit()
    return {"message": f"캐릭터 {character_index}가 성공적으로 삭제되었습니다."}

# 채팅방에 연결된 캐릭터 정보 조회 API
@app.get("/api/chat-room/{room_id}/character")
def get_room_character(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방에 연결된 캐릭터 정보를 반환하는 API 엔드포인트.
    """
    # 채팅방 ID를 기준으로 데이터베이스에서 채팅방 검색
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    
    # 채팅방에 연결된 캐릭터 검색
    character = db.query(Character).filter(Character.character_index == room.character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    
    # 캐릭터 정보를 반환
    return {
        "character_name": character.character_name,
        "character_prompt": character.character_prompt,
        "character_image": character.character_image,
        "character_status_message": character.character_status_message,
    }