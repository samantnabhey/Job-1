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

# ════════════════════════════════════════════════════════════════════════════════
# ██  CONFIGURE HERE — change these values, nothing else needs to be touched  ██
# ════════════════════════════════════════════════════════════════════════════════

# 1. ADZUNA — get free at https://developer.adzuna.com
ADZUNA_ID  = "ac1a4ebd"
ADZUNA_KEY = "b24bf85fcd6f5da0c1bf82d2d8ab5d30"

# 2. JSEARCH — get free at https://rapidapi.com → search JSearch → subscribe Basic
JSEARCH_KEY = "c878633452mshdf37c1410b3565bp18b884jsn05ae0b0654b8"

# 3. GOOGLE SHEET — exact name of your sheet (case sensitive)
SHEET_NAME = "Job Pipeline"

# 4. SERVICE ACCOUNT JSON — paste the full JSON from GCP between the triple quotes
#    Steps: console.cloud.google.com → IAM → Service Accounts → Keys → Add Key → JSON
#    Then share your Google Sheet with the client_email below (Editor access)
CREDS_JSON = """{
  "type": "service_account",
  "project_id": "airy-gate-238512",
  "private_key_id": "51cf2f8c913a7f9c5a84daac96bebfe3ff5048db",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQCkm3nqSAH1U+W9\nJsqvdUVWX4IBsdMSl/3zTXajWjzgBVZ/ID3VVevckHZ/Xy3Jo8Xi1LQIM2N3GnRD\nFmaIEi85VLkxmuicFcpZElkNnrXJ3PERvpjxYc5O4s+UVIuJl4Aj3rM9H0OqdzgS\nIPaokdxK7uzCLIQW0inl2Dxk0r4wkyh5vskD48HnXpcPnyMTKbuBvIP1Qneoe6jA\nkG1PnWqsYhqCdWwK2qJsruO+vI4bLjFEd9TkZVyaJ+QxAiIJ0cGf61qkVQCxCW7l\nhhC0dlVwGlVs8Gix3pZLyaJfpu16hKi5zF2RPPCpDcsuwZaXqLmyJIBycshQxrHR\nzLr6jikHAgMBAAECggEAI57ZhQ9MDTC4mHQajFmORaCpW4CFspJdjBcJQ1Q1tCyz\niRMLDm1nevVwDyQjnmzoV6u7wcKNFasN2a6xRWTZ/0gMQ2XITG6SuS+1QbNEl4hO\nSo66PhHyOTPvw6OABqhYPGrm0qU/WVYvNg0YE2ZtC3IknehQNTgJhQmEGDVantwA\njzm/mmS+hFQ3bpz6xXAGsFZVhjeCLw86VJ+MOG1sl5s3iU8CuTi/dVRD4X36r5Kg\ntD+ie2T4c0Tig9FemfPNAhp/dXXs3hMTmMkGmY0BLfcL7ZSCF/MJIbefYN/1QEpM\noNhtj/7M1NXo5nLaHXJ5VBKfxS10ey5fmRyszGUNsQKBgQDVUU5h/j1GNL2ZT68P\nEGNFrRXzFozF+C/aynHas7T6zgSzvqE8RbX0lnIWg9Nn6tmGJPs1kpRSuUsebm5p\nhsDubC5OHbCaCggaPfa66XA9JeHR7j6YcGz4Zt+azJUWhXLSL/QKSgasR7td1N5m\nWB8M+Qw9OLDcEUn24jn1x8Tj1QKBgQDFixm+D8nrRR4ylpftjfh1m4TG3mb7+f26\nCSW95ViWerC9lL3pOO6odM2MnJsFYUwt8PHw5ErsDb/SkEn04w3PqnN7EkKYLzgs\n+xbD5OFLLSeMLydeKix2NFM/V9/MxaO/A+xax57gRo6T+VGdV+VlaViZcOY/am7s\n1pXy66GzawKBgFTAZvn7/vBDyAh/Zjf/9NEcAZqBHRESmEC/KhkQSRlUfP3FAV5m\n+/HfTBix625gGmh3jO8t+4waXkQK8AcxKLoRdRxII4Av+CQk9kAwuw0wXdYAaBI8\nqK7QgIqKObmm74We08C6xIfyP/j5uBrFbCDFWh2AxpPIsrBKFWkXI5y5AoGAaGBr\nJaWqBwnqPsibVgWhtmKJ8ZopyBH7IoUa0A+Sk1AYetNQ1R4j3BZ7VUSaFGmoms2o\nyKOXgspxBI0AxsgB0Cw8AFdRoJ+yivHQwYj6EYK2VrfDkVmvTHWxVtLTiZsUPiWQ\niRbYt6AQTdd6bCy5JLBZBBpHTlKqcbGgYU5njikCgYBhVjeOZF0xFDKbSkCOJA2z\n30NyW/PPNabm++T1tUlQSyCttGcgX7CpMUXhyYiKSAL72Mw+tAr2qudggSyl1PMn\nTZg7Tv51cnNnUM01RAKrDCn33PfIdnU1mUG20EDRUcIvH7jN+MTbmCN9J6UxIjHC\nj/dbbQ1r1LnhO2KOrcGH2A==\n-----END PRIVATE KEY-----\n",
  "client_email": "nabhey@airy-gate-238512.iam.gserviceaccount.com",
  "client_id": "100136393772596802414",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
}"""

# 5. DEFAULT ROLES — user can change these in the app UI
DEFAULT_ROLES = [
    "Product Manager",
    "Product Marketing Manager",
    "Growth Marketing Manager",
]

