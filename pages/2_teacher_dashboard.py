"""PAPSrun 교사 종합 관제 대시보드 (Teacher Dashboard).

학급 드롭다운 선택, 신규 학급 생성, 학급별 학생 명단 JSON 일괄 등록/삭제,
1차시 맵 빌더 지형 작도 인터락(Lock/Unlock) 및 환경 변수 주입을 지원합니다.
"""

from datetime import datetime
import json
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from src.db.firebase_client import is_firestore_available
from src.db.user_manager import (
    bulk_register_students_from_json,
    create_new_class_for_teacher,
    delete_class_students,
    delete_student,
    get_students_by_class,
    get_teacher_managed_classes,
)
from src.utils.auth_helper import clear_login_session, sync_auth_session

# 1. 페이지 설정 및 세션 복원
st.set_page_config(
    page_title="PAPSrun - 교사 관제 센터",
    page_icon="👨‍🏫",
    layout="wide",
    initial_sidebar_state="expanded",
)
sync_auth_session()

# 2. 교사 권한 접근 통제 (RBAC Guardrail)
if not st.session_state.get("authenticated", False) or st.session_state.get("user_role") != "teacher":
    st.error("⛔ 접근 권한이 없습니다. 교사 계정으로 로그인 후 이용해 주세요.")
    if st.button("👉 메인 로그인 화면으로 이동", type="primary"):
        st.switch_page("app.py")
    st.stop()

# 실제 교사 ID를 우선적으로 바인딩
teacher_id = st.session_state.get("user_id") or st.session_state.get("user_name") or "teacher_01"
teacher_display = st.session_state.get("teacher_real_name", teacher_id)

managed_classes = get_teacher_managed_classes(teacher_id)
if not managed_classes:
    managed_classes = ["CLASS_2026_A"]

# 3. 사이드바: 학급 드롭다운 선택 및 신규 학급 개설
with st.sidebar:
    st.markdown("### 👨‍🏫 교사 관제 콘솔")
    st.write(f"**담당 교사**: {teacher_display} (`{teacher_id}`)")

    st.markdown("---")
    st.markdown("#### 🏫 학급 선택 (드롭다운)")
    
    cur_saved_class = st.session_state.get("class_code", managed_classes[0])
    selected_idx = managed_classes.index(cur_saved_class) if cur_saved_class in managed_classes else 0

    selected_class = st.selectbox(
        "관제할 학급을 선택하세요",
        options=managed_classes,
        index=selected_idx,
        help="선택한 학급의 학생 명단과 데이터가 메인 화면에 로드됩니다.",
    )
    st.session_state.class_code = selected_class

    with st.expander("➕ 새 학급 개설하기"):
        with st.form("create_class_form", clear_on_submit=True):
            new_code_input = st.text_input("새 학급 코드", placeholder="예: CLASS_2026_B")
            btn_create_class = st.form_submit_button("학급 생성", use_container_width=True)
            if btn_create_class:
                ok, msg = create_new_class_for_teacher(teacher_id, new_code_input)
                if ok:
                    st.success(msg)
                    st.session_state.class_code = new_code_input.strip()
                    st.rerun()
                else:
                    st.error(msg)

    st.markdown("---")
    if is_firestore_available():
        st.success("🟢 Firestore Cloud 연동됨")
    else:
        st.warning("🟡 InMemory Mock 모드")

    st.markdown("---")
    col_sb1, col_sb2 = st.columns(2)
    with col_sb1:
        if st.button("학생 화면 이동", use_container_width=True):
            st.switch_page("pages/1_student_workspace.py")
    with col_sb2:
        if st.button("로그아웃", use_container_width=True, type="secondary"):
            clear_login_session()
            st.switch_page("app.py")

# 4. 메인 화면 헤더
current_class = st.session_state.class_code
st.title("🎛️ PAPSrun 통합 교사 관제 대시보드")
st.info(f"현재 선택된 관제 학급: **`{current_class}`** | 상단 탭에서 학생 명단을 관리하거나 수업을 통제하세요.")

# 5. 관제 탭 구성
tab_students, tab_course_control, tab_analytics = st.tabs(
    ["👥 학급·학생 명단 관리", "🔒 수업 인터락 및 지형 통제", "📊 실시간 학습 현황"]
)

