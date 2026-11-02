"""PAPSrun 지능형 바이브 코딩 튜터 엔진 (Live LLM + Strict Master Code Pipeline).

- 일상 대화, 유도 질문, 힌트 피드백: Ubuntu 랩 서버의 Qwen2.5:3b-4k 모델이 실시간 스트리밍
- 최종 정상 코드: 임의 생성을 전면 차단하고 final_code/{team}/{file} 원본 코드를 그대로 인출
"""

import json
import os
import re
from typing import Any, Dict, Generator, List, Optional, Tuple
import requests
import streamlit as st

FINAL_CODE_DIR = os.path.join(os.getcwd(), "final_code")

ROLE_CATALOG = {
    "student_01": {
        "team": "team1", "file": "student_01_albedo.py", "title": "노면 피복별 알베도(반사율) 매핑",
        "keywords": ["알베도", "반사율", "노면", "아스팔트", "우레탄", "잔디", "흙길", "1번", "1"],
        "prompt_checklist": ["알베도", "노면", "우레탄", "아스팔트", "기본값", "0.15"],
        "core_concept": "아스팔트(0.12), 우레탄(0.20), 잔디(0.25) 등 도로 재질별 반사율 매핑 및 미지정 노면 기본값(0.15) 방어",
    },
    "student_02": {
        "team": "team1", "file": "student_02_solar.py", "title": "가로수 그늘 차광률 및 유효 일사량 연산",
        "keywords": ["그늘", "차광", "일사량", "가로수", "차광막", "태양", "햇빛", "2번", "2"],
        "prompt_checklist": ["그늘", "차광", "70%", "0.3", "음수", "0", "방어", "max"],
        "core_concept": "그늘일 때 일사량 70% 차광(투과율 0.3) 및 센서 오류로 인한 음수 일사량을 0으로 막는 방어 로직",
    },
    "student_03": {
        "team": "team1", "file": "student_03_radiation.py", "title": "지표면 순흡수 복사에너지 연산",
        "keywords": ["복사에너지", "순흡수", "r_abs", "흡수열", "복사열", "3번", "3"],
        "prompt_checklist": ["r_abs", "순흡수", "알베도", "1 -", "흡수"],
        "core_concept": "순흡수 복사에너지 공식: R_abs = S * (1 - albedo). 반사율을 제외한 실제 흡수율 연산",
    },
    "student_04": {
        "team": "team1", "file": "student_04_slope_dem.py", "title": "지형 고도차 기반 간선 경사도 산출",
        "keywords": ["경사", "경사도", "고도", "dem", "오르막", "내리막", "4번", "4"],
        "prompt_checklist": ["고도", "경사도", "거리", "100", "0", "방어"],
        "core_concept": "경사도(%) 공식: (고도차 / 거리) * 100 및 거리가 0일 때의 ZeroDivision 방어",
    },
    "student_05": {
        "team": "team1", "file": "student_05_failsafe.py", "title": "33도 폭염 Fail-Safe 안전 제어",
        "keywords": ["폭염", "failsafe", "안전", "33도", "인터락", "중단", "5번", "5"],
        "prompt_checklist": ["33", "폭염", "failsafe", "차단", "중단", "인터락"],
        "core_concept": "33도 이상 시 야외 활동 중단 및 실내 대체 코스로 전환하는 안전 인터락",
    }
}

for idx in range(6, 21):
    st_key = f"student_{idx:02d}"
    if st_key not in ROLE_CATALOG:
        team_dir = "team2" if idx <= 10 else ("team3" if idx <= 15 else "team4")
        ROLE_CATALOG[st_key] = {
            "team": team_dir, "file": f"{st_key}_module.py", "title": f"{idx}번 알고리즘 모듈",
            "keywords": [f"{idx}번", f"{idx}"],
            "prompt_checklist": ["수식", "방어", "계산", "변수"],
            "core_concept": f"{idx}번 파이프라인의 물리/수학 공식 및 이상치 방어 로직",
        }


def detect_role_from_prompt(user_text: str) -> Optional[str]:
    """학생 입력에서 담당 모듈 식별."""
    text_lower = user_text.lower()
    num_match = re.search(r"\b([1-9]|1[0-9]|20)\s*(?:번|학생|호)?\b", text_lower)
    if num_match:
        return f"student_{int(num_match.group(1)):02d}"
    scores = {st_id: sum(1 for kw in info["keywords"] if kw in text_lower) for st_id, info in ROLE_CATALOG.items()}
    max_s = max(scores.values()) if scores else 0
    return max(scores, key=scores.get) if max_s > 0 else None


