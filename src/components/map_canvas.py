"""캠퍼스 인터랙티브 지도 생성 및 지형·환경 도로망 오버레이 모듈.

- 모드별 지원: 선 그리기(Draw) 및 개별 점/노드 직접 클릭 스냅(Point-to-Point)
- 다중 선(Multi-Polyline) 누적 버퍼 렌더링 지원 (끊어져 있는 여러 도로 동시 시각화)
- 방향별 경사도 및 복사에너지(R_abs) 툴팁 노출
- 간선 클릭 시 '삭제 관리' 패널 연동 선택 기능
"""

from typing import Any, Dict, List, Optional, Tuple
import folium
from folium import plugins

SURFACE_COLOR_MAP: Dict[str, str] = {
    "urethane_track": "#E63946",   # 우레탄: 빨강
    "soil_trail": "#DDA15E",       # 흙길: 황토색
    "lawn_grass": "#2A9D8F",       # 잔디: 초록
    "concrete_walkway": "#457B9D", # 콘크리트/보도블록: 청파랑
    "asphalt_aged": "#6C757D",     # 노후 아스팔트: 중회색
    "asphalt_dark": "#212529",     # 신설 아스팔트: 흑색
    "dirt": "#DDA15E",
    "grass": "#2A9D8F",
    "concrete": "#457B9D",
    "asphalt": "#212529",
}


def create_interactive_campus_map(
    center_lat: float = 36.4675,
    center_lon: float = 127.1405,
    zoom_start: int = 17,
    draw_mode: str = "line",
) -> folium.Map:
    """캠퍼스 베이스맵 생성."""
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="CartoDB positron",
        control_scale=True,
    )

    folium.TileLayer(
        tiles="OpenStreetMap",
        name="오픈스트리트맵 (지형지물)",
        control=True,
    ).add_to(m)

    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="고해상도 위성 지도",
        control=True,
    ).add_to(m)

    plugins.Fullscreen(position="topright").add_to(m)
    plugins.MousePosition(
        position="bottomright",
        separator=" | ",
        empty_string="좌표 탐색",
        lng_first=False,
        num_digits=5,
        prefix="현재 좌표:",
    ).add_to(m)

    if draw_mode == "line":
        plugins.Draw(
            export=False,
            position="topleft",
            draw_options={
                "polyline": {
                    "shapeOptions": {
                        "color": "#E63946",
                        "weight": 4,
                        "dashArray": "6, 6"
                    }
                },
                "polygon": False,
                "circle": False,
                "rectangle": False,
                "marker": False,
                "circlemarker": False,
            },
            edit_options={"edit": False, "remove": True},
        ).add_to(m)

    return m