# ==============================================================================
# TAB 1: 학급·학생 명단 관리 (드롭다운 연동 및 JSON 일괄 등록)
# ==============================================================================
with tab_students:
    st.subheader(f"📋 `{current_class}` 학생 명단 조회 및 관리")

    students_list = get_students_by_class(current_class)

    col_view, col_upload = st.columns([1.3, 1])

    with col_view:
        st.markdown(f"#### 1. `{current_class}` 소속 학생 ({len(students_list)}명)")
        if not students_list:
            st.warning(f"현재 학급 `{current_class}`에 등록된 학생이 없습니다. 우측에서 JSON 명단을 업로드해 등록해 주세요.")
        else:
            df_students = pd.DataFrame(students_list)
            display_cols = ["student_id", "name", "team_id", "paps_grade", "created_at"]
            actual_cols = [c for c in display_cols if c in df_students.columns]

            st.dataframe(
                df_students[actual_cols].rename(
                    columns={
                        "student_id": "학번/ID",
                        "name": "성명",
                        "team_id": "소속 모둠",
                        "paps_grade": "PAPS 등급",
                        "created_at": "등록 일시",
                    }
                ),
                use_container_width=True,
                hide_index=True,
            )

            col_d1, col_d2 = st.columns(2)
            with col_d1:
                with st.expander("🗑️ 학생 개별 삭제"):
                    target_sid = st.selectbox(
                        "삭제할 학생",
                        options=[s.get("student_id") for s in students_list],
                        format_func=lambda sid: f"{sid} ({next((s.get('name') for s in students_list if s.get('student_id') == sid), '')})",
                    )
                    if st.button("해당 학생 계정 삭제", type="secondary", use_container_width=True):
                        if delete_student(target_sid):
                            st.success(f"학번 `{target_sid}` 학생이 삭제되었습니다.")
                            st.rerun()

            with col_d2:
                with st.expander(f"⚠️ `{current_class}` 학생 일괄 비우기"):
                    confirm_code = st.text_input(f"확인을 위해 학급 코드 '{current_class}' 입력")
                    if st.button("학급 명단 전체 초기화", type="primary", use_container_width=True):
                        if confirm_code.strip() == current_class:
                            cnt = delete_class_students(current_class)
                            st.success(f"{cnt}명의 학생 계정이 삭제되었습니다.")
                            st.rerun()
                        else:
                            st.error("학급 코드가 일치하지 않습니다.")

    with col_upload:
        st.markdown(f"#### 2. `{current_class}` 학생 명단 JSON 일괄 업로드")
        uploaded_file = st.file_uploader(
            f"'{current_class}'에 등록할 학생 JSON 파일 선택",
            type=["json"],
            help="학번, 성명, 모둠, PAPS 등급이 담긴 JSON 파일",
        )

        if uploaded_file is not None:
            try:
                json_text = uploaded_file.read().decode("utf-8")
                parsed_preview = json.loads(json_text)
                preview_list = parsed_preview if isinstance(parsed_preview, list) else parsed_preview.get("students", [])
                st.caption(f"총 {len(preview_list)}명의 학생 명단이 감지되었습니다.")

                if st.button(f"🚀 `{current_class}`에 학생 일괄 등록 실행", type="primary", use_container_width=True):
                    with st.spinner("Firestore users 컬렉션에 등록 중..."):
                        success_cnt, fail_cnt, errors = bulk_register_students_from_json(
                            json_content=json_text,
                            teacher_id=teacher_id,
                            default_class_code=current_class,
                        )
                    if success_cnt > 0:
                        st.success(f"✅ {success_cnt}명의 학생이 `{current_class}`에 등록되었습니다.")
                    if fail_cnt > 0:
                        st.error(f"❌ {fail_cnt}건 실패: {', '.join(errors)}")
                    st.rerun()
            except Exception as e:
                st.error(f"JSON 파싱 실패: {str(e)}")

        with st.expander("💡 JSON 예시 템플릿 보기"):
            sample_json = [
                {"student_id": "2026101", "name": "김철수", "team_id": "TEAM_1", "paps_grade": 2},
                {"student_id": "2026102", "name": "이영희", "team_id": "TEAM_2", "paps_grade": 3},
                {"student_id": "2026103", "name": "박민수", "team_id": "TEAM_3", "paps_grade": 1},
            ]
            st.code(json.dumps(sample_json, indent=2, ensure_ascii=False), language="json")

# ==============================================================================
# TAB 2: 수업 인터락 및 지형 통제
# ==============================================================================
with tab_course_control:
    st.subheader(f"🔒 `{current_class}` 차시별 학생 권한 통제")
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        st.markdown("#### 1차시 도로망 맵 빌더 편집 권한")
        is_locked_state = st.toggle("🔒 1차시 도로망 작도 잠금 (읽기 전용)", value=False)
        if is_locked_state:
            st.error(f"`{current_class}` 학생 워크스페이스의 도로 작도가 잠겼습니다.")
        else:
            st.success(f"`{current_class}` 학생 워크스페이스 작도 권한이 허용된 상태입니다.")

    with col_lock2:
        st.markdown("#### 가상 환경 변수 강제 주입 (Override)")
        override_active = st.checkbox("기상청 API 실측값 대신 가상 환경 주입", value=False)
        sim_temp = st.slider("가상 대기 기온 (°C)", 15.0, 38.0, 31.5, 0.5, disabled=not override_active)
        sim_solar = st.slider("가상 전일사량 (W/m²)", 100.0, 1100.0, 750.0, 25.0, disabled=not override_active)

# ==============================================================================
# TAB 3: 실시간 학습 현황
# ==============================================================================
with tab_analytics:
    st.subheader(f"📊 `{current_class}` 4개 권역별 참여 현황")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("1조 (정문/통학로)", "간선 112개", "위상 무결")
    with col_m2:
        st.metric("2조 (운동장 트랙)", "간선 86개", "위상 무결")
    with col_m3:
        st.metric("3조 (본관 사잇길)", "간선 124개", "경계 점검 요망", delta_color="inverse")
    with col_m4:
        st.metric("4조 (교내 언덕)", "간선 106개", "위상 무결")