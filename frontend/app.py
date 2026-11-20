"""
ContextBridge AI — Streamlit frontend (layout-optimized)

Layout principles applied:
- Constrained main content width (max 1200px) so wide monitors stay readable
- Consistent column ratios and vertical rhythm
- Tabs for related lists instead of three cramped equal columns
- Session-cached API payloads to cut flicker on sidebar navigation
- Native st.metric + compact cards; less raw HTML where Streamlit is enough
- Sidebar: project switcher first, then navigation, then actions
"""
import html
import os
import requests
import streamlit as st


def _normalise_api_base(raw: str) -> str:
    """Accept 'https://host', 'https://host/' or 'https://host/api' and return '.../api'."""
    raw = (raw or '').strip().rstrip('/')
    return raw if raw.endswith('/api') else f'{raw}/api'


# Local default keeps `streamlit run frontend/app.py` working with zero config.
API_BASE = _normalise_api_base(os.getenv('CONTEXTBRIDGE_API', 'http://127.0.0.1:8000/api'))
API_ROOT = API_BASE[:-len('/api')]
# Render free instances sleep; the first request may need a cold start.
API_TIMEOUT = float(os.getenv('CONTEXTBRIDGE_API_TIMEOUT', '60'))
# Pre-fill the demo credentials only when explicitly enabled (never by default).
# Public marketing site (landing page); used for the 'Back to website' link.
SITE_URL = os.getenv('CONTEXTBRIDGE_SITE_URL', 'https://contextbridge-landing.onrender.com').strip()
DEMO_MODE = os.getenv('CONTEXTBRIDGE_DEMO_MODE', 'false').strip().lower() in ('1', 'true', 'yes')


def esc(value) -> str:
    """HTML-escape any value that came from the API / uploaded documents."""
    return html.escape(str(value if value is not None else ''), quote=True)

st.set_page_config(
    page_title='ContextBridge AI',
    page_icon='🔗',
    layout='wide',
    initial_sidebar_state='expanded',
)

# ---------------------------------------------------------------------------
# Design system + layout CSS
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap');

:root {
  --bg: #080808;
  --surface: #101010;
  --surface-2: #171717;
  --ink: #fafafa;
  --muted: #a3a3a3;
  --border: #292929;
  --accent: #FFD600;
  --accent-dim: #E6C000;
  --accent-soft: #2B2400;
  --radius: 12px;
  --shadow: 0 4px 20px rgb(0 0 0 / 0.45);
  --shadow-hover: 0 8px 28px rgb(255 214 0 / 0.15);
}

html, body, [class*="css"] { font-family: 'Inter', system-ui, sans-serif; color: var(--ink); }
h1, h2, h3, .hero h1, .cb-card h3, .cb-card h4 { font-family: 'Space Grotesk', 'Inter', sans-serif !important; letter-spacing: -0.02em; }

