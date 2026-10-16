"""HMAC-SHA256 보안 세션 토큰 및 상태 동기화 헬퍼 모듈."""

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
    """새로고침 시 URL의 ?session_token을 검증하여 로그인 상태를 자동 복원합니다."""
    # 1. 이미 메모리에 인증 세션이 살아있는 경우
    if st.session_state.get("authenticated", False):
        if not st.query_params.get("session_token"):
            payload = {
                "auth": True,
                "role": st.session_state.get("user_role"),
                "user_id": st.session_state.get("user_id"),
                "user_name": st.session_state.get("user_name"),
                "class_code": st.session_state.get("class_code", "CLASS_2026_A"),
            }
            st.query_params["session_token"] = _generate_signed_token(payload)
        return

    # 2. 브라우저 새로고침(F5) 시 URL 토큰으로부터 복구
    token = st.query_params.get("session_token")
    if token:
        payload = _verify_and_decode_token(token)
        if payload and payload.get("auth") is True:
            st.session_state.authenticated = True
            st.session_state.user_role = payload.get("role")
            st.session_state.user_id = payload.get("user_id") or payload.get("user_name")
            st.session_state.user_name = payload.get("user_name") or payload.get("user_id")
            st.session_state.class_code = payload.get("class_code", "CLASS_2026_A")
            return

    # 3. 비인증 기본값
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_id = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_2026_A"


def set_login_session(
    role: str,
    user_name: str = "",
    class_code: str = "CLASS_2026_A",
    user_id: Optional[str] = None,
    **kwargs: Any,
) -> None:
    """로그인 상태를 세션과 URL 파라미터(토큰)에 저장합니다.
    
    인자 순서나 개수(3개/4개) 차이로 인한 TypeError를 방지하도록 설계되었습니다.
    """
    actual_user_id = user_id or kwargs.get("user_id") or user_name
    actual_user_name = user_name or actual_user_id

    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_id = actual_user_id
    st.session_state.user_name = actual_user_name
    st.session_state.class_code = class_code

    payload = {
        "auth": True,
        "role": role,
        "user_id": actual_user_id,
        "user_name": actual_user_name,
        "class_code": class_code,
    }
    st.query_params["session_token"] = _generate_signed_token(payload)


def clear_login_session() -> None:
    """로그아웃 시 세션 및 URL 토큰을 즉시 초기화합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_id = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_2026_A"
    st.query_params.clear()