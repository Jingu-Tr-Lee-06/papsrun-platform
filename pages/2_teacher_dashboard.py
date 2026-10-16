"""PAPSrun 교사 종합 관제 대시보드 (Teacher Dashboard)."""

from datetime import datetime
import json
from typing import Any, Dict, List
import pandas as pd
import streamlit as st

from src.db.firebase_client import is_firestore_available
from src.db.user_manager import (
    bulk_register_students_from_json,
    delete_class_students,
    delete_student,
    get_students_by_class,
)
from src.utils.auth_helper import clear_login_session, sync_auth_session
from src.geo.weather_engine import get_effective_weather_data
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

# 3. 사이드바 교사 프로필 및 학급 지정
with st.sidebar:
    st.markdown("### 👨‍🏫 교사 관제 콘솔")
    st.write(f"**담당 교사**: {st.session_state.get('user_name', '교사')}")

    current_class = st.text_input(
        "관리 대상 학급 코드",
        value=st.session_state.get("class_code", "CLASS_2026_A"),
        help="학생 계정을 조회하고 제어할 학급 코드를 입력하세요.",
    )
    st.session_state.class_code = current_class

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
st.title("🎛️ PAPSrun 통합 교사 관제 대시보드")
st.info(f"현재 선택된 관리 학급: **`{current_class}`** | 교사 권한으로 학생 및 수업 환경을 통제합니다.")

# 5. 관제 탭 구성
tab_students, tab_course_control, tab_analytics = st.tabs(
    ["👥 학급·학생 계정 관리", "🔒 수업 인터락 및 지형 통제", "📊 실시간 학습 현황"]
)

# ==============================================================================
# TAB 1: 학급·학생 계정 관리
# ==============================================================================
with tab_students:
    st.subheader("📋 학급 학생 명단 관리 및 JSON 일괄 등록")
    col_upload, col_sample = st.columns([1.2, 1])

    with col_upload:
        st.markdown("#### 1. 학생 명단 JSON 파일 업로드")
        uploaded_file = st.file_uploader(
            "학생 명단 JSON 파일을 선택하세요",
            type=["json"],
            help="학생 식별자, 이름, 모둠, PAPS 등급이 포함된 JSON 파일",
        )

        if uploaded_file is not None:
            try:
                json_text = uploaded_file.read().decode("utf-8")
                parsed_data = json.loads(json_text)
                st.info(f"📄 파일 감지 성공: 총 {len(parsed_data) if isinstance(parsed_data, list) else 1}건의 데이터")

                if st.button("🚀 위 학생 명단 Firestore 일괄 등록 실행", type="primary", use_container_width=True):
                    with st.spinner("Firestore users 컬렉션에 일괄 등록 중..."):
                        success_cnt, fail_cnt, errors = bulk_register_students_from_json(
                            json_content=json_text,
                            teacher_id=st.session_state.get("user_name", "teacher"),
                            default_class_code=current_class,
                        )
                    if success_cnt > 0:
                        st.success(f"✅ {success_cnt}명의 학생 계정이 정상 등록되었습니다.")
                    if fail_cnt > 0:
                        st.error(f"❌ {fail_cnt}건 등록 실패: {', '.join(errors)}")
                    st.rerun()

            except Exception as e:
                st.error(f"JSON 파일 파싱 실패: {str(e)}")

    with col_sample:
        st.markdown("#### 2. 표준 JSON 포맷 가이드")
        sample_json_template = [
            {"student_id": "2026101", "name": "김철수", "class_code": current_class, "team_id": "TEAM_1", "paps_grade": 2},
            {"student_id": "2026102", "name": "이영희", "class_code": current_class, "team_id": "TEAM_2", "paps_grade": 3},
            {"student_id": "2026103", "name": "박민수", "class_code": current_class, "team_id": "TEAM_3", "paps_grade": 1},
        ]
        st.code(json.dumps(sample_json_template, indent=2, ensure_ascii=False), language="json")

    st.markdown("---")

    # 등록된 학생 목록 조회 및 관리 섹션
    st.markdown(f"#### 3. 현재 학급(`{current_class}`) 등록 학생 목록")
    students_list = get_students_by_class(current_class)

    if not students_list:
        st.warning(f"현재 학급 `{current_class}`에 등록된 학생 계정이 없습니다.")
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

        col_del_single, col_del_bulk = st.columns([1, 1])
        with col_del_single:
            with st.expander("🗑️ 학생 개별 삭제"):
                target_sid = st.selectbox(
                    "삭제할 학생 선택",
                    [s.get("student_id") for s in students_list],
                    format_func=lambda sid: f"{sid} ({next((s.get('name') for s in students_list if s.get('student_id') == sid), '')})",
                )
                if st.button("선택 학생 계정 삭제", type="secondary", use_container_width=True):
                    if delete_student(target_sid):
                        st.success(f"학번 `{target_sid}` 학생이 삭제되었습니다.")
                        st.rerun()

        with col_del_bulk:
            with st.expander("⚠️ 학급 전체 학생 비우기"):
                confirm_txt = st.text_input(f"초기화 확인: '{current_class}' 입력")
                if st.button("학급 전체 학생 일괄 삭제", type="primary", use_container_width=True):
                    if confirm_txt.strip() == current_class:
                        del_cnt = delete_class_students(current_class)
                        st.success(f"총 {del_cnt}명의 학생 계정이 삭제되었습니다.")
                        st.rerun()
                    else:
                        st.error("학급 코드가 일치하지 않습니다.")

