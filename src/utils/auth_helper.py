"""HMAC-SHA256 기반 보안 세션 토큰 헬퍼 모듈.

URL 쿼리 파라미터 변조(학생의 교사 권한 탈취, 학번 도용 등)를 원천 차단하기 위해
서버 시크릿 키로 암호학적 무결성 서명(HMAC-SHA256)이 결합된 토큰을 발급하고 검증합니다.
"""

from typing import Any, Dict, Optional
import base64
import hashlib
import hmac
import json
import streamlit as st


def _get_server_secret() -> str:
    """토큰 무결성 서명에 사용할 서버 비밀키를 반환합니다."""
    return st.secrets.get("AUTH_SECRET_KEY", "papsrun_server_master_hmac_2026_!@#$")


def _generate_signed_token(payload: Dict[str, Any]) -> str:
    """페이로드 딕셔너리를 직렬화하고 HMAC-SHA256 서명을 부착한 보안 토큰을 생성합니다."""
    secret = _get_server_secret().encode("utf-8")
    json_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(json_bytes).decode("utf-8")

    # 서버 비밀키 기반 HMAC-SHA256 디지털 서명 생성
    signature = hmac.new(secret, b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{signature}"


def _verify_and_decode_token(token: str) -> Optional[Dict[str, Any]]:
    """보안 토큰의 위·변조 여부를 검증하고 원본 데이터를 복원합니다. 변조 시 None 반환."""
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None

        b64_payload, signature = parts[0], parts[1]
        secret = _get_server_secret().encode("utf-8")

        # 서명 검증 (타이밍 공격 방지 hmac.compare_digest)
        expected_sig = hmac.new(secret, b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected_sig):
            return None

        json_bytes = base64.urlsafe_b64decode(b64_payload.encode("utf-8"))
        return json.loads(json_bytes.decode("utf-8"))
    except Exception:
        return None


# ==============================================================================
# 공개 인터페이스
# ==============================================================================
def sync_auth_session() -> None:
    """새로고침 시 URL의 ?session_token을 검증하여 안전하게 로그인 세션을 복원합니다."""
    # 1. 메모리 세션이 유지되어 있는 경우 토큰 동기화 확인
    if st.session_state.get("authenticated", False):
        if not st.query_params.get("session_token"):
            payload = {
                "auth": True,
                "role": st.session_state.get("user_role"),
                "user": st.session_state.get("user_name"),
                "class_code": st.session_state.get("class_code", "CLASS_A"),
            }
            st.query_params["session_token"] = _generate_signed_token(payload)
        return

    # 2. 브라우저 새로고침(F5) 시 서명 토큰 검증 및 복구
    token = st.query_params.get("session_token")
    if token:
        payload = _verify_and_decode_token(token)
        if payload and payload.get("auth") is True:
            st.session_state.authenticated = True
            st.session_state.user_role = payload.get("role")
            st.session_state.user_name = payload.get("user")
            st.session_state.class_code = payload.get("class_code", "CLASS_A")
            return

    # 3. 토큰이 없거나 변조된 경우 세션 초기화
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"


def set_login_session(role: str, user_name: str, class_code: str) -> None:
    """로그인 시 세션에 저장하고, 변조 불가능한 서명 토큰만 URL 쿼리에 고정합니다."""
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    # URL에는 아이디나 역할 평문 대신 암호학적 서명 토큰 1개만 노출
    payload = {
        "auth": True,
        "role": role,
        "user": user_name,
        "class_code": class_code,
    }
    st.query_params.clear()
    st.query_params["session_token"] = _generate_signed_token(payload)


def clear_login_session() -> None:
    """로그아웃 시 세션 및 URL 토큰을 즉시 무효화합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"
    st.query_params.clear()