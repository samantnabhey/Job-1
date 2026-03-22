import streamlit as st
import requests
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, date
import json
import time
import hashlib

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="App 1 — Job Scraper",
    page_icon="🔍",
    layout="wide"
)

# ── Styling ───────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    .main { background: #0a0a0f; }
    .stApp { background: #0a0a0f; color: #e2e8f0; }
    .metric-card {
        background: #0f0f1a;
        border: 1px solid #1e1e30;
        border-radius: 10px;
        padding: 16px 20px;
        text-align: center;
    }
    .job-card {
        background: #0f0f1a;
        border: 1px solid #1e1e30;
        border-left: 3px solid #38bdf8;
        border-radius: 8px;
        padding: 14px 16px;
        margin-bottom: 10px;
    }
    .tag {
        background: #1e1e30;
        color: #6868a8;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
        margin-right: 5px;
    }
    .success-tag {
        background: #052016;
        color: #34d399;
        padding: 2px 10px;
        border-radius: 20px;
        font-size: 12px;
    }
    h1, h2, h3 { color: #38bdf8 !important; }
</style>
""", unsafe_allow_html=True)

# ── Config ────────────────────────────────────────────────────────────────────
ROLES = [
    "Product Manager",
    "Product Marketing Manager",
    "Growth Marketing Manager",
]

SHEET_NAME = "Job Pipeline"
WORKSHEET  = "Jobs"

# ── Google Sheet connection ───────────────────────────────────────────────────
@st.cache_resource
def get_sheet():
    try:
        creds_dict = dict(st.secrets["gcp_service_account"])
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sh     = client.open(SHEET_NAME)
        try:
            ws = sh.worksheet(WORKSHEET)
        except gspread.WorksheetNotFound:
            ws = sh.add_worksheet(title=WORKSHEET, rows=1000, cols=20)
            ws.append_row([
                "ID", "Date Added", "Title", "Company", "Location",
                "Source", "Role", "Salary", "URL", "JD Summary",
                "Remote", "Status", "Match Score", "Verdict"
            ])
        return ws
    except Exception as e:
        st.error(f"Sheet connection failed: {e}")
        st.info("Setup: Add gcp_service_account to .streamlit/secrets.toml")
        return None

def job_id(title, company):
    return hashlib.md5(f"{title}{company}".lower().encode()).hexdigest()[:8]

def get_existing_ids(ws):
    try:
        ids = ws.col_values(1)
        return set(ids[1:])  # skip header
    except:
        return set()

# ── Adzuna API ────────────────────────────────────────────────────────────────
def fetch_adzuna(role, app_id, app_key, country="in"):
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{country}/search/1"
        f"?app_id={app_id}&app_key={app_key}"
        f"&results_per_page=10&what={requests.utils.quote(role)}"
        f"&content-type=application/json"
    )
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        results = r.json().get("results", [])
        jobs = []
        for j in results:
            jobs.append({
                "id":       job_id(j.get("title",""), j.get("company",{}).get("display_name","")),
                "title":    j.get("title", ""),
                "company":  j.get("company", {}).get("display_name", "Unknown"),
                "location": j.get("location", {}).get("display_name", "India"),
                "source":   "Adzuna",
                "role":     role,
                "salary":   f"₹{int(j['salary_min']/100000)}L+" if j.get("salary_min") else "",
                "url":      j.get("redirect_url", ""),
                "jd":       j.get("description", "")[:500],
                "remote":   "remote" in j.get("description","").lower(),
            })
        return jobs, None
    except Exception as e:
        return [], str(e)

# ── JSearch API ───────────────────────────────────────────────────────────────
def fetch_jsearch(role, api_key):
    url = "https://jsearch.p.rapidapi.com/search"
    params = {
        "query":      f"{role} India remote",
        "page":       "1",
        "num_pages":  "1",
        "date_posted":"3days",
    }
    headers = {
        "X-RapidAPI-Key":  api_key,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }
    try:
        r = requests.get(url, headers=headers, params=params, timeout=10)
        r.raise_for_status()
        results = r.json().get("data", [])
        jobs = []
        for j in results[:8]:
            jobs.append({
                "id":       job_id(j.get("job_title",""), j.get("employer_name","")),
                "title":    j.get("job_title", ""),
                "company":  j.get("employer_name", "Unknown"),
                "location": f"{j.get('job_city','')}, {j.get('job_country','')}".strip(", "),
                "source":   j.get("job_publisher", "JSearch"),
                "role":     role,
                "salary":   f"${int(j['job_min_salary']/1000)}k+" if j.get("job_min_salary") else "",
                "url":      j.get("job_apply_link", ""),
                "jd":       j.get("job_description", "")[:500],
                "remote":   j.get("job_is_remote", False),
            })
        return jobs, None
    except Exception as e:
        return [], str(e)

# ── Save to Sheet ─────────────────────────────────────────────────────────────
def save_jobs(ws, jobs, existing_ids):
    new_count = 0
    for job in jobs:
        if job["id"] in existing_ids:
            continue
        ws.append_row([
            job["id"],
            str(date.today()),
            job["title"],
            job["company"],
            job["location"],
            job["source"],
            job["role"],
            job.get("salary", ""),
            job["url"],
            job["jd"],
            "Yes" if job.get("remote") else "No",
            "New",     # Status
            "",        # Match Score (filled by App 2)
            "",        # Verdict    (filled by App 2)
        ])
        existing_ids.add(job["id"])
        new_count += 1
        time.sleep(0.3)  # avoid rate limit
    return new_count

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🔍 App 1 — Job Scraper")
st.caption("Fetches jobs from Adzuna + JSearch → saves to Google Sheet. Run daily.")

# Sidebar config
with st.sidebar:
    st.header("⚙️ Configuration")

    st.subheader("API Keys")
    adzuna_id  = st.text_input("Adzuna App ID",  value=st.secrets.get("ADZUNA_APP_ID", ""),  type="password")
    adzuna_key = st.text_input("Adzuna App Key", value=st.secrets.get("ADZUNA_APP_KEY", ""), type="password")
    jsearch_key= st.text_input("JSearch Key",    value=st.secrets.get("JSEARCH_KEY", ""),    type="password")

    st.divider()
    st.subheader("Search Settings")
    selected_roles = st.multiselect("Target Roles", ROLES, default=ROLES)
    sources = st.multiselect("Sources", ["Adzuna", "JSearch"], default=["Adzuna", "JSearch"])

    st.divider()
    st.subheader("Google Sheet")
    sheet_name_input = st.text_input("Sheet Name", value=SHEET_NAME)

# Main area — stats row
ws = get_sheet()
col1, col2, col3, col4 = st.columns(4)

existing_ids = set()
total_in_sheet = 0
if ws:
    existing_ids = get_existing_ids(ws)
    total_in_sheet = len(existing_ids)

with col1:
    st.metric("Jobs in Sheet", total_in_sheet)
with col2:
    st.metric("Roles Targeted", len(selected_roles))
with col3:
    st.metric("Sources Active", len(sources))
with col4:
    last_run = st.session_state.get("last_run", "Never")
    st.metric("Last Run", last_run)

st.divider()

# Run button
run_col, info_col = st.columns([1, 3])
with run_col:
    run_btn = st.button("▶ Run Scraper", type="primary", use_container_width=True)
with info_col:
    st.info("Tip: Add API keys to `.streamlit/secrets.toml` so they persist across runs.")

# ── Scraping logic ─────────────────────────────────────────────────────────────
if run_btn:
    if not ws:
        st.error("Google Sheet not connected. Check secrets.toml setup below.")
        st.stop()

    all_jobs  = []
    log_lines = []

    progress = st.progress(0, text="Starting scrape...")
    total_steps = len(selected_roles) * len(sources)
    step = 0

    for role in selected_roles:
        if "Adzuna" in sources:
            progress.progress(step / total_steps, text=f"Fetching {role} from Adzuna...")
            jobs, err = fetch_adzuna(role, adzuna_id, adzuna_key)
            if err:
                log_lines.append(f"⚠️ Adzuna error for '{role}': {err}")
            else:
                log_lines.append(f"✅ Adzuna — {role}: {len(jobs)} results")
            all_jobs.extend(jobs)
            step += 1

        if "JSearch" in sources:
            progress.progress(step / total_steps, text=f"Fetching {role} from JSearch...")
            jobs, err = fetch_jsearch(role, jsearch_key)
            if err:
                log_lines.append(f"⚠️ JSearch error for '{role}': {err}")
            else:
                log_lines.append(f"✅ JSearch — {role}: {len(jobs)} results")
            all_jobs.extend(jobs)
            step += 1
            time.sleep(0.5)

    progress.progress(1.0, text="Saving to Google Sheet...")

    # Dedupe within this batch
    seen = {}
    deduped = []
    for j in all_jobs:
        if j["id"] not in seen:
            seen[j["id"]] = True
            deduped.append(j)

    new_count = save_jobs(ws, deduped, existing_ids)
    progress.empty()

    st.session_state["last_run"]    = datetime.now().strftime("%H:%M %d %b")
    st.session_state["scraped_jobs"] = deduped

    # Results summary
    st.success(f"Done! Found {len(deduped)} unique jobs → {new_count} new added to sheet.")

    # Log
    with st.expander("📋 Scrape Log", expanded=True):
        for line in log_lines:
            st.write(line)
        st.write(f"**Total unique jobs found:** {len(deduped)}")
        st.write(f"**New (not in sheet before):** {new_count}")
        st.write(f"**Duplicates skipped:** {len(deduped) - new_count}")

    # Preview cards
    if deduped:
        st.subheader(f"Preview — {len(deduped)} jobs found")
        for job in deduped[:15]:
            is_new = job["id"] not in (existing_ids - {job["id"]})
            with st.container():
                st.markdown(f"""
                <div class="job-card">
                    <strong>{job['title']}</strong> &nbsp;
                    <span class="{'success-tag' if is_new else 'tag'}">{'NEW' if is_new else 'duplicate'}</span>
                    <br/>
                    <span style="color:#8888aa;">{job['company']} · {job['location']}</span>
                    <br/><br/>
                    <span class="tag">{job['source']}</span>
                    <span class="tag">{job['role']}</span>
                    {'<span class="tag">🏠 Remote</span>' if job.get('remote') else ''}
                    {f'<span class="tag">{job["salary"]}</span>' if job.get('salary') else ''}
                </div>
                """, unsafe_allow_html=True)

# ── Setup instructions ─────────────────────────────────────────────────────────
with st.expander("📖 Setup Instructions", expanded=(ws is None)):
    st.markdown("""
### 1. Get API Keys (both free)
- **Adzuna**: [developer.adzuna.com](https://developer.adzuna.com) → Register → get App ID + Key
- **JSearch**: [rapidapi.com](https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch) → Subscribe free tier → get API Key

### 2. Google Sheet Setup
1. Create a new Google Sheet named **"Job Pipeline"**
2. Go to [console.cloud.google.com](https://console.cloud.google.com)
3. Create project → Enable **Google Sheets API** + **Google Drive API**
4. Create **Service Account** → Download JSON key
5. Share your Google Sheet with the service account email (Editor access)

### 3. secrets.toml
Create `.streamlit/secrets.toml` in your project folder:
```toml
ADZUNA_APP_ID  = "your_id"
ADZUNA_APP_KEY = "your_key"
JSEARCH_KEY    = "your_rapidapi_key"

[gcp_service_account]
type                        = "service_account"
project_id                  = "your_project_id"
private_key_id              = "..."
private_key                 = "-----BEGIN RSA PRIVATE KEY-----\\n...\\n-----END RSA PRIVATE KEY-----\\n"
client_email                = "your-sa@your-project.iam.gserviceaccount.com"
client_id                   = "..."
auth_uri                    = "https://accounts.google.com/o/oauth2/auth"
token_uri                   = "https://oauth2.googleapis.com/token"
```

### 4. Deploy to Streamlit Cloud
```bash
# Push to GitHub
git add . && git commit -m "add app1" && git push

# Go to share.streamlit.io
# New app → pick repo → main file: app1_scraper.py
# Add secrets in the Streamlit Cloud dashboard
```

### 5. Schedule daily runs (optional)
Streamlit apps run on demand — for true daily automation,
use **GitHub Actions** (free) to ping your app URL every morning:
```yaml
# .github/workflows/daily_scrape.yml
on:
  schedule:
    - cron: '0 4 * * *'  # 9:30am IST
jobs:
  ping:
    runs-on: ubuntu-latest
    steps:
      - run: curl -s "${{ secrets.APP1_URL }}" > /dev/null
```
    """)

