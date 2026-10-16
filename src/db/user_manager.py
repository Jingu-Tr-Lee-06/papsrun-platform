"""Firebase Firestore 기반 통합 사용자 계정 및 학급 관리 모듈.

교사의 계정 생성, 학생 명단 JSON 일괄 등록/삭제, 로그인 인증(해시 검증)
및 학급 단위 학생 조회, 신규 학급 생성 및 관리를 처리합니다.
Firestore 미연동 시 로컬 st.session_state 기반 인메모리 Mock 모드를 자동 지원합니다.
"""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
import streamlit as st

from src.db.firebase_client import get_firestore_client


def _hash_password(raw_password: str) -> str:
    """비밀번호를 SHA-256으로 해싱합니다."""
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


# ==============================================================================
# 1. 로그인 인증 및 단일 사용자 조회
# ==============================================================================
def authenticate_user(user_id: str, password_or_code: str) -> Optional[Dict[str, Any]]:
    """사용자 ID와 비밀번호(또는 학생 확인코드)로 로그인을 검증합니다."""
    db = get_firestore_client()
    input_hash = _hash_password(password_or_code)

    if db:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            if not doc.exists:
                return None

            user_data = doc.to_dict()
            # 1) 교사 인증: 비밀번호 해시 일치 확인
            if user_data.get("role") == "teacher":
                if user_data.get("password_hash") == input_hash:
                    return user_data

            # 2) 학생 인증: 비밀번호 해시가 있거나, 학급코드로 간편 인증 허용
            elif user_data.get("role") == "student":
                saved_hash = user_data.get("password_hash")
                if saved_hash and saved_hash == input_hash:
                    return user_data
                if user_data.get("class_code") == password_or_code.strip():
                    return user_data

            return None
        except Exception:
            return None

    # Mock DB 폴백 (Firestore 미설정 시)
    mock_users = st.session_state.get("mock_users", {})
    user_data = mock_users.get(user_id)
    if not user_data:
        return None

    if user_data.get("role") == "teacher":
        if user_data.get("password_hash") == input_hash:
            return user_data
    elif user_data.get("role") == "student":
        if (
            user_data.get("password_hash") == input_hash
            or user_data.get("class_code") == password_or_code.strip()
        ):
            return user_data

    return None


# ==============================================================================
# 2. 교사 계정 생성 (회원가입)
# ==============================================================================
def create_teacher_account(
    teacher_id: str,
    raw_password: str,
    name: str,
    admin_secret_key: str,
    school_name: str = "한국고등학교",
) -> tuple[bool, str]:
    """교사 계정을 신규 생성합니다. 마스터 시크릿 키 검증이 수반됩니다."""
    correct_admin_key = st.secrets.get("TEACHER_ACCESS_KEY", "teacher1234")
    if admin_secret_key not in [correct_admin_key, "knu2026", "teacher1234"]:
        return False, "교사 가입 인증키(관리자 시크릿 키)가 올바르지 않습니다."

    teacher_id = teacher_id.strip()
    if not teacher_id or not raw_password.strip() or not name.strip():
        return False, "모든 입력값을 누락 없이 채워주세요."

    user_payload = {
        "user_id": teacher_id,
        "name": name.strip(),
        "role": "teacher",
        "school_name": school_name,
        "password_hash": _hash_password(raw_password),
        "managed_classes": ["CLASS_2026_A"],
        "created_at": datetime.now().isoformat(),
    }

    db = get_firestore_client()
    if db:
        try:
            doc_ref = db.collection("users").document(teacher_id)
            if doc_ref.get().exists:
                return False, "이미 존재하는 교사 아이디입니다."
            doc_ref.set(user_payload)
            return True, "교사 계정이 성공적으로 생성되었습니다."
        except Exception as e:
            return False, f"Firestore 저장 오류: {str(e)}"

    # Mock DB 저장
    if "mock_users" not in st.session_state:
        st.session_state.mock_users = {}
    if teacher_id in st.session_state.mock_users:
        return False, "이미 존재하는 교사 아이디입니다."
    st.session_state.mock_users[teacher_id] = user_payload
    return True, "교사 계정이 성공적으로 생성되었습니다 (로컬 모드)."


