import os
import redis
import requests
from flask import Flask, request
 
app = Flask(__name__)
 
REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
API_KEY = os.environ.get('CRICKET_API_KEY')
cache = redis.Redis(host=REDIS_HOST, port=6379, decode_responses=True)
 
def is_ipl_match(match):
    return 'INDIAN PREMIER LEAGUE' in match.get('name', '').upper()
 
def get_visitor_stats():
    try:
        hits = cache.incr('total_hits')
        cache.sadd('unique_visitors', request.remote_addr)
        return hits, cache.scard('unique_visitors')
    except Exception as e:
        return "N/A", "N/A"
 
def fetch_all_matches(offset, total_rows, accumulated):
    """Recursively fetch all pages from cricapi, mirroring the JS pagination sample."""
    if offset >= total_rows:
        return accumulated
    url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset={offset}"
    resp = requests.get(url, timeout=8).json()
    if resp.get('status') != 'success':
        return accumulated
    batch = resp.get('data', [])
    return fetch_all_matches(offset + 25, total_rows, accumulated + batch)

def fetch_ipl_data():
    import json

    cached = cache.get('ipl_raw_json')
    if cached:
        return json.loads(cached), "CACHE"

    if not API_KEY:
        return None, "CONFIG_ERROR"

    try:
        # First call to get totalRows
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
        data = requests.get(url, timeout=8).json()

        if data.get('status') != 'success':
            return None, f"API_ERROR: {data.get('reason', data.get('status'))}"

        total_rows = data.get('info', {}).get('totalRows', 25)
        first_batch = data.get('data', [])

        # Recursively fetch remaining pages
        all_matches = fetch_all_matches(25, total_rows, first_batch)

        ipl_matches = [m for m in all_matches if is_ipl_match(m)]

        cache.setex('ipl_raw_json', 30, json.dumps(ipl_matches))
        return ipl_matches, "LIVE"

    except Exception as e:
        return None, f"ERROR: {e}"
 
def get_short_name(inning_str):
    parts = inning_str.split(' Inning ')
    team = parts[0] if parts else inning_str
    inn_num = parts[1] if len(parts) > 1 else ''
    short_map = {
        'Kolkata Knight Riders': 'KKR', 'Sunrisers Hyderabad': 'SRH',
        'Mumbai Indians': 'MI', 'Chennai Super Kings': 'CSK',
        'Delhi Capitals': 'DC', 'Royal Challengers Bengaluru': 'RCB',
        'Royal Challengers Bangalore': 'RCB', 'Rajasthan Royals': 'RR',
        'Punjab Kings': 'PBKS', 'Lucknow Super Giants': 'LSG',
        'Gujarat Titans': 'GT',
    }
    return short_map.get(team, team[:3].upper()), inn_num
 
