# from fastapi import APIRouter
# from typing import List

# router = APIRouter()

# # 더미 데이터
# chat_rooms = [
#     {"id": "room1", "name": "미오", "last_message": "응 나 방금 밥 먹었어", "timestamp": "11:45"},
#     {"id": "room2", "name": "마루", "last_message": "선물하고 간식먹어야지", "timestamp": "10:37"}
# ]

# @router.get("/api/chatrooms", response_model=List[dict])
# def get_chat_rooms():
#     return chat_rooms
