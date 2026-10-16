"""PAPSrun 플랫폼 메인 랜딩 및 Firestore 통합 인증 모듈.

캠퍼스 지형·환경물리 데이터와 NetworkX 그래프 기반 러닝 경로 최적화를 제공하며,
Firestore users 컬렉션 연동을 통한 교사/학생 계정 생성, 로그인 인증 및
역할 기반 안전 라우팅을 지원합니다.
"""

from typing import Any, Dict, Optional
import base64
import os
import streamlit as st

from src.db.firebase_client import is_firestore_available
from src.db.user_manager import (
    authenticate_user,
    bulk_register_students_from_json,
    create_teacher_account,
)
from src.utils.auth_helper import (
    clear_login_session,
    set_login_session,
    sync_auth_session,
)

# 로고 이미지 및 글로벌 네비게이션 설정
LOGO_IMAGE_PATH: str = "assets/logo.png"

NAV_LINKS = {
    "플랫폼 소개": "https://www.notion.so",
    "지능형 도로망": "pages/1_student_workspace.py",
    "위상 수학 검증": "pages/1_student_workspace.py",
    "바이브 코딩 최적화": "pages/1_student_workspace.py",
    "교사 관제 센터": "pages/2_teacher_dashboard.py",
}

NOTION_TERMS_URL: str = "https://www.notion.so"
NOTION_PRIVACY_URL: str = "https://www.notion.so"


def get_logo_html(image_path: str, default_emoji: str = "🏃") -> str:
    """로고 파일 존재 여부를 확인하고 이미지 태그 또는 기본 이모지 HTML을 생성합니다."""
    if os.path.exists(image_path):
        ext = os.path.splitext(image_path)[1].lower().replace(".", "")
        if ext == "svg":
            mime = "image/svg+xml"
        elif ext in ["png", "ico", "jpg", "jpeg", "webp"]:
            mime = f"image/{ext}" if ext != "ico" else "image/x-icon"
        else:
            mime = "image/png"

        try:
            with open(image_path, "rb") as f:
                encoded = base64.b64encode(f.read()).decode("utf-8")
            return f'<img src="data:{mime};base64,{encoded}" alt="PAPSrun Logo" style="height: 32px; width: auto; object-fit: contain; vertical-align: middle; margin-right: 6px;" />'
        except Exception:
            pass

    return f'<span style="font-size: 1.5rem; margin-right: 4px; vertical-align: middle;">{default_emoji}</span>'


