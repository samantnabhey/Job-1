import streamlit as st
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import json
import time
import hashlib

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

ROLES = ["Product Manager", "Product Marketing Manager", "Growth Marketing Manager"]

def job_id(title, company):
    return hashlib.md5(f"{title}{company}".lower().encode()).hexdigest()[:8]

def get_sheet(creds_json_str, sheet_name):
    try:
        creds_dict = json.loads(creds_json_str)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sh     = client.open(sheet_name)
        try:
            ws = sh.worksheet("Jobs")
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title="Jobs", rows=1000, cols=20)
            ws.append_row([
                "ID","Date Added","Title","Company","Location",
                "Source","Role","Salary","URL","JD Summary",
                "Remote","Status","Match Score","Verdict"
            ])
        return ws, None
    except json.JSONDecodeError:
        return None, "Invalid JSON — paste the full service account JSON"
    except Exception as e:
        return None, str(e)

def get_existing_ids(ws):
    try:
        ids = ws.col_values(1)
        return set(ids[1:])
    except:
        return set()

def fetch_adzuna(role, app_id, app_key):
    url = (
        f"https://api.adzuna.com/v1/api/jobs/in/search/1"
        f"?app_id={app_id}&app_key={app_key}"
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

def fetch_jsearch(role, api_key):
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={"X-RapidAPI-Key": api_key, "X-RapidAPI-Host": "jsearch.p.rapidapi.com"},
            params={"query": f"{role} India remote", "page":"1","num_pages":"1","date_posted":"3days"},
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
    for job in jobs:
        if job["id"] in existing_ids:
            continue
        ws.append_row([
            job["id"], str(date.today()), job["title"], job["company"],
            job["location"], job["source"], job["role"], job.get("salary",""),
            job["url"], job["jd"],
            "Yes" if job.get("remote") else "No",
            "New", "", ""
        ])
        existing_ids.add(job["id"])
        new_count += 1
        time.sleep(0.3)
    return new_count

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🔍 App 1 — Job Scraper")
st.caption("Fetches jobs from Adzuna + JSearch and saves to Google Sheet.")

with st.sidebar:
    st.header("⚙️ Setup")

    st.subheader("API Keys")
    adzuna_id   = st.text_input("Adzuna App ID",       type="password", placeholder="developer.adzuna.com")
    adzuna_key  = st.text_input("Adzuna App Key",      type="password")
    jsearch_key = st.text_input("JSearch RapidAPI Key",type="password", placeholder="rapidapi.com → JSearch")

    st.divider()
    st.subheader("Google Sheet")
    sheet_name = st.text_input("Sheet Name", value="Job Pipeline")
    st.caption("Paste your full service account JSON below")
    creds_json = st.text_area(
        "Service Account JSON",
        height=160,
        placeholder='{\n  "type": "service_account",\n  "project_id": "...",\n  "private_key": "...",\n  "client_email": "..@..iam.gserviceaccount.com"\n}',
        label_visibility="collapsed"
    )

    st.divider()
    st.subheader("Search Settings")
    selected_roles = st.multiselect("Roles", ROLES, default=ROLES)
    sources = st.multiselect("Sources", ["Adzuna", "JSearch"], default=["Adzuna", "JSearch"])

    with st.expander("How to get service account JSON"):
        st.markdown("""
1. [console.cloud.google.com](https://console.cloud.google.com) → New project
2. Enable **Google Sheets API** + **Google Drive API**
3. IAM → Service Accounts → Create → download JSON key
4. Open JSON file → copy all → paste above
5. Create Google Sheet named **"Job Pipeline"**
6. Share sheet with the `client_email` from JSON (Editor)
        """)

# Sheet connection
ws, sheet_err = None, None
if creds_json.strip():
    ws, sheet_err = get_sheet(creds_json, sheet_name)
    if sheet_err:
        st.error(f"Sheet error: {sheet_err}")
    else:
        st.success(f"Connected to **{sheet_name}**")
else:
    st.info("Paste your Service Account JSON in the sidebar to connect Google Sheet.")

existing_ids = get_existing_ids(ws) if ws else set()

c1, c2, c3, c4 = st.columns(4)
c1.metric("In Sheet",  len(existing_ids))
c2.metric("Roles",     len(selected_roles))
c3.metric("Sources",   len(sources))
c4.metric("Last Run",  st.session_state.get("last_run", "Never"))

st.divider()

missing = []
if "Adzuna" in sources and (not adzuna_id or not adzuna_key): missing.append("Adzuna keys")
if "JSearch" in sources and not jsearch_key: missing.append("JSearch key")
if not creds_json.strip(): missing.append("Service Account JSON")
if missing:
    st.warning(f"Fill in sidebar first: {', '.join(missing)}")

run_btn = st.button("▶ Run Scraper", type="primary", disabled=not ws)

if run_btn:
    all_jobs, log_lines = [], []
    total_steps = max(len(selected_roles) * len(sources), 1)
    step = 0
    progress = st.progress(0, text="Starting...")

    for role in selected_roles:
        if "Adzuna" in sources:
            progress.progress(step / total_steps, text=f"Adzuna → {role}...")
            jobs, err = fetch_adzuna(role, adzuna_id, adzuna_key)
            log_lines.append(f"{'✅' if not err else '⚠️'} Adzuna / {role}: {len(jobs)} jobs" + (f" ({err})" if err else ""))
            all_jobs.extend(jobs)
            step += 1

        if "JSearch" in sources:
            progress.progress(step / total_steps, text=f"JSearch → {role}...")
            jobs, err = fetch_jsearch(role, jsearch_key)
            log_lines.append(f"{'✅' if not err else '⚠️'} JSearch / {role}: {len(jobs)} jobs" + (f" ({err})" if err else ""))
            all_jobs.extend(jobs)
            step += 1
            time.sleep(0.5)

    seen, deduped = {}, []
    for j in all_jobs:
        if j["id"] not in seen:
            seen[j["id"]] = True
            deduped.append(j)

    progress.progress(1.0, text="Saving to sheet...")
    new_count = save_jobs(ws, deduped, existing_ids)
    progress.empty()

    st.session_state["last_run"] = datetime.now().strftime("%H:%M, %d %b")
    st.success(f"Done — {len(deduped)} unique jobs found, **{new_count} new** added to sheet.")

    with st.expander("Run Log", expanded=True):
        for line in log_lines:
            st.write(line)

    if deduped:
        st.subheader(f"Jobs Found ({len(deduped)})")
        for job in deduped[:20]:
            already = job["id"] in (existing_ids - {job["id"]})
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
