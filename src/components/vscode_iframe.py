"""웹 기반 VS Code (code-server) 임베딩 렌더러 컴포넌트.

Streamlit 인터페이스 내에 iframe을 삽입하여 학생이 브라우저에서 직접
data/code_workspace/ 디렉터리의 파이썬 스크립트를 편집, 디버깅할 수 있도록 지원하며,
code-server 활성화 여부 확인 및 대체 로컬 코드 에디터 폴백을 제공합니다.
"""

from typing import Optional
import os
import streamlit as st
import streamlit.components.v1 as components

WORKSPACE_DIR = os.path.join("data", "code_workspace")


def ensure_workspace_initialized() -> None:
    """학생 작업 공간 디렉터리 및 기본 예제 스크립트를 생성합니다."""
    os.makedirs(WORKSPACE_DIR, exist_ok=True)
    sample_script_path = os.path.join(WORKSPACE_DIR, "vibe_runner.py")

    if not os.path.exists(sample_script_path):
        sample_code = (
            '"""PAPSrun 학생 알고리즘 작업 영역 예제 스크립트."""\n\n'
            "def calculate_path_cost(distance_m, slope_pct, surface_type):\n"
            "    # 노면별 마찰계수 보정\n"
            "    surface_weights = {\n"
            "        'urethane_track': 0.8,\n"
            "        'lawn_grass': 1.0,\n"
            "        'concrete_walkway': 1.1,\n"
            "        'soil_trail': 1.2,\n"
            "        'asphalt_dark': 1.3,\n"
            "    }\n"
            "    weight = surface_weights.get(surface_type, 1.0)\n"
            "    # 경사도 보정 (오르막 저항)\n"
            "    slope_factor = 1.0 + (max(0.0, slope_pct) * 0.05)\n"
            "    return distance_m * weight * slope_factor\n\n\n"
            "if __name__ == '__main__':\n"
            "    sample_cost = calculate_path_cost(100.0, 3.5, 'urethane_track')\n"
            "    print(f'계산된 경로 가중치 비용: {sample_cost:.2f}')\n"
        )
        with open(sample_script_path, "w", encoding="utf-8") as f:
            f.write(sample_code)


def generate_vscode_embed_url(
    host: Optional[str] = None,
    port: Optional[int] = None,
) -> str:
    """code-server의 엔드포인트 URL을 생성합니다.

    Args:
        host: 호스트 주소 (기본값: localhost)
        port: code-server 서비스 포트 (기본값: 8080)

    Returns:
        임베딩용 URL 문자열
    """
    server_secrets = st.secrets.get("code_server", {})
    resolved_host = host or server_secrets.get("host", "localhost")
    resolved_port = port or int(server_secrets.get("port", 8080))

    # 기본 파라미터로 code_workspace 폴더 바로 열기 지정
    return f"http://{resolved_host}:{resolved_port}/?folder=/workspace/{WORKSPACE_DIR}"


def render_vscode_workspace(height: int = 650) -> None:
    """Streamlit 화면에 웹 VS Code(code-server) 작업창을 렌더링합니다.

    Args:
        height: iframe 높이 (픽셀 단위)
    """
    ensure_workspace_initialized()

    st.markdown("#### 💻 전문 파이썬 개발 작업 공간 (VS Code)")
    st.caption(
        "로컬 작업 영역(`data/code_workspace/`)과 실시간 동기화되는 웹 IDE 환경입니다. "
        "알고리즘 모듈을 직접 코딩하거나 테스트할 수 있습니다."
    )

    vscode_url = generate_vscode_embed_url()

    col1, col2 = st.columns([3, 1])
    with col1:
        st.info(f"🔗 현재 연결 대상 IDE 주소: `{vscode_url}`")
    with col2:
        use_fallback_editor = st.toggle("로컬 간이 텍스트 에디터 모드", value=False)

    if not use_fallback_editor:
        # code-server iframe 임베딩
        try:
            components.iframe(
                src=vscode_url,
                height=height,
                scrolling=True,
            )
        except Exception as e:
            st.error(f"code-server 임베딩 로드 중 오류 발생: {str(e)}")
            st.warning("code-server 컨테이너가 실행 중인지 확인하세요. 상단의 간이 에디터 모드로 전환할 수 있습니다.")
    else:
        # code-server 비활성 환경을 위한 Streamlit 네이티브 텍스트 에디터 폴백
        target_file = os.path.join(WORKSPACE_DIR, "vibe_runner.py")
        current_content = ""
        if os.path.exists(target_file):
            with open(target_file, "r", encoding="utf-8") as f:
                current_content = f.read()

        edited_code = st.text_area(
            label="[vibe_runner.py] 직접 편집",
            value=current_content,
            height=480,
        )

        if st.button("💾 vibe_runner.py 저장", use_container_width=True):
            with open(target_file, "w", encoding="utf-8") as f:
                f.write(edited_code)
            st.success("작업 공간 파일에 성공적으로 저장되었습니다.")