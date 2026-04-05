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
        print(f"[REDIS ERROR] {e}")
        return "N/A", "N/A"
 
def fetch_ipl_data():
    cached = cache.get('ipl_raw_json')
    if cached:
        import json
        return json.loads(cached), "CACHE"
 
    if not API_KEY:
        return None, "CONFIG_ERROR"
 
    try:
        url = f"https://api.cricapi.com/v1/currentMatches?apikey={API_KEY}&offset=0"
        response = requests.get(url, timeout=8)
        data = response.json()
 
        if data.get('status') != 'success':
            return None, f"API_ERROR: {data.get('reason', data.get('status'))}"
 
        ipl_matches = [m for m in data.get('data', []) if is_ipl_match(m)]
 
        import json
        cache.setex('ipl_raw_json', 45, json.dumps(ipl_matches))
        return ipl_matches, "LIVE"
 
    except Exception as e:
        print(f"[ERROR] {e}")
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
        <div class="innings-block">
            {innings_html}
        </div>
        <div class="status-bar">{status}</div>
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
    if ttl < 0: ttl = 45
 
    if not matches:
        main_content = '<div class="no-match">No IPL matches found right now</div>'
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
<meta http-equiv="refresh" content="30">
<title>IPL 2026 Live</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@400;600;700;800&family=Barlow:wght@400;500;600&display=swap" rel="stylesheet">
<style>
  :root {{
    --bg:        #eef0f7/*#0a0c14*/;
    --surface:   #fff/*#111520*/;
    --surface2:  #fff/*#181d2e*/;
    --border:    rgba(255,255,255,0.07);
    --accent:    #f5a623;
    --accent2:   #e8365d;
    --live:      #22c55e;
    --text:      #0528a3/*#0a0c14 #eef0f7*/;
    --muted:     #2C687B/*#6b7280*/;
    --card-r:    14px;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    background: var(--bg);
    color: var(--text);
    font-family: 'Barlow', sans-serif;
    min-height: 100vh;
    background-image:
      radial-gradient(ellipse 80% 50% at 50% -10%, rgba(245,166,35,0.08) 0%, transparent 70%),
      radial-gradient(ellipse 60% 40% at 80% 90%, rgba(232,54,93,0.06) 0%, transparent 60%);
  }}
  .header {{ text-align: center; padding: 40px 20px 10px; }}
  .header-logo {{ display: inline-flex; align-items: center; gap: 12px; margin-bottom: 4px; }}
  .ipl-badge {{
    background: linear-gradient(135deg, #f5a623, #e8365d);
    color: white;
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 0.7rem; letter-spacing: 0.15em;
    padding: 3px 10px; border-radius: 4px;
  }}
  .header h1 {{
    font-family: 'Barlow Condensed', sans-serif;
    font-weight: 800; font-size: 2.2rem; letter-spacing: 0.04em;
    text-transform: uppercase; color: var(--text);
  }}
  .header h1 span {{ color: var(--accent); }}
  .header-sub {{ font-size: 0.8rem; color: var(--muted); letter-spacing: 0.08em; text-transform: uppercase; margin-top: 4px; }}
  .container {{ max-width: 680px; margin: 0 auto; padding: 24px 16px 60px; }}
  .section-label {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 0.72rem; letter-spacing: 0.18em; color: var(--accent);
    text-transform: uppercase; margin: 28px 0 12px;
    display: flex; align-items: center; gap: 10px;
  }}
  .section-label::after {{ content: ''; flex: 1; height: 1px; background: var(--border); }}
  .recent-label {{ color: var(--muted); }}
  .match-card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: var(--card-r); overflow: hidden; margin-bottom: 12px;
  }}
  .live-match {{
    border-color: rgba(34,197,94,0.2);
    box-shadow: 0 0 0 1px rgba(34,197,94,0.1), 0 8px 32px rgba(0,0,0,0.4);
  }}
  .card-header {{
    display: flex; align-items: center; gap: 10px;
    padding: 12px 18px; border-bottom: 1px solid var(--border);
    background: var(--surface2);
  }}
  .match-meta {{
    font-size: 0.78rem; color: var(--muted); margin-left: auto;
    text-align: right; white-space: nowrap; overflow: hidden;
    text-overflow: ellipsis; max-width: 70%;
  }}
  .live-badge {{
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(34,197,94,0.12); color: var(--live);
    border: 1px solid rgba(34,197,94,0.3);
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 0.72rem; letter-spacing: 0.12em;
    padding: 3px 10px; border-radius: 20px; white-space: nowrap;
  }}
  .pulse-dot {{
    width: 7px; height: 7px; background: var(--live); border-radius: 50%;
    animation: pulse 1.4s ease infinite;
  }}
  @keyframes pulse {{
    0%,100% {{ box-shadow: 0 0 0 0 rgba(34,197,94,0.6); }}
    50% {{ box-shadow: 0 0 0 5px rgba(34,197,94,0); }}
  }}
  .ended-badge {{
    background: rgba(107,114,128,0.15); color: var(--muted);
    border: 1px solid rgba(107,114,128,0.2);
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 0.72rem; letter-spacing: 0.12em;
    padding: 3px 10px; border-radius: 20px;
  }}
  .teams-row {{
    display: flex; align-items: center; justify-content: space-around;
    padding: 20px 18px 12px; gap: 8px;
  }}
  .team-block {{ display: flex; flex-direction: column; align-items: center; gap: 8px; flex: 1; }}
  .team-logo img {{
    width: 52px; height: 52px; object-fit: contain;
    filter: drop-shadow(0 2px 8px rgba(0,0,0,0.5));
  }}
  .team-name {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 1.3rem; letter-spacing: 0.06em; color: var(--text);
  }}
  .vs-block {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 800;
    font-size: 0.85rem; color: var(--muted); letter-spacing: 0.1em; padding: 0 8px;
  }}
  .innings-block {{ padding: 4px 18px 16px; display: flex; flex-direction: column; gap: 8px; }}
  .innings-row {{
    display: flex; align-items: center; gap: 10px;
    background: var(--surface2); border-radius: 8px;
    padding: 10px 14px; border: 1px solid var(--border);
  }}
  .inn-label {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 0.65rem;
    font-weight: 700; letter-spacing: 0.1em; color: var(--muted); min-width: 32px;
  }}
  .inn-team {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 700;
    font-size: 1rem; color: var(--accent); min-width: 44px;
  }}
  .inn-score {{
    font-family: 'Barlow Condensed', sans-serif; font-weight: 800;
    font-size: 1.6rem; color: var(--text); letter-spacing: -0.01em; line-height: 1;
  }}
  .wickets {{ font-size: 1.1rem; color: var(--accent2); font-weight: 700; }}
  .inn-overs {{ font-size: 0.82rem; color: var(--muted); }}
  .inn-rr {{
    margin-left: auto; font-family: 'Barlow Condensed', sans-serif;
    font-size: 0.82rem; font-weight: 600; color: var(--muted);
    background: rgba(255,255,255,0.04); padding: 3px 8px;
    border-radius: 6px; border: 1px solid var(--border);
  }}
  .no-score-yet {{ text-align: center; padding: 14px; color: var(--muted); font-size: 0.9rem; }}
  .status-bar {{ text-align: center; padding: 10px 18px 14px; font-size: 0.82rem; font-weight: 500; color: var(--live); }}
  .result-card {{ padding: 12px 16px; border-radius: 10px; opacity: 0.85; }}
  .result-header {{ display: flex; font-weight: bold; align-items: center; gap: 8px; margin-bottom: 8px; }}
  .result-badge {{
    font-family: 'Barlow Condensed', sans-serif; font-size: 0.65rem; font-weight: 700;
    letter-spacing: 0.1em; color: var(--muted);
    background: rgba(255,255,255,0.05); padding: 2px 7px;
    border-radius: 4px; border: 1px solid var(--border);
  }}
  .result-date, .result-num {{ font-size: 0.75rem; color: var(--muted); }}
  .result-teams {{ display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }}
  .r-logo img {{ width: 22px; height: 22px; object-fit: contain; vertical-align: middle; }}
  .r-name {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 0.95rem; color: var(--text); }}
  .r-scores {{ font-size: 0.8rem; font-weight: bold; color: var(--muted); flex: 1; text-align: center; }}
  .result-status {{ font-size: 0.78rem; font-weight: bold; color: var(--muted); margin-top: 6px; padding-top: 6px; border-top: 1px solid var(--border); }}
  .footer-stats {{
    margin-top: 32px; display: flex; justify-content: center; gap: 32px;
    padding: 16px; background: var(--surface);
    border: 1px solid var(--border); border-radius: var(--card-r);
  }}
  .stat-item {{ text-align: center; }}
  .stat-val {{ font-family: 'Barlow Condensed', sans-serif; font-weight: 700; font-size: 1.6rem; color: var(--accent); line-height: 1; }}
  .stat-lbl {{ font-size: 0.7rem; color: var(--muted); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 3px; }}
  .footer-meta {{ text-align: center; margin-top: 14px; font-size: 0.72rem; color: var(--muted); }}
  .footer-meta a {{ color: var(--muted); text-decoration: none; }}
  .footer-meta a:hover {{ color: var(--accent); }}
  .no-match, .no-live {{ text-align: center; padding: 40px; color: var(--muted); font-size: 0.9rem; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-logo"><span class="ipl-badge">IPL 2026</span></div>
  <h1>🏏 Live <span>Tracker</span></h1>
  <p class="header-sub">Indian Premier League · Auto-updates every 30s</p>
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
      <div class="stat-val">{ttl}s</div>
      <div class="stat-lbl">Next Refresh</div>
    </div>
  </div>
  <div class="footer-meta">
    Source: {source} &nbsp;·&nbsp;
    <a href="/debug">raw api</a> &nbsp;·&nbsp;
    <a href="/clearcache">clear cache</a>
  </div>
</div>
</body>
</html>"""
 
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
 