def render_live_card(match):
    teams = match.get('teamInfo', [])
    team1 = teams[0] if len(teams) > 0 else {}
    team2 = teams[1] if len(teams) > 1 else {}
    score_list = match.get('score', [])
    status = match.get('status', '')
    venue = match.get('venue', '')
    match_name = match.get('name', '')
    match_num = ''
    for part in match_name.split(','):
        if 'match' in part.lower() or 'final' in part.lower() or 'qualifier' in part.lower():
            match_num = part.strip()
            break
 
    is_live = match.get('matchStarted') and not match.get('matchEnded')
    is_ended = match.get('matchEnded', False)
 
    innings_html = ''
    for s in score_list:
        short, inn_num = get_short_name(s.get('inning', ''))
        r, w, o = s.get('r', 0), s.get('w', 0), s.get('o', 0)
        try:
            rr = f"{float(r)/float(o):.2f}" if float(o) > 0 else '-'
        except:
            rr = '-'
        innings_html += f"""
        <div class="innings-row">
            <div class="inn-label">INN {inn_num}</div>
            <div class="inn-team">{short}</div>
            <div class="inn-score">{r}<span class="wickets">/{w}</span></div>
            <div class="inn-overs">({o} ov)</div>
            <div class="inn-rr">RR {rr}</div>
        </div>"""
 
    if not innings_html:
        innings_html = f'<div class="no-score-yet">⏳ {status}</div>'
 
    live_badge = ''
    if is_live:
        live_badge = '<span class="live-badge"><span class="pulse-dot"></span>LIVE</span>'
    elif is_ended:
        live_badge = '<span class="ended-badge">RESULT</span>'
 
    logo1 = f'<img src="{team1.get("img","")}" onerror="this.style.display=\'none\'">' if team1.get('img') else ''
    logo2 = f'<img src="{team2.get("img","")}" onerror="this.style.display=\'none\'">' if team2.get('img') else ''
 
    match_id = match.get('id', '')
    return f"""
    <div class="match-card live-match">
        <div class="card-header">
            {live_badge}
            <div class="match-meta">{match_num} &nbsp;·&nbsp; {venue}</div>
        </div>
        <div class="teams-row">
            <div class="team-block">
                <div class="team-logo">{logo1}</div>
                <div class="team-name">{team1.get('shortname', team1.get('name','?'))}</div>
            </div>
            <div class="vs-block">VS</div>
            <div class="team-block">
                <div class="team-logo">{logo2}</div>
                <div class="team-name">{team2.get('shortname', team2.get('name','?'))}</div>
            </div>
        </div>
        <div class="innings-block" id="innings-{match_id}">
            {innings_html}
        </div>
        <div class="status-bar" id="status-{match_id}">{status}</div>
    </div>"""
 
def render_result_card(match):
    teams = match.get('teamInfo', [])
    team1 = teams[0] if len(teams) > 0 else {}
    team2 = teams[1] if len(teams) > 1 else {}
    score_list = match.get('score', [])
    status = match.get('status', '')
    date = match.get('date', '')
    match_name = match.get('name', '')
    match_num = ''
    for part in match_name.split(','):
        if 'match' in part.lower() or 'final' in part.lower():
            match_num = part.strip()
            break
 
    scores_str = '  •  '.join(
        [f"{get_short_name(s.get('inning',''))[0]}: {s.get('r')}/{s.get('w')} ({s.get('o')} ov)"
         for s in score_list]
    )
 
    logo1 = f'<img src="{team1.get("img","")}" onerror="this.style.display=\'none\'">' if team1.get('img') else ''
    logo2 = f'<img src="{team2.get("img","")}" onerror="this.style.display=\'none\'">' if team2.get('img') else ''
 
    return f"""
    <div class="match-card result-card">
        <div class="result-header">
            <span class="result-badge">FT</span>
            <span class="result-date">{date}</span>
            <span class="result-num">{match_num}</span>
        </div>
        <div class="result-teams">
            <span class="r-logo">{logo1}</span>
            <span class="r-name">{team1.get('shortname','?')}</span>
            <span class="r-scores">{scores_str}</span>
            <span class="r-logo">{logo2}</span>
            <span class="r-name">{team2.get('shortname','?')}</span>
        </div>
        <div class="result-status">{status}</div>
    </div>"""
 

@app.route('/api/scores')
def api_scores():
    import json
    from flask import jsonify
    matches, source = fetch_ipl_data()
    ttl = cache.ttl('ipl_raw_json')
    if ttl < 0: ttl = 30
    live = []
    ended = []
    if matches:
        live = [m for m in matches if m.get('matchStarted') and not m.get('matchEnded')]
        ended = [m for m in matches if m.get('matchEnded')]
    return jsonify({
        'live': live,
        'ended': ended[:4],
        'source': source,
        'ttl': ttl
    })

@app.route('/debug')
def debug():
    if not API_KEY:
        return "CRICKET_API_KEY not set", 500
    try:
        import json
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
        data = requests.get(url, timeout=8).json()
        return f"<pre>{json.dumps(data, indent=2)}</pre>"
    except Exception as e:
        return f"Error: {e}", 500
 
@app.route('/clearcache')
def clearcache():
    try:
        cache.delete('ipl_raw_json')
        return "Cache cleared."
    except Exception as e:
        return f"Redis error: {e}", 500
 
