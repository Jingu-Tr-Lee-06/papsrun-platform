"""학급 캠퍼스 도로망 간선(Edges) 및 노드(Nodes) CRUD 저장소 모듈.

Cloud Firestore가 활성화되어 있으면 클라우드 컬렉션과 실시간 동기화하고,
오프라인 또는 API 키 미설정 시 data/cache/ 로컬 JSON 캐시 매니저와 연동합니다.
"""

from typing import Any, Dict, List, Optional
import time

from src.db.firebase_client import get_firestore_client, is_firestore_available
from src.db.local_cache_manager import (
    add_edge_to_cache,
    clear_cached_edges,
    delete_edge_from_cache,
    load_class_edges_from_cache,
)


def _generate_edge_id(u: str, v: str) -> str:
    """간선 양 끝 노드 식별자를 조합하여 고유 간선 키를 생성합니다."""
    return f"{u}__{v}"


def save_single_edge(class_code: str, edge_data: Dict[str, Any]) -> tuple[bool, str]:
    """단일 도로 간선 정보를 저장(추가 또는 갱신)합니다.

    Args:
        class_code: 학급 식별 코드
        edge_data: 노드 u, v, 좌표, 길이, 노면, 그늘, 경사도 등 메타데이터

    Returns:
        (성공 여부 bool, 메시지 str)
    """
    u = str(edge_data.get("u", ""))
    v = str(edge_data.get("v", ""))
    if not u or not v:
        return False, "시작 노드(u) 또는 종료 노드(v)가 유효하지 않습니다."

    edge_id = edge_data.get("edge_id") or _generate_edge_id(u, v)
    edge_data["edge_id"] = edge_id
    edge_data["updated_at"] = time.time()

    # 1. Cloud Firestore 저장 시도
    if is_firestore_available():
        db = get_firestore_client()
        if db:
            try:
                doc_ref = (
                    db.collection("classes")
                    .document(class_code)
                    .collection("roads")
                    .document(edge_id)
                )
                doc_ref.set(edge_data, merge=True)
                # 로컬 캐시에도 백업 복사
                add_edge_to_cache(class_code, edge_data)
                return True, f"간선 '{edge_id}' 저장 완료 (Cloud Firestore)"
            except Exception as e:
                pass  # Firestore 실패 시 아래 로컬 캐시로 폴백

    # 2. 로컬 JSON 캐시 폴백 저장
    ok = add_edge_to_cache(class_code, edge_data)
    if ok:
        return True, f"간선 '{edge_id}' 저장 완료 (로컬 캐시)"
    return False, "로컬 캐시 파일 저장에 실패했습니다."


def get_all_edges(class_code: str) -> List[Dict[str, Any]]:
    """학급에 등록된 모든 도로 간선 데이터를 조회합니다.

    Args:
        class_code: 학급 식별 코드

    Returns:
        간선 속성 딕셔너리 리스트
    """
    if is_firestore_available():
        db = get_firestore_client()
        if db:
            try:
                roads_ref = (
                    db.collection("classes")
                    .document(class_code)
                    .collection("roads")
                )
                docs = roads_ref.stream()
                edges = [doc.to_dict() for doc in docs]
                if edges:
                    return edges
            except Exception:
                pass

    # 로컬 캐시 폴백 반환
    return load_class_edges_from_cache(class_code)


def delete_single_edge(class_code: str, edge_id: str) -> bool:
    """특정 간선을 데이터베이스 및 캐시에서 제거합니다.

    Args:
        class_code: 학급 식별 코드
        edge_id: 삭제할 간선 고유 식별자

    Returns:
        삭제 성공 여부
    """
    if is_firestore_available():
        db = get_firestore_client()
        if db:
            try:
                db.collection("classes").document(class_code).collection("roads").document(edge_id).delete()
            except Exception:
                pass

    return delete_edge_from_cache(class_code, edge_id)


def clear_all_edges_in_class(class_code: str) -> bool:
    """수업 초기화 시 해당 학급의 모든 도로 간선 데이터를 삭제합니다.

    Args:
        class_code: 학급 식별 코드

    Returns:
        초기화 성공 여부
    """
    if is_firestore_available():
        db = get_firestore_client()
        if db:
            try:
                roads_ref = (
                    db.collection("classes")
                    .document(class_code)
                    .collection("roads")
                )
                docs = roads_ref.limit(500).stream()
                for doc in docs:
                    doc.reference.delete()
            except Exception:
                pass

    return clear_cached_edges(class_code)