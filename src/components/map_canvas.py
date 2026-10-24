"""캠퍼스 인터랙티브 지도 생성 및 지형·환경 도로망 오버레이 모듈.

- 기본 배경: CartoDB Positron (네이버/구글 스타일의 깔끔한 일반 지도)
- 레이어 컨트롤러(우측 상단)를 통해 위성 영상(Esri World Imagery) 전환 지원
- 노면 피복별 고유 색상 및 나무 그늘 점선 시각화
- 마우스 오버 시 학생이 지정한 '구간 이름' 및 복사에너지(R_abs) 툴팁 노출
- 연속 클릭 중인 임시 핀 및 Polyline 점선 오버레이 지원
"""

from typing import Any, Dict, List, Optional, Tuple
import folium
from folium import plugins

# 1. 노면 피복별 표준 시각화 색상 매핑
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
    enable_drawing: bool = False,
) -> folium.Map:
    """네이버/구글 지도 스타일의 풀 뷰 캠퍼스 Folium 지도를 생성합니다."""
    # 💡 기본 레이어: CartoDB Positron (일반 도로 지도)
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="CartoDB positron",
        control_scale=True,
    )

    # 선택 가능한 보조 레이어 1: OpenStreetMap
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="오픈스트리트맵 (지형지물)",
        control=True,
    ).add_to(m)

    # 선택 가능한 보조 레이어 2: Esri 위성 지도
    folium.TileLayer(
        tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
        attr="Esri World Imagery",
        name="고해상도 위성 지도",
        control=True,
    ).add_to(m)

    # 부가 플러그인 (전체화면, 마우스 위·경도 표시)
    plugins.Fullscreen(position="topright").add_to(m)
    plugins.MousePosition(
        position="bottomright",
        separator=" | ",
        empty_string="좌표 탐색",
        lng_first=False,
        num_digits=5,
        prefix="현재 좌표:",
    ).add_to(m)

    if enable_drawing:
        plugins.Draw(
            export=False,
            position="topleft",
            draw_options={"polyline": True, "marker": True},
        ).add_to(m)

    return m


def render_graph_overlay(
    base_map: folium.Map,
    edges: List[Dict[str, Any]],
    nodes_dict: Dict[str, Tuple[float, float]],
    highlight_edges: Optional[List[str]] = None,
    current_drawing_points: Optional[List[Tuple[float, float]]] = None,
) -> folium.Map:
    """구축된 학급 도로망과 현재 연속으로 찍고 있는 임시 드로잉 핀/경로를 지도에 오버레이합니다."""
    road_layer = folium.FeatureGroup(name="학급 도로망 (간선/노드)", show=True)
    drawing_layer = folium.FeatureGroup(name="현재 드로잉 핀/경로", show=True)

    highlight_set = set(highlight_edges or [])

    # 1. 확정된 기존 도로 간선 렌더링
    for edge in edges:
        edge_id = str(edge.get("edge_id", ""))
        u = str(edge.get("u", ""))
        v = str(edge.get("v", ""))

        u_coords = edge.get("u_coords") or edge.get("coord_u")
        v_coords = edge.get("v_coords") or edge.get("coord_v")

        # 노드 딕셔너리에서 좌표 폴백
        if not u_coords and u in nodes_dict:
            u_coords = list(nodes_dict[u])
        if not v_coords and v in nodes_dict:
            v_coords = list(nodes_dict[v])

        if not u_coords or not v_coords or len(u_coords) < 2 or len(v_coords) < 2:
            continue

        surface = str(edge.get("surface_type", "asphalt_dark"))
        is_shaded = bool(edge.get("is_shaded", False))
        length_m = float(edge.get("length_m", edge.get("length", 0.0)))
        slope_pct = float(edge.get("slope_pct", edge.get("slope", 0.0)))
        r_abs = edge.get("absorbed_rad_w_m2", edge.get("net_radiation", "-"))
        seg_name = edge.get("name") or f"{u} ➔ {v}"

        line_color = SURFACE_COLOR_MAP.get(surface, "#212529")
        line_weight = 5
        opacity = 0.85

        # 결함 구간 강조
        if edge_id in highlight_set or f"{u}_{v}" in highlight_set:
            line_color = "#FF0055"
            line_weight = 7
            opacity = 1.0

        # 💡 구간 이름 및 주요 지표 툴팁
        tooltip_html = (
            f"<div style='font-family: Pretendard, sans-serif; font-size: 12px; line-height: 1.4;'>"
            f"<b>📍 구간: {seg_name}</b> ({length_m:.1f}m)<br>"
            f"• <b>노면:</b> {surface}<br>"
            f"• <b>흡수 복사에너지:</b> <span style='color:#E63946; font-weight:bold;'>{r_abs} W/m²</span><br>"
            f"• <b>경사도:</b> {slope_pct:.1f}% | <b>그늘:</b> {'🌲 O' if is_shaded else '☀️ X'}"
            f"</div>"
        )

        folium.PolyLine(
            locations=[u_coords, v_coords],
            color=line_color,
            weight=line_weight,
            opacity=opacity,
            dash_array="6, 6" if is_shaded else None,
            tooltip=folium.Tooltip(tooltip_html),
        ).add_to(road_layer)

    # 2. 확정된 기존 노드 마커 렌더링
    for node_id, coords in nodes_dict.items():
        folium.CircleMarker(
            location=coords,
            radius=4,
            color="#1D3557",
            weight=2,
            fill=True,
            fill_color="#FFFFFF",
            fill_opacity=0.9,
            tooltip=f"교차점(Node): {node_id}",
        ).add_to(road_layer)

    # 3. 실시간으로 연속 클릭 중인 임시 핀 및 Polyline 표시
    if current_drawing_points:
        for idx, pt in enumerate(current_drawing_points, start=1):
            folium.CircleMarker(
                location=pt,
                radius=6,
                color="#E63946",
                weight=3,
                fill=True,
                fill_color="#FF4D6D",
                fill_opacity=1.0,
                tooltip=f"임시 핀 #{idx} ({pt[0]:.5f}, {pt[1]:.5f})",
            ).add_to(drawing_layer)

        if len(current_drawing_points) >= 2:
            folium.PolyLine(
                locations=current_drawing_points,
                color="#E63946",
                weight=3,
                dash_array="6, 6",
                opacity=0.9,
                tooltip="생성 대기 중인 도로 선",
            ).add_to(drawing_layer)

    road_layer.add_to(base_map)
    drawing_layer.add_to(base_map)

    # 우측 상단 레이어 전환 컨트롤러 (일반 지도 ↔ 위성 지도)
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
    """3단계 다익스트라 최적화 경로를 지도 위에 강조하여 렌더링합니다."""
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

    # 출발지와 도착지 마커
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