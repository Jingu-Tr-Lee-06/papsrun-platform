"""PAPSrun 지능형 바이브 코더 모듈.

Ubuntu 랩 서버의 Ollama Qwen2.5:3b-4k와 통신하여 학생의 자연어 요구사항을 바탕으로
모듈 코드 생성, 코드 리뷰, 최적화 제안을 수행합니다.
"""

import json
import os
import re
from typing import Any, Dict, List, Optional
import requests
import streamlit as st


def _get_ollama_base_url() -> str:
    """Streamlit Secrets 또는 기본 Funnel URL에서 Ollama 엔드포인트를 가져옵니다."""
    return st.secrets.get("OLLAMA_BASE_URL", "https://lab-server.crayfish-coho.ts.net").rstrip("/")


def _call_ollama_generate(
    system_prompt: str,
    user_content: str,
    model_name: str = "qwen2.5:3b-4k",
    temperature: float = 0.3,
    max_tokens: int = 500,
) -> str:
    """Ollama API의 /api/generate 엔드포인트를 호출하여 결과를 텍스트로 반환합니다."""
    url = f"{_get_ollama_base_url()}/api/generate"
    payload = {
        "model": model_name,
        "prompt": user_content,
        "system": system_prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }
    try:
        response = requests.post(url, json=payload, timeout=30.0)
        if response.status_code == 200:
            return response.json().get("response", "").strip()
        return f"# [AI 서버 오류] 상태 코드: {response.status_code}\n# {response.text[:200]}"
    except requests.exceptions.Timeout:
        return "# [AI 서버 오류] 응답 시간(30초) 초과"
    except requests.exceptions.ConnectionError:
        return "# [AI 서버 오류] Ollama 서버에 연결할 수 없습니다. Tailscale Funnel 상태를 확인하세요."
    except Exception as e:
        return f"# [AI 서버 오류] {str(e)}"


def generate_module_code(
    component_name: str,
    requirements: str,
    existing_code: Optional[str] = None,
    target_role: Optional[str] = None,
) -> Dict[str, Any]:
    """학생의 요구사항을 받아 완전한 파이썬 모듈 코드를 생성합니다."""
    system_prompt = (
        "당신은 고등학교 파이썬 교육용 러닝 최적화 플랫폼 PAPSrun의 전문 알고리즘 튜터입니다.\n"
        "학생의 자연어 요구사항을 바탕으로 안전하고 명확한 파이썬 함수/클래스를 작성해야 합니다.\n"
        "반드시 다음 원칙을 준수하세요:\n"
        "1. 방어적 프로그래밍(예외 처리, 0으로 나누기 방지, 음수 클램핑 등)을 철저히 반영합니다.\n"
        "2. 코드는 마크다운 코드 블록(```python ... ```)으로 감싸서 출력하세요.\n"
        "3. 코드 하단에 핵심 로직에 대한 간단한 주석이나 1~2문장의 교육적 설명을 덧붙이세요."
    )

    user_prompt = f"### 대상 컴포넌트: {component_name}\n"
    if target_role:
        user_prompt += f"### 담당 역할: {target_role}\n"
    if existing_code:
        user_prompt += f"### 기존 코드:\n```python\n{existing_code}\n```\n"
    user_prompt += f"### 구현 요구사항:\n{requirements}\n"

    raw_response = _call_ollama_generate(system_prompt, user_prompt, temperature=0.25, max_tokens=600)

    # 코드 블록 추출
    code_match = re.search(r"```python(.*?)```", raw_response, re.DOTALL)
    if code_match:
        extracted_code = code_match.group(1).strip()
        explanation = re.sub(r"```python.*?```", "", raw_response, flags=re.DOTALL).strip()
    else:
        extracted_code = raw_response
        explanation = "코드가 직접 생성되었습니다."

    return {
        "success": True if "오류" not in extracted_code else False,
        "code": extracted_code,
        "explanation": explanation,
        "raw_response": raw_response,
    }


def review_student_code(code: str, requirements: str) -> Dict[str, Any]:
    """학생이 작성한 코드를 요구사항과 대조하여 품질 및 논리 결함을 진단합니다."""
    system_prompt = (
        "당신은 학생들의 알고리즘 코드를 검토하는 친절한 교사입니다.\n"
        "코드의 물리/수학적 공식 반영 여부, 제로 디비전 및 결측값 방어 여부를 검토하고\n"
        "칭찬할 점, 보완할 점, 그리고 개선 방향을 3줄 이내로 명확하게 피드백하세요."
    )

    user_prompt = (
        f"### 요구사항:\n{requirements}\n\n"
        f"### 학생 코드:\n```python\n{code}\n```\n\n"
        "위 코드를 평가해 주세요."
    )

    feedback = _call_ollama_generate(system_prompt, user_prompt, temperature=0.3, max_tokens=350)

    return {
        "feedback": feedback,
    }


def optimize_vibe_prompt(rough_prompt: str) -> str:
    """학생이 입력한 모호하거나 단순한 프롬프트를 구체적인 AI 지시문으로 개선합니다."""
    system_prompt = (
        "당신은 프롬프트 엔지니어링 튜터입니다.\n"
        "학생이 입력한 짧거나 모호한 코딩 프롬프트를, AI가 정확한 파이썬 코드를 작성할 수 있도록\n"
        "입력 변수, 물리/수학 수식, 예외 방어 조건이 포함된 1~2개의 구체적인 지시 문장으로 다듬어주세요.\n"
        "결과 문장만 따옴표 안에 깔끔하게 출력하세요."
    )

    user_prompt = f"학생의 원본 프롬프트: '{rough_prompt}'"
    return _call_ollama_generate(system_prompt, user_prompt, temperature=0.4, max_tokens=200)