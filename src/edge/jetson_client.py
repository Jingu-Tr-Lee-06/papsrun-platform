"""NVIDIA 젯슨 나노(Jetson Nano) 연동 REST 통신 클라이언트 모듈.

다익스트라 알고리즘으로 최적화된 경로 노드 시퀀스 및 웨이포인트 환경 데이터를
젯슨 보드로 안전하게 패킷화하여 전송하고, 보드의 실시간 응답 상태를 관리합니다.
실제 하드웨어가 연결되지 않은 실습 환경에서는 로컬 에뮬레이터로 자동 전환됩니다.
"""

from typing import Any, Dict, List, Optional
import json
import time
import requests
import streamlit as st

from src.edge.hardware_emulator import (
    simulate_jetson_metrics,
    simulate_path_execution,
)


class JetsonClient:
    """젯슨 나노 하드웨어 REST 통신 제어 클라이언트."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        timeout: float = 2.0,
    ) -> None:
        """클라이언트 접속 설정을 초기화합니다."""
        jetson_secrets = st.secrets.get("jetson", {})
        self.host = host or jetson_secrets.get("host", "192.168.0.100")
        self.port = port or int(jetson_secrets.get("port", 8000))
        self.timeout = timeout
        self.base_url = f"http://{self.host}:{self.port}"
        self.is_connected = False
        self._check_initial_connection()

    def _check_initial_connection(self) -> None:
        """초기 인스턴스화 시 젯슨 보드의 온라인 여부를 확인합니다."""
        try:
            res = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            self.is_connected = res.status_code == 200
        except Exception:
            self.is_connected = False

    def ping(self) -> bool:
        """젯슨 보드로 헬스체크 핑을 송신하여 연결 상태를 갱신합니다."""
        try:
            res = requests.get(f"{self.base_url}/api/health", timeout=self.timeout)
            self.is_connected = res.status_code == 200
        except Exception:
            self.is_connected = False
        return self.is_connected

    def send_optimized_path(
        self,
        session_id: str,
        path_nodes: List[str],
        waypoints: List[Dict[str, Any]],
        evaluation_metrics: Dict[str, Any],
    ) -> Dict[str, Any]:
        """최적화된 경로 데이터 및 웨이포인트 속성을 젯슨 보드로 전송합니다.

        Args:
            session_id: 고유 주행 세션 ID
            path_nodes: 노드 식별자 순차 리스트
            waypoints: 각 노드별 위경도 및 노면 환경 메타데이터
            evaluation_metrics: 심박수, 칼로리, Rn 평가 지표

        Returns:
            보드 처리 응답 결과 딕셔너리
        """
        payload = {
            "session_id": session_id,
            "timestamp": time.time(),
            "node_count": len(path_nodes),
            "nodes": path_nodes,
            "waypoints": waypoints,
            "metrics": evaluation_metrics,
        }

        # 1. 실제 하드웨어가 연결된 경우 HTTP POST 전송
        if self.is_connected:
            try:
                res = requests.post(
                    f"{self.base_url}/api/path/dispatch",
                    json=payload,
                    timeout=self.timeout * 2,
                )
                if res.status_code == 200:
                    return res.json()
            except Exception as e:
                self.is_connected = False

        # 2. 하드웨어 미연결 또는 통신 실패 시 로컬 에뮬레이션 백엔드로 처리
        return simulate_path_execution(payload)

    def get_telemetry(self) -> Dict[str, Any]:
        """젯슨 보드의 하드웨어 텔레메트리(온도, 자원 점유율)를 조회합니다."""
        if self.is_connected:
            try:
                res = requests.get(f"{self.base_url}/api/telemetry", timeout=self.timeout)
                if res.status_code == 200:
                    return res.json()
            except Exception:
                self.is_connected = False

        # 에뮬레이션 데이터 반환
        return simulate_jetson_metrics()


def get_jetson_client() -> JetsonClient:
    """Streamlit 세션 컨텍스트 내에서 유지되는 단일 젯슨 클라이언트를 반환합니다."""
    if "jetson_client_instance" not in st.session_state:
        st.session_state["jetson_client_instance"] = JetsonClient()
    return st.session_state["jetson_client_instance"]