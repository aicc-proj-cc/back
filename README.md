## 프로토타입 백엔드 시작하는 방법

- 1. 콘다 가상환경 생성  
conda create -n gganbu-test python=3.10.16 

- 2. 콘다 가상환경 실행  
conda activate gganbu-test

- 3. Git clone   
git clone 

- 4. back 디렉토리로 이동  
cd back

- 5. .env 파일 설정 ( 슬랙 공지 참고 )

- 6. 필수 라이브러리 설치  
pip install -r requirements.txt

- 7. app 디렉토리로 이동  
cd app

- 8. DB 생성  
python database.py

- 9. 백엔드 실행(uvicorn 이용)  
uvicorn main:app --reload