def read_master_code(st_id: str) -> str:
    """final_code 폴더에서 엄격하게 원본 정답 코드를 읽어옵니다."""
    info = ROLE_CATALOG.get(st_id, ROLE_CATALOG["student_01"])
    candidate_paths = [
        os.path.join(os.getcwd(), "final_code", info["team"], info["file"]),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "final_code", info["team"], info["file"]),
    ]
    for fpath in candidate_paths:
        if os.path.exists(fpath):
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    content = f.read().strip()
                    if content:
                        return content
            except Exception:
                pass
    return f"# [알림] final_code/{info['team']}/{info['file']} 파일이 존재하지 않습니다.\ndef {info['file'].replace('.py', '')}():\n    pass"


def check_prompt_success(st_id: str, prompt: str) -> Tuple[bool, list]:
    """학생 프롬프트가 정답 코드를 수령할 조건을 만족했는지 판정."""
    info = ROLE_CATALOG.get(st_id, ROLE_CATALOG["student_01"])
    p_lower = prompt.strip().lower()
    matched = [item for item in info["prompt_checklist"] if item.lower() in p_lower]
    is_success = (len(p_lower) >= 25 and len(matched) >= 2)
    return is_success, matched


@st.cache_data(ttl=5)
def check_ollama_status(target_model: str = "qwen2.5:3b-4k") -> dict:
    """Ollama 서버 연결 및 모델 상태 체크."""
    base_url = st.secrets.get("OLLAMA_BASE_URL", "https://lab-server.crayfish-coho.ts.net")
    target_endpoint = f"{base_url.rstrip('/')}/api/tags"
    
    debug_info = {
        "online": False, "model_loaded": False, "base_url": base_url,
        "endpoint": target_endpoint, "status_code": None, "msg": "", "detail": "", "models": []
    }
    try:
        res = requests.get(target_endpoint, timeout=4.0)
        debug_info["status_code"] = res.status_code
        if res.status_code == 200:
            models = [m.get("name", "") for m in res.json().get("models", [])]
            debug_info["models"] = models
            is_model_present = any(target_model in m or "3b" in m for m in models)
            debug_info["online"] = True
            debug_info["model_loaded"] = is_model_present
            debug_info["msg"] = "정상 연결" if is_model_present else "모델 미발견"
        else:
            debug_info["msg"] = f"HTTP {res.status_code}"
    except Exception as e:
        debug_info["msg"] = "연결 실패"
        debug_info["detail"] = str(e)
    return debug_info


def stream_qwen_raw(messages: List[Dict[str, str]], temperature: float = 0.5) -> Generator[str, None, None]:
    """Ollama /api/chat 엔드포인트를 호출하여 토큰 단위로 실시간 스트리밍."""
    base_url = st.secrets.get("OLLAMA_BASE_URL", "https://lab-server.crayfish-coho.ts.net")
    url = f"{base_url.rstrip('/')}/api/chat"

    payload = {
        "model": "qwen2.5:3b-4k",
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "top_p": 0.9,
            "num_predict": 450,
        },
    }
    try:
        with requests.post(url, json=payload, stream=True, timeout=30.0) as res:
            if res.status_code == 200:
                for line in res.iter_lines():
                    if line:
                        chunk = json.loads(line.decode("utf-8"))
                        token = chunk.get("message", {}).get("content", "")
                        if token:
                            yield token
                        if chunk.get("done", False):
                            break
            else:
                yield f"\n⚠️ [서버 응답 오류: HTTP {res.status_code}]\n"
    except Exception as e:
        yield f"\n⚠️ [AI 통신 오류: {str(e)}]\n"