@app.route('/')
def index():
    hits, unique = get_visitor_stats()
    matches, source = fetch_ipl_data()
    ttl = cache.ttl('ipl_raw_json')
    if ttl < 0: ttl = 30
 
    if not matches:
        if 'hits today exceeded' in source or 'Blocking' in source:
            main_content = '<div class="no-match"><div class="no-match-icon">⚠️</div><div class="no-match-title">Daily API Limit Reached</div><div class="no-match-sub">The free plan allows 100 requests/day. Scores will resume automatically tomorrow when the limit resets.</div></div>'
        elif source == 'CONFIG_ERROR':
            main_content = '<div class="no-match"><div class="no-match-icon">🔑</div><div class="no-match-title">API Key Not Configured</div><div class="no-match-sub">Set the CRICKET_API_KEY environment variable and restart.</div></div>'
        elif source.startswith('ERROR') or source.startswith('API_ERROR'):
            main_content = '<div class="no-match"><div class="no-match-icon">📡</div><div class="no-match-title">Unable to Fetch Scores</div><div class="no-match-sub">Could not connect to the cricket data service. Will retry shortly.</div></div>'
        else:
            main_content = '<div class="no-match"><div class="no-match-icon">🏏</div><div class="no-match-title">No IPL Matches Right Now</div><div class="no-match-sub">Check back when the next match starts.</div></div>'
    else:
        live = [m for m in matches if m.get('matchStarted') and not m.get('matchEnded')]
        ended = [m for m in matches if m.get('matchEnded')]
 
        main_content = ''
        if live:
            main_content += '<div class="section-label">LIVE NOW</div>'
            for m in live:
                main_content += render_live_card(m)
        else:
            main_content += '<div class="no-live">No match live right now — check back soon</div>'
 
        if ended:
            main_content += '<div class="section-label recent-label">RECENT RESULTS</div>'
            for m in ended[:4]:
                main_content += render_result_card(m)
 
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">

