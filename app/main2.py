# 캐릭터 생성시, 첫 대사 1가지를 입력해야함.

from fastapi import FastAPI, Depends, HTTPException, APIRouter # FastAPI 프레임워크 및 종속성 주입 도구
from fastapi.responses import FileResponse

from sqlalchemy import select
from sqlalchemy.sql import func
from sqlalchemy.orm import Session # SQLAlchemy 세션 관리
<<<<<<< HEAD
from database import SessionLocal, ChatRoom, Character, CharacterPrompt, Voice, ChatLog, Field as DBField

 # DB 세션과 모델 가져오기
from typing import List # 데이터 타입 리스트 지원
=======

from database import SessionLocal, ChatRoom, Character, CharacterPrompt, Voice

 # DB 세션과 모델 가져오기
from typing import List, Optional # 데이터 타입 리스트 지원
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
from pydantic import BaseModel # 데이터 검증 및 스키마 생성용 Pydantic 모델
import uuid # 고유 ID 생성을 위한 UUID 라이브러리
from datetime import datetime # 날짜 및 시간 처리
from fastapi.middleware.cors import CORSMiddleware # CORS 설정용 미들웨어
import re
import websockets
import asyncio


# from auth import verify_token

# RabbitMQ 파트
import pika
import json
import time
import base64
import os

import user
import wordcloud_router
import follow
import search


# FastAPI 앱 초기화
app = FastAPI()

app.include_router(user.router)
app.include_router(wordcloud_router.router, prefix="/api", tags=["WordCloud"])
app.include_router(follow.router, tags=["Follow"])
app.include_router(search.router, tags=["Search"])

# RabbitMQ 연결 설정
# 배포용 PC 에 rabbitMQ 서버 및 GPU서버 세팅 완료 - 250102 민식 
# .env 파일 수정후 사용 (슬랙 공지 참고)
RABBITMQ_HOST = os.getenv("RBMQ_HOST")
RABBITMQ_PORT = os.getenv("RBMQ_PORT")
RABBITMQ_USER = os.getenv("RABBITMQ_USER", "guest")  # RabbitMQ 사용자 (기본값: guest)
RABBITMQ_PASSWORD = os.getenv("RABBITMQ_PASSWORD", "guest")  # RabbitMQ 비밀번호 (기본값: guest)

REQUEST_IMG_QUEUE = "image_generation_requests" # 이미지 요청
RESPONSE_IMG_QUEUE = "image_generation_responses" #
REQUEST_TTS_QUEUE = "tts_generation_requests" # TTS 요청
RESPONSE_TTS_QUEUE = "tts_generation_responses" #

# CORS 설정: 모든 도메인, 메서드, 헤더를 허용
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # 모든 도메인 허용
    allow_credentials=True, # 자격 증명 허용 (쿠키 등)
    allow_methods=["*"], # 모든 HTTP 메서드 허용 (GET, POST 등)
    allow_headers=["*"], # 모든 HTTP 헤더 허용
    expose_headers=["*"]
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
<<<<<<< HEAD
    user_idx: str
    field_idx: int
    voice_idx: str
    char_name: str
    char_description: str
    character_appearance: str
    character_personality: str
    character_background: str
    character_speech_style: str
    example_dialogues: List[dict]
    nicknames: dict
=======
    character_owner: str
    field_idx: str
    voice_idx: str
    char_name: str
    char_description: str
    nickname: Optional[dict] = None
    character_appearance: dict
    character_personality: dict
    character_background: dict
    character_speech_style: dict
    example_dialogues: Optional[List[dict]] = None
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7

# 캐릭터 응답 스키마
class CharacterResponseSchema(BaseModel):
    """
    클라이언트에 반환되는 캐릭터 정보 스키마.
    """
    char_idx: int
    char_name: str
    char_description: str
    created_at: str
<<<<<<< HEAD
    character_appearance: str
    character_personality: str
    character_background: str
    character_speech_style: str
    example_dialogues: List[dict]
    nicknames: dict
=======
    nickname: dict
    character_appearance: dict
    character_personality: dict
    character_background: dict
    character_speech_style: dict
    example_dialogues: Optional[List[dict]] = None
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7

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
    speaker: str = "bingsu"
    language: str
    speed: float = 1.0