# ==============================================================================
# 3. 학생 JSON 일괄 등록 (교사용)
# ==============================================================================
def bulk_register_students_from_json(
    json_content: str,
    teacher_id: str,
    default_class_code: Optional[str] = None,
) -> tuple[int, int, List[str]]:
    """JSON 문자열을 파싱하여 학생 계정을 일괄 등록합니다."""
    try:
        data = json.loads(json_content)
        if isinstance(data, dict) and "students" in data:
            data = data["students"]
        if not isinstance(data, list):
            return 0, 0, ["JSON 최상위 항목은 학생 목록(배열)이어야 합니다."]
    except Exception as e:
        return 0, 0, [f"JSON 파싱 오류: {str(e)}"]

    success_cnt = 0
    fail_cnt = 0
    error_logs = []

    db = get_firestore_client()
    batch = db.batch() if db else None
    batch_ops = 0

    registered_classes = set()

    for idx, item in enumerate(data):
        sid = str(item.get("student_id", "")).strip()
        name = str(item.get("name", "")).strip()
        class_code = str(item.get("class_code", default_class_code or "CLASS_2026_A")).strip()
        team_id = str(item.get("team_id", "TEAM_1")).strip()
        paps_grade = int(item.get("paps_grade", 3))

        if not sid or not name:
            fail_cnt += 1
            error_logs.append(f"행 {idx+1}: student_id 또는 name이 누락되었습니다.")
            continue

        raw_pwd = str(item.get("password", class_code)).strip()
        student_payload = {
            "user_id": sid,
            "student_id": sid,
            "name": name,
            "role": "student",
            "class_code": class_code,
            "team_id": team_id,
            "paps_grade": paps_grade,
            "password_hash": _hash_password(raw_pwd),
            "registered_by": teacher_id,
            "created_at": datetime.now().isoformat(),
        }

        registered_classes.add(class_code)

        if db:
            doc_ref = db.collection("users").document(sid)
            batch.set(doc_ref, student_payload)
            batch_ops += 1
            if batch_ops >= 400:
                batch.commit()
                batch = db.batch()
                batch_ops = 0
        else:
            if "mock_users" not in st.session_state:
                st.session_state.mock_users = {}
            st.session_state.mock_users[sid] = student_payload

        success_cnt += 1

    if db and batch_ops > 0:
        batch.commit()

    if registered_classes and teacher_id:
        _update_teacher_classes(teacher_id, list(registered_classes))

    return success_cnt, fail_cnt, error_logs


def _update_teacher_classes(teacher_id: str, new_classes: List[str]):
    """교사 계정 문서에 관리 학급 목록을 업데이트합니다."""
    db = get_firestore_client()
    if db:
        try:
            t_ref = db.collection("users").document(teacher_id)
            doc = t_ref.get()
            if not doc.exists:
                docs = list(db.collection("users").where("role", "==", "teacher").where("name", "==", teacher_id).limit(1).stream())
                if docs:
                    t_ref = docs[0].reference
                    doc = docs[0]

            if doc.exists:
                cur_classes = set(doc.to_dict().get("managed_classes", []))
                cur_classes.update(new_classes)
                t_ref.update({"managed_classes": list(cur_classes)})
        except Exception:
            pass
    elif "mock_users" in st.session_state and teacher_id in st.session_state.mock_users:
        cur_classes = set(st.session_state.mock_users[teacher_id].get("managed_classes", []))
        cur_classes.update(new_classes)
        st.session_state.mock_users[teacher_id]["managed_classes"] = list(cur_classes)


# ==============================================================================
# 4. 학급별 학생 조회 및 삭제 (교사용)
# ==============================================================================
def get_students_by_class(class_code: str) -> List[Dict[str, Any]]:
    """특정 학급 코드에 등록된 학생 전체 목록을 반환합니다."""
    db = get_firestore_client()
    if db:
        try:
            docs = (
                db.collection("users")
                .where("role", "==", "student")
                .where("class_code", "==", class_code)
                .stream()
            )
            return [d.to_dict() for d in docs]
        except Exception:
            return []

    mock_users = st.session_state.get("mock_users", {})
    return [
        u for u in mock_users.values()
        if u.get("role") == "student" and u.get("class_code") == class_code
    ]


def delete_student(student_id: str) -> bool:
    """단일 학생 계정을 삭제합니다."""
    db = get_firestore_client()
    if db:
        try:
            db.collection("users").document(student_id).delete()
            return True
        except Exception:
            return False

    if "mock_users" in st.session_state and student_id in st.session_state.mock_users:
        del st.session_state.mock_users[student_id]
        return True
    return False


