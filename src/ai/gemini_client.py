"""Gemini API 세션 통신 및 바이브 코딩 연동 클라이언트 모듈.

Thinking Budget을 비활성화하여 저지연(Low-Latency) 코드 생성을 수행하며,
특정 모델 과부하(503) 시 대기열 없는 최적 플래시 모델로 자동 장애조치(Failover)합니다.
"""

from typing import Any, Dict, Optional
import time
import streamlit as st
from google import genai

from src.ai.prompt_templates import VIBE_SYSTEM_PROMPT, format_weight_function_prompt

_CACHED_CLIENT: Optional[genai.Client] = None


def get_gemini_api_key() -> Optional[str]:
    """Streamlit secrets 또는 설정에서 Gemini API 키를 조회합니다."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if api_key:
        return str(api_key).strip()

    gemini_sec = st.secrets.get("gemini", {})
    if isinstance(gemini_sec, dict) and "api_key" in gemini_sec:
        return str(gemini_sec["api_key"]).strip()

    return None


def get_gemini_client() -> Optional[genai.Client]:
    """초기화된 최신 genai.Client 인스턴스를 반환합니다."""
    global _CACHED_CLIENT
    if _CACHED_CLIENT is not None:
        return _CACHED_CLIENT

    api_key = get_gemini_api_key()
    if not api_key:
        return None

    try:
        _CACHED_CLIENT = genai.Client(api_key=api_key)
        return _CACHED_CLIENT
    except Exception:
        return None


def is_gemini_available() -> bool:
    """Gemini API 클라이언트의 사용 가능 여부를 판정합니다."""
    return get_gemini_client() is not None


def generate_vibe_code(
    user_requirements: str,
    student_profile: Optional[Dict[str, Any]] = None,
    weather_info: Optional[Dict[str, Any]] = None,
) -> str:
    """학생 요구사항과 환경 변수를 반영하여 초고속으로 가중치 함수 코드를 생성합니다."""
    client = get_gemini_client()

    fallback_code = (
        "```python\n"
        "def custom_weight_function(u, v, edge_dict):\n"
        "    length = edge_dict.get('length', 1.0)\n"
        "    slope = edge_dict.get('slope', 0.0)\n"
        "    surface = edge_dict.get('surface_type', 'concrete_walkway')\n"
        "    is_shaded = edge_dict.get('is_shaded', False)\n\n"
        "    surface_mult = 0.85 if surface == 'urethane_track' else 1.15\n"
        "    shade_mult = 0.9 if is_shaded else 1.1\n"
        "    slope_mult = 1.0 + max(0.0, slope) * 0.06\n\n"
        "    return length * surface_mult * shade_mult * slope_mult\n"
        "```\n"
    )

    if not client:
        return f"⚠️ **Gemini API 키 미설정으로 기본 템플릿 코드를 반환합니다.**\n\n{fallback_code}"

    try:
        formatted_prompt = format_weight_function_prompt(
            user_input=user_requirements,
            student_profile=student_profile or {},
            weather_data=weather_info or {},
        )
    except Exception:
        formatted_prompt = (
            f"[학생 요구사항]: {user_requirements}\n"
            f"[체력 정보]: {student_profile}\n"
            f"[기상 정보]: {weather_info}\n"
            "위 조건을 만족하는 NetworkX용 custom_weight_function 코드를 작성하세요."
        )

    # Thinking 지연 끄기
    config = genai.types.GenerateContentConfig(
        system_instruction=VIBE_SYSTEM_PROMPT,
        temperature=0.1,
        thinking_config=genai.types.ThinkingConfig(thinking_budget=0),
    )

    # 트래픽 분산 우선순위: 3.5 Flash / 3.1 Flash-Lite 우선 호출 후 3.8 시도
    active_models = [
        "gemini-3.5-flash",
        "gemini-3.1-flash-lite",
        "gemini-3.8-flash",
        "gemini-flash-latest",
    ]

    last_error_msg = ""
    for model_name in active_models:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=formatted_prompt,
                config=config,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_error_msg = str(e)
            continue

    return f"⚠️ **Gemini API 응답 지연({last_error_msg})으로 안전 기본 템플릿을 적용합니다.**\n\n{fallback_code}"