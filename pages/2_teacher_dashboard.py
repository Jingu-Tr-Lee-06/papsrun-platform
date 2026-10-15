"""교사용 실시간 수업 통제 및 모니터링 대시보드 페이지.

학급 세션 생성, 학생 작도 편집 권한 잠금(Lock/Unlock),
학급 공통 기상 파라미터(기온, 태양 일사량) 일괄 배포,
전체 모둠의 도로망 구축 현황 및 위상 통계를 통합 관제합니다.
"""

from typing import Any, Dict, List, Tuple
import streamlit as st
from streamlit_folium import st_folium

from src.components.map_canvas import (
    create_interactive_campus_map,
    render_graph_overlay,
)
from src.db.class_session_manager import (
    get_class_session_config,
    set_class_locked_state,
    update_class_session_config,
)
from src.db.road_repository import clear_all_edges_in_class, get_all_edges
from src.geo.snap_engine import extract_unique_nodes_from_edges
from src.graph.graph_builder import build_campus_multidigraph
from src.graph.topology_validator import validate_campus_network_topology

# 페이지 기본 설정
st.set_page_config(
    page_title="교사 통제 대시보드 - PAPSrun",
    page_icon="👨‍🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)

from src.utils.auth_helper import sync_auth_session
sync_auth_session()

# ------------------ 권한 검증 (RBAC Guard) ------------------
if not st.session_state.get("authenticated", False):
    st.warning("로그인이 필요한 페이지입니다. 시작 화면으로 이동합니다.")
    st.switch_page("app.py")

if st.session_state.get("user_role") != "teacher":
    st.error("이 페이지는 교사(관리자) 전용 통제 대시보드입니다. 학생 워크스페이스로 이동합니다.")
    st.switch_page("pages/1_student_workspace.py")


def render_teacher_dashboard_page() -> None:
    """교사 통제 대시보드 메인 렌더러."""
    st.sidebar.title("👨‍🏫 교사 통제 센터")
    st.sidebar.caption(f"접속자: {st.session_state.get('user_name', '담당 교사')} 선생님")

    # 1. 관리 대상 학급 선택 (기본값: 로그인 시 설정한 학급 코드)
    default_code = st.session_state.get("class_code", "KNU_2026_01")
    class_code = st.sidebar.text_input(
        "관리 대상 학급 코드",
        value=default_code,
        help="수업을 진행할 학급 코드를 입력하세요.",
    ).strip()
    st.session_state["class_code"] = class_code

    # 세션 설정 로드
    session_cfg = get_class_session_config(class_code)
    current_locked = session_cfg.get("is_locked", False)
    current_temp = session_cfg.get("air_temp_c", 30.0)
    current_solar = session_cfg.get("solar_rad", 750.0)

    st.sidebar.divider()

    # 2. 학생 작도 권한 통제 (Lock/Unlock)
    st.sidebar.markdown("##### 🔒 학생 작도 권한 제어")
    lock_label = "🔓 작도 편집 해제됨" if not current_locked else "🔒 작도 잠김 (읽기 전용)"
    st.sidebar.info(f"현재 상태: **{lock_label}**")

    btn_cols = st.sidebar.columns(2)
    with btn_cols[0]:
        if st.button("🔒 작도 잠금", use_container_width=True, disabled=current_locked):
            set_class_locked_state(class_code, True)
            st.toast("학생들의 도로망 추가/수정이 차단되었습니다.", icon="🔒")
            st.rerun()
    with btn_cols[1]:
        if st.button("🔓 작도 허용", use_container_width=True, disabled=not current_locked):
            set_class_locked_state(class_code, False)
            st.toast("학생들의 도로망 작도가 허용되었습니다.", icon="🔓")
            st.rerun()

    # 3. 학급 공통 기상 환경 일괄 배포 폼
    st.sidebar.divider()
    st.sidebar.markdown("##### 🌤️ 학급 환경 변수 주입")
    with st.sidebar.form("weather_override_form"):
        new_temp = st.slider("대기 기온 (°C)", min_value=15.0, max_value=40.0, value=float(current_temp), step=0.5)
        new_solar = st.slider("하향 단파 일사량 (W/m²)", min_value=200.0, max_value=1100.0, value=float(current_solar), step=25.0)
        apply_weather = st.form_submit_button("전체 모둠 환경 적용", use_container_width=True)

        if apply_weather:
            update_class_session_config(
                class_code,
                {"air_temp_c": new_temp, "solar_rad": new_solar},
            )
            st.toast("기상 환경 변수가 학급 전체에 반영되었습니다.", icon="☀️")
            st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("🚪 메인 화면(로그아웃)", use_container_width=True):
        st.session_state.authenticated = False
        st.session_state.user_role = None
        st.session_state.user_name = ""
        st.switch_page("app.py")

    # ------------------ 메인 패널 ------------------
    st.markdown(f"### 🏫 학급 관제 센터: `{class_code}`")
    st.caption("학생 모둠들이 수집 및 작성한 도로망의 실시간 병합 상태와 네트워크 위상을 점검합니다.")

    edges = get_all_edges(class_code)
    nodes_dict = extract_unique_nodes_from_edges(edges)
    G = build_campus_multidigraph(edges)
    topo_report = validate_campus_network_topology(G) if edges else {}

    # 상단 요약 카드
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    with kpi1:
        st.metric(label="총 수집 도로 간선", value=f"{len(edges)} 개")
    with kpi2:
        st.metric(label="통합 교차점(노드)", value=f"{len(nodes_dict)} 개")
    with kpi3:
        num_comp = topo_report.get("component_count", 0) if edges else 0
        st.metric(label="네트워크 연결 덩어리", value=f"{num_comp} 개")
    with kpi4:
        participating_teams = len(set(e.get("team_id", "미지정") for e in edges))
        st.metric(label="참여 모둠 수", value=f"{participating_teams} 팀")

    tab_map, tab_teams, tab_manage = st.tabs(["🗺️ 통합 도로망 관제", "👥 모둠별 기여도", "⚙️ 학급 데이터 관리"])

    with tab_map:
        st.markdown("##### 📍 실시간 수집 통합 도로망 현황")
        base_map = create_interactive_campus_map(center_lat=36.4675, center_lon=127.1405, zoom_start=17)
        rendered_map = render_graph_overlay(base_map, edges, nodes_dict)
        st_folium(rendered_map, width="100%", height=550)

    with tab_teams:
        st.markdown("##### 📊 모둠별 도로망 구축 기여 분석")
        if edges:
            team_stats: Dict[str, Dict[str, Any]] = {}
            for e in edges:
                tid = e.get("team_id", "UNKNOWN")
                if tid not in team_stats:
                    team_stats[tid] = {"count": 0, "total_len": 0.0, "surfaces": set()}
                team_stats[tid]["count"] += 1
                length_val = e.get("length_m") or e.get("length") or 0.0
                team_stats[tid]["total_len"] += float(length_val)
                team_stats[tid]["surfaces"].add(e.get("surface_type", "unknown"))

            stat_rows = []
            for tid, stat in team_stats.items():
                stat_rows.append({
                    "모둠 식별자": tid,
                    "작도 간선 수": f"{stat['count']} 개",
                    "총 연장 거리": f"{stat['total_len']:.1f} m",
                    "기여 노면 다양성": f"{len(stat['surfaces'])} 종",
                })
            st.dataframe(stat_rows, use_container_width=True)
        else:
            st.info("아직 제출된 모둠 데이터가 없습니다.")

    with tab_manage:
        st.markdown("##### ⚠️ 학급 데이터 비상 초기화")
        st.caption("수업 리셋 시 현재 학급에 등록된 모든 도로 간선 데이터를 영구 삭제합니다.")

        with st.expander("🚨 학급 데이터 전체 삭제 영역", expanded=False):
            st.error("이 작업은 되돌릴 수 없습니다. 학생들의 작도 데이터가 모두 제거됩니다.")
            confirm_code = st.text_input("확인을 위해 학급 코드를 다시 입력하세요:")
            if st.button("모든 도로 데이터 일괄 삭제", type="primary"):
                if confirm_code == class_code:
                    clear_all_edges_in_class(class_code)
                    st.success(f"`{class_code}` 학급의 도로망 데이터가 초기화되었습니다.")
                    st.rerun()
                else:
                    st.error("학급 코드가 일치하지 않습니다.")


if __name__ == "__main__":
    render_teacher_dashboard_page()