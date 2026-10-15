"""PAPSrun 프론트엔드 UI 컴포넌트 및 시각화 패키지.

세션 인증 및 역할 관리, Folium 인터랙티브 지도 렌더러, 대시보드 지표 카드 컴포넌트를 제공합니다.
"""

from src.ui.auth import (
    get_active_gemini_key,
    init_session_state,
    render_auth_sidebar,
    verify_teacher_pin,
)
from src.ui.dashboard_components import (
    render_environmental_summary,
    render_metric_cards,
    render_surface_distribution_bar,
    render_topology_health_card,
)
from src.ui.map_renderer import (
    SURFACE_COLOR_MAP,
    create_base_campus_map,
    render_edges_on_map,
    render_nodes_on_map,
    render_optimal_path_overlay,
)

__all__ = [
    # 인증 및 세션 관리
    "init_session_state",
    "verify_teacher_pin",
    "render_auth_sidebar",
    "get_active_gemini_key",
    # Folium 지도 시각화
    "SURFACE_COLOR_MAP",
    "create_base_campus_map",
    "render_edges_on_map",
    "render_nodes_on_map",
    "render_optimal_path_overlay",
    # 대시보드 지표 컴포넌트
    "render_metric_cards",
    "render_environmental_summary",
    "render_surface_distribution_bar",
    "render_topology_health_card",
]