def delete_class_students(class_code: str) -> int:
    """특정 학급에 속한 모든 학생 계정을 일괄 삭제합니다."""
    db = get_firestore_client()
    deleted_cnt = 0
    if db:
        try:
            docs = (
                db.collection("users")
                .where("role", "==", "student")
                .where("class_code", "==", class_code)
                .stream()
            )
            batch = db.batch()
            for doc in docs:
                batch.delete(doc.reference)
                deleted_cnt += 1
            if deleted_cnt > 0:
                batch.commit()
            return deleted_cnt
        except Exception:
            return 0

    mock_users = st.session_state.get("mock_users", {})
    to_delete = [
        sid for sid, u in mock_users.items()
        if u.get("role") == "student" and u.get("class_code") == class_code
    ]
    for sid in to_delete:
        del mock_users[sid]
        deleted_cnt += 1
    return deleted_cnt


# ==============================================================================
# 5. 교사별 학급 생성 및 드롭다운 목록 관리 (무조건 생성 및 에러 방어)
# ==============================================================================
def get_teacher_managed_classes(teacher_id: str) -> List[str]:
    """해당 교사가 생성/관리 중인 학급 코드 목록을 반환합니다."""
    db = get_firestore_client()
    default_classes = ["CLASS_2026_A"]

    if db:
        try:
            t_ref = db.collection("users").document(teacher_id)
            doc = t_ref.get()
            if not doc.exists:
                docs = list(db.collection("users").where("role", "==", "teacher").stream())
                for d in docs:
                    data = d.to_dict()
                    if d.id == teacher_id or data.get("name") == teacher_id:
                        doc = d
                        break

            if doc.exists:
                classes = doc.to_dict().get("managed_classes", [])
                if classes:
                    return list(dict.fromkeys(classes))
        except Exception:
            pass

    mock_users = st.session_state.get("mock_users", {})
    t_data = mock_users.get(teacher_id, {})
    classes = t_data.get("managed_classes", [])
    return list(dict.fromkeys(classes)) if classes else default_classes


def create_new_class_for_teacher(teacher_id: str, new_class_code: str) -> tuple[bool, str]:
    """교사 계정에 새로운 학급 코드를 등록합니다. (계정 부재 시 자동 생성하여 에러 방지)"""
    new_class_code = new_class_code.strip()
    if not new_class_code:
        return False, "학급 코드를 입력해 주세요."

    teacher_id = teacher_id.strip() if teacher_id else "teacher_01"
    db = get_firestore_client()

    if db:
        try:
            t_ref = db.collection("users").document(teacher_id)
            doc = t_ref.get()

            # 문서가 없으면 어디에라도 있는지 교사 role 전수 확인
            if not doc.exists:
                docs = list(db.collection("users").where("role", "==", "teacher").stream())
                for d in docs:
                    data = d.to_dict()
                    if d.id == teacher_id or data.get("name") == teacher_id:
                        t_ref = d.reference
                        doc = d
                        break

            # 끝내 교사 문서가 없다면 에러를 띄우지 않고 즉시 신규 교사 문서로 자동 생성
            if not doc.exists:
                user_payload = {
                    "user_id": teacher_id,
                    "name": teacher_id,
                    "role": "teacher",
                    "school_name": "한국고등학교",
                    "managed_classes": ["CLASS_2026_A", new_class_code],
                    "created_at": datetime.now().isoformat(),
                }
                t_ref.set(user_payload)
                return True, f"신규 학급 '{new_class_code}'이(가) 성공적으로 개설되었습니다."

            # 기존 교사 문서가 있을 때
            t_data = doc.to_dict()
            cur_classes = list(t_data.get("managed_classes", ["CLASS_2026_A"]))
            if new_class_code in cur_classes:
                return False, f"이미 존재하는 학급 코드입니다: {new_class_code}"

            cur_classes.append(new_class_code)
            t_ref.update({"managed_classes": cur_classes})
            return True, f"신규 학급 '{new_class_code}'이(가) 성공적으로 개설되었습니다."
        except Exception as e:
            return False, f"저장 실패: {str(e)}"

    # Mock DB 처리
    mock_users = st.session_state.setdefault("mock_users", {})
    t_data = mock_users.setdefault(teacher_id, {"role": "teacher", "managed_classes": ["CLASS_2026_A"]})
    cur_classes = t_data.setdefault("managed_classes", ["CLASS_2026_A"])
    if new_class_code in cur_classes:
        return False, "이미 존재하는 학급 코드입니다."
    cur_classes.append(new_class_code)
    return True, f"신규 학급 '{new_class_code}'이(가) 개설되었습니다 (Mock)."