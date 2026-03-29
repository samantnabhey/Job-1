import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import time
import re
import requests

st.set_page_config(page_title="App 2 — Resume Matcher", page_icon="🧠", layout="wide")

st.markdown("""
<style>
    .stApp { background: #0a0a0f; color: #e2e8f0; }
    .job-card {
        background: #0f0f1a; border: 1px solid #1e1e30;
        border-radius: 8px; padding: 16px; margin-bottom: 10px;
    }
    .score-high { color: #34d399; font-weight: bold; font-size: 18px; }
    .score-mid  { color: #fbbf24; font-weight: bold; font-size: 18px; }
    .score-low  { color: #f87171; font-weight: bold; font-size: 18px; }
    .tag         { background:#1e1e30; color:#6868a8; padding:2px 10px; border-radius:20px; font-size:12px; margin-right:5px; }
    .refined-tag { background:#0d1a00; color:#34d399; padding:2px 10px; border-radius:20px; font-size:12px; }
    .good-tag    { background:#0d1020; color:#38bdf8; padding:2px 10px; border-radius:20px; font-size:12px; }
    h1, h2, h3 { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# ██  CONFIGURE HERE                                                          ██
# ════════════════════════════════════════════════════════════════════════════════

# 1. GEMINI API KEY — free at https://aistudio.google.com → Get API Key
GEMINI_KEY = "AIzaSyBmdRww9IYs4xLA1OUCMrX3iqiJHbpm8z0"

# 2. SAME SERVICE ACCOUNT JSON as App 1
CREDS_JSON = """
{
  "type": "service_account",
  "project_id": "airy-gate-238512",
  "private_key_id": "51cf2f8c913a7f9c5a84daac96bebfe3ff5048db",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCkm3nqSAH1U+W9\nJsqvdUVWX4IBsdMSl/3zTXajWjzgBVZ/ID3VVevckHZ/Xy3Jo8Xi1LQIM2N3GnRD\nFmaIEi85VLkxmuicFcpZElkNnrXJ3PERvpjxYc5O4s+UVIuJl4Aj3rM9H0OqdzgS\nIPaokdxK7uzCLIQW0inl2Dxk0r4wkyh5vskD48HnXpcPnyMTKbuBvIP1Qneoe6jA\nkG1PnWqsYhqCdWwK2qJsruO+vI4bLjFEd9TkZVyaJ+QxAiIJ0cGf61qkVQCxCW7l\nhhC0dlVwGlVs8Gix3pZLyaJfpu16hKi5zF2RPPCpDcsuwZaXqLmyJIBycshQxrHR\nzLr6jikHAgMBAAECggEAI57ZhQ9MDTC4mHQajFmORaCpW4CFspJdjBcJQ1Q1tCyz\niRMLDm1nevVwDyQjnmzoV6u7wcKNFasN2a6xRWTZ/0gMQ2XITG6SuS+1QbNEl4hO\nSo66PhHyOTPvw6OABqhYPGrm0qU/WVYvNg0YE2ZtC3IknehQNTgJhQmEGDVantwA\njzm/mmS+hFQ3bpz6xXAGsFZVhjeCLw86VJ+MOG1sl5s3iU8CuTi/dVRD4X36r5Kg\ntD+ie2T4c0Tig9FemfPNAhp/dXXs3hMTmMkGmY0BLfcL7ZSCF/MJIbefYN/1QEpM\noNhtj/7M1NXo5nLaHXJ5VBKfxS10ey5fmRyszGUNsQKBgQDVUU5h/j1GNL2ZT68P\nEGNFrRXzFozF+C/aynHas7T6zgSzvqE8RbX0lnIWg9Nn6tmGJPs1kpRSuUsebm5p\nhsDubC5OHbCaCggaPfa66XA9JeHR7j6YcGz4Zt+azJUWhXLSL/QKSgasR7td1N5m\nWB8M+Qw9OLDcEUn24jn1x8Tj1QKBgQDFixm+D8nrRR4ylpftjfh1m4TG3mb7+f26\nCSW95ViWerC9lL3pOO6odM2MnJsFYUwt8PHw5ErsDb/SkEn04w3PqnN7EkKYLzgs\n+xbD5OFLLSeMLydeKix2NFM/V9/MxaO/A+xax57gRo6T+VGdV+VlaViZcOY/am7s\n1pXy66GzawKBgFTAZvn7/vBDyAh/Zjf/9NEcAZqBHRESmEC/KhkQSRlUfP3FAV5m\n+/HfTBix625gGmh3jO8t+4waXkQK8AcxKLoRdRxII4Av+CQk9kAwuw0wXdYAaBI8\nqK7QgIqKObmm74We08C6xIfyP/j5uBrFbCDFWh2AxpPIsrBKFWkXI5y5AoGAaGBr\nJaWqBwnqPsibVgWhtmKJ8ZopyBH7IoUa0A+Sk1AYetNQ1R4j3BZ7VUSaFGmoms2o\nyKOXgspxBI0AxsgB0Cw8AFdRoJ+yivHQwYj6EYK2VrfDkVmvTHWxVtLTiZsUPiWQ\niRbYt6AQTdd6bCy5JLBZBBpHTlKqcbGgYU5njikCgYBhVjeOZF0xFDKbSkCOJA2z\n30NyW/PPNabm++T1tUlQSyCttGcgX7CpMUXhyYiKSAL72Mw+tAr2qudggSyl1PMn\nTZg7Tv51cnNnUM01RAKrDCn33PfIdnU1mUG20EDRUcIvH7jN+MTbmCN9J6UxIjHC\nj/dbbQ1r1LnhO2KOrcGH2A==\n-----END PRIVATE KEY-----\n",
  "client_email": "nabhey@airy-gate-238512.iam.gserviceaccount.com",
  "client_id": "100136393772596802414",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token"
}"""

# 3. SCORE THRESHOLD — refine resume only if below this
SCORE_THRESHOLD = 70

# ════════════════════════════════════════════════════════════════════════════════
# ██  END CONFIG                                                              ██
# ════════════════════════════════════════════════════════════════════════════════

GEMINI_URL = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={GEMINI_KEY}"

def gemini(prompt, max_tokens=1500):
    """Call Gemini API."""
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": max_tokens, "temperature": 0.3}
    }
    try:
        r = requests.post(GEMINI_URL, json=body, timeout=30)
        r.raise_for_status()
        return r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
    except Exception as e:
        raise Exception(f"Gemini error: {e}")

def get_gspread_client():
    fixed = CREDS_JSON
    def fix_key(m):
        inner = m.group(1).replace('\n', '\\n')
        return f'"private_key": "{inner}"'
    fixed = re.sub(r'"private_key":\s*"(.*?)"(?=\s*,)', fix_key, fixed, flags=re.DOTALL)
    creds_dict = json.loads(fixed)
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    return gspread.authorize(creds)

def load_jobs(sheet_name, tab_name):
    try:
        client = get_gspread_client()
        sh     = client.open(sheet_name)
        ws     = sh.worksheet(tab_name)
        rows   = ws.get_all_records()
        return ws, rows, None
    except Exception as e:
        return None, [], str(e)

def update_row(ws, row_num, score, verdict, tailored_resume, status):
    try:
        ws.update_cell(row_num, 12, status)
        ws.update_cell(row_num, 13, score)
        ws.update_cell(row_num, 14, verdict)
        ws.update_cell(row_num, 15, tailored_resume[:40000] if tailored_resume else "")
        time.sleep(5)
    except Exception as e:
        st.warning(f"Row {row_num} update error: {e}")

def score_job(resume, job_title, company, jd):
    """Score resume vs JD. Returns dict with score, verdict, gap_reasons."""
    prompt = f"""You are a resume-job match analyser.
Return ONLY valid JSON, no markdown, no explanation.
Format: {{"score": 0-100, "verdict": "Strong Match or Good Match or Weak Match", "gap_reasons": ["reason1","reason2"]}}

JOB: {job_title} at {company}
JD: {jd[:800]}

RESUME:
{resume[:1500]}

Return only JSON."""
    raw = gemini(prompt, max_tokens=300)
    clean = raw.replace("```json","").replace("```","").strip()
    return json.loads(clean)

def refine_resume(resume, job_title, company, jd, gap_reasons):
    """Refine resume for this specific job. Only called if score < threshold."""
    prompt = f"""You are an expert resume writer for PM and Growth roles.
The applicant is Nabhey — Product Analyst based in Goa, India, targeting MNC remote/hybrid roles.

Rewrite the resume below to maximise match with the job.
Address the gaps listed. Stay truthful — do not invent experience.
Return ONLY the full refined resume as plain text. No JSON, no markdown.

JOB: {job_title} at {company}
JD: {jd[:800]}

GAPS TO ADDRESS:
{chr(10).join(f'- {g}' for g in gap_reasons)}

ORIGINAL RESUME:
{resume}

Return the full refined resume as plain text."""
    return gemini(prompt, max_tokens=1500)

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🧠 App 2 — Resume Matcher & Refiner")
st.caption("Scores each job vs your resume. Refines resume if score < threshold.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    st.subheader("Google Sheet")
    sheet_name = st.text_input("Sheet File Name", value="Job Pipeline",
                               help="Same name as App 1")

    tab_name = None
    if "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON and CREDS_JSON.strip():
        try:
            client_gs = get_gspread_client()
            sh_obj    = client_gs.open(sheet_name)
            tabs      = [ws.title for ws in sh_obj.worksheets()]
            if tabs:
                tab_name = st.selectbox("Select Run Tab", options=tabs, index=0)
            else:
                st.warning("No tabs found.")
        except Exception as e:
            st.error(f"Sheet error: {e}")

    st.divider()
    st.subheader("Your Base Resume")
    st.caption("Paste once — Claude refines it per job below threshold")
    resume_text = st.text_area(
        "resume",
        height=300,
        placeholder="Paste your full resume here...\n\nExperience, skills, education, achievements...",
        label_visibility="collapsed"
    )
    st.caption(f"{len(resume_text.split())} words")

    st.divider()
    st.subheader("Score Threshold")
    threshold = st.slider(
        "Refine if score below (%)",
        min_value=40, max_value=90,
        value=SCORE_THRESHOLD,
        help="Jobs below this score get a tailored resume"
    )
    st.caption(f"Jobs ≥ {threshold}% → Good Match (no refine)\nJobs < {threshold}% → Resume refined")

    st.divider()
    with st.expander("📖 Gemini API Key Setup"):
        st.markdown("""
1. Go to [aistudio.google.com](https://aistudio.google.com)
2. Sign in with Google
3. Click **Get API Key → Create API Key**
4. Copy key → paste in `GEMINI_KEY` in config section
5. Free tier: 15 requests/min, 1500 requests/day
        """)

# ── Config check ──────────────────────────────────────────────────────────────
config_ok = True
if "PASTE_YOUR_GEMINI_API_KEY_HERE" in GEMINI_KEY:
    st.warning("⚠️ Add Gemini API key in CONFIG section of `app2_matcher.py` — free at aistudio.google.com")
    config_ok = False
if "PASTE_YOUR_FULL_SERVICE" in CREDS_JSON:
    st.warning("⚠️ Add Service Account JSON in CONFIG section — same as App 1")
    config_ok = False
if not resume_text.strip():
    st.info("📄 Paste your resume in the sidebar to begin.")
    config_ok = False

# ── Load jobs ─────────────────────────────────────────────────────────────────
ws, rows = None, []
if tab_name and "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON:
    ws, rows, load_err = load_jobs(sheet_name, tab_name)
    if load_err:
        st.error(f"Load error: {load_err}")
    else:
        st.success(f"✅ Loaded {len(rows)} jobs from **{tab_name}**")

new_jobs = [r for r in rows if str(r.get("Status","")).strip() == "New"]

# Stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs",    len(rows))
c2.metric("Pending",       len(new_jobs))
c3.metric("Threshold",     f"{threshold}%")
c4.metric("Last Run",      st.session_state.get("last_run_2", "Never"))

st.divider()

if rows and not new_jobs:
    st.success("✅ All jobs already processed in this tab!")
elif new_jobs:
    st.markdown(f"**{len(new_jobs)} new jobs** to process from tab **{tab_name}**")

run_btn = st.button(
    "▶ Run Matcher",
    type="primary",
    disabled=(not config_ok or not ws or not new_jobs),
)

# ── Matching ──────────────────────────────────────────────────────────────────
if run_btn:
    progress = st.progress(0, text="Starting...")
    total    = len(new_jobs)
    results  = []

    for i, job in enumerate(new_jobs):
        title   = job.get("Title", "Unknown")
        company = job.get("Company", "Unknown")
        jd      = job.get("JD Summary", "")
        row_num = i + 2  # +2 accounts for header row

        # ── Step 1: Score ──
        progress.progress(i / total, text=f"📊 Scoring: {title[:30]} @ {company}...")
        try:
            score_data  = score_job(resume_text, title, company, jd)
            score       = int(score_data.get("score", 0))
            verdict     = score_data.get("verdict", "Unknown")
            gap_reasons = score_data.get("gap_reasons", [])
        except Exception as e:
            st.warning(f"⚠️ Score failed — {title}: {e}")
            continue

        # ── Step 2: Refine only if below threshold ──
        tailored = ""
        if score < threshold:
            progress.progress(i / total, text=f"✍️ Refining resume for: {title[:30]}...")
            try:
                tailored = refine_resume(resume_text, title, company, jd, gap_reasons)
                status   = "Refined"
            except Exception as e:
                st.warning(f"⚠️ Refine failed — {title}: {e}")
                status = "Score Only"
        else:
            status = "Good Match"

        # ── Update sheet ──
        update_row(ws, row_num, score, verdict, tailored, status)

        results.append({
            "title":   title,
            "company": company,
            "score":   score,
            "verdict": verdict,
            "status":  status,
            "refined": bool(tailored),
        })

        time.sleep(150)  # respect Gemini free tier rate limit

    progress.progress(1.0, text="All done!")
    progress.empty()

    st.session_state["last_run_2"] = datetime.now().strftime("%H:%M, %d %b")

    refined_count = sum(1 for r in results if r["refined"])
    good_count    = len(results) - refined_count
    st.success(f"✅ {len(results)} jobs processed — {good_count} good match, {refined_count} resumes refined.")

    st.subheader("Results")
    for r in results:
        sc   = r["score"]
        cls  = "score-high" if sc >= 70 else "score-mid" if sc >= 50 else "score-low"
        tag  = '<span class="refined-tag">✨ Refined</span>' if r["refined"] else '<span class="good-tag">✓ Good Match</span>'
        st.markdown(f"""
        <div class="job-card">
            <strong>{r['title']}</strong> — {r['company']} &nbsp; {tag}<br/>
            <span class="{cls}">{sc}%</span>
            <span style="color:#6868a8;font-size:13px;margin-left:8px;">{r['verdict']}</span>
        </div>""", unsafe_allow_html=True)

# ── Show previously processed ─────────────────────────────────────────────────
if rows and not run_btn:
    done = [r for r in rows if r.get("Status","") not in ("New","")]
    if done:
        st.subheader(f"Previously Processed ({len(done)})")
        for r in done[:15]:
            sc_raw = r.get("Match Score","")
            try:
                sc  = int(float(sc_raw))
                cls = "score-high" if sc >= 70 else "score-mid" if sc >= 50 else "score-low"
                sc_html = f'<span class="{cls}">{sc}%</span>'
            except:
                sc_html = f'<span class="tag">{sc_raw}</span>'
            st.markdown(f"""
            <div class="job-card">
                <strong>{r.get('Title','')}</strong> — {r.get('Company','')} &nbsp;
                <span class="tag">{r.get('Status','')}</span><br/>
                {sc_html}
                <span style="color:#6868a8;font-size:13px;margin-left:8px;">{r.get('Verdict','')}</span>
            </div>""", unsafe_allow_html=True)
