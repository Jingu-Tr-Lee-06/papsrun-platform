"""[1단계 UI] 좌측 HUD 사이드 패널 & 우측 풀사이즈 지도 맵 빌더 컨트롤러 모듈.

- 가중치 일괄 재연산 버튼(기상 변동 시 전체 간선 R_abs 및 경사도 즉시 동기화)
- 좌측 컨트롤 패널(3.2): 핀 관리, 도로 일괄 생성(구간명 지정), 간선 수정, 수동 연결, 삭제, 2차시 탐구 CSV 내보내기
- 우측 풀사이즈 캔버스(6.8): 네이버 지도 뷰포트, 실시간 핀 및 노면 색상 오버레이
- 15m 간격 자동 보간(Interpolation) 및 지오펜싱 노면 자동 판별
"""

import math
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

# 노면 선택지 표준 정의
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
    """1단계 맵 빌더 화면 (좌우 분할 스플릿 HUD 레이아웃 & 2차시 CSV 내보내기)."""

    # 1. 전폭 레이아웃 CSS 인젝션
    st.markdown(
        """
        <style>
        .block-container {
            padding-top: 1.2rem !important;
            padding-bottom: 0rem !important;
            padding-left: 1.5rem !important;
            padding-right: 1.5rem !important;
            max-width: 100% !important;
        }
        iframe {
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.12);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # 2. 세션 상태 초기화
    if "map_view_center" not in st.session_state:
        st.session_state["map_view_center"] = [36.4675, 127.1405]
    if "map_view_zoom" not in st.session_state:
        st.session_state["map_view_zoom"] = 17
    if "drawing_points" not in st.session_state:
        st.session_state["drawing_points"] = []

    locked = is_class_locked(class_code)

    # 3. 실시간 기상 데이터 수신
    center_coords = st.session_state["map_view_center"]
    cur_weather = get_effective_weather_data(lat=center_coords[0], lng=center_coords[1])
    solar_w = float(cur_weather.get("solar_w_m2", 700.0))
    ambient_temp = float(cur_weather.get("temp_c", 20.0))
    stn_name = cur_weather.get("station_name", "인접 관측소")

    # 4. 도로망 데이터 로드
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

    pts_count = len(st.session_state["drawing_points"])

    # ==========================================================================
    # 🖥️ 2단 분할 레이아웃: 좌측 컨트롤 패널(3.2) / 우측 풀 지도(6.8)
    # ==========================================================================
    col_panel, col_map = st.columns([3.2, 6.8])

    # --------------------------------------------------------------------------
    # [좌측] HUD 컨트롤 사이드바
    # --------------------------------------------------------------------------
    with col_panel:
        st.markdown("#### 🛰️ 도로망 관제 패널")
        st.caption(f"학급: `{class_code}` | 모둠: `{team_id}` | 기온: `{ambient_temp:.1f}°C` | 일사: `{solar_w:.0f}W/m²`")

        sub_tab1, sub_tab2, sub_tab3, sub_tab4, sub_tab5 = st.tabs([
            f"✏️ 드로잉 ({pts_count})",
            "🛠️ 간선 수정",
            "🔗 수동 연결",
            "🗑️ 삭제 관리",
            "📊 2차시 탐구",
        ])

        # TAB 1: 실시간 드로잉 및 일괄 생성
        with sub_tab1:
            if pts_count == 0:
                st.info("👉 우측 지도 위를 마우스로 연속 클릭하여 경로 핀을 찍으세요.")
            else:
                st.success(f"📍 현재 찍힌 핀: **{pts_count}개**")

                route_name_input = st.text_input(
                    "구간 이름 (선택)",
                    placeholder="예: 운동장 직선코스, 본관 사잇길",
                    help="미입력 시 노면과 구간 번호로 자동 명명됩니다.",
                ).strip()

                is_shaded_all = st.checkbox("🌲 그늘 구간 일괄 적용 (일사 70% 차감)", value=False)

                btn_c1, btn_c2 = st.columns([1.5, 1.0])
                with btn_c1:
                    create_clicked = st.button(
                        "🚀 연속 도로 확정",
                        type="primary",
                        disabled=(pts_count < 2 or locked),
                        use_container_width=True,
                    )
                with btn_c2:
                    if st.button("🔄 핀 리셋", use_container_width=True):
                        st.session_state["drawing_points"] = []
                        st.rerun()

                if create_clicked:
                    pts = st.session_state["drawing_points"]
                    created_cnt = 0

                    expanded_pts: List[Tuple[float, float]] = []
                    for i in range(len(pts) - 1):
                        sub_seg = interpolate_points_by_distance(pts[i], pts[i + 1], interval_m=15.0)
                        if i == 0:
                            expanded_pts.extend(sub_seg)
                        else:
                            expanded_pts.extend(sub_seg[1:])

                    for i in range(len(expanded_pts) - 1):
                        p1, p2 = expanded_pts[i], expanded_pts[i + 1]

                        snapped_u_id, u_coords = snap_to_existing_node(p1, nodes_dict, threshold_m=15.0)
                        nodes_dict[snapped_u_id] = u_coords
                        snapped_v_id, v_coords = snap_to_existing_node(p2, nodes_dict, threshold_m=15.0)
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

                        seg_name = route_name_input if route_name_input else f"{snapped_u_id}➔{snapped_v_id}"
                        if len(expanded_pts) > 2:
                            seg_name = f"{seg_name} (#{i+1})"

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
                            created_cnt += 1

                    st.session_state["drawing_points"] = []
                    st.success(f"🎉 {created_cnt}개 간선 생성 완료!")
                    st.rerun()

                st.divider()
                st.caption("📍 찍힌 핀 좌표 내역:")
                for idx, pt in enumerate(st.session_state["drawing_points"], 1):
                    st.write(f"• #{idx}: `{pt[0]:.5f}`, `{pt[1]:.5f}`")

        # TAB 2: 구축된 간선 정보 수정 & 가중치 일괄 재연산
        with sub_tab2:
            if not edges:
                st.info("수정할 등록 도로가 없습니다.")
            else:
                st.markdown("##### ⚡ 실시간 환경 가중치 일괄 갱신")
                st.caption("현재 실시간 기상(기온/일사량) 및 DEM 지형 경사도를 전체 도로망에 동기화합니다.")
                if st.button("🔄 학급 전체 도로 가중치 일괄 재연산", type="secondary", use_container_width=True, disabled=locked):
                    with st.spinner("전체 도로망 경사도 및 복사에너지(R_abs) 재계산 중..."):
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

                        st.success(f"✅ 총 {recalc_cnt}개 도로 간선의 경사도와 흡수 복사에너지가 최신화되었습니다!")
                        st.rerun()

                st.divider()

                st.markdown("##### ✏️ 개별 도로 속성 수정")
                edge_id_map = {
                    e.get("edge_id"): f"{e.get('name', '무제')} ({e.get('u')}➔{e.get('v')})"
                    for e in edges
                }
                selected_edge_id = st.selectbox(
                    "수정할 간선 선택",
                    options=list(edge_id_map.keys()),
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

                        st.caption(f"거리: `{target_edge.get('length_m')}m` | 경사도: `{target_edge.get('slope_pct')}%`")

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
                            st.success("✅ 간선 정보가 갱신되었습니다!")
                            st.rerun()

        # TAB 3: 기존 노드 수동 연결
        with sub_tab3:
            available_nids = sorted(list(nodes_dict.keys()))
            if len(available_nids) >= 2:
                sel_u = st.selectbox("출발 노드 (U)", options=available_nids, key="m_u")
                sel_v = st.selectbox("도착 노드 (V)", options=available_nids, index=1, key="m_v")
                link_name = st.text_input("구간 이름", placeholder="예: 체육관 연결로", key="m_name")
                link_shaded = st.checkbox("그늘 구간", value=False, key="m_sh")

                if st.button("➕ 두 노드 직접 잇기", disabled=locked, use_container_width=True):
                    if sel_u != sel_v:
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
                        st.success(f"{sel_u} ➔ {sel_v} 연결 완료!")
                        st.rerun()
            else:
                st.info("등록된 노드가 2개 이상일 때 연결할 수 있습니다.")

        # TAB 4: 노드 및 간선 삭제
        with sub_tab4:
            if edges:
                e_del = st.selectbox("삭제 간선 선택", options=[e.get("edge_id", "") for e in edges], key="del_e")
                if st.button("선택 간선 삭제", disabled=locked, use_container_width=True):
                    delete_single_edge(class_code, e_del)
                    st.rerun()

                st.divider()
                n_del = st.selectbox("삭제 노드 선택 (연결 도로 함께 삭제)", options=sorted(list(nodes_dict.keys())), key="del_n")
                if st.button("선택 노드 및 관련 도로 전체 삭제", disabled=locked, use_container_width=True):
                    for ed in edges:
                        if ed.get("u") == n_del or ed.get("v") == n_del:
                            delete_single_edge(class_code, ed.get("edge_id", ""))
                    st.rerun()
            else:
                st.info("삭제할 데이터가 없습니다.")

        # 💡 TAB 5: 2차시 지구과학 탐구 (Alice Stats CSV 내보내기 & 복사에너지 시각화)
        with sub_tab5:
            st.markdown("##### 🌍 2차시 지구과학: 피복별 복사에너지 분석")
            st.caption("수집된 캠퍼스 도로망 데이터를 CSV로 추출하여 Alice Stats 통계 분석에 활용합니다.")

            if not edges:
                st.info("등록된 도로 데이터가 없습니다.")
            else:
                df_edges = pd.DataFrame(edges)

                # 내보낼 핵심 물리·환경 컬럼 매핑
                export_cols = [
                    "edge_id", "name", "u", "v", "surface_type", "albedo",
                    "absorbed_rad_w_m2", "slope_pct", "length_m", "is_shaded", "team_id"
                ]
                actual_cols = [c for c in export_cols if c in df_edges.columns]

                rename_map = {
                    "edge_id": "간선ID",
                    "name": "구간명",
                    "u": "시작노드",
                    "v": "도착노드",
                    "surface_type": "노면피복",
                    "albedo": "알베도_alpha",
                    "absorbed_rad_w_m2": "흡수복사에너지_W_m2",
                    "slope_pct": "경사도_pct",
                    "length_m": "거리_m",
                    "is_shaded": "그늘여부",
                    "team_id": "수집모둠",
                }

                df_export = df_edges[actual_cols].rename(columns=rename_map)

                # 1. UTF-8-SIG 인코딩 CSV 다운로드 버튼
                csv_bytes = df_export.to_csv(index=False, encoding="utf-8-sig").encode("utf-8-sig")
                st.download_button(
                    label="📥 Alice Stats용 도로망 CSV 다운로드",
                    data=csv_bytes,
                    file_name=f"papsrun_roads_{class_code}.csv",
                    mime="text/csv",
                    type="primary",
                    use_container_width=True,
                    help="Alice Stats 웹 클래스룸에 바로 업로드할 수 있는 UTF-8 CSV 파일입니다.",
                )

                st.divider()

                # 2. 노면 피복별 평균 순흡수 복사에너지 바 차트
                st.markdown("**📊 노면 피복별 평균 흡수 복사에너지 (W/m²)**")
                if "흡수복사에너지_W_m2" in df_export.columns and "노면피복" in df_export.columns:
                    df_chart = df_export.copy()
                    df_chart["흡수복사에너지_W_m2"] = pd.to_numeric(df_chart["흡수복사에너지_W_m2"], errors="coerce")
                    rad_summary = df_chart.groupby("노면피복")["흡수복사에너지_W_m2"].mean().dropna().round(1)

                    if not rad_summary.empty:
                        st.bar_chart(rad_summary, use_container_width=True)
                        st.caption("💡 *알베도($\\alpha$)가 낮을수록(예: 흑색 아스팔트) 지표 흡수 복사에너지가 극대화됩니다.*")

                # 3. 데이터 미리보기 테이블
                with st.expander("📋 CSV 원본 데이터 미리보기", expanded=False):
                    st.dataframe(df_export, use_container_width=True, height=200)

    # --------------------------------------------------------------------------
    # [우측] 풀사이즈 지도 캔버스
    # --------------------------------------------------------------------------
    with col_map:
        base_map = create_interactive_campus_map(
            center_lat=st.session_state["map_view_center"][0],
            center_lon=st.session_state["map_view_center"][1],
            zoom_start=st.session_state["map_view_zoom"],
        )

        rendered_map = render_graph_overlay(
            base_map,
            edges,
            nodes_dict,
            current_drawing_points=st.session_state["drawing_points"],
        )

        map_output = st_folium(
            rendered_map,
            width="100%",
            height=780,
            returned_objects=["last_clicked", "zoom", "center"],
            key="tab1_fullscreen_hud_map",
        )

        c_zoom = map_output.get("zoom")
        c_center = map_output.get("center")
        if c_zoom is not None:
            st.session_state["map_view_zoom"] = c_zoom
        if c_center is not None and isinstance(c_center, dict):
            st.session_state["map_view_center"] = [
                c_center.get("lat", st.session_state["map_view_center"][0]),
                c_center.get("lng", st.session_state["map_view_center"][1]),
            ]

        clicked = map_output.get("last_clicked")
        if clicked and not locked:
            new_p = (round(clicked["lat"], 5), round(clicked["lng"], 5))
            if not st.session_state["drawing_points"] or st.session_state["drawing_points"][-1] != new_p:
                st.session_state["drawing_points"].append(new_p)
                st.rerun()