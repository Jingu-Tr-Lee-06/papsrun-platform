"""Folium 기반 캠퍼스 도로망 작도 및 동적 경로 시각화 캔버스 컴포넌트.

사용자가 지도를 클릭하여 간선/노드를 추가할 수 있는 Leaflet Draw 플러그인,
수집된 도로망 간선과 교차점 노드, 그리고 다익스트라 최적 경로를
색상 코딩된 레이어로 인터랙티브하게 렌더링합니다.
"""

from typing import Any, Dict, List, Optional, Tuple
import folium
from folium.plugins import Draw, MeasureControl

# 노면 재질별 렌더링 컬러 팔레트 매핑
SURFACE_COLOR_PALETTE: Dict[str, str] = {
    "urethane_track": "#E63946",     # 우레탄 러닝 트랙 (선명한 빨강)
    "soil_trail": "#8B5A2B",         # 흙길 산책로 (자연 갈색)
    "lawn_grass": "#2A9D8F",         # 잔디 (청록 녹색)
    "concrete_walkway": "#457B9D",   # 보도블록/콘크리트 (청록 파랑)
    "asphalt_aged": "#6C757D",       # 노후 아스팔트 (회색)
    "asphalt_dark": "#212529",       # 신설 아스팔트 (짙은 차콜)
}


def create_interactive_campus_map(
    center_lat: float = 36.4675,
    center_lon: float = 127.1405,
    zoom_start: int = 17,
    enable_drawing: bool = False,
) -> folium.Map:
    """캠퍼스 중심 기본 대화형 지도 객체를 생성합니다.

    Args:
        center_lat: 중심 위도 (기본값: 공주대 신관캠퍼스 중심)
        center_lon: 중심 경도
        zoom_start: 초기 줌 레벨
        enable_drawing: 선/점 작도 툴바 활성화 여부

    Returns:
        folium.Map 인스턴스
    """
    m = folium.Map(
        location=[center_lat, center_lon],
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
    )

    # 거리 측정 도구 추가
    m.add_child(MeasureControl(position="topleft", primary_length_unit="meters"))

    # 선 작도 도구 활성화 (1단계 지도 작도용)
    if enable_drawing:
        draw_options = {
            "polyline": True,
            "polygon": False,
            "circle": False,
            "rectangle": False,
            "marker": True,
            "circlemarker": False,
        }
        Draw(
            export=False,
            position="topleft",
            draw_options=draw_options,
        ).add_to(m)

    return m


def render_graph_overlay(
    folium_map: folium.Map,
    edges: List[Dict[str, Any]],
    nodes_dict: Dict[str, Tuple[float, float]],
    highlight_edges: Optional[List[str]] = None,
) -> folium.Map:
    """수집된 도로망 간선과 교차점 노드를 지도 위에 오버레이합니다.

    Args:
        folium_map: folium.Map 인스턴스
        edges: 도로 간선 딕셔너리 리스트
        nodes_dict: {node_id: (lat, lon)} 딕셔너리
        highlight_edges: 강조 표시할 간선 ID 목록

    Returns:
        레이어가 추가된 folium.Map 객체
    """
    highlight_set = set(highlight_edges or [])

    # 1. 간선(Edges) 렌더링
    for edge in edges:
        u_coords = edge.get("u_coords")
        v_coords = edge.get("v_coords")
        if not u_coords or not v_coords:
            continue

        edge_id = edge.get("edge_id", "")
        surface = edge.get("surface_type", "concrete_walkway")
        color = SURFACE_COLOR_PALETTE.get(surface, "#457B9D")
        is_shaded = edge.get("is_shaded", False)
        length_m = edge.get("length_m", 0.0)
        team_id = edge.get("team_id", "미지정")

        is_high = edge_id in highlight_set
        weight = 7 if is_high else 4
        opacity = 0.95 if is_high else 0.75

        shade_tag = "🌳 그늘" if is_shaded else "☀️ 직사광"
        popup_content = (
            f"<div style='font-family: sans-serif; font-size: 13px;'>"
            f"<b>간선 ID:</b> {edge_id}<br>"
            f"<b>노면:</b> {surface}<br>"
            f"<b>거리:</b> {length_m:.1f} m<br>"
            f"<b>환경:</b> {shade_tag}<br>"
            f"<b>모둠:</b> {team_id}</div>"
        )

        folium.PolyLine(
            locations=[u_coords, v_coords],
            color=color,
            weight=weight,
            opacity=opacity,
            tooltip=f"{surface} ({length_m:.1f}m) [{shade_tag}]",
            popup=folium.Popup(popup_content, max_width=240),
        ).add_to(folium_map)

    # 2. 노드(Nodes) 렌더링
    for node_id, (lat, lon) in nodes_dict.items():
        folium.CircleMarker(
            location=[lat, lon],
            radius=4,
            color="#1D3557",
            weight=2,
            fill=True,
            fill_color="#F1FAEE",
            fill_opacity=0.9,
            tooltip=f"노드: {node_id}",
            popup=f"<b>노드 ID:</b> {node_id}<br>좌표: ({lat:.5f}, {lon:.5f})",
        ).add_to(folium_map)

    return folium_map


def render_dynamic_path_layer(
    folium_map: folium.Map,
    path_nodes: List[str],
    nodes_dict: Dict[str, Tuple[float, float]],
    label: str = "최적 경로",
    color: str = "#06D6A0",
    is_dashed: bool = False,
) -> folium.Map:
    """탐색된 노드 순서열을 폴리라인 및 시작/종료 마커로 지도에 그립니다.

    Args:
        folium_map: folium.Map 객체
        path_nodes: 경로 상의 노드 ID 리스트
        nodes_dict: {node_id: (lat, lon)} 딕셔너리
        label: 경로 라벨
        color: 선 색상
        is_dashed: 점선 스타일 적용 여부

    Returns:
        경로 레이어가 추가된 folium.Map 객체
    """
    if not path_nodes or len(path_nodes) < 2:
        return folium_map

    coords = [nodes_dict[n] for n in path_nodes if n in nodes_dict]
    if len(coords) < 2:
        return folium_map

    dash_style = "10, 10" if is_dashed else None

    # 경로 폴리라인
    folium.PolyLine(
        locations=coords,
        color=color,
        weight=6,
        opacity=0.95,
        dash_array=dash_style,
        tooltip=label,
    ).add_to(folium_map)

    # 출발점 마커 (초록 재생 버튼)
    folium.Marker(
        location=coords[0],
        icon=folium.Icon(color="green", icon="play", prefix="fa"),
        tooltip=f"출발점: {path_nodes[0]}",
    ).add_to(folium_map)

    # 도착점 마커 (빨간 깃발)
    folium.Marker(
        location=coords[-1],
        icon=folium.Icon(color="red", icon="flag-checkered", prefix="fa"),
        tooltip=f"도착점: {path_nodes[-1]}",
    ).add_to(folium_map)

    return folium_map