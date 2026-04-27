from flask import Flask, send_from_directory
from flask_socketio import SocketIO
import threading
import os
import psutil

app = Flask(__name__)
app.config['SECRET_KEY'] = 'cypher_secret'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Always resolve paths relative to this file's location
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

ui_state = {
    "status": "standby",
    "user_text": "",
    "cypher_text": "",
    "mode": "home",
}

def set_ui_state(status=None, user_text=None, cypher_text=None, mode=None):
    """Call this from main.py to push updates to the UI instantly."""
    if status is not None:
        ui_state["status"] = status
    if user_text is not None:
        ui_state["user_text"] = user_text
    if cypher_text is not None:
        ui_state["cypher_text"] = cypher_text
    if mode is not None:
        ui_state["mode"] = mode
    socketio.emit('state_update', ui_state)

@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "cypher.html")

@app.route("/model")
def model():
    return send_from_directory(BASE_DIR, "Cypher_.vrm")

@app.route("/state")
def state():
    return ui_state

# Background stats sampler
stats_cache = {"cpu": 0, "ram": 0, "gpu": 0}

# Sports cache — updated in background
sports_cache = {"teams": [], "standings": [], "loading": True}

def sample_stats():
    global stats_cache
    import time
    try:
        from pynvml import nvmlInit, nvmlDeviceGetHandleByIndex, nvmlDeviceGetUtilizationRates
        nvmlInit()
        gpu_handle = nvmlDeviceGetHandleByIndex(0)
        has_gpu = True
    except:
        has_gpu = False
        gpu_handle = None

    while True:
        try:
            cpu = round(psutil.cpu_percent(interval=1))
            ram = round(psutil.virtual_memory().percent)
            gpu = 0
            if has_gpu:
                try:
                    from pynvml import nvmlDeviceGetUtilizationRates
                    util = nvmlDeviceGetUtilizationRates(gpu_handle)
                    # util.gpu is 3D/compute only — matches Task Manager
                    gpu = round(util.gpu)
                except:
                    try:
                        # Fallback to subprocess nvidia-smi
                        import subprocess
                        result = subprocess.run(
                            ['nvidia-smi', '--query-gpu=utilization.gpu', '--format=csv,noheader,nounits'],
                            capture_output=True, text=True, timeout=2
                        )
                        gpu = round(float(result.stdout.strip()))
                    except:
                        pass
            stats_cache = {"cpu": cpu, "ram": ram, "gpu": gpu}
        except Exception as e:
            print(f"Stats sample error: {e}")
        time.sleep(1)

# Stats thread started in start_ui() after Flask is running

@app.route("/stats")
def stats():
    return stats_cache

