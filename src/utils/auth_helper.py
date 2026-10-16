"""안정적인 세션 및 HMAC-SHA256 서명 토큰 헬퍼 모듈.

호출부의 인자 개수(3개/4개)나 키워드 전달 방식 차이로 인한 TypeError를 원천 방지합니다.
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
    """새로고침 시 URL의 ?session_token을 검증하여 로그인 상태를 자동 복원합니다."""
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

    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_id = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_2026_A"


def set_login_session(*args: Any, **kwargs: Any) -> None:
    """인자 개수/순서/키워드 형태와 무관하게 세션을 기록하는 가변 매개변수 함수."""
    # 위치 인자 또는 키워드 인자에서 role 추출
    role = kwargs.get("role")
    if role is None and len(args) >= 1:
        role = args[0]
    role = str(role or "student")

    # user_id 및 user_name 추출
    user_id = kwargs.get("user_id")
    user_name = kwargs.get("user_name") or kwargs.get("user")

    if user_id is None and user_name is None:
        if len(args) == 2:
            user_id = str(args[1])
            user_name = str(args[1])
        elif len(args) == 3:
            user_id = str(args[1])
            user_name = str(args[1])
        elif len(args) >= 4:
            user_id = str(args[1])
            user_name = str(args[2])

    user_id = str(user_id or user_name or "unknown")
    user_name = str(user_name or user_id)

    # class_code 추출
    class_code = kwargs.get("class_code")
    if class_code is None:
        if len(args) == 3:
            class_code = str(args[2])
        elif len(args) >= 4:
            class_code = str(args[3])
    class_code = str(class_code or "CLASS_2026_A")

    # 상태 저장
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_id = user_id
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    payload = {
        "auth": True,
        "role": role,
        "user_id": user_id,
        "user_name": user_name,
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