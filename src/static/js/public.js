/**
 * Public Spectator Portal Logic
 * Mobile-first, responsive viewer for live standings, scores, leaders,
 * Fan MVP voting (F4.2), Journalism match reports (F4.3), Fair-play (F3.3),
 * Head-to-Head (F3.2), and Predictions leaderboard (F4.1).
 */

let currentTournamentId = null;
let currentTournamentData = null;
let activeVoteMatchId = null;

// Unique device fingerprint for Fan MVP voting without cookies
function getVoterFingerprint() {
  let fp = localStorage.getItem("fan_voter_uuid");
  if (!fp) {
    fp = "voter_" + Math.random().toString(36).substring(2, 12) + Date.now().toString(36);
    localStorage.setItem("fan_voter_uuid", fp);
  }
  return fp;
}

document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupShareButton();
  await loadPublicTournaments();
});

function setupTabs() {
  document.querySelectorAll(".p-tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".p-tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".p-pane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const target = document.getElementById(tabId);
      if (target) target.classList.add("active");

      if (tabId === "tab-p-predictions") loadPublicPredictions();
      if (tabId === "tab-p-h2h") preparePublicH2HSelectors();
      if (tabId === "tab-p-history") loadPublicHistory();
    });
  });
}

function setupShareButton() {
  document.getElementById("btnShareLink").addEventListener("click", async () => {
    const url = window.location.href;
    const title = currentTournamentData ? currentTournamentData.tournament.name : "Tournoi Sportif Saint Jérôme";
    const shareText = `Suivez les résultats et le classement en direct du ${title} !\n\n${url}`;

    if (navigator.share) {
      try {
        await navigator.share({
          title: title,
          text: `Suivez les résultats et le classement en direct du ${title} !`,
          url: url
        });
      } catch (err) {
        copyToClipboard(shareText);
      }
    } else {
      copyToClipboard(shareText);
    }
  });

  document.getElementById("pSelectTournament").addEventListener("change", (e) => {
    currentTournamentId = parseInt(e.target.value);
    const newUrl = new URL(window.location.href);
    newUrl.searchParams.set("t", currentTournamentId);
    window.history.pushState({}, "", newUrl);
    loadTournamentDetails();
  });
}

function copyToClipboard(text) {
  navigator.clipboard.writeText(text).then(() => {
    alert("Lien du tournoi copié avec succès ! Vous pouvez le coller directement sur WhatsApp ou Telegram.");
  }).catch(() => {
    alert("Lien : " + window.location.href);
  });
}

async function loadPublicTournaments() {
  try {
    const res = await fetch("/api/tournaments");
    const tournaments = await res.json();
    const select = document.getElementById("pSelectTournament");
    select.innerHTML = "";

    if (tournaments.length === 0) {
      select.innerHTML = `<option value="">Aucun tournoi</option>`;
      return;
    }

    tournaments.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `${t.name} (${t.sport.toUpperCase()})`;
      select.appendChild(opt);
    });

    // Check URL param ?t=
    const params = new URLSearchParams(window.location.search);
    const paramT = params.get("t");
    if (paramT && tournaments.some(t => t.id === parseInt(paramT))) {
      currentTournamentId = parseInt(paramT);
      select.value = currentTournamentId;
    } else {
      currentTournamentId = parseInt(select.value);
    }

    await loadTournamentDetails();
  } catch (err) {
    console.error(err);
  }
}

async function loadTournamentDetails() {
  if (!currentTournamentId) return;

  try {
    const res = await fetch(`/api/tournament/${currentTournamentId}/full`);
    currentTournamentData = await res.json();

    const t = currentTournamentData.tournament;
    document.getElementById("pTournamentTitle").textContent = t.name;
    document.getElementById("pSportBadge").textContent = (t.sport || "SPORT").toUpperCase();

    renderPublicStandings();
    renderPublicMatches();
    renderPublicStats();
    renderPublicFairPlay();
    renderPublicAwards();
    renderPublicTeams();
    loadPublicHighlights();
  } catch (err) {
    console.error("Erreur chargement détails public :", err);
  }
}

