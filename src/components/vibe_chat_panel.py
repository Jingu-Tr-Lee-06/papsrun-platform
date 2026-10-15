"""Gemini 기반 바이브 코딩 대화형 패널 컴포넌트.

학생 러너의 체력 조건, 부상 이력, 기상 환경에 맞춘 최적화 요구사항을 자연어로 입력받아
Gemini 모델과 대화형 인터랙션을 진행하고, 반환된 custom_weight_function 코드를
AST 검증기(sandbox_runner)와 연계하여 실시간으로 확인·수정할 수 있도록 지원합니다.
"""

from typing import Any, Dict, Optional, Tuple
import streamlit as st

from src.ai.code_extractor import extract_vibe_function_code
from src.ai.gemini_client import generate_vibe_code
from src.ai.sandbox_runner import verify_code_security


def init_vibe_chat_state() -> None:
    """바이브 코딩 채팅 이력 및 활성 코드 세션 상태를 초기화합니다."""
    if "vibe_messages" not in st.session_state:
        st.session_state["vibe_messages"] = [
            {
                "role": "assistant",
                "content": (
                    "안녕하세요! PAPSrun 바이브 코더입니다. 🏃‍♂️\n\n"
                    "어떤 러닝 코스를 설계하고 싶으신가요? "
                    "(예: '무릎 관절 보호를 위해 우레탄 트랙과 평지 위주', '직사광선을 피하는 시원한 그늘 코스')"
                ),
            }
        ]

    if "current_vibe_code" not in st.session_state:
        # 기본 균형형 가중치 함수 템플릿
        st.session_state["current_vibe_code"] = (
            "def custom_weight_function(u, v, edge_dict):\n"
            "    length = edge_dict.get('length', 1.0)\n"
            "    slope = edge_dict.get('slope', 0.0)\n"
            "    surface = edge_dict.get('surface_type', 'concrete_walkway')\n"
            "    is_shaded = edge_dict.get('is_shaded', False)\n\n"
            "    surface_mult = 0.8 if surface == 'urethane_track' else 1.2\n"
            "    shade_mult = 0.85 if is_shaded else 1.15\n"
            "    slope_mult = 1.0 + max(0.0, slope) * 0.08\n\n"
            "    return length * surface_mult * shade_mult * slope_mult"
        )


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
    init_vibe_chat_state()

    st.markdown("#### ⚡ AI 바이브 코딩 파트너")
    st.caption("자연어로 경로 조건을 설명하면 다익스트라 가중치 함수가 자동 생성됩니다.")

    # 1. 채팅 메시지 히스토리 출력 (컨테이너 제한)
    chat_box = st.container(height=320)
    for msg in st.session_state["vibe_messages"]:
        with chat_box.chat_message(msg["role"]):
            st.markdown(msg["content"])

    # 2. 학생 프롬프트 입력창
    user_prompt = st.chat_input("원하는 러닝 경로 특성을 입력하세요...")
    if user_prompt:
        # 사용자 메시지 추가
        st.session_state["vibe_messages"].append({"role": "user", "content": user_prompt})

        with st.spinner("Gemini가 물리/지형 알고리즘을 분석하여 코드를 작성 중입니다..."):
            ai_response = generate_vibe_code(
                user_requirements=user_prompt,
                student_profile=student_profile,
                weather_info=weather_info,
            )

            # 코드 블록 추출
            extracted_code = extract_vibe_function_code(ai_response)
            if extracted_code:
                st.session_state["current_vibe_code"] = extracted_code

            st.session_state["vibe_messages"].append(
                {"role": "assistant", "content": ai_response}
            )
            st.rerun()

    st.divider()

    # 3. 실시간 생성 코드 뷰어 및 에디터
    st.markdown("##### 📝 생성된 다익스트라 가중치 함수 (`custom_weight_function`)")
    
    code_editor_val = st.text_area(
        label="파이썬 코드 검토 및 직접 편집",
        value=st.session_state["current_vibe_code"],
        height=200,
        help="def custom_weight_function(u, v, edge_dict) 형태를 유지해야 합니다.",
    )
    st.session_state["current_vibe_code"] = code_editor_val

    # 4. AST 정적 보안 검증 결과 피드백
    is_safe, sec_error = verify_code_security(code_editor_val)
    if is_safe:
        st.success("✅ AST 구문 및 보안 검증 통과 (실행 가능)")
    else:
        st.error(f"⚠️ 보안/문법 오류 감지: {sec_error}")

    apply_clicked = st.button(
        "🚀 가중치 함수 적용 및 경로 탐색 실행",
        disabled=not is_safe,
        use_container_width=True,
    )

    return code_editor_val, apply_clicked