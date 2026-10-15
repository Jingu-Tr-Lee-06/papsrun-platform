"""PAPSrun 오프라인 로컬 JSON 캐시 관리 모듈.

Firestore 미연결 또는 오프라인 환경에서 학급별 도로 데이터 및 세션 상태를
data/cache/ 디렉터리 하위의 JSON 파일로 안전하게 직렬화, 역직렬화, 초기화하며,
road_repository에서 요구하는 간선 단위 CRUD 헬퍼 함수들을 완벽히 매핑하여 제공합니다.
"""

from typing import Any, Dict, List, Optional
import json
import os

CACHE_DIR = os.path.join("data", "cache")


def ensure_cache_directory() -> None:
    """캐시 디렉터리가 없으면 생성합니다."""
    os.makedirs(CACHE_DIR, exist_ok=True)


def _get_cache_file_path(cache_key: str) -> str:
    """캐시 키에 매핑되는 파일 경로를 반환합니다."""
    ensure_cache_directory()
    safe_key = "".join(c for c in cache_key if c.isalnum() or c in ("_", "-"))
    return os.path.join(CACHE_DIR, f"{safe_key}.json")


def save_json_cache(cache_key: str, data: Any) -> bool:
    """데이터를 로컬 JSON 파일로 안전하게 저장합니다.

    Args:
        cache_key: 파일명으로 사용할 고유 식별 키 (예: class_code_roads)
        data: JSON 직렬화 가능한 딕셔너리 또는 리스트

    Returns:
        저장 성공 여부 (bool)
    """
    file_path = _get_cache_file_path(cache_key)
    temp_path = f"{file_path}.tmp"

    try:
        with open(temp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        # 원자적 파일 교체 (Atomic write)
        if os.path.exists(file_path):
            os.remove(file_path)
        os.rename(temp_path, file_path)
        return True
    except Exception:
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except OSError:
                pass
        return False


def load_json_cache(cache_key: str, default_value: Optional[Any] = None) -> Any:
    """로컬 JSON 파일에서 데이터를 읽어옵니다.

    Args:
        cache_key: 캐시 식별 키
        default_value: 파일이 없거나 읽기 실패 시 반환할 기본값

    Returns:
        역직렬화된 Python 객체 또는 default_value
    """
    file_path = _get_cache_file_path(cache_key)

    if not os.path.exists(file_path):
        return default_value if default_value is not None else []

    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default_value if default_value is not None else []


def clear_local_cache(cache_key: Optional[str] = None) -> bool:
    """특정 캐시 키의 파일 또는 data/cache 전체 캐시를 삭제합니다.

    Args:
        cache_key: 삭제할 캐시 키. None일 경우 data/cache 폴더 내 모든 json 파일 삭제.

    Returns:
        삭제 완료 여부 (bool)
    """
    ensure_cache_directory()

    try:
        if cache_key:
            file_path = _get_cache_file_path(cache_key)
            if os.path.exists(file_path):
                os.remove(file_path)
        else:
            for fname in os.listdir(CACHE_DIR):
                if fname.endswith(".json"):
                    os.remove(os.path.join(CACHE_DIR, fname))
        return True
    except Exception:
        return False


# ============================================================
# road_repository 전용 간선(Edge) 캐시 헬퍼 함수
# ============================================================

def load_class_edges_from_cache(class_code: str) -> List[Dict[str, Any]]:
    """학급에 저장된 도로 간선 리스트를 로컬 캐시에서 조회합니다."""
    cache_key = f"{class_code}_roads"
    data = load_json_cache(cache_key, default_value=[])
    return data if isinstance(data, list) else []


# 별칭: get_cached_edges
get_cached_edges = load_class_edges_from_cache


def save_class_edges_to_cache(class_code: str, edges: List[Dict[str, Any]]) -> bool:
    """학급 전체 도로 간선 리스트를 캐시에 덮어씁니다."""
    cache_key = f"{class_code}_roads"
    return save_json_cache(cache_key, edges)


def add_edge_to_cache(class_code: str, edge_data: Dict[str, Any]) -> bool:
    """단일 도로 간선을 로컬 캐시에 추가하거나 업데이트합니다."""
    cache_key = f"{class_code}_roads"
    edges = load_class_edges_from_cache(class_code)

    edge_id = edge_data.get("edge_id")
    updated = False
    for i, e in enumerate(edges):
        if e.get("edge_id") == edge_id:
            edges[i] = edge_data
            updated = True
            break
    if not updated:
        edges.append(edge_data)

    return save_json_cache(cache_key, edges)


def delete_edge_from_cache(class_code: str, edge_id: str) -> bool:
    """특정 간선 식별자를 갖는 도로 데이터를 로컬 캐시에서 제거합니다."""
    cache_key = f"{class_code}_roads"
    edges = load_class_edges_from_cache(class_code)
    filtered = [e for e in edges if e.get("edge_id") != edge_id]
    return save_json_cache(cache_key, filtered)


# 별칭: remove_edge_from_cache
remove_edge_from_cache = delete_edge_from_cache


def clear_cached_edges(class_code: str) -> bool:
    """해당 학급의 도로 간선 캐시 파일을 비웁니다."""
    cache_key = f"{class_code}_roads"
    return save_json_cache(cache_key, [])