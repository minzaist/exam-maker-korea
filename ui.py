from __future__ import annotations


CSS = r"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Gowun+Dodum&family=Pretendard:wght@400;500;600;700;800&display=swap');

:root {
  --ink: #191f28;
  --muted: #6b7684;
  --blue: #3182f6;
  --surface: #ffffff;
  --line: #e5e8eb;
  --mint: #dff7ee;
  --peach: #fff0e6;
}

html, body, [class*="css"] { font-family: Pretendard, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
.stApp { background: #f5f7fa; color: var(--ink); }
.block-container { max-width: 1180px; padding-top: 1.5rem; padding-bottom: 4rem; }
#MainMenu, footer, header { visibility: hidden; }

.brand-row { display:flex; align-items:center; justify-content:space-between; gap:1rem; margin-bottom:1rem; }
.brand { display:flex; align-items:center; gap:.7rem; font-size:1.15rem; font-weight:800; }
.brand-mark { width:2.45rem; height:2.45rem; border-radius:14px; background:#3182f6; color:#fff; display:grid; place-items:center; box-shadow:0 8px 22px rgba(49,130,246,.25); }
.user-chip { color:#4e5968; background:#fff; border:1px solid #e5e8eb; border-radius:999px; padding:.55rem .9rem; font-size:.88rem; }
.hero { background:linear-gradient(135deg,#eaf3ff 0%,#f8fbff 52%,#fff3ec 100%); border:1px solid #e5edf8; border-radius:30px; padding:2rem 2.1rem; margin-bottom:1rem; position:relative; overflow:hidden; }
.hero:after { content:'✦'; position:absolute; right:2.2rem; top:.9rem; font-size:5rem; color:rgba(49,130,246,.12); transform:rotate(12deg); }
.hero h1 { font-size:clamp(2rem,5vw,3.5rem); line-height:1.12; letter-spacing:-.05em; margin:0 0 .65rem; font-weight:800; }
.hero p { margin:0; font-size:1.05rem; color:#4e5968; max-width:700px; line-height:1.7; }
.hero-badge { display:inline-block; margin-bottom:.8rem; border-radius:999px; background:#fff; padding:.35rem .75rem; color:#3182f6; font-weight:700; font-size:.82rem; box-shadow:0 3px 12px rgba(0,0,0,.04); }

[data-testid="stVerticalBlockBorderWrapper"] { background:#fff; border-radius:26px !important; border:1px solid #e8ebee !important; box-shadow:0 9px 30px rgba(27,31,35,.045); }
.card-head { min-height:4.7rem; }
.card-kicker { color:#3182f6; font-size:.8rem; font-weight:800; letter-spacing:.08em; }
.card-title { font-size:1.32rem; font-weight:800; letter-spacing:-.025em; margin:.24rem 0; }
.card-copy { color:#8b95a1; font-size:.88rem; line-height:1.5; }

[data-testid="stFileUploader"] { padding:.4rem 0 .1rem; }
[data-testid="stFileUploaderDropzone"] { min-height:180px; border:1.5px dashed #b8d5fb; background:#f8fbff; border-radius:22px; }
[data-testid="stFileUploaderDropzone"] button { min-height:46px; border-radius:14px; font-weight:700; }
.stTextInput input, .stTextArea textarea, [data-baseweb="select"] > div { border-radius:15px !important; border-color:#dfe3e8 !important; min-height:48px; }
.stTextArea textarea { padding:14px 16px; line-height:1.55; }
.stButton > button, .stDownloadButton > button { border-radius:16px; min-height:50px; font-weight:750; border:0; transition:all .15s ease; }
.stButton > button[kind="primary"] { background:#3182f6; box-shadow:0 10px 20px rgba(49,130,246,.2); }
.stButton > button:hover, .stDownloadButton > button:hover { transform:translateY(-1px); }

.y-connector { width:100%; height:58px; position:relative; margin:-3px 0 0; }
.y-connector:before, .y-connector:after { content:''; position:absolute; top:4px; width:calc(25% + 1px); height:2px; background:#d8e7fa; }
.y-connector:before { left:25%; transform:rotate(12deg); transform-origin:left; }
.y-connector:after { right:25%; transform:rotate(-12deg); transform-origin:right; }
.y-stem { position:absolute; left:50%; top:27px; width:2px; height:31px; background:#d8e7fa; }
.result-shell { background:#fff; border:1px solid #e8ebee; border-radius:28px; padding:1.2rem 1.25rem .6rem; box-shadow:0 12px 34px rgba(27,31,35,.05); }
.result-empty { min-height:235px; display:grid; place-items:center; text-align:center; color:#8b95a1; padding:2rem; }
.result-empty .icon { font-size:2.5rem; margin-bottom:.7rem; }
.result-empty strong { display:block; color:#4e5968; font-size:1.05rem; margin-bottom:.25rem; }

.question-card { border:1px solid #edf0f2; border-radius:20px; padding:1.05rem 1.1rem; margin:.7rem 0; background:#fff; }
.question-meta { display:flex; flex-wrap:wrap; gap:.35rem; margin-bottom:.55rem; }
.pill { display:inline-block; padding:.24rem .55rem; border-radius:999px; background:#eef6ff; color:#2272eb; font-size:.75rem; font-weight:700; }
.pill.gray { background:#f2f4f6; color:#6b7684; }
.pill.high { background:#fff0f0; color:#e34d59; }
.question-text { font-size:1rem; font-weight:650; line-height:1.65; color:#191f28; }
.option { padding:.42rem .7rem; margin:.3rem 0; border-radius:12px; background:#f8f9fa; color:#333d4b; }
.answer-box { padding:1rem; border-radius:16px; background:#f2f7ff; margin:.6rem 0; line-height:1.65; }
.privacy-note { border-radius:18px; background:#f8f9fa; padding:.9rem 1rem; color:#6b7684; font-size:.82rem; line-height:1.55; }
.login-wrap { max-width:500px; margin:5vh auto; }
.login-logo { text-align:center; font-size:2.2rem; margin-bottom:.4rem; }
.login-title { text-align:center; font-size:1.7rem; font-weight:800; letter-spacing:-.04em; }
.login-copy { text-align:center; color:#8b95a1; margin-bottom:1.25rem; }

@media (max-width: 760px) {
  .block-container { padding:1rem .85rem 3rem; }
  .hero { padding:1.5rem 1.25rem; border-radius:24px; }
  .hero:after { display:none; }
  .y-connector { height:32px; }
  .y-connector:before,.y-connector:after { display:none; }
  .y-stem { top:0; height:32px; }
  .user-chip { display:none; }
}
</style>
"""


def card_header(step: str, title: str, copy: str) -> str:
    return f"""
    <div class="card-head">
      <div class="card-kicker">{step}</div>
      <div class="card-title">{title}</div>
      <div class="card-copy">{copy}</div>
    </div>
    """

