"""PAPSrun 프론트엔드 재사용 가능 UI 컴포넌트 패키지.

Folium 기반 대화형 지도 캔버스, Gemini 바이브 코딩 사이드 패널,
웹 기반 VS Code(code-server) iframe 임베더, PAPS 핵심 운동역학 지표 카드를 제공합니다.
"""

from src.components.map_canvas import (
    create_interactive_campus_map,
    render_dynamic_path_layer,
    render_graph_overlay,
)
from src.components.metrics_card import (
    render_comparative_metrics_card,
    render_paps_fitness_card,
    render_surface_breakdown_widget,
)
from src.components.vibe_chat_panel import (
    render_vibe_chat_sidebar,
)
from src.components.vscode_iframe import (
    generate_vscode_embed_url,
    render_vscode_workspace,
)

__all__ = [
    # 지도 캔버스
    "create_interactive_campus_map",
    "render_graph_overlay",
    "render_dynamic_path_layer",
    # 바이브 코딩 패널
    "render_vibe_chat_sidebar",
    # VS Code 임베딩
    "generate_vscode_embed_url",
    "render_vscode_workspace",
    # 지표 카드
    "render_paps_fitness_card",
    "render_comparative_metrics_card",
    "render_surface_breakdown_widget",
]