.stApp {
  background: radial-gradient(ellipse at top, #202020 0%, #080808 55%);
  color: var(--ink);
}

/* Constrain main block so ultra-wide screens stay readable */
.block-container {
  max-width: 1200px !important;
  padding-top: 1.25rem !important;
  padding-bottom: 2.5rem !important;
  padding-left: 1.5rem !important;
  padding-right: 1.5rem !important;
}

/* Sidebar */
section[data-testid="stSidebar"] {
  background: linear-gradient(180deg, #000000 0%, #101010 50%, #080808 100%);
  min-width: 260px !important;
  border-right: 1px solid #292929;
}
section[data-testid="stSidebar"] * { color: #FFF6B8 !important; }
section[data-testid="stSidebar"] .stRadio > div { gap: 0.15rem; }
section[data-testid="stSidebar"] .stRadio label {
  padding: 0.4rem 0.7rem;
  border-radius: 8px;
  font-size: 0.9rem;
}
section[data-testid="stSidebar"] .stRadio label:hover {
  background: rgba(255,214,0,0.15);
}
section[data-testid="stSidebar"] [data-baseweb="select"] { color: #0f172a !important; }

/* Cards */
.cb-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.1rem 1.25rem;
  margin-bottom: 0.85rem;
  transition: box-shadow 0.18s ease, transform 0.18s ease, border-color 0.18s ease;
}
.cb-card:hover { border-color: #FFD60055; }
.cb-card:hover { box-shadow: var(--shadow-hover); transform: translateY(-1px); }
.cb-card h3, .cb-card h4 { margin: 0 0 0.3rem 0; font-weight: 600; color: #FFFBE0; font-size: 1rem; }
.cb-muted { color: var(--muted); font-size: 0.85rem; line-height: 1.4; }

/* KPI grid via CSS (stable across column widths) */
.kpi-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(140px, 1fr));
  gap: 0.85rem;
  margin-bottom: 1.25rem;
}
.kpi {
  background: linear-gradient(160deg, #171717 0%, #101010 100%);
  border-radius: var(--radius);
  border: 1px solid #292929;
  box-shadow: var(--shadow);
  padding: 0.9rem 1rem;
  position: relative;
  overflow: hidden;
}
.kpi::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0;
  height: 3px;
  background: linear-gradient(90deg, #E6C000, #FCEB00);
}
.kpi .label {
  font-size: 0.72rem;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  font-weight: 500;
}
.kpi .value {
  font-size: 1.55rem;
  font-weight: 700;
  color: #FCEB00;
  margin-top: 0.15rem;
  line-height: 1.2;
}

/* Hero — compact on secondary pages */
.hero {
  background: linear-gradient(135deg, #000000 0%, #202020 40%, #2B2400 100%);
  border: 1px solid #FFD60055;
  border-radius: 16px;
  padding: 1.35rem 1.6rem;
  margin-bottom: 1.25rem;
  box-shadow: 0 16px 40px -10px rgb(255 214 0 / 0.25);
  position: relative;
  overflow: hidden;
}
.hero::after {
  content: '';
  position: absolute;
  width: 220px; height: 220px;
  border-radius: 50%;
  background: radial-gradient(circle, rgba(255,255,255,0.12) 0%, transparent 70%);
  top: -60px; right: -30px;
}
.hero h1 { margin: 0; font-size: 1.45rem; font-weight: 700; color: #FCEB00; }
.hero p { margin: 0.3rem 0 0; color: #d4d4d4; font-size: 0.92rem; }

/* Score */
.score-wrap { display: flex; align-items: center; gap: 1.25rem; flex-wrap: wrap; }
.score-circle {
  width: 100px; height: 100px;
  border-radius: 50%;
  background: conic-gradient(#FFD600 var(--pct), #333 0);
  display: grid; place-items: center;
  box-shadow: var(--shadow);
  flex-shrink: 0;
}
.score-inner {
  width: 78px; height: 78px;
  border-radius: 50%;
  background: #080808;
  color: #FCEB00;
  display: grid; place-items: center;
  font-weight: 700; font-size: 1.3rem;
}

/* Badges */
.badge {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.72rem;
  font-weight: 600;
  vertical-align: middle;
}
.badge-high, .badge-critical, .badge-blocked { background: #3b0d0d; color: #fca5a5; border: 1px solid #7f1d1d; }
.badge-medium, .badge-in_progress { background: #2B2400; color: #FFD600; border: 1px solid #7A6500; }
.badge-low, .badge-done { background: #062e1f; color: #6ee7b7; border: 1px solid #065f46; }
.badge-pending { background: #1f2937; color: #cbd5e1; border: 1px solid #374151; }
.badge-claude { background: #1e1b4b; color: #c7d2fe; border: 1px solid #4338ca; }
.badge-rule_based, .badge-local_keyword_match { background: #1f2937; color: #e5e7eb; border: 1px solid #4b5563; }
.badge-rule_based_fallback, .badge-mixed { background: #2B2400; color: #FFD600; border: 1px solid #7A6500; }
.bar { height: 8px; background: #262626; border-radius: 99px; overflow: hidden; margin-top: 0.35rem; }
.bar > span { display: block; height: 100%; border-radius: 99px; }

.evidence {
  background: #171717;
  border-left: 3px solid #FFD600;
  padding: 0.65rem 0.9rem;
  margin: 0.4rem 0;
  border-radius: 0 8px 8px 0;
  font-size: 0.88rem;
  color: #e5e5e5;
}

/* Native Streamlit controls */
div.stButton > button {
  border-radius: 999px;
  font-weight: 600;
  border: none;
  box-shadow: 0 2px 6px rgb(230 192 0 / 0.25);
  transition: transform 0.12s ease, box-shadow 0.12s ease;
}
div.stButton > button:hover {
  transform: translateY(-1px);
  box-shadow: 0 5px 12px rgb(230 192 0 / 0.35);
}
div.stButton > button[kind="primary"] {
  background: linear-gradient(135deg, #B89B00, #FFD600);
  color: #080808 !important;
}

/* Metric polish */
[data-testid="stMetric"] {
  background: #101010;
  border: 1px solid #292929;
  border-radius: var(--radius);
  padding: 0.75rem 1rem;
  box-shadow: var(--shadow);
}
[data-testid="stMetricValue"] { color: #FCEB00 !important; }
[data-testid="stMetricLabel"] { color: #a3a3a3 !important; }
[data-testid="stMetricLabel"] { font-size: 0.78rem !important; }

/* Tabs tighter */
.stTabs [data-baseweb="tab-list"] { gap: 0.35rem; }
.stTabs [data-baseweb="tab"] {
  border-radius: 8px 8px 0 0;
  padding: 0.45rem 1rem;
  font-weight: 500;
}

/* Login center */
.login-shell {
  max-width: 420px;
  margin: 2rem auto 0;
}

#MainMenu, footer, [data-testid="stToolbar"], [data-testid="stDecoration"] { visibility: hidden; }
header[data-testid="stHeader"] { background: transparent; }

/* Reduce default vertical gaps between Streamlit elements */
div[data-testid="stVerticalBlock"] > div { gap: 0.55rem; }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# API + cache helpers
# ---------------------------------------------------------------------------
def get_session() -> requests.Session:
    """One requests.Session PER Streamlit user session.

    Streamlit re-executes this script on every interaction, so a module-level
    Session would be recreated (losing the Django session cookie) on each rerun.
    """
    if 'http' not in st.session_state:
        st.session_state.http = requests.Session()
    return st.session_state.http


def api(method, path, **kwargs):
    """Call the backend; show a friendly message and stop the page on transport failure."""
    url = f'{API_BASE}{path}'
    kwargs.setdefault('timeout', API_TIMEOUT)
    try:
        r = get_session().request(method, url, **kwargs)
    except requests.exceptions.Timeout:
        st.error(f'The backend did not respond within {int(API_TIMEOUT)}s. If it was idle it may still be waking up — '
                 'wait a moment and try again.')
        st.stop()
    except requests.exceptions.ConnectionError:
        st.error('Cannot reach the ContextBridge API. '
                 f'Configured endpoint: `{API_BASE}`. Check that the backend is running and `CONTEXTBRIDGE_API` is correct.')
        st.stop()
    except requests.exceptions.RequestException as exc:
        st.error(f'Unexpected network error: {type(exc).__name__}')
        st.stop()

    # Session expired / not logged in → return to the sign-in screen cleanly.
    if r.status_code in (401, 403) and not path.startswith('/auth/') and st.session_state.get('user'):
        st.session_state.clear()
        st.session_state.flash = 'Your session expired. Please sign in again.'
        st.rerun()
    if r.status_code >= 500:
        st.error('The server hit an error handling that request. Please try again; check backend logs if it persists.')
        st.stop()
    return r


def err_text(r) -> str:
    try:
        data = r.json()
    except ValueError:
        return f'HTTP {r.status_code}'
    if isinstance(data, dict):
        return data.get('detail') or '; '.join(f'{k}: {v}' for k, v in data.items())
    return str(data)


def cache_key(*parts):
    return 'cache_' + '_'.join(str(p) for p in parts)


def get_json(path, project_id=None, force=False):
    """Session-level cache for GET payloads; cleared on process / project switch."""
    key = cache_key(path, project_id or 'global')
    if not force and key in st.session_state:
        return st.session_state[key]
    r = api('GET', path)
    if r.status_code == 200:
        st.session_state[key] = r.json()
        return st.session_state[key]
    return None


def clear_project_cache(project_id):
    prefix = f'cache_/projects/{project_id}'
    for k in list(st.session_state.keys()):
        if isinstance(k, str) and (k.startswith(prefix) or k.startswith('cache_/workspace')
                                   or k == 'cache_/projects/_global'):
            del st.session_state[k]
    st.session_state.pop('cache_/projects/_global', None)


def badge(text, kind=None):
    kind = kind or text
    return f'<span class="badge badge-{esc(kind)}">{esc(text)}</span>'


MODE_LABELS = {
    'claude': 'Claude (LLM)',
    'rule_based': 'Rule-based (no LLM)',
    'rule_based_fallback': 'Rule-based (Claude failed)',
    'local_keyword_match': 'Keyword match (no LLM)',
    'mixed': 'Mixed',
}


def mode_badge(mode):
    return badge(MODE_LABELS.get(mode, mode or 'unknown'), mode or 'rule_based')


def kpi_grid(items):
    """items: list of (label, value)"""
    cells = ''.join(
        f'<div class="kpi"><div class="label">{esc(lab)}</div><div class="value">{esc(val)}</div></div>'
        for lab, val in items
    )
    st.markdown(f'<div class="kpi-grid">{cells}</div>', unsafe_allow_html=True)


def hero(title, subtitle=''):
    sub = f'<p>{esc(subtitle)}</p>' if subtitle else ''
    st.markdown(f'<div class="hero"><h1>{esc(title)}</h1>{sub}</div>', unsafe_allow_html=True)


def card_html(title, body_html, meta=''):
    """`title`/`meta` are plain text (escaped here); `body_html` must already be safe."""
    meta_h = f'<div class="cb-muted">{esc(meta)}</div>' if meta else ''
    st.markdown(
        f'<div class="cb-card"><h4>{esc(title)}</h4>{meta_h}'
        f'<div style="margin-top:0.35rem;font-size:0.9rem;">{body_html}</div></div>',
        unsafe_allow_html=True,
    )


def score_color(score):
    return '#10b981' if score >= 70 else ('#FFB800' if score >= 45 else '#ef4444')


def bar(pct, color):
    pct = max(0, min(100, float(pct)))
    return f'<div class="bar"><span style="width:{pct}%;background:{color};"></span></div>'


def require_project():
    pid = st.session_state.get('project_id')
    if not pid:
        st.warning('Select or create a project in the sidebar first.')
    return pid


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
def page_login():
    hero('ContextBridge AI', 'Enterprise knowledge continuity — decisions, ownership, handover readiness.')
    if st.session_state.get('flash'):
        st.warning(st.session_state.pop('flash'))
    if SITE_URL:
        st.markdown(f'<a href="{SITE_URL}" target="_self" style="color:#FFD600;font-size:0.9rem;">&larr; Back to website</a>', unsafe_allow_html=True)
    st.markdown('<div class="login-shell">', unsafe_allow_html=True)
    tab_in, tab_up = st.tabs(['Sign in', 'Create account'])
    with tab_in:
        with st.form('login_form', clear_on_submit=False):
            username = st.text_input('Username', value='demo' if DEMO_MODE else '')
            password = st.text_input('Password', type='password', value='DemoPass123' if DEMO_MODE else '')
            if st.form_submit_button('Sign in', use_container_width=True, type='primary'):
                if not username or not password:
                    st.error('Enter your username and password.')
                else:
                    with st.spinner('Signing in…'):
                        r = api('POST', '/auth/login/', json={'username': username, 'password': password})
                    if r.status_code == 200:
                        st.session_state.user = r.json()['user']
                        st.session_state.page = 'overview'
                        st.rerun()
                    elif r.status_code == 401:
                        st.error('Incorrect username or password.')
                    else:
                        st.error(f'Sign-in failed: {err_text(r)}')
    with tab_up:
        with st.form('reg_form'):
            u = st.text_input('Username', key='reg_u')
            e = st.text_input('Email', key='reg_e')
            p = st.text_input('Password (min. 8 characters)', type='password', key='reg_p')
            if st.form_submit_button('Register', use_container_width=True, type='primary'):
                r = api('POST', '/auth/register/', json={'username': u, 'email': e, 'password': p})
                if r.status_code == 201:
                    st.success('Account created. Switch to the Sign in tab.')
                else:
                    st.error(err_text(r))
    st.markdown('</div>', unsafe_allow_html=True)
    if DEMO_MODE:
        st.caption('Demo mode: **demo** / **DemoPass123** (seeded sample data).')


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
NAV = [
    ('overview', 'Workspace overview'),
    ('documents', 'Documents'),
    ('decisions', 'Decisions & tasks'),
    ('risks', 'Risk intelligence'),
    ('gaps', 'Knowledge gaps'),
    ('graph', 'Knowledge graph'),
    ('readiness', 'Readiness'),
    ('assistant', 'AI assistant'),
    ('rehearsal', 'Handover rehearsal'),
    ('reports', 'Reports'),
    ('guide', 'Quick start'),
]


def sidebar_nav():
    with st.sidebar:
        st.markdown('### ContextBridge')
        user = st.session_state.get('user') or {}
        st.caption(f"{user.get('username', '')}")

        projects = get_json('/projects/') or []
        names = {p['name']: p['id'] for p in projects}

        if names:
            options = list(names.keys())
            current_id = st.session_state.get('project_id')
            idx = 0
            for i, (n, pid) in enumerate(names.items()):
                if pid == current_id:
                    idx = i
                    break
            selected = st.selectbox('Project', options, index=idx, label_visibility='collapsed')
            new_id = names[selected]
            if new_id != current_id:
                clear_project_cache(current_id or 0)
            st.session_state.project_id = new_id
            st.session_state.project_name = selected
        else:
            st.info('Create a project below')
            st.session_state.project_id = None

        with st.expander('New project', expanded=not bool(names)):
            with st.form('new_proj'):
                name = st.text_input('Name')
                desc = st.text_area('Description', height=70)
                if st.form_submit_button('Create', use_container_width=True):
                    if not name.strip():
                        st.error('Project name is required.')
                    else:
                        r = api('POST', '/projects/', json={'name': name.strip(), 'description': desc})
                        if r.status_code == 201:
                            clear_project_cache(0)
                            st.session_state.project_id = r.json()['id']
                            st.session_state.project_name = name
                            st.rerun()
                        else:
                            st.error(err_text(r))

        st.divider()
        labels = [lab for _, lab in NAV]
        keys = [k for k, _ in NAV]
        current_page = st.session_state.get('page', 'overview')
        try:
            default_i = keys.index(current_page)
        except ValueError:
            default_i = 0
        choice = st.radio('Navigate', labels, index=default_i, label_visibility='collapsed')
        st.session_state.page = keys[labels.index(choice)]

        if SITE_URL:
            st.markdown(f'<a href="{SITE_URL}" target="_self">&larr; Back to website</a>', unsafe_allow_html=True)
        st.divider()
        if st.button('Sign out', use_container_width=True):
            try:
                get_session().post(f'{API_BASE}/auth/logout/', timeout=10)
            except requests.exceptions.RequestException:
                pass
            st.session_state.clear()
            st.rerun()


# ---------------------------------------------------------------------------
# Pages
# ---------------------------------------------------------------------------
def page_overview():
    hero('Workspace overview', 'Knowledge continuity across your projects')
    data = get_json('/workspace/overview/')
    if not data:
        st.error('Could not load the overview. Try again in a moment.')
        return
    t = data['totals']
    rows = data.get('projects') or []
    avg = round(sum(p['readiness'] for p in rows) / len(rows), 1) if rows else 0
    kpi_grid([
        ('Projects', t['projects']),
        ('Documents', t['documents']),
        ('Decisions', t['decisions']),
        ('Tasks', t['tasks']),
        ('Risks', t['risks']),
        ('Open gaps', t['gaps']),
        ('Avg readiness', avg),
    ])

    st.subheader('Projects')
    if not rows:
        st.info('No projects yet. Create one in the sidebar.')
        return

    for i in range(0, len(rows), 2):
        cols = st.columns(2, gap='medium')
        for col, p in zip(cols, rows[i:i + 2]):
            score = p['readiness']
            color = score_color(score)
            with col:
                st.markdown(
                    f'<div class="cb-card">'
                    f'<div style="display:flex;justify-content:space-between;align-items:center;gap:1rem;">'
                    f'<div><h4 style="margin:0;">{esc(p["name"])}</h4>'
                    f'<div class="cb-muted">{esc(p["documents"])} docs · {esc(p["gaps"])} gaps</div></div>'
                    f'<div style="text-align:right;"><div style="font-size:1.4rem;font-weight:700;color:{color};">{esc(score)}</div>'
                    f'<div class="cb-muted">readiness</div></div></div>{bar(score, color)}</div>',
                    unsafe_allow_html=True,
                )


def page_documents():
    pid = require_project()
    if not pid:
        return
    hero('Documents', st.session_state.get('project_name', ''))

    left, right = st.columns([1.1, 1], gap='large')
    with left:
        st.markdown('##### Upload')
        uploaded = st.file_uploader('PDF, DOCX, or TXT', type=['pdf', 'docx', 'txt'], label_visibility='collapsed')
        if uploaded and st.button('Upload file', type='primary', use_container_width=True):
            with st.spinner(f'Uploading {uploaded.name}…'):
                r = api('POST', f'/projects/{pid}/documents/', files={'file': (uploaded.name, uploaded.getvalue())})
            if r.status_code == 201:
                clear_project_cache(pid)
                st.success(f'Uploaded {uploaded.name}')
                st.rerun()
            else:
                st.error(f'Upload failed: {err_text(r)}')
        if st.button('Process project documents', type='primary', use_container_width=True):
            with st.spinner('Extracting decisions, tasks, risks…'):
                r = api('POST', f'/projects/{pid}/process/')
            if r.status_code == 200:
                res = r.json()
                clear_project_cache(pid)
                st.success(res.get('detail', 'Done'))
                if res.get('extraction_mode'):
                    st.markdown('Extraction method: ' + mode_badge(res['extraction_mode']), unsafe_allow_html=True)
                if res.get('ai_errors'):
                    st.warning('Claude was configured but failed (' + ', '.join(res['ai_errors']) +
                               '); rule-based extraction was used instead.')
                kpi_grid([('Decisions', res.get('decisions', 0)), ('Tasks', res.get('tasks', 0)),
                          ('Risks', res.get('risks', 0)), ('Gaps', res.get('gaps', 0))])
            else:
                st.error(f'Processing failed: {err_text(r)}')

    with right:
        st.markdown('##### Library')
        docs = get_json(f'/projects/{pid}/documents/', pid) or []
        if not docs:
            st.info('No documents yet. Upload one to get started.')
        for d in docs:
            status = 'Processed' if d['processed'] else 'Pending'
            st.markdown(
                f'<div class="cb-card"><h4>{esc(d["filename"])}</h4>'
                f'<div class="cb-muted">{esc(d["file_type"].upper())} · {esc(status)} · '
                f'{esc(d.get("page_count", 0))} pages · {d.get("char_count", 0):,} chars</div></div>',
                unsafe_allow_html=True,
            )


def page_decisions():
    pid = require_project()
    if not pid:
        return
    hero('Decisions & tasks', st.session_state.get('project_name', ''))

    tab_d, tab_t = st.tabs(['Decisions', 'Tasks'])

    with tab_d:
        decisions = get_json(f'/projects/{pid}/decisions/', pid) or []
        if not decisions:
            st.info('No decisions extracted yet. Process documents first.')
        for d in decisions:
            body = esc((d.get('rationale') or d.get('description') or '')[:220])
            meta = f"{d.get('decided_by') or '—'} · {d.get('decided_at') or ''}"
            card_html(d['title'], body, meta)

    with tab_t:
        tasks = get_json(f'/projects/{pid}/tasks/', pid) or []
        if not tasks:
            st.info('No tasks yet.')
        else:
            unassigned = sum(1 for t in tasks if not (t.get('assignee') or '').strip())
            kpi_grid([('Tasks', len(tasks)), ('Unassigned', unassigned),
                      ('Blocked', sum(1 for t in tasks if t['status'] == 'blocked'))])
        for t in tasks:
            st.markdown(
                f'<div class="cb-card"><h4>{esc(t["title"])}</h4>'
                f'{badge(t["status"])} '
                f'<span class="cb-muted">Owner: {esc(t.get("assignee") or "unassigned")}</span></div>',
                unsafe_allow_html=True,
            )


def page_risks():
    pid = require_project()
    if not pid:
        return
    hero('Risk intelligence', st.session_state.get('project_name', ''))
    risks = get_json(f'/projects/{pid}/risks/', pid) or []
    if not risks:
        st.info('No risks identified yet. Process documents first.')
        return
    order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3}
    counts = {k: sum(1 for r in risks if r['severity'] == k) for k in order}
    unmitigated = sum(1 for r in risks if not (r.get('mitigation') or '').strip() and r['severity'] in ('critical', 'high'))
    kpi_grid([('Critical', counts['critical']), ('High', counts['high']), ('Medium', counts['medium']),
              ('Low', counts['low']), ('High/critical unmitigated', unmitigated)])
    for risk in sorted(risks, key=lambda r: order.get(r['severity'], 9)):
        mit = (risk.get('mitigation') or '').strip()
        st.markdown(
            f'<div class="cb-card"><div style="display:flex;justify-content:space-between;gap:0.75rem;">'
            f'<h4 style="margin:0;">{esc(risk["title"])}</h4>{badge(risk["severity"])}</div>'
            f'<div class="cb-muted" style="margin-top:0.3rem;">'
            f'{"Mitigation: " + esc(mit[:200]) if mit else "No mitigation documented"}'
            f'{" · Owner: " + esc(risk["owner"]) if risk.get("owner") else ""}</div></div>',
            unsafe_allow_html=True,
        )


def page_gaps():
    pid = require_project()
    if not pid:
        return
    hero('Knowledge gaps', st.session_state.get('project_name', ''))
    gaps = get_json(f'/projects/{pid}/knowledge-gaps/', pid) or []
    if not gaps:
        st.success('No open knowledge gaps detected.')
        return
    sev = {k: sum(1 for g in gaps if g.get('severity') == k) for k in ('critical', 'high', 'medium', 'low')}
    kpi_grid([('Total gaps', len(gaps))] + [(k.title(), v) for k, v in sev.items()])
    for g in gaps:
        severity = g.get('severity', 'medium')
        st.markdown(
            f'<div class="cb-card">'
            f'<div style="display:flex;justify-content:space-between;gap:0.75rem;align-items:flex-start;">'
            f'<h4 style="margin:0;">{esc(g["title"])}</h4>{badge(severity)}</div>'
            f'<p class="cb-muted" style="margin:0.4rem 0;">{esc(g.get("description", ""))}</p>'
            f'<div style="font-size:0.85rem;"><strong>Action:</strong> {esc(g.get("suggested_action", ""))}</div>'
            f'</div>',
            unsafe_allow_html=True,
        )


def page_graph():
    pid = require_project()
    if not pid:
        return
    hero('Knowledge graph', st.session_state.get('project_name', ''))
    data = get_json(f'/projects/{pid}/knowledge-graph/', pid)
    if not data:
        st.error('Could not load the graph.')
        return
    nodes, edges = data.get('nodes', []), data.get('edges', [])
    if len(nodes) <= 1:
        st.info('The graph is empty. Process documents to populate decisions, tasks and risks.')
        return

    try:
        import networkx as nx
        import plotly.graph_objects as go

        G = nx.Graph()
        for n in nodes:
            G.add_node(n['id'], label=n['label'], ntype=n['type'])
        for e in edges:
            G.add_edge(e['source'], e['target'])

        pos = nx.spring_layout(G, seed=42, k=0.55)
        colors = {'project': '#FFD600', 'decision': '#10b981', 'task': '#FFB800', 'risk': '#ef4444'}
        sizes = {'project': 26, 'decision': 15, 'task': 15, 'risk': 15}
        nx_, ny_, text, color, size = [], [], [], [], []
        for nid, (x, y) in pos.items():
            nx_.append(x)
            ny_.append(y)
            n = G.nodes[nid]
            text.append(n.get('label', nid))
            color.append(colors.get(n.get('ntype'), '#64748b'))
            size.append(sizes.get(n.get('ntype'), 14))

        ex, ey = [], []
        for a, b in G.edges():
            x0, y0 = pos[a]
            x1, y1 = pos[b]
            ex += [x0, x1, None]
            ey += [y0, y1, None]

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=ex, y=ey, mode='lines', line=dict(width=1, color='#3f3f46'), hoverinfo='none'))
        fig.add_trace(go.Scatter(
            x=nx_, y=ny_, mode='markers+text', text=text, textposition='top center',
            marker=dict(size=size, color=color, line=dict(width=1, color='#080808')),
            textfont=dict(size=10, color='#e5e5e5'), hovertext=text, hoverinfo='text',
        ))
        fig.update_layout(
            showlegend=False, margin=dict(l=8, r=8, t=8, b=8), height=520,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            xaxis=dict(visible=False), yaxis=dict(visible=False),
        )
        try:
            st.plotly_chart(fig, width='stretch')
        except TypeError:  # older Streamlit without the `width` argument
            st.plotly_chart(fig, use_container_width=True)
    except Exception as ex:
        st.warning(f'Graph could not be drawn ({type(ex).__name__}). Showing counts instead.')
        st.caption(f'{len(nodes)} nodes · {len(edges)} edges')

    st.caption(f'{len(nodes)} nodes · {len(edges)} edges — yellow project · green decision · amber task · red risk')


def page_readiness():
    pid = require_project()
    if not pid:
        return
    hero('Handover readiness', st.session_state.get('project_name', ''))
    data = get_json(f'/projects/{pid}/readiness/', pid)
    if not data:
        st.error('Could not load readiness.')
        return

    score = data['overall_score']
    pct = int(score * 3.6)
    st.markdown(
        f'<div class="cb-card"><div class="score-wrap">'
        f'<div class="score-circle" style="--pct:{pct}deg;"><div class="score-inner">{esc(score)}</div></div>'
        f'<div><h3 style="margin:0;">Overall readiness</h3>'
        f'<p class="cb-muted" style="margin:0.3rem 0 0;">{esc(data.get("recommendation", ""))}</p></div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    cats = data.get('categories') or {}
    if cats:
        cols = st.columns(len(cats))
        for col, (name, val) in zip(cols, cats.items()):
            with col:
                st.metric(name.replace('_', ' ').title(), f'{val}')
                st.markdown(bar(val, score_color(val)), unsafe_allow_html=True)
    st.caption(f"{data.get('gap_count', 0)} open knowledge gap(s) reduce the overall score.")


def page_assistant():
    pid = require_project()
    if not pid:
        return
    hero('AI assistant', st.session_state.get('project_name', ''))
    st.caption('Answers are grounded in your processed documents. The badge on each answer states exactly '
               'whether Claude or plain keyword matching produced it.')

    suggestions = [
        'What database technology was selected?',
        'Who owns the dual-write pilot?',
        'What are the highest severity risks?',
        'Which tasks are unassigned?',
    ]
    scols = st.columns(4)
    for col, s in zip(scols, suggestions):
        if col.button(s, use_container_width=True):
            st.session_state.ask_q = s

    q = st.text_input('Ask about project evidence', value=st.session_state.get('ask_q', ''))
    if st.button('Ask', type='primary'):
        if not q.strip():
            st.warning('Type a question first.')
            return
        with st.spinner('Searching evidence…'):
            r = api('POST', f'/projects/{pid}/ask/', json={'question': q})
        if r.status_code == 200:
            data = r.json()
            st.markdown('Answer method: ' + mode_badge(data.get('mode')), unsafe_allow_html=True)
            st.markdown(data.get('answer', ''))
            for ev in data.get('evidence') or []:
                st.markdown(
                    f'<div class="evidence"><strong>{esc(ev["document"])}</strong> · page {esc(ev["page"])}<br/>'
                    f'{esc(ev["excerpt"])}</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.error(f'Could not answer: {err_text(r)}')


def page_rehearsal():
    pid = require_project()
    if not pid:
        return
    hero('Handover rehearsal', st.session_state.get('project_name', ''))
    if st.button('Start rehearsal', type='primary'):
        r = api('POST', f'/projects/{pid}/rehearsals/', json={})
        if r.status_code == 200:
            data = r.json()
            st.markdown(f"**Project:** {esc(data.get('project'))}")
            for i, q in enumerate(data.get('questions') or [], 1):
                card_html(f'Question {i}', esc(q))
            st.info('Practice answering these with a peer, then generate a report under Reports.')
        else:
            st.error(err_text(r))


def page_reports():
    pid = require_project()
    if not pid:
        return
    hero('Handover reports', st.session_state.get('project_name', ''))

    if st.button('Generate new handover report', type='primary'):
        with st.spinner('Building report…'):
            r = api('POST', f'/projects/{pid}/handover/', json={})
        if r.status_code == 201:
            clear_project_cache(pid)
            st.success(f"Report v{r.json()['version']} · readiness {r.json()['readiness_score']}")
            st.rerun()
        else:
            st.error(f'Report generation failed: {err_text(r)}')

    reports = get_json(f'/projects/{pid}/reports/', pid) or []
    if not reports:
        st.info('No reports yet.')
    for rep in reports:
        st.markdown(
            f'<div class="cb-card"><h4>Version {esc(rep["version"])} · score {esc(rep["readiness_score"])}</h4>'
            f'<div class="cb-muted">{esc(str(rep.get("created_at", ""))[:19].replace("T", " "))}</div></div>',
            unsafe_allow_html=True,
        )
        with st.expander(f'Preview v{rep["version"]}'):
            st.text((rep.get('content') or '')[:4000])
        # The browser holds no API session cookie, so a plain link would 403.
        # Content is already in the report payload; serve it via download_button.
        st.download_button('Download', data=rep.get('content') or '', file_name=f'handover_v{rep["version"]}.txt',
                           mime='text/plain', key=f'dl_{rep["id"]}')


def page_guide():
    hero('Quick start', 'Empty workspace → readiness score in a few steps')
    st.markdown("""
    <div class="cb-card">
      <ol style="line-height:1.75;margin:0;padding-left:1.2rem;">
        <li>Sign in or create an account.</li>
        <li>Create or select a project in the sidebar.</li>
        <li><strong>Documents</strong> → upload PDF / DOCX / TXT → <strong>Process project documents</strong>.</li>
        <li>Review <strong>Decisions &amp; tasks</strong>, <strong>Risk intelligence</strong>, <strong>Knowledge gaps</strong> and the graph.</li>
        <li>Check <strong>Readiness</strong> for score and category breakdown.</li>
        <li>Ask grounded questions in the <strong>AI assistant</strong>.</li>
        <li>Practice with <strong>Handover rehearsal</strong>, then generate a <strong>Report</strong>.</li>
      </ol>
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------
PAGES = {
    'overview': page_overview,
    'documents': page_documents,
    'decisions': page_decisions,
    'risks': page_risks,
    'gaps': page_gaps,
    'graph': page_graph,
    'readiness': page_readiness,
    'assistant': page_assistant,
    'rehearsal': page_rehearsal,
    'reports': page_reports,
    'guide': page_guide,
}


def main():
    if 'page' not in st.session_state:
        st.session_state.page = 'login'
    if 'user' not in st.session_state:
        st.session_state.user = None

    if st.session_state.page == 'login' or not st.session_state.user:
        page_login()
        return

    sidebar_nav()
    page_fn = PAGES.get(st.session_state.get('page', 'overview'), page_overview)
    page_fn()


main()
