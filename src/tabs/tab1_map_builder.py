"""[1단계 UI] 좌측 HUD 사이드 패널 & 우측 풀사이즈 지도 맵 빌더 컨트롤러 모듈.

- 끊어져 있는 여러 개의 선(Multi-Polyline)을 연속으로 계속 그려두고 한 번에 확정하는 다중 작도 버퍼 지원
- 선을 그릴 때마다 발생하는 st.rerun()을 완전히 차단하여 지도 깜빡임/백화 현상 방지
- 듀얼 작도 모드 지원 (선 긋기 & 점 직접 찍기 자석 스냅)
- 지도 간선 클릭 시 '삭제 관리' 탭과 연동하여 정보 노출 및 삭제 버튼 동적 활성화
- 일괄 연산 처리: 누적된 모든 선 구간의 DEM 고도차, 양방향 경사도, 복사에너지(R_abs) 집중 연산
"""

import math
import time
from typing import Any, Dict, List, Tuple
import pandas as pd
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
from src.geo.weather_engine import calculate_absorbed_radiation, get_effective_weather_data

SURFACE_OPTIONS = [
    ("urethane_track", "우레탄 러닝 트랙 (α=0.20)"),
    ("lawn_grass", "잔디밭 / 녹지 (α=0.22)"),
    ("soil_trail", "흙길 산책로 (α=0.25)"),
    ("concrete_walkway", "보도블록 / 콘크리트 (α=0.30)"),
    ("asphalt_aged", "노후 아스팔트 (α=0.15)"),
    ("asphalt_dark", "신설 흑색 아스팔트 (α=0.10)"),
]


def _map_surface_to_albedo_key(surface_type: str) -> str:
    stype = surface_type.lower()
    if "urethane" in stype:
        return "urethane"
    elif "soil" in stype or "dirt" in stype:
        return "dirt"
    elif "lawn" in stype or "grass" in stype:
        return "grass"
    elif "concrete" in stype:
        return "concrete"
    return "asphalt"


def interpolate_points_by_distance(
    p1: Tuple[float, float],
    p2: Tuple[float, float],
    interval_m: float = 15.0,
) -> List[Tuple[float, float]]:
    total_dist = calculate_haversine_distance(p1, p2)
    if total_dist <= interval_m:
        return [p1, p2]

    num_segments = math.ceil(total_dist / interval_m)
    interpolated = []
    for i in range(num_segments + 1):
        ratio = i / num_segments
        lat = round(p1[0] + (p2[0] - p1[0]) * ratio, 5)
        lng = round(p1[1] + (p2[1] - p1[1]) * ratio, 5)
        interpolated.append((lat, lng))
    return interpolated


