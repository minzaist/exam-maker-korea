from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
from streamlit_cookies_controller import CookieController

from exports import (
    make_answer_pdf,
    make_docx_zip,
    make_question_pdf,
    natural_language_output,
    validate_pdf_bytes,
)
from generator import GenerationError, generate_exam
from storage import Storage, SupabaseStorage, User
from ui import CSS, card_header


APP_DIR = Path(__file__).resolve().parent
EXAM_TYPES = ["객관식", "단답형", "서술형", "논술형", "OX형", "빈칸 채우기", "사례 분석형"]
AUTH_COOKIE = "exam_maker_session"
AUTH_DAYS = 30


def secret(name: str, default: str = "") -> str:
    try:
        value = st.secrets.get(name, default)
    except Exception:
        value = default
    return str(os.environ.get(name, value) or default)


@st.cache_resource
def get_storage(
    path: str,
    pepper: str,
    admin_service_number: str,
    admin_name: str,
    supabase_url: str,
    supabase_secret_key: str,
) -> Storage | SupabaseStorage:
    if supabase_url and supabase_secret_key:
        return SupabaseStorage(
            supabase_url,
            supabase_secret_key,
            pepper,
            admin_service_number,
            admin_name,
        )
    return Storage(path, pepper, admin_service_number, admin_name)


def init() -> Storage | SupabaseStorage:
    st.set_page_config(page_title="시험제작소", page_icon="📝", layout="wide", initial_sidebar_state="collapsed")
    st.markdown(CSS, unsafe_allow_html=True)
    db_path = secret("DATABASE_PATH", str(APP_DIR / "data" / "exam_maker.db"))
    pepper = secret("AUTH_PEPPER", "local-development-pepper-change-in-deployment")
    admin_service_number = secret("ADMIN_SERVICE_NUMBER")
    admin_name = secret("ADMIN_NAME")
    supabase_url = secret("SUPABASE_URL")
    supabase_secret_key = secret("SUPABASE_SECRET_KEY")
    return get_storage(
        db_path,
        pepper,
        admin_service_number,
        admin_name,
        supabase_url,
        supabase_secret_key,
    )


def browser_user_agent() -> str:
    try:
        return str(st.context.headers.get("User-Agent", ""))
    except Exception:
        return ""


def complete_login(
    storage: Storage | SupabaseStorage,
    cookies: CookieController,
    user: User,
    remember: bool,
    method: str,
) -> None:
    storage.record_login(user.id, method, browser_user_agent())
    st.session_state.user = user
    if remember:
        token = storage.create_auth_session(user.id, AUTH_DAYS)
        expires = datetime.now(timezone.utc) + timedelta(days=AUTH_DAYS)
        cookies.set(AUTH_COOKIE, token, expires=expires, secure=True, same_site="strict")
        st.session_state.auth_token = token


