// ─── CYPHER-SPORTS.JS ───────────────────────────────────────────────────────
// Sports widgets, team cards, ticker, standings
// NHL live widget: score, period, series, goalies, last goal, shots, faceoffs

// ─── LOGO HELPER ────────────────────────────────────────────────────────────
function logoImg(url, size) {
  size = size || 32; if (!url) return '';
  return '<img src="' + url + '" width="' + size + '" height="' + size + '" style="object-fit:contain;opacity:0.9;flex-shrink:0;">';
}

// ─── HEADSHOT HELPER ────────────────────────────────────────────────────────
function headshotImg(url, size, border) {
  if (!url) return '<div style="width:' + size + 'px;height:' + size + 'px;border-radius:50%;background:rgba(255,60,180,0.1);border:' + (border||'1.5px solid rgba(255,60,180,0.3)') + ';flex-shrink:0;"></div>';
  return '<img src="/headshot?url=' + encodeURIComponent(url) + '" width="' + size + '" height="' + size + '" style="border-radius:50%;object-fit:cover;border:' + (border||'1.5px solid rgba(255,60,180,0.4)') + ';flex-shrink:0;">';
}

// ─── STAT PILL ───────────────────────────────────────────────────────────────
function statPill(label, val, col) {
  col = col || 'rgba(255,200,230,0.9)';
  return '<div style="display:flex;flex-direction:column;align-items:center;padding:4px 8px;border:1px solid rgba(255,60,180,0.15);border-radius:3px;background:rgba(255,60,180,0.04);">' +
    '<div style="font-size:13px;font-weight:bold;color:' + col + ';line-height:1;">' + val + '</div>' +
    '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.1em;margin-top:2px;">' + label + '</div>' +
  '</div>';
}

// ─── FETCH SPORTS DATA ───────────────────────────────────────────────────────
function fetchSportsData() {
  fetch('/sports').then(function(r) { return r.json(); }).then(function(data) {
    renderSports(data);
    renderStandingsAndStreak(data);
    renderTicker(data);
  }).catch(function(){});
}
window.fetchSportsData = fetchSportsData;

// ─── STANDINGS + STREAK ──────────────────────────────────────────────────────
function renderStandingsAndStreak(data) {
  var topEl = document.getElementById('sports-right-top-content');
  if (topEl && data.standings && data.standings.length > 0) {
    var html = '';
    data.standings.forEach(function(s) {
      var cls = s.is_my_team ? ' standing-mine' : '';
      html += '<div class="standing-row' + cls + '"><span class="standing-name">' + s.name + '</span><span class="standing-record">' + s.record + '</span></div>';
    });
    topEl.innerHTML = html;
  }
  var botEl = document.getElementById('sports-right-bottom-content');
  if (botEl && data.teams) {
    var active = data.teams.filter(function(t) { return t.active !== false && t.player_stats && t.player_stats.length > 0; });
    if (!active.length) { botEl.innerHTML = '<div style="color:rgba(255,200,230,0.3);font-size:9px;">Loading stats...</div>'; return; }
    var html = '';
    active.forEach(function(t) {
      html += '<div style="margin-bottom:12px;"><div style="display:flex;align-items:center;gap:6px;margin-bottom:6px;">' + logoImg(t.our_logo, 20) + '<div style="font-size:9px;color:rgba(0,200,255,0.7);letter-spacing:0.1em;">' + t.name.replace('Tampa Bay ', 'TB ') + '</div></div>';
      t.player_stats.forEach(function(s) {
        html += '<div style="display:flex;justify-content:space-between;align-items:center;padding:6px 4px;font-size:13px;border-bottom:1px solid rgba(255,60,180,0.1);"><span style="color:rgba(255,80,180,0.8);letter-spacing:0.08em;">' + s.label + '</span><span style="color:rgba(255,200,230,0.95);font-weight:bold;font-size:15px;">' + s.value + '</span></div>';
      });
      html += '</div>';
    });
    botEl.innerHTML = html;
  }
}

