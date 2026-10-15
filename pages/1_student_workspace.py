"""학생용 5단계 STEAM 통합 학습 워크스페이스 메인 페이지.

1단계: 지형·환경 도로망 연속 작도 (Map Builder)
2단계: 도로망 위상 및 연결성 진단 (Topology Checker)
3단계: Gemini 바이브 코딩 & 다익스트라 경로 최적화 (Vibe Optimizer)
4단계: 웹 VS Code 작업 영역 (VS Code Workspace)
5단계: 엣지 디바이스 구동 및 산출물 리포트 (Edge Dispatch & Artifact)
"""

import streamlit as st

from src.db.class_session_manager import get_class_session_config
from src.tabs.tab1_map_builder import render_tab1_map_builder
from src.tabs.tab2_topology_checker import render_tab2_topology_checker
from src.tabs.tab3_vibe_optimizer import render_tab3_vibe_optimizer
from src.tabs.tab4_vscode_workspace import render_tab4_vscode_workspace
from src.tabs.tab5_edge_runner_artifact import render_tab5_edge_runner_artifact

# Streamlit 페이지 메타데이터 설정 (브라우저 탭 및 상단 UI)
st.set_page_config(
    page_title="학생 학습 워크스페이스 - PAPSrun",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)


def render_student_workspace_page() -> None:
    """학생 워크스페이스 페이지 메인 렌더러."""
    # 1. 사이드바 세션 설정 및 프로필
    st.sidebar.title("🎓 학생 워크스페이스")
    st.sidebar.caption("PAPSrun 스마트 캠퍼스 러닝 코스 설계 프로젝트")

    class_code = st.sidebar.text_input(
        "학급 코드 (Class Code)",
        value=st.session_state.get("current_class_code", "CLASS_2026_A"),
        help="선생님께 안내받은 학급 코드를 입력하세요.",
    ).strip()
    st.session_state["current_class_code"] = class_code

    team_id = st.sidebar.text_input(
        "모둠 식별자 (Team ID)",
        value=st.session_state.get("current_team_id", "TEAM_01"),
        help="소속 모둠명을 입력하세요.",
    ).strip()
    st.session_state["current_team_id"] = team_id

    # 학급 세션 환경 조회
    session_cfg = get_class_session_config(class_code)
    is_locked = session_cfg.get("is_locked", False)
    air_temp = session_cfg.get("air_temp_c", 30.0)
    solar_rad = session_cfg.get("solar_rad", 750.0)

    st.sidebar.divider()
    st.sidebar.markdown("##### 🌤️ 학급 환경 파라미터")
    st.sidebar.write(f"• **대기 기온:** `{air_temp:.1f} °C`")
    st.sidebar.write(f"• **태양 일사량:** `{solar_rad:.1f} W/m²`")
    if is_locked:
        st.sidebar.warning("🔒 교사 작도 잠금 활성화")
    else:
        st.sidebar.success("🔓 도로망 작도 편집 가능")

    # 2. 메인 단계 탭 구성
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "1️⃣ 지형 작도",
        "2️⃣ 위상 진단",
        "3️⃣ 바이브 코딩",
        "4️⃣ 개발 워크스페이스",
        "5️⃣ 엣지 구동 & 산출물",
    ])

    with tab1:
        render_tab1_map_builder(class_code, team_id)

    with tab2:
        render_tab2_topology_checker(class_code)

    with tab3:
        render_tab3_vibe_optimizer(class_code, team_id)

    with tab4:
        render_tab4_vscode_workspace(class_code, team_id)

    with tab5:
        render_tab5_edge_runner_artifact(class_code, team_id)


if __name__ == "__main__":
    render_student_workspace_page()