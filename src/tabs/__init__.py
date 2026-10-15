"""PAPSrun 학생 5단계 학습 워크스페이스 탭 컨트롤러 패키지.

1단계: 캠퍼스 지형·환경 맵 연속 작도 화면
2단계: 학급 도로망 위상 및 연결성 검사 화면
3단계: 바이브 코딩 경로 최적화 대화·실행 화면
4단계: 웹 VS Code (code-server) 임베딩 화면
5단계: 엣지 구동 및 최종 PAPS 산출물 리포트 화면
"""

from src.tabs.tab1_map_builder import render_tab1_map_builder
from src.tabs.tab2_topology_checker import render_tab2_topology_checker
from src.tabs.tab3_vibe_optimizer import render_tab3_vibe_optimizer
from src.tabs.tab4_vscode_workspace import render_tab4_vscode_workspace
from src.tabs.tab5_edge_runner_artifact import render_tab5_edge_runner_artifact

__all__ = [
    "render_tab1_map_builder",
    "render_tab2_topology_checker",
    "render_tab3_vibe_optimizer",
    "render_tab4_vscode_workspace",
    "render_tab5_edge_runner_artifact",
]