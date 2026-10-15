"""Gemini 응답 텍스트 기반 파이썬 코드 블록 추출 및 정제 모듈.

대화형 LLM이 반환한 마크다운 텍스트 내에서 ```python ... ``` 형태의 코드 블록을
탐색·추출하고, 블록 기호 누락이나 잔여 설명 텍스트를 제거하여
구문 분석(AST) 가능한 순수 파이썬 소스코드 형태로 정제합니다.
"""

import re
from typing import Optional


def extract_vibe_function_code(llm_response_text: str) -> Optional[str]:
    """LLM 응답에서 custom_weight_function 함수 정의가 포함된 파이썬 소스코드를 추출합니다.

    Args:
        llm_response_text: Gemini 모델의 전체 텍스트 응답

    Returns:
        정제된 파이썬 함수 소스코드 문자열 또는 None
    """
    if not llm_response_text or not llm_response_text.strip():
        return None

    # 1. 마크다운 코드 블록(```python ... ``` 또는 ``` ... ```) 정규식 추출
    markdown_pattern = r"```(?:python)?\s*([\s\S]*?)\s*```"
    code_blocks = re.findall(markdown_pattern, llm_response_text, re.IGNORECASE)

    for block in code_blocks:
        cleaned_block = block.strip()
        if "def custom_weight_function" in cleaned_block:
            return sanitize_extracted_code(cleaned_block)

    # 2. 마크다운 백틱 표기가 누락되었으나 본문에 함수 정의가 포함된 경우
    if "def custom_weight_function" in llm_response_text:
        lines = llm_response_text.splitlines()
        extracted_lines = []
        is_capturing = False

        for line in lines:
            if "def custom_weight_function" in line:
                is_capturing = True

            if is_capturing:
                # 함수 내부 또는 인접 주석/공백 라인 수집
                # 코드 블록 외 새로운 한글 설명 섹션 시작 시 안전하게 수집 종료
                if line.startswith("#") or line.startswith(" ") or line.startswith("\t") or line.startswith("def ") or line.strip() == "":
                    extracted_lines.append(line)
                elif line.strip().startswith("import ") or line.strip().startswith("from "):
                    extracted_lines.append(line)
                else:
                    # 들여쓰기가 끝난 일반 자연어 텍스트 문장이 나오면 종료
                    if extracted_lines and not line.startswith(" "):
                        break

        candidate_code = "\n".join(extracted_lines).strip()
        if candidate_code:
            return sanitize_extracted_code(candidate_code)

    return None


def sanitize_extracted_code(raw_code: str) -> str:
    """추출된 코드에서 불필요한 앞뒤 백틱, 제어 문자 등을 정리합니다.

    Args:
        raw_code: 원본 추출 소스코드

    Returns:
        안정화된 파이썬 소스코드 문자열
    """
    lines = raw_code.splitlines()
    cleaned_lines = []

    for line in lines:
        stripped = line.strip()
        # 잔여 백틱 제거
        if stripped.startswith("```") or stripped.endswith("```"):
            continue
        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()