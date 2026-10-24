"""PAPSrun 지능형 바이브 코딩 튜터 엔진 (3단계 교육학적 스캐폴딩 탑재).

학생의 실패 횟수(retry_count)를 세션별로 추적하여:
1회 실패: 정답 힌트 없이 현상 환기 및 스스로 사고 촉진
2회 실패: 핵심 과학/물리 개념 단서만 살짝 제공 (코드 노출 금지)
3회 이상: 자연어 프롬프트 작성 뼈대 문장 제시
우수 프롬프트 입력 시에만 최종 마스터 코드를 지급합니다.
"""

import json
import os
import re
from typing import Any, Dict, Generator, Optional, Tuple
import requests
import streamlit as st

FINAL_CODE_DIR = os.path.join(os.getcwd(), "final_code")

ROLE_CATALOG = {
    "student_01": {
        "team": "team1", "file": "student_01_albedo.py", "title": "노면 피복별 알베도(반사율) 매핑",
        "keywords": ["알베도", "반사율", "노면", "아스팔트", "우레탄", "잔디", "흙길", "1번"],
        "prompt_checklist": ["알베도", "노면", "우레탄", "아스팔트", "예외", "기본값"],
        "defect_desc": "노면 재질별 알베도 사전 매핑 및 미지정 노면 기본값 방어 누락",
        "scaffold_hints": [
            "도로 바닥 재질(아스팔트, 우레탄, 잔디)에 따라 햇빛이 반사되는 정도가 다르다는 점을 AI에게 알려줘야 해요!",
            "지구과학 시간에 배운 아스팔트와 우레탄의 반사율 수치를 명시하고, 알 수 없는 길일 때 적용할 기본값도 요청해 보세요.",
            "이렇게 써보세요: '우레탄, 아스팔트, 잔디의 반사율을 매핑하고, 목록에 없으면 기본값 0.15를 주는 함수 짜줘'"
        ],
        "buggy_code": "def get_surface_albedo(surface_type: str) -> float:\n    # ⚠️ 결함: 노면 재질 구분 없이 단일 값만 반환\n    return 0.15"
    },
    "student_02": {
        "team": "team1", "file": "student_02_solar.py", "title": "가로수 그늘 차광률 및 유효 일사량 연산",
        "keywords": ["그늘", "차광", "일사량", "가로수", "차광막", "태양", "햇빛", "2번"],
        "prompt_checklist": ["그늘", "차광", "70%", "0.3", "클램핑", "음수", "방어"],
        "defect_desc": "그늘일 때 일사량 70% 차광 감쇄 및 음수 일사량 방어 누락",
        "scaffold_hints": [
            "지금 코드는 그늘진 숲길을 지나가도 한낮 땡볕과 똑같은 열을 받는 치명적인 버그가 있어요! 무엇을 고려해야 할까요?",
            "가로수 그늘이 햇빛을 몇 %나 막아주는지(감쇄율), 그리고 센서 오류로 일사량이 0 미만(음수)으로 떨어지는 상황을 어떻게 막을지 문장에 담아보세요.",
            "이렇게 써보세요: '그늘(is_shaded)일 때는 일사량을 70% 줄이고, 일사량이 음수가 되지 않게 0으로 방어하는 함수를 만들어줘'"
        ],
        "buggy_code": "def calculate_effective_solar(solar_w_m2: float, is_shaded: bool = False) -> float:\n    # ⚠️ 결함: 그늘 감쇄 로직과 음수 일사량 방어가 빠져있음\n    return float(solar_w_m2)"
    },
    "student_03": {
        "team": "team1", "file": "student_03_radiation.py", "title": "지표면 순흡수 복사에너지 연산",
        "keywords": ["복사에너지", "순흡수", "r_abs", "흡수열", "복사열", "3번"],
        "prompt_checklist": ["r_abs", "순흡수", "알베도", "1 -", "흡수"],
        "defect_desc": "순흡수 공식 R_abs = S * (1 - albedo) 누락",
        "scaffold_hints": [
            "바닥이 반사한 열과 바닥이 실제로 흡수해서 러너를 뜨겁게 달구는 열은 달라요. 물리 공식이 빠져 있습니다!",
            "알베도가 반사율이라면, 지표면이 '흡수'하는 비율은 수식으로 어떻게 표현했었죠?",
            "이렇게 써보세요: '일사량에 (1 - 알베도)를 곱해서 노면이 실제로 흡수하는 순흡수 복사에너지를 구하도록 해줘'"
        ],
        "buggy_code": "def calculate_absorbed_radiation(solar_w_m2: float, albedo: float) -> float:\n    # ⚠️ 결함: 반사율을 그대로 곱해버려 물리 공식 왜곡\n    return solar_w_m2 * albedo"
    },
    "student_04": {
        "team": "team1", "file": "student_04_slope_dem.py", "title": "지형 고도차 기반 간선 경사도 산출",
        "keywords": ["경사", "경사도", "고도", "dem", "오르막", "내리막", "4번"],
        "prompt_checklist": ["고도", "경사도", "거리", "100", "0 나누기", "방어"],
        "defect_desc": "수평 거리가 0일 때의 ZeroDivision 방어 누락",
        "scaffold_hints": [
            "두 지점의 거리가 0인 데이터가 들어오면 프로그램 전체가 멈춰버려요!",
            "경사도를 계산할 때 고도차를 무엇으로 나누는지, 그 분모가 0일 때는 어떤 처리를 해야 안전할지 생각해 보세요.",
            "이렇게 써보세요: '고도차를 거리로 나누어 경사도를 구하되, 거리가 0이면 경사도를 0으로 처리하게 해줘'"
        ],
        "buggy_code": "def calculate_edge_slope(ele_start: float, ele_end: float, distance_m: float) -> float:\n    # ⚠️ 결함: 거리가 0일 때 프로그램 다운 방어 누락\n    return ((ele_end - ele_start) / distance_m) * 100.0"
    },
    "student_05": {
        "team": "team1", "file": "student_05_failsafe.py", "title": "33도 폭염 Fail-Safe 안전 제어",
        "keywords": ["폭염", "failsafe", "안전", "33도", "인터락", "중단", "5번"],
        "prompt_checklist": ["33", "폭염", "failsafe", "차단", "중단", "인터락"],
        "defect_desc": "33도 이상 시 야외 활동 중단 인터락 누락",
        "scaffold_hints": [
            "살인적인 폭염 경보가 내려져도 학생들을 무조건 뛰게 만드는 위험한 상태예요!",
            "기상청 폭염 경보 기준 온도가 몇 도였는지, 그 온도를 넘으면 코드가 무엇을 반환해야 할지 명시해 보세요.",
            "이렇게 써보세요: '기온이 33도 이상이면 위험으로 판정하고 야외 질주를 즉시 차단하는 인터락을 걸어줘'"
        ],
        "buggy_code": "def check_heatwave_failsafe(temperature: float) -> bool:\n    # ⚠️ 결함: 안전 인터락 없이 무조건 통과\n    return True"
    }
}