<title>IPL 2026 Live</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,400;0,14..32,500;0,14..32,600;0,14..32,700&family=Bebas+Neue&family=Roboto+Mono:wght@400;500&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:        #f5f5f5;
    --surface:   #ffffff;
    --surface2:  #fafafa;
    --border:    #e8e8e8;
    --accent:    #d4790a;
    --accent2:   #c0392b;
    --live:      #16a34a;
    --live-bg:   #f0fdf4;
    --live-border:#bbf7d0;
    --text:      #111111;
    --text2:     #444444;
    --muted:     #888888;
    --card-r:    12px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Inter', sans-serif;
    min-height: 100vh;
  }}

  /* ── HEADER ── */
  .header {{
    background: #fff;
    border-bottom: 1px solid var(--border);
    padding: 0;
  }}
  .header-inner {{
    max-width: 720px;
    margin: 0 auto;
    padding: 20px 20px 18px;
    display: flex;
    align-items: center;
    gap: 14px;
  }}
  .header-icon {{
    width: 40px; height: 40px;
    background: linear-gradient(135deg, #d4790a, #c0392b);
    border-radius: 10px;
    display: flex; align-items: center; justify-content: center;
    font-size: 1.2rem; flex-shrink: 0;
  }}
  .header-text h1 {{
    font-family: 'Bebas Neue', sans-serif;
    font-weight: 400; font-size: 1.4rem;
    letter-spacing: 0.05em; color: var(--text);
    line-height: 1;
  }}
  .header-text p {{
    font-size: 0.72rem; color: var(--muted);
    letter-spacing: 0.04em; margin-top: 3px;
    text-transform: uppercase;
  }}
  .header-badge {{
    margin-left: auto;
    background: #fff7ed;
    border: 1px solid #fed7aa;
    color: var(--accent);
    font-family: 'Roboto Mono', monospace;
    font-size: 0.65rem; font-weight: 500;
    padding: 4px 10px; border-radius: 20px;
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }}

  /* ── LAYOUT ── */
  .container {{ max-width: 720px; margin: 0 auto; padding: 24px 20px 60px; }}

  /* ── SECTION LABELS ── */
  .section-label {{
    font-family: 'Roboto Mono', monospace;
    font-size: 0.65rem; font-weight: 500;
    letter-spacing: 0.12em; color: var(--muted);
    text-transform: uppercase;
    margin: 28px 0 10px;
    display: flex; align-items: center; gap: 10px;
  }}
  .section-label::after {{
    content: ''; flex: 1; height: 1px; background: var(--border);
  }}
  .live-label {{ color: var(--live); }}

  /* ── MATCH CARDS ── */
  .match-card {{
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--card-r);
    overflow: hidden;
    margin-bottom: 10px;
    transition: box-shadow 0.2s;
  }}
  .match-card:hover {{
    box-shadow: 0 4px 20px rgba(0,0,0,0.07);
  }}
  .live-match {{
    border-color: var(--live-border);
    background: var(--surface);
  }}

  /* ── CARD HEADER ── */
  .card-header {{
    display: flex; align-items: center; gap: 10px;
    padding: 11px 16px;
    border-bottom: 1px solid var(--border);
    background: var(--surface2);
  }}
  .match-meta {{
    font-size: 0.75rem; color: var(--muted);
    margin-left: auto; text-align: right;
    white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; max-width: 65%;
    font-family: 'Inter', sans-serif;
  }}

  /* ── BADGES ── */
  .live-badge {{
    display: inline-flex; align-items: center; gap: 5px;
    background: var(--live-bg); color: var(--live);
    border: 1px solid var(--live-border);
    font-family: 'Roboto Mono', monospace; font-weight: 500;
    font-size: 0.62rem; letter-spacing: 0.1em;
    padding: 3px 9px; border-radius: 20px; white-space: nowrap;
    text-transform: uppercase;
  }}
  .pulse-dot {{
    width: 6px; height: 6px; background: var(--live); border-radius: 50%;
    animation: pulse 1.4s ease infinite;
  }}
  @keyframes pulse {{
    0%,100% {{ box-shadow: 0 0 0 0 rgba(22,163,74,0.5); }}
    50% {{ box-shadow: 0 0 0 5px rgba(22,163,74,0); }}
  }}
  .ended-badge {{
    background: #f3f4f6; color: var(--muted);
    border: 1px solid #e5e7eb;
    font-family: 'Roboto Mono', monospace; font-weight: 500;
    font-size: 0.62rem; letter-spacing: 0.1em;
    padding: 3px 9px; border-radius: 20px;
  }}

  /* ── TEAMS ROW ── */
  .teams-row {{
    display: flex; align-items: center; justify-content: space-between;
    padding: 20px 24px 14px;
  }}
  .team-block {{
    display: flex; flex-direction: column; align-items: center; gap: 8px;
    flex: 1;
  }}
  .team-logo img {{
    width: 54px; height: 54px; object-fit: contain;
    filter: drop-shadow(0 2px 6px rgba(0,0,0,0.12));
  }}
  .team-name {{
    font-family: 'Bebas Neue', sans-serif;
    font-weight: 400; font-size: 1.4rem;
    letter-spacing: 0.06em; color: var(--text);
  }}
  .vs-block {{
    font-family: 'Roboto Mono', monospace;
    font-size: 0.7rem; color: var(--muted);
    letter-spacing: 0.1em; padding: 0 12px;
    flex-shrink: 0;
  }}

  /* ── INNINGS ── */
  .innings-block {{
    padding: 4px 16px 16px;
    display: flex; flex-direction: column; gap: 6px;
  }}
  .innings-row {{
    display: flex; align-items: center; gap: 10px;
    background: #fafafa;
    border-radius: 8px;
    padding: 10px 14px;
    border: 1px solid #f0f0f0;
  }}
  .inn-label {{
    font-family: 'Roboto Mono', monospace; font-size: 0.6rem;
    font-weight: 500; letter-spacing: 0.08em;
    color: var(--muted); min-width: 34px;
    text-transform: uppercase;
  }}
  .inn-team {{
    font-family: 'Bebas Neue', sans-serif; font-weight: 400;
    font-size: 1rem; color: var(--accent); min-width: 42px;
    letter-spacing: 0.06em;
  }}
  .inn-score {{
    font-family: 'Bebas Neue', sans-serif; font-weight: 400;
    font-size: 1.7rem; color: var(--text);
    letter-spacing: 0.02em; line-height: 1;
  }}
  .wickets {{ font-size: 1rem; color: var(--accent2); font-weight: 700; }}
  .inn-overs {{
    font-size: 0.78rem; color: var(--muted);
    font-family: 'Roboto Mono', monospace;
  }}
  .inn-rr {{
    margin-left: auto;
    font-family: 'Roboto Mono', monospace;
    font-size: 0.72rem; font-weight: 500; color: var(--text2);
    background: #f0f0f0; padding: 3px 8px;
    border-radius: 5px;
  }}
  .no-score-yet {{
    text-align: center; padding: 14px;
    color: var(--muted); font-size: 0.88rem;
  }}

  /* ── STATUS BAR ── */
  .status-bar {{
    text-align: center; padding: 10px 16px 14px;
    font-size: 0.8rem; font-weight: 600;
    color: var(--live);
    border-top: 1px solid var(--live-border);
    background: var(--live-bg);
    font-family: 'Inter', sans-serif;
  }}

  /* ── RESULT CARDS ── */
  .result-card {{
    padding: 14px 16px;
  }}
  .result-header {{
    display: flex; align-items: center; gap: 8px; margin-bottom: 10px;
  }}
  .result-badge {{
    font-family: 'Roboto Mono', monospace; font-size: 0.6rem; font-weight: 500;
    letter-spacing: 0.1em; color: var(--muted);
    background: #f3f4f6; padding: 2px 7px;
    border-radius: 4px; border: 1px solid #e5e7eb;
    text-transform: uppercase;
  }}
  .result-date, .result-num {{
    font-size: 0.73rem; color: var(--muted);
    font-family: 'Roboto Mono', monospace;
  }}
  .result-teams {{
    display: flex; align-items: center; gap: 8px; flex-wrap: wrap;
  }}
  .r-logo img {{ width: 22px; height: 22px; object-fit: contain; vertical-align: middle; }}
  .r-name {{
    font-family: 'Bebas Neue', sans-serif; font-weight: 400;
    font-size: 1rem; color: var(--text); letter-spacing: 0.06em;
  }}
  .r-scores {{
    font-size: 0.78rem; color: var(--text2); flex: 1;
    text-align: center; font-family: 'Roboto Mono', monospace;
  }}
  .result-status {{
    font-size: 0.76rem; font-weight: 500; color: var(--text2);
    margin-top: 8px; padding-top: 8px;
    border-top: 1px solid var(--border);
  }}

  /* ── FOOTER STATS ── */
  .footer-stats {{
    margin-top: 32px;
    display: flex; justify-content: center; gap: 0;
    background: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--card-r);
    overflow: hidden;
  }}
  .stat-item {{
    text-align: center; flex: 1; padding: 16px 12px;
    border-right: 1px solid var(--border);
  }}
  .stat-item:last-child {{ border-right: none; }}
  .stat-val {{
    font-family: 'Bebas Neue', sans-serif; font-weight: 400;
    font-size: 1.8rem; color: var(--text); line-height: 1;
    letter-spacing: 0.04em;
  }}
  .stat-lbl {{
    font-family: 'Roboto Mono', monospace;
    font-size: 0.62rem; color: var(--muted);
    text-transform: uppercase; letter-spacing: 0.1em; margin-top: 4px;
  }}

  /* ── FOOTER META ── */
  .footer-meta {{
    text-align: center; margin-top: 14px;
    font-size: 0.7rem; color: var(--muted);
    font-family: 'Roboto Mono', monospace;
  }}
  .footer-meta a {{ color: var(--muted); text-decoration: none; }}
  .footer-meta a:hover {{ color: var(--accent); }}

  .no-match, .no-live {{
    text-align: center; padding: 48px 20px;
    color: var(--muted); font-size: 0.9rem;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--card-r);
  }}
  .no-match-icon {{ font-size: 2rem; margin-bottom: 12px; }}
  .no-match-title {{ font-family: 'Bebas Neue', sans-serif; font-size: 1.3rem; color: var(--text); letter-spacing: 0.05em; margin-bottom: 8px; }}
  .no-match-sub {{ font-size: 0.82rem; color: var(--muted); max-width: 340px; margin: 0 auto; line-height: 1.6; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-inner">
    <div class="header-icon">🏏</div>
    <div class="header-text">
      <h1>IPL Live Tracker</h1>
      <p>Indian Premier League · Auto-updates every 30s</p>
    </div>
    <span class="header-badge">IPL 2026</span>
  </div>
</div>
<div class="container">
  {main_content}
  <div class="footer-stats">
    <div class="stat-item">
      <div class="stat-val">{hits}</div>
      <div class="stat-lbl">Page Views</div>
    </div>
    <div class="stat-item">
      <div class="stat-val">{unique}</div>
      <div class="stat-lbl">Unique Visitors</div>
    </div>
    <div class="stat-item">
      <div class="stat-val" id="ttl-val">{ttl}s</div>
      <div class="stat-lbl">Next Refresh</div>
    </div>
  </div>
  <div class="footer-meta">
    Source: <span id="source-val">{source if source in ["LIVE","CACHE"] else "API"}</span> &nbsp;·&nbsp;
    <a href="/debug">raw api</a> &nbsp;·&nbsp;
    <a href="/clearcache">clear cache</a>
  </div>
</div>

<script>
var shortMap = {{'Kolkata Knight Riders':'KKR','Sunrisers Hyderabad':'SRH','Mumbai Indians':'MI','Chennai Super Kings':'CSK','Delhi Capitals':'DC','Royal Challengers Bengaluru':'RCB','Royal Challengers Bangalore':'RCB','Rajasthan Royals':'RR','Punjab Kings':'PBKS','Lucknow Super Giants':'LSG','Gujarat Titans':'GT'}};

function getShort(inning) {{
  var team = inning.split(' Inning ')[0];
  return shortMap[team] || team.substring(0,3).toUpperCase();
}}

function getInnNum(inning) {{
  var parts = inning.split(' Inning ');
  return parts.length > 1 ? parts[1] : '';
}}

function fmtScore(s) {{
  var rr = s.o > 0 ? (s.r / s.o).toFixed(2) : '-';
  return '<div class="innings-row">'
    + '<div class="inn-label">INN ' + getInnNum(s.inning) + '</div>'
    + '<div class="inn-team">' + getShort(s.inning) + '</div>'
    + '<div class="inn-score">' + s.r + '<span class="wickets">/' + s.w + '</span></div>'
    + '<div class="inn-overs">(' + s.o + ' ov)</div>'
    + '<div class="inn-rr">RR ' + rr + '</div>'
    + '</div>';
}}

function pollScores() {{
  fetch('/api/scores')
    .then(function(r) {{ return r.json(); }})
    .then(function(data) {{
      var ttlEl = document.getElementById('ttl-val');
      if (ttlEl) ttlEl.textContent = data.ttl + 's';

      var srcEl = document.getElementById('source-val');
      if (srcEl) srcEl.textContent = data.source;

      data.live.forEach(function(match) {{
        var inningsBlock = document.getElementById('innings-' + match.id);
        if (!inningsBlock) return;
        var html = '';
        match.score.forEach(function(s) {{ html += fmtScore(s); }});
        if (!html) html = '<div class="no-score-yet">' + match.status + '</div>';
        inningsBlock.innerHTML = html;

        var statusEl = document.getElementById('status-' + match.id);
        if (statusEl) statusEl.textContent = match.status;
      }});
    }})
    .catch(function() {{}});
}}

setInterval(pollScores, 15000);
</script>
</body>
</html>"""
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
