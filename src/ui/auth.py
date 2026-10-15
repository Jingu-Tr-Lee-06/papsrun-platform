"""사용자 인증 및 세션 상태(Session State) 관리 모듈.

교사 및 학생 모둠별 세션 상태를 격리하여 관리하고,
교사 PIN 인증 및 교사용 Gemini API 키의 인메모리 주입을 안전하게 처리합니다.
"""

from typing import Optional
import streamlit as st


def init_session_state() -> None:
    """Streamlit 세션 상태의 기본 키들을 안전하게 초기화합니다."""
    default_states = {
        "user_role": "student",          # 'teacher' 또는 'student'
        "is_authenticated": False,       # 교사 인증 완료 여부
        "class_code": "CLASS_2026_A",    # 현재 활성 학급 코드
        "team_id": "1모둠",              # 학생 모둠명
        "student_name": "러너A",          # 학생 이름
        "teacher_gemini_key": "",        # 교사가 직접 입력한 Gemini API 키 (인메모리 전용)
        "current_step": 1,               # 5단계 워크플로우 진행 단계 (1~5)
    }

    for key, val in default_states.items():
        if key not in st.session_state:
            st.session_state[key] = val


def verify_teacher_pin(input_pin: str) -> bool:
    """입력된 PIN 번호를 secrets.toml 또는 기본 마스터 키와 대조합니다.

    Args:
        input_pin: 교사가 입력한 비밀번호 문자열

    Returns:
        인증 성공 여부 (bool)
    """
    auth_secrets = st.secrets.get("auth", {})
    master_pin = auth_secrets.get("teacher_pin", "admin1234").strip()
    return input_pin.strip() == master_pin


def render_auth_sidebar() -> None:
    """사이드바 상단에 학급/모둠 설정 및 교사 모드 전환 UI를 렌더링합니다."""
    init_session_state()

    st.sidebar.markdown("### 🏃 PAPSrun 세션 제어")

    # 학급 코드 및 모둠 설정
    class_code_input = st.sidebar.text_input(
        "학급 코드 (Class Code)",
        value=st.session_state["class_code"],
        help="같은 반 학생들과 도로망을 공유하기 위한 고유 학급 코드입니다.",
    )
    if class_code_input != st.session_state["class_code"]:
        st.session_state["class_code"] = class_code_input.strip() or "CLASS_2026_A"

    # 역할 토글 (학생 vs 교사)
    role_options = ["학생 모둠 (Student)", "지도 교사 (Teacher)"]
    current_index = 1 if st.session_state["user_role"] == "teacher" else 0
    selected_role = st.sidebar.radio("접속 모드", role_options, index=current_index)

    if selected_role == "학생 모둠 (Student)":
        st.session_state["user_role"] = "student"
        col1, col2 = st.sidebar.columns(2)
        with col1:
            team_val = st.text_input("모둠명", value=st.session_state["team_id"])
            st.session_state["team_id"] = team_val.strip() or "1모둠"
        with col2:
            name_val = st.text_input("러너명", value=st.session_state["student_name"])
            st.session_state["student_name"] = name_val.strip() or "학생"

    else:
        # 교사 모드 선택 시 PIN 인증
        st.session_state["user_role"] = "teacher"
        if not st.session_state["is_authenticated"]:
            pin_input = st.sidebar.text_input("교사 PIN 번호", type="password")
            if st.sidebar.button("교사 권한 인증", use_container_width=True):
                if verify_teacher_pin(pin_input):
                    st.session_state["is_authenticated"] = True
                    st.sidebar.success("인증 완료되었습니다.")
                    st.rerun()
                else:
                    st.sidebar.error("PIN 번호가 일치하지 않습니다.")
        else:
            st.sidebar.success("🔑 교사 권한 활성화됨")
            if st.sidebar.button("로그아웃", use_container_width=True):
                st.session_state["is_authenticated"] = False
                st.session_state["user_role"] = "student"
                st.rerun()

    st.sidebar.divider()


def get_active_gemini_key() -> Optional[str]:
    """현재 세션에서 유효한 교사 입력 Gemini API 키를 반환합니다.

    Returns:
        세션에 등록된 API 키 또는 None
    """
    key = st.session_state.get("teacher_gemini_key", "").strip()
    return key if key else None