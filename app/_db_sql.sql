
DROP TABLE messages;

DROP TABLE chat_rooms;

CREATE TABLE chat_rooms (
    id VARCHAR(36) PRIMARY KEY,
	character_prompt TEXT NOT NULL,
	character_name VARCHAR(255) NOT NULL,
	character_image VARCHAR(255) NOT NULL,
	character_status_message VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE messages (
    id VARCHAR(36) PRIMARY KEY,
    room_id VARCHAR(36) REFERENCES chat_rooms(id),
    sender VARCHAR(255),
    content TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);


SELECT * FROM chat_rooms
SELECT * FROM messages




-- 캐릭터 챗봇 테이블
CREATE TABLE characters (
    character_index SERIAL PRIMARY KEY,       -- 캐릭터 인덱스, 고유한 값으로 자동 증가
    character_field VARCHAR(255) NOT NULL,   -- 캐릭터 필드 (장르)
    character_name VARCHAR(255) NOT NULL,    -- 캐릭터 이름
    character_description TEXT NOT NULL,     -- 캐릭터 설명
    character_status_message TEXT[] NOT NULL, -- 캐릭터 상태 메시지 (리스트 형식)
    character_created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, -- 캐릭터 생성 일자
    character_likes INTEGER DEFAULT 0,       -- 좋아요 숫자, 기본값 0
    is_active BOOLEAN DEFAULT TRUE,          -- 활성화 여부, 기본값 TRUE
    character_prompt TEXT NOT NULL,          -- 캐릭터 프롬프트
    character_image TEXT NOT NULL    -- 캐릭터 이미지 URL
);


-- 캐릭터 챗봇 예제 데이터 삽입
INSERT INTO characters (
    character_field,
    character_name,
    character_description,
    character_status_message,
    character_likes,
    character_prompt,
    character_image
) VALUES (
    'Fantasy', 
    'Miho', 
    'A cheerful and friendly chatbot who loves chatting with people.', 
    ARRAY['Available', 'Happy to chat'], 
    10, 
    'You are Miho, a cheerful chatbot that interacts in a friendly manner.', 
    'https://example.com/miho.png'
);

-- 캐릭터 챗봇 데이터 조회 예제
SELECT * FROM characters WHERE is_active = TRUE;