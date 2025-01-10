from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from database import SessionLocal, Image, ImageMapping, Character
from fastapi.responses import FileResponse
import os

# APIRouter 인스턴스 생성
router = APIRouter()

# 데이터베이스 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 특정 user_idx에 해당하는 이미지 데이터를 반환하는 API
@router.get("/images/user/{user_idx}")
def get_user_images(request: Request, user_idx: int, db: Session = Depends(get_db)):
    try:
        char_idxs = db.query(Character.char_idx).filter(Character.character_owner == user_idx).all()
        if not char_idxs:
            raise HTTPException(status_code=404, detail="해당 유저에 연결된 캐릭터가 없습니다.")
        
        images = (
            db.query(Image.img_idx, Image.file_path)
            .join(ImageMapping, ImageMapping.img_idx == Image.img_idx)
            .filter(ImageMapping.char_idx.in_([char[0] for char in char_idxs]))
            .all()
        )
        if not images:
            raise HTTPException(status_code=404, detail="해당 유저에 연결된 이미지가 없습니다.")

        base_url = str(request.base_url).rstrip("/")
        return [
            {"img_idx": img.img_idx, "file_path": f"{base_url}/images/{img.img_idx}"}
            for img in images
        ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    
@router.get("/images/{img_idx}")
def get_image(img_idx: int, db: Session = Depends(get_db)):
    # 데이터베이스에서 img_idx에 해당하는 이미지 경로 검색
    image = db.query(Image).filter(Image.img_idx == img_idx).first()

    if not image:
        raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")

    # 이미지 파일 경로 생성
    file_path = image.file_path

    # 이미지 파일이 존재하는지 확인
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="이미지 파일이 존재하지 않습니다.")

    # 이미지 파일 반환
    return FileResponse(file_path)