// ─── TICKER ─────────────────────────────────────────────────────────────────
function renderTicker(data) {
  var ticker = document.getElementById('scores-ticker');
  var tickerContent = document.getElementById('ticker-content');
  if (!ticker || !tickerContent || !data.teams) return;
  var segments = [];
  data.teams.forEach(function(t) {
    var name = t.name.replace('Tampa Bay ', 'TB ');
    if (!t.active) {
      if (t.news && t.news.length > 0) {
        t.news.slice(0, 2).forEach(function(h) {
          if (!h) return;
          segments.push('<div class="ticker-item"><img src="' + t.our_logo + '" width="44" height="44" style="object-fit:contain;flex-shrink:0;"><span class="ticker-news-badge news" style="margin-left:12px;">NEWS</span><div class="ticker-news-text" style="margin-left:8px;max-width:500px;">' + h + '</div></div>');
          segments.push('<div class="ticker-divider"></div>');
        });
      }
      return;
    }
    var seg = '<div class="ticker-item">';
    seg += '<div style="display:flex;flex-direction:column;align-items:center;gap:2px;"><img src="' + t.our_logo + '" width="44" height="44" style="object-fit:contain;"><div style="font-size:9px;color:rgba(0,200,255,0.7);">' + t.record + '</div></div>';
    if (t.state === 'in') {
      seg += '<span class="ticker-live-badge" style="margin:0 8px;">LIVE</span>';
      seg += '<div class="ticker-score">' + t.our_score + '</div>';
      seg += '<div style="font-size:16px;color:rgba(255,200,230,0.3);margin:0 4px;">—</div>';
      seg += '<div class="ticker-score">' + t.opp_score + '</div>';
      seg += '<div style="font-size:8px;color:rgba(255,80,180,0.6);margin:0 6px;">' + t.status_detail + '</div>';
      if (t.opponent_logo) seg += '<img src="' + t.opponent_logo + '" width="40" height="40" style="object-fit:contain;opacity:0.8;">';
    } else if (t.game_today && t.state === 'pre') {
      seg += '<div style="font-size:14px;font-weight:bold;color:rgba(255,200,230,0.9);margin:0 12px;">' + t.game_time + '</div>';
      if (t.opponent_logo) seg += '<img src="' + t.opponent_logo + '" width="40" height="40" style="object-fit:contain;opacity:0.8;">';
    } else if (t.state === 'post') {
      var won = parseInt(t.our_score) > parseInt(t.opp_score);
      var col = won ? 'rgba(50,255,100,0.9)' : 'rgba(255,50,50,0.9)';
      seg += '<div style="font-size:18px;font-weight:bold;color:' + col + ';margin:0 10px;">' + t.our_score + '—' + t.opp_score + '</div>';
      seg += '<div style="font-size:9px;font-weight:bold;color:' + col + ';margin-right:8px;">' + (won ? 'WIN' : 'LOSS') + '</div>';
      if (t.opponent_logo) seg += '<img src="' + t.opponent_logo + '" width="36" height="36" style="object-fit:contain;opacity:0.7;">';
    } else {
      seg += '<div style="font-size:10px;color:rgba(255,200,230,0.2);margin:0 12px;letter-spacing:0.1em;">OFF</div>';
    }
    seg += '</div>';
    if (t.news && t.news.length > 0) {
      t.news.forEach(function(headline) {
        if (!headline) return;
        segments.push('<div class="ticker-divider"></div>');
        segments.push('<div class="ticker-item"><img src="' + t.our_logo + '" width="36" height="36" style="object-fit:contain;flex-shrink:0;"><span class="ticker-news-badge news" style="margin-left:8px;">NEWS</span><div class="ticker-news-text" style="margin-left:8px;">' + headline + '</div></div>');
      });
    }
    segments.push(seg);
    segments.push('<div class="ticker-divider"></div>');
  });
  var segHtml = segments.join('');
  tickerContent.innerHTML = '<div class="ticker-inner">' + segHtml + '</div><div class="ticker-inner">' + segHtml + '</div>';
  ticker.classList.add('active');
}


