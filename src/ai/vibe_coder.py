"""PAPSrun 지능형 바이브 코더 모듈.

Ubuntu 랩 서버의 Ollama Qwen2.5:3b-4k와 통신하여 학생의 자연어 요구사항을 바탕으로
모듈 코드 생성, 코드 리뷰, 프롬프트 최적화, 가중치 코드 생성 및 커스텀 가중치 함수 컴파일을 수행합니다.
"""

import json
import math
import os
import re
from typing import Any, Callable, Dict, List, Optional, Tuple
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

    code_match = re.search(r"```python(.*?)```", raw_response, re.DOTALL)
    if code_match:
        extracted_code = code_match.group(1).strip()
        explanation = re.sub(r"```python.*?```", "", raw_response, flags=re.DOTALL).strip()
    else:
        extracted_code = raw_response
        explanation = "코드가 생성되었습니다."

    return {
        "success": True if "오류" not in extracted_code else False,
        "code": extracted_code,
        "explanation": explanation,
        "raw_response": raw_response,
    }


def generate_weight_function_code(
    requirements: str,
    target_role: Optional[str] = None,
    base_code: Optional[str] = None,
) -> str:
    """학생의 자연어 요구사항을 바탕으로 간선 가중치 계산 함수 코드를 생성합니다."""
    system_prompt = (
        "당신은 PAPSrun 러닝 최적화 경로 설계를 위한 전문 파이썬 알고리즘 튜터입니다.\n"
        "학생의 자연어 요구사항을 바탕으로 간선(Edge)의 가중치를 계산하는 `calculate_edge_weight(edge_data)` 함수를 작성하세요.\n"
        "반드시 다음 조건을 지켜야 합니다:\n"
        "1. 입력 인자: `edge_data: dict` (length, slope, is_shaded, surface, net_radiation 등의 속성 포함)\n"
        "2. 반환값: `float` (0 이상의 비용/가중치)\n"
        "3. 0으로 나누기 방지 및 음수 방어 로직 필수 반영\n"
        "4. 마크다운 파이썬 코드 블록(```python ... ```)으로 감싸서 출력하세요."
    )

    user_prompt = f"요구사항: {requirements}\n"
    if target_role:
        user_prompt += f"역할: {target_role}\n"
    if base_code:
        user_prompt += f"기본 코드 템플릿:\n```python\n{base_code}\n```\n"

    res = _call_ollama_generate(system_prompt, user_prompt, temperature=0.25, max_tokens=400)
    
    code_match = re.search(r"```python(.*?)```", res, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    return res.strip()


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
    return {"feedback": feedback}


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


def generate_running_route_feedback(
    route_metrics: Dict[str, Any],
    student_profile: Optional[Dict[str, Any]] = None,
    weather_info: Optional[Dict[str, Any]] = None,
) -> str:
    """다익스트라 알고리즘으로 도출된 최적 러닝 경로에 대해 Qwen 기반 종합 피드백을 생성합니다."""
    if not route_metrics or not route_metrics.get("is_valid", False):
        return "유효한 러닝 경로 데이터가 전달되지 않았습니다."

    dist_m = float(route_metrics.get("total_distance_m", 0.0))
    elev_gain = float(route_metrics.get("elevation_gain_m", 0.0))
    avg_slope = float(route_metrics.get("avg_slope_pct", 0.0))
    shade_ratio = float(route_metrics.get("shaded_ratio_pct", route_metrics.get("shade_ratio_pct", 0.0)))
    avg_rabs = float(route_metrics.get("avg_absorbed_radiation", 0.0))
    bpm = int(route_metrics.get("estimated_avg_bpm", 135))
    calories = float(route_metrics.get("calories_burned_kcal", 0.0))

    system_prompt = (
        "당신은 고등학교 체육·과학 융합 러닝 코스 설계 플랫폼 PAPSrun의 다정한 AI 코치 선생님입니다.\n"
        "학생이 설계하고 알고리즘으로 최적화한 러닝 코스의 지표(거리, 고도차, 그늘 비율, 흡수 복사에너지, 추정 심박수)를 바탕으로,\n"
        "1. 코스의 장점과 운동 효과 칭찬\n"
        "2. 온열부하 및 부상 방지를 위한 안전 러닝 팁\n"
        "을 친절하고 격려하는 어조로 3문장 이내로 요약 피드백하세요."
    )

    user_prompt = (
        f"### 최적화 러닝 경로 분석 지표\n"
        f"- 총 거리: {dist_m:.1f} m\n"
        f"- 누적 상승 고도: +{elev_gain:.1f} m (평균 경사도: {avg_slope:+.1f}%)\n"
        f"- 그늘 구간 비율: {shade_ratio:.1f}%\n"
        f"- 평균 흡수 복사에너지(R_abs): {avg_rabs:.1f} W/m²\n"
        f"- 예상 평균 심박수: {bpm} BPM\n"
        f"- 소모 열량: {calories:.1f} kcal\n\n"
        "이 경로를 달릴 학생에게 격려와 피드백을 전달해 주세요."
    )

    return _call_ollama_generate(system_prompt, user_prompt, temperature=0.4, max_tokens=250)


# =====================================================================
# 🛠️ 다익스트라 가중치 함수 동적 컴파일 및 런타임 실행기
# =====================================================================

def default_edge_weight_calculator(edge_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> float:
    """기본 간선 가중치 계산기 (거리 + 경사도 페널티 + 온열부하 기본 모델)."""
    dist = float(edge_data.get("distance_m", edge_data.get("length", 10.0)))
    slope = float(edge_data.get("slope_pct", edge_data.get("slope", 0.0)))
    surface = str(edge_data.get("surface", "asphalt")).lower()
    is_shaded = bool(edge_data.get("is_shaded", False))

    slope_penalty = 1.0 + (max(0.0, slope) * 0.05)
    shade_discount = 0.90 if is_shaded else 1.0

    return max(0.1, round(dist * slope_penalty * shade_discount, 2))


def compile_custom_weight_function(code_snippet: str) -> Tuple[Optional[Callable], str]:
    """학생이 작성한 파이썬 코드를 검사하고 간선 가중치 함수로 안전하게 동적 컴파일합니다."""
    if not code_snippet or not code_snippet.strip():
        return default_edge_weight_calculator, "기본 가중치 함수가 적용되었습니다."

    forbidden = ["import os", "import sys", "subprocess", "open(", "__import__", "eval(", "exec("]
    for bad in forbidden:
        if bad in code_snippet:
            return None, f"보안상 허용되지 않는 구문이 포함되어 있습니다: `{bad}`"

    safe_globals = {
        "math": math,
        "max": max,
        "min": min,
        "round": round,
        "abs": abs,
        "float": float,
        "int": int,
        "bool": bool,
        "str": str,
    }
    local_env: Dict[str, Any] = {}

    try:
        clean_code = re.sub(r"^```python\s*", "", code_snippet, flags=re.MULTILINE)
        clean_code = re.sub(r"^```\s*$", "", clean_code, flags=re.MULTILINE).strip()

        exec(clean_code, safe_globals, local_env)

        candidate_names = [
            "calculate_edge_weight",
            "get_edge_cost",
            "calculate_effective_solar",
            "calculate_edge_slope",
            "calculate_absorbed_radiation",
            "custom_weight",
        ]
        target_func = None
        for name in candidate_names:
            if name in local_env and callable(local_env[name]):
                target_func = local_env[name]
                break

        if not target_func:
            for val in local_env.values():
                if callable(val):
                    target_func = val
                    break

        if not target_func:
            return None, "코드 내에서 호출 가능한 함수를 찾을 수 없습니다."

        def safe_wrapper(edge_data: Dict[str, Any], context: Optional[Dict[str, Any]] = None) -> float:
            try:
                return float(target_func(edge_data))
            except TypeError:
                try:
                    return float(target_func(edge_data, context))
                except TypeError:
                    return default_edge_weight_calculator(edge_data, context)
            except Exception:
                return default_edge_weight_calculator(edge_data, context)

        return safe_wrapper, "커스텀 가중치 함수가 성공적으로 컴파일되었습니다."

    except Exception as e:
        return None, f"컴파일 오류: {str(e)}"