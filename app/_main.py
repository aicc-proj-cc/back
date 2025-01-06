# 캐릭터 생성시, 첫 대사 1가지를 입력해야함.

from fastapi import FastAPI, Depends, HTTPException # FastAPI 프레임워크 및 종속성 주입 도구
from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.orm import Session # SQLAlchemy 세션 관리
from database import SessionLocal, ChatRoom, ChatLog, Character, CharacterPrompt # DB 세션과 모델 가져오기
from typing import List, Optional # 데이터 타입 리스트 지원
from pydantic import BaseModel, Field # 데이터 검증 및 스키마 생성용 Pydantic 모델
import uuid # 고유 ID 생성을 위한 UUID 라이브러리
from datetime import datetime # 날짜 및 시간 처리
from fastapi.middleware.cors import CORSMiddleware # CORS 설정용 미들웨어

import requests
# from auth import verify_token

# RabbitMQ 파트
import pika
import json
import time

# FastAPI 앱 초기화
app = FastAPI()

# RabbitMQ 연결 설정
# RABBITMQ_HOST = "localhost"
RABBITMQ_HOST = "222.112.27.120"
REQUEST_QUEUE = "image_generation_requests"
RESPONSE_QUEUE = "image_generation_responses"

# CORS 설정: 모든 도메인, 메서드, 헤더를 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 모든 도메인 허용
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
    채팅방 생성을 위한 Pydantic 스키마
    """
    user_idx: int
    character_id: int
    user_unique_name: Optional[str] = None
    user_introduction: Optional[str] = None

    class Config:
        orm_mode = True


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
    character_owner: int
    field_idx: int
    voice_idx: str
    char_name: str
    char_description: str
    nickname: Optional[dict] = None
    character_appearance: str
    character_personality: str
    character_background: str
    character_speech_style: str
    example_dialogues: Optional[List[str]] = None

# 캐릭터 응답 스키마
class CharacterResponseSchema(BaseModel):
    """
    클라이언트에 반환되는 캐릭터 정보 스키마.
    """
    char_idx: int
    char_name: str
    char_description: str
    created_at: str
    nickname: dict
    character_appearance: str
    character_personality: str
    character_background: str
    character_speech_style: str
    example_dialogues: Optional[List[str]] = None

    class Config:
        orm_mode = True  # SQLAlchemy 객체 변환 지원
        json_encoders = {
            datetime: lambda v: v.isoformat()  # datetime 문자열로 변환
        }


# 이미지 생성 요청 스키마
class ImageRequest(BaseModel):
    prompt: str
    negative_prompt: str = "lowres, bad anatomy, bad hands, text, error, missing fingers, extra digit, fewer digits, cropped, worst quality, low quality, normal quality, jpeg artifacts, signature, watermark, username, blurry"
    width: int = 512
    height: int = 512
    guidance_scale: float = 12.0
    num_inference_steps: int = 60


def get_rabbitmq_channel():
    """
    RabbitMQ 연결 및 채널 반환
    """
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, heartbeat=6000)
    )
    channel = connection.channel()
    channel.queue_declare(queue=REQUEST_QUEUE, durable=True)
    channel.queue_declare(queue=RESPONSE_QUEUE, durable=True)
    return connection, channel


# ====== API 엔드포인트 ======

# 채팅방 생성 API
@app.post("/api/chat-room/", response_model=dict)
def create_chat_room(room: CreateRoomSchema, db: Session = Depends(get_db)):
    try:
        # 트랜잭션 시작
        with db.begin():
            # 각 캐릭터에 대한 최신 char_prompt_id를 가져오는 subquery
            subquery = (
                select(
                    CharacterPrompt.char_idx,
                    func.max(CharacterPrompt.created_at).label("latest_created_at")
                )
                .group_by(CharacterPrompt.char_idx)
                .subquery()
            )
            # 캐릭터 정보 가져오기
            character_data = (
                db.query(Character, CharacterPrompt)
                .join(subquery, subquery.c.char_idx == Character.char_idx)
                .join(
                    CharacterPrompt,
                    (CharacterPrompt.char_idx == subquery.c.char_idx) &
                    (CharacterPrompt.created_at == subquery.c.latest_created_at)
                )
                .filter(
                    Character.char_idx == room.character_id, 
                    Character.is_active == True
                )
                .first()
            )
            
            if not character_data:
                raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
            
            character, prompt = character_data
            
            # 채팅방 ID 생성
            room_id = str(uuid.uuid4())

            # 채팅방 생성
            new_room = ChatRoom(
                chat_id=room_id,
                user_idx=room.user_idx,
                char_prompt_id=prompt.char_prompt_id,
                user_unique_name=room.user_unique_name,
                user_introduction=room.user_introduction,
            )
            
            db.add(new_room)
        
        # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨)
        db.commit()

        return {
            "room_id": new_room.chat_id,
            "user_idx": new_room.user_idx,
            "character_idx": character.char_idx,
            "char_prompt_id": new_room.char_prompt_id,
            "created_at": new_room.created_at,
            "user_unique_name": new_room.user_unique_name,
            "user_introduction": new_room.user_introduction
        }
    except Exception as e:
        print(f"Error creating chat room: {str(e)}")  # 에러 로깅
        db.rollback()  # 트랜잭션 롤백
        raise HTTPException(status_code=500, detail=f"채팅방 생성 중 오류가 발생했습니다: {str(e)}")

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
        # 캐릭터 정보 가져오기
        character_data = (
            db.query(Character, CharacterPrompt)
            .join(CharacterPrompt, CharacterPrompt.char_idx == Character.char_idx)
            .join(ChatRoom, ChatRoom.char_prompt_id == CharacterPrompt.char_prompt_id)
            .filter(
                ChatRoom.chat_id == room.chat_id,
                Character.is_active == True
            )
            .first()
        )
        character, prompt = character_data
        if character:
            result.append({
                "room_id": room.chat_id,
                "character_name": character.char_name,
                "char_description": character.char_description,
                "character_appearance": prompt.character_appearance,
                "character_personality": prompt.character_personality,
                "character_background": prompt.character_background,
                "character_speech_style": prompt.character_speech_style,
                "room_created_at": room.created_at,
            })
    return result


# 채팅 메시지 불러오기
@app.get("/api/chat/{room_id}")
def get_chat_logs(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방의 메시지 로그를 반환하는 API 엔드포인트.
    """
    logs = db.query(ChatLog).filter(ChatLog.room_id == room_id).all() # 채팅방 ID에 맞는 메시지 가져오기
    return [{"sender": log.sender, "content": log.content, "timestamp": log.timestamp} for log in logs]

