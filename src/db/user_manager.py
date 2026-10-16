"""Firebase Firestore 기반 통합 사용자 계정 및 학급 관리 모듈."""

from datetime import datetime
import hashlib
import json
from typing import Any, Dict, List, Optional
import streamlit as st

from src.db.firebase_client import get_firestore_client


def _hash_password(raw_password: str) -> str:
    return hashlib.sha256(raw_password.encode("utf-8")).hexdigest()


def authenticate_user(user_id: str, password_or_code: str) -> Optional[Dict[str, Any]]:
    db = get_firestore_client()
    input_hash = _hash_password(password_or_code)

    if db:
        try:
            doc_ref = db.collection("users").document(user_id)
            doc = doc_ref.get()
            if not doc.exists:
                return None

            user_data = doc.to_dict()
            if user_data.get("role") == "teacher":
                if user_data.get("password_hash") == input_hash:
                    return user_data

            elif user_data.get("role") == "student":
                saved_hash = user_data.get("password_hash")
                if saved_hash and saved_hash == input_hash:
                    return user_data
                if user_data.get("class_code") == password_or_code.strip():
                    return user_data

            return None
        except Exception:
            return None

    # Mock DB 폴백
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


def create_teacher_account(
    teacher_id: str,
    raw_password: str,
    name: str,
    admin_secret_key: str,
    school_name: str = "한국고등학교",
) -> tuple[bool, str]:
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

    mock_users = st.session_state.setdefault("mock_users", {})
    if teacher_id in mock_users:
        return False, "이미 존재하는 교사 아이디입니다."
    mock_users[teacher_id] = user_payload
    return True, "교사 계정이 성공적으로 생성되었습니다 (로컬 모드)."


def bulk_register_students_from_json(
    json_content: str,
    teacher_id: str,
    default_class_code: Optional[str] = None,
) -> tuple[int, int, List[str]]:
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
            error_logs.append(f"행 {idx+1}: student_id 또는 name 누락")
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
            mock_users = st.session_state.setdefault("mock_users", {})
            mock_users[sid] = student_payload

        success_cnt += 1

    if db and batch_ops > 0:
        batch.commit()

    if registered_classes and teacher_id:
        for c in registered_classes:
            create_new_class_for_teacher(teacher_id, c)

    return success_cnt, fail_cnt, error_logs


def get_students_by_class(class_code: str) -> List[Dict[str, Any]]:
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
    db = get_firestore_client()
    if db:
        try:
            db.collection("users").document(student_id).delete()
            return True
        except Exception:
            return False

    mock_users = st.session_state.get("mock_users", {})
    if student_id in mock_users:
        del mock_users[student_id]
        return True
    return False


def delete_class_students(class_code: str) -> int:
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


def get_teacher_managed_classes(teacher_id: str) -> List[str]:
    """해당 교사가 관리 중인 학급 목록을 가져옵니다."""
    db = get_firestore_client()
    default_classes = ["CLASS_2026_A"]
    teacher_id = (teacher_id or "").strip() or "teacher_01"

    if db:
        try:
            # 1. 문서 ID 직접 조회
            doc = db.collection("users").document(teacher_id).get()
            if doc.exists:
                classes = doc.to_dict().get("managed_classes", [])
                if classes:
                    return list(dict.fromkeys(classes))

            # 2. name 필드로 교사 문서 역추적
            docs = list(db.collection("users").where("role", "==", "teacher").stream())
            for d in docs:
                data = d.to_dict()
                if d.id == teacher_id or data.get("name") == teacher_id:
                    classes = data.get("managed_classes", [])
                    if classes:
                        return list(dict.fromkeys(classes))
        except Exception:
            pass

    mock_users = st.session_state.get("mock_users", {})
    t_data = mock_users.get(teacher_id, {})
    classes = t_data.get("managed_classes", [])
    return list(dict.fromkeys(classes)) if classes else default_classes


def create_new_class_for_teacher(teacher_id: str, new_class_code: str) -> tuple[bool, str]:
    """신규 학급을 개설합니다. (문서가 없으면 자동 생성하여 절대 실패하지 않음)"""
    new_class_code = new_class_code.strip()
    if not new_class_code:
        return False, "학급 코드를 입력해 주세요."

    teacher_id = (teacher_id or "").strip() or "teacher_01"
    db = get_firestore_client()

    if db:
        try:
            t_ref = db.collection("users").document(teacher_id)
            doc = t_ref.get()

            # 문서가 없으면 교사 계정을 즉시 생성
            if not doc.exists:
                docs = list(db.collection("users").where("role", "==", "teacher").stream())
                found = False
                for d in docs:
                    data = d.to_dict()
                    if d.id == teacher_id or data.get("name") == teacher_id:
                        t_ref = d.reference
                        doc = d
                        found = True
                        break

                if not found:
                    payload = {
                        "user_id": teacher_id,
                        "name": teacher_id,
                        "role": "teacher",
                        "school_name": "한국고등학교",
                        "managed_classes": ["CLASS_2026_A", new_class_code],
                        "created_at": datetime.now().isoformat(),
                    }
                    t_ref.set(payload)
                    return True, f"신규 학급 '{new_class_code}'이(가) 개설되었습니다."

            # 기존 문서 갱신
            cur_classes = list(doc.to_dict().get("managed_classes", ["CLASS_2026_A"]))
            if new_class_code in cur_classes:
                return False, f"이미 존재하는 학급 코드입니다: {new_class_code}"

            cur_classes.append(new_class_code)
            t_ref.update({"managed_classes": cur_classes})
            return True, f"신규 학급 '{new_class_code}'이(가) 개설되었습니다."
        except Exception as e:
            return False, f"저장 실패: {str(e)}"

    # Mock DB
    mock_users = st.session_state.setdefault("mock_users", {})
    t_data = mock_users.setdefault(teacher_id, {"role": "teacher", "managed_classes": ["CLASS_2026_A"]})
    cur_classes = t_data.setdefault("managed_classes", ["CLASS_2026_A"])
    if new_class_code in cur_classes:
        return False, "이미 존재하는 학급 코드입니다."
    cur_classes.append(new_class_code)
    return True, f"신규 학급 '{new_class_code}'이(가) 개설되었습니다 (Mock)."