def render_tab1_map_builder(class_code: str, team_id: str) -> None:
    """1단계 맵 빌더 화면."""

    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 4.2rem !important;
            padding-bottom: 1.0rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }
        div[data-baseweb="tab-list"] {
            margin-bottom: 1.2rem !important;
            position: relative !important;
            z-index: 10 !important;
        }
        iframe {
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    locked = is_class_locked(class_code)

    # 0. 지도에서 간선 클릭으로 넘어온 파라미터 감지
    query_params = st.query_params
    if "select_edge_id" in query_params:
        st.session_state["selected_edge_id"] = query_params["select_edge_id"]
        del st.query_params["select_edge_id"]
        st.rerun()

    # 세션 상태 초기화
    if "map_view_center" not in st.session_state:
        st.session_state["map_view_center"] = [36.4675, 127.1405]
    if "map_view_zoom" not in st.session_state:
        st.session_state["map_view_zoom"] = 17
    if "drawing_lines_buffer" not in st.session_state:
        st.session_state["drawing_lines_buffer"] = []
    if "drawing_points" not in st.session_state:
        st.session_state["drawing_points"] = []
    if "draw_mode" not in st.session_state:
        st.session_state["draw_mode"] = "line"
    if "selected_edge_id" not in st.session_state:
        st.session_state["selected_edge_id"] = None
    if "last_processed_click" not in st.session_state:
        st.session_state["last_processed_click"] = None

    center_coords = st.session_state["map_view_center"]
    cur_weather = get_effective_weather_data(lat=center_coords[0], lng=center_coords[1])
    solar_w = float(cur_weather.get("solar_w_m2", 700.0))
    ambient_temp = float(cur_weather.get("temp_c", 20.0))

    edges = get_all_edges(class_code)
    nodes_dict: Dict[str, Tuple[float, float]] = {}
    for edge in edges:
        u, v = str(edge.get("u")), str(edge.get("v"))
        u_coords = edge.get("u_coords") or edge.get("coord_u")
        v_coords = edge.get("v_coords") or edge.get("coord_v")
        if u_coords and len(u_coords) == 2:
            nodes_dict[u] = (float(u_coords[0]), float(u_coords[1]))
        if v_coords and len(v_coords) == 2:
            nodes_dict[v] = (float(v_coords[0]), float(v_coords[1]))

    current_selected_edge_id = st.session_state.get("selected_edge_id")

    col_panel, col_map = st.columns([3.2, 6.8])

    with col_panel:
        st.markdown("#### 🛰️ 도로망 관제 패널")
        st.caption(f"학급: `{class_code}` | 모둠: `{team_id}` | 기온: `{ambient_temp:.1f}°C` | 일사: `{solar_w:.0f}W/m²`")

        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
            "✏️ 드로잉 작도",
            "🛠️ 간선 수정",
            "🔗 수동 연결",
            "🗑️ 삭제 관리",
            "📊 2차시 탐구",
        ])

        # TAB 1: 연속 다중 드로잉 및 일괄 연산 확정
        with sub_tab1:
            mode_choice = st.radio(
                "작도 방식 선택",
                options=["⚡ 연속 드로잉 (여러 선 자유 작도)", "🎯 점 직접 찍기 (노드 스냅 결합)"],
                index=0 if st.session_state["draw_mode"] == "line" else 1,
                horizontal=True,
            )
            selected_mode = "line" if "연속 드로잉" in mode_choice else "click"
            if selected_mode != st.session_state["draw_mode"]:
                st.session_state["draw_mode"] = selected_mode
                st.session_state["drawing_lines_buffer"] = []
                st.session_state["drawing_points"] = []
                st.rerun()

            if st.session_state["draw_mode"] == "line":
                st.info(
                    "👉 **다중 선 연속 작도 방법:**\n"
                    "1. 좌상단 **선 아이콘**을 누르고 선 하나를 그린 뒤 **더블클릭**합니다.\n"
                    "2. **지도가 깜빡이지 않습니다.** 바로 다시 선 아이콘을 눌러 다른 선을 연달아 그리세요.\n"
                    "3. 원하는 만큼 끊어진 선들을 다 그린 후 아래 **[도로망 일괄 확정 및 연산]**을 누르세요."
                )
            else:
                st.info(
                    "👉 **점 직접 찍기 안내:**\n"
                    "- 빈 곳을 클릭하면 점이 찍히고, 기존 교차점 근처를 누르면 자석 스냅됩니다."
                )

            # 대상 선 목록 산출
            lines_to_process = list(st.session_state["drawing_lines_buffer"])
            if st.session_state["draw_mode"] == "click" and len(st.session_state["drawing_points"]) >= 2:
                lines_to_process.append(list(st.session_state["drawing_points"]))

            line_count = len(lines_to_process)

            if line_count > 0:
                st.success(f"📍 현재 작도된 선: **{line_count}개 구간 대기 중**")
            else:
                st.caption("선 아이콘을 눌러 지도 위에 자유롭게 도로를 그려주세요.")

            route_name_prefix = st.text_input(
                "대표 구간명 (선택)",
                placeholder="예: 운동장 외곽, 본관 진입로",
                help="미입력 시 노드 번호 및 순번으로 자동 생성됩니다.",
            ).strip()

            is_shaded_all = st.checkbox("🌲 전체 구간 그늘 일괄 적용 (일사 70% 차감)", value=False)

            btn_c1, btn_c2 = st.columns([1.6, 1.0])
            with btn_c1:
                create_all_clicked = st.button(
                    f"🚀 {max(1, line_count)}개 도로망 일괄 확정 및 연산",
                    type="primary",
                    disabled=(line_count == 0 or locked),
                    use_container_width=True,
                )
            with btn_c2:
                if st.button("🔄 작도 초기화", use_container_width=True):
                    st.session_state["drawing_lines_buffer"] = []
                    st.session_state["drawing_points"] = []
                    st.rerun()

            # 일괄 연산 처리 (버튼을 눌렀을 때만 최초 1회 실행)
            if create_all_clicked and line_count > 0:
                total_created_cnt = 0
                with st.spinner(f"⏳ 총 {line_count}개 구간의 DEM 고도차, 양방향 경사도, 복사에너지(R_abs) 연산 중..."):
                    for line_idx, pts in enumerate(lines_to_process, start=1):
                        expanded_pts: List[Tuple[float, float]] = []
                        for i in range(len(pts) - 1):
                            sub_seg = interpolate_points_by_distance(pts[i], pts[i + 1], interval_m=15.0)
                            if i == 0:
                                expanded_pts.extend(sub_seg)
                            else:
                                expanded_pts.extend(sub_seg[1:])

                        for i in range(len(expanded_pts) - 1):
                            p1, p2 = expanded_pts[i], expanded_pts[i + 1]

                            snapped_u_id, u_coords = snap_to_existing_node(p1, nodes_dict, threshold_m=12.0)
                            nodes_dict[snapped_u_id] = u_coords
                            snapped_v_id, v_coords = snap_to_existing_node(p2, nodes_dict, threshold_m=12.0)
                            nodes_dict[snapped_v_id] = v_coords

                            dist_m = calculate_haversine_distance(u_coords, v_coords)
                            if dist_m < 1.0 or snapped_u_id == snapped_v_id:
                                continue

                            inferred_surface = infer_surface_with_osm_fallback(u_coords, v_coords)
                            elev_u, elev_v, slope_pct = calculate_elevation_and_slope(u_coords, v_coords)
                            clean_key = _map_surface_to_albedo_key(inferred_surface)

                            rad_calc = calculate_absorbed_radiation(
                                solar_w_m2=solar_w,
                                surface_type=clean_key,
                                tree_canopy_cover=0.70 if is_shaded_all else 0.0,
                            )

                            base_title = route_name_prefix if route_name_prefix else f"{snapped_u_id}➔{snapped_v_id}"
                            seg_name = f"{base_title} (코스{line_idx}-{i+1})" if line_count > 1 else base_title

                            edge_data = {
                                "u": snapped_u_id,
                                "v": snapped_v_id,
                                "u_coords": list(u_coords),
                                "v_coords": list(v_coords),
                                "name": seg_name,
                                "length_m": round(dist_m, 2),
                                "surface_type": inferred_surface,
                                "is_shaded": is_shaded_all,
                                "albedo": rad_calc["albedo"],
                                "effective_solar_w_m2": rad_calc["effective_solar_w_m2"],
                                "absorbed_rad_w_m2": rad_calc["absorbed_rad_w_m2"],
                                "ambient_temp_c": ambient_temp,
                                "elevation_start": round(elev_u, 2),
                                "elevation_end": round(elev_v, 2),
                                "slope_pct": round(slope_pct, 2),
                                "team_id": team_id,
                            }
                            ok, _ = save_single_edge(class_code, edge_data)
                            if ok:
                                total_created_cnt += 1

                st.session_state["drawing_lines_buffer"] = []
                st.session_state["drawing_points"] = []
                st.toast(f"🎉 총 {line_count}개 코스({total_created_cnt}개 간선) 등록 완료!", icon="🚀")
                time.sleep(0.4)
                st.rerun()

        # TAB 2: 수정
        with sub_tab2:
            if not edges:
                st.info("수정할 등록 도로가 없습니다.")
            else:
                st.markdown("##### ⚡ 실시간 환경 가중치 일괄 갱신")
                if st.button("🔄 학급 전체 도로 가중치 일괄 재연산", type="secondary", use_container_width=True, disabled=locked):
                    with st.spinner("⏳ 전체 도로망 경사도 및 복사에너지(R_abs) 재계산 중..."):
                        recalc_cnt = 0
                        for ed in edges:
                            u_c = ed.get("u_coords") or (nodes_dict.get(str(ed.get("u"))))
                            v_c = ed.get("v_coords") or (nodes_dict.get(str(ed.get("v"))))
                            if not u_c or not v_c:
                                continue

                            elev_u, elev_v, slope_pct = calculate_elevation_and_slope(u_c, v_c)

                            surf = ed.get("surface_type", "asphalt_dark")
                            is_sh = ed.get("is_shaded", False)
                            clean_key = _map_surface_to_albedo_key(surf)
                            re_rad = calculate_absorbed_radiation(
                                solar_w_m2=solar_w,
                                surface_type=clean_key,
                                tree_canopy_cover=0.70 if is_sh else 0.0,
                            )

                            ed["elevation_start"] = round(elev_u, 2)
                            ed["elevation_end"] = round(elev_v, 2)
                            ed["slope_pct"] = round(slope_pct, 2)
                            ed["ambient_temp_c"] = ambient_temp
                            ed["albedo"] = re_rad["albedo"]
                            ed["effective_solar_w_m2"] = re_rad["effective_solar_w_m2"]
                            ed["absorbed_rad_w_m2"] = re_rad["absorbed_rad_w_m2"]

                            save_single_edge(class_code, ed)
                            recalc_cnt += 1

                        st.toast(f"✅ 총 {recalc_cnt}개 도로 간선 재연산 완료!", icon="⚡")
                        time.sleep(0.5)
                        st.rerun()

                st.divider()

                edge_id_map = {
                    e.get("edge_id"): f"{e.get('name', '무제')} ({e.get('u')}➔{e.get('v')})"
                    for e in edges
                }
                default_sel_idx = 0
                if current_selected_edge_id in edge_id_map:
                    default_sel_idx = list(edge_id_map.keys()).index(current_selected_edge_id)

                selected_edge_id = st.selectbox(
                    "수정할 간선 선택",
                    options=list(edge_id_map.keys()),
                    index=default_sel_idx,
                    format_func=lambda eid: edge_id_map.get(eid, eid),
                )
                target_edge = next((e for e in edges if e.get("edge_id") == selected_edge_id), None)

                if target_edge:
                    with st.form("edit_edge_form"):
                        new_name = st.text_input("구간 이름", value=target_edge.get("name", ""))
                        curr_surf = target_edge.get("surface_type", "asphalt_dark")
                        surf_keys = [s[0] for s in SURFACE_OPTIONS]
                        curr_surf_idx = surf_keys.index(curr_surf) if curr_surf in surf_keys else 0

                        new_surf = st.selectbox(
                            "노면 피복 변경",
                            options=surf_keys,
                            index=curr_surf_idx,
                            format_func=lambda x: dict(SURFACE_OPTIONS).get(x, x),
                        )
                        new_shaded = st.checkbox("나무 그늘 구간 여부", value=bool(target_edge.get("is_shaded", False)))

                        u_node = target_edge.get("u", "U")
                        v_node = target_edge.get("v", "V")
                        e_start = float(target_edge.get("elevation_start", 0.0))
                        e_end = float(target_edge.get("elevation_end", 0.0))
                        fwd_slope = float(target_edge.get("slope_pct", 0.0))
                        rev_slope = -fwd_slope

                        fwd_type = "오르막 🔺" if fwd_slope > 0 else ("내리막 🔻" if fwd_slope < 0 else "평지 ➖")
                        rev_type = "오르막 🔺" if rev_slope > 0 else ("내리막 🔻" if rev_slope < 0 else "평지 ➖")

                        st.markdown(
                            f"""
                            <div style="background:#f8fafc; padding:10px; border-radius:8px; border:1px solid #e2e8f0; font-size:0.85rem; margin-bottom:12px;">
                                <div>• <strong>거리:</strong> <code>{target_edge.get('length_m')} m</code> | <strong>고도:</strong> <code>{e_start:.1f}m ➔ {e_end:.1f}m</code> (Δh: {e_end - e_start:+.1f}m)</div>
                                <div style="margin-top:4px;">• <strong>순방향 ({u_node}➔{v_node}):</strong> <span style="font-weight:600; color:{'#dc2626' if fwd_slope>0 else '#2563eb'};">{fwd_slope:+.1f}% ({fwd_type})</span></div>
                                <div>• <strong>역방향 ({v_node}➔{u_node}):</strong> <span style="font-weight:600; color:{'#dc2626' if rev_slope>0 else '#2563eb'};">{rev_slope:+.1f}% ({rev_type})</span></div>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                        if st.form_submit_button("💾 개별 간선 저장", type="primary", use_container_width=True, disabled=locked):
                            clean_key = _map_surface_to_albedo_key(new_surf)
                            re_rad = calculate_absorbed_radiation(
                                solar_w_m2=solar_w,
                                surface_type=clean_key,
                                tree_canopy_cover=0.70 if new_shaded else 0.0,
                            )

                            target_edge["name"] = new_name
                            target_edge["surface_type"] = new_surf
                            target_edge["is_shaded"] = new_shaded
                            target_edge["albedo"] = re_rad["albedo"]
                            target_edge["absorbed_rad_w_m2"] = re_rad["absorbed_rad_w_m2"]
                            target_edge["effective_solar_w_m2"] = re_rad["effective_solar_w_m2"]

                            save_single_edge(class_code, target_edge)
                            st.toast("✅ 간선 속성 저장 완료!", icon="💾")
                            st.rerun()

        # TAB 3: 두 노드 수동 연결
        with sub_tab3:
            available_nids = sorted(list(nodes_dict.keys()))
            if len(available_nids) >= 2:
                sel_u = st.selectbox("출발 노드 (U)", options=available_nids, key="m_u")
                sel_v = st.selectbox("도착 노드 (V)", options=available_nids, index=1, key="m_v")
                link_name = st.text_input("구간 이름", placeholder="예: 체육관 연결로", key="m_name")
                link_shaded = st.checkbox("그늘 구간", value=False, key="m_sh")

                if st.button("➕ 두 노드 직접 잇기", disabled=locked, use_container_width=True):
                    if sel_u != sel_v:
                        with st.spinner("연결 간선 연산 중..."):
                            u_c, v_c = nodes_dict[sel_u], nodes_dict[sel_v]
                            dist_m = calculate_haversine_distance(u_c, v_c)
                            inferred = infer_surface_with_osm_fallback(u_c, v_c)
                            elev_u, elev_v, slope_pct = calculate_elevation_and_slope(u_c, v_c)
                            clean_key = _map_surface_to_albedo_key(inferred)
                            rad = calculate_absorbed_radiation(
                                solar_w_m2=solar_w,
                                surface_type=clean_key,
                                tree_canopy_cover=0.70 if link_shaded else 0.0,
                            )
                            seg_title = link_name if link_name else f"{sel_u}➔{sel_v}"
                            save_single_edge(class_code, {
                                "u": sel_u,
                                "v": sel_v,
                                "u_coords": list(u_c),
                                "v_coords": list(v_c),
                                "name": seg_title,
                                "length_m": round(dist_m, 2),
                                "surface_type": inferred,
                                "is_shaded": link_shaded,
                                "albedo": rad["albedo"],
                                "effective_solar_w_m2": rad["effective_solar_w_m2"],
                                "absorbed_rad_w_m2": rad["absorbed_rad_w_m2"],
                                "ambient_temp_c": ambient_temp,
                                "elevation_start": round(elev_u, 2),
                                "elevation_end": round(elev_v, 2),
                                "slope_pct": round(slope_pct, 2),
                                "team_id": team_id,
                            })
                            st.toast(f"✅ {sel_u} ➔ {sel_v} 연결 완료!", icon="🔗")
                            st.rerun()
            else:
                st.info("등록된 노드가 2개 이상일 때 연결할 수 있습니다.")

        # TAB 4: 노드 및 간선 삭제
        with sub_tab4:
            st.markdown("##### 🗑️ 간선 및 노드 삭제")
            selected_edge_obj = next((e for e in edges if e.get("edge_id") == current_selected_edge_id), None)
            if selected_edge_obj:
                u_n = selected_edge_obj.get("u")
                v_n = selected_edge_obj.get("v")
                s_name = selected_edge_obj.get("name", f"{u_n}➔{v_n}")
                dist_val = selected_edge_obj.get("length_m", 0.0)
                surf_val = selected_edge_obj.get("surface_type", "asphalt")
                slope_val = selected_edge_obj.get("slope_pct", 0.0)

                st.markdown(
                    f"""
                    <div style="background:#fff1f2; padding:12px; border-radius:8px; border:1px solid #fecdd3; margin-bottom:12px;">
                        <div style="font-weight:bold; color:#be123c; font-size:14px;">🎯 지도에서 선택된 간선</div>
                        <div style="font-size:13px; margin-top:4px; color:#1e293b;">
                            • <strong>구간명:</strong> <code>{s_name}</code> ({u_n}➔{v_n})<br>
                            • <strong>길이:</strong> {dist_val} m | <strong>경사도:</strong> {slope_val:+.1f}%<br>
                            • <strong>노면:</strong> {surf_val}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                col_del_btn, col_del_cancel = st.columns([1.5, 1.0])
                with col_del_btn:
                    if st.button("🗑️ 선택한 간선 즉시 삭제", type="primary", use_container_width=True, disabled=locked):
                        delete_single_edge(class_code, current_selected_edge_id)
                        st.session_state["selected_edge_id"] = None
                        st.toast(f"간선 `{s_name}` 삭제 완료!", icon="🗑️")
                        time.sleep(0.3)
                        st.rerun()

                with col_del_cancel:
                    if st.button("선택 해제", use_container_width=True):
                        st.session_state["selected_edge_id"] = None
                        st.rerun()

                st.divider()

            if edges:
                e_del = st.selectbox(
                    "목록에서 직접 선택하여 삭제",
                    options=[e.get("edge_id", "") for e in edges],
                    format_func=lambda eid: next((f"{e.get('name', '무제')} ({e.get('u')}➔{e.get('v')})" for e in edges if e.get("edge_id") == eid), eid),
                    key="del_e",
                )
                if st.button("선택 간선 삭제", disabled=locked, use_container_width=True):
                    delete_single_edge(class_code, e_del)
                    if st.session_state.get("selected_edge_id") == e_del:
                        st.session_state["selected_edge_id"] = None
                    st.toast("간선이 삭제되었습니다.", icon="🗑️")
                    st.rerun()

                st.divider()
                n_del = st.selectbox("삭제 노드 선택 (연결 도로 함께 삭제)", options=sorted(list(nodes_dict.keys())), key="del_n")
                if st.button("선택 노드 및 관련 도로 전체 삭제", disabled=locked, use_container_width=True):
                    for ed in edges:
                        if ed.get("u") == n_del or ed.get("v") == n_del:
                            delete_single_edge(class_code, ed.get("edge_id", ""))
                    st.session_state["selected_edge_id"] = None
                    st.toast("노드 및 연결 도로 삭제 완료", icon="🗑️")
                    st.rerun()
            else:
                st.info("삭제할 도로망 데이터가 없습니다.")

        # TAB 5: 2차시 탐구
        with sub_tab5:
            st.markdown("##### 🌍 2차시 지구과학: 피복별 복사에너지 분석")
            if edges:
                df_edges = pd.DataFrame(edges)
                if "slope_pct" in df_edges.columns:
                    df_edges["reverse_slope_pct"] = -pd.to_numeric(df_edges["slope_pct"], errors="coerce").fillna(0.0)

                export_cols = [
                    "edge_id", "name", "u", "v", "surface_type", "albedo",
                    "absorbed_rad_w_m2", "slope_pct", "reverse_slope_pct", "length_m", "is_shaded", "team_id"
                ]
                actual_cols = [c for c in export_cols if c in df_edges.columns]
                rename_map = {
                    "edge_id": "간선ID", "name": "구간명", "u": "시작노드_U", "v": "도착노드_V",
                    "surface_type": "노면피복", "albedo": "알베도_alpha", "absorbed_rad_w_m2": "흡수복사에너지_W_m2",
                    "slope_pct": "경사도_pct(U➔V기준)", "reverse_slope_pct": "역방향_경사도_pct(V➔U기준)",
                    "length_m": "거리_m", "is_shaded": "그늘여부", "team_id": "수집모둠",
                }
                df_export = df_edges[actual_cols].rename(columns=rename_map)
                csv_bytes = df_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label="📥 Alice Stats용 도로망 CSV 다운로드",
                    data=csv_bytes,
                    file_name=f"papsrun_roads_{class_code}.csv",
                    mime="text/csv",
                    use_container_width=True,
                )

    # --------------------------------------------------------------------------
    # [우측] 풀사이즈 지도 캔버스 (클릭 및 선 완료 시 깜빡임 차단)
    # --------------------------------------------------------------------------
    with col_map:
        current_mode = st.session_state["draw_mode"]

        base_map = create_interactive_campus_map(
            center_lat=st.session_state["map_view_center"][0],
            center_lon=st.session_state["map_view_center"][1],
            zoom_start=st.session_state["map_view_zoom"],
            draw_mode=current_mode,
        )

        rendered_map = render_graph_overlay(
            base_map,
            edges,
            nodes_dict,
            current_drawing_points=st.session_state["drawing_points"],
            interactive_nodes=(current_mode == "click"),
            selected_edge_id=current_selected_edge_id,
            multi_lines_buffer=None,  # Leaflet.draw가 화면 상에 선들을 유지하므로 중복 렌더링 방지
        )

        ret_objs = ["last_clicked"] if current_mode == "click" else ["all_drawings"]

        map_output = st_folium(
            rendered_map,
            width="100%",
            height=780,
            returned_objects=ret_objs,
            key=f"tab1_map_{current_mode}",
        )

        # 모드 1: 점 직접 찍기 (노드 자석 스냅)
        if current_mode == "click" and not locked:
            clicked = map_output.get("last_clicked")
            if clicked and isinstance(clicked, dict):
                raw_lat = round(float(clicked.get("lat", 0.0)), 5)
                raw_lng = round(float(clicked.get("lng", 0.0)), 5)
                new_p = (raw_lat, raw_lng)

                if st.session_state["last_processed_click"] != new_p:
                    st.session_state["last_processed_click"] = new_p

                    target_pt = new_p
                    if nodes_dict:
                        snapped_id, snapped_coords = snap_to_existing_node(new_p, nodes_dict, threshold_m=12.0)
                        if snapped_id in nodes_dict:
                            target_pt = snapped_coords

                    if not st.session_state["drawing_points"] or st.session_state["drawing_points"][-1] != target_pt:
                        st.session_state["drawing_points"].append(target_pt)
                        st.rerun()

        # 모드 2: 연속 선 그리기 (st.rerun()을 호출하지 않고 조용히 버퍼만 수신)
        elif current_mode == "line" and not locked:
            all_draws = map_output.get("all_drawings") or []
            extracted_lines = []
            for feat in all_draws:
                if isinstance(feat, dict) and "geometry" in feat:
                    coords = feat["geometry"].get("coordinates", [])
                    if coords and isinstance(coords[0], (list, tuple)):
                        pts = [(round(float(c[1]), 5), round(float(c[0]), 5)) for c in coords if len(c) >= 2]
                        if len(pts) >= 2:
                            extracted_lines.append(pts)
            st.session_state["drawing_lines_buffer"] = extracted_lines