def stream_hybrid_vibe_dialogue(
    messages: List[Dict[str, str]],
    assigned_role: Optional[str] = None,
) -> Generator[str, None, None]:
    """실시간 대화와 final_code 원본 코드 인출을 결합한 하이브리드 스트리머."""
    latest_user_text = messages[-1]["content"] if messages else ""

    # 1. 교사용 마스터키 오버라이드
    match = re.search(r"\$\$answer-student_?([1-9]|1[0-9]|20)\b", latest_user_text.strip().lower())
    if match:
        target_role = f"student_{int(match.group(1)):02d}"
        info = ROLE_CATALOG.get(target_role, ROLE_CATALOG["student_01"])
        master_code = read_master_code(target_role)
        yield "🔓 **[교사용 마스터 오버라이드]**\n\n"
        yield f"`final_code/{info['team']}/{info['file']}` 원본 정답 코드를 즉시 인출합니다:\n\n"
        yield f"```python\n{master_code}\n```\n\n"
        yield f"💡 위 코드를 복사하여 `final_code/{info['team']}/{info['file']}`에 저장하세요."
        return

    # 2. 역할이 배정되지 않은 경우
    if not assigned_role:
        system_prompt = (
            "당신은 PAPSrun 고등학교 STEAM 코딩 수업의 AI 튜터 교사입니다.\n"
            "학생이 질문한 내용(정체성, 모델 질문, 일상 대화 등)에 유쾌하고 친절하게 대답하세요.\n"
            "그리고 학생이 오늘 담당할 1~20번 모듈 중 어떤 번호를 구현할 것인지 다정하게 물어보세요.\n"
            "(절대로 코드를 먼저 출력하지 마세요)"
        )
        chat_history = [{"role": "system", "content": system_prompt}] + messages
        for token in stream_qwen_raw(chat_history, temperature=0.6):
            yield token
        return

    # 3. 역할이 배정된 경우
    info = ROLE_CATALOG.get(assigned_role, ROLE_CATALOG["student_01"])
    is_success, matched = check_prompt_success(assigned_role, latest_user_text)

    # 3-A. 우수 프롬프트 합격 시: 칭찬 + final_code 원본 방출
    if is_success:
        master_code = read_master_code(assigned_role)
        system_praise = (
            f"당신은 친절한 STEAM 교사입니다. 학생이 [{assigned_role}] {info['title']} 모듈의 필수 조건({matched})을 "
            f"훌륭하게 프롬프트로 작성했습니다. 학생의 성장을 축하하고, 이 모듈이 캠퍼스 러닝 추천 시스템에서 어떤 역할을 "
            f"하게 되는지 2~3문장으로 다정하게 칭찬해 주세요. (코드는 출력하지 마세요)"
        )
        praise_history = [{"role": "system", "content": system_praise}] + messages
        yield "🎉 **훌륭해요! 제시한 요구 조건이 모두 충족되었습니다.**\n\n"
        for token in stream_qwen_raw(praise_history, temperature=0.4):
            yield token

        yield f"\n\n📂 **검증된 마스터 원본 코드 (`final_code/{info['team']}/{info['file']}`)**:\n"
        yield f"```python\n{master_code}\n```\n\n"
        yield f"💡 위 코드를 그대로 복사하여 `final_code/{info['team']}/{info['file']}` 파일에 저장하세요!"
        return

    # 3-B. 미흡한 경우: 실시간 스캐폴딩 힌트 생성
    system_guide = f"""
당신은 PAPSrun 고등학교 STEAM 수업의 AI 튜터 교사입니다.
학생은 현재 [{assigned_role}] {info['title']} 모듈을 작성하고 있습니다.
핵심 개념: {info['core_concept']}

[행동 규칙]
1. 절대로 완성된 파이썬 함수/정답 코드를 통째로 출력하지 마세요. (학생이 스스로 프롬프트를 다듬어야 합니다)
2. 학생이 "모르겠어", "어려워", "코드 줘"라고 하면 격려하면서 단계를 유도하세요.
3. 학생의 말에 귀 기울이며 다정하고 자연스러운 한국어 구어체로 대화하세요.
"""
    guide_history = [{"role": "system", "content": system_guide}] + messages
    for token in stream_qwen_raw(guide_history, temperature=0.5):
        yield token


# =====================================================================
# 📦 레거시 컴포넌트(vibe_chat_panel 등) 하위 호환성 심볼 및 함수
# =====================================================================

MASTER_COMPONENTS: Dict[str, Dict[str, Any]] = {
    k: {
        "name": v["title"],
        "correct_code": f'# final_code/{v["team"]}/{v["file"]}',
        "incomplete_code": f'# incomplete {v["file"]}',
        "missing_features": v["core_concept"],
    }
    for k, v in ROLE_CATALOG.items()
}
for t in range(1, 5):
    MASTER_COMPONENTS[f"TEAM_{t}"] = MASTER_COMPONENTS[f"student_{(t-1)*5 + 1:02d}"]


def stream_gemini_vibe_code(team_id: str, user_prompt: str) -> Generator[str, None, None]:
    """기존 호출부와의 호환을 위한 스트리머 래퍼."""
    assigned_role = detect_role_from_prompt(user_prompt) or team_id
    messages = [{"role": "user", "content": user_prompt}]
    return stream_hybrid_vibe_dialogue(messages=messages, assigned_role=assigned_role)


def request_gemini_vibe_code(team_id: str, user_prompt: str, api_key: Optional[str] = None) -> Tuple[str, str]:
    """기존 vibe_chat_panel 호출용 동기 래퍼 함수."""
    full_text = "".join(list(stream_gemini_vibe_code(team_id, user_prompt)))
    code_match = re.search(r"```python(.*?)```", full_text, re.DOTALL)
    code = code_match.group(1).strip() if code_match else read_master_code(team_id)
    return code, full_text


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