# image, tts 큐 분리하기위한 코드 추가 - 1230 민식 
def get_rabbitmq_channel(req_que, res_que):
    """
    RabbitMQ 연결 및 채널 반환
    """

    credentials = pika.PlainCredentials(RABBITMQ_USER, RABBITMQ_PASSWORD)  # ID와 PW 설정

    connection = pika.BlockingConnection(
        pika.ConnectionParameters(
            host=RABBITMQ_HOST, 
            port=RABBITMQ_PORT, 
            credentials=credentials,
            heartbeat=6000)
    )
    channel = connection.channel()
    channel.queue_declare(queue=req_que, durable=True)
    channel.queue_declare(queue=res_que, durable=True)
    return connection, channel


# ====== API 엔드포인트 ======

# 채팅방 생성 API
@app.post("/api/chat-room/", response_model=dict)
def create_chat_room(room: CreateRoomSchema, db: Session = Depends(get_db)):
    try:
<<<<<<< HEAD
        # 캐릭터 정보 가져오기
        character = db.query(Character).filter(
            Character.char_idx == room.character_id, 
            Character.is_active == True
        ).first()
        
        if not character:
            raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
        
        # 프롬프트 정보 가져오기
        prompt = db.query(CharacterPrompt).filter(
            CharacterPrompt.char_prompt_id == character.char_idx
        ).first()

        if not prompt:
            raise HTTPException(status_code=404, detail="캐릭터 프롬프트를 찾을 수 없습니다.")

        # 채팅방 생성
        new_room = ChatRoom(
            chat_id=str(uuid.uuid4()),
            user_idx=1,  # TODO: 실제 사용자 ID로 교체 필요
            char_prompt_id=prompt.char_prompt_id,
            favorability=0
        )
=======
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
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
        
        # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨)
        db.commit()

        return {
<<<<<<< HEAD
            "chat_id": new_room.chat_id,
            "char_name": character.char_name,
            "character_personality": prompt.character_personality
=======
            "room_id": new_room.chat_id,
            "user_idx": new_room.user_idx,
            "character_idx": character.char_idx,
            "char_prompt_id": new_room.char_prompt_id,
            "created_at": new_room.created_at,
            "user_unique_name": new_room.user_unique_name,
            "user_introduction": new_room.user_introduction
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
        }
    except Exception as e:
        print(f"Error creating chat room: {str(e)}")
        db.rollback()
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
<<<<<<< HEAD
        # CharacterPrompt 및 Character 테이블과 연관된 데이터 가져오기
        character_prompt = db.query(CharacterPrompt).filter(CharacterPrompt.char_prompt_id == room.char_prompt_id).first()
        character = db.query(Character).filter(Character.char_idx == character_prompt.char_idx).first() if character_prompt else None

        if character:
            result.append({
                "room_id": room.chat_id,  # 수정된 필드 이름
                "character_name": character.char_name,
                "character_prompt": character_prompt.character_personality if character_prompt else "No prompt available",
                "created_at": room.created_at.isoformat() if room.created_at else "N/A",
            })
    return result
# rooms 반환 예시
# [ room01, room02, ... ]

# room01 반환 내용
# room_id : "채팅방 id (uuid)"
# character_name : "캐릭터 이름" 
# character_image : "이미지 url"
# character_prompt : "캐릭터 프롬프트"
# created_at : "생성날짜"

=======
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
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7