# 6~20번 학생 모듈 기본 스캐폴딩 템플릿
for idx in range(6, 21):
    st_key = f"student_{idx:02d}"
    if st_key not in ROLE_CATALOG:
        team_dir = "team2" if idx <= 10 else ("team3" if idx <= 15 else "team4")
        ROLE_CATALOG[st_key] = {
            "team": team_dir, "file": f"{st_key}_module.py", "title": f"{idx}번 알고리즘 컴포넌트",
            "keywords": [f"{idx}번", f"{idx}"],
            "prompt_checklist": ["수식", "방어", "계산", "변수"],
            "defect_desc": "핵심 공식 및 이상치 방어 로직 누락",
            "scaffold_hints": [
                "요구사항이 너무 짧아서 필요한 수식이 전혀 반영되지 않았어요. 어떤 기능을 만들고 싶나요?",
                "입력값으로 들어올 변수와 최종 계산 공식, 비정상적인 데이터가 들어왔을 때의 방어 조건을 고민해 보세요.",
                "이렇게 써보세요: 'OO 변수와 OO 공식을 사용해서 계산하고, 비정상 값은 방어하는 함수를 만들어줘'"
            ],
            "buggy_code": f"def process_{st_key}(data: dict) -> dict:\n    # ⚠️ 결함: 필수 로직 누락\n    return data"
        }


def check_hidden_master_command(user_text: str) -> Optional[str]:
    match = re.search(r"\$\$answer-student_?([1-9]|1[0-9]|20)\b", user_text.strip().lower())
    return f"student_{int(match.group(1)):02d}" if match else None


