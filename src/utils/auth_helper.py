"""브라우저 쿠키 기반 로그인 세션 영구 유지 헬퍼 모듈.

Streamlit 새로고침(F5) 시에도 브라우저 쿠키(papsrun_session)를 통해
로그인 인증 상태를 자동으로 복원합니다.
"""

from datetime import datetime, timedelta
import json
import extra_streamlit_components as stx
import streamlit as st


def get_cookie_manager():
    """CookieManager 싱글톤 인스턴스를 반환합니다."""
    return stx.CookieManager(key="papsrun_cookie_mgr")


def sync_auth_session():
    """페이지 로드 시 쿠키를 읽어 세션 상태를 복원합니다."""
    # 이미 세션이 살아있으면 통과
    if st.session_state.get("authenticated", False):
        return

    cookie_mgr = get_cookie_manager()
    cookie_val = cookie_mgr.get("papsrun_session")

    if cookie_val:
        try:
            if isinstance(cookie_val, str):
                data = json.loads(cookie_val)
            else:
                data = cookie_val

            if data.get("authenticated"):
                st.session_state.authenticated = True
                st.session_state.user_role = data.get("role")
                st.session_state.user_name = data.get("user")
                st.session_state.class_code = data.get("class_code", "KNU_2026_01")
        except Exception:
            pass


def set_login_session(role: str, user_name: str, class_code: str):
    """로그인 시 세션에 저장하고 유효기간 7일짜리 브라우저 쿠키를 생성합니다."""
    st.session_state.authenticated = True
    st.session_state.user_role = role
    st.session_state.user_name = user_name
    st.session_state.class_code = class_code

    cookie_mgr = get_cookie_manager()
    payload = json.dumps({
        "authenticated": True,
        "role": role,
        "user": user_name,
        "class_code": class_code,
    })

    # 브라우저에 쿠키 굽기 (7일간 유지)
    cookie_mgr.set(
        cookie="papsrun_session",
        val=payload,
        expires_at=datetime.now() + timedelta(days=7),
    )


def clear_login_session():
    """로그아웃 시 세션 초기화 및 쿠키를 삭제합니다."""
    st.session_state.authenticated = False
    st.session_state.user_role = None
    st.session_state.user_name = ""
    st.session_state.class_code = "KNU_2026_01"

    cookie_mgr = get_cookie_manager()
    try:
        cookie_mgr.delete("papsrun_session")
    except Exception:
        pass