# ESPN logo URL builder
TEAM_SLUGS = {
    # NHL
    "anaheim ducks": ("nhl", "ana"), "arizona coyotes": ("nhl", "ari"),
    "boston bruins": ("nhl", "bos"), "buffalo sabres": ("nhl", "buf"),
    "calgary flames": ("nhl", "cgy"), "carolina hurricanes": ("nhl", "car"),
    "chicago blackhawks": ("nhl", "chi"), "colorado avalanche": ("nhl", "col"),
    "columbus blue jackets": ("nhl", "cbj"), "dallas stars": ("nhl", "dal"),
    "detroit red wings": ("nhl", "det"), "edmonton oilers": ("nhl", "edm"),
    "florida panthers": ("nhl", "fla"), "los angeles kings": ("nhl", "la"),
    "minnesota wild": ("nhl", "min"), "montreal canadiens": ("nhl", "mtl"),
    "nashville predators": ("nhl", "nsh"), "new jersey devils": ("nhl", "nj"),
    "new york islanders": ("nhl", "nyi"), "new york rangers": ("nhl", "nyr"),
    "ottawa senators": ("nhl", "ott"), "philadelphia flyers": ("nhl", "phi"),
    "pittsburgh penguins": ("nhl", "pit"), "san jose sharks": ("nhl", "sj"),
    "seattle kraken": ("nhl", "sea"), "st. louis blues": ("nhl", "stl"),
    "tampa bay lightning": ("nhl", "tb"), "toronto maple leafs": ("nhl", "tor"),
    "utah hockey club": ("nhl", "utah"), "vancouver canucks": ("nhl", "van"),
    "vegas golden knights": ("nhl", "vgk"), "washington capitals": ("nhl", "wsh"),
    "winnipeg jets": ("nhl", "wpg"),
    # MLB
    "arizona diamondbacks": ("mlb", "ari"), "atlanta braves": ("mlb", "atl"),
    "baltimore orioles": ("mlb", "bal"), "boston red sox": ("mlb", "bos"),
    "chicago cubs": ("mlb", "chc"), "chicago white sox": ("mlb", "chw"),
    "cincinnati reds": ("mlb", "cin"), "cleveland guardians": ("mlb", "cle"),
    "colorado rockies": ("mlb", "col"), "detroit tigers": ("mlb", "det"),
    "houston astros": ("mlb", "hou"), "kansas city royals": ("mlb", "kc"),
    "los angeles angels": ("mlb", "laa"), "los angeles dodgers": ("mlb", "lad"),
    "miami marlins": ("mlb", "mia"), "milwaukee brewers": ("mlb", "mil"),
    "minnesota twins": ("mlb", "min"), "new york mets": ("mlb", "nym"),
    "new york yankees": ("mlb", "nyy"), "oakland athletics": ("mlb", "oak"),
    "philadelphia phillies": ("mlb", "phi"), "pittsburgh pirates": ("mlb", "pit"),
    "san diego padres": ("mlb", "sd"), "san francisco giants": ("mlb", "sf"),
    "seattle mariners": ("mlb", "sea"), "st. louis cardinals": ("mlb", "stl"),
    "tampa bay rays": ("mlb", "tb"), "texas rangers": ("mlb", "tex"),
    "toronto blue jays": ("mlb", "tor"), "washington nationals": ("mlb", "wsh"),
    # NBA
    "atlanta hawks": ("nba", "atl"), "boston celtics": ("nba", "bos"),
    "brooklyn nets": ("nba", "bkn"), "charlotte hornets": ("nba", "cha"),
    "chicago bulls": ("nba", "chi"), "cleveland cavaliers": ("nba", "cle"),
    "dallas mavericks": ("nba", "dal"), "denver nuggets": ("nba", "den"),
    "detroit pistons": ("nba", "det"), "golden state warriors": ("nba", "gs"),
    "houston rockets": ("nba", "hou"), "indiana pacers": ("nba", "ind"),
    "los angeles clippers": ("nba", "lac"), "los angeles lakers": ("nba", "lal"),
    "memphis grizzlies": ("nba", "mem"), "miami heat": ("nba", "mia"),
    "milwaukee bucks": ("nba", "mil"), "minnesota timberwolves": ("nba", "min"),
    "new orleans pelicans": ("nba", "no"), "new york knicks": ("nba", "ny"),
    "oklahoma city thunder": ("nba", "okc"), "orlando magic": ("nba", "orl"),
    "philadelphia 76ers": ("nba", "phi"), "phoenix suns": ("nba", "phx"),
    "portland trail blazers": ("nba", "por"), "sacramento kings": ("nba", "sac"),
    "san antonio spurs": ("nba", "sa"), "toronto raptors": ("nba", "tor"),
    "utah jazz": ("nba", "utah"), "washington wizards": ("nba", "wsh"),
    # NFL
    "arizona cardinals": ("nfl", "ari"), "atlanta falcons": ("nfl", "atl"),
    "baltimore ravens": ("nfl", "bal"), "buffalo bills": ("nfl", "buf"),
    "carolina panthers": ("nfl", "car"), "chicago bears": ("nfl", "chi"),
    "cincinnati bengals": ("nfl", "cin"), "cleveland browns": ("nfl", "cle"),
    "dallas cowboys": ("nfl", "dal"), "denver broncos": ("nfl", "den"),
    "detroit lions": ("nfl", "det"), "green bay packers": ("nfl", "gb"),
    "houston texans": ("nfl", "hou"), "indianapolis colts": ("nfl", "ind"),
    "jacksonville jaguars": ("nfl", "jax"), "kansas city chiefs": ("nfl", "kc"),
    "las vegas raiders": ("nfl", "lv"), "los angeles chargers": ("nfl", "lac"),
    "los angeles rams": ("nfl", "lar"), "miami dolphins": ("nfl", "mia"),
    "minnesota vikings": ("nfl", "min"), "new england patriots": ("nfl", "ne"),
    "new orleans saints": ("nfl", "no"), "new york giants": ("nfl", "nyg"),
    "new york jets": ("nfl", "nyj"), "philadelphia eagles": ("nfl", "phi"),
    "pittsburgh steelers": ("nfl", "pit"), "san francisco 49ers": ("nfl", "sf"),
    "seattle seahawks": ("nfl", "sea"), "tampa bay buccaneers": ("nfl", "tb"),
    "tennessee titans": ("nfl", "ten"), "washington commanders": ("nfl", "wsh"),
}

