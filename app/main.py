# 캐릭터 생성시, 첫 대사 1가지를 입력해야함.

from fastapi import FastAPI, Depends, HTTPException, APIRouter # FastAPI 프레임워크 및 종속성 주입 도구
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session # SQLAlchemy 세션 관리
from database import SessionLocal, ChatRoom, Message, Character, CharacterPrompt, Voice

 # DB 세션과 모델 가져오기
from typing import List # 데이터 타입 리스트 지원
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
# RABBITMQ_HOST = "localhost"
RABBITMQ_HOST = "222.112.27.104"
RABBITMQ_PORT = os.getenv("RBMQ_PORT")
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
    character_id: int

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
    user_idx: str
    field_idx: str
    voice_idx: str
    char_name: str
    char_description: str
    character_status_message: List[str]
    favorability: int
    character_appearance: dict
    character_personality: dict
    character_background: dict
    character_speech_style: dict
    example_dialogues: List[dict]

# 캐릭터 응답 스키마
class CharacterResponseSchema(BaseModel):
    """
    클라이언트에 반환되는 캐릭터 정보 스키마.
    """
    char_idx: int
    char_name: str
    char_description: str
    character_status_message: List[str]
    created_at: str
    favorability: int
    character_appearance: dict
    character_personality: dict
    character_background: dict
    character_speech_style: dict
    example_dialogues: List[dict]

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