def render_graph_overlay(
    base_map: folium.Map,
    edges: List[Dict[str, Any]],
    nodes_dict: Dict[str, Tuple[float, float]],
    highlight_edges: Optional[List[str]] = None,
    current_drawing_points: Optional[List[Tuple[float, float]]] = None,
    interactive_nodes: bool = False,
    selected_edge_id: Optional[str] = None,
    multi_lines_buffer: Optional[List[List[Tuple[float, float]]]] = None,
) -> folium.Map:
    """도로망 및 노드, 다중 누적 대기 선들을 지도에 렌더링."""
    road_layer = folium.FeatureGroup(name="학급 도로망 (간선/노드)", show=True)
    drawing_layer = folium.FeatureGroup(name="작도 대기 경로", show=True)
    highlight_set = set(highlight_edges or [])

    # 1. 확정된 기존 도로 간선 렌더링
    for edge in edges:
        edge_id = str(edge.get("edge_id", ""))
        u = str(edge.get("u", ""))
        v = str(edge.get("v", ""))

        u_coords = edge.get("u_coords") or edge.get("coord_u")
        v_coords = edge.get("v_coords") or edge.get("coord_v")

        if not u_coords and u in nodes_dict:
            u_coords = list(nodes_dict[u])
        if not v_coords and v in nodes_dict:
            v_coords = list(nodes_dict[v])

        if not u_coords or not v_coords or len(u_coords) < 2 or len(v_coords) < 2:
            continue

        surface = str(edge.get("surface_type", "asphalt_dark"))
        is_shaded = bool(edge.get("is_shaded", False))
        length_m = float(edge.get("length_m", edge.get("length", 0.0)))

        fwd_slope = float(edge.get("slope_pct", edge.get("slope", 0.0)))
        rev_slope = -fwd_slope

        fwd_label = "오르막 🔺" if fwd_slope > 0 else ("내리막 🔻" if fwd_slope < 0 else "평지 ➖")
        rev_label = "오르막 🔺" if rev_slope > 0 else ("내리막 🔻" if rev_slope < 0 else "평지 ➖")

        r_abs = edge.get("absorbed_rad_w_m2", edge.get("net_radiation", "-"))
        seg_name = edge.get("name") or f"{u} ➔ {v}"

        line_color = SURFACE_COLOR_MAP.get(surface, "#212529")
        line_weight = 5
        opacity = 0.85

        is_selected = (selected_edge_id and edge_id == selected_edge_id)
        if is_selected:
            line_color = "#FF0055"
            line_weight = 8
            opacity = 1.0
        elif edge_id in highlight_set or f"{u}_{v}" in highlight_set:
            line_color = "#FF8500"
            line_weight = 7
            opacity = 1.0

        tooltip_html = (
            f"<div style='font-family: Pretendard, sans-serif; font-size: 12px; line-height: 1.5;'>"
            f"<b>📍 {seg_name}</b> ({length_m:.1f}m)<br>"
            f"• <b>노면:</b> {surface} | <b>그늘:</b> {'🌲 O' if is_shaded else '☀️ X'}<br>"
            f"• <b>순방향 ({u}➔{v}):</b> <span style='font-weight:bold; color:{'#e63946' if fwd_slope>0 else '#1d3557'};'>{fwd_slope:+.1f}% ({fwd_label})</span><br>"
            f"• <b>역방향 ({v}➔{u}):</b> <span style='font-weight:bold; color:{'#e63946' if rev_slope>0 else '#1d3557'};'>{rev_slope:+.1f}% ({rev_label})</span><br>"
            f"• <b>흡수 복사에너지:</b> <span style='color:#e63946; font-weight:bold;'>{r_abs} W/m²</span><br>"
            f"<span style='color:#0284c7; font-size:11px; font-weight:bold;'>👉 클릭하여 이 간선 선택/삭제</span>"
            f"</div>"
        )

        popup_html = (
            f"<div style='font-family: Pretendard, sans-serif; font-size: 12px; text-align:center; padding:4px;'>"
            f"<b>선택된 간선:</b> <code>{seg_name}</code><br>"
            f"<a href='?select_edge_id={edge_id}' target='_self' "
            f"style='display:inline-block; margin-top:6px; background:#0284c7; color:white; "
            f"padding:4px 10px; border-radius:4px; text-decoration:none; font-weight:bold; font-size:11px;'>"
            f"🎯 삭제/관리 패널에서 선택</a>"
            f"</div>"
        )

        folium.PolyLine(
            locations=[u_coords, v_coords],
            color=line_color,
            weight=line_weight,
            opacity=opacity,
            dash_array="6, 6" if is_shaded else None,
            tooltip=folium.Tooltip(tooltip_html),
            popup=folium.Popup(popup_html, max_width=220),
        ).add_to(road_layer)

    # 2. 노드 마커 렌더링
    node_radius = 6 if interactive_nodes else 4
    for node_id, coords in nodes_dict.items():
        folium.CircleMarker(
            location=coords,
            radius=node_radius,
            color="#0077B6" if interactive_nodes else "#1D3557",
            weight=3 if interactive_nodes else 2,
            fill=True,
            fill_color="#CAF0F8" if interactive_nodes else "#FFFFFF",
            fill_opacity=0.95,
            tooltip=f"교차점(Node): {node_id} (클릭 시 자동 스냅 연결)",
        ).add_to(road_layer)

    # 3. 누적된 여러 개의 끊어진 선(Multi-Polyline) 버퍼 렌더링
    if multi_lines_buffer:
        for idx, line_coords in enumerate(multi_lines_buffer, start=1):
            folium.PolyLine(
                locations=line_coords,
                color="#E63946",
                weight=4,
                dash_array="6, 6",
                opacity=0.9,
                tooltip=f"대기 중인 도로 #{idx} (핀 {len(line_coords)}개)",
            ).add_to(drawing_layer)

            # 양 끝단 지점에 시각적 마커 표시
            for pt in [line_coords[0], line_coords[-1]]:
                folium.CircleMarker(
                    location=pt,
                    radius=5,
                    color="#D90429",
                    weight=2,
                    fill=True,
                    fill_color="#FF4D6D",
                    fill_opacity=0.9,
                ).add_to(drawing_layer)

    # 4. 점 직접 찍기 모드에서 현재 작업 중인 단일 경로 렌더링
    if current_drawing_points:
        for idx, pt in enumerate(current_drawing_points, start=1):
            is_last = (idx == len(current_drawing_points))
            folium.CircleMarker(
                location=pt,
                radius=7 if is_last else 5,
                color="#D90429",
                weight=3,
                fill=True,
                fill_color="#FF4D6D" if is_last else "#FFAFCC",
                fill_opacity=1.0,
                tooltip=f"작도 핀 #{idx} ({pt[0]:.5f}, {pt[1]:.5f})",
            ).add_to(drawing_layer)

        if len(current_drawing_points) >= 2:
            folium.PolyLine(
                locations=current_drawing_points,
                color="#D90429",
                weight=4,
                dash_array="6, 6",
                opacity=0.9,
                tooltip="생성 대기 중인 연결 도로",
            ).add_to(drawing_layer)

    road_layer.add_to(base_map)
    drawing_layer.add_to(base_map)
    folium.LayerControl(position="topright", collapsed=True).add_to(base_map)

    return base_map


def render_dynamic_path_layer(
    base_map: folium.Map,
    path_nodes: List[str],
    nodes_dict: Dict[str, Tuple[float, float]],
    label: str,
    color: str,
    is_dashed: bool = False,
) -> None:
    """최적화 경로 레이어를 렌더링합니다."""
    locations = [nodes_dict[nid] for nid in path_nodes if nid in nodes_dict]
    if len(locations) < 2:
        return

    folium.PolyLine(
        locations=locations,
        color=color,
        weight=6,
        opacity=0.95,
        dash_array="8, 8" if is_dashed else None,
        tooltip=f"<b>{label}</b> (총 {len(locations)}개 노드 경유)",
    ).add_to(base_map)

    folium.Marker(
        location=locations[0],
        icon=folium.Icon(color="green", icon="play"),
        tooltip=f"출발: {path_nodes[0]}",
    ).add_to(base_map)

    folium.Marker(
        location=locations[-1],
        icon=folium.Icon(color="black", icon="flag"),
        tooltip=f"도착: {path_nodes[-1]}",
    ).add_to(base_map)