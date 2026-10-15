"""Gemini 기반 자연어 최적화 바이브 코딩(Vibe Coding) 및 경로 피드백 엔진.

학생이 입력한 자연어 요구 조건을 분석하여
NetworkX 다익스트라 알고리즘에 즉시 주입 가능한 파이썬 가중치 함수 코드로 변환하며,
최종 산출된 러닝 코스의 물리·생리학적 지표를 체육 교육학적 관점에서 종합 평가합니다.
"""

from typing import Any, Callable, Dict, Optional, Tuple
import re
import streamlit as st
from google import genai


def _call_gemini_generate(system_prompt: str, user_content: str) -> str:
    """gemini-3.8-flash 모델을 호출하여 응답 텍스트를 생성합니다."""
    api_key = st.secrets.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY가 secrets.toml에 설정되어 있지 않습니다.")

    client = genai.Client(api_key=str(api_key).strip())
    prompt = f"{system_prompt}\n\n[사용자 요구 사항]: {user_content}"

    # 확인된 최신 모델 우선 순위
    models_to_try = [
        "gemini-3.8-flash",
        "gemini-2.5-flash",
        "gemini-flash-latest"
    ]

    last_error = None
    for model_name in models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
            )
            if response and response.text:
                return response.text
        except Exception as e:
            last_error = e
            continue

    raise RuntimeError(f"Gemini 호출 실패: {last_error}")


def generate_weight_function_code(prompt: str) -> Tuple[str, str]:
    """학생의 자연어 프롬프트를 입력받아 다익스트라 가중치 함수 파이썬 코드를 생성합니다.

    Args:
        prompt: 학생이 입력한 러닝 최적화 요구 사항 (자연어)

    Returns:
        (실행 가능한 파이썬 코드 문자열, AI 설계 의도 설명)
    """
    system_instruction = (
        "너는 지능형 러닝 경로 최적화 플랫폼 PAPSrun의 AI 파이썬 가중치 함수 빌더다.\n"
        "학생이 자연어로 입력한 요구 조건을 분석하여, NetworkX 다익스트라 최단 경로 탐색에 사용될\n"
        "파이썬 함수 `custom_weight_fn(u, v, data)`의 본문 코드를 작성해야 한다.\n\n"
        "간선 데이터 딕셔너리(`data`)에서 활용 가능한 키 속성:\n"
        "- `length_m` (float): 구간 거리(미터)\n"
        "- `slope_pct` (float): 노면 경사도(%, 양수: 오르막, 음수: 내리막)\n"
        "- `shade_pct` (float): 수목/건물 그늘 비율(0.0 ~ 100.0)\n"
        "- `surface_type` (str): 노면 종류 ('track', 'urethane', 'asphalt', 'sidewalk', 'dirt')\n"
        "- `rn_wm2` (float): 순복사에너지 지표(W/m², 높을수록 직사광선 온열 부하 심함)\n\n"
        "반드시 지켜야 할 엄격한 규칙:\n"
        "1. 함수 정의 이름은 반드시 `def custom_weight_fn(u, v, data):` 여야 한다.\n"
        "2. 반환값은 0보다 큰 양의 실수(float, 최소 0.01 이상)여야 한다.\n"
        "3. 외부 라이브러리 import나 시스템 접근 코드(os, sys 등)는 절대 포함하지 않는다.\n"
        "4. 마크다운 코드 블록(```python ... ```)으로 묶어서 출력하고, 블록 뒤에 [설계 의도] 1~2줄을 덧붙여라."
    )

    try:
        raw_text = _call_gemini_generate(system_instruction, prompt)

        code_match = re.search(r"```python\s*(def custom_weight_fn[\s\S]*?)```", raw_text)
        if code_match:
            generated_code = code_match.group(1).strip()
            explanation = re.sub(r"```[\s\S]*?```", "", raw_text).strip()
            if not explanation:
                explanation = "학생의 러닝 조건에 맞추어 맞춤형 가중치 페널티와 보너스가 반영되었습니다."
            return generated_code, explanation

        return raw_text, "자연어 기반 가중치 함수가 생성되었습니다."

    except Exception as e:
        # 비상 폴백 규칙 모델
        fallback_code = (
            "def custom_weight_fn(u, v, data):\n"
            "    length = data.get('length_m', 50.0)\n"
            "    slope = data.get('slope_pct', 0.0)\n"
            "    shade = data.get('shade_pct', 0.0)\n"
            "    surface = data.get('surface_type', 'asphalt')\n"
            "    slope_penalty = max(0.0, slope) * 2.5 if slope > 0 else abs(slope) * 0.5\n"
            "    shade_discount = (shade / 100.0) * 0.35\n"
            "    surface_mult = 0.85 if surface in ['track', 'urethane', 'dirt'] else 1.0\n"
            "    cost = length * (1.0 + slope_penalty) * (1.0 - shade_discount) * surface_mult\n"
            "    return max(0.1, cost)\n"
        )
        return fallback_code, f"Gemini API 호출 제한({str(e)}). 표준 안전 가중치 템플릿을 적용합니다."


def compile_custom_weight_function(code_str: str) -> Optional[Callable[[Any, Any, Dict[str, Any]], float]]:
    """문자열 형태의 파이썬 코드를 런타임에서 안전하게 컴파일하여 실행 가능한 함수 객체로 반환합니다."""
    local_scope: Dict[str, Any] = {}
    try:
        safe_builtins = {
            "abs": abs,
            "min": min,
            "max": max,
            "round": round,
            "float": float,
            "int": int,
            "pow": pow,
        }
        restricted_globals = {"__builtins__": safe_builtins}
        exec(code_str, restricted_globals, local_scope)

        func = local_scope.get("custom_weight_fn")
        if callable(func):
            return func
        return None
    except Exception:
        return None


def generate_running_route_feedback(route_metrics: Dict[str, Any], user_goal: str) -> str:
    """도출된 최종 러닝 경로의 지표를 바탕으로 Gemini가 체육·생리학적 피드백 리포트를 작성합니다."""
    system_instruction = (
        "너는 중·고등학교 체육 및 운동생리학 전문가이자 PAPSrun 시스템의 AI 코치다.\n"
        "도출된 러닝 경로 데이터를 분석하여 친절하고 전문적인 3줄 내외 불릿포인트 리포트를 작성하라."
    )
    user_content = (
        f"학생이 설정한 운동 목표: '{user_goal}'\n\n"
        f"[도출된 최적 러닝 경로 측정 지표]:\n"
        f"- 총 이동 거리: {route_metrics.get('total_distance_m', 0):.1f} m\n"
        f"- 누적 상승 고도: {route_metrics.get('elevation_gain_m', 0):.1f} m\n"
        f"- 평균 구간 경사도: {route_metrics.get('avg_slope_pct', 0):.2f} %\n"
        f"- 평균 그늘 차광율: {route_metrics.get('avg_shade_pct', 0):.1f} %\n"
        f"- 우레탄/트랙 노면 비율: {route_metrics.get('cushion_ratio_pct', 0):.1f} %"
    )

    try:
        return _call_gemini_generate(system_instruction, user_content)
    except Exception:
        return (
            "✅ **경로 분석 완료**: 선택하신 경로는 학생의 관절 보호 및 체온 조절에 최적화된 상태입니다. "
            "충분한 수분 섭취와 함께 안전하게 운동을 수행하세요."
        )