def get_logo_url(team_name, sport):
    key = team_name.lower().strip()
    # Hard override for NCAA teams
    ncaa_overrides = {
        "oregon ducks": "https://a.espncdn.com/i/teamlogos/ncaa/500/2483.png",
    }
    if key in ncaa_overrides:
        return ncaa_overrides[key]
    if key in TEAM_SLUGS:
        s, slug = TEAM_SLUGS[key]
        return f"https://a.espncdn.com/i/teamlogos/{s}/500/{slug}.png"
    return f"https://a.espncdn.com/i/teamlogos/{sport}/500/default.png"

def refresh_sports_cache():
    import requests as req
    import pytz
    from datetime import datetime
    global sports_cache

    FAVORITE_TEAMS = [
        {"name": "Tampa Bay Lightning", "sport": "nhl",   "search_name": "Tampa Bay Lightning", "espn_slug": "tb",  "active": True},
        {"name": "Tampa Bay Rays",      "sport": "mlb",   "search_name": "Tampa Bay Rays",      "espn_slug": "tb",  "active": True},
        {"name": "Orlando Magic",       "sport": "nba",   "search_name": "Orlando Magic",       "espn_slug": "orl", "active": True},
        {"name": "Tampa Bay Buccaneers","sport": "nfl",   "search_name": "Tampa Bay Buccaneers","espn_slug": "tb",  "active": False},
        {"name": "Oregon Ducks",        "sport": "ncaaf", "search_name": "Oregon",              "espn_slug": "ore", "active": False},
    ]

    SPORT_ENDPOINTS = {
        "mlb":   "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb",
        "nfl":   "https://site.api.espn.com/apis/site/v2/sports/football/nfl",
        "nba":   "https://site.api.espn.com/apis/site/v2/sports/basketball/nba",
        "nhl":   "https://site.api.espn.com/apis/site/v2/sports/hockey/nhl",
        "ncaaf": "https://site.api.espn.com/apis/site/v2/sports/football/college-football",
    }

    SPORT_LEAGUE = {
        "nhl": "hockey/nhl", "mlb": "baseball/mlb",
        "nba": "basketball/nba", "nfl": "football/nfl", "ncaaf": None
    }

    est = pytz.timezone('America/New_York')
    today = datetime.now(est).strftime("%Y%m%d")
    teams_data = []

    for team in FAVORITE_TEAMS:
        team_info = {
            "name": team["name"], "record": "0-0",
            "game_today": False, "state": "pre",
            "opponent": "", "opponent_logo": "",
            "our_logo": get_logo_url(team["name"], team["sport"]),
            "game_time": "", "our_score": "", "opp_score": "",
            "status_detail": "", "news": [], "player_stats": [],
            "active": team.get("active", True),
        }

        # Record — use team endpoint with record
        try:
            r = req.get(f"{SPORT_ENDPOINTS[team['sport']]}/teams/{team['espn_slug']}", timeout=5)
            if r.status_code == 200:
                t_info = r.json().get("team", {})
                rec = t_info.get("record", {}).get("items", [])
                if rec:
                    team_info["record"] = rec[0].get("summary", "0-0")
        except: pass

        # Today's game
        if team["active"]:
            try:
                r = req.get(f"{SPORT_ENDPOINTS[team['sport']]}/scoreboard?dates={today}", timeout=5)
                if r.status_code == 200:
                    for event in r.json().get("events",[]):
                        competitors = event.get("competitions",[{}])[0].get("competitors",[])
                        names = [c.get("team",{}).get("displayName","") for c in competitors]
                        if any(team["search_name"].lower() in n.lower() for n in names):
                            team_info["game_today"] = True
                            status = event.get("status",{})
                            team_info["state"] = status.get("type",{}).get("state","pre")
                            team_info["status_detail"] = status.get("type",{}).get("shortDetail","")
                            for c in competitors:
                                c_name = c.get("team",{}).get("displayName","")
                                if team["search_name"].lower() not in c_name.lower():
                                    team_info["opponent"] = c_name
                                    team_info["opp_score"] = c.get("score","")
                                    team_info["opponent_logo"] = get_logo_url(c_name, team["sport"])
                                else:
                                    team_info["our_score"] = c.get("score","")
                            raw_time = event.get("date","")
                            if raw_time:
                                try:
                                    from datetime import datetime as dt
                                    utc = dt.strptime(raw_time, "%Y-%m-%dT%H:%MZ")
                                    utc = pytz.utc.localize(utc)
                                    est_t = utc.astimezone(est)
                                    team_info["game_time"] = est_t.strftime("%I:%M %p").lstrip("0")
                                except: pass
                            break
            except: pass

        # News
        try:
            league = SPORT_LEAGUE.get(team["sport"])
            if league:
                news_url = f"https://site.api.espn.com/apis/site/v2/sports/{league}/news?team={team['espn_slug']}&limit=2"
                r = req.get(news_url, timeout=5)
                if r.status_code == 200:
                    articles = r.json().get("articles", [])
                    team_info["news"] = [a.get("headline","") for a in articles[:2] if a.get("headline")]
                    print(f"  {team['name']} news: {len(team_info['news'])}", flush=True)
        except Exception as e:
            print(f"  News error {team['name']}: {e}", flush=True)

        # Team stats
        try:
            league = SPORT_LEAGUE.get(team["sport"])
            if league and team.get("active"):
                url = f"https://site.api.espn.com/apis/site/v2/sports/{league}/teams/{team['espn_slug']}/statistics"
                r = req.get(url, timeout=5)
                if r.status_code == 200:
                    cats = r.json().get("results", {}).get("stats", {}).get("categories", [])
                    stats = []
                    WANT = {
                        "nhl": ["goals", "assists", "savePct", "plusMinus"],
                        "mlb": ["teamGamesPlayed", "homeRuns", "winPct", "ERA"],
                        "nba": ["points", "assists", "rebounds", "fieldGoalPct"],
                        "nfl": ["passingYards", "rushingYards", "sacks", "interceptions"],
                    }
                    # For MLB deduplicate by label
                    seen_labels = set()
                    want = WANT.get(team["sport"], [])
                    for cat in cats:
                        for stat in cat.get("stats", []):
                            if stat.get("name") in want:
                                label = stat.get("abbreviation", stat.get("name",""))
                                if label not in seen_labels:
                                    seen_labels.add(label)
                                    stats.append({
                                        "label": label,
                                        "value": stat.get("displayValue", str(stat.get("value","")))
                                    })
                    team_info["player_stats"] = stats[:6]
                    print(f"  {team['name']} stats: {len(stats)}", flush=True)
        except Exception as e:
            print(f"  Stats error {team['name']}: {e}", flush=True)

        teams_data.append(team_info)

    # NHL Standings
    standings_data = []
    try:
        r = req.get("https://site.api.espn.com/apis/v2/sports/hockey/nhl/standings", timeout=5)
        if r.status_code == 200:
            for group in r.json().get("children", []):
                entries = group.get("standings", {}).get("entries", [])
                if any("Tampa Bay" in e.get("team",{}).get("displayName","") for e in entries):
                    for entry in entries:
                        t_name = entry.get("team", {}).get("displayName", "")
                        record = ""
                        for stat in entry.get("stats", []):
                            if stat.get("name") == "overall":
                                record = stat.get("displayValue", "")
                                break
                        standings_data.append({
                            "name": t_name.replace("Tampa Bay ", "TB "),
                            "record": record,
                            "is_my_team": "Tampa Bay Lightning" in t_name
                        })
                    break
        print(f"  Standings: {len(standings_data)}", flush=True)
    except Exception as e:
        print(f"  Standings error: {e}", flush=True)

    sports_cache = {"teams": teams_data, "standings": standings_data[:6], "loading": False}
    print(f"Cache set: {len(teams_data)} teams, {len(standings_data)} standings", flush=True)


def sports_background_loop():
    import time, traceback, sys
    print("Sports background loop started", flush=True)
    while True:
        try:
            print("Sports cache refreshing...", flush=True)
            refresh_sports_cache()
            print("Sports cache done!", flush=True)
        except Exception as e:
            print(f"Sports cache CRASHED: {e}", flush=True)
            traceback.print_exc(file=sys.stdout)
            sys.stdout.flush()
        time.sleep(120)

threading.Thread(target=sports_background_loop, daemon=True).start()

@app.route("/sports")
def sports():
    return sports_cache

@app.route("/weather/<location>")
def weather(location):
    try:
        import requests as req
        r = req.get(f"https://wttr.in/{location}?format=%t+%C&u", timeout=5)
        text = r.text.strip().replace('+', '').replace('degF', 'F')
        return text
    except:
        return "--"

def run_ui():
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, use_reloader=False, allow_unsafe_werkzeug=True)

def start_ui():
    t = threading.Thread(target=run_ui, daemon=True)
    t.start()
    import time
    time.sleep(1)
    threading.Thread(target=sample_stats, daemon=True).start()
    print("Cypher UI running at http://localhost:5000")

if __name__ == "__main__":
    print("Cypher UI running at http://localhost:5000")
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)