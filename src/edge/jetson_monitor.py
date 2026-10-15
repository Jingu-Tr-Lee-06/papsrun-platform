"""NVIDIA 젯슨 나노 하드웨어 리소스 및 텔레메트리 모니터링 모듈.

CPU 사용률, Maxwell GPU 로드율, 온보드 메모리 점유량, thermal 센서 온도,
소비 전력(mW) 등의 텔레메트리 데이터를 수집하고 이상 징후(과열, 메모리 부족)를 진단합니다.
"""

from dataclasses import dataclass
from typing import Any, Dict, Optional
import time

from src.edge.jetson_client import JetsonClient, get_jetson_client


@dataclass
class JetsonMetrics:
    """젯슨 나노 시스템 텔레메트리 상태 데이터 모델."""

    cpu_usage_pct: float         # 4코어 ARM CPU 평균 사용률 (%)
    gpu_usage_pct: float         # 128코어 NVIDIA Maxwell GPU 점유율 (%)
    ram_used_mb: float           # 사용 중인 RAM 용량 (MB)
    ram_total_mb: float          # 전체 RAM 용량 (MB, 대개 4096MB)
    temperature_c: float         # SoC 접합부(Junction) 온도 (°C)
    power_mw: float              # 실시간 추정 전력 소모량 (mW)
    is_throttling: bool          # 열 스로틀링 발생 여부
    timestamp: float             # 측정 시각 에포크 타임스탬프

    @property
    def ram_usage_pct(self) -> float:
        """RAM 사용률 백분율을 계산합니다."""
        if self.ram_total_mb <= 0:
            return 0.0
        return (self.ram_used_mb / self.ram_total_mb) * 100.0


def parse_telemetry_dict(data: Dict[str, Any]) -> JetsonMetrics:
    """원시 딕셔너리 데이터를 구조화된 JetsonMetrics 객체로 변환합니다.

    Args:
        data: 젯슨 보드 또는 에뮬레이터에서 반환된 원시 딕셔너리

    Returns:
        JetsonMetrics 데이터클래스 인스턴스
    """
    temp_c = float(data.get("temperature_c", 42.0))
    is_throttling = data.get("is_throttling", temp_c >= 75.0)

    return JetsonMetrics(
        cpu_usage_pct=float(data.get("cpu_usage_pct", 15.0)),
        gpu_usage_pct=float(data.get("gpu_usage_pct", 5.0)),
        ram_used_mb=float(data.get("ram_used_mb", 1250.0)),
        ram_total_mb=float(data.get("ram_total_mb", 4096.0)),
        temperature_c=temp_c,
        power_mw=float(data.get("power_mw", 2800.0)),
        is_throttling=is_throttling,
        timestamp=float(data.get("timestamp", time.time())),
    )


def fetch_system_telemetry(client: Optional[JetsonClient] = None) -> JetsonMetrics:
    """활성 젯슨 클라이언트를 통해 최신 시스템 리소스 지표를 조회합니다.

    Args:
        client: 젯슨 통신 클라이언트 (None일 경우 세션 기본 클라이언트 참조)

    Returns:
        JetsonMetrics 지표 객체
    """
    target_client = client or get_jetson_client()
    raw_telemetry = target_client.get_telemetry()
    return parse_telemetry_dict(raw_telemetry)


def diagnose_hardware_health(metrics: JetsonMetrics) -> Dict[str, Any]:
    """수집된 텔레메트리 지표를 기반으로 하드웨어 상태를 판정합니다.

    Args:
        metrics: JetsonMetrics 인스턴스

    Returns:
        {"status": "정상" | "주의" | "위험", "message": str} 딕셔너리
    """
    if metrics.is_throttling or metrics.temperature_c >= 80.0:
        return {
            "status": "위험",
            "message": f"SoC 코어 온도가 위험 수준({metrics.temperature_c:.1f}°C)입니다. 쿨링 팬 확인이 필요합니다.",
        }

    if metrics.temperature_c >= 68.0:
        return {
            "status": "주의",
            "message": f"발열 증가 중({metrics.temperature_c:.1f}°C). 고부하 알고리즘 지속 시 스로틀링 발생 가능.",
        }

    if metrics.ram_usage_pct >= 90.0:
        return {
            "status": "주의",
            "message": f"RAM 가용량 한계 도달({metrics.ram_used_mb:.0f}/{metrics.ram_total_mb:.0f} MB). 메모리 누수를 점검하세요.",
        }

    return {
        "status": "정상",
        "message": f"하드웨어 동작 상태 양호 ({metrics.temperature_c:.1f}°C, GPU {metrics.gpu_usage_pct:.0f}% 부하)",
    }