import streamlit as st
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import json
import time
import hashlib
import re

st.set_page_config(page_title="App 1 — Job Scraper", page_icon="🔍", layout="wide")

st.markdown("""
<style>
    .stApp { background: #0a0a0f; color: #e2e8f0; }
    .job-card {
        background: #0f0f1a; border: 1px solid #1e1e30;
        border-left: 3px solid #38bdf8; border-radius: 8px;
        padding: 14px 16px; margin-bottom: 10px;
    }
    .tag { background:#1e1e30; color:#6868a8; padding:2px 10px; border-radius:20px; font-size:12px; margin-right:5px; }
    .new-tag { background:#052016; color:#34d399; padding:2px 10px; border-radius:20px; font-size:12px; }
    h1, h2, h3 { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════════
# ██  CONFIGURE HERE — change these values, nothing else needs to be touched  ██
# ════════════════════════════════════════════════════════════════════════════════

# 1. ADZUNA — get free at https://developer.adzuna.com
ADZUNA_ID  = "PASTE_YOUR_ADZUNA_APP_ID_HERE"
ADZUNA_KEY = "PASTE_YOUR_ADZUNA_APP_KEY_HERE"

# 2. JSEARCH — get free at https://rapidapi.com → search JSearch → subscribe Basic
JSEARCH_KEY = "PASTE_YOUR_RAPIDAPI_KEY_HERE"

# 3. SERVICE ACCOUNT JSON — paste full JSON from GCP between the triple quotes
#    console.cloud.google.com → IAM → Service Accounts → Keys → Add Key → JSON
CREDS_JSON = """
PASTE_YOUR_FULL_SERVICE_ACCOUNT_JSON_HERE
"""

# 4. DEFAULT ROLES — user can change in the app sidebar
DEFAULT_ROLES = [
    "Product Manager",
    "Product Marketing Manager",
    "Growth Marketing Manager",
]

# 5. DEFAULT DAYS BACK — user can change in the app sidebar
DEFAULT_DAYS_BACK = 3

# 6. COUNTRY MAP
COUNTRY_MAP = {
    "India":     {"adzuna": "in",  "jsearch": "India"},
    "UK":        {"adzuna": "gb",  "jsearch": "United Kingdom"},
    "USA":       {"adzuna": "us",  "jsearch": "United States"},
    "Australia": {"adzuna": "au",  "jsearch": "Australia"},
    "Remote":    {"adzuna": "in",  "jsearch": "remote"},
}

# ════════════════════════════════════════════════════════════════════════════════
# ██  END OF CONFIG — do not edit below this line  ████████████████████████████ ██
# ════════════════════════════════════════════════════════════════════════════════

def job_id(title, company):
    return hashlib.md5(f"{title}{company}".lower().encode()).hexdigest()[:8]

def get_sheet(sheet_name, roles):
    try:
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
        client = gspread.authorize(creds)
        sh     = client.open(sheet_name)

        # New worksheet name: first role first 20 chars + date
        tab_label = roles[0][:20].strip() if roles else "Run"
        tab_name  = f"{tab_label} {date.today().strftime('%d%b')}"

        # Create fresh tab for this run
        try:
            # Delete if same name exists today (re-run)
            existing = sh.worksheet(tab_name)
            sh.del_worksheet(existing)
        except gspread.WorksheetNotFound:
            pass

        ws = sh.add_worksheet(title=tab_name, rows=1000, cols=20)
        ws.append_row([
            "ID", "Date Added", "Title", "Company", "Location",
            "Source", "Role", "Salary", "URL", "JD Summary",
            "Remote", "Status", "Match Score", "Verdict"
        ])
        return ws, None, tab_name
    except json.JSONDecodeError as e:
        return None, f"JSON Error: {str(e)}", None
    except Exception as e:
        return None, str(e), None

def get_existing_ids(ws):
    try:
        ids = ws.col_values(1)
        return set(ids[1:])
    except:
        return set()

def fetch_adzuna(role, country_code="in"):
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{country_code}/search/1"
        f"?app_id={ADZUNA_ID}&app_key={ADZUNA_KEY}"
        f"&results_per_page=10&what={requests.utils.quote(role)}"
        f"&content-type=application/json"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        jobs = []
        for j in r.json().get("results", []):
            jobs.append({
                "id":      job_id(j.get("title",""), j.get("company",{}).get("display_name","")),
                "title":   j.get("title",""),
                "company": j.get("company",{}).get("display_name","Unknown"),
                "location":j.get("location",{}).get("display_name","India"),
                "source":  "Adzuna", "role": role,
                "salary":  f"Rs.{int(j['salary_min']/100000)}L+" if j.get("salary_min") else "",
                "url":     j.get("redirect_url",""),
                "jd":      j.get("description","")[:500],
                "remote":  "remote" in j.get("description","").lower(),
            })
        return jobs, None
    except Exception as e:
        return [], str(e)

def fetch_jsearch(role, days_back=3, country_name="India"):
    date_filter = "today" if days_back == 1 else f"{days_back}days" if days_back <= 7 else "month"
    query = f"{role} {country_name}" if country_name != "remote" else f"{role} remote"
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  JSEARCH_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            },
            params={
                "query":      query,
                "page":       "1",
                "num_pages":  "1",
                "date_posted": date_filter
            },
            timeout=10
        )
        r.raise_for_status()
        jobs = []
        for j in r.json().get("data", [])[:8]:
            jobs.append({
                "id":      job_id(j.get("job_title",""), j.get("employer_name","")),
                "title":   j.get("job_title",""),
                "company": j.get("employer_name","Unknown"),
                "location":f"{j.get('job_city','')}, {j.get('job_country','')}".strip(", "),
                "source":  j.get("job_publisher","JSearch"), "role": role,
                "salary":  f"${int(j['job_min_salary']/1000)}k+" if j.get("job_min_salary") else "",
                "url":     j.get("job_apply_link",""),
                "jd":      j.get("job_description","")[:500],
                "remote":  j.get("job_is_remote", False),
            })
        return jobs, None
    except Exception as e:
        return [], str(e)

def save_jobs(ws, jobs, existing_ids):
    new_count = 0
    errors = []
    for job in jobs:
        if job["id"] in existing_ids:
            continue
        try:
            ws.append_row([
                job["id"], str(date.today()), job["title"], job["company"],
                job["location"], job["source"], job["role"], job.get("salary",""),
                job["url"], job["jd"][:200],  # truncate JD to avoid cell size limit
                "Yes" if job.get("remote") else "No",
                "New", "", ""
            ])
            existing_ids.add(job["id"])
            new_count += 1
            time.sleep(0.5)  # increased delay to avoid quota
        except Exception as e:
            errors.append(f"{job['title']}: {str(e)[:100]}")
            time.sleep(2)  # back off on error
            continue
    if errors:
        st.warning(f"⚠️ {len(errors)} rows failed: {errors[0]}")
    return new_count

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🔍 App 1 — Job Scraper")
st.caption("Fetches jobs from Adzuna + JSearch and saves to Google Sheet.")

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Search Settings")

    st.subheader("Job Positions")
    st.caption("One role per line — add or remove as needed")
    roles_input = st.text_area(
        "roles",
        value="\n".join(DEFAULT_ROLES),
        height=120,
        label_visibility="collapsed"
    )
    ROLES = [r.strip() for r in roles_input.strip().split("\n") if r.strip()]

    st.divider()
    st.subheader("Country")
    selected_country = st.selectbox(
        "country",
        options=list(COUNTRY_MAP.keys()),
        index=0,
        label_visibility="collapsed"
    )
    adzuna_country = COUNTRY_MAP[selected_country]["adzuna"]
    jsearch_country = COUNTRY_MAP[selected_country]["jsearch"]

    st.divider()
    st.subheader("Days Back")
    days_back = st.slider("Fetch jobs posted in last N days", 1, 30, DEFAULT_DAYS_BACK)

    st.divider()
    st.subheader("Google Sheet")
    SHEET_NAME = st.text_input(
        "Sheet File Name",
        value="Job Pipeline",
        placeholder="e.g. Job Pipeline",
        help="Exact name of your Google Sheet (case sensitive)"
    )
    st.caption("📌 Create a Google Sheet with this exact name, then share it with Editor access to:")
    st.markdown("""
<div style="background:#0d1a00; border:1px solid #34d399; border-left:3px solid #34d399;
     border-radius:6px; padding:12px; margin-top:4px;">
    <span style="color:#a0aec0; font-size:12px;">Share with <strong>Editor</strong> access to:</span><br/>
    <div style="background:#0a0f00; border:1px solid #2a4a00; border-radius:4px;
         padding:8px; margin-top:6px; word-break:break-all;">
        <span style="color:#38bdf8; font-size:11px; font-weight:bold;">
            nabhey@airy-gate-238512.iam.gserviceaccount.com
        </span>
    </div>
    <span style="color:#4a6a4a; font-size:11px; margin-top:6px; display:block;">
        Jobs will auto-save here on every run.
    </span>
</div>
""", unsafe_allow_html=True)

# ── Config validation ─────────────────────────────────────────────────────────
config_ok = True
warnings = []
if "PASTE_YOUR_ADZUNA_APP_ID_HERE"  in ADZUNA_ID:   warnings.append("Adzuna App ID not set")
if "PASTE_YOUR_ADZUNA_APP_KEY_HERE" in ADZUNA_KEY:  warnings.append("Adzuna App Key not set")
if "PASTE_YOUR_RAPIDAPI_KEY_HERE"   in JSEARCH_KEY: warnings.append("JSearch key not set")
if "PASTE_YOUR_FULL_SERVICE"        in CREDS_JSON:  warnings.append("Service Account JSON not set")

if warnings:
    st.warning(f"⚠️ Open `app1_scraper.py` → fill CONFIG section: {', '.join(warnings)}")
    config_ok = False

# ── Sheet connection ──────────────────────────────────────────────────────────
ws, sheet_err, tab_name = None, None, None
if "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON and CREDS_JSON.strip():
    ws, sheet_err, tab_name = get_sheet(SHEET_NAME, ROLES)
    if sheet_err:
        st.error(f"Sheet error: {sheet_err}")
    else:
        st.success(f"✅ Connected to **{SHEET_NAME}** → new tab: **{tab_name}**")

existing_ids = get_existing_ids(ws) if ws else set()

c1, c2, c3, c4 = st.columns(4)
c1.metric("In Sheet",  len(existing_ids))
c2.metric("Roles",     len(ROLES))
c3.metric("Country",   selected_country)
c4.metric("Last Run",  st.session_state.get("last_run", "Never"))

st.divider()

if not ROLES:
    st.error("Add at least one job role in the sidebar.")
else:
    st.markdown(f"**Searching for:** {' · '.join(ROLES)}")

run_btn = st.button(
    "▶ Run Scraper",
    type="primary",
    disabled=(not config_ok or not ROLES),
)

# ── Scraping ──────────────────────────────────────────────────────────────────
if run_btn:
    all_jobs, log_lines = [], []
    total_steps = max(len(ROLES) * 2, 1)
    step = 0
    progress = st.progress(0, text="Starting...")

    for role in ROLES:
        progress.progress(step / total_steps, text=f"Adzuna → {role}...")
        jobs, err = fetch_adzuna(role, adzuna_country)
        log_lines.append(f"{'✅' if not err else '⚠️'} Adzuna / {role}: {len(jobs)} jobs" + (f" ({err})" if err else ""))
        all_jobs.extend(jobs)
        step += 1

        progress.progress(step / total_steps, text=f"JSearch → {role}...")
        jobs, err = fetch_jsearch(role, days_back, jsearch_country)
        log_lines.append(f"{'✅' if not err else '⚠️'} JSearch / {role}: {len(jobs)} jobs" + (f" ({err})" if err else ""))
        all_jobs.extend(jobs)
        step += 1
        time.sleep(0.5)

    # Dedupe
    seen, deduped = {}, []
    for j in all_jobs:
        if j["id"] not in seen:
            seen[j["id"]] = True
            deduped.append(j)

    progress.progress(1.0, text="Saving to sheet...")

    if ws:
        new_count = save_jobs(ws, deduped, existing_ids)
        st.session_state["last_run"] = datetime.now().strftime("%H:%M, %d %b")
        st.success(f"✅ Done — {len(deduped)} unique jobs, **{new_count} new** added to sheet.")
    else:
        st.warning(f"Found {len(deduped)} jobs but Sheet not connected — fix CREDS_JSON in config.")

    progress.empty()

    with st.expander("Run Log", expanded=True):
        for line in log_lines:
            st.write(line)

    if deduped:
        st.subheader(f"Jobs Found ({len(deduped)})")
        for job in deduped[:20]:
            already = job["id"] in existing_ids
            st.markdown(f"""
            <div class="job-card">
                <strong>{job['title']}</strong> &nbsp;
                <span class="{'tag' if already else 'new-tag'}">{'duplicate' if already else 'NEW'}</span><br/>
                <span style="color:#8888aa">{job['company']} · {job['location']}</span><br/><br/>
                <span class="tag">{job['source']}</span>
                <span class="tag">{job['role']}</span>
                {'<span class="tag">Remote</span>' if job.get('remote') else ''}
                {f'<span class="tag">{job["salary"]}</span>' if job.get("salary") else ''}
            </div>""", unsafe_allow_html=True)