# ----------------------------------------수정 필요----------------------------------------
# 채팅 메시지 불러오기
@app.get("/api/chat/{room_id}")
def get_chat_logs(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방의 메시지 로그를 반환하는 API 엔드포인트.
    """
    logs = db.query(ChatLog).filter(ChatLog.chat_id == room_id).all()
    return [{"session_id": log.session_id, "log": log.log, "start_time": log.start_time, "end_time": log.end_time} for log in logs]

# ----------------------------------------수정 필요----------------------------------------
# 채팅방에서 캐릭터 정보 불러오기
@app.get("/api/chat-room-info/{room_id}")
def get_chat_room_info(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방의 정보를 반환하는 API 엔드포인트.
    """
    chat_room = db.query(ChatRoom).filter(ChatRoom.chat_id == room_id).first()
    if not chat_room:
        raise HTTPException(status_code=404, detail="해당 채팅방을 찾을 수 없습니다.")
    
        
    # voice 테이블에서 character_id와 연결된 TTS 정보 검색
    voice_info = db.query(Voice).filter(Voice.voice_idx == chat_room.voice_idx).first()
    print("voice_info :", voice_info)
    if not voice_info:
        raise HTTPException(status_code=404, detail="TTS 정보를 찾을 수 없습니다.")

    
    return {
        "room_id": chat_room.id,
        "character_name": chat_room.character_name,
        "character_emotion": chat_room.character_emotion,
        "character_likes": chat_room.character_likes,
        "character_voice": chat_room.character_voice,
        "voice_path": voice_info.voice_path, # TTS 모델 경로
        "voice_speaker": voice_info.voice_speaker, # TTS 스피커 이름
    }


# ----------------------------------------수정 필요----------------------------------------
# 채팅 전송 및 캐릭터 응답 - LangChain 서버 이용
LANGCHAIN_SERVER_URL = "http://localhost:8001"  # LangChain 서버 URL
WS_SERVER_URL = "ws://localhost:8001"  # LangChain 서버 URL

def get_chat_history(db: Session, room_id: str, limit: int = 10) -> str:
    """
    채팅방의 최근 대화 내역을 가져옵니다.
    """
    logs = db.query(ChatLog).filter(
        ChatLog.chat_id == room_id
    ).order_by(ChatLog.end_time.desc()).limit(limit).all()
    
    # 시간순으로 정렬
    logs = logs[::-1]
    
    # 대화 내역을 문자열로 포맷팅
    history = ""
    for log in logs:
        # ChatLog의 log 필드에서 대화 내용 파싱
        log_lines = log.log.split('\n')
        for line in log_lines:
            if 'user:' in line or 'chatbot:' in line:
                history += line + '\n'
    
    return history

async def send_to_langchain(request_data: dict, room_id: str):
    """
    LangChain WebSocket 서버에 데이터를 전송하고 응답을 반환.
    """
    try:
        uri = f"ws://localhost:8001/ws/generate/?room_id={room_id}"
        async with websockets.connect(uri) as websocket:
            # 요청 데이터 전송
            await websocket.send(json.dumps(request_data))
            
            # 서버 응답 수신
            response = await websocket.recv()
            return json.loads(response)
    except asyncio.TimeoutError:
        print("WebSocket 응답 시간이 초과되었습니다.")
        raise HTTPException(status_code=504, detail="LangChain 서버 응답 시간 초과.")
    except websockets.exceptions.ConnectionClosedError as e:
        print(f"WebSocket closed with error: {str(e)}")
        raise HTTPException(status_code=500, detail="WebSocket 연결이 닫혔습니다.")
    except Exception as e:
        print(f"Error in send_to_langchain: {str(e)}")
        raise HTTPException(status_code=500, detail="LangChain 서버와 통신 중 오류가 발생했습니다.")

# ----------------------------------------수정 필요----------------------------------------
@app.post("/api/chat/{room_id}")
async def query_langchain(room_id: str, message: MessageSchema, db: Session = Depends(get_db)):
    """
    LangChain 서버에 요청을 보내고 응답을 처리합니다.
    """
    try:
        # DB에서 채팅방과 캐릭터 정보 불러오기
        room = db.query(ChatRoom).filter(ChatRoom.chat_id == room_id).first()
        if not room:
            raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")

        # 캐릭터와 프롬프트 정보 가져오기
        character_prompt = db.query(CharacterPrompt).filter(
            CharacterPrompt.char_prompt_id == room.character_id
        ).first()

        if not character_prompt:
            raise HTTPException(status_code=404, detail="캐릭터 프롬프트를 찾을 수 없습니다.")

        # 사용자 메시지 생성
        session_id = str(uuid.uuid4())
        current_time = datetime.now()

        chat_log = ChatLog(
            session_id=session_id,
            chat_id=room_id,
            log=f"[{current_time.strftime('%Y-%m-%d %H:%M:%S')}] user: {message.content}\n",
            start_time=current_time,
            end_time=current_time
        )

        db.add(chat_log)
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

        # LangChain 서버와 WebSocket 통신
        response_data = await send_to_langchain(request_data, room_id)

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
            session_id=bot_message_id,
            chat_id=room_id,
            log=f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] chatbot: {bot_response_text}",
            start_time=datetime.now(),
            end_time=datetime.now()
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



from fastapi import File, UploadFile, Form

# 캐릭터 생성 api
@app.post("/api/characters/", response_model=CharacterResponseSchema)
async def create_character(
    character_image: UploadFile = File(...),
    character_data: str = Form(...),
    db: Session = Depends(get_db)
):
    try:
        with db.begin:
            print("Received character data:", character_data)  # 디버깅용 로그
            character_dict = json.loads(character_data)
            character = CreateCharacterSchema(**character_dict)
            nickname = character.nickname or {30: "stranger", 70: "friend", 100: "best friend"}

