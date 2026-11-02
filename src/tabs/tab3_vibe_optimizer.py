"""PAPSrun 3단계: AI 바이브 코딩 스튜디오 (Full Live Streaming + Master Code 방출)."""

from typing import Any, Dict, Optional
import streamlit as st

from src.ai.gemini_client import (
    ROLE_CATALOG,
    check_ollama_status,
    detect_role_from_prompt,
    stream_hybrid_vibe_dialogue,
)


def render_tab3_vibe_optimizer(class_code: str, student_identifier: str = "student_01") -> None:
    """3단계: AI 바이브 코딩 스튜디오 메인 탭."""
    
    # 1. 상단 타이틀 및 AI 서버 연결 뱃지
    col_title, col_status = st.columns([2.5, 1.5])
    with col_title:
        st.markdown("### ⚡ 3단계: AI 바이브 코딩 스튜디오")
        st.caption("Qwen AI 튜터와 대화하며 나만의 러닝 알고리즘 모듈을 완성해 보세요.")
    
    with col_status:
        ai_stat = check_ollama_status("qwen2.5:3b-4k")
        if ai_stat["online"] and ai_stat["model_loaded"]:
            st.success("🟢 **AI 튜터 Online** (`Qwen 3B`)")
        elif ai_stat["online"]:
            st.warning("🟡 **AI 튜터 대기 중**")
        else:
            st.error("🔴 **AI 튜터 오프라인**")

    # 세션 초기화
    if "vibe_messages" not in st.session_state:
        st.session_state["vibe_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "👨‍🏫 **반가워요! PAPSrun 알고리즘 코딩 수업을 함께할 AI 튜터 선생님이에요.**\n\n"
                    "오늘 우리 학생은 20개 역할 중 몇 번 파트를 맡으셨나요? 편하게 말씀해 주세요!\n"
                    "*(예: '선생님 저 2번 그늘 계산 맡았어요!', '경사도 구하는 파트예요')*"
                ),
            }
        ]

    # 현재 역할 상태 확인
    assigned_role = st.session_state.get("assigned_student_role")
    
    col_info, col_reset = st.columns([4, 1])
    with col_info:
        if assigned_role and assigned_role in ROLE_CATALOG:
            info = ROLE_CATALOG[assigned_role]
            st.success(
                f"🎯 **현재 담당 모듈**: `[{assigned_role}] {info['title']}` "
                f"(`final_code/{info['team']}/{info['file']}`)"
            )
        else:
            st.info("💡 **안내**: 채팅창에 오늘 맡은 역할(예: '2번', '그늘 계산')을 말씀하시면 모듈이 자동 연결됩니다.")

    with col_reset:
        if st.button("🔄 대화 초기화", use_container_width=True, help="채팅과 배정 역할을 초기화합니다."):
            st.session_state["vibe_messages"] = [
                {
                    "role": "assistant",
                    "content": "👨‍🏫 **대화가 초기화되었습니다!** 오늘 몇 번 역할을 구현해 볼까요?",
                }
            ]
            st.session_state["assigned_student_role"] = None
            st.rerun()

    st.markdown("---")

    # 고정 높이 채팅 컨테이너
    chat_container = st.container(height=520)

    # 기존 대화 이력 출력
    with chat_container:
        for msg in st.session_state["vibe_messages"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # 사용자 프롬프트 입력창
    user_input = st.chat_input("선생님에게 질문하거나 코드 요구사항을 말씀해 주세요...")

    if user_input:
        # 입력 문장에서 역할 자동 감지
        if not assigned_role:
            detected = detect_role_from_prompt(user_input)
            if detected:
                st.session_state["assigned_student_role"] = detected
                assigned_role = detected

        # 1. 사용자 메시지 추가 및 렌더링
        st.session_state["vibe_messages"].append({"role": "user", "content": user_input})
        with chat_container:
            with st.chat_message("user"):
                st.markdown(user_input)

            # 2. 실시간 라이브 스트리밍 (대화는 Qwen, 코드는 final_code 파일 원본 방출)
            with st.chat_message("assistant"):
                token_stream = stream_hybrid_vibe_dialogue(
                    messages=st.session_state["vibe_messages"],
                    assigned_role=assigned_role,
                )
                full_reply = st.write_stream(token_stream)

        # 3. 완료된 응답 세션 저장
        st.session_state["vibe_messages"].append({"role": "assistant", "content": full_reply})
        st.rerun()