"""PAPSrun 데이터베이스 및 세션 영속성 계층 패키지.

Firebase Firestore 연동 클라이언트, 도로망 CRUD 리포지토리,
학급 세션 및 잠금 관리자, 오프라인 로컬 캐시 관리자를 노출합니다.
"""

from src.db.class_session_manager import (
    get_class_session_config,
    is_class_locked,
    set_class_locked_state,
    update_class_session_config,
)
from src.db.firebase_client import (
    get_firestore_client,
    is_firebase_available,
    is_firestore_available,
)
from src.db.local_cache_manager import (
    clear_local_cache,
    load_json_cache,
    save_json_cache,
)
from src.db.road_repository import (
    clear_all_edges_in_class,
    delete_single_edge,
    get_all_edges,
    save_single_edge,
)

__all__ = [
    # Firebase 클라이언트
    "get_firestore_client",
    "is_firestore_available",
    "is_firebase_available",
    # 도로망 데이터 CRUD
    "save_single_edge",
    "get_all_edges",
    "delete_single_edge",
    "clear_all_edges_in_class",
    # 학급 세션 및 제어
    "get_class_session_config",
    "update_class_session_config",
    "set_class_locked_state",
    "is_class_locked",
    # 로컬 캐시 관리
    "save_json_cache",
    "load_json_cache",
    "clear_local_cache",
]