def login_screen(storage: Storage | SupabaseStorage, cookies: CookieController) -> None:
    st.markdown('<div class="login-wrap">', unsafe_allow_html=True)
    st.markdown('<div class="login-logo">📝</div><div class="login-title">시험제작소</div><div class="login-copy">강의자료가 공부하기 좋은 문제집으로 바뀌어요.</div>', unsafe_allow_html=True)
    with st.container(border=True):
        login_tab, signup_tab = st.tabs(["로그인", "처음이에요"])
        with login_tab:
            with st.form("login_form", clear_on_submit=False):
                service_number = st.text_input("군번", placeholder="예: 24-12345678")
                name = st.text_input("이름", placeholder="이름을 입력하세요")
                remember = st.checkbox("이 브라우저에서 로그인 유지 (30일)", value=True)
                submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)
                if submitted:
                    try:
                        user = storage.login(service_number, name)
                    except (ValueError, RuntimeError) as exc:
                        st.error(str(exc))
                    else:
                        if user:
                            complete_login(storage, cookies, user, remember, "직접 로그인")
                            return
                        st.error("군번 또는 이름을 확인해주세요.")
        with signup_tab:
            with st.form("signup_form", clear_on_submit=False):
                service_number = st.text_input("군번", placeholder="예: 24-12345678", key="signup_number")
                name = st.text_input("이름", placeholder="실명을 입력하세요", key="signup_name")
                st.markdown(
                    '<div class="privacy-note">계정 식별을 위해 이름과 마스킹된 군번을 저장합니다. 로그인 시각·방식·브라우저 정보와 문제 생성 메타데이터가 운영 기록에 남고 관리자에게 공개됩니다. 군번 원문, PDF 원문, 생성된 문제 전문은 저장하지 않습니다.</div>',
                    unsafe_allow_html=True,
                )
                consent = st.checkbox("위 개인정보 처리 및 운영 기록 안내에 동의합니다.")
                remember = st.checkbox("이 브라우저에서 로그인 유지 (30일)", value=True, key="signup_remember")
                submitted = st.form_submit_button("가입하고 시작하기", type="primary", use_container_width=True)
                if submitted:
                    try:
                        user = storage.signup(service_number, name, consent)
                    except (ValueError, RuntimeError) as exc:
                        st.error(str(exc))
                    else:
                        complete_login(storage, cookies, user, remember, "회원가입")
                        return
    st.markdown("</div>", unsafe_allow_html=True)


