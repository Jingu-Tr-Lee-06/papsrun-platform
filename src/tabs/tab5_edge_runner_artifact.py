"""[5단계 UI] 엣지 구동 및 최종 PAPS 산출물 리포트 화면 컨트롤러 모듈.

최적화된 경로 노드 시퀀스와 환경 데이터를 엣지 보드(NVIDIA Jetson Nano)로 디스패치하고,
하드웨어 텔레메트리(CPU, GPU, 온도) 모니터링 및 최종 PAPS 러닝 코스 설계 리포트를 생성·배포합니다.
"""

from typing import Any, Dict, List, Optional
import json
import time
import streamlit as st

from src.edge.jetson_client import get_jetson_client
from src.edge.jetson_monitor import diagnose_hardware_health, fetch_system_telemetry


def render_tab5_edge_runner_artifact(class_code: str, team_id: str) -> None:
    """5단계 엣지 구동 및 산출물 배포 화면을 렌더링합니다.

    Args:
        class_code: 현재 접속한 학급 코드
        team_id: 현재 로그인한 모둠 식별자
    """
    st.markdown("### 🚀 5단계: 엣지 디바이스 구동 및 PAPS 최종 산출물")
    st.caption(
        "도출된 맞춤형 경로를 엣지 코어(NVIDIA Jetson Nano)로 전송하여 실시간 주행 데이터를 시뮬레이션하고, "
        "체육-정보 융합 산출물(PAPS 코스 리포트)을 완성합니다."
    )

    # 3단계에서 계산된 경로 세션 데이터 조회
    paths_data = st.session_state.get("latest_paths", {})
    vibe_data = paths_data.get("vibe", {})
    path_nodes = vibe_data.get("nodes") or []
    eval_metrics = vibe_data.get("eval") or {}

    col_edge, col_report = st.columns([1, 1])

    with col_edge:
        st.markdown("##### ⚡ 엣지 컴퓨팅(Jetson Nano) 연동 제어")
        client = get_jetson_client()
        is_online = client.ping()

        status_text = "🟢 온라인 (하드웨어 연결)" if is_online else "🟡 로컬 가상 에뮬레이터 모드"
        st.write(f"**디바이스 연결 상태:** `{status_text}`")

        # 텔레메트리 조회
        metrics = fetch_system_telemetry(client)
        diag = diagnose_hardware_health(metrics)

        m_col1, m_col2, m_col3 = st.columns(3)
        with m_col1:
            st.metric(label="GPU 부하율", value=f"{metrics.gpu_usage_pct:.1f}%")
        with m_col2:
            st.metric(label="CPU 점유율", value=f"{metrics.cpu_usage_pct:.1f}%")
        with m_col3:
            st.metric(label="SoC 접합 온도", value=f"{metrics.temperature_c:.1f}°C")

        st.caption(f"**하드웨어 진단:** {diag['message']}")

        st.divider()

        if not path_nodes:
            st.warning("3단계에서 최적화 경로 탐색을 먼저 완료해야 엣지 보드로 전송할 수 있습니다.")
            dispatch_disabled = True
        else:
            st.success(f"전송 준비 완료: {len(path_nodes)}개 노드 경로 시퀀스")
            dispatch_disabled = False

        if st.button("📡 엣지 코어로 경로 디스패치 (Dispatch)", disabled=dispatch_disabled, use_container_width=True):
            with st.spinner("웨이포인트 패킷 변환 및 엣지 스트림 전송 중..."):
                waypoints = [{"node_id": nid} for nid in path_nodes]
                session_id = f"{class_code}_{team_id}_{int(time.time())}"
                response = client.send_optimized_path(
                    session_id=session_id,
                    path_nodes=path_nodes,
                    waypoints=waypoints,
                    evaluation_metrics=eval_metrics,
                )
                st.session_state["edge_last_dispatch"] = response
                st.success("엣지 보드 주행 패킷 디스패치 완료!")

        dispatch_res = st.session_state.get("edge_last_dispatch")
        if dispatch_res:
            with st.expander("🔍 엣지 디스패치 응답 패킷 원문 확인", expanded=True):
                st.json(dispatch_res)

    with col_report:
        st.markdown("##### 📄 PAPS 융합 러닝 코스 산출물 리포트")

        if not path_nodes or not eval_metrics:
            st.info("경로 탐색 결과가 생성되면 정량 분석 리포트가 자동으로 작성됩니다.")
            return

        total_dist = eval_metrics.get("total_distance_m", 0.0)
        elev_gain = eval_metrics.get("elevation_gain_m", 0.0)
        est_bpm = eval_metrics.get("estimated_avg_bpm", 0)
        calories = eval_metrics.get("calories_burned_kcal", 0.0)
        shaded_pct = eval_metrics.get("shaded_ratio_pct", 0.0)

        markdown_report = (
            f"# PAPS 맞춤형 스마트 러닝 코스 설계 보고서\n\n"
            f"- **학급 코드:** {class_code}\n"
            f"- **모둠명:** {team_id}\n"
            f"- **경로 노드 시퀀스:** {' ➔ '.join(path_nodes)}\n\n"
            f"## 1. 정량 생체역학 및 환경 지표\n"
            f"- **총 연장 거리:** {total_dist:.1f} m\n"
            f"- **누적 획득 고도:** {elev_gain:.1f} m\n"
            f"- **추정 소모 열량:** {calories:.1f} kcal\n"
            f"- **목표 심박수:** {est_bpm} BPM (PAPS 심폐지구력 구간)\n"
            f"- **그늘 차광 비율:** {shaded_pct:.1f} %\n\n"
            f"## 2. 알고리즘 설계 의도\n"
            f"지형 경사도와 노면 마찰계수(우레탄, 흙길 등) 및 태양 순복사에너지(Rn)를 고려하여 "
            f"관절 충격을 최소화하고 열 스트레스를 경감하도록 가중치 함수를 최적화함.\n"
        )

        st.text_area(label="생성된 리포트 마크다운", value=markdown_report, height=280)

        # 다운로드 버튼
        dl_col1, dl_col2 = st.columns(2)
        with dl_col1:
            st.download_button(
                label="📥 Markdown 리포트 다운로드",
                data=markdown_report,
                file_name=f"PAPSrun_Report_{team_id}.md",
                mime="text/markdown",
                use_container_width=True,
            )
        with dl_col2:
            json_export = json.dumps({
                "class_code": class_code,
                "team_id": team_id,
                "path_nodes": path_nodes,
                "metrics": eval_metrics,
                "edge_dispatch": dispatch_res,
            }, ensure_ascii=False, indent=2)
            st.download_button(
                label="📥 JSON 경로 데이터 내보내기",
                data=json_export,
                file_name=f"PAPSrun_Artifact_{team_id}.json",
                mime="application/json",
                use_container_width=True,
            )