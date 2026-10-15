"""Folium 기반 캠퍼스 도로망 및 경로 탐색 시각화 모듈.

학급에서 작도된 도로 간선(Edges), 교차점 노드(Nodes),
그리고 다익스트라 알고리즘으로 도출된 최적 경로(최단거리, 쾌적 경로, 바이브 코딩 경로)를
색상 코딩된 폴리라인과 커스텀 마커로 인터랙티브 지도 위에 렌더링합니다.
"""

from typing import Any, Dict, List, Optional, Tuple
import folium
from folium.plugins import MeasureControl

# 노면 재질별 지도 폴리라인 렌더링 색상 매핑
SURFACE_COLOR_MAP: Dict[str, str] = {
    "urethane_track": "#E63946",     # 우레탄 트랙 (선명한 빨강)
    "soil_trail": "#8B5A2B",         # 흙길 산책로 (갈색)
    "lawn_grass": "#2A9D8F",         # 잔디 (청록녹색)
    "concrete_walkway": "#457B9D",   # 콘크리트/보도블록 (파랑)
    "asphalt_aged": "#6C757D",       # 노후 아스팔트 (회색)
    "asphalt_dark": "#212529",       # 신설/짙은 아스팔트 (검정)
}


def create_base_campus_map(
    center_lat: float = 36.4675,
    center_lon: float = 127.1405,
    zoom_start: int = 17,
) -> folium.Map:
    """캠퍼스 중심 기본 Folium 지도 객체를 생성합니다.

    Args:
        center_lat: 중심 위도 (기본값: 공주대학교 신관캠퍼스 중심)
        center_lon: 중심 경도
        zoom_start: 초기 줌 레벨

    Returns:
        folium.Map 객체
    """
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
    )
    # 거리 측정 도구 플러그인 추가
    m.add_child(MeasureControl(position="topleft", primary_length_unit="meters"))
    return m


def render_edges_on_map(
    folium_map: folium.Map,
    edges: List[Dict[str, Any]],
    highlight_edge_ids: Optional[List[str]] = None,
) -> folium.Map:
    """수집된 도로 간선들을 노면 재질별 색상과 함께 지도에 그립니다.

    Args:
        folium_map: 렌더링 대상 folium.Map 객체
        edges: 도로 간선 딕셔너리 리스트
        highlight_edge_ids: 강조할 간선 식별자 목록 (선택 사항)

    Returns:
        간선이 추가된 folium.Map 객체
    """
    highlight_set = set(highlight_edge_ids or [])

    for edge in edges:
        u_coords = edge.get("u_coords")
        v_coords = edge.get("v_coords")
        if not u_coords or not v_coords:
            continue

        edge_id = edge.get("edge_id", "")
        surface = edge.get("surface_type", "concrete_walkway")
        color = SURFACE_COLOR_MAP.get(surface, "#457B9D")
        is_shaded = edge.get("is_shaded", False)
        length_m = edge.get("length_m", 0.0)
        team_id = edge.get("team_id", "미지정")

        # 강조 간선일 경우 두께와 투명도 상향
        is_highlighted = edge_id in highlight_set
        weight = 7 if is_highlighted else 4
        opacity = 0.95 if is_highlighted else 0.75

        # 팝업 툴팁 구성
        shade_label = "🌳 그늘 구간" if is_shaded else "☀️ 직사광 구간"
        popup_html = (
            f"<b>간선 ID:</b> {edge_id}<br>"
            f"<b>노면:</b> {surface}<br>"
            f"<b>거리:</b> {length_m:.1f} m<br>"
            f"<b>환경:</b> {shade_label}<br>"
            f"<b>기여 모둠:</b> {team_id}"
        )

        folium.PolyLine(
            locations=[u_coords, v_coords],
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=f"{surface} ({length_m:.1f}m) - {shade_label}",
            popup=folium.Popup(popup_html, max_width=250),
        ).add_to(folium_map)

    return folium_map


def render_nodes_on_map(
    folium_map: folium.Map,
    nodes_map: Dict[str, Tuple[float, float]],
    selected_node_ids: Optional[List[str]] = None,
) -> folium.Map:
    """교차점 노드들을 원형 마커로 지도에 표시합니다.

    Args:
        folium_map: folium.Map 객체
        nodes_map: {node_id: (lat, lon)} 딕셔너리
        selected_node_ids: 특별 강조할 노드 목록 (출발/도착 등)

    Returns:
        노드가 추가된 folium.Map 객체
    """
    selected_set = set(selected_node_ids or [])

    for node_id, (lat, lon) in nodes_map.items():
        is_selected = node_id in selected_set
        radius = 7 if is_selected else 4
        color = "#D90429" if is_selected else "#2B2D42"
        fill_color = "#FFD166" if is_selected else "#8D99AE"

        folium.CircleMarker(
            location=[lat, lon],
            radius=radius,
            color=color,
            weight=2,
            fill=True,
            fill_color=fill_color,
            fill_opacity=0.9,
            tooltip=f"노드: {node_id}",
            popup=f"<b>노드 ID:</b> {node_id}<br><b>좌표:</b> ({lat:.5f}, {lon:.5f})",
        ).add_to(folium_map)

    return folium_map


def render_optimal_path_overlay(
    folium_map: folium.Map,
    node_sequence: List[str],
    nodes_map: Dict[str, Tuple[float, float]],
    path_name: str = "최적 경로",
    path_color: str = "#06D6A0",
    dash_array: Optional[str] = None,
) -> folium.Map:
    """다익스트라 알고리즘 등으로 탐색된 노드 경로를 지도 위에 강조 선으로 오버레이합니다.

    Args:
        folium_map: folium.Map 객체
        node_sequence: 노드 ID 리스트 (순서대로)
        nodes_map: {node_id: (lat, lon)} 좌표 딕셔너리
        path_name: 경로 명칭 (툴팁/팝업용)
        path_color: 렌더링 선 색상 코드
        dash_array: 점선 표현용 스타일 (예: '10, 10')

    Returns:
        경로가 렌더링된 folium.Map 객체
    """
    if not node_sequence or len(node_sequence) < 2:
        return folium_map

    path_coords = []
    for node_id in node_sequence:
        if node_id in nodes_map:
            path_coords.append(nodes_map[node_id])

    if len(path_coords) < 2:
        return folium_map

    # 1. 경로 폴리라인 렌더링
    folium.PolyLine(
        locations=path_coords,
        color=path_color,
        weight=6,
        opacity=0.9,
        dash_array=dash_array,
        tooltip=path_name,
    ).add_to(folium_map)

    # 2. 출발점 마커 (초록 깃발)
    start_pt = path_coords[0]
    folium.Marker(
        location=start_pt,
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
        tooltip=f"🏁 출발: {node_sequence[0]}",
    ).add_to(folium_map)

    # 3. 도착점 마커 (빨간 깃발)
    end_pt = path_coords[-1]
    folium.Marker(
        location=end_pt,
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        tooltip=f"🎯 도착: {node_sequence[-1]}",
    ).add_to(folium_map)

    return folium_map