def detect_role_from_prompt(user_text: str) -> Optional[str]:
    text_lower = user_text.lower()
    num_match = re.search(r"\b([1-9]|1[0-9]|20)\s*(?:번|학생|호)?\b", text_lower)
    if num_match:
        return f"student_{int(num_match.group(1)):02d}"
    scores = {st_id: sum(1 for kw in info["keywords"] if kw in text_lower) for st_id, info in ROLE_CATALOG.items()}
    max_s = max(scores.values()) if scores else 0
    return max(scores, key=scores.get) if max_s > 0 else None


def read_master_code(st_id: str) -> str:
    info = ROLE_CATALOG.get(st_id, ROLE_CATALOG["student_01"])
    fpath = os.path.join(FINAL_CODE_DIR, info["team"], info["file"])
    if os.path.exists(fpath):
        try:
            with open(fpath, "r", encoding="utf-8") as f:
                c = f.read().strip()
                if c:
                    return c
        except Exception:
            pass
    return f'# {info["file"]}\ndef {info["file"].replace(".py", "")}():\n    pass'


def evaluate_prompt_quality(st_id: str, prompt: str) -> Tuple[bool, list, list]:
    info = ROLE_CATALOG.get(st_id, ROLE_CATALOG["student_01"])
    p_lower = prompt.strip().lower()
    matched = [item for item in info["prompt_checklist"] if item.lower() in p_lower]
    missing = [item for item in info["prompt_checklist"] if item.lower() not in p_lower]
    # 25자 이상 + 필수 기술 키워드 2개 이상 명시 시에만 완성형 마스터 인정
    is_quality = (len(p_lower) >= 25 and len(matched) >= 2)
    return is_quality, matched, missing


def stream_local_ollama_qwen(prompt: str, system_prompt: str, model_name: str = "qwen2.5-coder:7b") -> Generator[str, None, None]:
    url = "http://localhost:11434/api/generate"
    payload = {
        "model": model_name, "prompt": prompt, "system": system_prompt,
        "stream": True, "options": {"temperature": 0.3, "num_predict": 300}
    }
    try:
        with requests.post(url, json=payload, stream=True, timeout=30.0) as res:
            if res.status_code == 200:
                for line in res.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        yield chunk.get("response", "")
                        if chunk.get("done", False):
                            break
    except Exception:
        yield "\n(튜터 피드백 연동 대기 중)\n"