# 6. COUNTRIES — adzuna country codes: in=India, gb=UK, us=USA, au=Australia
ADZUNA_COUNTRY = "in"

# 7. DEFAULT DAYS BACK — user can change this in the app UI
DEFAULT_DAYS_BACK = 3

# ════════════════════════════════════════════════════════════════════════════════
# ██  END OF CONFIG — do not edit below this line  ██████████████████████████  ██
# ════════════════════════════════════════════════════════════════════════════════

def job_id(title, company):
    return hashlib.md5(f"{title}{company}".lower().encode()).hexdigest()[:8]

def get_sheet():
    try:
        creds_dict = json.loads(CREDS_JSON)
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        sh     = client.open(SHEET_NAME)
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
        return None, "CREDS_JSON is not valid JSON — check the format in config section"
    except Exception as e:
        return None, str(e)

def get_existing_ids(ws):
    try:
        ids = ws.col_values(1)
        return set(ids[1:])
    except:
        return set()

def fetch_adzuna(role):
    url = (
        f"https://api.adzuna.com/v1/api/jobs/{ADZUNA_COUNTRY}/search/1"
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

def fetch_jsearch(role, days_back=3):
    date_filter = "today" if days_back == 1 else f"{days_back}days" if days_back <= 7 else "month"
    try:
        r = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            headers={
                "X-RapidAPI-Key":  JSEARCH_KEY,
                "X-RapidAPI-Host": "jsearch.p.rapidapi.com"
            },
            params={
                "query":      f"{role} India remote",
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

# ── Sidebar — user inputs ─────────────────────────────────────────────────────
with st.sidebar:
    st.header("🔧 Search Settings")

    st.subheader("Job Positions")
    st.caption("Add or remove roles to search for")
    roles_input = st.text_area(
        "One role per line",
        value="\n".join(DEFAULT_ROLES),
        height=120,
        label_visibility="collapsed"
    )
    ROLES = [r.strip() for r in roles_input.strip().split("\n") if r.strip()]

    st.divider()
    st.subheader("Days Back")
    days_back = st.slider("Fetch jobs posted in last N days", 1, 30, DEFAULT_DAYS_BACK)

    st.divider()
    st.subheader("Google Sheet Name")
    SHEET_NAME = st.text_input("Sheet name (case sensitive)", value="Job Pipeline")
    st.markdown("""
<div style="background:#0d1a00; border:1px solid #34d399; border-left:3px solid #34d399;
     border-radius:6px; padding:12px; margin-top:8px; font-size:13px;">
    <strong style="color:#34d399;">📋 Sheet Setup:</strong><br/><br/>
    <span style="color:#a0aec0;">1. Create a Google Sheet with the name above</span><br/><br/>
    <span style="color:#a0aec0;">2. Share it with <strong>Editor</strong> access to:</span><br/>
    <div style="background:#0a0f00; border:1px solid #2a4a00; border-radius:4px;
         padding:8px; margin-top:6px; word-break:break-all;">
        <span style="color:#38bdf8; font-size:12px; font-weight:bold;">
            nabhey@airy-gate-238512.iam.gserviceaccount.com
        </span>
    </div>
    <span style="color:#4a6a4a; font-size:11px; margin-top:6px; display:block;">
        Once shared, jobs will auto-save to this sheet on every run.
    </span>
</div>
""", unsafe_allow_html=True)

# ── Config validation ─────────────────────────────────────────────────────────
config_ok = True
warnings = []
if "PASTE_YOUR_ADZUNA_APP_ID_HERE"  in ADZUNA_ID:  warnings.append("Adzuna App ID not set")
if "PASTE_YOUR_ADZUNA_APP_KEY_HERE" in ADZUNA_KEY: warnings.append("Adzuna App Key not set")
if "PASTE_YOUR_RAPIDAPI_KEY_HERE"   in JSEARCH_KEY:warnings.append("JSearch key not set")
if "PASTE_YOUR_FULL_SERVICE"        in CREDS_JSON: warnings.append("Service Account JSON not set")

if warnings:
    st.warning(f"⚠️ Open `app1_scraper.py` → fill CONFIG section: {', '.join(warnings)}")
    config_ok = False

# ── Sheet connection ──────────────────────────────────────────────────────────
ws, sheet_err = None, None
if "PASTE_YOUR_FULL_SERVICE" not in CREDS_JSON and CREDS_JSON.strip():
    ws, sheet_err = get_sheet()
    if sheet_err:
        st.error(f"Sheet error: {sheet_err}")
    else:
        st.success(f"✅ Connected to **{SHEET_NAME}**")

existing_ids = get_existing_ids(ws) if ws else set()

c1, c2, c3, c4 = st.columns(4)
c1.metric("In Sheet",  len(existing_ids))
c2.metric("Roles",     len(ROLES))
c3.metric("Days Back", days_back)
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

if run_btn:
    all_jobs, log_lines = [], []
    sources = ["Adzuna", "JSearch"]
    total_steps = max(len(ROLES) * len(sources), 1)
    step = 0
    progress = st.progress(0, text="Starting...")

    for role in ROLES:
        progress.progress(step / total_steps, text=f"Adzuna → {role}...")
        jobs, err = fetch_adzuna(role)
        log_lines.append(f"{'✅' if not err else '⚠️'} Adzuna / {role}: {len(jobs)} jobs" + (f" ({err})" if err else ""))
        all_jobs.extend(jobs)
        step += 1

        progress.progress(step / total_steps, text=f"JSearch → {role}...")
        jobs, err = fetch_jsearch(role, days_back)
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
        st.warning(f"Found {len(deduped)} jobs but Sheet not connected — add CREDS_JSON in config to save.")

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
