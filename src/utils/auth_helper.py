"""브라우저 localStorage 기반 로그인 세션 영구 유지 헬퍼 모듈.

Streamlit 새로고침(F5) 시 session_state 초기화 현상을 방지하기 위해
브라우저 localStorage와 streamlit session_state를 양방향 동기화합니다.
"""

import json
import streamlit as st
import streamlit.components.v1 as components


def sync_auth_session():
    """브라우저와 Streamlit 세션 상태를 동기화하고 새로고침 시 복원합니다."""
    # 1. 쿼리 파라미터 기반 복원 (우선순위 1)
    qp = st.query_params
    if not st.session_state.get("authenticated", False):
        if qp.get("auth") == "true" and qp.get("role") and qp.get("user"):
            st.session_state.authenticated = True
            st.session_state.user_role = qp.get("role")
            st.session_state.user_name = qp.get("user")
            st.session_state.class_code = qp.get("class_code", "KNU_2026_01")


def set_login_session(role: str, user_name: str, class_code: str):
    """로그인 성공 시 세션 상태, 쿼리 파라미터 및 브라우저 localStorage에 저장합니다."""
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    # URL 쿼리 파라미터 동기화
    st.query_params["auth"] = "true"
    st.query_params["role"] = role
    st.query_params["user"] = user_name
    st.query_params["class_code"] = class_code

    # 브라우저 localStorage에 영구 보관 (스크립트 실행)
    auth_data = json.dumps({
        "auth": "true",
        "role": role,
        "user": user_name,
        "class_code": class_code,
    })
    components.html(
        f"""
        <script>
            localStorage.setItem('papsrun_auth', '{auth_data}');
        </script>
        """,
        height=0,
        width=0,
    )


def clear_login_session():
    """로그아웃 시 세션 상태, 쿼리 파라미터 및 localStorage를 완전 초기화합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "KNU_2026_01"
    st.query_params.clear()

    components.html(
        """
        <script>
            localStorage.removeItem('papsrun_auth');
        </script>
        """,
        height=0,
        width=0,
    )