def render_header(storage: Storage | SupabaseStorage, cookies: CookieController, user: User) -> None:
    admin_tag = " · 관리자" if user.is_admin else ""
    st.markdown(
        f"""
        <div class="brand-row">
          <div class="brand"><div class="brand-mark">✓</div>시험제작소</div>
          <div class="user-chip">{user.name} · {user.masked_service_number}{admin_tag}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    left, right = st.columns([8, 2])
    with right:
        if st.button("로그아웃", use_container_width=True):
            token = st.session_state.get("auth_token") or st.context.cookies.get(AUTH_COOKIE, "")
            storage.revoke_auth_session(str(token))
            cookies.remove(AUTH_COOKIE, secure=True, same_site="strict")
            for key in list(st.session_state):
                del st.session_state[key]
            st.rerun()


def render_question(question: dict) -> None:
    difficulty_class = "high" if question.get("difficulty") == "상" else "gray"
    options = "".join(
        f'<div class="option">{index}) {option}</div>'
        for index, option in enumerate(question.get("options") or [], 1)
    )
    pages = ", ".join(f"PDF p.{value}" for value in question.get("pages") or [])
    st.markdown(
        f"""
        <div class="question-card">
          <div class="question-meta">
            <span class="pill">{question.get('topic')}</span>
            <span class="pill gray">{question.get('type')}</span>
            <span class="pill {difficulty_class}">{question.get('difficulty')}</span>
          </div>
          <div class="question-text">{question.get('number')}. {question.get('question')}</div>
          {options}
          <div style="margin-top:.65rem;color:#8b95a1;font-size:.78rem">근거: {pages}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def build_artifacts(data: dict) -> dict:
    question_pdf = make_question_pdf(data)
    answer_pdf = make_answer_pdf(data)
    title = str(data.get("title") or "예상문제집")
    question_qa = validate_pdf_bytes(question_pdf, title)
    answer_qa = validate_pdf_bytes(answer_pdf, title)
    if not question_qa["ok"] or not answer_qa["ok"]:
        problems = question_qa["errors"] + answer_qa["errors"]
        raise RuntimeError("PDF 교차검증 실패: " + " / ".join(problems))
    return {
        "question_pdf": question_pdf,
        "answer_pdf": answer_pdf,
        "docx_zip": make_docx_zip(data),
        "text": natural_language_output(data),
        "question_qa": question_qa,
        "answer_qa": answer_qa,
    }


def render_results(data: dict, artifacts: dict, warnings: list[str]) -> None:
    st.markdown('<div class="result-shell">', unsafe_allow_html=True)
    st.subheader(data.get("title") or "예상문제집")
    question_tab, answer_tab, analysis_tab, text_tab = st.tabs(["예상문제", "정답·해설", "출제 분석", "전체 텍스트"])
    with question_tab:
        for question in data.get("questions", []):
            render_question(question)
    with answer_tab:
        for question in data.get("questions", []):
            answer = question.get("answer") or ""
            if question.get("type") == "객관식" and question.get("answer_index"):
                answer = f"{question.get('answer_index')}번 · {answer}"
            with st.expander(f"{question.get('number')}번 · {question.get('topic')}", expanded=False):
                st.markdown(f'<div class="answer-box"><b>정답/모범답안</b><br>{answer}</div>', unsafe_allow_html=True)
                st.markdown(f"**해설**  \n{question.get('explanation') or ''}")
                st.markdown(f"**풀이 과정**  \n{question.get('reasoning') or ''}")
                st.markdown(f"**주의할 오개념**  \n{question.get('misconceptions') or ''}")
    with analysis_tab:
        analysis = data.get("analysis") or {}
        st.write(analysis.get("scope") or data.get("source_scope"))
        topic_counts = analysis.get("topic_counts") or []
        if topic_counts:
            st.dataframe(topic_counts, use_container_width=True, hide_index=True)
        c1, c2, c3 = st.columns(3)
        counts = analysis.get("difficulty_counts") or {}
        c1.metric("하", counts.get("하", 0))
        c2.metric("중", counts.get("중", 0))
        c3.metric("상", counts.get("상", 0))
        st.markdown("**핵심 출제 개념**")
        st.write(" · ".join(analysis.get("core_concepts") or []) or "없음")
        st.markdown("**중요 학습 주제**")
        st.write(" · ".join(analysis.get("important_topics") or []) or "없음")
        st.markdown("**근거 부족으로 제외한 내용**")
        st.write(" · ".join(analysis.get("excluded_topics") or []) or "없음")
        with st.expander("자동 검수 결과"):
            st.json(analysis.get("quality_check") or {})
            if warnings:
                for warning in warnings:
                    st.warning(warning)
            else:
                st.success("문항 구조, 페이지 표기, 객관식 선지 균형 검사를 통과했습니다.")
            st.success(
                f"PDF 렌더링 교차검증 통과 · 문제집 {artifacts['question_qa']['page_count']}쪽 · 해설 {artifacts['answer_qa']['page_count']}쪽"
            )
    with text_tab:
        st.text_area("복사해서 바로 쓸 수 있는 전체 내용", artifacts["text"], height=520)

    st.markdown("#### 파일로 받기")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.download_button(
            "한글/Word 문서 2종 (.zip)",
            data=artifacts["docx_zip"],
            file_name="시험제작소_문제집과해설_DOCX.zip",
            mime="application/zip",
            use_container_width=True,
        )
    with c2:
        st.download_button(
            "예상문제집 PDF",
            data=artifacts["question_pdf"],
            file_name="예상문제집.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with c3:
        st.download_button(
            "모범답안 PDF",
            data=artifacts["answer_pdf"],
            file_name="모범답안_및_해설.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    st.caption("DOCX 파일은 한컴오피스 한글과 Microsoft Word에서 열 수 있습니다.")
    st.markdown("</div>", unsafe_allow_html=True)


def render_admin(storage: Storage | SupabaseStorage) -> None:
    st.markdown("### 운영 기록")
    st.caption(
        f"가입 시 안내·동의한 범위의 메타데이터만 표시합니다. PDF 원문과 생성된 문제 전문은 저장하지 않습니다. · {storage.backend_name}"
    )
    stats = storage.stats()
    c1, c2, c3 = st.columns(3)
    c1.metric("가입 계정", stats["users"])
    c2.metric("전체 요청", stats["total"])
    c3.metric("완료", stats["completed"])
    generation_tab, login_tab = st.tabs(["문제 생성 기록", "로그인 기록"])
    with generation_tab:
        rows = storage.list_activities()
        if not rows:
            st.info("아직 생성 기록이 없습니다.")
        else:
            display = []
            for row in rows:
                display.append(
                    {
                        "시간(UTC)": row["created_at"],
                        "계정": f"{row['name']} · {row['masked_service_number']}",
                        "파일": ", ".join(row["file_names"]),
                        "유형": ", ".join(row["exam_types"]),
                        "문항": row["question_count"],
                        "제목 힌트": row["title_hint"],
                        "추가 요청": row["additional_notes"],
                        "상태": row["status"],
                        "결과": row["result_title"],
                    }
                )
            st.dataframe(display, use_container_width=True, hide_index=True)
            st.download_button(
                "문제 생성 기록 내려받기",
                data=json.dumps(rows, ensure_ascii=False, indent=2),
                file_name="시험제작소_문제생성기록.json",
                mime="application/json",
            )
    with login_tab:
        login_rows = storage.list_login_events()
        if not login_rows:
            st.info("아직 로그인 기록이 없습니다.")
        else:
            login_display = [
                {
                    "시간(UTC)": row["created_at"],
                    "계정": f"{row['name']} · {row['masked_service_number']}",
                    "방식": row["method"],
                    "브라우저": row["user_agent"],
                }
                for row in login_rows
            ]
            st.dataframe(login_display, use_container_width=True, hide_index=True)
            st.download_button(
                "로그인 기록 내려받기",
                data=json.dumps(login_rows, ensure_ascii=False, indent=2),
                file_name="시험제작소_로그인기록.json",
                mime="application/json",
            )


def main_screen(storage: Storage | SupabaseStorage, cookies: CookieController, user: User) -> None:
    render_header(storage, cookies, user)
    if user.is_admin:
        home_tab, admin_tab = st.tabs(["문제 만들기", "운영 기록"])
    else:
        home_tab = st.container()
        admin_tab = None

    with home_tab:
        st.markdown(
            """
            <div class="hero">
              <span class="hero-badge">PDF → 대학 시험 문제집</span>
              <h1>공부할 자료만 올리세요.<br>문제는 제가 만들게요.</h1>
              <p>강의자료의 핵심을 골고루 짚고, 근거 페이지와 해설까지 한 번에 정리합니다.</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        left, right = st.columns(2, gap="medium")
        with left:
            with st.container(border=True):
                st.markdown(card_header("STEP 1", "시험 범위 올리기", "강의자료·교재·논문 PDF를 최대 49MB까지 올려주세요."), unsafe_allow_html=True)
                uploaded_files = st.file_uploader(
                    "PDF 파일",
                    type=["pdf"],
                    accept_multiple_files=True,
                    label_visibility="collapsed",
                )
                if uploaded_files:
                    total_size = sum(file.size for file in uploaded_files)
                    st.caption(f"{len(uploaded_files)}개 파일 · {total_size / 1024 / 1024:.1f}MB")
        with right:
            with st.container(border=True):
                st.markdown(card_header("STEP 2", "문제 스타일 고르기", "유형을 여러 개 선택하면 자료에 맞게 비율을 나눠드려요."), unsafe_allow_html=True)
                exam_types = st.multiselect("출제 유형", EXAM_TYPES, default=["객관식"])
                title_hint = st.text_input("과목명 또는 제목", placeholder="예: 조직행동론 중간고사")
                additional_notes = st.text_area(
                    "참고해야 할 점",
                    placeholder="예: 3장은 비중을 높이고, 계산 문제는 제외해줘.",
                    height=112,
                )
                with st.expander("문항 수 설정"):
                    question_count = st.slider("총 문항 수", min_value=6, max_value=30, value=12, step=1)

        st.markdown('<div class="y-connector"><div class="y-stem"></div></div>', unsafe_allow_html=True)
        st.markdown("### 결과물 만들기")
        st.caption("자료 전체 분석 → 문항 생성 → 정답 대조 → PDF 렌더링 검증 순서로 진행됩니다.")
        generate_clicked = st.button("예상문제집 만들기", type="primary", use_container_width=True)

        if generate_clicked:
            if not uploaded_files:
                st.error("시험 범위 PDF를 한 개 이상 올려주세요.")
            elif not exam_types:
                st.error("출제 유형을 한 개 이상 선택해주세요.")
            elif (
                not user.is_admin
                and storage.generation_count_today(user.id)
                >= int(secret("DAILY_GENERATION_LIMIT", "3"))
            ):
                st.error("오늘의 문제집 생성 횟수를 모두 사용했습니다. 내일 다시 이용해주세요.")
            else:
                file_payloads = [(file.name, file.getvalue()) for file in uploaded_files]
                activity_id = storage.start_activity(
                    user.id,
                    [name for name, _ in file_payloads],
                    exam_types,
                    question_count,
                    title_hint,
                    additional_notes,
                )
                api_key = secret("OPENAI_API_KEY")
                model = secret("OPENAI_MODEL", "gpt-4.1")
                safety_id = hashlib.sha256(f"exam-maker:{user.id}".encode()).hexdigest()
                try:
                    with st.status("PDF를 읽고 문제를 설계하고 있어요…", expanded=True) as status:
                        st.write("전체 페이지와 핵심 주제를 분석하는 중")
                        result = generate_exam(
                            api_key,
                            model,
                            file_payloads,
                            exam_types,
                            question_count,
                            additional_notes,
                            title_hint,
                            safety_id,
                        )
                        st.write("문항과 정답의 구조를 교차검증하는 중")
                        artifacts = build_artifacts(result.data)
                        status.update(label="문제집이 완성됐어요", state="complete", expanded=False)
                    storage.finish_activity(activity_id, str(result.data.get("title") or ""))
                    st.session_state.result_data = result.data
                    st.session_state.result_artifacts = artifacts
                    st.session_state.result_warnings = result.warnings
                except (GenerationError, RuntimeError, ValueError) as exc:
                    storage.fail_activity(activity_id, str(exc))
                    st.error(str(exc))

        if "result_data" in st.session_state:
            render_results(
                st.session_state.result_data,
                st.session_state.result_artifacts,
                st.session_state.get("result_warnings", []),
            )
        else:
            st.markdown(
                '<div class="result-shell"><div class="result-empty"><div><div class="icon">🪄</div><strong>완성된 문제집이 여기에 나타나요</strong>문제와 해설을 확인하고 DOCX·PDF로 바로 내려받을 수 있어요.</div></div></div>',
                unsafe_allow_html=True,
            )
        st.markdown(
            '<div class="privacy-note" style="margin-top:1rem">개인정보 안내 · 이름과 마스킹 군번, 로그인 기록, 생성 요청 메타데이터는 서비스 운영을 위해 저장되며 관리자에게 공개됩니다. 군번 원문, 업로드한 PDF 원문과 생성된 결과 전문은 운영 기록에 저장하지 않습니다.</div>',
            unsafe_allow_html=True,
        )
        if not user.is_admin:
            daily_limit = int(secret("DAILY_GENERATION_LIMIT", "3"))
            used_today = storage.generation_count_today(user.id)
            st.caption(f"오늘 생성 {used_today}/{daily_limit}회 · 과도한 API 사용을 막기 위한 계정별 한도입니다.")

    if admin_tab is not None:
        with admin_tab:
            render_admin(storage)


def main() -> None:
    storage = init()
    cookies = CookieController(key="exam_maker_cookie_controller")
    user = st.session_state.get("user")
    if not isinstance(user, User):
        token = str(st.context.cookies.get(AUTH_COOKIE, "") or "")
        if token:
            restored = storage.restore_auth_session(token)
            if restored:
                st.session_state.user = restored
                st.session_state.auth_token = token
                storage.record_login(restored.id, "자동 로그인", browser_user_agent())
                user = restored
    if not isinstance(user, User):
        login_screen(storage, cookies)
        return
    main_screen(storage, cookies, user)


if __name__ == "__main__":
    main()