// ---------------- TAB 1: STANDINGS ----------------
function renderPublicStandings() {
  const standings = currentTournamentData.standings || [];
  const sport = currentTournamentData.tournament.sport;
  const thead = document.getElementById("pTableHeadStandings");
  const tbody = document.getElementById("pTableBodyStandings");

  const isBasket = sport === "basketball";

  thead.innerHTML = `
    <tr>
      <th style="width: 40px;">#</th>
      <th class="th-left">Équipe</th>
      <th>Pts</th>
      <th>J</th>
      <th>V</th>
      ${!isBasket ? '<th>N</th>' : ''}
      <th>D</th>
      <th>${isBasket ? 'Marq.' : 'BP'}</th>
      <th>${isBasket ? 'Enc.' : 'BC'}</th>
      <th>Diff</th>
    </tr>
  `;

  tbody.innerHTML = "";

  if (standings.length === 0) {
    tbody.innerHTML = `<tr><td colspan="10" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Aucun match terminé pour le moment.</td></tr>`;
    return;
  }

  standings.forEach(s => {
    const tr = document.createElement("tr");

    // Badges HTML
    const teamData = (currentTournamentData.teams || []).find(tm => tm.id === s.team_id);
    let badgesHtml = "";
    if (teamData && teamData.badges) {
      badgesHtml = teamData.badges.map(b => `<span class="badge-chip" style="background: ${b.color};" title="${b.description}">${b.label}</span>`).join(" ");
    }

    tr.innerHTML = `
      <td style="font-weight: 800; color: ${s.rank === 1 ? 'var(--accent)' : 'inherit'};">#${s.rank}</td>
      <td class="th-left">
        <div style="display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap;">
          <div style="width: 12px; height: 12px; border-radius: 3px; background: ${s.color};"></div>
          <strong>${s.name}</strong>
          <small style="color: var(--text-muted);">(${s.short_name})</small>
          ${badgesHtml}
        </div>
      </td>
      <td style="font-weight: 900; color: var(--accent); font-size: 1rem;">${s.points}</td>
      <td>${s.played}</td>
      <td style="color: #22c55e; font-weight: 700;">${s.won}</td>
      ${!isBasket ? `<td style="color: var(--text-muted);">${s.drawn}</td>` : ''}
      <td style="color: #ef4444;">${s.lost}</td>
      <td>${s.scored}</td>
      <td>${s.conceded}</td>
      <td style="font-weight: 700; color: ${s.diff > 0 ? '#22c55e' : (s.diff < 0 ? '#ef4444' : 'inherit')};">
        ${s.diff > 0 ? '+' : ''}${s.diff}
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------------- TAB 2: MATCHS, FAN MVP VOTE & JOURNALISM REPORTS ----------------
async function renderPublicMatches() {
  const matches = currentTournamentData.matches || [];
  const container = document.getElementById("pMatchesList");
  container.innerHTML = "";

  if (matches.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">Aucun match programmé pour le moment.</div>`;
    return;
  }

  // Load approved reports for this tournament
  let reports = [];
  try {
    const res = await fetch("/api/match-reports?status=approved");
    reports = await res.json();
  } catch (e) {
    console.warn(e);
  }

  matches.forEach(m => {
    const card = document.createElement("div");
    card.className = "p-match-card";
    const isFinished = m.status === "finished";

    const matchReport = reports.find(r => r.match_id === m.id);

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem; font-size: 0.8rem; color: var(--text-muted);">
        <span><strong>${m.round_name}</strong> • ${m.match_date || 'Date à fixer'}</span>
        <span style="background: ${isFinished ? 'rgba(34, 197, 94, 0.2)' : 'rgba(245, 158, 11, 0.2)'}; color: ${isFinished ? '#22c55e' : 'var(--accent)'}; padding: 0.2rem 0.5rem; border-radius: 4px; font-weight: 800; font-size: 0.75rem;">
          ${isFinished ? 'TERMINÉ' : (m.match_time || 'À VENIR')}
        </span>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin: 0.75rem 0;">
        <div style="flex: 1; text-align: left;">
          <div style="font-weight: 800; font-size: 0.95rem;">${m.team_home_name}</div>
          <small style="color: var(--text-muted);">${m.team_home_filiere || m.team_home_short}</small>
        </div>

        <div style="padding: 0 1rem; text-align: center;">
          <div style="font-size: 1.4rem; font-weight: 900; color: #fff; letter-spacing: 2px;">
            ${m.score_home !== null ? m.score_home : '-'} : ${m.score_away !== null ? m.score_away : '-'}
          </div>
          <small style="color: var(--text-muted); font-size: 0.75rem;">${m.venue || 'Terrain'}</small>
        </div>

        <div style="flex: 1; text-align: right;">
          <div style="font-weight: 800; font-size: 0.95rem;">${m.team_away_name}</div>
          <small style="color: var(--text-muted);">${m.team_away_filiere || m.team_away_short}</small>
        </div>
      </div>

      ${m.mvp_name ? `
        <div style="background: rgba(245, 158, 11, 0.1); border: 1px dashed var(--accent); padding: 0.4rem 0.75rem; border-radius: 6px; font-size: 0.8rem; margin: 0.5rem 0;">
          ⭐ <strong>Homme du match officiel :</strong> ${m.mvp_name}
        </div>
      ` : ''}

      <!-- Fan Actions Bar -->
      <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; border-top: 1px solid var(--border-dark); padding-top: 0.5rem; font-size: 0.8rem;">
        <div style="display: flex; gap: 0.4rem; flex-wrap: wrap;">
          <button class="nav-action-btn" onclick="openPublicMatchStatsModal(${m.id}, '${(m.team_home_name || '').replace(/'/g, "\\'")}', '${(m.team_away_name || '').replace(/'/g, "\\'")}', ${m.team_home_id}, ${m.team_away_id})" style="font-size: 0.75rem;">
            📊 Stats & Notes Joueurs
          </button>
          <button class="nav-action-btn" onclick="openFanVoteModal(${m.id}, '${(m.team_home_name || '').replace(/'/g, "\\'")}', '${(m.team_away_name || '').replace(/'/g, "\\'")}')" style="font-size: 0.75rem;">
            ⭐ Voter MVP Public
          </button>
        </div>
        <a href="/match_sheet.html?id=${m.id}" target="_blank" style="color: var(--accent-blue); text-decoration: none; font-weight: 700;">
          📄 Feuille Officielle A4 ↗
        </a>
      </div>

      <!-- F4.3: Match Report from Journalism Club -->
      ${matchReport ? `
        <div style="background: rgba(255, 255, 255, 0.05); border-left: 3px solid var(--accent); padding: 0.75rem; border-radius: 6px; margin-top: 0.75rem; font-size: 0.85rem;">
          <div style="font-weight: 800; color: var(--accent); margin-bottom: 0.25rem;">📰 ${matchReport.title}</div>
          <div style="color: var(--text-muted); line-height: 1.4; margin-bottom: 0.4rem;">${matchReport.content}</div>
          <small style="color: var(--accent-blue);">Rédigé par ${matchReport.author_name} (${matchReport.author_school || 'Club Média'})</small>
        </div>
      ` : ''}
    `;
    container.appendChild(card);
  });
}

// ---------------- MODAL STATS ET NOTES MATCH (SPECTATEURS) ----------------
let currentStatsModalHomeTeamId = null;
let currentStatsModalAwayTeamId = null;

async function openPublicMatchStatsModal(matchId, homeName, awayName, homeId, awayId) {
  currentStatsModalHomeTeamId = homeId;
  currentStatsModalAwayTeamId = awayId;

  const modal = document.getElementById("modalPublicMatchStats");
  if (!modal) return;
  modal.style.display = "flex";

  document.getElementById("mStatsMatchTitle").textContent = `📊 Statistiques : ${homeName} vs ${awayName}`;
  document.getElementById("pStatsTabHomeTitle").textContent = `🏠 ${homeName}`;
  document.getElementById("pStatsTabAwayTitle").textContent = `✈️ ${awayName}`;

  switchPublicStatsTeam("home");

  const homeBox = document.getElementById("pStatsHomeContent");
  const awayBox = document.getElementById("pStatsAwayContent");
  homeBox.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Chargement des statistiques...</div>`;
  awayBox.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Chargement des statistiques...</div>`;

  try {
    const res = await fetch(`/api/matches/${matchId}/player-stats`);
    const data = await res.json();
    const stats = data.stats || [];

    renderPublicStatsTable("pStatsHomeContent", stats.filter(s => s.team_id === homeId), homeName);
    renderPublicStatsTable("pStatsAwayContent", stats.filter(s => s.team_id === awayId), awayName);
  } catch (err) {
    homeBox.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Aucune statistique individuelle saisie pour ce match.</div>`;
    awayBox.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Aucune statistique individuelle saisie pour ce match.</div>`;
  }
}

function closePublicMatchStatsModal() {
  const modal = document.getElementById("modalPublicMatchStats");
  if (modal) modal.style.display = "none";
}

function switchPublicStatsTeam(team) {
  const homeBox = document.getElementById("pStatsHomeContent");
  const awayBox = document.getElementById("pStatsAwayContent");
  const btnHome = document.getElementById("btnPStatsTabHome");
  const btnAway = document.getElementById("btnPStatsTabAway");

  if (team === "home") {
    if (homeBox) homeBox.style.display = "block";
    if (awayBox) awayBox.style.display = "none";
    if (btnHome) { btnHome.style.borderColor = "var(--accent)"; btnHome.style.opacity = "1"; }
    if (btnAway) { btnAway.style.borderColor = "transparent"; btnAway.style.opacity = "0.6"; }
  } else {
    if (homeBox) homeBox.style.display = "none";
    if (awayBox) awayBox.style.display = "block";
    if (btnAway) { btnAway.style.borderColor = "var(--accent)"; btnAway.style.opacity = "1"; }
    if (btnHome) { btnHome.style.borderColor = "transparent"; btnHome.style.opacity = "0.6"; }
  }
}

function renderPublicStatsTable(containerId, statsList, teamName) {
  const box = document.getElementById(containerId);
  if (!box) return;
  if (!statsList || statsList.length === 0) {
    box.innerHTML = `<div style="padding: 1.5rem; text-align: center; color: var(--text-muted); font-size: 0.85rem;">Aucune statistique détaillée disponible pour ${teamName}.</div>`;
    return;
  }

  let html = `
    <table class="p-table" style="width: 100%; font-size: 0.82rem; min-width: 580px;">
      <thead>
        <tr>
          <th class="th-left">Joueur</th>
          <th>PTS</th>
          <th>AST</th>
          <th>REB</th>
          <th>BLK</th>
          <th>FLS</th>
          <th>TEC</th>
          <th>Appréciation</th>
          <th>Note /10</th>
          <th>MVP</th>
        </tr>
      </thead>
      <tbody>
  `;

  statsList.forEach(s => {
    const r = Number(s.rating || 5.0).toFixed(1);
    let ratingBadgeClass = "background: rgba(59, 130, 246, 0.2); color: #60a5fa;";
    if (s.rating >= 8.0) ratingBadgeClass = "background: rgba(34, 197, 94, 0.25); color: #22c55e; font-weight: 900;";
    else if (s.rating >= 6.5) ratingBadgeClass = "background: rgba(245, 158, 11, 0.25); color: #f59e0b; font-weight: 800;";
    else if (s.rating < 5.0) ratingBadgeClass = "background: rgba(239, 68, 68, 0.25); color: #ef4444;";

    let apprText = "⚪ Neutre";
    if (s.coach_appreciation >= 2.0) apprText = "⭐⭐ Exceptionnel";
    else if (s.coach_appreciation >= 1.0) apprText = "⭐ Très bon";
    else if (s.coach_appreciation <= -2.0) apprText = "❌ Mauvais";
    else if (s.coach_appreciation <= -1.0) apprText = "⚠️ Décevant";

    html += `
      <tr>
        <td class="th-left" style="font-weight: 700;">
          <div style="display: flex; align-items: center; gap: 6px;">
            ${s.photo_url ? `<img src="${s.photo_url}" style="width: 24px; height: 24px; border-radius: 50%; object-fit: cover;">` : `<span style="display: inline-block; width: 22px; height: 22px; border-radius: 50%; background: #374151; text-align: center; line-height: 22px; font-size: 0.7rem;">#${s.number || '•'}</span>`}
            <div>
              <div>${s.player_name || 'Joueur'}</div>
              <small style="color: var(--text-muted); font-size: 0.7rem;">#${s.number || '-'} • ${s.position || 'Poste'}</small>
            </div>
          </div>
        </td>
        <td style="font-weight: 900; color: var(--accent); font-size: 0.95rem;">${s.points}</td>
        <td>${s.assists}</td>
        <td>${s.rebounds}</td>
        <td>${s.blocks}</td>
        <td>${s.fouls}</td>
        <td style="${s.technical_fouls > 0 ? 'color: #ef4444; font-weight: 800;' : ''}">${s.technical_fouls}</td>
        <td style="font-size: 0.75rem; color: var(--text-muted);">${apprText}</td>
        <td>
          <span style="display: inline-block; padding: 2px 8px; border-radius: 6px; font-size: 0.85rem; ${ratingBadgeClass}">
            ${r}
          </span>
        </td>
        <td>${s.is_mvp ? '⭐' : '-'}</td>
      </tr>
    `;
  });

  html += `</tbody></table>`;
  box.innerHTML = html;
}

// ---------------- F4.2: FAN MVP VOTE MODAL ----------------
async function openFanVoteModal(matchId, homeName, awayName) {
  activeVoteMatchId = matchId;
  const modal = document.getElementById("modalFanVote");
  modal.style.display = "flex";
  document.getElementById("modalVoteMatchTitle").textContent = `⭐ Vote MVP : ${homeName} vs ${awayName}`;

  const playersList = document.getElementById("modalVotePlayersList");
  const resultsBox = document.getElementById("modalVoteResults");
  playersList.innerHTML = `<div style="text-align: center; color: var(--text-muted);">Chargement des joueurs...</div>`;
  resultsBox.style.display = "none";

  try {
    // 1. Fetch match players
    const resM = await fetch(`/api/matches/${matchId}/sheet`);
    const sheetData = await resM.json();
    const allPlayers = [...(sheetData.home_players || []), ...(sheetData.away_players || [])];

    // 2. Fetch current votes
    const resV = await fetch(`/api/matches/${matchId}/mvp-votes`);
    const votesData = await resV.json();

    renderFanVoteDialog(allPlayers, votesData);
  } catch (err) {
    playersList.innerHTML = `<div style="color: #ef4444;">Erreur lors du chargement des votes.</div>`;
  }
}

function renderFanVoteDialog(players, votesData) {
  const playersList = document.getElementById("modalVotePlayersList");
  const resultsBox = document.getElementById("modalVoteResults");

  playersList.innerHTML = "";
  resultsBox.innerHTML = "";

  // Render Vote Buttons
  players.forEach(p => {
    const item = document.createElement("div");
    item.style.display = "flex";
    item.style.justifyContent = "space-between";
    item.style.alignItems = "center";
    item.style.padding = "0.4rem 0";
    item.style.borderBottom = "1px solid var(--border-dark)";

    item.innerHTML = `
      <div>
        <strong>${p.name}</strong> <small style="color: var(--text-muted);">(#${p.number} - ${p.position || 'Joueur'})</small>
      </div>
      <button class="nav-action-btn" onclick="submitFanMvpVote(${p.id})">Voter</button>
    `;
    playersList.appendChild(item);
  });

  // Render Results breakdown
  if (votesData && votesData.total_votes > 0) {
    resultsBox.style.display = "block";
    resultsBox.innerHTML = `
      <div style="font-weight: 800; font-size: 0.9rem; color: var(--accent); margin-bottom: 0.5rem;">
        Résultats en direct (${votesData.total_votes} votes) :
      </div>
      ${votesData.votes.map(v => `
        <div style="margin-bottom: 0.4rem; font-size: 0.8rem;">
          <div style="display: flex; justify-content: space-between;">
            <span>${v.player_name} (${v.team_name})</span>
            <strong>${v.percent}% (${v.votes_count} votes)</strong>
          </div>
          <div class="fan-vote-progress">
            <div class="fan-vote-fill" style="width: ${v.percent}%;"></div>
          </div>
        </div>
      `).join('')}
    `;
  }
}

async function submitFanMvpVote(playerId) {
  if (!activeVoteMatchId) return;
  const fingerprint = getVoterFingerprint();

  try {
    const res = await fetch(`/api/matches/${activeVoteMatchId}/vote-mvp`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ player_id: playerId, fingerprint })
    });
    const data = await res.json();
    if (res.ok && data.status === "ok") {
      alert(data.message);
      // Reload vote modal
      const resV = await fetch(`/api/matches/${activeVoteMatchId}/mvp-votes`);
      const votesData = await resV.json();
      const resM = await fetch(`/api/matches/${activeVoteMatchId}/sheet`);
      const sheetData = await resM.json();
      renderFanVoteDialog([...(sheetData.home_players || []), ...(sheetData.away_players || [])], votesData);
    } else {
      alert(data.error || "Vous avez déjà voté sur cette rencontre.");
    }
  } catch (err) {
    alert("Erreur lors de l'envoi de votre vote.");
  }
}

function closeFanVoteModal() {
  document.getElementById("modalFanVote").style.display = "none";
  activeVoteMatchId = null;
}

// ---------------- TAB 3: STATS & MVPS ----------------
async function renderPublicStats() {
  const leaders = currentTournamentData.leaders || {};
  let scorers = leaders.scorers || [];
  let mvps = leaders.mvps || [];

  // Check if we have rich individual stats summary from match scores
  if (currentTournamentId) {
    try {
      const res = await fetch(`/api/tournament/${currentTournamentId}/player-stats-summary`);
      if (res.ok) {
        const summary = await res.json();
        if (summary && summary.length > 0) {
          const pointsLeaders = summary
            .filter(s => s.total_points > 0)
            .sort((a, b) => b.total_points - a.total_points)
            .map((s, idx) => ({
              rank: idx + 1,
              player_name: s.player_name,
              player_number: s.player_number,
              team_name: s.team_name,
              total: s.total_points
            }));
          if (pointsLeaders.length > 0) scorers = pointsLeaders;

          const mvpLeaders = summary
            .filter(s => s.mvp_count > 0)
            .sort((a, b) => b.mvp_count - a.mvp_count)
            .map((s, idx) => ({
              rank: idx + 1,
              player_name: s.player_name,
              total: s.mvp_count
            }));
          if (mvpLeaders.length > 0) mvps = mvpLeaders;
        }
      }
    } catch (e) {
      console.warn("Could not fetch player stats summary:", e);
    }
  }

  const tbodyScorers = document.getElementById("pTableScorers");
  if (tbodyScorers) {
    tbodyScorers.innerHTML = "";
    if (scorers.length === 0) {
      tbodyScorers.innerHTML = `<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 1rem;">Aucun point enregistré pour l'instant.</td></tr>`;
    } else {
      scorers.slice(0, 10).forEach(sc => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 800;">#${sc.rank}</td>
          <td class="th-left"><strong>${sc.player_name}</strong> ${sc.player_number ? `<small>(#${sc.player_number})</small>` : ''}</td>
          <td>${sc.team_name}</td>
          <td style="font-weight: 900; color: var(--accent);">${sc.total}</td>
        `;
        tbodyScorers.appendChild(tr);
      });
    }
  }

  const tbodyMvps = document.getElementById("pTableMvps");
  if (tbodyMvps) {
    tbodyMvps.innerHTML = "";
    if (mvps.length === 0) {
      tbodyMvps.innerHTML = `<tr><td colspan="3" style="text-align: center; color: var(--text-muted); padding: 1rem;">Aucun MVP désigné pour l'instant.</td></tr>`;
    } else {
      mvps.slice(0, 10).forEach(m => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
          <td style="font-weight: 800;">#${m.rank}</td>
          <td class="th-left"><strong>${m.player_name}</strong></td>
          <td style="font-weight: 900; color: var(--accent);">⭐ ${m.total}</td>
        `;
        tbodyMvps.appendChild(tr);
      });
    }
  }
}

// ---------------- TAB 4: FAIR-PLAY (F3.3) ----------------
function renderPublicFairPlay() {
  const fpList = currentTournamentData.fair_play || [];
  const thead = document.getElementById("pTableHeadFairPlay");
  const tbody = document.getElementById("pTableBodyFairPlay");
  tbody.innerHTML = "";

  const sport = (currentTournamentData.tournament && currentTournamentData.tournament.sport) ? currentTournamentData.tournament.sport.toLowerCase() : "football";
  const isBasketball = sport === "basketball";
  const isHandball = sport === "handball";

  if (thead) {
    if (isBasketball) {
      thead.innerHTML = `
        <tr>
          <th style="width: 50px;">#</th>
          <th class="th-left">Équipe</th>
          <th>Fautes Perso.</th>
          <th>Fautes Tech.</th>
          <th>Antisportives / Disq.</th>
          <th>Points Pénalité</th>
        </tr>
      `;
    } else if (isHandball) {
      thead.innerHTML = `
        <tr>
          <th style="width: 50px;">#</th>
          <th class="th-left">Équipe</th>
          <th>Avertissements</th>
          <th>Exclusions 2min</th>
          <th>Disqualifications</th>
          <th>Points Pénalité</th>
        </tr>
      `;
    } else {
      thead.innerHTML = `
        <tr>
          <th style="width: 50px;">#</th>
          <th class="th-left">Équipe</th>
          <th>Cartons Jaunes</th>
          <th>Cartons Rouges</th>
          <th>Points Pénalité</th>
        </tr>
      `;
    }
  }

  fpList.forEach(fp => {
    const tr = document.createElement("tr");
    let statsCols = "";

    if (isBasketball) {
      const antisp = (fp.unsportsmanlike_fouls || 0) + (fp.disqualifying_fouls || 0);
      statsCols = `
        <td>${fp.fouls || 0}</td>
        <td>${fp.technical_fouls || 0}</td>
        <td>${antisp}</td>
      `;
    } else if (isHandball) {
      statsCols = `
        <td>${fp.yellow_cards || 0}</td>
        <td>${fp.suspensions || 0}</td>
        <td>${fp.red_cards || 0}</td>
      `;
    } else {
      statsCols = `
        <td>${fp.yellow_cards || 0}</td>
        <td>${fp.red_cards || 0}</td>
      `;
    }

    tr.innerHTML = `
      <td style="font-weight: 800; color: ${fp.rank === 1 ? '#22c55e' : 'inherit'};">#${fp.rank}</td>
      <td class="th-left">
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <div style="width: 10px; height: 10px; border-radius: 2px; background: ${fp.color};"></div>
          <strong>${fp.name}</strong>
        </div>
      </td>
      ${statsCols}
      <td style="font-weight: 900; color: ${fp.penalty_points === 0 ? '#22c55e' : 'var(--accent)'};">${fp.penalty_points} pts</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------------- TAB 5: HEAD-TO-HEAD (F3.2) ----------------
function preparePublicH2HSelectors() {
  const teams = currentTournamentData.teams || [];
  const s1 = document.getElementById("pH2hTeam1");
  const s2 = document.getElementById("pH2hTeam2");
  if (!s1 || !s2 || s1.children.length > 0) return;

  teams.forEach((t, idx) => {
    const o1 = document.createElement("option");
    o1.value = t.id;
    o1.textContent = t.name;
    s1.appendChild(o1);

    const o2 = document.createElement("option");
    o2.value = t.id;
    o2.textContent = t.name;
    if (idx === 1) o2.selected = true;
    s2.appendChild(o2);
  });
}

async function loadPublicH2H() {
  const t1 = parseInt(document.getElementById("pH2hTeam1").value);
  const t2 = parseInt(document.getElementById("pH2hTeam2").value);
  if (t1 === t2) {
    alert("Veuillez choisir 2 équipes différentes.");
    return;
  }

  try {
    const res = await fetch(`/api/head-to-head?team1=${t1}&team2=${t2}`);
    const data = await res.json();
    const results = document.getElementById("pH2hResults");
    results.style.display = "block";

    results.innerHTML = `
      <div style="display: flex; justify-content: space-around; text-align: center; margin-bottom: 1rem; background: rgba(255,255,255,0.05); padding: 1rem; border-radius: 8px;">
        <div>
          <div style="font-size: 1.1rem; font-weight: 800;">${data.team1.name}</div>
          <div style="font-size: 1.8rem; font-weight: 900; color: var(--accent);">${data.team1_wins} V</div>
          <small style="color: var(--text-muted);">${data.team1_scored} buts/pts</small>
        </div>
        <div style="display: flex; flex-direction: column; justify-content: center;">
          <div style="font-size: 1.2rem; font-weight: 900; color: #fff;">${data.total_matches} Matchs</div>
          <small style="color: var(--text-muted);">${data.draws} nuls</small>
        </div>
        <div>
          <div style="font-size: 1.1rem; font-weight: 800;">${data.team2.name}</div>
          <div style="font-size: 1.8rem; font-weight: 900; color: var(--accent-blue);">${data.team2_wins} V</div>
          <small style="color: var(--text-muted);">${data.team2_scored} buts/pts</small>
        </div>
      </div>
      <div style="font-size: 0.85rem;">
        ${data.matches.map(m => `
          <div style="padding: 0.4rem 0; border-bottom: 1px solid var(--border-dark); display: flex; justify-content: space-between;">
            <span>${m.round_name} (${m.match_date || '--'})</span>
            <strong>${m.team_home_name} ${m.score_home} - ${m.score_away} ${m.team_away_name}</strong>
          </div>
        `).join('')}
      </div>
    `;
  } catch (err) {
    alert("Erreur face-à-face");
  }
}

// ---------------- TAB 6: PREDICTIONS (F4.1) ----------------
async function loadPublicPredictions() {
  if (!currentTournamentId) return;
  try {
    const res = await fetch(`/api/predictions?tournament_id=${currentTournamentId}`);
    const data = await res.json();

    const tbodyStudents = document.getElementById("pTablePredStudents");
    tbodyStudents.innerHTML = "";
    (data.students || []).slice(0, 10).forEach(st => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 800;">#${st.rank}</td>
        <td><strong>${st.student_name}</strong></td>
        <td>${st.student_school}</td>
        <td style="font-weight: 900; color: var(--accent);">${st.total_points}</td>
      `;
      tbodyStudents.appendChild(tr);
    });

    const tbodySchools = document.getElementById("pTablePredSchools");
    tbodySchools.innerHTML = "";
    (data.schools || []).forEach(sc => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 800;">#${sc.rank}</td>
        <td><strong>${sc.student_school}</strong></td>
        <td>${sc.avg_points} pts/él.</td>
        <td style="font-weight: 900; color: var(--accent-blue);">${sc.total_points}</td>
      `;
      tbodySchools.appendChild(tr);
    });
  } catch (err) {
    console.error(err);
  }
}

function openPublicPredictionModal() {
  const name = prompt("Votre Nom ou Pseudo d'élève :");
  if (!name) return;
  const school = prompt("Votre Filière / Établissement (ex: Génie Informatique) :") || "Élève";

  const matches = (currentTournamentData.matches || []).filter(m => m.status !== "finished");
  if (matches.length === 0) {
    alert("Aucun match à venir n'est disponible pour les pronostics.");
    return;
  }

  const matchOptions = matches.map((m, idx) => `${idx + 1}. ${m.round_name} : ${m.team_home_name} vs ${m.team_away_name}`).join("\n");
  const choice = prompt(`Choisissez le numéro du match :\n${matchOptions}`);
  const matchIdx = parseInt(choice) - 1;
  if (isNaN(matchIdx) || !matches[matchIdx]) return;

  const targetMatch = matches[matchIdx];
  const sh = parseInt(prompt(`Score prévu pour ${targetMatch.team_home_name} :`, "0"));
  const sa = parseInt(prompt(`Score prévu pour ${targetMatch.team_away_name} :`, "0"));

  if (isNaN(sh) || isNaN(sa)) return;

  fetch("/api/predictions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      tournament_id: currentTournamentId,
      match_id: targetMatch.id,
      student_name: name,
      student_school: school,
      predicted_score_home: sh,
      predicted_score_away: sa
    })
  }).then(r => r.json()).then(data => {
    if (data.status === "ok") {
      alert("Votre pronostic a bien été validé ! (3 pts score exact, 1 pt bonne issue)");
      loadPublicPredictions();
    } else {
      alert(data.error || "Erreur pronostic");
    }
  });
}

