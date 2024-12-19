import openai
import os
from dotenv import load_dotenv
from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI

# 환경 변수 불러오기
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# LangChain을 위한 LLM 객체 생성
llm = ChatOpenAI(model="gpt-4o-mini", openai_api_key=openai.api_key)

def get_openai_response(prompt: str, user_message: str, character_name: str) -> str:
    """
    OpenAI의 API를 사용하여 사용자 입력에 따라 캐릭터 챗봇이 응답을 생성

    Parameters:
        prompt (str): 캐릭터와 관련된 프롬프트 정보.
        user_message (str): 사용자가 입력한 메시지.
        character_name (str): 캐릭터 이름.

    Returns:
        str: GPT 모델이 생성한 응답.
    """
    # print('prompt :', prompt)
    # print('character :', character_name)
    # print('user_input :', user_message)

    # 캐릭터에 해당하는 프롬프트 템플릿 생성
    character_prompt_template = """
    You are now a fictional character. The information about the character is as follows: {prompt}.
    Act as if you are the actual character, and respond to the user's message in a manner that the character would likely respond.
    The character's name is {character_name}.

    User input: {user_message}
    """

    # 템플릿을 채워서 완성된 프롬프트 생성
    character_prompt = PromptTemplate(
        template=character_prompt_template,
        input_variables=["prompt", "character_name", "user_message"]
    )

    # LLMChain 생성
    chain = LLMChain(llm=llm, prompt=character_prompt)

    try:
        # 체인을 통해 결과 생성
        response = chain.invoke({
            "prompt": prompt,
            "character_name": character_name,
            "user_message": user_message
        })
        return response.get("text", "openai_api 에러가 발생했습니다.")  # OpenAI API 응답 내용 반환
    except Exception as e:
        return f"Error: {str(e)}"


