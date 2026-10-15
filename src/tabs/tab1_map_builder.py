"""[1단계 UI] 캠퍼스 지형·환경 맵 연속 작도 컨트롤러 모듈.

학생 모둠이 캠퍼스 도로망의 노드(좌표)와 간선(도로 세그먼트)을 입력하고,
15m 자석 스냅(snap_engine)과 노면 피복 분류기(surface_classifier)를 연동하여
정밀한 지형·환경 속성이 부가된 도로 데이터를 DB/캐시에 저장합니다.
"""

from typing import Any, Dict, List, Tuple
import streamlit as st
from streamlit_folium import st_folium

from src.components.map_canvas import (
    create_interactive_campus_map,
    render_graph_overlay,
)
from src.db.class_session_manager import is_class_locked
from src.db.road_repository import (
    delete_single_edge,
    get_all_edges,
    save_single_edge,
)
from src.geo.elevation_engine import calculate_elevation_and_slope
from src.geo.snap_engine import calculate_haversine_distance, snap_to_existing_node
from src.geo.surface_classifier import infer_surface_with_osm_fallback


def render_tab1_map_builder(class_code: str, team_id: str) -> None:
    """1단계 도로망 작도 화면을 렌더링합니다.

    Args:
        class_code: 현재 접속한 학급 코드
        team_id: 현재 로그인한 모둠 식별자
    """
    st.markdown("### 🗺️ 1단계: 캠퍼스 지형·환경 도로망 작도")
    st.caption(
        "캠퍼스 도로의 양 끝점 좌표를 입력하여 도로망을 구축합니다. "
        "기존 노드 15m 이내 좌표는 자동으로 자석 스냅(Snap)되어 위상 단절을 방지합니다."
    )

    # 교사의 학급 작도 잠금 여부 확인
    if is_class_locked(class_code):
        st.warning("🔒 현재 교사 통제에 의해 도로망 작도가 잠겨 있습니다. (읽기 전용 모드)")

    # 1. 현재 학급에 등록된 전체 간선 로드
    edges = get_all_edges(class_code)
    nodes_dict: Dict[str, Tuple[float, float]] = {}

    for edge in edges:
        u, v = str(edge.get("u")), str(edge.get("v"))
        u_coords = edge.get("u_coords")
        v_coords = edge.get("v_coords")
        if u_coords and len(u_coords) == 2:
            nodes_dict[u] = (float(u_coords[0]), float(u_coords[1]))
        if v_coords and len(v_coords) == 2:
            nodes_dict[v] = (float(v_coords[0]), float(v_coords[1]))

    col_map, col_input = st.columns([3, 2])

    with col_map:
        st.markdown("##### 📍 실시간 학급 도로망 캔버스")
        base_map = create_interactive_campus_map(
            center_lat=36.4675,
            center_lon=127.1405,
            zoom_start=17,
            enable_drawing=False,
        )
        rendered_map = render_graph_overlay(base_map, edges, nodes_dict)
        map_output = st_folium(
            rendered_map,
            width="100%",
            height=540,
            returned_objects=["last_clicked"],
        )

        clicked_coord = map_output.get("last_clicked")
        if clicked_coord:
            st.info(
                f"📌 지도 클릭 좌표: 위도 `{clicked_coord['lat']:.5f}`, 경도 `{clicked_coord['lng']:.5f}`"
            )

    with col_input:
        st.markdown("##### ✏️ 신규 도로 간선 등록")

        with st.form("new_edge_form", clear_on_submit=False):
            st.markdown("**1. 시작 지점 (Node U)**")
            u_lat = st.number_input("시작 위도 (Lat)", value=36.46750, format="%.5f")
            u_lon = st.number_input("시작 경도 (Lon)", value=127.14050, format="%.5f")

            st.markdown("**2. 종료 지점 (Node V)**")
            v_lat = st.number_input("종료 위도 (Lat)", value=36.46820, format="%.5f")
            v_lon = st.number_input("종료 경도 (Lon)", value=127.14120, format="%.5f")

            st.markdown("**3. 지형 및 환경 속성**")
            surface_options = [
                ("urethane_track", "우레탄 러닝 트랙 (부상 방지)"),
                ("soil_trail", "흙길 산책로 (자연 보행로)"),
                ("lawn_grass", "잔디밭 (쿠션감 우수)"),
                ("concrete_walkway", "보도블록 / 콘크리트 (일반 보행로)"),
                ("asphalt_aged", "노후 아스팔트"),
                ("asphalt_dark", "신설 흑색 아스팔트 (고열 흡수)"),
            ]
            surface_type = st.selectbox(
                "노면 피복 재질",
                options=[s[0] for s in surface_options],
                format_func=lambda x: dict(surface_options).get(x, x),
            )

            is_shaded = st.checkbox("나무 그늘 / 차광 구간 여부", value=False)
            auto_classify = st.checkbox("지오펜싱 기반 노면 자동 판별 적용", value=True)

            submit_btn = st.form_submit_button(
                "➕ 도로 간선 저장",
                disabled=is_class_locked(class_code),
                use_container_width=True,
            )

            if submit_btn:
                # 15m 자석 스냅 적용
                raw_u = (u_lat, u_lon)
                raw_v = (v_lat, v_lon)
                snapped_u_id, final_u_coords = snap_to_existing_node(raw_u, nodes_dict, threshold_m=15.0)
                snapped_v_id, final_v_coords = snap_to_existing_node(raw_v, nodes_dict, threshold_m=15.0)

                # 거리 계산
                dist_m = calculate_haversine_distance(final_u_coords, final_v_coords)
                if dist_m < 1.0:
                    st.error("시작점과 끝점이 동일하거나 거리가 너무 가깝습니다 (1m 이상 필요).")
                else:
                    # 지오펜싱 노면 자동 추정
                    final_surface = surface_type
                    if auto_classify:
                        final_surface = infer_surface_with_osm_fallback(
                            final_u_coords, final_v_coords
                        )

                    # 고도차 및 경사도 계산
                    elev_u, elev_v, slope_pct = calculate_elevation_and_slope(
                        final_u_coords, final_v_coords
                    )

                    new_edge_data: Dict[str, Any] = {
                        "u": snapped_u_id,
                        "v": snapped_v_id,
                        "u_coords": list(final_u_coords),
                        "v_coords": list(final_v_coords),
                        "length_m": round(dist_m, 2),
                        "surface_type": final_surface,
                        "is_shaded": is_shaded,
                        "elevation_start": round(elev_u, 2),
                        "elevation_end": round(elev_v, 2),
                        "slope_pct": round(slope_pct, 2),
                        "team_id": team_id,
                    }

                    ok, msg = save_single_edge(class_code, new_edge_data)
                    if ok:
                        st.success(f"도로 간선 저장 완료: {snapped_u_id} ➔ {snapped_v_id} ({dist_m:.1f}m)")
                        st.rerun()
                    else:
                        st.error(f"저장 실패: {msg}")

    # 등록된 간선 목록 관리 섹션
    st.divider()
    st.markdown("##### 📋 우리 학급 수집 도로망 목록")
    if edges:
        del_cols = st.columns([4, 1])
        with del_cols[0]:
            st.caption(f"총 {len(edges)}개의 도로 세그먼트가 등록되어 있습니다.")
        with del_cols[1]:
            if not is_class_locked(class_code):
                edge_to_delete = st.selectbox(
                    "삭제 대상 간선",
                    options=[e.get("edge_id", "") for e in edges],
                    label_visibility="collapsed",
                )
                if st.button("🗑️ 선택 삭제", use_container_width=True):
                    delete_single_edge(class_code, edge_to_delete)
                    st.rerun()

        # 요약 테이블
        table_rows = []
        for e in edges:
            table_rows.append({
                "간선 식별자": e.get("edge_id"),
                "구간 (U ➔ V)": f"{e.get('u')} ➔ {e.get('v')}",
                "거리 (m)": e.get("length_m"),
                "노면": e.get("surface_type"),
                "그늘": "O" if e.get("is_shaded") else "X",
                "경사도 (%)": e.get("slope_pct"),
                "등록 모둠": e.get("team_id"),
            })
        st.dataframe(table_rows, use_container_width=True)
    else:
        st.info("아직 등록된 도로 간선이 없습니다. 우측 폼에서 첫 번째 도로를 등록해 보세요.")