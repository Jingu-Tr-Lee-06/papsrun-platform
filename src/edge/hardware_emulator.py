"""NVIDIA 젯슨 나노 로컬 하드웨어 가상 에뮬레이터 모듈.

실제 보드가 연결되지 않은 교육 환경에서도 다익스트라 가중치 연산 부하에 따른
GPU 로드, 온보드 메모리 점유, SoC 온도 변화를 사실적으로 모의 시뮬레이션하고,
전송된 최적 경로에 대한 가상 주행 패킷 처리 응답을 생성합니다.
"""

from dataclasses import dataclass
import math
import random
import time
from typing import Any, Dict, List


@dataclass
class EmulatedJetsonStatus:
    """에뮬레이터 내부 상태 모델."""

    is_running: bool = True
    base_temp_c: float = 43.5
    accumulated_packets: int = 0
    last_dispatched_session: str = ""


_EMULATOR_STATE = EmulatedJetsonStatus()


def simulate_jetson_metrics() -> Dict[str, Any]:
    """젯슨 나노의 CPU, Maxwell GPU, 메모리, 열 센서 텔레메트리를 모의 생성합니다.

    Returns:
        JetsonMetrics 파싱에 적합한 딕셔너리
    """
    now = time.time()
    # 시간 경과에 따른 미세 진동 부여 (노이즈)
    noise = math.sin(now / 5.0) * 2.0 + random.uniform(-0.5, 0.5)

    cpu_usage = min(95.0, max(8.0, 18.0 + noise * 3.0))
    gpu_usage = min(98.0, max(2.0, 12.0 + noise * 4.0))
    
    # 패킷 처리 누적치에 따른 점진적 온도 상승 모의
    thermal_load = min(15.0, _EMULATOR_STATE.accumulated_packets * 0.4)
    temperature = _EMULATOR_STATE.base_temp_c + thermal_load + noise

    ram_used = min(3900.0, max(800.0, 1420.0 + noise * 50.0))
    power = 2400.0 + (cpu_usage * 15.0) + (gpu_usage * 25.0)

    return {
        "cpu_usage_pct": round(cpu_usage, 1),
        "gpu_usage_pct": round(gpu_usage, 1),
        "ram_used_mb": round(ram_used, 1),
        "ram_total_mb": 4096.0,
        "temperature_c": round(temperature, 1),
        "power_mw": round(power, 1),
        "is_throttling": temperature >= 75.0,
        "timestamp": now,
        "mode": "EMULATED_JETSON_NANO",
    }


def simulate_path_execution(payload: Dict[str, Any]) -> Dict[str, Any]:
    """젯슨 보드가 최적화된 경로 패킷을 수신하여 자율 주행/웨이포인트 연산을 수행한 결과를 모의합니다.

    Args:
        payload: send_optimized_path()로부터 전달된 경로 데이터 패킷

    Returns:
        가상 실행 응답 딕셔너리
    """
    session_id = payload.get("session_id", "UNKNOWN_SESSION")
    node_count = payload.get("node_count", 0)
    waypoints: List[Dict[str, Any]] = payload.get("waypoints", [])

    _EMULATOR_STATE.accumulated_packets += 1
    _EMULATOR_STATE.last_dispatched_session = session_id

    # 가상 연산 지연 시뮬레이션 (밀리초 단위 계산)
    simulated_inference_latency_ms = round(12.5 + (node_count * 1.8) + random.uniform(0.5, 3.0), 2)

    return {
        "status": "SUCCESS",
        "device": "JETSON_NANO_VIRTUAL_BACKEND",
        "session_id": session_id,
        "received_nodes": node_count,
        "latency_ms": simulated_inference_latency_ms,
        "message": f"{node_count}개 웨이포인트 경로 주행 패킷이 가상 엣지 코어로 성공적으로 디스패치되었습니다.",
        "edge_metrics": {
            "allocated_cuda_streams": 2,
            "tensorrt_ready": True,
            "target_waypoint_eta_sec": round(node_count * 22.5, 1),
        },
        "processed_at": time.time(),
    }