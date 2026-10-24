"""Gemini 기반 바이브 코딩 대화형 패널 컴포넌트.

학생 러너의 체력 조건, 부상 이력, 기상 환경에 맞춘 최적화 요구사항을 자연어로 입력받아
Gemini 모델과 대화형 인터랙션을 진행하고, 반환된 조별 컴포넌트 코드를
AST 검증기(sandbox_runner)와 연계하여 실시간으로 확인·수정할 수 있도록 지원합니다.
프롬프트가 모호하거나 단순할 경우 AI가 특정 핵심 기능을 의도적으로 누락한 코드를 제공합니다.
"""

from typing import Any, Dict, Optional, Tuple
import streamlit as st

from src.ai.gemini_client import MASTER_COMPONENTS, request_gemini_vibe_code
from src.ai.sandbox_runner import verify_code_security


def init_vibe_chat_state(team_id: str) -> None:
    """바이브 코딩 채팅 이력 및 활성 코드 세션 상태를 초기화합니다."""
    team_key = team_id.upper() if team_id.upper() in MASTER_COMPONENTS else "TEAM_1"
    comp_meta = MASTER_COMPONENTS[team_key]

    if "vibe_messages" not in st.session_state:
        st.session_state["vibe_messages"] = [
            {
                "role": "assistant",
                "content": (
                    f"안녕하세요! PAPSrun AI 페어 프로그래머입니다. 🏃‍♂️\n\n"
                    f"현재 우리 조의 담당 소프트웨어 컴포넌트는 **[{comp_meta['name']}]** 입니다.\n\n"
                    f"💡 **작성 팁**: 요구사항을 너무 짧거나 대충 입력하면 AI가 핵심 예외 처리나 필수 물리 조건을 누락한 채 코드를 작성할 수 있습니다. "
                    f"우리 조의 역할, 사용할 변수, 예외 방어 조건을 구체적으로 설명해 주세요!"
                ),
            }
        ]

    if "current_vibe_code" not in st.session_state:
        st.session_state["current_vibe_code"] = comp_meta["incomplete_code"]


def render_vibe_chat_sidebar(
    student_profile: Optional[Dict[str, Any]] = None,
    weather_info: Optional[Dict[str, Any]] = None,
) -> Tuple[str, bool]:
    """바이브 코딩 채팅 패널과 생성 코드 에디터를 렌더링합니다.

    Args:
        student_profile: 학생 PAPS 등급 및 체력 프로필 (선택)
        weather_info: 기온 및 순복사에너지 환경 정보 (선택)

    Returns:
        (현재 활성화된 파이썬 코드 문자열, 실행/적용 클릭 여부)
    """
    team_id = (student_profile or {}).get("team_id", "TEAM_1").upper()
    comp_meta = MASTER_COMPONENTS.get(team_id, MASTER_COMPONENTS["TEAM_1"])

    init_vibe_chat_state(team_id)

    st.markdown("#### ⚡ AI 바이브 코딩 관제소")
    st.caption(f"소속: **{team_id}** | 담당 컴포넌트: `{comp_meta['name']}`")

    # 1. 채팅 메시지 히스토리 컨테이너 (이전 대화 복원)
    chat_box = st.container(height=300)
    for msg in st.session_state["vibe_messages"]:
        with chat_box.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 2. 학생 자연어 프롬프트 입력창 (chat_input)
    user_prompt = st.chat_input("우리 조 컴포넌트에 필요한 요구사항을 입력하세요...")
    if user_prompt:
        st.session_state["vibe_messages"].append({"role": "user", "content": user_prompt})

        with st.spinner("AI가 프롬프트의 구체성을 평가하여 컴포넌트 코드를 작성 중입니다..."):
            extracted_code, ai_feedback = request_gemini_vibe_code(
                team_id=team_id,
                user_prompt=user_prompt,
            )

            if extracted_code:
                st.session_state["current_vibe_code"] = extracted_code

            st.session_state["vibe_messages"].append(
                {"role": "assistant", "content": ai_feedback}
            )
            st.rerun()

    st.divider()

    # 3. 실시간 생성 코드 에디터
    st.markdown("##### 📝 생성된 컴포넌트 소스코드")
    st.caption("AI가 작성한 코드입니다. 누락된 기능이 있다면 프롬프트를 보강하거나 직접 편집할 수 있습니다.")

    code_editor_val = st.text_area(
        label="파이썬 코드 검토 및 직접 편집",
        value=st.session_state["current_vibe_code"],
        height=220,
        key="vibe_code_editor_area",
    )
    st.session_state["current_vibe_code"] = code_editor_val

    # 4. AST 정적 구문 및 보안 검증기 연동
    is_safe, sec_error = verify_code_security(code_editor_val)
    if is_safe:
        st.success("✅ AST 구문 및 보안 검증 통과 (장착 가능)")
    else:
        st.error(f"⚠️ 문법/보안 오류 감지: {sec_error}")

    # 5. 컴포넌트 장착 및 통합 테스트 실행 버튼
    apply_clicked = st.button(
        "🚀 컴포넌트 장착 및 통합 테스트 실행",
        disabled=not is_safe,
        use_container_width=True,
        type="primary",
    )

    return code_editor_val, apply_clicked