# 채팅방에서 캐릭터 정보 불러오기
@app.get("/api/chat-room-info/{room_id}")
def get_chat_room_info(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방의 정보를 반환하는 API 엔드포인트.
    """
    chat_room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not chat_room:
        raise HTTPException(status_code=404, detail="해당 채팅방을 찾을 수 없습니다.")

    return {
        "room_id": chat_room.id,
        "character_name": chat_room.character_name,
        "character_emotion": chat_room.character_emotion,
        "character_likes": chat_room.character_likes
    }


# 채팅 전송 및 캐릭터 응답 - LangChain 서버 이용
LANGCHAIN_SERVER_URL = "http://localhost:8001"  # LangChain 서버 URL

def get_chat_history(db: Session, room_id: str, limit: int = 10) -> str:
    """
    채팅방의 최근 대화 내역을 가져옵니다.
    """
    messages = db.query(ChatLog).filter(
        ChatLog.room_id == room_id
    ).order_by(ChatLog.timestamp.desc()).limit(limit).all()
    
    # 시간순으로 정렬
    messages = messages[::-1]
    
    # 대화 내역을 문자열로 포맷팅
    history = ""
    for msg in messages:
        history += f"{msg.sender}: {msg.content}\n"
    
    return history

@app.post("/api/chat/{room_id}")
def query_langchain(room_id: str, message: MessageSchema, db: Session = Depends(get_db)):
    """
    LangChain 서버에 요청을 보내고 응답을 처리합니다.
    """
    try:
        # DB에서 채팅방과 캐릭터 정보 불러오기
        room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")

        # 캐릭터와 프롬프트 정보 가져오기
        character_prompt = db.query(CharacterPrompt).filter(
            CharacterPrompt.char_idx == room.character_id
        ).first()

        if not character_prompt:
            raise HTTPException(status_code=404, detail="캐릭터 프롬프트를 찾을 수 없습니다.")

        # 사용자 메시지 생성
        message_id = str(uuid.uuid4())
        user_message = ChatLog(
            id=message_id,
            room_id=room_id,
            sender="user", 
            content=message.content
        )
        db.add(user_message)
        db.commit()

        # 대화 내역 가져오기
        chat_history = get_chat_history(db, room_id)
        print("Chat History being sent to LangChain:", chat_history)

        # JSON 문자열을 딕셔너리로 변환하고 description 키로 감싸기
        try:
            character_appearance = {"description": json.loads(character_prompt.character_appearance)} if character_prompt.character_appearance else None
            character_personality = {"description": json.loads(character_prompt.character_personality)} if character_prompt.character_personality else None
            character_background = {"description": json.loads(character_prompt.character_background)} if character_prompt.character_background else None
            character_speech_style = {"description": json.loads(character_prompt.character_speech_style)} if character_prompt.character_speech_style else None
            example_dialogues = [json.loads(dialogue) if dialogue else None for dialogue in character_prompt.example_dialogues] if character_prompt.example_dialogues else []
        except json.JSONDecodeError as e:
            raise HTTPException(status_code=500, detail=f"JSON 데이터 변환 오류: {str(e)}")

        # LangChain 서버로 보낼 요청 데이터 준비
        request_data = {
            "user_message": message.content,
            "character_name": room.character_name,
            "favorability": room.character_likes,
            "character_appearance": character_appearance,
            "character_personality": character_personality,
            "character_background": character_background,
            "character_speech_style": character_speech_style,
            "example_dialogues": example_dialogues,
            "chat_history": chat_history
        }
        print("Full request data:", request_data)  # 로그 추가

        print("Sending request to LangChain:", request_data)  # 디버깅용

        # LangChain 서버로 요청 보내기
        bot_response = requests.post(
            f"{LANGCHAIN_SERVER_URL}/generate/",
            json=request_data
        )

        if bot_response.status_code != 200:
            print("LangChain server error:", bot_response.text)  # 디버깅용
            raise HTTPException(status_code=bot_response.status_code, detail="LangChain 서버 요청 실패")

        # LangChain 서버 응답 처리
        response_data = bot_response.json()
        print("LangChain response:", response_data)  # 디버깅용

        bot_response_text = response_data.get("text", "openai_api 에러가 발생했습니다.")
        predicted_emotion = response_data.get("emotion", "Neutral")
        updated_favorability = response_data.get("favorability", room.character_likes)

        # 캐릭터 상태 업데이트
        room.character_likes = updated_favorability
        room.character_emotion = predicted_emotion
        db.commit()

        # 봇 응답 메시지 저장
        bot_message_id = str(uuid.uuid4())
        bot_message = ChatLog(
            id=bot_message_id,
            room_id=room_id,
            sender=room.character_name,
            content=bot_response_text
        )
        db.add(bot_message)
        db.commit()

        return {
            "user": message.content,
            "bot": bot_response_text,
            "updated_favorability": updated_favorability,
            "emotion": predicted_emotion
        }

    except Exception as e:
        print(f"Error in query_langchain: {str(e)}")  # 디버깅용
        raise HTTPException(status_code=500, detail=str(e))


# 캐릭터 생성 api
@app.post("/api/characters/", response_model=CharacterResponseSchema)
def create_character(character: CreateCharacterSchema, db: Session = Depends(get_db)):
    import json

    try:
        # 트랜잭션 시작
        with db.begin():
            # `nickname`에 기본값 설정
            nickname = character.nickname or {30: "손님", 70: "친구", 100: "소중한 친구"}

            # 새 캐릭터 객체 생성
            new_character = Character(
                character_owner=character.character_owner,
                field_idx=character.field_idx,
                voice_idx=character.voice_idx,
                char_name=character.char_name,
                char_description=character.char_description,
                nickname=nickname,  # 기본값 적용
            )
            db.add(new_character)
            db.flush()  # `new_character.char_idx`를 사용하기 위해 flush 실행

            # 캐릭터 프롬프트 생성
            new_prompt = CharacterPrompt(
                char_idx=new_character.char_idx,
                character_appearance=character.character_appearance,
                character_personality=character.character_personality,
                character_background=character.character_background,
                character_speech_style=character.character_speech_style,
                example_dialogues = (
                    [json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues]
                    if character.example_dialogues
                    else None
                )
            )
            db.add(new_prompt)

        # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨)
        db.commit()

        # 응답 형식으로 반환
        return CharacterResponseSchema(
            char_idx=new_character.char_idx,
            char_name=new_character.char_name,
            char_description=new_character.char_description,
            created_at=new_character.created_at.isoformat(),
            nickname=new_character.nicknames,
            character_appearance=new_prompt.character_appearance,
            character_personality=new_prompt.character_personality,
            character_background=new_prompt.character_background,
            character_speech_style=new_prompt.character_speech_style,
            example_dialogues=[
                json.loads(dialogue) for dialogue in new_prompt.example_dialogues
            ] if new_prompt.example_dialogues else None,
        )

    except Exception as e:
        # 트랜잭션 롤백
        db.rollback()
        raise e
    

# 캐릭터 목록 조회 API
@app.get("/api/characters/", response_model=List[CharacterResponseSchema])
def get_characters(db: Session = Depends(get_db)):
    # 각 캐릭터에 대한 최신 char_prompt_id를 가져오는 subquery
    subquery = (
        select(
            CharacterPrompt.char_idx,
            func.max(CharacterPrompt.created_at).label("latest_created_at")
        )
        .group_by(CharacterPrompt.char_idx)
        .subquery()
    )

    # 캐릭터를 최신 프롬프트와 join하는 query
    query = (
        db.query(Character, CharacterPrompt)
        .join(subquery, subquery.c.char_idx == Character.char_idx)
        .join(
            CharacterPrompt,
            (CharacterPrompt.char_idx == subquery.c.char_idx) &
            (CharacterPrompt.created_at == subquery.c.latest_created_at)
        )
        .filter(Character.is_active == True)  # is_active가 True인 캐릭터만 가져오기
    )

    results = query.all()
    print(results)

    # Transform into response model
    return [
        {
            "char_idx": character.char_idx,
            "char_name": character.char_name,
            "char_description":character.char_description,
            "created_at":character.created_at.isoformat(),
            "nickname":character.nickname,
            "character_appearance":prompt.character_appearance,
            "character_personality":prompt.character_personality,
            "character_background":prompt.character_background,
            "character_speech_style":prompt.character_speech_style,
            "example_dialogues":prompt.example_dialogues,
        }
        for character, prompt in results
    ]

# 캐릭터 삭제 API
@app.delete("/api/characters/{char_idx}")
def delete_character(char_idx: int, db: Session = Depends(get_db)):
    """
    특정 캐릭터를 삭제(숨김처리)하는 API 엔드포인트.
    캐릭터의 is_active 필드를 False로 변경합니다.
    """
    # 캐릭터 인덱스를 기준으로 데이터베이스에서 검색
    character = db.query(Character).filter(Character.char_idx == char_idx).first()
    if not character:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")

    # 캐릭터 숨김 처리
    character.is_active = False
    db.commit()
    return {"message": f"캐릭터 {char_idx}이(가) 성공적으로 삭제되었습니다."}

# 채팅방에 연결된 캐릭터 정보 조회 API
@app.get("/api/chat-room/{room_id}/character")
def get_room_character(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방에 연결된 캐릭터 정보를 반환하는 API 엔드포인트.
    """
    try:
        # 채팅방, 캐릭터 프롬프트, 캐릭터 정보를 가져오는 쿼리
        chat_data = (
            db.query(ChatRoom, CharacterPrompt, Character)
            .join(CharacterPrompt, ChatRoom.char_prompt_id == CharacterPrompt.char_prompt_id)
            .join(Character, CharacterPrompt.char_idx == Character.char_idx)
            .filter(ChatRoom.chat_id == room_id)
            .first()
        )

        if not chat_data:
            raise HTTPException(status_code=404, detail="해당 채팅방 정보를 찾을 수 없습니다.")

        # 데이터 분리
        chat, prompt, character = chat_data

        # 응답 데이터 구성
        return {
            "chat_id": chat.chat_id,
            "user_idx": chat.user_idx,
            "favorability": chat.favorability,
            "user_unique_name": chat.user_unique_name,
            "user_introduction": chat.user_introduction,
            "room_created_at": chat.created_at.isoformat(),
            "char_idx": character.char_idx,
            "char_name": character.char_name,
            "char_description": character.char_description,
            "character_appearance": prompt.character_appearance,
            "character_personality": prompt.character_personality,
            "character_background": prompt.character_background,
            "character_speech_style": prompt.character_speech_style,
            "example_dialogues": prompt.example_dialogues,
        }
    except Exception as e:
        print(f"Error fetching chat room info: {str(e)}")  # 에러 로깅
        raise HTTPException(status_code=500, detail=f"채팅방 정보를 가져오는 중 오류가 발생했습니다: {str(e)}")


# 이미지 생성 요청 API
@app.post("/generate-image/")
def send_to_queue(request: ImageRequest):
    """
    RabbitMQ 큐에 이미지 생성 요청을 추가하고, 결과를 대기.
    """
    try:
        # RabbitMQ 연결
        # connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        connection, channel = get_rabbitmq_channel()
        request_id = str(uuid.uuid4())

        # 요청 메시지 작성
        message = {
            "id": request_id,
            "prompt": request.prompt,
            "negative_prompt": request.negative_prompt,
            "width": request.width,
            "height": request.height,
            "guidance_scale": request.guidance_scale,
            "num_inference_steps": request.num_inference_steps,
        }

        # 메시지를 요청 큐에 추가
        channel.basic_publish(
            exchange="",
            routing_key=REQUEST_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=1),
        )
        print(f"이미지 생성 요청 전송: {request_id}")

        # 응답 큐에서 결과 대기
        for _ in range(6000):  # 최대 600초 대기 ( 100분 )
            method, properties, body = channel.basic_get(RESPONSE_QUEUE, auto_ack=True)
            if body:
                response = json.loads(body)
                if response["id"] == request_id:
                    connection.close()
                    return {"image": response["image"]}
            time.sleep(1)

        connection.close()
        raise HTTPException(status_code=504, detail="응답 시간 초과")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    


# uvicorn main:app --reload --log-level debug --port 8000