<<<<<<< HEAD
        # 새 캐릭터 객체 생성
        new_character = Character(
            character_owner=character.user_idx,
            field_idx=character.field_idx,
            voice_idx=character.voice_idx,
            char_name=character.char_name,
            char_description=character.char_description,
            nicknames=json.dumps(character.nicknames)
        )
=======
            # 새 캐릭터 객체 생성
            new_character = Character(
                user_idx=character.character_owner,
                field_idx=character.field_idx,
                voice_idx=character.voice_idx,
                char_name=character.char_name,
                char_description=character.char_description,
                nicknames=nickname,  # 기본값 적용
            )
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7

            db.add(new_character)
            db.flush()  # `new_character.char_idx`를 사용하기 위해 flush 실행

            def extract_description(data):
                """데이터에서 description 값을 추출하는 헬퍼 함수"""
                if isinstance(data, dict):
                    return data.get('description', '')
                try:
                    parsed = json.loads(data) if isinstance(data, str) else data
                    return parsed.get('description', str(data))
                except (json.JSONDecodeError, AttributeError):
                    return str(data)

<<<<<<< HEAD
        # 각 필드의 description 값을 추출하여 저장
        appearance_str = extract_description(character.character_appearance)
        personality_str = extract_description(character.character_personality)
        background_str = extract_description(character.character_background)
        speech_style_str = extract_description(character.character_speech_style)
        
        # 캐릭터 프롬프트 생성
        new_prompt = CharacterPrompt(
            char_idx=new_character.char_idx,
            character_appearance=character.character_appearance,
            character_personality=character.character_personality,
            character_background=character.character_background,
            character_speech_style=character.character_speech_style,
            example_dialogues=[json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues],
        )
=======
            # 각 필드의 description 값을 추출하여 저장
            appearance_str = extract_description(character.character_appearance)
            personality_str = extract_description(character.character_personality)
            background_str = extract_description(character.character_background)
            speech_style_str = extract_description(character.character_speech_style)
            
            # 캐릭터 프롬프트 생성
            new_prompt = CharacterPrompt(
                char_idx=new_character.char_idx,
                character_appearance=appearance_str,
                character_personality=personality_str,
                character_background=background_str,
                character_speech_style=speech_style_str,
                example_dialogues=(
                    [json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues]
                    if character.example_dialogues else None
                ),
            )
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7

            db.add(new_prompt)

        # 트랜잭션 커밋 (with 블록 종료 시 자동으로 커밋됨)
        db.commit()

        return CharacterResponseSchema(
            char_idx=new_character.char_idx,
            char_name=new_character.char_name,
            char_description=new_character.char_description,
            created_at=new_character.created_at.isoformat(),
<<<<<<< HEAD
            character_appearance=new_prompt.character_appearance,
            character_personality=new_prompt.character_personality,
            character_background=new_prompt.character_background,
            character_speech_style=new_prompt.character_speech_style,
            example_dialogues=[json.loads(dialogue) for dialogue in new_prompt.example_dialogues],
            nicknames=json.loads(new_character.nicknames)
=======
            nickname=new_character.nicknames,
            character_appearance={'description': appearance_str},
            character_personality={'description': personality_str},
            character_background={'description': background_str},
            character_speech_style={'description': speech_style_str},
            example_dialogues=[
                json.loads(dialogue) for dialogue in new_prompt.example_dialogues
            ] if new_prompt.example_dialogues else None,
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
        )
    except Exception as e:
        print(f"Error in create_character: {str(e)}")  # 디버깅용 로그
        db.rollback() # 트랜잭션 롤백
        raise HTTPException(status_code=500, detail=str(e))

def clean_json_string(json_string):
    if not json_string:
        return json_string
    return re.sub(r'[\x00-\x1F\x7F]', '', json_string)

# 캐릭터 목록 조회 API
@app.get("/api/characters/", response_model=List[CharacterResponseSchema])
def get_characters(db: Session = Depends(get_db)):
<<<<<<< HEAD
    characters = db.query(Character).filter(Character.is_active == True).all()
=======
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

    characters = query.all()

