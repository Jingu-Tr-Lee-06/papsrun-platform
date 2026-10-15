"""학급 세션 상태, 권한 통제 및 수업 환경 변수 관리 모듈.

교사의 도로망 작도 잠금(is_locked), 학급별 환경 기상 파라미터(기온, 일사량),
모둠별 접속 및 진행 단계 현황을 Firestore 및 로컬 캐시를 통해 동기화합니다.
"""

from typing import Any, Dict, List, Optional
import json
import os
import time

from src.db.firebase_client import get_firestore_client, is_firebase_available

SESSION_CACHE_DIR = os.path.join("data", "cache")
SESSION_CACHE_FILE = os.path.join(SESSION_CACHE_DIR, "class_sessions.json")


def _ensure_session_cache_dir() -> None:
    """세션 캐시 디렉터리 존재 여부를 확인하고 생성합니다."""
    os.makedirs(SESSION_CACHE_DIR, exist_ok=True)


def _load_local_sessions() -> Dict[str, Any]:
    """로컬 JSON에서 전체 학급 세션 정보를 로드합니다."""
    _ensure_session_cache_dir()
    if not os.path.exists(SESSION_CACHE_FILE):
        return {}
    try:
        with open(SESSION_CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_local_sessions(data: Dict[str, Any]) -> bool:
    """로컬 JSON에 학급 세션 정보를 저장합니다."""
    _ensure_session_cache_dir()
    try:
        with open(SESSION_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False


def get_class_session_config(class_code: str) -> Dict[str, Any]:
    """해당 학급의 수업 세션 설정(잠금 여부, 환경 변수 등)을 조회합니다.

    Args:
        class_code: 학급 식별 코드

    Returns:
        세션 설정 딕셔너리
    """
    class_code = class_code.strip() or "DEFAULT_CLASS"
    default_config: Dict[str, Any] = {
        "class_code": class_code,
        "is_locked": False,               # True일 경우 학생 작도/수정 차단
        "air_temp_c": 30.0,               # 기본 대기온도 (°C)
        "solar_rad": 750.0,               # 기본 하향 단파 일사량 (W/m^2)
        "active_step": 1,                 # 교사가 지정한 현재 권장 단계 (1~5)
        "teacher_active": True,
        "updated_at": time.time(),
    }

    if is_firebase_available():
        try:
            db = get_firestore_client()
            if db is not None:
                doc_ref = db.collection("classes").document(class_code)
                doc = doc_ref.get()
                if doc.exists:
                    data = doc.to_dict() or {}
                    default_config.update(data)
                    # 로컬 캐시 동기화
                    all_sessions = _load_local_sessions()
                    all_sessions[class_code] = default_config
                    _save_local_sessions(all_sessions)
                    return default_config
        except Exception:
            pass

    # 로컬 캐시에서 조회
    all_sessions = _load_local_sessions()
    if class_code in all_sessions:
        default_config.update(all_sessions[class_code])
    else:
        all_sessions[class_code] = default_config
        _save_local_sessions(all_sessions)

    return default_config


def update_class_session_config(
    class_code: str,
    updates: Dict[str, Any],
) -> bool:
    """교사가 지정한 학급 세션 설정(작도 잠금, 날씨 파라미터 등)을 업데이트합니다.

    Args:
        class_code: 학급 식별 코드
        updates: 수정할 필드 딕셔너리

    Returns:
        업데이트 성공 여부 (bool)
    """
    class_code = class_code.strip() or "DEFAULT_CLASS"
    current_config = get_class_session_config(class_code)
    current_config.update(updates)
    current_config["updated_at"] = time.time()

    # 1. Firestore 업데이트
    if is_firebase_available():
        try:
            db = get_firestore_client()
            if db is not None:
                db.collection("classes").document(class_code).set(
                    current_config, merge=True
                )
        except Exception:
            pass

    # 2. 로컬 캐시 업데이트
    all_sessions = _load_local_sessions()
    all_sessions[class_code] = current_config
    return _save_local_sessions(all_sessions)


def set_class_locked_state(class_code: str, is_locked: bool) -> bool:
    """학급 도로망 작도 편집 권한 잠금 상태를 변경합니다.

    Args:
        class_code: 학급 식별 코드
        is_locked: True면 편집 잠금, False면 편집 허용

    Returns:
        반영 성공 여부
    """
    return update_class_session_config(class_code, {"is_locked": is_locked})


def is_class_locked(class_code: str) -> bool:
    """현재 학급이 교사에 의해 편집 잠금 상태인지 판별합니다.

    Args:
        class_code: 학급 식별 코드

    Returns:
        잠금 여부 (bool)
    """
    cfg = get_class_session_config(class_code)
    return bool(cfg.get("is_locked", False))