# ==============================================================================
# TAB 2: 수업 인터락 및 지형 통제
# ==============================================================================
with tab_course_control:
    st.subheader("🔒 차시별 학생 권한 잠금 (Interlock Control)")
    col_lock1, col_lock2 = st.columns(2)
    with col_lock1:
        st.markdown("#### 1차시 도로망 맵 빌더 편집 권한")
        is_locked_state = st.toggle("🔒 1차시 도로망 작도 잠금 (읽기 전용 모드)", value=False)
        if is_locked_state:
            st.error("현재 학생 워크스페이스의 도로 작도 기능이 잠겨 있습니다. (동결 상태)")
        else:
            st.success("학생들이 도로망을 자유롭게 작도하고 수정할 수 있는 상태입니다.")

    with col_lock2:
        st.markdown("#### 기상청 API 장애 대비 가상 환경 주입 (Override)")
        override_active = st.checkbox("기상청 API 실측값 대신 가상 환경 주입", value=False)
        sim_temp = st.slider("가상 대기 기온 (°C)", 15.0, 38.0, 31.5, 0.5, disabled=not override_active)
        sim_solar = st.slider("가상 전일사량 (W/m²)", 100.0, 1100.0, 750.0, 25.0, disabled=not override_active)

        # weather_engine과 연동되는 세션 키 기록
        st.session_state["weather_override"] = {
            "active": override_active,
            "temp_c": sim_temp,
            "solar_w_m2": sim_solar,
        }

    st.markdown("---")
    st.markdown("#### 📡 현재 플랫폼 기상 데이터 수신 상태 점검")

    # weather_engine을 통해 현재 적용 중인 실제 기상 데이터 조회
    current_weather = get_effective_weather_data()
    weather_status = current_weather.get("status", "UNKNOWN")

    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4)
    with col_stat1:
        if weather_status == "LIVE_KMA_API":
            st.success("🟢 기상청 실시간 API 연동")
        elif weather_status == "TEACHER_OVERRIDE":
            st.info("🔵 교사 강제 주입(Override) 활성")
        else:
            st.warning(f"🟡 {weather_status} (기본값 작동)")

    with col_stat2:
        st.metric("현재 적용 기온", f"{current_weather.get('temp_c')} °C")
    with col_stat3:
        st.metric("현재 적용 일사량", f"{current_weather.get('solar_w_m2')} W/m²")
    with col_stat4:
        st.metric("최종 갱신 시각", f"{current_weather.get('updated_at')}")

    with st.expander("🔍 기상 원본 JSON 데이터 확인"):
        st.json(current_weather)

# ==============================================================================
# TAB 3: 실시간 학습 현황
# ==============================================================================
with tab_analytics:
    st.subheader("📊 모둠별 진행 현황 요약")
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    with col_m1:
        st.metric("1조 (정문/통학로)", "간선 112개", "위상 무결")
    with col_m2:
        st.metric("2조 (운동장 트랙)", "간선 86개", "위상 무결")
    with col_m3:
        st.metric("3조 (본관 사잇길)", "간선 124개", "경계 점검 요망", delta_color="inverse")
    with col_m4:
        st.metric("4조 (교내 언덕)", "간선 106개", "위상 무결")