from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal, Image


# APIRouter 인스턴스 생성
router = APIRouter()

# 데이터베이스 세션 의존성
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# 이미지 데이터를 반환하는 API
@router.get("/images")
def get_images(db: Session = Depends(get_db)):
    try:
        images = db.query(Image).all()
        return [{"img_idx": image.img_idx, "file_path": image.file_path} for image in images]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# 모듈 속성으로 `router` 설정
routes = router
