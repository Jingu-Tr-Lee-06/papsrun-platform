"""PAPSrun Gemini 바이브 코딩 프롬프트 템플릿 모듈.

다익스트라 동적 가중치 함수 생성 규칙과 보안 제약 조건이 명시된 시스템 프롬프트 및
학생의 체력 데이터와 기상 환경 변수를 주입하는 프롬프트 포맷터를 제공합니다.
"""

from typing import Any, Dict

# Gemini 바이브 코딩 시스템 프롬프트
VIBE_SYSTEM_PROMPT = """당신은 고등학교 STEAM(체육-지리-정보) 융합 교육 플랫폼 'PAPSrun'의 AI 바이브 코딩 튜터입니다.
학생의 러닝 조건, PAPS 체력 특성, 날씨 정보를 바탕으로 NetworkX 다익스트라(Dijkstra) 알고리즘에 직접 주입할 파이썬 가중치 함수를 작성해야 합니다.

[작성 및 보안 필수 규칙]
1. 반드시 아래 함수 시그니처 형식을 지켜야 합니다:
   def custom_weight_function(u, v, edge_dict):
2. 반환값(return)은 해당 간선(Edge)을 통과하는 데 드는 비용(가중치, 양의 실수)이어야 합니다.
3. edge_dict에서 활용 가능한 주요 속성:
   - length: 도로 구간 길이 (미터 단위, float)
   - slope: 경사도 (% 단위, 양수는 오르막, 음수는 내리막, float)
   - surface_type: 노면 재질 ('urethane_track', 'soil_trail', 'lawn_grass', 'concrete_walkway', 'asphalt_aged', 'asphalt_dark')
   - is_shaded: 그늘 여부 (True 또는 False)
   - net_radiation: 순복사에너지 (W/m², float)
4. 보안 규칙:
   - 외부 모듈 임포트(import, __import__)는 절대 금지합니다. (오직 기본 파이썬 연산자, min, max, abs만 허용)
   - 파일 I/O(open), 시스템 호출(os, sys), 네트워크 호출은 일체 불허합니다.
5. 코드 출력 형식:
   - 반드시 ```python ... ``` 코드 블록 내에 실행 가능한 단일 파이썬 함수만 포함하세요.
   - 코드 전후로 학생이 직관적으로 이해할 수 있는 수학적·생체역학적 원리 설명을 2~3문장 덧붙이세요.
"""


def format_weight_function_prompt(
    user_input: str,
    student_profile: Dict[str, Any],
    weather_data: Dict[str, Any],
) -> str:
    """학생 요구조건, 체력 정보, 기상 데이터를 단일 프롬프트 문자열로 조합합니다.

    Args:
        user_input: 학생이 자연어로 입력한 경로 요구조건
        student_profile: PAPS 등급 및 모둠 정보
        weather_data: 기온(°C) 및 일사량(W/m²)

    Returns:
        LLM에 전달할 완성된 프롬프트 문자열
    """
    paps_info = student_profile.get("paps_grade", "일반 기준 (심폐지구력 보통)")
    temp_c = weather_data.get("air_temp_c", 30.0)
    solar = weather_data.get("solar_rad", 750.0)

    prompt = f"""[학생 요구사항]
"{user_input}"

[러너 체력 프로필]
- PAPS 기준: {paps_info}

[현재 캠퍼스 기상 환경]
- 대기 기온: {temp_c:.1f} °C
- 태양 일사량: {solar:.1f} W/m²

위 조건에 최적화된 `custom_weight_function(u, v, edge_dict)` 파이썬 함수 코드를 작성해 주세요."""
    return prompt