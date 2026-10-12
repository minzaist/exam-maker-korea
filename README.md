# 시험제작소

대학 시험 범위 PDF를 분석해 예상문제집, 모범답안·해설, 출제 분석을 만들고 DOCX/PDF로 내려받는 Streamlit 앱입니다.

## 주요 기능

- 여러 PDF 업로드와 출제 유형 다중 선택
- 객관식 5지선다·선지 길이 균형 자동검사
- 모든 문항의 원본 PDF 근거 페이지 표시
- 문제집/해설 PDF 렌더링 교차검증
- 한컴오피스에서 열 수 있는 DOCX 2종 ZIP 제공
- 군번+이름 기반 가입·로그인(군번 원문은 저장하지 않음)
- `로그인 유지` 선택 시 30일간 안전한 세션 유지
- 로그인 시각·방식·브라우저 정보를 관리자 전용 화면에서 조회·내려받기
- Supabase 영구 DB 연동으로 여러 컴퓨터에서 같은 계정 사용
- 안내·동의를 받은 생성 메타데이터 관리자 대시보드

## 로컬 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
mkdir -p .streamlit
cp .streamlit/secrets.example.toml .streamlit/secrets.toml
streamlit run app.py
```

`.streamlit/secrets.toml`에 실제 OpenAI API 키와 충분히 긴 임의의 `AUTH_PEPPER`를 설정하세요.

## 배포

1. Supabase 프로젝트의 SQL Editor에서 [`supabase_schema.sql`](supabase_schema.sql)을 한 번 실행합니다.
2. Supabase의 Connect 또는 Settings > API Keys에서 Project URL과 서버용 Secret Key를 확인합니다.
3. Streamlit Community Cloud에서 이 저장소의 `app.py`를 선택하고 Advanced settings의 Secrets에 아래 값을 입력합니다.

```toml
OPENAI_API_KEY = "sk-..."
OPENAI_MODEL = "gpt-4.1"
AUTH_PEPPER = "충분히 긴 임의 문자열"
ADMIN_SERVICE_NUMBER = "관리자 군번"
ADMIN_NAME = "관리자 이름"
DAILY_GENERATION_LIMIT = 3
SUPABASE_URL = "https://your-project.supabase.co"
SUPABASE_SECRET_KEY = "sb_secret_..."
```

`SUPABASE_URL`과 `SUPABASE_SECRET_KEY`가 있으면 Supabase를 사용하고, 없으면 로컬 개발용 SQLite로 자동 전환됩니다. Secret Key는 서버 전용이며 GitHub 저장소나 브라우저 코드에 넣으면 안 됩니다.

## 개인정보 설계

- 군번 원문은 DB에 저장하지 않고 HMAC 지문과 마스킹 값만 저장합니다.
- 로그인 유지 토큰은 브라우저에만 두고 DB에는 SHA-256 해시만 저장합니다. 로그아웃 시 서버 세션도 폐기합니다.
- 로그인 기록(시각·방식·브라우저 정보)은 가입 화면에서 안내·동의 후 저장됩니다.
- PDF 원문과 생성된 문제·답안 전문은 운영 로그에 저장하지 않습니다.
- 가입 화면과 홈 화면에 관리자 열람 범위를 명시합니다.
- API 비용 오남용을 줄이기 위해 일반 계정은 기본 하루 3회로 제한합니다.
