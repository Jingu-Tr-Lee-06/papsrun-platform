"""PAPSrun 3단계: AI 바이브 코딩 스튜디오 (실시간 타이핑 스트리밍 지원).

st.write_stream()을 활용해 Ollama Qwen SLM의 토큰 생성 속도에 맞춰
제미나이처럼 글자가 한 글자씩 실시간으로 작성되는 롸이팅 효과를 연출합니다.
"""

from typing import Any, Dict, Optional
import streamlit as st

from src.ai.gemini_client import (
    ROLE_CATALOG,
    detect_role_from_prompt,
    read_master_code,
    stream_gemini_vibe_code,
)


def get_teacher_greeting() -> str:
    """선생님다운 어조의 초기 환영 안내 멘트."""
    return (
        "👨‍🏫 **반가워요! PAPSrun 코딩 수업을 함께할 AI 튜터 선생님이에요.**\n\n"
        "우리 지난 차시까지 모은 환경 데이터와 체육 실측 데이터를 바탕으로 멋진 러닝 경로 서비스를 완성해 볼 텐데요,\n"
        "**오늘 우리 학생은 20개 역할 중 어떤 파트를 맡아 구현해보고 싶나요?**\n\n"
        "편하게 평소 대화하듯 말씀해 주세요:\n"
        "• *'선생님, 저 2번 그늘 차광률 계산 맡았어요!'*\n"
        "• *'오르막길 경사도(%) 계산하는 함수 구현하고 싶어요'*\n"
        "• *'심박수 예측하는 머신러닝 추론 함수 만들래요'*\n\n"
        "💡 말씀해 주시면 담당 파일(`student_XX.py`)과 기초 코드를 즉시 연결해 드릴게요!"
    )


def render_tab3_vibe_optimizer(class_code: str, student_identifier: str = "student_01") -> None:
    """3단계: AI 바이브 코딩 스튜디오 (실시간 타이핑 롸이팅 전용 뷰)."""
    st.markdown("### ⚡ 3단계: AI 바이브 코딩 스튜디오")
    st.caption("선생님 AI와 대화하며 나만의 모듈 코드를 완성하고, 코드를 복사하여 내 파일에 적용해 보세요.")

    # 세션 상태 초기화
    if "vibe_messages" not in st.session_state:
        st.session_state["vibe_messages"] = [
            {"role": "assistant", "content": get_teacher_greeting()}
        ]

    # 현재 배정된 역할 배지 안내
    assigned_role = st.session_state.get("assigned_student_role")
    if assigned_role and assigned_role in ROLE_CATALOG:
        info = ROLE_CATALOG[assigned_role]
        st.success(
            f"🎯 **현재 연결된 담당 모듈**: `[{assigned_role}] {info['title']}` "
            f"(파일: `final_code/{info['team']}/{info['file']}`)"
        )
    else:
        st.info("💡 **안내**: 아래 채팅창에 오늘 담당한 번호나 기능(예: '2번', '그늘 계산')을 말씀해 주시면 모듈이 연결됩니다.")

    st.markdown("---")

    # 💡 고정 높이 스크롤 컨테이너
    chat_container = st.container(height=560)

    # 기존 대화 이력 렌더링
    with chat_container:
        for msg in st.session_state["vibe_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 사용자 프롬프트 입력창
    user_input = st.chat_input("선생님에게 맡은 역할이나 필요한 코드 로직을 자유롭게 말씀해 주세요...")

    if user_input:
        # 1. 사용자 메시지 즉시 렌더링 및 세션 저장
        st.session_state["vibe_messages"].append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

            # 2. AI 튜터 스트리밍 응답 (제미나이 실시간 타이핑 롸이팅 효과)
            with st.chat_message("assistant"):
                token_stream = stream_gemini_vibe_code(
                    team_id=assigned_role or student_identifier,
                    user_prompt=user_input,
                )
                # st.write_stream이 제너레이터를 받아서 토큰 단위로 실시간 타자를 침
                full_reply = st.write_stream(token_stream)

        # 3. 완료된 전체 메시지 세션 저장
        st.session_state["vibe_messages"].append({"role": "assistant", "content": full_reply})
        st.rerun()