// ---------------- TAB 7: AWARDS ----------------
function renderPublicAwards() {
  const awards = currentTournamentData.awards || [];
  const container = document.getElementById("pAwardsContainer");
  container.innerHTML = "";

  if (awards.length === 0) {
    container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">Aucun joueur de la semaine proclamé pour l'instant.</div>`;
    return;
  }

  awards.forEach(a => {
    const card = document.createElement("div");
    card.className = "standings-card";
    card.style.marginBottom = "1rem";

    card.innerHTML = `
      <div style="display: flex; gap: 1rem; align-items: center;">
        <div style="width: 50px; height: 50px; border-radius: 50%; background: var(--accent); display: flex; align-items: center; justify-content: center; font-size: 1.5rem;">
          ⭐
        </div>
        <div>
          <div style="font-size: 0.8rem; color: var(--accent); font-weight: 800;">${a.week_label.toUpperCase()}</div>
          <h3 style="font-size: 1.1rem; font-weight: 800;">${a.player_name} (${a.team_name})</h3>
          <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.2rem;">${a.description || a.title}</p>
        </div>
      </div>
    `;
    container.appendChild(card);
  });
}

// ---------------- TAB 8: HIGHLIGHTS ----------------
async function loadPublicHighlights() {
  if (!currentTournamentId) return;
  try {
    const res = await fetch(`/api/highlights?tournament_id=${currentTournamentId}`);
    const highlights = await res.json();
    const container = document.getElementById("pHighlightsGrid");
    container.innerHTML = "";

    highlights.forEach(h => {
      const card = document.createElement("div");
      card.className = "p-highlight-card";

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <span style="background: rgba(245, 158, 11, 0.2); color: var(--accent); font-size: 0.75rem; font-weight: 800; padding: 0.2rem 0.5rem; border-radius: 4px;">
            ${h.action_type.toUpperCase()}
          </span>
          <button class="nav-action-btn" onclick="likeHighlight(${h.id}, this)">
            ❤️ <span class="like-count">${h.likes_count}</span>
          </button>
        </div>
        <h4 style="font-size: 1.05rem; font-weight: 800; margin-bottom: 0.35rem;">${h.title}</h4>
        <p style="font-size: 0.85rem; color: var(--text-muted); line-height: 1.4;">${h.description}</p>
      `;
      container.appendChild(card);
    });
  } catch (err) {
    console.error(err);
  }
}

async function likeHighlight(hlId, btn) {
  try {
    const res = await fetch(`/api/highlights/${hlId}/like`, { method: "POST" });
    const data = await res.json();
    if (data.status === "ok") {
      btn.querySelector(".like-count").textContent = data.likes_count;
    }
  } catch (e) {
    console.warn(e);
  }
}

// ---------------- TAB: PALMARES & HISTORIQUE ----------------
let currentPublicHistorySport = "all";

async function loadPublicHistory(sport = null) {
  if (sport) currentPublicHistorySport = sport;
  const grid = document.getElementById("pHistoryGrid");
  if (!grid) return;

  grid.innerHTML = `<div style="grid-column: 1 / -1; text-align: center; padding: 2.5rem; color: #9ca3af;">Chargement des archives du Palmarès...</div>`;

  try {
    const url = `/api/history?sport=${encodeURIComponent(currentPublicHistorySport)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("Erreur de chargement");
    const list = await res.json();

    if (!list || list.length === 0) {
      grid.innerHTML = `
        <div style="grid-column: 1 / -1; text-align: center; padding: 3.5rem 1rem; background: rgba(31, 41, 55, 0.5); border-radius: 16px; border: 1px dashed var(--border-dark);">
          <div style="font-size: 3rem; margin-bottom: 0.75rem;">🏛️</div>
          <h3 style="font-size: 1.2rem; font-weight: 800; color: #fff;">Aucun palmarès archivé pour cette sélection</h3>
          <p style="color: #9ca3af; font-size: 0.9rem; margin-top: 0.35rem;">Les archives officielles des saisons précédentes apparaîtront ici.</p>
        </div>
      `;
      return;
    }

    grid.innerHTML = list.map(h => {
      const sportIcons = { football: "⚽ Football", basketball: "🏀 Basketball", handball: "🤾 Handball", volleyball: "🏐 Volleyball" };
      const sportLabel = sportIcons[h.sport] || h.sport.toUpperCase();

      const imageHtml = h.image_url ? `
        <div class="history-img-wrapper">
          <img src="${h.image_url}" alt="Sacre ${h.champion_team}" loading="lazy" onerror="this.parentElement.style.display='none'">
          <div style="position: absolute; inset: 0; background: linear-gradient(to top, rgba(0,0,0,0.85) 0%, rgba(0,0,0,0.1) 60%, transparent 100%); pointer-events: none;"></div>
          <div class="history-badge-year">
            🏆 ${h.year}
          </div>
        </div>
      ` : `
        <div style="padding: 1.25rem; background: linear-gradient(135deg, #1e3a8a, #0284c7); display: flex; justify-content: space-between; align-items: center; color: #fff;">
          <span style="font-size: 1.15rem; font-weight: 900;">🏆 Édition ${h.year}</span>
          <span style="background: rgba(255,255,255,0.2); padding: 0.25rem 0.6rem; border-radius: 6px; font-size: 0.8rem; font-weight: 700;">${sportLabel}</span>
        </div>
      `;

      return `
        <div class="history-public-card">
          ${imageHtml}
          <div class="history-card-body">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.6rem;">
              <span class="badge-chip" style="background: var(--accent-gold-bg); color: var(--accent); border: 1px solid rgba(245, 158, 11, 0.35);">
                ${sportLabel}
              </span>
              <span style="font-size: 0.85rem; font-weight: 700; color: var(--text-muted);">${h.year}</span>
            </div>

            <h3 style="font-size: 1.25rem; font-weight: 900; color: var(--text-main); margin-bottom: 0.85rem; line-height: 1.3;">
              ${h.tournament_title}
            </h3>

            <!-- Champion Box -->
            <div class="history-champion-box">
              <div style="display: flex; align-items: center; gap: 0.4rem; margin-bottom: 0.2rem;">
                <span style="font-size: 1.2rem;">👑</span>
                <span style="font-size: 0.75rem; text-transform: uppercase; font-weight: 800; color: #b45309; letter-spacing: 0.5px;">ÉQUIPE CHAMPIONNE</span>
              </div>
              <div style="font-size: 1.25rem; font-weight: 900; color: var(--text-main);">
                ${h.champion_team}
              </div>
              ${h.final_score || h.runner_up_team ? `
                <div style="margin-top: 0.45rem; padding-top: 0.45rem; border-top: 1px solid rgba(245, 158, 11, 0.25); font-size: 0.85rem; color: var(--text-muted); display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 0.3rem;">
                  <span>Score finale : <strong style="color: var(--accent); font-size: 0.95rem;">${h.final_score || 'Victoire'}</strong></span>
                  ${h.runner_up_team ? `<span>vs ${h.runner_up_team}</span>` : ''}
                </div>
              ` : ''}
            </div>

            <!-- Stats Box -->
            <div class="history-stats-grid">
              ${h.top_scorer_name ? `
                <div class="history-stat-card">
                  <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">👟 Meilleur Buteur</div>
                  <div style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin-top: 0.15rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${h.top_scorer_name}">
                    ${h.top_scorer_name}
                  </div>
                  ${h.top_scorer_stat ? `<div style="font-size: 0.8rem; color: var(--primary); font-weight: 700;">${h.top_scorer_stat}</div>` : ''}
                </div>
              ` : ''}
              ${h.mvp_name ? `
                <div class="history-stat-card">
                  <div style="font-size: 0.7rem; color: var(--text-muted); font-weight: 700; text-transform: uppercase;">⭐ MVP / Joueur Clé</div>
                  <div style="font-size: 0.95rem; font-weight: 800; color: var(--text-main); margin-top: 0.15rem; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${h.mvp_name}">
                    ${h.mvp_name}
                  </div>
                  <div style="font-size: 0.8rem; color: #16a34a; font-weight: 700;">Meilleur Joueur</div>
                </div>
              ` : ''}
            </div>

            ${h.summary ? `
              <div class="history-summary-box">
                <p style="font-size: 0.85rem; color: var(--text-main); line-height: 1.5; margin: 0; font-style: italic;">
                  « ${h.summary} »
                </p>
              </div>
            ` : ''}
          </div>
        </div>
      `;
    }).join("");
  } catch (err) {
    console.error("loadPublicHistory error:", err);
    grid.innerHTML = `<div style="grid-column: 1 / -1; color: #ef4444; padding: 2rem; text-align: center;">Erreur de chargement des archives.</div>`;
  }
}

function filterPublicHistory(sport, btn) {
  document.querySelectorAll("#publicHistorySportFilters .history-filter-btn").forEach(b => {
    b.classList.remove("active");
  });
  if (btn) {
    btn.classList.add("active");
  }
  loadPublicHistory(sport);
}
