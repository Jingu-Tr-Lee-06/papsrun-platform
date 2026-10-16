"""인증 세션 및 브라우저 URL 쿼리 동기화 헬퍼 모듈.

Streamlit의 st.query_params와 st.session_state를 동기화하여
새로고침(F5) 시에도 중복 키 에러 없이 로그인 상태를 안정적으로 유지합니다.
"""

from typing import Any, Dict, Optional
import streamlit as st


def sync_auth_session() -> None:
    """페이지 초기화 시 URL 쿼리 파라미터를 읽어 세션을 자동 복원합니다."""
    # 1. 이미 세션 메모리가 살아있다면 URL 쿼리 파라미터와 동기화만 유지
    if st.session_state.get("authenticated", False):
        if not st.query_params.get("auth"):
            st.query_params["auth"] = "true"
            st.query_params["role"] = str(st.session_state.get("user_role", ""))
            st.query_params["user"] = str(st.session_state.get("user_name", ""))
            st.query_params["class_code"] = str(st.session_state.get("class_code", "CLASS_A"))
        return

    # 2. 브라우저 새로고침(F5)으로 메모리가 날아간 경우 URL 쿼리 파라미터에서 복원
    qp = st.query_params
    if qp.get("auth") == "true" and qp.get("role") and qp.get("user"):
        st.session_state.authenticated = True
        st.session_state.user_role = qp.get("role")
        st.session_state.user_name = qp.get("user")
        st.session_state.class_code = qp.get("class_code", "CLASS_A")
    else:
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = ""
        st.session_state.class_code = qp.get("class_code", "CLASS_A")


def set_login_session(role: str, user_name: str, class_code: str) -> None:
    """로그인 성공 시 세션 상태를 저장하고 URL 쿼리 파라미터에 기록합니다."""
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    # URL 주소창에 파라미터를 고정하여 F5 새로고침 시에도 복원되도록 보장
    st.query_params["auth"] = "true"
    st.query_params["role"] = role
    st.query_params["user"] = user_name
    st.query_params["class_code"] = class_code


def clear_login_session() -> None:
    """로그아웃 시 세션 상태 및 URL 쿼리 파라미터를 완전히 초기화합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "CLASS_A"
    st.query_params.clear()