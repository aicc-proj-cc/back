from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session, joinedload
from wordcloud import WordCloud
from fastapi.responses import FileResponse
from io import BytesIO
from sqlalchemy import Column, Integer, String, Text, ForeignKey
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
import os
from datetime import datetime, timedelta
from sqlalchemy.orm import sessionmaker
import shutil
from pydantic import BaseModel
from sqlalchemy.ext.declarative import declarative_base
import re
from database import SessionLocal, ChatRoom, ChatLog
from collections import Counter
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt


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

UPLOAD_DIR = "media"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@router.post("/upload-image/", response_model=dict)
def upload_image(file: UploadFile = File(...)):
    try:
        # 업로드 디렉토리 생성
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # 파일 저장 경로
        file_location = f"{UPLOAD_DIR}/{file.filename}"
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 성공 메시지 반환
        return {"message": f"파일 '{file.filename}'이 '{file_location}'에 저장되었습니다."}
    except Exception as e:
        print(f"파일 업로드 처리 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {str(e)}")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def decode_token(token: str):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_idx: int = payload.get("user_idx")
        if user_idx is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return user_idx
    except JWTError:
        raise HTTPException(status_code=401, detail="Could not validate token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    return decode_token(token)

def preprocess_korean_text(logs_text):
    # 한글 텍스트 전처리: 한글만 추출
    words = re.findall(r'[가-힣]+', logs_text)  # 한글만 추출
    
    # 한국어 불용어 목록
    korean_stopwords = set([
        "은", "는", "이", "가", "을", "를", "에", "의", "와", "과", 
        "도", "로", "에서", "에게", "한", "하다", "있다", "합니다",
        "했다", "하지만", "그리고", "그러나", "때문에", "한다", "것", 
        "같다", "더", "못", "이런", "저런", "그런", "어떻게", "왜"
    ])
    
    # 불용어 제거
    filtered_words = [word for word in words if word not in korean_stopwords]
    return filtered_words

@router.get("/user-wordcloud/{user_idx}", response_class=FileResponse)
def generate_user_wordcloud(user_idx: int, db: Session = Depends(get_db)):
    try:
        # 해당 User_idx의 chat_id 가져오기
        chat_ids = db.query(ChatRoom.chat_id).filter(ChatRoom.user_idx == user_idx).all()
        if not chat_ids:
            raise HTTPException(status_code=404, detail="해당 User_idx에 대한 채팅 데이터가 없습니다.")

        chat_ids = [chat_id[0] for chat_id in chat_ids]  # 결과를 리스트로 변환

        # chat_id에 해당하는 로그 가져오기
        logs = db.query(ChatLog.log).filter(ChatLog.chat_id.in_(chat_ids)).all()
        if not logs:
            raise HTTPException(status_code=404, detail="해당 User_idx에 대한 로그 데이터가 없습니다.")

        logs_text = " ".join([log[0] for log in logs])  # 모든 로그를 하나의 문자열로 결합

        # 텍스트 전처리 (한국어 기준)
        words = preprocess_korean_text(logs_text)

        # 단어 빈도 계산
        word_frequencies = Counter(words)

        # 워드 클라우드 생성
        font_path = "C:\\Windows\\Fonts\\malgun.ttf"  # 한글 지원 폰트 경로
        if not os.path.exists(font_path):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

        if not os.path.exists(font_path):
            raise HTTPException(status_code=500, detail="폰트 파일이 없습니다.")

        wordcloud = WordCloud(
            width=800,
            height=400,
            background_color="white",
            font_path=font_path,
            max_words=200
        ).generate_from_frequencies(word_frequencies)

        # 결과 저장 및 반환
        output_path = "user_wordcloud.png"
        wordcloud.to_file(output_path)
        return FileResponse(output_path, media_type="image/png", filename="user_wordcloud.png")

    except Exception as e:
        print(f"Error in generate_user_wordcloud: {e}")
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")