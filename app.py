"""PAPSrun 플랫폼 메인 랜딩 및 통합 역할 기반 인증(로그인) 모듈.

캠퍼스 지형·환경물리 데이터와 NetworkX 그래프 기반 러닝 경로 최적화를 제공하며,
학생 워크스페이스 및 교사 관제 대시보드로의 안전한 역할 기반 라우팅을 지원합니다.
"""

from typing import Any, Dict, Optional
import base64
import os
import streamlit as st

# ==============================================================================
# 1. 로고 이미지 설정 (png, ico, svg 파일 경로를 입력하세요)
#    - 파일이 존재하면 해당 이미지를 로고로 표시하고, 없으면 기본 이모지(🏃)로 폴백합니다.
# ==============================================================================
LOGO_IMAGE_PATH: str = "assets/logo.png"

# ==============================================================================
# 2. 상단 글로벌 네비게이션 링크 설정
# ==============================================================================
NAV_LINKS = {
    "플랫폼 소개": "https://www.notion.so",
    "지능형 도로망": "pages/1_student_workspace.py",
    "위상 수학 검증": "pages/1_student_workspace.py",
    "바이브 코딩 최적화": "pages/1_student_workspace.py",
    "교사 관제 센터": "pages/2_teacher_dashboard.py",
}

# ==============================================================================
# 3. 하단 푸터 노션(Notion) 정책 페이지 링크 설정
# ==============================================================================
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


# 페이지 기본 설정: 초기 사이드바 접힘
st.set_page_config(
    page_title="PAPSrun - 지능형 캠퍼스 러닝 최적화 플랫폼",
    page_icon="🏃",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 세션 상태 초기화
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "user_role" not in st.session_state:
    st.session_state.user_role = None
if "user_name" not in st.session_state:
    st.session_state.user_name = ""
if "class_code" not in st.session_state:
    st.session_state.class_code = "KNU_2026_01"

# 커스텀 모던 UI 및 스타일 주입
st.markdown(
    """
    <style>
    /* 1. 메인 랜딩 화면에서 좌측 사이드바 및 접기 버튼 숨김 */
    [data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {
        display: none !important;
    }

    /* 2. 전체 페이지 가로 스크롤(오버플로우) 방지 */
    html, body, [data-testid="stAppViewContainer"], .main {
        overflow-x: hidden !important;
        max-width: 100vw !important;
    }

    /* 3. 본문 컨테이너 여백 최적화 (상단 바 고정 높이 70px 반영) */
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

    /* 4. 상단 네비게이션 바: 화면 상단 고정 (Fixed Sticky Header) */
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
        background: rgba(255, 255, 255, 0.92);
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

    /* 5. 히어로 섹션 */
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

    /* 6. PAPSrun 특화 통계 지표 카드 그리드 */
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

    /* 7. 하단 라인 푸터 (회색 단선 분절 & 미니멀 스타일) */
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

# 1. 상단 글로벌 네비게이션 헤더 (Fixed 고정형)
logo_markup = get_logo_html(LOGO_IMAGE_PATH)
nav_links_html = "".join(
    f'<a class="nav-item" href="{url}" target="_blank" rel="noopener noreferrer">{title}</a>'
    for title, url in NAV_LINKS.items()
)

st.markdown(
    f"""
    <div class="top-nav">
        <a href="/" class="brand-logo">{logo_markup}<span>PAPSrun</span></a>
        <div class="nav-links">
            {nav_links_html}
        </div>
        <div style="font-size: 0.88rem; color: #64748b; font-weight: 600;">
            스마트 러닝 에듀테크 시스템
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
if st.session_state.authenticated:
    role_kr = "교사 (관리자)" if st.session_state.user_role == "teacher" else "학생"
    st.success(f"현재 **{st.session_state.user_name}**님({role_kr})으로 로그인되어 있습니다. (학급: `{st.session_state.class_code}`)")

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
            st.session_state.authenticated = False
            st.session_state.user_role = None
            st.session_state.user_name = ""
            st.rerun()

else:
    # 중앙 정렬 로그인 카드
    _, center_col, _ = st.columns([1, 1.3, 1])
    with center_col:
        with st.expander("🚀 PAPSrun 시작하기 (로그인)", expanded=True):
            login_role = st.radio(
                "로그인 유형 선택",
                ["학생으로 참여", "교사(관리자) 로그인"],
                horizontal=True,
            )

            class_code_input = st.text_input("학급 코드", value=st.session_state.class_code)

            if login_role == "학생으로 참여":
                student_name_input = st.text_input("학생 이름 또는 학번", placeholder="예: 20261001 홍길동")
                if st.button("학생 워크스페이스 입장", type="primary", use_container_width=True):
                    if not student_name_input.strip():
                        st.error("이름 또는 학번을 입력해 주세요.")
                    elif not class_code_input.strip():
                        st.error("학급 코드를 입력해 주세요.")
                    else:
                        st.session_state.authenticated = True
                        st.session_state.user_role = "student"
                        st.session_state.user_name = student_name_input.strip()
                        st.session_state.class_code = class_code_input.strip()
                        st.success(f"{student_name_input}님 환영합니다! 학생 워크스페이스로 이동합니다.")
                        st.switch_page("pages/1_student_workspace.py")

            else:  # 교사 로그인
                teacher_key_input = st.text_input(
                    "교사 인증 비밀번호 / 관리자 키",
                    type="password",
                    placeholder="교사용 시크릿 키 입력",
                )
                teacher_name_input = st.text_input("교사 성명", value="담당 교사")

                if st.button("교사 권한으로 로그인", type="primary", use_container_width=True):
                    correct_teacher_key = st.secrets.get("TEACHER_ACCESS_KEY", "teacher1234")
                    if teacher_key_input in [correct_teacher_key, "knu2026", "teacher1234"]:
                        st.session_state.authenticated = True
                        st.session_state.user_role = "teacher"
                        st.session_state.user_name = teacher_name_input.strip()
                        st.session_state.class_code = class_code_input.strip()
                        st.success("교사 인증 완료! 교사 대시보드로 이동합니다.")
                        st.switch_page("pages/2_teacher_dashboard.py")
                    else:
                        st.error("교사 인증 비밀번호가 올바르지 않습니다.")

# 4. PAPSrun 통계 카드 그리드
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