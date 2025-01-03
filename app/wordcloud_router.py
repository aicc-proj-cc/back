from fastapi import APIRouter, HTTPException, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.future import select
from sqlalchemy.orm import Session
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
from database import SessionLocal,Character
from dotenv import load_dotenv

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

@router.get("/wordcloud", response_class=FileResponse)
def generate_wordcloud(db: Session = Depends(get_db)):
    try:
        characters = db.query(Character).all()
        if not characters:
            raise HTTPException(status_code=404, detail="캐릭터 데이터가 없습니다.")

        word_frequencies = {character.char_name: character.follows for character in characters}
        font_path = "C:\\Windows\\Fonts\\malgun.ttf"  # Windows
        if not os.path.exists(font_path):
            font_path = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"  # Linux

        if not os.path.exists(font_path):
            raise HTTPException(status_code=500, detail="폰트 파일이 없습니다.")

        wordcloud = WordCloud(
            width=800, height=400, background_color="white", max_words=200,
            font_path=font_path
        ).generate_from_frequencies(word_frequencies)

        output_path = "wordcloud.png"
        wordcloud.to_file(output_path)
        return FileResponse(output_path, media_type="image/png", filename="wordcloud.png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"서버 오류: {str(e)}")