def stream_gemini_vibe_code(team_id: str, user_prompt: str) -> Generator[str, None, None]:
    prompt_clean = user_prompt.strip()

    # 시도 횟수(retry_count) 세션 초기화
    if "prompt_retry_count" not in st.session_state:
        st.session_state["prompt_retry_count"] = 0

    # 1. 교사용 비상 마스터키 오버라이드
    hidden_target = check_hidden_master_command(prompt_clean)
    if hidden_target:
        st.session_state["assigned_student_role"] = hidden_target
        info = ROLE_CATALOG.get(hidden_target, ROLE_CATALOG["student_01"])
        code = read_master_code(hidden_target)
        yield "🔓 **[교사용 마스터 오버라이드: 정답 코드 즉각 인출]**\n\n"
        yield f"검증된 마스터 완성본 코드를 인출합니다:\n\n```python\n{code}\n```\n\n"
        yield f"💡 위 코드를 복사하여 `final_code/{info['team']}/{info['file']}`에 바로 저장하세요."
        return

    # 2. 역할 판별
    active_role = st.session_state.get("assigned_student_role")
    detected = detect_role_from_prompt(prompt_clean)

    # 2-A. 최초 역할 진입
    if not active_role and detected:
        st.session_state["assigned_student_role"] = detected
        st.session_state["prompt_retry_count"] = 0
        info = ROLE_CATALOG.get(detected, ROLE_CATALOG["student_01"])
        yield f"🎯 **[{detected}] {info['title']} 모듈이 연결되었습니다!**\n\n"
        yield f"우리 학생이 전담할 파일은 `final_code/{info['team']}/{info['file']}`이에요.\n\n"
        yield "이 모듈에 필요한 **함수의 목적, 계산 공식, 예외 방어 조건**을 자연어로 AI에게 구체적으로 지시해 보세요!\n"
        yield "💡 *팁: 요구사항이 너무 짧거나 모호하면 중요한 로직이 빠진 불완전한 코드가 만들어집니다.*"
        return

    if not active_role and not detected:
        yield "👨‍🏫 **반가워요! PAPSrun 코딩 수업을 함께할 AI 튜터 선생님이에요.**\n\n오늘 우리 학생은 몇 번 파트를 맡으셨나요? (예: '2번 그늘 계산', '4번 경사도' 등)"
        return

    if detected:
        active_role = detected
        st.session_state["assigned_student_role"] = active_role

    info = ROLE_CATALOG.get(active_role, ROLE_CATALOG["student_01"])
    master_code = read_master_code(active_role)
    is_quality, matched, missing = evaluate_prompt_quality(active_role, prompt_clean)

    # 3-A. 프롬프트가 부실한 경우 -> 3단계 스캐폴딩 적용
    if not is_quality:
        st.session_state["prompt_retry_count"] += 1
        current_step = min(st.session_state["prompt_retry_count"], 3)
        buggy_code = info.get("buggy_code", f"# {info['file']}\npass")

        yield "⚠️ **요구사항이 너무 단순하여 핵심 로직이 빠진 코드가 만들어졌어요!**\n\n"
        yield f"```python\n{buggy_code}\n```\n\n"

        scaffold_text = info["scaffold_hints"][current_step - 1]

        if current_step == 1:
            yield f"👨‍🏫 **선생님 생각 유도 (1단계):**\n{scaffold_text}\n\n"
            yield "👉 *포기하지 말고, 빠진 물리·수학적 상황을 한 번 더 떠올려 프롬프트에 살을 붙여보세요!*"
        elif current_step == 2:
            yield f"👨‍🏫 **선생님 개념 단서 (2단계):**\n{scaffold_text}\n\n"
            yield "👉 *이 단서들을 조합해서 자연어 문장으로 다시 요청해 보세요.*"
        else:
            yield f"👨‍🏫 **선생님 문장 가이드 (3단계):**\n{scaffold_text}\n\n"
            yield "👉 *위 예시 문장을 참고하여 내 생각을 담은 온전한 문장으로 요청해 보세요!*"
        return

    # 3-B. 프롬프트가 구체적이고 우수한 경우 -> 성공 축하 및 마스터 코드 지급
    st.session_state["prompt_retry_count"] = 0  # 성공 시 카운트 리셋
    yield f"🎉 **대단해요! 요구하신 조건({', '.join(matched)})이 모두 명확하게 반영된 완성형 코드입니다.**\n\n"
    yield f"```python\n{master_code}\n```\n\n"
    yield "👨‍🏫 **선생님의 파이프라인 해설:**\n"
    
    system_praise = "당신은 STEAM 교사입니다. 학생이 훌륭한 프롬프트로 모듈을 완성했음을 칭찬하고, 이 모듈이 러닝 코스 추천 시스템 전체에서 어떤 중요한 역할을 하는지 다정하게 2문장으로 설명하세요."
    prompt_praise = f"완성 모듈: [{active_role}] {info['title']}, 만족 조건: {matched}"
    for token in stream_local_ollama_qwen(prompt=prompt_praise, system_prompt=system_praise):
        yield token

    yield f"\n\n💡 **적용 방법**: 위 완성 코드를 복사하여 `final_code/{info['team']}/{info['file']}`에 저장하세요!"


MASTER_COMPONENTS = {
    k: {
        "name": v["title"],
        "correct_code": f'# {v["file"]}',
        "incomplete_code": f'# {v["file"]}',
        "missing_features": "기본 구현",
    }
    for k, v in ROLE_CATALOG.items()
}
for t in range(1, 5):
    MASTER_COMPONENTS[f"TEAM_{t}"] = MASTER_COMPONENTS[f"student_{(t-1)*5 + 1:02d}"]


def request_gemini_vibe_code(team_id: str, user_prompt: str, api_key: Optional[str] = None) -> Tuple[str, str]:
    full_text = "".join(list(stream_gemini_vibe_code(team_id, user_prompt)))
    code_match = re.search(r"```python(.*?)```", full_text, re.DOTALL)
    return (code_match.group(1).strip() if code_match else ""), full_text


def generate_vibe_code(
    user_requirements: str,
    student_profile: Optional[Dict[str, Any]] = None,
    weather_info: Optional[Dict[str, Any]] = None,
) -> str:
    team_id = (student_profile or {}).get("team_id", "student_01")
    code, feedback = request_gemini_vibe_code(team_id=team_id, user_prompt=user_requirements)
    return f"{feedback}\n\n```python\n{code}\n```"


def is_gemini_available() -> bool:
    return True


def get_gemini_client(api_key: Optional[str] = None):
    return None