st.set_page_config(
    page_title="PAPSrun - 지능형 캠퍼스 러닝 최적화 플랫폼",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 세션 초기화 및 브라우저 세션 동기화
sync_auth_session()

# URL 쿼리 파라미터에서 기본 학급 코드 추출 (QR코드 접속 지원)
qp = st.query_params
url_class_code = qp.get("class_code", "CLASS_2026_A")

# 커스텀 모던 UI 및 스타일 주입
st.markdown(
    """
    <style>
    /* 메인 랜딩 화면 좌측 사이드바 원천 숨김 */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }

    /* 전체 페이지 가로 스크롤 방지 */
    html, body, [data-testid="stAppViewContainer"], .main {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }

    /* 본문 컨테이너 여백 최적화 (고정 상단바 64px 고려) */
    .block-container {
        padding-top: 5.5rem !important;
        padding-bottom: 2rem !important;
        padding-left: 2rem !important;
        padding-right: 2rem !important;
        max-width: 1240px;
        margin: 0 auto;
    }
    header[data-testid="stHeader"] {
        background: transparent;
        height: 0rem;
    }

    /* 상단 네비게이션 바: 고정형 */
    .top-nav {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 64px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 0 max(2rem, calc((100vw - 1240px) / 2));
        background: rgba(255, 255, 255, 0.94);
        backdrop-filter: blur(8px);
        -webkit-backdrop-filter: blur(8px);
        border-bottom: 1px solid #e2e8f0;
        z-index: 999999;
        box-sizing: border-box;
    }
    .brand-logo {
        display: inline-flex;
        align-items: center;
        font-size: 1.45rem;
        font-weight: 800;
        color: #1e3a8a !important;
        letter-spacing: -0.6px;
        text-decoration: none !important;
    }
    .brand-logo:hover, .brand-logo:visited, .brand-logo:active, .brand-logo:focus {
        text-decoration: none !important;
        color: #1e3a8a !important;
    }
    .nav-links {
        display: flex;
        align-items: center;
        gap: 1.8rem;
        font-size: 0.95rem;
        font-weight: 500;
    }
    .nav-item {
        color: #334155 !important;
        text-decoration: none !important;
        transition: color 0.15s ease-in-out;
    }
    .nav-item:hover {
        color: #2563eb !important;
    }
    .nav-item:visited, .nav-item:active, .nav-item:focus {
        text-decoration: none !important;
        color: #334155 !important;
    }

    /* DB 헬스체크 배지 */
    .db-badge {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        font-size: 0.8rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
    }

    /* 히어로 섹션 */
    .hero-container {
        text-align: center;
        padding: 1.2rem 1rem 1.6rem 1rem;
        margin: 0 auto;
    }
    .hero-sub {
        color: #64748b;
        font-size: 0.98rem;
        font-weight: 600;
        margin-bottom: 0.6rem;
    }
    .hero-title {
        font-size: 2.7rem;
        font-weight: 800;
        color: #0f172a;
        line-height: 1.2;
        margin-bottom: 0.5rem;
        letter-spacing: -0.8px;
    }
    .hero-desc {
        font-size: 1.55rem;
        font-weight: 600;
        color: #334155;
        margin-bottom: 1.8rem;
    }

    /* 통계 지표 카드 그리드 */
    .stat-container {
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 1.5rem;
        max-width: 820px;
        margin: 2.5rem auto 3rem auto;
        padding-top: 1.8rem;
        border-top: 1px solid #edf2f7;
    }
    .stat-card {
        text-align: center;
    }
    .stat-label {
        font-size: 0.88rem;
        color: #64748b;
        margin-bottom: 0.35rem;
        font-weight: 500;
    }
    .stat-value {
        font-size: 2.1rem;
        font-weight: 800;
        color: #2563eb;
    }

    /* 미니멀 라인 푸터 */
    .clean-footer {
        width: 100%;
        margin-top: 4.0rem;
        padding-top: 2.5rem;
        padding-bottom: 2.5rem;
        border-top: 1px solid #e2e8f0;
        text-align: center;
        color: #64748b;
        font-size: 0.88rem;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
    }
    .footer-links {
        display: flex;
        justify-content: center;
        align-items: center;
        gap: 1.2rem;
        font-size: 0.92rem;
        font-weight: 600;
        margin-bottom: 1.0rem;
    }
    .footer-links a {
        color: #475569 !important;
        text-decoration: none !important;
        transition: color 0.15s ease-in-out;
    }
    .footer-links a:hover {
        color: #2563eb !important;
        text-decoration: underline !important;
    }
    .footer-dot {
        color: #cbd5e1;
        font-size: 0.8rem;
    }
    .footer-info {
        font-size: 0.86rem;
        color: #475569;
        margin-bottom: 1.0rem;
    }
    .footer-info strong {
        color: #1e293b;
    }
    .footer-disclaimer {
        font-size: 0.8rem;
        color: #94a3b8;
        line-height: 1.6;
        max-width: 800px;
        margin: 0 auto 1.2rem auto;
    }
    .footer-copyright {
        font-size: 0.78rem;
        color: #94a3b8;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# 1. 상단 글로벌 네비게이션 헤더 및 헬스 배지
logo_markup = get_logo_html(LOGO_IMAGE_PATH)
nav_links_html = "".join(
    f'<a class="nav-item" href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
    for title, url in NAV_LINKS.items()
)

db_status_badge = (
    '<span class="db-badge" style="border-color:#bbf7d0; background:#f0fdf4; color:#15803d;">● Cloud Firestore Online</span>'
    if is_firestore_available()
    else '<span class="db-badge" style="border-color:#fef08a; background:#fefce8; color:#854d0e;">○ Local InMemory Mode</span>'
)

st.markdown(
    f"""
    <div class="top-nav">
        <a href="/" class="brand-logo">{logo_markup}<span>PAPSrun</span></a>
        <div class="nav-links">
            {nav_links_html}
        </div>
        <div style="display:flex; align-items:center; gap:12px;">
            {db_status_badge}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 2. 히어로 슬로건 섹션
st.markdown(
    """
    <div class="hero-container">
        <div class="hero-sub">지능형 캠퍼스 러닝 경로 설계 및 학생 체력평가 융합 플랫폼 PAPSrun</div>
        <div class="hero-title">내 손안의 지능형 러닝 코스.</div>
        <div class="hero-desc">알고리즘과 데이터로, 쾌적하게.</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 3. 로그인 및 세션 라우팅
if st.session_state.get("authenticated", False):
    role_kr = "교사 (관리자)" if st.session_state.user_role == "teacher" else "학생"
    st.success(
        f"현재 **{st.session_state.user_name}**님({role_kr})으로 로그인되어 있습니다. "
        f"(학급: `{st.session_state.get('class_code', 'CLASS_A')}`)"
    )

    col_a, col_b, col_c = st.columns([1, 1, 1])
    with col_a:
        if st.button("👉 학생 워크스페이스 입장", use_container_width=True, type="primary"):
            st.switch_page("pages/1_student_workspace.py")
    with col_b:
        if st.session_state.user_role == "teacher":
            if st.button("📊 교사 통제 대시보드 입장", use_container_width=True):
                st.switch_page("pages/2_teacher_dashboard.py")
        else:
            st.info("교사 전용 대시보드는 교사 계정으로 로그인 시 열람 가능합니다.")
    with col_c:
        if st.button("로그아웃", use_container_width=True):
            clear_login_session()
            st.rerun()

else:
    # 로그인 / 신규 교사 가입 / 학생 개별 등록 탭 전환
    _, center_col, _ = st.columns([1, 1.35, 1])
    with center_col:
        tab_login, tab_student_signup, tab_teacher_signup = st.tabs(
            ["🚀 로그인", "🙋 학생 계정 생성", "👨‍🏫 신규 교사 등록"]
        )

        # ----------------------------------------------------------------------
        # TAB 1: 정식 로그인 (학생 / 교사)
        # ----------------------------------------------------------------------
        with tab_login:
            role_choice = st.radio(
                "로그인 대상",
                ["학생 로그인", "교사(관리자) 로그인"],
                horizontal=True,
            )

            with st.form("login_form", clear_on_submit=False):
                if role_choice == "학생 로그인":
                    student_id_input = st.text_input(
                        "학번 / 학생 ID",
                        placeholder="예: 2026001",
                    )
                    class_code_or_pw = st.text_input(
                        "학급 코드 또는 학생 비밀번호",
                        value=url_class_code,
                        placeholder="발급받은 학급코드 또는 비밀번호 입력",
                    )
                    submitted = st.form_submit_button(
                        "학생 워크스페이스 입장 (Enter)",
                        type="primary",
                        use_container_width=True,
                    )
                    if submitted:
                        if not student_id_input.strip() or not class_code_or_pw.strip():
                            st.error("학번과 학급 코드를 모두 입력해 주세요.")
                        else:
                            user_data = authenticate_user(
                                user_id=student_id_input.strip(),
                                password_or_code=class_code_or_pw.strip(),
                            )
                            if user_data and user_data.get("role") == "student":
                                set_login_session(
                                    role="student",
                                    user_name=user_data.get("name", student_id_input.strip()),
                                    class_code=user_data.get("class_code", class_code_or_pw.strip()),
                                )
                                st.success(f"{user_data.get('name')} 학생 인증 완료!")
                                st.switch_page("pages/1_student_workspace.py")
                            else:
                                st.error("등록되지 않은 학번이거나 학급 코드가 올바르지 않습니다.")

                else:  # 교사 로그인
                    teacher_id_input = st.text_input(
                        "교사 아이디",
                        placeholder="예: teacher_01",
                    )
                    teacher_pw_input = st.text_input(
                        "비밀번호",
                        type="password",
                        placeholder="교사 계정 비밀번호 입력",
                    )
                    submitted = st.form_submit_button(
                        "교사 권한으로 로그인 (Enter)",
                        type="primary",
                        use_container_width=True,
                    )
                    if submitted:
                        if not teacher_id_input.strip() or not teacher_pw_input.strip():
                            st.error("교사 아이디와 비밀번호를 입력해 주세요.")
                        else:
                            user_data = authenticate_user(
                                user_id=teacher_id_input.strip(),
                                password_or_code=teacher_pw_input.strip(),
                            )
                            if user_data and user_data.get("role") == "teacher":
                                managed_classes = user_data.get("managed_classes", [])
                                default_class = managed_classes[0] if managed_classes else "CLASS_2026_A"
                                set_login_session(
                                    role="teacher",
                                    user_name=user_data.get("name", "담당 교사"),
                                    class_code=default_class,
                                )
                                st.success(f"{user_data.get('name')} 선생님 환영합니다!")
                                st.switch_page("pages/2_teacher_dashboard.py")
                            else:
                                st.error("교사 아이디 또는 비밀번호가 올바르지 않습니다.")

        # ----------------------------------------------------------------------
        # TAB 2: 학생 즉시 계정 등록 (Self-Registration)
        # ----------------------------------------------------------------------
        with tab_student_signup:
            st.caption("수업 담당 교사로부터 안내받은 공식 학급 코드를 입력하여 학생 계정을 등록합니다.")
            with st.form("student_signup_form", clear_on_submit=False):
                col_s1, col_s2 = st.columns(2)
                with col_s1:
                    new_student_id = st.text_input("학번 / 학생 ID", placeholder="예: 2026001")
                    new_student_name = st.text_input("학생 성명", placeholder="예: 김철수")
                with col_s2:
                    new_student_class = st.text_input("공식 학급 코드", value=url_class_code)
                    new_student_team = st.selectbox(
                        "소속 모둠 (권역)",
                        ["1조: 통학로", "2조: 운동장 트랙", "3조: 본관 사잇길", "4조: 교내 녹지 언덕"],
                    )

                new_student_paps = st.slider("본인 PAPS 심폐지구력 등급", min_value=1, max_value=5, value=3)
                new_student_pw = st.text_input(
                    "로그인 비밀번호 설정 (미입력 시 학급코드로 로그인)",
                    type="password",
                    placeholder="선택 사항",
                )

                st_submitted = st.form_submit_button("학생 계정 등록 완료", type="primary", use_container_width=True)
                if st_submitted:
                    if not new_student_id.strip() or not new_student_name.strip() or not new_student_class.strip():
                        st.error("학번, 성명, 학급 코드는 필수 입력 항목입니다.")
                    else:
                        team_key = f"TEAM_{new_student_team.split('조')[0]}"
                        student_json_payload = f"""
                        [
                            {{
                                "student_id": "{new_student_id.strip()}",
                                "name": "{new_student_name.strip()}",
                                "class_code": "{new_student_class.strip()}",
                                "team_id": "{team_key}",
                                "paps_grade": {new_student_paps},
                                "password": "{new_student_pw.strip() if new_student_pw.strip() else new_student_class.strip()}"
                            }}
                        ]
                        """
                        ok_cnt, fail_cnt, errs = bulk_register_students_from_json(
                            json_content=student_json_payload,
                            teacher_id="SELF_REGISTRATION",
                            default_class_code=new_student_class.strip(),
                        )
                        if ok_cnt > 0:
                            st.success(f"{new_student_name.strip()} 학생 계정이 등록되었습니다! [🚀 로그인] 탭으로 이동해 접속하세요.")
                        else:
                            st.error(f"등록 실패: {', '.join(errs)}")

        # ----------------------------------------------------------------------
        # TAB 3: 신규 교사 계정 생성
        # ----------------------------------------------------------------------
        with tab_teacher_signup:
            st.caption("학교에 배포된 기관 마스터 시크릿 키를 확인 후 교사 계정을 등록합니다.")
            with st.form("teacher_signup_form", clear_on_submit=False):
                new_teacher_id = st.text_input("교사 아이디 (ID)", placeholder="예: teacher_2026")
                new_teacher_name = st.text_input("교사 성명", placeholder="예: 이진호")
                new_teacher_school = st.text_input("소속 학교", value="한국고등학교")
                new_teacher_pw = st.text_input("비밀번호 설정", type="password")
                admin_key_input = st.text_input(
                    "교사 인증 시크릿 키 (관리자 키)",
                    type="password",
                    placeholder="기본값: teacher1234",
                )
                signup_submitted = st.form_submit_button(
                    "교사 계정 생성 완료",
                    type="primary",
                    use_container_width=True,
                )
                if signup_submitted:
                    ok, msg = create_teacher_account(
                        teacher_id=new_teacher_id,
                        raw_password=new_teacher_pw,
                        name=new_teacher_name,
                        admin_secret_key=admin_key_input,
                        school_name=new_teacher_school,
                    )
                    if ok:
                        st.success(f"{msg} [🚀 로그인] 탭으로 이동해 교사 로그인을 진행하세요.")
                    else:
                        st.error(msg)

# 4. PAPSrun 시스템 고유 통계 카드 그리드
st.markdown(
    """
    <div class="stat-container">
        <div class="stat-card">
            <div class="stat-label">작도된 도로망 세그먼트</div>
            <div class="stat-value">428개</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">GIS 15m 스냅 교차 노드</div>
            <div class="stat-value">182개</div>
        </div>
        <div class="stat-card">
            <div class="stat-label">AI 바이브 코딩 최적화 연산</div>
            <div class="stat-value">1,240회</div>
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# 5. 미니멀 라인 푸터 (회색 라인 분절형)
st.markdown(
    f"""
    <div class="clean-footer">
        <div class="footer-links">
            <a href="{NOTION_TERMS_URL}" target="_blank" rel="noopener noreferrer">이용약관</a>
            <span class="footer-dot">•</span>
            <a href="{NOTION_PRIVACY_URL}" target="_blank" rel="noopener noreferrer">개인정보처리방침</a>
        </div>
        <div class="footer-info">
            운영 및 개발: <strong>JH's SW Lab</strong> &nbsp;|&nbsp; 문의: devlee92736@gmail.com
        </div>
        <div class="footer-disclaimer">
            본 서비스의 러닝 경로 추천 및 지형·온열부하 분석 결과는 지리정보(GIS) 데이터와 체육 물리 모델을 AI 및 다익스트라 알고리즘으로 시뮬레이션한 교육용 보조 지표이며<br>
            개별 사용자의 신체 건강 상태나 기상 악화 시 절대적 안전 지침 또는 의료적 판단의 근거가 될 수 없습니다.
        </div>
        <div class="footer-copyright">
            © 2026 JH's SW Lab. All rights reserved. Powered by Google Gemini.
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)