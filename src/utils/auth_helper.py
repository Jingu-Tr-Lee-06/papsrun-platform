"""브라우저 window.localStorage 기반 영구 세션 관리 헬퍼 모듈.

Streamlit 페이지 이동(switch_page) 및 F5 새로고침 시에도
브라우저 스토리지와 HMAC-SHA256 서명 토큰을 대조하여 세션을 영구 유지합니다.
"""

from typing import Any, Dict, Optional
import base64
import hashlib
import hmac
import json
import streamlit as st
from streamlit_javascript import st_javascript


def _get_server_secret() -> str:
    return st.secrets.get("AUTH_SECRET_KEY", "papsrun_server_master_hmac_2026_!@#$")


def _generate_signed_token(payload: Dict[str, Any]) -> str:
    secret = _get_server_secret().encode("utf-8")
    json_bytes = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(json_bytes).decode("utf-8")
    signature = hmac.new(secret, b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{signature}"


def _verify_and_decode_token(token: str) -> Optional[Dict[str, Any]]:
    if not token or not isinstance(token, str):
        return None
    try:
        parts = token.split(".")
        if len(parts) != 2:
            return None
        b64_payload, signature = parts[0], parts[1]
        secret = _get_server_secret().encode("utf-8")
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
    """새로고침 시 브라우저 localStorage에서 토큰을 읽어와 로그인 상태를 복원합니다."""
    # 이미 메모리 세션이 유지되고 있으면 재검증 생략
    if st.session_state.get("authenticated", False):
        return

    # 브라우저 window.top.localStorage에서 직접 토큰 조회
    local_token = st_javascript("window.top.localStorage.getItem('papsrun_auth_token');")

    if local_token and isinstance(local_token, str):
        payload = _verify_and_decode_token(local_token)
        if payload and payload.get("auth") is True:
            st.session_state.authenticated = True
            st.session_state.user_role = payload.get("role")
            st.session_state.user_name = payload.get("user")
            st.session_state.class_code = payload.get("class_code", "CLASS_A")
            st.rerun()


def set_login_session(role: str, user_name: str, class_code: str) -> None:
    """로그인 시 세션에 저장하고, 브라우저 window.top.localStorage에 서명 토큰을 기록합니다."""
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    payload = {
        "auth": True,
        "role": role,
        "user": user_name,
        "class_code": class_code,
    }
    signed_token = _generate_signed_token(payload)

    # 브라우저 최상위 로컬스토리지에 저장 실행
    st_javascript(f"window.top.localStorage.setItem('papsrun_auth_token', '{signed_token}');")


def clear_login_session() -> None:
    """로그아웃 시 세션 및 브라우저 스토리지의 토큰을 즉시 삭제합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"

    st_javascript("window.top.localStorage.removeItem('papsrun_auth_token');")