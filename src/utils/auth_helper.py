"""안정적인 세션 및 인증 동기화 헬퍼 모듈.

외부 서드파티 라이브러리 의존성을 제거하고,
URL Query Params 및 HTML5 스토리지 브릿지를 통해 새로고침 시에도 세션을 안전하게 복구합니다.
"""

from typing import Any, Dict, Optional
import base64
import hashlib
import hmac
import json
import streamlit as st


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


def sync_auth_session() -> None:
    """새로고침(F5) 시 URL의 session_token을 검증하여 로그인 상태를 복원합니다."""
    # 1. 이미 세션이 살아있는 경우
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

    # 2. 새로고침으로 세션이 날아갔을 때 토큰에서 복구
    token = st.query_params.get("session_token")
    if token:
        payload = _verify_and_decode_token(token)
        if payload and payload.get("auth") is True:
            st.session_state.authenticated = True
            st.session_state.user_role = payload.get("role")
            st.session_state.user_name = payload.get("user")
            st.session_state.class_code = payload.get("class_code", "CLASS_A")
            return

    # 3. 비인증 기본값 설정
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"


def set_login_session(role: str, user_name: str, class_code: str) -> None:
    """로그인 성공 시 세션 상태를 저장하고 서명 토큰을 URL에 고정합니다."""
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
    st.query_params["session_token"] = _generate_signed_token(payload)


def clear_login_session() -> None:
    """로그아웃 시 세션 및 URL 토큰을 즉시 초기화합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"
    st.query_params.clear()