# 캐릭터 생성시, 첫 대사 1가지를 입력해야함.

from fastapi import FastAPI, Depends, HTTPException # FastAPI 프레임워크 및 종속성 주입 도구
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session # SQLAlchemy 세션 관리
from back.app._database import SessionLocal, ChatRoom, Message, Character # DB 세션과 모델 가져오기
from typing import List # 데이터 타입 리스트 지원
from pydantic import BaseModel, Field # 데이터 검증 및 스키마 생성용 Pydantic 모델
import uuid # 고유 ID 생성을 위한 UUID 라이브러리
from datetime import datetime # 날짜 및 시간 처리
from fastapi.middleware.cors import CORSMiddleware # CORS 설정용 미들웨어

import requests
# from auth import verify_token

# RabbitMQ 파트
import base64
import pika
import json
import time
import os

# FastAPI 앱 초기화
app = FastAPI()

# RabbitMQ 연결 설정
# RABBITMQ_HOST = "localhost"
RABBITMQ_HOST = "222.112.27.120"
RABBITMQ_PORT = os.getenv("RBMQ_PORT")
REQUEST_IMG_QUEUE = "image_generation_requests"
RESPONSE_IMG_QUEUE = "image_generation_responses"
REQUEST_TTS_QUEUE = "tts_generation_requests"
RESPONSE_TTS_QUEUE = "tts_generation_responses"


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
    character_likes: int  # 캐릭터 기본 호감도
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
    character_likes: int # 디폴트 호감도
    character_thumbs: int # 좋아요 수
    is_active: bool # 캐릭터 숨김 여부
    character_prompt: str # 캐릭터 프롬프트
    character_image: str # 캐릭터 이미지

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


# TTS 생성 요청 스키마
class TTSRequest(BaseModel):
    # TTS 관련 파라미터들
    # id: str
    text: str
    speaker: str = "paimon"
    language: str
    speed: float = 1.0


def get_rabbitmq_channel(req_que, res_que):
    """
    RabbitMQ 연결 및 채널 반환
    """
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=5675, heartbeat=6000)
    )
    channel = connection.channel()
    channel.queue_declare(queue=req_que, durable=True)
    channel.queue_declare(queue=res_que, durable=True)
    return connection, channel


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
        character_likes=character.character_likes,
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

@app.post("/api/chat/{room_id}")
def query_langchain(room_id: str, message: MessageSchema, db: Session = Depends(get_db)):
    """
    LangChain 서버에 요청을 보내기 전에 사용자 인증 검증.
    """
    # db 에서 채팅방 정보 불러오기
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

    # LangChain 서버로 요청 보내기
    bot_response = requests.post(
        f"{LANGCHAIN_SERVER_URL}/generate/",
        json={
            "user_message": message.content,
            "prompt": room.character_prompt,
            "character_name": room.character_name,
            "character_likes": room.character_likes,
        }
    )
    if bot_response.status_code != 200:
        raise HTTPException(status_code=bot_response.status_code, detail="LangChain 서버 요청 실패")

    # LangChain 서버 응답에서 텍스트 추출
    response_data = bot_response.json()  # JSON 데이터로 변환
    print("response_data", response_data)
    bot_response_text = response_data.get("text", "openai_api 에러가 발생했습니다.") # OpenAI로부터 받은 응답
    predicted_emotion = response_data.get("emotion", "Neutral")  # 캐릭터 기분 추출
    updated_likes = response_data.get("character_likes", room.character_likes)  # 업데이트된 호감도

    # 캐릭터 상태 업데이트
    room.character_likes = updated_likes
    room.character_emotion = predicted_emotion
    db.commit()  # 변경사항 저장

    # 캐릭터 응답 메세지 생성
    bot_message_id = str(uuid.uuid4()) # 고유 메시지 ID 생성
    bot_message = Message(
        id=bot_message_id, 
        room_id=room_id, 
        sender=room.character_name, # 캐릭터 이름
        content=bot_response_text
        )
    db.add(bot_message) # 캐릭터 응답 메시지 DB에 추가
    db.commit() # 변경사항 저장

    return {"user": message.content, "bot": bot_response_text, "updated_likes": updated_likes, "emotion": predicted_emotion} # 사용자와 봇의 메시지 반환 및 캐릭터 상태 업데이트 반환


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
        character_likes=character.character_likes, # 캐릭터 프롬프트
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
        character_likes=new_character.character_likes, # 캐릭터 호감도
        character_thumbs=new_character.character_thumbs, # 캐릭터 좋아요 수
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
            "character_thumbs": char.character_thumbs,
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


# 이미지 생성 요청 API
@app.post("/generate-image/")
def send_to_queue(request: ImageRequest):
    """
    RabbitMQ 큐에 이미지 생성 요청을 추가하고, 결과를 대기.
    """
    try:
        # RabbitMQ 연결
        # connection = pika.BlockingConnection(pika.ConnectionParameters(host=RABBITMQ_HOST))
        connection, channel = get_rabbitmq_channel(REQUEST_IMG_QUEUE, RESPONSE_IMG_QUEUE)
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
            routing_key=REQUEST_IMG_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=1),
        )
        print(f"이미지 생성 요청 전송: {request_id}")

        # 응답 큐에서 결과 대기
        for _ in range(6000):  # 최대 600초 대기 ( 100분 )
            method, properties, body = channel.basic_get(RESPONSE_IMG_QUEUE, auto_ack=True)
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
    


# 
# TTS 생성 요청 API
@app.post("/generate-tts/")
def send_to_queue(request: TTSRequest):
    try:
        connection, channel = get_rabbitmq_channel(REQUEST_TTS_QUEUE, RESPONSE_TTS_QUEUE)
        request_id = str(uuid.uuid4())
        message = {
            "id": request_id,
            "text": request.text,
            "speaker": request.speaker,
            "language": request.language,
            "speed": request.speed,
        }

        channel.basic_publish(
            exchange="",
            routing_key=REQUEST_TTS_QUEUE,
            body=json.dumps(message),
            properties=pika.BasicProperties(delivery_mode=1),
        )

        for _ in range(6000):  # 최대 600초 대기
            method, properties, body = channel.basic_get(RESPONSE_TTS_QUEUE, auto_ack=True)
            if body:
                response = json.loads(body)
                if response["id"] == request_id:
                    connection.close()
                    if response["status"] == "success":
                        audio_base64 = response["audio_base64"]
                        # print("audio_base64 ", audio_base64)
                        audio_data = base64.b64decode(audio_base64)

                        output_path = f"temp_audio/{request_id}.wav"
                        with open(output_path, "wb") as f:
                            f.write(audio_data)

                        return FileResponse(
                            path=output_path,
                            media_type="audio/wav",
                            filename="output_audio.wav"
                        )
                    else:
                        raise HTTPException(status_code=500, detail=response["error"])

        connection.close()
        raise HTTPException(status_code=504, detail="응답 시간 초과")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# uvicorn main:app --reload --log-level debug --port 8000