// ─── NHL LIVE WIDGET ─────────────────────────────────────────────────────────
var _nhlWidgetCount = 0;
function renderNHLLive(t, pos) {
  var sit = t.situation || {};
  var lg = sit.last_goal || {};
  var goalies = sit.goalies || [];
  var name = t.name.replace('Tampa Bay ', 'TB ');
  var widgetId = 'nhl' + (++_nhlWidgetCount);

  // Parse shot counts
  var ourShots = parseInt(sit.our_shots) || 0;
  var oppShots = parseInt(sit.opp_shots) || 0;
  var totalShots = ourShots + oppShots || 1;

  // Strength indicator from last play text or PP data
  var strengthLabel = '5v5';
  var strengthCol = 'rgba(255,200,230,0.4)';
  if (sit.our_pp && sit.our_pp !== '--' && sit.our_pp.split('/')[0] !== '0') {
    strengthLabel = '5v4 PP'; strengthCol = 'rgba(50,220,120,0.8)';
  }

  // Border fix: use box-shadow for live glow instead of border bleed
  var html = '<div class="team-widget" style="left:' + pos.left + 'px;top:' + pos.top + 'px;width:' + pos.width + 'px;height:' + pos.height + 'px;display:flex;flex-direction:column;border:1px solid rgba(255,50,50,0.5);box-shadow:0 0 12px rgba(255,50,50,0.15) inset;overflow:hidden;">';

  // ── HEADER ──
  html += '<div style="padding:4px 10px;border-bottom:1px solid rgba(255,50,50,0.25);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">';
  html += '<div style="font-size:8px;letter-spacing:0.15em;color:rgba(0,200,255,0.7);">' + name + '</div>';
  html += '<div style="display:flex;align-items:center;gap:10px;">';
  if (sit.series) html += '<div style="font-size:8px;color:rgba(255,200,230,0.35);letter-spacing:0.08em;">' + sit.series + '</div>';
  html += '<div style="font-size:8px;font-weight:bold;color:' + strengthCol + ';letter-spacing:0.1em;">' + strengthLabel + '</div>';
  html += '<span class="live-dot"></span>';
  html += '</div></div>';

  // ── SCOREBOARD ──
  var tbAhead = parseInt(t.our_score) >= parseInt(t.opp_score);
  var ourScoreCol = tbAhead ? 'rgba(50,255,100,0.95)' : 'rgba(255,200,230,0.95)';
  var oppScoreCol = !tbAhead ? 'rgba(255,50,50,0.9)' : 'rgba(255,200,230,0.45)';

  html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 14px;border-bottom:1px solid rgba(255,60,180,0.12);flex-shrink:0;">';
  html += '<div style="display:flex;align-items:center;gap:8px;">' + logoImg(t.our_logo, 30) + '<div style="font-size:32px;font-weight:bold;color:' + ourScoreCol + ';line-height:1;">' + t.our_score + '</div></div>';
  html += '<div style="text-align:center;">';
  html += '<div style="font-size:11px;font-weight:bold;color:rgba(255,80,180,0.85);letter-spacing:0.1em;">P' + (sit.period||'?') + ' &mdash; ' + (sit.clock||'--:--') + '</div>';
  html += '<div style="font-size:8px;color:rgba(255,200,230,0.25);margin-top:1px;">' + t.status_detail + '</div>';
  html += '</div>';
  html += '<div style="display:flex;align-items:center;gap:8px;"><div style="font-size:32px;font-weight:bold;color:' + oppScoreCol + ';line-height:1;">' + t.opp_score + '</div>' + logoImg(t.opponent_logo, 30) + '</div>';
  html += '</div>';

  // Parse shot counts for shot bars
  var ourShots = parseInt(sit.our_shots) || 0;
  var oppShots = parseInt(sit.opp_shots) || 0;
  var totalShots = ourShots + oppShots || 1;

  // ── MAIN CONTENT: 3 COLUMNS ──
  html += '<div style="display:flex;flex:1;min-height:0;overflow:hidden;">';

  // ── COL 1: GOALIES + SHOT BARS ──
  html += '<div style="width:185px;flex-shrink:0;padding:7px 9px;border-right:1px solid rgba(255,60,180,0.1);display:flex;flex-direction:column;">';
  html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:5px;flex-shrink:0;">GOALIES</div>';
  if (goalies.length > 0) {
    goalies.slice(0, 2).forEach(function(g) {
      var isTB = t.our_team_id && g.team_id === t.our_team_id;
      var svPct = parseInt(g.shots) > 0 ? Math.round((parseInt(g.saves)/parseInt(g.shots))*1000)/10 : 0;
      html += '<div style="display:flex;align-items:center;gap:7px;padding:4px 0;border-bottom:1px solid rgba(255,60,180,0.06);">';
      html += headshotImg(g.headshot, 36, '2px solid ' + (isTB?'rgba(0,200,255,0.6)':'rgba(255,60,180,0.2)'));
      html += '<div style="flex:1;min-width:0;">';
      html += '<div style="font-size:10px;font-weight:bold;color:' + (isTB?'rgba(255,200,230,0.95)':'rgba(255,200,230,0.5)') + ';white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + g.name + '</div>';
      html += '<div style="font-size:10px;color:' + (isTB?'rgba(0,200,255,0.8)':'rgba(0,200,255,0.4)') + ';font-weight:bold;">' + g.saves + '/' + g.shots + ' <span style="font-size:8px;font-weight:normal;color:rgba(255,200,230,0.3);">SVS</span>';
      if (svPct > 0) html += ' <span style="font-size:8px;color:rgba(255,200,230,0.3);">' + svPct.toFixed(1) + '%</span>';
      html += '</div></div></div>';
    });
  } else {
    html += '<div style="font-size:9px;color:rgba(255,200,230,0.2);">Loading...</div>';
  }
  // Shot bars
  var tbPct = Math.round((ourShots/totalShots)*100);
  var tbBarCol = tbPct >= 50 ? 'rgba(50,220,120,0.7)' : 'rgba(0,200,255,0.6)';
  var oppPct = 100 - tbPct;
  var oppBarCol = oppPct > 60 ? 'rgba(255,50,50,0.7)' : 'rgba(255,80,180,0.5)';
  html += '<div style="margin-top:auto;padding-top:6px;border-top:1px solid rgba(255,60,180,0.08);">';
  html += '<div style="font-size:7px;color:rgba(255,80,180,0.4);letter-spacing:0.12em;margin-bottom:5px;">SHOT PRESSURE</div>';
  html += '<div style="margin-bottom:5px;"><div style="display:flex;justify-content:space-between;margin-bottom:2px;"><span style="font-size:8px;color:rgba(0,200,255,0.7);">TB</span><span style="font-size:9px;font-weight:bold;color:' + tbBarCol + ';">' + ourShots + '</span></div><div style="height:5px;background:rgba(255,60,180,0.1);border-radius:3px;overflow:hidden;"><div style="height:100%;width:' + tbPct + '%;background:' + tbBarCol + ';border-radius:3px;transition:width 0.8s ease;"></div></div></div>';
  html += '<div><div style="display:flex;justify-content:space-between;margin-bottom:2px;"><span style="font-size:8px;color:rgba(255,80,180,0.5);">OPP</span><span style="font-size:9px;font-weight:bold;color:' + oppBarCol + ';">' + oppShots + '</span></div><div style="height:5px;background:rgba(255,60,180,0.1);border-radius:3px;overflow:hidden;"><div style="height:100%;width:' + oppPct + '%;background:' + oppBarCol + ';border-radius:3px;transition:width 0.8s ease;"></div></div></div>';
  html += '</div>';
  html += '</div>'; // end col 1

  // ── COL 2: GOAL LIGHT + LAST GOAL ──
  html += '<div style="display:flex;flex-direction:column;flex:1;min-width:0;border-right:1px solid rgba(255,60,180,0.1);">';

  // GOAL LIGHT — tracks TB score changes, flashes red when TB scores
  var tbScore = parseInt(t.our_score) || 0;
  var prevScore = window['_nhl_prev_score_' + widgetId] || 0;
  var justScored = tbScore > prevScore && prevScore > 0;
  window['_nhl_prev_score_' + widgetId] = tbScore;
  var lightActive = justScored;
  // Keep light on for ~10 seconds after goal by storing timestamp
  var now = Date.now();
  if (justScored) window['_nhl_goal_ts_' + widgetId] = now;
  var goalTs = window['_nhl_goal_ts_' + widgetId] || 0;
  lightActive = (now - goalTs) < 10000 && goalTs > 0;

  html += '<div style="padding:8px 10px;border-bottom:1px solid rgba(255,60,180,0.08);display:flex;align-items:center;gap:12px;flex-shrink:0;">';
  // The light
  if (lightActive) {
    html += '<div style="width:36px;height:36px;border-radius:50%;background:radial-gradient(circle,rgba(255,60,20,1) 30%,rgba(255,100,0,0.6) 70%,rgba(255,50,0,0) 100%);box-shadow:0 0 20px rgba(255,50,0,0.9),0 0 40px rgba(255,80,0,0.5);flex-shrink:0;animation:goal-pulse 0.4s ease-in-out infinite alternate;"></div>';
    html += '<div style="flex:1;"><div style="font-size:10px;font-weight:bold;color:rgba(255,100,30,0.95);letter-spacing:0.15em;animation:goal-pulse 0.4s ease-in-out infinite alternate;">GOAL!</div><div style="font-size:8px;color:rgba(255,200,230,0.4);margin-top:1px;">TB LIGHTNING</div></div>';
  } else {
    html += '<div style="width:36px;height:36px;border-radius:50%;background:radial-gradient(circle,rgba(60,10,5,1) 40%,rgba(40,5,0,0.8) 80%);border:2px solid rgba(120,20,10,0.4);flex-shrink:0;"></div>';
    html += '<div style="flex:1;"><div style="font-size:9px;color:rgba(255,200,230,0.2);letter-spacing:0.12em;">GOAL LIGHT</div><div style="font-size:8px;color:rgba(255,200,230,0.15);margin-top:1px;">STANDING BY</div></div>';
  }
  html += '</div>';

  // Last goal
  html += '<div style="padding:7px 10px;flex:1;display:flex;flex-direction:column;overflow:hidden;">';
  html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:5px;">LAST GOAL</div>';
  if (lg.scorer_name) {
    html += '<div style="display:flex;align-items:center;gap:8px;margin-bottom:5px;">';
    html += headshotImg(lg.scorer_headshot, 42, '2px solid rgba(255,200,0,0.65)');
    html += '<div style="flex:1;min-width:0;">';
    html += '<div style="font-size:13px;font-weight:bold;color:rgba(255,200,230,0.95);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + lg.scorer_name + '</div>';
    html += '<div style="display:flex;align-items:center;gap:5px;margin-top:2px;flex-wrap:wrap;">';
    if (lg.strength)  html += '<span style="font-size:7px;color:rgba(255,80,180,0.7);border:1px solid rgba(255,80,180,0.2);padding:1px 4px;border-radius:2px;">' + lg.strength + '</span>';
    if (lg.shot_type) html += '<span style="font-size:7px;color:rgba(255,200,230,0.35);">' + lg.shot_type + '</span>';
    if (lg.period)    html += '<span style="font-size:7px;color:rgba(255,200,230,0.25);">P' + lg.period + ' ' + (lg.clock||'') + '</span>';
    html += '</div></div></div>';
    if (lg.assists && lg.assists.length > 0) {
      html += '<div style="display:flex;align-items:center;gap:5px;">';
      html += '<span style="font-size:7px;color:rgba(255,80,180,0.35);letter-spacing:0.1em;flex-shrink:0;">AST</span>';
      lg.assists.slice(0,2).forEach(function(a) {
        html += headshotImg(a.headshot, 20, '1px solid rgba(0,200,255,0.3)');
        html += '<span style="font-size:8px;color:rgba(255,200,230,0.55);white-space:nowrap;">' + a.name + '</span>';
      });
      html += '</div>';
    }
    if (sit.lastPlay) {
      html += '<div style="margin-top:6px;padding:3px 6px;background:rgba(255,60,180,0.04);border-left:2px solid rgba(255,60,180,0.2);">';
      html += '<div style="font-size:8px;color:rgba(255,200,230,0.4);line-height:1.4;">' + sit.lastPlay.substring(0,70) + (sit.lastPlay.length>70?'...':'') + '</div>';
      html += '</div>';
    }
  } else {
    html += '<div style="font-size:9px;color:rgba(255,200,230,0.2);">No goals yet</div>';
  }
  html += '</div>'; // end last goal
  html += '</div>'; // end col 2

  // ── COL 3: TEAM STATS ──
  html += '<div style="width:150px;flex-shrink:0;padding:7px 9px;display:flex;flex-direction:column;gap:4px;">';
  html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:3px;">TEAM STATS</div>';

  function statRow(label, val, sub, col) {
    col = col || 'rgba(255,200,230,0.85)';
    return '<div style="display:flex;align-items:center;justify-content:space-between;padding:4px 0;border-bottom:1px solid rgba(255,60,180,0.07);">' +
      '<span style="font-size:8px;color:rgba(255,80,180,0.5);letter-spacing:0.06em;">' + label + '</span>' +
      '<div style="text-align:right;">' +
        '<span style="font-size:12px;font-weight:bold;color:' + col + ';">' + val + '</span>' +
        (sub ? '<span style="font-size:8px;color:rgba(255,200,230,0.25);margin-left:4px;">' + sub + '</span>' : '') +
      '</div>' +
    '</div>';
  }

  // HITS
  var hitsVal = (sit.our_hits && sit.our_hits !== '--') ? sit.our_hits : null;
  var hitsOpp = (sit.opp_hits && sit.opp_hits !== '--') ? sit.opp_hits : null;
  var hitsCol = (hitsVal && hitsOpp) ? (parseInt(hitsVal) >= parseInt(hitsOpp) ? 'rgba(50,220,120,0.9)' : 'rgba(255,200,230,0.8)') : 'rgba(255,200,230,0.4)';
  html += statRow('HITS', hitsVal || '--', hitsOpp ? 'vs ' + hitsOpp : null, hitsCol);

  // POWER PLAY
  var ppVal = (sit.our_pp && sit.our_pp !== '--') ? sit.our_pp : '--';
  var ppParts = ppVal.split('/');
  var ppG = parseInt(ppParts[0]) || 0;
  var ppCol = ppG > 0 ? 'rgba(50,220,120,0.9)' : ppVal === '--' ? 'rgba(255,200,230,0.3)' : 'rgba(255,200,230,0.8)';
  html += statRow('POWER PLAY', ppVal, null, ppCol);

  // PENALTY KILL
  var pkVal = '--';
  var pkCol = 'rgba(255,200,230,0.4)';
  if (sit.opp_pp && sit.opp_pp !== '--') {
    var oppPPparts = sit.opp_pp.split('/');
    var oppPPG = parseInt(oppPPparts[0]) || 0;
    var oppPPO = parseInt(oppPPparts[1]) || 0;
    if (oppPPO > 0) {
      pkVal = (oppPPO - oppPPG) + '/' + oppPPO;
      pkCol = oppPPG === 0 ? 'rgba(50,220,120,0.9)' : 'rgba(255,160,40,0.9)';
    }
  }
  html += statRow('PEN KILL', pkVal, null, pkCol);

  // FACEOFF
  var foRaw = sit.our_faceoff;
  var fo = 0, foDisplay = '--', foCol = 'rgba(255,200,230,0.3)';
  if (foRaw && foRaw !== '--' && foRaw !== '0') {
    fo = parseFloat(foRaw);
    if (!isNaN(fo) && fo > 0) {
      foDisplay = fo.toFixed(1) + '%';
      foCol = fo >= 50 ? 'rgba(50,220,120,0.9)' : fo >= 40 ? 'rgba(255,160,40,0.9)' : 'rgba(255,50,50,0.9)';
    }
  }
  html += statRow('FACEOFF', foDisplay, null, foCol);
  if (fo > 0) {
    html += '<div style="margin-top:4px;"><div style="height:4px;background:rgba(255,60,180,0.1);border-radius:2px;overflow:hidden;"><div style="height:100%;width:' + fo + '%;background:' + foCol + ';border-radius:2px;transition:width 0.8s ease;"></div></div><div style="display:flex;justify-content:space-between;margin-top:2px;"><span style="font-size:7px;color:rgba(0,200,255,0.45);">TB ' + fo.toFixed(1) + '%</span><span style="font-size:7px;color:rgba(255,80,180,0.3);">OPP ' + (100-fo).toFixed(1) + '%</span></div></div>';
  }

  html += '</div>'; // end col 3
  html += '</div>'; // end main content
  html += '</div>'; // end widget

  return html;
}


