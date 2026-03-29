import streamlit as st
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import json
import time
import re
import anthropic

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
    .tag { background:#1e1e30; color:#6868a8; padding:2px 10px; border-radius:20px; font-size:12px; margin-right:5px; }
    .refined-tag { background:#0d1a00; color:#34d399; padding:2px 10px; border-radius:20px; font-size:12px; }
    .skipped-tag { background:#1a0d00; color:#fbbf24; padding:2px 10px; border-radius:20px; font-size:12px; }
    h1, h2, h3 { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# ██  CONFIGURE HERE                                                          ██
# ════════════════════════════════════════════════════════════════════════════════

ANTHROPIC_KEY = "PASTE_YOUR_ANTHROPIC_API_KEY_HERE"
# Get free at: https://console.anthropic.com → API Keys

CREDS_JSON = """
PASTE_YOUR_FULL_SERVICE_ACCOUNT_JSON_HERE
"""

SCORE_THRESHOLD = 70  # Refine resume only if score < this

# ════════════════════════════════════════════════════════════════════════════════
# ██  END CONFIG                                                              ██
# ════════════════════════════════════════════════════════════════════════════════

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
    """Load all rows from selected tab."""
    try:
        client = get_gspread_client()
        sh     = client.open(sheet_name)
        ws     = sh.worksheet(tab_name)
        rows   = ws.get_all_records()
        return ws, rows, None
    except Exception as e:
        return None, [], str(e)

def update_row(ws, row_num, score, verdict, tailored_resume, status):
    """Update columns M(13), N(14), O(15), L(12) for a given row."""
    try:
        ws.update_cell(row_num, 12, status)          # L — Status
        ws.update_cell(row_num, 13, score)           # M — Match Score
        ws.update_cell(row_num, 14, verdict)         # N — Verdict
        ws.update_cell(row_num, 15, tailored_resume) # O — Tailored Resume
        time.sleep(0.4)
    except Exception as e:
        st.warning(f"Row update error: {e}")

def score_job(client, resume, job_title, company, jd):
    """Step 1 — just score, no refinement yet."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=300,
        system="""You are a resume-job match analyser. 
Return ONLY valid JSON, no markdown, no explanation.
Format: {"score": 0-100, "verdict": "Strong Match"|"Good Match"|"Weak Match", "gap_reasons": ["reason1","reason2"]}""",
        messages=[{
            "role": "user",
            "content": f"""Score this resume against the job.

JOB: {job_title} at {company}
JD: {jd[:1000]}

RESUME:
{resume[:2000]}

Return only JSON."""
        }]
    )
    raw = message.content[0].text.strip()
    return json.loads(raw.replace("```json","").replace("```","").strip())

def refine_resume(client, resume, job_title, company, jd, gap_reasons):
    """Step 2 — only called if score < threshold."""
    message = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1500,
        system="""You are an expert resume writer for PM and Growth roles.
The applicant is Nabhey — Product Analyst, Goa India, targeting MNC remote/hybrid roles.
Return ONLY the full refined resume as plain text. No JSON, no markdown headers, no explanation.
Rewrite to maximise match with the job while staying truthful.""",
        messages=[{
            "role": "user",
            "content": f"""Refine this resume for the job below.

JOB: {job_title} at {company}
JD: {jd[:1000]}

GAPS TO ADDRESS:
{chr(10).join(f'- {g}' for g in gap_reasons)}

ORIGINAL RESUME:
{resume}

Return the full refined resume as plain text."""
        }]
    )
    return message.content[0].text.strip()

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🧠 App 2 — Resume Matcher & Refiner")
st.caption("Scores each job against your resume. Refines resume if score < 70%.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Settings")

    st.subheader("Google Sheet")
    sheet_name = st.text_input("Sheet File Name", value="Job Pipeline",
                               help="Same sheet name as App 1")

    # Load available tabs
    tab_name = None
    if "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON and CREDS_JSON.strip():
        try:
            client_gs = get_gspread_client()
            sh = client_gs.open(sheet_name)
            tabs = [ws.title for ws in sh.worksheets()]
            if tabs:
                tab_name = st.selectbox("Select Run Tab", options=tabs, index=0)
            else:
                st.warning("No tabs found in sheet.")
        except Exception as e:
            st.error(f"Sheet error: {e}")

    st.divider()
    st.subheader("Your Resume")
    st.caption("Paste your base resume — Claude will tailor it per job")
    resume_text = st.text_area(
        "resume",
        height=300,
        placeholder="Paste your full resume here...\n\nExperience, skills, education, achievements...",
        label_visibility="collapsed"
    )
    st.caption(f"{len(resume_text.split())} words")

    st.divider()
    st.subheader("Threshold")
    threshold = st.slider(
        "Refine if score below (%)",
        min_value=40, max_value=90,
        value=SCORE_THRESHOLD,
        help="Jobs below this score will get a tailored resume"
    )

# ── Config check ──────────────────────────────────────────────────────────────
config_ok = True
if "PASTE_YOUR_ANTHROPIC_API_KEY_HERE" in ANTHROPIC_KEY:
    st.warning("⚠️ Add your Anthropic API key in the CONFIG section of `app2_matcher.py`")
    config_ok = False
if not resume_text.strip():
    st.info("📄 Paste your resume in the sidebar to begin.")
    config_ok = False

# ── Load jobs ─────────────────────────────────────────────────────────────────
ws, rows, load_err = None, [], None
if tab_name and "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON:
    ws, rows, load_err = load_jobs(sheet_name, tab_name)
    if load_err:
        st.error(f"Load error: {load_err}")

new_jobs = [r for r in rows if r.get("Status") == "New"]

# Stats
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Jobs",    len(rows))
c2.metric("New / Pending", len(new_jobs))
c3.metric("Threshold",     f"{threshold}%")
c4.metric("Last Run",      st.session_state.get("last_run_2", "Never"))

st.divider()

if rows and not new_jobs:
    st.success("✅ All jobs already processed!")

if new_jobs:
    st.markdown(f"**{len(new_jobs)} jobs** ready to score from tab **{tab_name}**")

run_btn = st.button(
    "▶ Run Matcher",
    type="primary",
    disabled=(not config_ok or not ws or not new_jobs),
)

# ── Matching logic ────────────────────────────────────────────────────────────
if run_btn:
    anthropic_client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    progress = st.progress(0, text="Starting...")
    total    = len(new_jobs)
    results  = []

    for i, job in enumerate(new_jobs):
        title   = job.get("Title", "")
        company = job.get("Company", "")
        jd      = job.get("JD Summary", "")
        row_num = i + 2  # +2 for header row

        progress.progress(i / total, text=f"Scoring: {title} @ {company}...")

        # Step 1 — Score
        try:
            score_data   = score_job(anthropic_client, resume_text, title, company, jd)
            score        = score_data.get("score", 0)
            verdict      = score_data.get("verdict", "Unknown")
            gap_reasons  = score_data.get("gap_reasons", [])
        except Exception as e:
            st.warning(f"Score failed for {title}: {e}")
            continue

        # Step 2 — Refine only if below threshold
        tailored = ""
        if score < threshold:
            progress.progress(i / total, text=f"Refining resume for: {title}...")
            try:
                tailored = refine_resume(
                    anthropic_client, resume_text,
                    title, company, jd, gap_reasons
                )
                status = "Refined"
            except Exception as e:
                st.warning(f"Refine failed for {title}: {e}")
                status = "Score Only"
        else:
            status = "Good Match"

        # Update sheet
        update_row(ws, row_num, score, verdict, tailored, status)

        results.append({
            "title":   title,
            "company": company,
            "score":   score,
            "verdict": verdict,
            "status":  status,
            "refined": bool(tailored),
        })
        time.sleep(1)

    progress.progress(1.0, text="Done!")
    progress.empty()
    st.session_state["last_run_2"] = datetime.now().strftime("%H:%M, %d %b")

    # Summary
    refined_count = sum(1 for r in results if r["refined"])
    good_count    = sum(1 for r in results if not r["refined"])
    st.success(f"✅ Done — {len(results)} jobs scored. {refined_count} resumes refined, {good_count} already good match.")

    # Results cards
    st.subheader("Results")
    for r in results:
        score_class = "score-high" if r["score"] >= 70 else "score-mid" if r["score"] >= 50 else "score-low"
        status_tag  = f'<span class="refined-tag">✨ Refined</span>' if r["refined"] else f'<span class="skipped-tag">✓ Good Match</span>'
        st.markdown(f"""
        <div class="job-card">
            <strong>{r['title']}</strong> — {r['company']} &nbsp; {status_tag}<br/>
            <span class="{score_class}">{r['score']}%</span>
            <span style="color:#6868a8; font-size:13px; margin-left:8px;">{r['verdict']}</span>
        </div>""", unsafe_allow_html=True)

# ── Preview existing results ──────────────────────────────────────────────────
if rows and not run_btn:
    processed = [r for r in rows if r.get("Status") not in ("New", "")]
    if processed:
        st.subheader(f"Previously Processed ({len(processed)})")
        for r in processed[:10]:
            score = r.get("Match Score", "")
            try:
                score_int = int(float(score))
                score_class = "score-high" if score_int >= 70 else "score-mid" if score_int >= 50 else "score-low"
                score_str = f'<span class="{score_class}">{score_int}%</span>'
            except:
                score_str = f'<span class="tag">{score}</span>'
            st.markdown(f"""
            <div class="job-card">
                <strong>{r.get('Title','')}</strong> — {r.get('Company','')} &nbsp;
                <span class="tag">{r.get('Status','')}</span><br/>
                {score_str}
                <span style="color:#6868a8; font-size:13px; margin-left:8px;">{r.get('Verdict','')}</span>
            </div>""", unsafe_allow_html=True)
