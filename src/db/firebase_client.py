"""Firebase Firestore 기반 학급 러닝 세션 및 학생 경로 동기화 모듈.

Streamlit secrets의 Firebase 인증 정보를 활용해 Firestore 클라이언트를 초기화하고,
교사의 수업 제어(세션 잠금/해제) 및 학생별 최적화 경로 데이터의 실시간 저장을 처리합니다.
인증 정보 미설정 시 로컬 세션 상태 기반 인메모리 폴백(Mock DB)을 지원합니다.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional
import streamlit as st

_CACHED_DB = None


def get_firestore_client():
    """Firestore 클라이언트를 안전하게 초기화하고 반환합니다."""
    global _CACHED_DB
    if _CACHED_DB is not None:
        return _CACHED_DB

    try:
        import firebase_admin
        from firebase_admin import credentials, firestore

        if not firebase_admin._apps:
            fb_creds = st.secrets.get("firebase")
            if not fb_creds:
                return None

            cred_dict = dict(fb_creds)
            if "private_key" in cred_dict:
                cred_dict["private_key"] = cred_dict["private_key"].replace("\\n", "\n")

            cred = credentials.Certificate(cred_dict)
            firebase_admin.initialize_app(cred)

        _CACHED_DB = firestore.client()
        return _CACHED_DB
    except Exception:
        return None


def is_firebase_available() -> bool:
    """Firebase 연결 가능 여부를 확인합니다."""
    return get_firestore_client() is not None


# 모듈 간 호환성을 위한 별칭 정의
is_firestore_available = is_firebase_available
_get_firestore_client = get_firestore_client


def init_session(session_id: str, teacher_name: str, target_paps_grade: int = 3) -> bool:
    """새로운 체육 수업 러닝 세션을 생성합니다."""
    db = get_firestore_client()
    session_data = {
        "session_id": session_id,
        "teacher_name": teacher_name,
        "is_locked": False,
        "target_paps_grade": target_paps_grade,
        "created_at": datetime.now().isoformat(),
        "status": "active",
    }

    if db:
        try:
            db.collection("running_sessions").document(session_id).set(session_data)
            return True
        except Exception:
            return False

    # Mock DB 폴백 (독립 실행 및 Secrets 미설정 시)
    if "mock_sessions" not in st.session_state:
        st.session_state.mock_sessions = {}
    st.session_state.mock_sessions[session_id] = session_data
    return True


def toggle_session_lock(session_id: str, lock_status: bool) -> bool:
    """교사가 학생 워크스페이스의 코드 제출 및 경로 수정을 원격 잠금/해제합니다."""
    db = get_firestore_client()
    if db:
        try:
            db.collection("running_sessions").document(session_id).update({
                "is_locked": lock_status,
                "updated_at": datetime.now().isoformat(),
            })
            return True
        except Exception:
            return False

    if "mock_sessions" in st.session_state and session_id in st.session_state.mock_sessions:
        st.session_state.mock_sessions[session_id]["is_locked"] = lock_status
        return True
    return False


def get_session_status(session_id: str) -> Optional[Dict[str, Any]]:
    """현재 세션의 잠금 상태 및 수업 설정을 조회합니다."""
    db = get_firestore_client()
    if db:
        try:
            doc = db.collection("running_sessions").document(session_id).get()
            return doc.to_dict() if doc.exists else None
        except Exception:
            return None

    return st.session_state.get("mock_sessions", {}).get(session_id)


def save_student_run_record(
    session_id: str,
    student_id: str,
    student_name: str,
    weight_code: str,
    route_metrics: Dict[str, Any],
) -> bool:
    """학생이 최적화한 러닝 코스 산출 지표와 생성 코드를 클라우드에 저장합니다."""
    db = get_firestore_client()
    record = {
        "student_id": student_id,
        "student_name": student_name,
        "session_id": session_id,
        "weight_code": weight_code,
        "metrics": {
            "total_distance_m": float(route_metrics.get("total_distance_m", 0.0)),
            "elevation_gain_m": float(route_metrics.get("elevation_gain_m", 0.0)),
            "avg_slope_pct": float(route_metrics.get("avg_slope_pct", 0.0)),
            "avg_shade_pct": float(route_metrics.get("avg_shade_pct", 0.0)),
        },
        "submitted_at": datetime.now().isoformat(),
    }

    if db:
        try:
            doc_id = f"{session_id}_{student_id}"
            db.collection("student_records").document(doc_id).set(record)
            return True
        except Exception:
            return False

    if "mock_records" not in st.session_state:
        st.session_state.mock_records = {}
    st.session_state.mock_records[f"{session_id}_{student_id}"] = record
    return True


def fetch_all_student_records(session_id: str) -> List[Dict[str, Any]]:
    """교사용 대시보드에서 학급 학생들의 경로 설계 제출 현황을 일괄 수집합니다."""
    db = get_firestore_client()
    if db:
        try:
            docs = (
                db.collection("student_records")
                .where("session_id", "==", session_id)
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception:
            return []

    mock_recs = st.session_state.get("mock_records", {})
    return [rec for rec in mock_recs.values() if rec.get("session_id") == session_id]