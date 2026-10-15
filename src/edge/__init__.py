"""PAPSrun 엣지 컴퓨팅 및 젯슨 나노(Jetson Nano) 연동 패키지.

젯슨 나노 REST/소켓 통신 클라이언트, GPU/CPU/온도 모니터링 모듈,
그리고 실제 하드웨어 미연결 환경을 지원하는 로컬 에뮬레이터를 제공합니다.
"""

from src.edge.hardware_emulator import (
    EmulatedJetsonStatus,
    simulate_jetson_metrics,
    simulate_path_execution,
)
from src.edge.jetson_client import (
    JetsonClient,
    get_jetson_client,
)
from src.edge.jetson_monitor import (
    JetsonMetrics,
    fetch_system_telemetry,
)

__all__ = [
    # 클라이언트 인터페이스
    "JetsonClient",
    "get_jetson_client",
    # 텔레메트리 모니터링
    "JetsonMetrics",
    "fetch_system_telemetry",
    # 하드웨어 에뮬레이터
    "EmulatedJetsonStatus",
    "simulate_jetson_metrics",
    "simulate_path_execution",
]