# image, tts 큐 분리하기위한 코드 추가 - 1230 민식 
def get_rabbitmq_channel(req_que, res_que):
    """
    RabbitMQ 연결 및 채널 반환
    """
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBITMQ_HOST, port=RABBITMQ_PORT, heartbeat=6000)
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
        # 캐릭터 정보 가져오기
        character = db.query(Character).filter(
            Character.char_idx == room.character_id, 
            Character.is_active == True
        ).first()
        
        if not character:
            raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
        
        # 채팅방 ID 생성
        room_id = str(uuid.uuid4())

        # 프롬프트 정보 가져오기
        character_prompt = db.query(CharacterPrompt).filter(
            CharacterPrompt.char_idx == character.char_idx
        ).first()

        if not character_prompt:
            raise HTTPException(status_code=404, detail="캐릭터 프롬프트를 찾을 수 없습니다.")

        # 채팅방 생성
        new_room = ChatRoom(
            id=room_id,
            character_prompt=str(character_prompt.character_personality),  # 프롬프트 정보
            character_id=character.char_idx,
            character_name=character.char_name,
            character_status_message=character.character_status_message,
            character_likes=character.favorability,
            character_image="placeholder_image_url",  # 기본 이미지 URL 설정
            character_voice=character.voice_idx # 캐릭터 목소리 모델 - TTS
        )
        
        db.add(new_room)
        db.commit()

        return {
            "id": room_id,
            "character_name": character.char_name,
            "character_prompt": str(character_prompt.character_personality),
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
        character = db.query(Character).filter(Character.char_idx == room.character_id).first()
        if character:
            result.append({
                "room_id": room.id,
                "character_name": character.char_name,
                "character_status_message": character.character_status_message,
                "character_prompt": character.current_prompt,
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
    
        
    # voice 테이블에서 character_id와 연결된 TTS 정보 검색
    voice_info = db.query(Voice).filter(Voice.voice_idx == chat_room.character_voice).first()
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


# 채팅 전송 및 캐릭터 응답 - LangChain 서버 이용
LANGCHAIN_SERVER_URL = "http://localhost:8001"  # LangChain 서버 URL

def get_chat_history(db: Session, room_id: str, limit: int = 10) -> str:
    """
    채팅방의 최근 대화 내역을 가져옵니다.
    """
    messages = db.query(Message).filter(
        Message.room_id == room_id
    ).order_by(Message.timestamp.desc()).limit(limit).all()
    
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
        user_message = Message(
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
        bot_message = Message(
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



@app.post("/api/characters/", response_model=CharacterResponseSchema)
def create_character(character: CreateCharacterSchema, db: Session = Depends(get_db)):
    import json

    # 새 캐릭터 객체 생성
    new_character = Character(
        user_idx=character.user_idx,
        field_idx=character.field_idx,
        voice_idx=character.voice_idx,
        char_name=character.char_name,
        char_description=character.char_description,
        character_status_message=character.character_status_message,
        favorability=character.favorability,
    )

    db.add(new_character)
    db.commit()
    db.refresh(new_character)

    # 딕셔너리를 직접 문자열로 변환
    appearance_str = json.dumps(character.character_appearance['description'] if isinstance(character.character_appearance, dict) else character.character_appearance, 
                              ensure_ascii=False)
    personality_str = json.dumps(character.character_personality['description'] if isinstance(character.character_personality, dict) else character.character_personality, 
                               ensure_ascii=False)
    background_str = json.dumps(character.character_background['description'] if isinstance(character.character_background, dict) else character.character_background, 
                              ensure_ascii=False)
    speech_style_str = json.dumps(character.character_speech_style['description'] if isinstance(character.character_speech_style, dict) else character.character_speech_style, 
                                ensure_ascii=False)
    
    # 캐릭터 프롬프트 생성
    new_prompt = CharacterPrompt(
        char_idx=new_character.char_idx,
        character_appearance=appearance_str,
        character_personality=personality_str,
        character_background=background_str,
        character_speech_style=speech_style_str,
        example_dialogues=[json.dumps(dialogue, ensure_ascii=False) for dialogue in character.example_dialogues],
    )

    db.add(new_prompt)
    db.commit()

    # 응답 형식으로 반환
    return CharacterResponseSchema(
        char_idx=new_character.char_idx,
        char_name=new_character.char_name,
        char_description=new_character.char_description,
        character_status_message=new_character.character_status_message,
        created_at=new_character.created_at.isoformat(),
        favorability=new_character.favorability,
        character_appearance={'description': appearance_str},
        character_personality={'description': personality_str},
        character_background={'description': background_str},
        character_speech_style={'description': speech_style_str},
        example_dialogues=[json.loads(dialogue) for dialogue in new_prompt.example_dialogues],
    )


# 캐릭터 목록 조회 API
@app.get("/api/characters/", response_model=List[CharacterResponseSchema])
def get_characters(db: Session = Depends(get_db)):
    characters = db.query(Character).filter(Character.is_active == True).all()
    results = []
    for char in characters:
        prompt = db.query(CharacterPrompt).filter(CharacterPrompt.char_idx == char.char_idx).first()
        if prompt:
            # JSON 문자열을 객체로 변환하고 description 키로 감싸기
            character_appearance = {"description": json.loads(prompt.character_appearance)} if prompt.character_appearance else None
            character_personality = {"description": json.loads(prompt.character_personality)} if prompt.character_personality else None
            character_background = {"description": json.loads(prompt.character_background)} if prompt.character_background else None
            character_speech_style = {"description": json.loads(prompt.character_speech_style)} if prompt.character_speech_style else None
            example_dialogues = [json.loads(dialogue) if dialogue else None for dialogue in prompt.example_dialogues] if prompt.example_dialogues else None
        else:
            character_appearance = character_personality = character_background = character_speech_style = example_dialogues = None

        results.append({
            "char_idx": char.char_idx,
            "char_name": char.char_name,
            "char_description": char.char_description,
            "character_status_message": char.character_status_message,
            "created_at": char.created_at.isoformat(),
            "favorability": char.favorability,
            "character_appearance": character_appearance,
            "character_personality": character_personality,
            "character_background": character_background,
            "character_speech_style": character_speech_style,
            "example_dialogues": example_dialogues,
        })
    return results

# 캐릭터 삭제 API
@app.delete("/api/characters/{char_idx}")
def delete_character(char_idx: int, db: Session = Depends(get_db)):
    """
    특정 캐릭터를 삭제(숨김처리)하는 API 엔드포인트.
    TODO : 현재는 실제로 삭제함. 위에 내용 처럼 변경해야함..
    """
    # 캐릭터 인덱스를 기준으로 데이터베이스에서 검색
    character = db.query(Character).filter(Character.char_idx == char_idx).first()
    if not character:
        raise HTTPException(status_code=404, detail="해당 캐릭터를 찾을 수 없습니다.")
    db.query(CharacterPrompt).filter(CharacterPrompt.char_idx == char_idx).delete()
    db.delete(character)
    db.commit()
    return {"message": f"캐릭터 {char_idx}가 성공적으로 삭제되었습니다."}

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
        "character_status_message": character.character_status_message
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
        "character_status_message": character.character_status_message,
        "voice_path": voice_info.voice_path,
        "voice_speaker": voice_info.voice_speaker,
    }


# app.include_router(user_router, tags=["users"])

@app.get("/")
async def root():
    return {"message": "Hello World"}

# uvicorn main:app --reload --log-level debug --port 8000