>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
    results = []

    for char in characters:
        prompt = db.query(CharacterPrompt).filter(CharacterPrompt.char_idx == char.char_idx).first()
        if prompt:
            example_dialogues = [json.loads(dialogue) for dialogue in prompt.example_dialogues] if prompt.example_dialogues else []
            nicknames = json.loads(char.nicknames) if char.nicknames else {'30': '', '70': '', '100': ''}
        else:
            example_dialogues = []
            nicknames = {'30': '', '70': '', '100': ''}

        results.append({
            "char_idx": char.char_idx,
            "char_name": char.char_name,
            "char_description": char.char_description,
            "created_at": char.created_at.isoformat(),
<<<<<<< HEAD
            "character_appearance": prompt.character_appearance if prompt else "",
            "character_personality": prompt.character_personality if prompt else "",
            "character_background": prompt.character_background if prompt else "",
            "character_speech_style": prompt.character_speech_style if prompt else "",
=======
            "nickname": char.nickname,
            "character_appearance": character_appearance,
            "character_personality": character_personality,
            "character_background": character_background,
            "character_speech_style": character_speech_style,
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7
            "example_dialogues": example_dialogues,
            "nicknames": nicknames
        })
    return results

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
<<<<<<< HEAD
    # 채팅방 ID를 기준으로 데이터베이스에서 채팅방 검색
    room = db.query(ChatRoom).filter(ChatRoom.chat_id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    
    # 채팅방에 연결된 캐릭터 검색
    character = db.query(Character).filter(Character.char_idx == room.char_prompt_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")

    
    # 캐릭터 정보를 반환
    return {
        "character_name": character.character_name,
        "character_prompt": character.character_prompt,
        "character_image": character.character_image,
    }
=======
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
>>>>>>> e6927b170da19efa8c02f9956821d06383689aa7


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
        print(f"TTS 요청 데이터: {message}")

        for _ in range(6000):  # 최대 600초 대기
            method, properties, body = channel.basic_get(RESPONSE_TTS_QUEUE, auto_ack=True)
            if body:
                response = json.loads(body)
                print(f"TTS 응답 데이터: {response}")
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
        print(f"Exception 발생: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# TTS 모델 정보 조회 API
@app.get("/api/ttsmodel/{room_id}")
def get_tts_model(room_id: str, db: Session = Depends(get_db)):
    """
    특정 채팅방에 연결된 캐릭터 및 TTS 모델 정보를 반환하는 API 엔드포인트.
    """
    # 채팅방 ID를 기준으로 데이터베이스에서 채팅방 검색
    room = db.query(ChatRoom).filter(ChatRoom.id == room_id).first()
    if not room:
        raise HTTPException(status_code=404, detail="채팅방을 찾을 수 없습니다.")
    
    # 채팅방에 연결된 캐릭터 검색
    character = db.query(Character).filter(Character.character_index == room.character_id).first()
    if not character:
        raise HTTPException(status_code=404, detail="캐릭터를 찾을 수 없습니다.")
    
    # `voice` 테이블에서 character_id와 연결된 TTS 정보 검색
    voice_info = db.query(Voice).filter(Voice.voice_idx == room.character_voice).first()
    if not voice_info:
        raise HTTPException(status_code=404, detail="TTS 정보를 찾을 수 없습니다.")
    
    # 캐릭터 및 TTS 정보를 반환
    return {
        "character_name": character.character_name,
        "character_prompt": character.character_prompt,
        "character_image": character.character_image,
        "voice_path": voice_info.voice_path,
        "voice_speaker": voice_info.voice_speaker,
    }

@app.get("/api/voices/")
def get_voices(db: Session = Depends(get_db)):
    voices = db.query(Voice).all()
    return [{"voice_idx": str(voice.voice_idx), "voice_speaker": voice.voice_speaker} for voice in voices]

# 필드 항목 가져오기 API
@app.get("/api/fields/")
def get_fields(db: Session = Depends(get_db)):
    """
    필드 항목을 반환하는 API 엔드포인트.
    """
    try:
        fields = db.query(DBField).all()  # DBField로 변경
        return [{"field_idx": field.field_idx, "field_category": field.field_category} for field in fields]
    except Exception as e:
        print(f"Error in get_fields: {str(e)}")  # 에러 로깅 추가
        raise HTTPException(status_code=500, detail=str(e))


# app.include_router(user_router, tags=["users"])

@app.get("/")
async def root():
    return {"message": "Hello World"}

# uvicorn main:app --reload --log-level debug --port 8000