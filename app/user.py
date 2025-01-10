from sqlalchemy import Boolean, DateTime, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.future import select
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from typing import Optional, List
from jose import jwt, JWTError
from datetime import datetime, timedelta
from fastapi.security import OAuth2PasswordBearer
# from main import get_db
import os
import shutil
from database import SessionLocal, User
from dotenv import load_dotenv


# Load environment variables
load_dotenv()

# Environment configurations
DATABASE_URL = os.getenv("DATABASE_URL")
SECRET_KEY = os.getenv("SECRET_KEY", "default_key")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 720
UPLOAD_DIR = "uploads"  # Directory for uploaded files

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

# OAuth2 Configuration
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="signin")


def create_access_token(data: dict, expires_delta: timedelta = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


class SignupRequest(BaseModel):
    nickname: str
    user_id: str
    profile_img: Optional[str] = None
    password: str


class UserResponse(BaseModel):
    user_idx: int
    nickname: str
    user_id: str
    profile_img: Optional[str] = None
    # is_active: bool
    # created_at: datetime

    class Config:
        from_attributes = True 


class SignInRequest(BaseModel):
    user_id: str
    password: str


router = APIRouter()


@router.post("/signup", response_model=dict)
def signup(signup_request: SignupRequest, db: Session = Depends(get_db)):
    try:
        # 기존 사용자 확인
        existing_user = db.query(User).filter(User.user_id == signup_request.user_id).first()

        if existing_user:
            raise HTTPException(status_code=400, detail="ID가 이미 존재합니다!")

        # 새 사용자 생성
        new_user = User(**signup_request.dict())
        db.add(new_user)
        db.commit()
        return {"message": "회원가입 성공"}
    except Exception as e:
        print(f"회원가입 처리 중 오류: {e}")  # 상세 오류 출력
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")




@router.post("/signin", response_model=dict)
def signin(signin_request: SignInRequest, db: Session = Depends(get_db)):
    try:
        # 사용자 조회
        user = db.query(User).filter(User.user_id == signin_request.user_id).first()
        if not user or user.password != signin_request.password:
            raise HTTPException(status_code=400, detail="잘못된 사용자 ID 또는 비밀번호입니다.")

        # 액세스 토큰 생성 (user_id와 user_idx 포함)
        token = create_access_token(data={"sub": user.user_id, "user_idx": user.user_idx})
        return {"message": "로그인 성공", "token": token}
    except Exception as e:
        print(f"로그인 처리 중 오류: {e}")  # 상세 오류 출력
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


@router.get("/verify-token", response_model=dict)
def verify_token(token: str = Depends(oauth2_scheme)):
    try:
        # JWT 토큰 디코딩
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        user_idx: int = payload.get("user_idx")  # user_idx 추출
        
        if not user_id or not user_idx:
            raise HTTPException(status_code=401, detail="유효하지 않은 토큰")
        expiration = payload.get("exp")
        if expiration and datetime.utcnow() > datetime.utcfromtimestamp(expiration):
            new_token = jwt.encode(
                {"user_idx": user_idx, "exp": datetime.utcnow() + timedelta(minutes=60)},
                SECRET_KEY,
                algorithm=ALGORITHM
            )
            return {"user_idx": user_idx, "new_token": new_token}
        
        # 토큰이 유효한 경우 user_idx 반환
        return {"message": "토큰이 유효합니다", "user_idx": user_idx}
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

@router.get("/users", response_model=List[UserResponse])
def get_all_users(db: Session = Depends(get_db)):
    try:
        # 모든 사용자 조회
        users = db.query(User).all()
        return [
            {
                "user_idx": user.user_idx,
                "user_id": user.user_id,
                "nickname": user.nickname,
                "profile_img": user.profile_img,
            }
            for user in users
        ]
    except Exception as e:
        print(f"사용자 목록 조회 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


@router.get("/users/{user_id}", response_model=UserResponse)
def get_user(user_id: int, db: Session = Depends(get_db)):
    try:
        # 사용자 조회
        user = db.query(User).filter(User.user_idx == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")
        
        # 사용자 반환
        return user
    except Exception as e:
        print(f"사용자 조회 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(user_id: str, user_update: SignupRequest, db: Session = Depends(get_db)):
    try:
        # 사용자 조회
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

        # 사용자 정보 업데이트
        for key, value in user_update.dict(exclude_unset=True).items():
            setattr(user, key, value)
        
        db.commit()
        db.refresh(user)

        # 업데이트된 사용자 반환
        return user
    except Exception as e:
        print(f"사용자 업데이트 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")



@router.delete("/users/{user_id}", response_model=dict)
def delete_user(user_id: str, db: Session = Depends(get_db)):
    try:
        # 사용자 조회
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

        # 사용자 삭제
        db.delete(user)
        db.commit()

        # 삭제 완료 메시지 반환
        return {"message": f"사용자 ID {user_id}가 삭제되었습니다."}
    except Exception as e:
        print(f"사용자 삭제 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"서버 내부 오류: {e}")


@router.post("/upload-profile-img/{user_id}/", response_model=dict)
def upload_profile_img(
    user_id: str,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    try:
        # 업로드 디렉토리 생성
        os.makedirs(UPLOAD_DIR, exist_ok=True)

        # 파일 저장 경로 설정
        file_location = f"{UPLOAD_DIR}/{file.filename}"
        with open(file_location, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 사용자 조회
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

        # 사용자 프로필 사진 업데이트
        user.profile_img = file_location
        db.commit()
        db.refresh(user)

        # 성공 메시지 반환
        return {"message": f"사용자의 프로필 사진이 저장되었습니다.", "profile_img": file_location}
    except Exception as e:
        print(f"파일 업로드 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"파일 업로드 실패: {str(e)}")



@router.get("/get-profile-img/{user_id}/", response_model=dict)
def get_profile_img(user_id: str, db: Session = Depends(get_db)):
    try:
        # 사용자 조회
        user = db.query(User).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(status_code=404, detail="사용자를 찾을 수 없습니다!")

        # 프로필 사진 확인
        if not user.profile_img:
            raise HTTPException(status_code=404, detail="프로필 사진이 등록되지 않았습니다.")

        # 성공 응답 반환
        return {
            "message": "사용자의 프로필 사진을 조회했습니다.",
            "profile_img": user.profile_img,
        }
    except Exception as e:
        print(f"프로필 사진 조회 중 오류: {e}")  # 디버깅용 로그
        raise HTTPException(status_code=500, detail=f"프로필 사진 조회 실패: {str(e)}")

    

