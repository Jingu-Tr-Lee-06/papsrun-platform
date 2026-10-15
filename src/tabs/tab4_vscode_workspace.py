"""[4단계 UI] 웹 VS Code (code-server) 임베딩 워크스페이스 화면 컨트롤러 모듈.

학생들이 브라우저 내부에서 격리된 파이썬 프로젝트 작업 공간(data/code_workspace/)을 열어
직접 다익스트라 확장 가중치 알고리즘을 코딩하고, 단위 테스트를 실행하며,
실제 개발 환경의 개발 주기(수정-저장-실행)를 체험할 수 있도록 지원합니다.
"""

import os
from typing import Optional
import streamlit as st

from src.components.vscode_iframe import render_vscode_workspace


def render_tab4_vscode_workspace(class_code: str, team_id: str) -> None:
    """4단계 웹 VS Code 워크스페이스 탭을 렌더링합니다.

    Args:
        class_code: 현재 접속한 학급 코드
        team_id: 현재 로그인한 모둠 식별자
    """
    st.markdown("### 💻 4단계: 전문 개발 환경 워크스페이스 (VS Code)")
    st.caption(
        "바이브 코딩으로 도출된 프로토타입을 넘어, 실제 파이썬 모듈 구조 내에서 "
        "단위 테스트(Unit Test)를 작성하고 가중치 알고리즘의 복잡도와 예외를 직접 디버깅합니다."
    )

    # 상단 퀵 가이드 및 워크스페이스 상태 요약
    guide_col1, guide_col2 = st.columns([2, 1])
    with guide_col1:
        st.info(
            f"📂 **작업 경로:** `data/code_workspace/` | **현재 세션:** `{class_code}` ({team_id})\n\n"
            "• `vibe_runner.py` 파일을 열어 함수 로직과 테스트 케이스를 수정할 수 있습니다.\n"
            "• 수정된 알고리즘은 5단계 엣지 보드 주행 디스패치 파이프라인과 직접 연계됩니다."
        )
    with guide_col2:
        st.markdown(
            "> **💡 학습 팁**\n"
            "> `math` 라이브러리의 삼각함수나 지수함수를 활용하여 "
            "> 급경사 오르막에 대한 페널티를 비선형적으로 증가시켜 보세요."
        )

    st.divider()

    # 웹 VS Code 임베더 컴포넌트 호출
    render_vscode_workspace(height=680)