// ─── RENDER SPORTS WIDGETS ───────────────────────────────────────────────────
function renderSports(data) {
  if (!data || !data.teams) return;
  var container = document.getElementById('team-widgets-container'); if (!container) return;
  var tickerH = 90, padding = 8, gap = 6;
  var totalH = window.innerHeight - tickerH - padding * 2;
  var boxH = Math.floor((totalH - gap * 4) / 5);
  var cypherFrameLeft = document.getElementById('cypher-frame') ? document.getElementById('cypher-frame').getBoundingClientRect().left : 450;
  var boxW = Math.floor(cypherFrameLeft - padding * 2);
  var positions = [
    { left:padding, top:padding+(boxH+gap)*0, width:boxW, height:boxH },
    { left:padding, top:padding+(boxH+gap)*1, width:boxW, height:boxH },
    { left:padding, top:padding+(boxH+gap)*2, width:boxW, height:boxH },
    { left:padding, top:padding+(boxH+gap)*3, width:boxW, height:boxH },
    { left:padding, top:padding+(boxH+gap)*4, width:boxW, height:boxH },
  ];
  var html = '';
  data.teams.forEach(function(t, i) {
    var pos = positions[i] || positions[4];
    var name = t.name.replace('Tampa Bay ', 'TB ');
    var isLive = t.state === 'in', isPost = t.state === 'post';

    // ── NHL LIVE — rich widget ──────────────────────────────────────────
    if (isLive && t.sport === 'nhl' && t.situation && t.situation.sport === 'nhl') {
      html += renderNHLLive(t, pos);
      return;
    }

    // ── MLB LIVE ────────────────────────────────────────────────────────
    if (isLive && t.sport === 'mlb' && t.situation && t.situation.batter) {
      var sit = t.situation;
      html += '<div class="team-widget live" style="left:' + pos.left + 'px;top:' + pos.top + 'px;width:' + pos.width + 'px;height:' + pos.height + 'px;display:flex;flex-direction:column;">';
      html += '<div style="padding:4px 10px;border-bottom:1px solid rgba(255,60,180,0.15);display:flex;align-items:center;justify-content:space-between;"><div style="font-size:8px;letter-spacing:0.15em;color:rgba(0,200,255,0.6);">' + name + '</div><span class="live-dot" style="margin:0;"></span></div>';
      html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:8px 14px;border-bottom:1px solid rgba(255,60,180,0.1);flex-shrink:0;">';
      html += '<div style="display:flex;align-items:center;gap:8px;">' + logoImg(t.our_logo, 28) + '<div style="font-size:22px;font-weight:bold;color:rgba(255,200,230,0.95);">' + t.our_score + '</div></div>';
      html += '<div style="font-size:10px;color:rgba(255,80,180,0.6);text-align:center;"><div>' + t.status_detail + '</div></div>';
      html += '<div style="display:flex;align-items:center;gap:8px;"><div style="font-size:22px;font-weight:bold;color:rgba(255,200,230,0.6);">' + t.opp_score + '</div>' + logoImg(t.opponent_logo, 28) + '</div>';
      html += '</div>';
      html += '<div style="display:flex;flex:1;min-height:0;">';
      html += '<div style="width:210px;flex-shrink:0;padding:12px 14px;border-right:1px solid rgba(255,60,180,0.1);display:flex;flex-direction:column;justify-content:space-evenly;gap:10px;">';
      var pitcher = sit.pitcher || {}, batter = sit.batter || {};
      if (pitcher.name) {
        html += '<div style="display:flex;align-items:center;gap:8px;">' + headshotImg(pitcher.headshot, 40, '1.5px solid rgba(255,60,180,0.4)') + '<div><div style="font-size:8px;color:rgba(255,80,180,0.5);letter-spacing:0.1em;">PITCHER</div><div style="font-size:12px;font-weight:bold;color:rgba(255,200,230,0.9);">' + pitcher.name + '</div><div style="font-size:9px;color:rgba(0,200,255,0.6);">' + (pitcher.summary || '') + '</div></div></div>';
      }
      if (batter.name) {
        html += '<div style="display:flex;align-items:center;gap:8px;">' + headshotImg(batter.headshot, 40, '1.5px solid rgba(0,200,255,0.4)') + '<div><div style="font-size:8px;color:rgba(0,200,255,0.5);letter-spacing:0.1em;">AT BAT</div><div style="font-size:12px;font-weight:bold;color:rgba(255,200,230,0.9);">' + batter.name + '</div><div style="font-size:9px;color:rgba(0,200,255,0.6);">' + (batter.summary || '') + '</div></div></div>';
      }
      html += '</div>';
      html += '<div style="display:flex;flex-direction:column;flex:1;padding:10px 14px;">';
      html += '<div style="display:flex;gap:10px;margin-bottom:10px;">';
      html += statPill('B', sit.balls || 0, 'rgba(50,255,100,0.9)');
      html += statPill('S', sit.strikes || 0, 'rgba(255,160,40,0.9)');
      html += statPill('O', sit.outs || 0, 'rgba(255,50,50,0.9)');
      html += '</div>';
      // Bases
      var onFirst = sit.onFirst, onSecond = sit.onSecond, onThird = sit.onThird;
      html += '<div style="position:relative;width:70px;height:70px;margin:4px auto;">';
      html += '<div style="position:absolute;top:50%;left:50%;transform:translate(-50%,-50%) rotate(45deg);width:50px;height:50px;border:1px solid rgba(255,60,180,0.2);">';
      html += '<div style="position:absolute;top:0;left:50%;transform:translate(-50%,-50%);width:16px;height:16px;background:' + (onSecond ? 'rgba(255,200,0,0.9)' : 'rgba(255,60,180,0.15)') + ';border:1px solid rgba(255,60,180,0.4);"></div>';
      html += '<div style="position:absolute;top:50%;left:0;transform:translate(-50%,-50%);width:16px;height:16px;background:' + (onThird ? 'rgba(255,200,0,0.9)' : 'rgba(255,60,180,0.15)') + ';border:1px solid rgba(255,60,180,0.4);"></div>';
      html += '<div style="position:absolute;top:50%;right:0;transform:translate(50%,-50%);width:16px;height:16px;background:' + (onFirst ? 'rgba(255,200,0,0.9)' : 'rgba(255,60,180,0.15)') + ';border:1px solid rgba(255,60,180,0.4);"></div>';
      html += '</div></div>';
      if (sit.lastPlay) html += '<div style="font-size:9px;color:rgba(255,200,230,0.5);line-height:1.4;margin-top:6px;">' + sit.lastPlay.substring(0, 60) + '...</div>';
      html += '</div></div></div>';
      return;
    }

    // ── NBA LIVE ────────────────────────────────────────────────────────
    if (isLive && t.sport === 'nba' && t.situation && t.situation.sport === 'nba') {
      var sit = t.situation, leaders = sit.leaders || [];
      var ourAhead = parseInt(t.our_score) >= parseInt(t.opp_score);
      var ourScoreCol = ourAhead ? 'rgba(50,255,100,0.95)' : 'rgba(255,200,230,0.95)';
      var oppScoreCol = !ourAhead ? 'rgba(255,50,50,0.9)' : 'rgba(255,200,230,0.45)';

      html += '<div class="team-widget live" style="left:' + pos.left + 'px;top:' + pos.top + 'px;width:' + pos.width + 'px;height:' + pos.height + 'px;display:flex;flex-direction:column;overflow:hidden;">';

      // Header
      html += '<div style="padding:4px 10px;border-bottom:1px solid rgba(255,60,180,0.15);display:flex;align-items:center;justify-content:space-between;flex-shrink:0;">';
      html += '<div style="font-size:8px;letter-spacing:0.15em;color:rgba(0,200,255,0.7);">' + name + '</div>';
      html += '<div style="display:flex;align-items:center;gap:8px;">';
      if (sit.series) html += '<span style="font-size:8px;color:rgba(255,200,230,0.3);">' + sit.series + '</span>';
      html += '<span class="live-dot"></span></div></div>';

      // Scoreboard
      html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:6px 14px;border-bottom:1px solid rgba(255,60,180,0.12);flex-shrink:0;">';
      html += '<div style="display:flex;align-items:center;gap:8px;">' + logoImg(t.our_logo, 30) + '<div style="font-size:32px;font-weight:bold;color:' + ourScoreCol + ';line-height:1;">' + t.our_score + '</div></div>';
      html += '<div style="text-align:center;"><div style="font-size:11px;font-weight:bold;color:rgba(255,80,180,0.85);">Q' + (sit.period||'?') + ' &mdash; ' + (sit.clock||'--:--') + '</div></div>';
      html += '<div style="display:flex;align-items:center;gap:8px;"><div style="font-size:32px;font-weight:bold;color:' + oppScoreCol + ';line-height:1;">' + t.opp_score + '</div>' + logoImg(t.opponent_logo, 30) + '</div>';
      html += '</div>';

      // Main content — 2 columns
      html += '<div style="display:flex;flex:1;min-height:0;overflow:hidden;">';

      // ── COL 1: TOP 2 PERFORMERS ──
      // Get top 2 by points from our team
      var ourLeaders = leaders.filter(function(l) { return l.category === 'points' || l.category === 'scoring'; });
      // Sort by value desc, take top 2
      ourLeaders.sort(function(a,b){ return (b.value||0)-(a.value||0); });
      var top2 = ourLeaders.slice(0, 2);
      // Fallback: just take first 2 leaders if not enough points leaders
      if (top2.length < 2) {
        var seen = {};
        leaders.forEach(function(l) {
          if (!seen[l.name] && top2.length < 2) { seen[l.name]=true; top2.push(l); }
        });
      }
      var pColors = ['rgba(255,200,0,0.85)', 'rgba(0,200,255,0.85)'];

      html += '<div style="flex:1;padding:8px 10px;border-right:1px solid rgba(255,60,180,0.1);display:flex;flex-direction:column;gap:6px;">';
      html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:2px;">TOP PERFORMERS</div>';
      top2.forEach(function(l, idx) {
        if (!l) return;
        var col = pColors[idx] || 'rgba(255,80,180,0.7)';
        html += '<div style="display:flex;align-items:center;gap:8px;padding:6px 0;border-bottom:1px solid rgba(255,60,180,0.08);">';
        if (l.headshot) {
          html += '<div style="position:relative;flex-shrink:0;">';
          html += '<img src="/headshot?url=' + encodeURIComponent(l.headshot) + '" width="46" height="46" style="border-radius:50%;object-fit:cover;border:2px solid ' + col + ';">';
          html += '<div style="position:absolute;bottom:-2px;left:50%;transform:translateX(-50%);font-size:6px;background:' + col + ';color:#000;padding:1px 4px;border-radius:2px;font-weight:bold;white-space:nowrap;">' + (l.label||'PTS') + '</div>';
          html += '</div>';
        }
        html += '<div style="flex:1;min-width:0;">';
        html += '<div style="font-size:11px;font-weight:bold;color:rgba(255,200,230,0.95);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + l.name + '</div>';
        html += '<div style="font-size:22px;font-weight:bold;color:' + col + ';line-height:1.1;">' + l.display_value + '</div>';
        if (l.summary) html += '<div style="font-size:8px;color:rgba(0,200,255,0.55);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">' + l.summary + '</div>';
        html += '</div></div>';
      });
      html += '</div>';

      // ── COL 2: QUARTER SCORES + TEAM STATS ──
      html += '<div style="width:200px;flex-shrink:0;padding:8px 10px;display:flex;flex-direction:column;gap:6px;">';

      // Quarter scores
      var scoring = sit.scoring_by_period || {};
      var quarters = Object.keys(scoring).sort();
      if (quarters.length > 0) {
        html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:3px;">BY QUARTER</div>';
        html += '<div style="display:flex;gap:3px;margin-bottom:6px;">';
        quarters.forEach(function(q) {
          var qd = scoring[q] || {};
          var ourQ = qd['our'] !== undefined ? qd['our'] : '--';
          var oppQ = qd['opp'] !== undefined ? qd['opp'] : '--';
          var ourWon = ourQ !== '--' && oppQ !== '--' && ourQ >= oppQ;
          html += '<div style="flex:1;text-align:center;padding:3px 2px;border:1px solid rgba(255,60,180,0.12);border-radius:2px;background:rgba(255,60,180,0.03);">';
          html += '<div style="font-size:6px;color:rgba(255,80,180,0.35);letter-spacing:0.1em;">Q' + q + '</div>';
          html += '<div style="font-size:10px;font-weight:bold;color:' + (ourWon?'rgba(50,255,100,0.8)':'rgba(255,50,50,0.7)') + ';">' + ourQ + '</div>';
          html += '<div style="font-size:8px;color:rgba(255,200,230,0.3);">' + oppQ + '</div>';
          html += '</div>';
        });
        html += '</div>';
      }

      // Team stats
      html += '<div style="font-size:7px;color:rgba(255,80,180,0.5);letter-spacing:0.15em;margin-bottom:3px;">TEAM STATS</div>';
      function nbaStatRow(label, val, col) {
        return '<div style="display:flex;justify-content:space-between;align-items:center;padding:3px 0;border-bottom:1px solid rgba(255,60,180,0.06);">' +
          '<span style="font-size:8px;color:rgba(255,80,180,0.45);">' + label + '</span>' +
          '<span style="font-size:11px;font-weight:bold;color:' + (col||'rgba(255,200,230,0.85)') + ';">' + val + '</span>' +
        '</div>';
      }
      // Pull best category leaders for team stats display
      var ptsCat  = leaders.filter(function(l){return l.category==='points';});
      var astCat  = leaders.filter(function(l){return l.category==='assists';});
      var rebCat  = leaders.filter(function(l){return l.category==='rebounds';});
      var ourPts  = ptsCat.find(function(l){return l.team_id===t.our_team_id;});
      var ourAst  = astCat.find(function(l){return l.team_id===t.our_team_id;});
      var ourReb  = rebCat.find(function(l){return l.team_id===t.our_team_id;});
      html += nbaStatRow('PTS LEADER', ourPts ? ourPts.name.split(' ').slice(-1)[0]+' '+ourPts.display_value : '--');
      html += nbaStatRow('AST LEADER', ourAst ? ourAst.name.split(' ').slice(-1)[0]+' '+ourAst.display_value : '--', 'rgba(0,200,255,0.8)');
      html += nbaStatRow('REB LEADER', ourReb ? ourReb.name.split(' ').slice(-1)[0]+' '+ourReb.display_value : '--', 'rgba(50,255,100,0.8)');

      html += '</div>'; // end col 2
      html += '</div>'; // end main content
      html += '</div>'; // end widget
      return;
    }

    // ── OFF SEASON ──────────────────────────────────────────────────────
    var liveCls = isLive ? ' live' : '';
    html += '<div class="team-widget' + liveCls + '" style="left:' + pos.left + 'px;top:' + pos.top + 'px;width:' + pos.width + 'px;height:' + pos.height + 'px;display:flex;flex-direction:column;">';
    html += '<div style="padding:4px 10px;border-bottom:1px solid rgba(255,60,180,0.15);display:flex;align-items:center;justify-content:space-between;"><div style="font-size:8px;letter-spacing:0.15em;color:rgba(0,200,255,0.6);">' + name + '</div>' + (isLive ? '<span class="live-dot" style="margin:0;"></span>' : '') + '</div>';

    if (!t.active) {
      html += '<div style="display:flex;flex-direction:column;flex:1;padding:12px 14px;overflow:hidden;">';
      html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-shrink:0;">' + logoImg(t.our_logo, 42) + '<div><div style="font-size:15px;font-weight:bold;color:rgba(255,200,230,0.9);">' + name + '</div><div style="font-size:9px;color:rgba(255,80,180,0.5);letter-spacing:0.12em;margin-top:2px;">OFF SEASON</div></div></div>';
      if (t.news && t.news.length > 0) { t.news.slice(0, 4).forEach(function(h) { if (!h) return; html += '<div style="padding:7px 0;border-top:1px solid rgba(255,60,180,0.1);font-size:11px;color:rgba(255,200,230,0.75);line-height:1.4;"><span style="color:rgba(255,80,180,0.5);margin-right:6px;">▸</span>' + h + '</div>'; }); }
      else { html += '<div style="font-size:10px;color:rgba(255,200,230,0.2);margin-top:6px;">No recent news</div>'; }
      html += '</div>';
    } else if (!t.game_today) {
      html += '<div style="display:flex;flex-direction:column;flex:1;padding:12px 14px;overflow:hidden;">';
      html += '<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;flex-shrink:0;">' + logoImg(t.our_logo, 42) + '<div><div style="font-size:15px;font-weight:bold;color:rgba(255,200,230,0.9);">' + name + '</div><div style="font-size:12px;color:rgba(0,200,255,0.7);margin-top:2px;">' + t.record + '</div></div><div style="flex:1;text-align:right;font-size:9px;color:rgba(255,200,230,0.2);letter-spacing:0.1em;">NO GAME TODAY</div></div>';
      if (t.news && t.news.length > 0) { t.news.slice(0, 2).forEach(function(h) { if (!h) return; html += '<div style="padding:6px 0;border-top:1px solid rgba(255,60,180,0.1);font-size:11px;color:rgba(255,200,230,0.7);line-height:1.4;"><span style="color:rgba(255,80,180,0.5);margin-right:6px;">▸</span>' + h + '</div>'; }); }
      html += '</div>';
    } else {
      var oppName = t.opponent.replace('Tampa Bay ', 'TB ').split(' ').slice(-1)[0];
      var scoreOrTime = '';
      if (isLive) { var won = parseInt(t.our_score) >= parseInt(t.opp_score); var sCol = won ? 'rgba(50,255,100,0.9)' : 'rgba(255,50,50,0.9)'; scoreOrTime = '<div style="text-align:center;"><div style="font-size:20px;font-weight:bold;color:' + sCol + ';">' + t.our_score + ' — ' + t.opp_score + '</div><div style="font-size:8px;color:rgba(255,80,180,0.6);">' + t.status_detail + '</div></div>'; }
      else if (isPost) { var won = parseInt(t.our_score) > parseInt(t.opp_score); var sCol = won ? 'rgba(50,255,100,0.9)' : 'rgba(255,50,50,0.8)'; scoreOrTime = '<div style="text-align:center;"><div style="font-size:18px;font-weight:bold;color:' + sCol + ';">' + t.our_score + '—' + t.opp_score + '</div><div style="font-size:9px;font-weight:bold;color:' + sCol + ';">FINAL</div></div>'; }
      else { scoreOrTime = '<div style="text-align:center;"><div style="font-size:20px;font-weight:bold;color:rgba(255,200,230,0.95);">' + t.game_time + '</div><div style="font-size:10px;color:rgba(255,80,180,0.5);letter-spacing:0.1em;">VS</div></div>'; }
      html += '<div style="display:flex;align-items:center;justify-content:space-between;padding:10px 12px;gap:6px;flex:1;">';
      html += '<div style="text-align:center;min-width:70px;">' + logoImg(t.our_logo, 52) + '<div style="font-size:13px;font-weight:bold;color:rgba(255,200,230,0.9);margin-top:6px;">' + name.split(' ').slice(-1)[0] + '</div><div style="font-size:11px;color:rgba(0,200,255,0.7);">' + t.record + '</div></div>';
      html += scoreOrTime;
      html += '<div style="text-align:center;min-width:70px;">' + logoImg(t.opponent_logo || t.our_logo, 52) + '<div style="font-size:13px;font-weight:bold;color:rgba(255,200,230,0.7);margin-top:6px;">' + oppName + '</div><div style="font-size:11px;color:rgba(0,200,255,0.55);">' + (t.opp_record || '—') + '</div></div>';
      html += '</div>';
    }

    var hasOwnStatsBar = (isLive && t.sport === 'mlb' && t.situation && t.situation.batter) || (isLive && t.sport === 'nhl' && t.situation && t.situation.sport === 'nhl') || (isLive && t.sport === 'nba' && t.situation && t.situation.sport === 'nba');
    if (!hasOwnStatsBar && t.player_stats && t.player_stats.length > 0) {
      html += '<div style="display:flex;gap:0;border-top:1px solid rgba(255,60,180,0.12);flex-shrink:0;">';
      t.player_stats.slice(1, 4).forEach(function(s) { html += '<div style="flex:1;text-align:center;padding:8px 2px;border-right:1px solid rgba(255,60,180,0.08);"><div style="font-size:10px;color:rgba(255,80,180,0.7);letter-spacing:0.05em;">' + s.label + '</div><div style="font-size:14px;font-weight:bold;color:rgba(255,200,230,0.95);">' + s.value + '</div></div>'; });
      html += '</div>';
    }
    html += '</div>';
  });

  container.innerHTML = html;
  var standingsEl = document.getElementById('sports-standings-widget');
  var streakEl    = document.getElementById('sports-streak-widget');
  if (standingsEl && streakEl) { streakEl.style.top = (standingsEl.offsetHeight + 20) + 'px'; }
}
