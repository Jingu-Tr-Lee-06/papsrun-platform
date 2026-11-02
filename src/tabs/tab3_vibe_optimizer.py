"""PAPSrun 3단계: AI 바이브 코딩 스튜디오 (실시간 타이핑 스트리밍 지원).

st.write_stream()을 활용해 Ollama Qwen SLM의 토큰 생성 속도에 맞춰
글자가 실시간으로 작성되는 타이핑 효과를 연출합니다.
"""

from typing import Any, Dict, Optional
import streamlit as st

from src.ai.gemini_client import (
    ROLE_CATALOG,
    check_ollama_status,
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
        "• *'3번 복사에너지 공식 짜줘'*\n\n"
        "💡 말씀해 주시면 담당 파일(`student_XX.py`)과 기초 코드를 즉시 연결해 드릴게요!"
    )


def render_tab3_vibe_optimizer(class_code: str, student_identifier: str = "student_01") -> None:
    """3단계: AI 바이브 코딩 스튜디오 (실시간 타이핑 롸이팅 전용 뷰)."""
    
    # 1. 상단 헤더 및 조작 버튼 영역
    col_title, col_status = st.columns([2.5, 1.5])
    with col_title:
        st.markdown("### ⚡ 3단계: AI 바이브 코딩 스튜디오")
        st.caption("선생님 AI와 대화하며 나만의 모듈 코드를 완성하고, 내 파일에 적용해 보세요.")
    
    with col_status:
        # AI 서버 상태 점검
        ai_stat = check_ollama_status("qwen2.5:3b-4k")
        if ai_stat["online"] and ai_stat["model_loaded"]:
            st.success("🟢 **AI 서버 연결됨** (`Qwen 3B`)")
        elif ai_stat["online"]:
            st.warning("🟡 **AI 모델 대기 중**")
        else:
            st.error("🔴 **AI 서버 오프라인**")

    # 세션 상태 초기화
    if "vibe_messages" not in st.session_state:
        st.session_state["vibe_messages"] = [
            {"role": "assistant", "content": get_teacher_greeting()}
        ]
    if "prompt_retry_count" not in st.session_state:
        st.session_state["prompt_retry_count"] = 0

    # 2. 역할 및 실습 진행 상태 알림바
    assigned_role = st.session_state.get("assigned_student_role")
    
    col_info, col_reset = st.columns([4, 1])
    with col_info:
        if assigned_role and assigned_role in ROLE_CATALOG:
            info = ROLE_CATALOG[assigned_role]
            retry = st.session_state.get("prompt_retry_count", 0)
            retry_badge = f" (스캐폴딩 힌트 단계: {min(retry, 3)}/3)" if retry > 0 else ""
            st.success(
                f"🎯 **현재 연결된 담당 모듈**: `[{assigned_role}] {info['title']}` "
                f"| 파일: `final_code/{info['team']}/{info['file']}`{retry_badge}"
            )
        else:
            st.info("💡 **안내**: 아래 채팅창에 오늘 담당한 번호나 기능(예: '2번', '그늘 계산')을 말씀해 주시면 모듈이 연결됩니다.")

    with col_reset:
        if st.button("🔄 대화 및 역할 초기화", use_container_width=True, help="채팅 기록과 배정된 역할을 초기 상태로 되돌립니다."):
            st.session_state["vibe_messages"] = [
                {"role": "assistant", "content": get_teacher_greeting()}
            ]
            st.session_state["assigned_student_role"] = None
            st.session_state["prompt_retry_count"] = 0
            st.rerun()

    st.markdown("---")

    # 3. 고정 높이 대화 스크롤 컨테이너
    chat_container = st.container(height=520)

    # 기존 대화 이력 렌더링
    with chat_container:
        for msg in st.session_state["vibe_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 4. 사용자 프롬프트 입력창
    user_input = st.chat_input("선생님에게 맡은 역할이나 필요한 코드 로직을 자유롭게 말씀해 주세요...")

    if user_input:
        # 사용자 메시지 즉시 렌더링 및 세션 저장
        st.session_state["vibe_messages"].append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

            # AI 튜터 스트리밍 응답 (Ollama Qwen 실시간 타이핑 효과)
            with st.chat_message("assistant"):
                token_stream = stream_gemini_vibe_code(
                    team_id=assigned_role or student_identifier,
                    user_prompt=user_input,
                )
                full_reply = st.write_stream(token_stream)

        # 응답 완료 후 세션 동기화
        st.session_state["vibe_messages"].append({"role": "assistant", "content": full_reply})
        st.rerun()