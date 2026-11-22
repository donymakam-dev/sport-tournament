/**
 * Admin Dashboard Logic for Sports Tournament Manager
 * Implements all 18 features from the specifications:
 * - F3.1: Charts (Points evolution, goals, 5-match form)
 * - F3.2: Head-to-Head comparator
 * - F3.3: Fair-Play table & rule configuration
 * - F3.4: Dynamic CSV export links
 * - F4.1: Predictions leaderboard & submission
 * - F4.3: School journalism articles & moderation
 * - F4.4: Automatic team badges
 * - F5.1: Automatic calendar generator with constraint optimization
 * - F5.2: CSV import with validation report and dry-run
 * - F5.3: Match sheet A4 printable link
 * - F5.4: Automatic backups with 14-days retention & restore
 * - F6.4: Privacy analytics counters
 * - F6.5: Immutable audit logs
 */

let currentTournamentId = null;
let currentTournamentData = null;
let uploadedTeamLogoUrl = "";
let uploadedPlayerPhotoUrl = "";
let serverNetworkInfo = null;
let pointsChartInstance = null;
let goalsChartInstance = null;
let pendingGeneratedSchedule = null;
let pendingCsvParsedData = null;

// ---------------- AUTHENTIFICATION ADMIN ----------------
async function checkAdminAuth() {
  const overlay = document.getElementById("adminAuthOverlay");
  const token = localStorage.getItem("admin_token");
  if (!token) {
    if (overlay) overlay.style.display = "flex";
    return false;
  }
  try {
    const res = await fetch("/api/auth/verify", {
      headers: { "X-Admin-Token": token }
    });
    const data = await res.json();
    if (data.authenticated) {
      if (overlay) overlay.style.display = "none";
      return true;
    } else {
      localStorage.removeItem("admin_token");
      if (overlay) overlay.style.display = "flex";
      return false;
    }
  } catch (err) {
    console.error("Auth verify error:", err);
    if (overlay) overlay.style.display = "flex";
    return false;
  }
}

async function handleAdminLogin(e) {
  e.preventDefault();
  const username = document.getElementById("loginUsername").value.trim();
  const password = document.getElementById("loginPassword").value;
  const errorBox = document.getElementById("loginErrorMsg");
  const btn = document.getElementById("btnLoginSubmit");

  errorBox.style.display = "none";
  btn.disabled = true;
  btn.textContent = "Vérification...";

  try {
    const res = await fetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await res.json();
    if (res.ok && data.success) {
      localStorage.setItem("admin_token", data.token);
      document.getElementById("adminAuthOverlay").style.display = "none";
      showToast("Connexion réussie ! Bienvenue dans l'Espace Organisateur.");
      await loadTournaments();
      await loadAdminToolsData();
    } else {
      errorBox.textContent = data.error || "Identifiant ou mot de passe incorrect.";
      errorBox.style.display = "block";
    }
  } catch (err) {
    errorBox.textContent = "Erreur de connexion au serveur.";
    errorBox.style.display = "block";
  } finally {
    btn.disabled = false;
    btn.textContent = "Se connecter";
  }
}

function logoutAdmin() {
  localStorage.removeItem("admin_token");
  window.location.href = "/";
}

// ---------------- DOM Ready ----------------
document.addEventListener("DOMContentLoaded", async () => {
  setupTabs();
  setupEventListeners();
  await loadNetworkInfo();
  const authed = await checkAdminAuth();
  if (authed) {
    await loadTournaments();
    await loadAdminToolsData();
  }
});

async function loadNetworkInfo() {
  try {
    const res = await fetch("/api/network-info");
    if (res.ok) {
      serverNetworkInfo = await res.json();
    }
  } catch (e) {
    console.warn("Could not load network info", e);
  }
}

function getPublicTournamentUrl(tournamentId) {
  const isLocalhost = window.location.hostname === "127.0.0.1" || window.location.hostname === "localhost";
  if (isLocalhost && serverNetworkInfo && serverNetworkInfo.local_ip && serverNetworkInfo.local_ip !== "127.0.0.1") {
    return `http://${serverNetworkInfo.local_ip}:${serverNetworkInfo.port || 8080}/public?t=${tournamentId}`;
  }
  return `${window.location.origin}/public?t=${tournamentId}`;
}

function setupTabs() {
  document.querySelectorAll(".tab-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".tab-btn").forEach(b => b.classList.remove("active"));
      document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
      btn.classList.add("active");
      const tabId = btn.getAttribute("data-tab");
      const targetPane = document.getElementById(tabId);
      if (targetPane) targetPane.classList.add("active");

      // Trigger lazy tab loaders
      if (tabId === "tab-charts") loadTeamChartsData();
      if (tabId === "tab-h2h") prepareHeadToHeadSelectors();
      if (tabId === "tab-predictions") loadPredictionsTab();
      if (tabId === "tab-journalism") loadJournalismTab();
      if (tabId === "tab-admin-tools") loadAdminToolsData();
    });
  });
}

function setupEventListeners() {
  // Switch Tournament Select
  document.getElementById("selectTournament").addEventListener("change", (e) => {
    currentTournamentId = parseInt(e.target.value);
    loadTournamentFull();
  });

  // Create Tournament Form
  document.getElementById("formTournament").addEventListener("submit", async (e) => {
    e.preventDefault();
    const name = document.getElementById("tournName").value.trim();
    const sport = document.getElementById("tournSport").value;
    const year = document.getElementById("tournYear").value.trim();

    try {
      const res = await fetch("/api/tournaments", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, sport, year })
      });
      const data = await res.json();
      if (data.status === "ok") {
        closeModal("modalTournament");
        await loadTournaments(data.id);
        showToast("Tournoi créé avec succès !");
      }
    } catch (err) {
      showToast("Erreur lors de la création du tournoi", "error");
    }
  });

  // Team Form
  document.getElementById("formTeam").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentTournamentId) return;

    const name = document.getElementById("teamName").value.trim();
    const filiere = document.getElementById("teamFiliere").value.trim();
    const short_name = document.getElementById("teamShort").value.trim();
    const color = document.getElementById("teamColor").value;

    try {
      const res = await fetch("/api/teams", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_id: currentTournamentId,
          name,
          filiere,
          short_name,
          color,
          logo_url: uploadedTeamLogoUrl
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        closeModal("modalTeam");
        document.getElementById("formTeam").reset();
        uploadedTeamLogoUrl = "";
        await loadTournamentFull();
        showToast("Équipe ajoutée avec succès !");
      }
    } catch (err) {
      showToast("Erreur lors de la création de l'équipe", "error");
    }
  });

  // Team Logo File Upload
  const logoInput = document.getElementById("teamLogoFile");
  if (logoInput) {
    logoInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      uploadedTeamLogoUrl = await uploadMediaFile(file);
    });
  }

  // Player Form (Add or Edit)
  document.getElementById("formPlayer").addEventListener("submit", async (e) => {
    e.preventDefault();
    const editId = document.getElementById("playerEditId") ? document.getElementById("playerEditId").value : "";
    const team_id = parseInt(document.getElementById("playerTeamId").value);
    const name = document.getElementById("playerName").value.trim();
    const number = parseInt(document.getElementById("playerNumber").value);
    const position = document.getElementById("playerPosition").value.trim();
    const age = document.getElementById("playerAge") && document.getElementById("playerAge").value ? parseInt(document.getElementById("playerAge").value) : null;
    const height = document.getElementById("playerHeight") ? document.getElementById("playerHeight").value.trim() : "";
    const weight = document.getElementById("playerWeight") ? document.getElementById("playerWeight").value.trim() : "";
    const urlInput = document.getElementById("playerPhotoUrl") ? document.getElementById("playerPhotoUrl").value.trim() : "";
    const photo_url = uploadedPlayerPhotoUrl || urlInput || "";

    try {
      let res;
      if (editId) {
        res = await fetch(`/api/players/${editId}`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name,
            number,
            position,
            photo_url,
            age,
            height,
            weight
          })
        });
      } else {
        res = await fetch("/api/players", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            team_id,
            name,
            number,
            position,
            photo_url,
            age,
            height,
            weight
          })
        });
      }
      const data = await res.json();
      if (data.status === "ok") {
        closeModal("modalPlayer");
        document.getElementById("formPlayer").reset();
        uploadedPlayerPhotoUrl = "";
        await loadTournamentFull();
        showToast(editId ? "Fiche du joueur modifiée avec succès !" : "Joueur inscrit avec succès !");
      } else {
        showToast(data.error || "Erreur lors de l'enregistrement", "error");
      }
    } catch (err) {
      showToast("Erreur lors de l'enregistrement du joueur", "error");
    }
  });

  // Player Photo File Upload
  const photoInput = document.getElementById("playerPhotoFile");
  if (photoInput) {
    photoInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      uploadedPlayerPhotoUrl = await uploadMediaFile(file);
      const previewImg = document.getElementById("playerPhotoPreviewImg");
      const previewBox = document.getElementById("playerPhotoPreviewBox");
      const previewInfo = document.getElementById("playerPhotoPreviewInfo");
      if (previewImg && previewBox) {
        previewImg.src = uploadedPlayerPhotoUrl;
        previewBox.style.display = "flex";
        if (previewInfo) previewInfo.textContent = file.name;
      }
    });
  }

  // Player Photo URL live preview
  const photoUrlInput = document.getElementById("playerPhotoUrl");
  if (photoUrlInput) {
    photoUrlInput.addEventListener("input", (e) => {
      const val = e.target.value.trim();
      const previewImg = document.getElementById("playerPhotoPreviewImg");
      const previewBox = document.getElementById("playerPhotoPreviewBox");
      const previewInfo = document.getElementById("playerPhotoPreviewInfo");
      if (val) {
        uploadedPlayerPhotoUrl = val;
        if (previewImg && previewBox) {
          previewImg.src = val;
          previewBox.style.display = "flex";
          if (previewInfo) previewInfo.textContent = "Lien URL renseigné";
        }
      }
    });
  }

  // Match Form
  document.getElementById("formMatch").addEventListener("submit", async (e) => {
    e.preventDefault();
    if (!currentTournamentId) return;

    const team_home_id = parseInt(document.getElementById("matchHomeTeam").value);
    const team_away_id = parseInt(document.getElementById("matchAwayTeam").value);
    const round_name = document.getElementById("matchRound").value.trim();
    const match_date = document.getElementById("matchDate").value;
    const match_time = document.getElementById("matchTime").value;
    const venue = document.getElementById("matchVenue").value.trim();
    const referee = document.getElementById("matchReferee").value.trim();

    if (team_home_id === team_away_id) {
      showToast("L'équipe à domicile et l'équipe à l'extérieur doivent être différentes.", "error");
      return;
    }

    try {
      const res = await fetch("/api/matches", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tournament_id: currentTournamentId,
          team_home_id,
          team_away_id,
          round_name,
          match_date,
          match_time,
          venue,
          referee
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        closeModal("modalMatch");
        document.getElementById("formMatch").reset();
        await loadTournamentFull();
        showToast("Rencontre programmée avec succès !");
      }
    } catch (err) {
      showToast("Erreur lors de la programmation de la rencontre", "error");
    }
  });

  // Score Form
  document.getElementById("formScore").addEventListener("submit", async (e) => {
    e.preventDefault();
    const match_id = parseInt(document.getElementById("scoreMatchId").value);
    const score_home = parseInt(document.getElementById("scoreHome").value);
    const score_away = parseInt(document.getElementById("scoreAway").value);
    const mvp_player_id = document.getElementById("scoreMvpSelect").value ? parseInt(document.getElementById("scoreMvpSelect").value) : null;

    try {
      const res = await fetch(`/api/matches/${match_id}/score`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          score_home,
          score_away,
          status: "finished",
          mvp_player_id,
          author_role: "admin"
        })
      });
      const data = await res.json();
      if (data.status === "ok") {
        closeModal("modalScore");
        await loadTournamentFull();
        showToast("Score officiel enregistré avec succès !");
      }
    } catch (err) {
      showToast("Erreur lors de l'enregistrement du score", "error");
    }
  });

  // Fair-Play Rules Form (F3.3)
  const fpForm = document.getElementById("formFairPlayRules");
  if (fpForm) {
    fpForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentTournamentId) return;

      const yellow_card_points = parseFloat(document.getElementById("fpYellowPts").value);
      const red_card_points = parseFloat(document.getElementById("fpRedPts").value);
      const suspension_points = parseFloat(document.getElementById("fpSuspensionPts").value);
      const foul_points = parseFloat(document.getElementById("fpFoulPts").value);

      try {
        const res = await fetch(`/api/tournament/${currentTournamentId}/fair-play-rules`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ yellow_card_points, red_card_points, suspension_points, foul_points })
        });
        if (res.ok) {
          closeModal("modalFairPlay");
          await loadTournamentFull();
          showToast("Barème Fair-Play mis à jour avec succès !");
        }
      } catch (err) {
        showToast("Erreur lors de la mise à jour du barème", "error");
      }
    });
  }

  // Scheduler Form (F5.1)
  const schedForm = document.getElementById("formScheduler");
  if (schedForm) {
    schedForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentTournamentId) return;

      const venuesStr = document.getElementById("schedVenues").value.trim();
      const venues = venuesStr.split(",").map(s => s.strip ? s.strip() : s.trim()).filter(Boolean);
      const start_date = document.getElementById("schedStartDate").value;
      const min_rest_days = parseInt(document.getElementById("schedRestDays").value || 2);
      const examStr = document.getElementById("schedExamDates").value.trim();
      const exam_dates = examStr.split(",").map(s => s.trim()).filter(Boolean);

      try {
        const res = await fetch(`/api/tournament/${currentTournamentId}/generate-schedule`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            venues,
            start_date,
            min_rest_days,
            exam_dates,
            commit: false
          })
        });
        const data = await res.json();
        if (data.schedule) {
          pendingGeneratedSchedule = data.schedule;
          closeModal("modalScheduler");
          renderSchedulerPreview(data);
          showToast("Calendrier optimisé calculé avec succès !");
        } else if (data.error) {
          showToast(data.error, "error");
        }
      } catch (err) {
        showToast("Erreur lors du calcul du calendrier", "error");
      }
    });
  }

  // Prediction Submit Form (F4.1)
  const predForm = document.getElementById("formPrediction");
  if (predForm) {
    predForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentTournamentId) return;

      const student_name = document.getElementById("predStudentName").value.trim();
      const student_school = document.getElementById("predStudentSchool").value.trim();
      const match_id = parseInt(document.getElementById("predMatchSelect").value);
      const predicted_score_home = parseInt(document.getElementById("predScoreHome").value);
      const predicted_score_away = parseInt(document.getElementById("predScoreAway").value);

      try {
        const res = await fetch("/api/predictions", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tournament_id: currentTournamentId,
            match_id,
            student_name,
            student_school,
            predicted_score_home,
            predicted_score_away
          })
        });
        const data = await res.json();
        if (data.status === "ok") {
          closeModal("modalSubmitPrediction");
          predForm.reset();
          loadPredictionsTab();
          showToast("Votre pronostic a été enregistré !");
        } else {
          showToast(data.error || "Erreur pronostic", "error");
        }
      } catch (err) {
        showToast("Erreur lors du dépôt du pronostic", "error");
      }
    });
  }

  // Article Submit Form (F4.3)
  const articleForm = document.getElementById("formArticle");
  if (articleForm) {
    articleForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const match_id = parseInt(document.getElementById("articleMatchSelect").value);
      const author_name = document.getElementById("articleAuthor").value.trim();
      const author_school = document.getElementById("articleSchool").value.trim();
      const title = document.getElementById("articleTitle").value.trim();
      const content = document.getElementById("articleContent").value.trim();

      try {
        const res = await fetch("/api/match-reports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ match_id, author_name, author_school, title, content })
        });
        const data = await res.json();
        if (data.status === "ok") {
          closeModal("modalWriteArticle");
          articleForm.reset();
          loadJournalismTab();
          showToast(data.message || "Compte rendu soumis avec succès !");
        }
      } catch (err) {
        showToast("Erreur lors de la soumission de l'article", "error");
      }
    });
  }

  // Highlights Form
  const hlForm = document.getElementById("formHighlight");
  if (hlForm) {
    hlForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      if (!currentTournamentId) return;

      const title = document.getElementById("hlTitle").value.trim();
      const action_type = document.getElementById("hlActionType").value;
      const media_type = document.getElementById("hlMediaType").value;
      const description = document.getElementById("hlDescription").value.trim();
      const player_id = document.getElementById("hlPlayerSelect").value ? parseInt(document.getElementById("hlPlayerSelect").value) : null;
      const match_id = document.getElementById("hlMatchSelect").value ? parseInt(document.getElementById("hlMatchSelect").value) : null;

      let media_url = "";
      const fileInput = document.getElementById("hlFileInput");
      if (fileInput && fileInput.files[0]) {
        media_url = await uploadMediaFile(fileInput.files[0]);
      }

      try {
        const res = await fetch("/api/highlights", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            tournament_id: currentTournamentId,
            title,
            action_type,
            media_type,
            media_url,
            description,
            player_id,
            match_id
          })
        });
        const data = await res.json();
        if (data.status === "ok") {
          closeModal("modalHighlight");
          hlForm.reset();
          loadHighlights();
          showToast("Action mise en ligne !");
        }
      } catch (err) {
        showToast("Erreur lors de l'ajout de l'action", "error");
      }
    });
  }
}

// ---------------- Media Upload Helper ----------------
async function uploadMediaFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = async () => {
      try {
        const res = await fetch("/api/upload-media", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            filename: file.name,
            data: reader.result
          })
        });
        const data = await res.json();
        if (data.status === "ok") {
          resolve(data.url);
        } else {
          reject("Upload error");
        }
      } catch (err) {
        reject(err);
      }
    };
    reader.readAsDataURL(file);
  });
}

// ---------------- Load Tournaments List ----------------
async function loadTournaments(selectIdAfter = null) {
  try {
    const res = await fetch("/api/tournaments");
    const tournaments = await res.json();

    const select = document.getElementById("selectTournament");
    select.innerHTML = "";

    if (tournaments.length === 0) {
      document.getElementById("displayTournamentName").textContent = "Aucun tournoi disponible";
      return;
    }

    tournaments.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = `${t.name} (${t.sport.toUpperCase()} - ${t.year})`;
      select.appendChild(opt);
    });

    if (selectIdAfter) {
      currentTournamentId = selectIdAfter;
      select.value = selectIdAfter;
    } else {
      currentTournamentId = tournaments[0].id;
    }

    await loadTournamentFull();
  } catch (err) {
    console.error("Erreur chargement tournois :", err);
  }
}

// ---------------- Load Active Tournament Full Data ----------------
async function loadTournamentFull() {
  if (!currentTournamentId) return;

  try {
    const res = await fetch(`/api/tournament/${currentTournamentId}/full`);
    currentTournamentData = await res.json();

    renderTournamentHeader();
    renderStandings();
    renderMatches();
    renderTeams();
    renderStats();
    renderFairPlay();
    renderShareInfo();
    loadHighlights();
    populateSelects();
    updateExportLinks();
  } catch (err) {
    console.error("Erreur chargement données tournoi :", err);
  }
}

function updateExportLinks() {
  if (!currentTournamentId) return;
  const setLink = (id, path) => {
    const el = document.getElementById(id);
    if (el) el.href = `${path}?tournament_id=${currentTournamentId}`;
  };
  setLink("btnExportStandingsCsv", "/api/export/standings.csv");
  setLink("btnExportMatchesCsv", "/api/export/matches.csv");
  setLink("btnExportTeamsCsv", "/api/export/teams.csv");
  setLink("btnExportScorersCsv", "/api/export/scorers.csv");
}

function renderTournamentHeader() {
  const t = currentTournamentData.tournament;
  document.getElementById("displayTournamentName").textContent = t.name;
  document.getElementById("displayTournamentSport").textContent = `Discipline : ${t.sport.toUpperCase()}`;
  document.getElementById("displayTournamentYear").textContent = `Édition : ${t.year}`;

  const link = getPublicTournamentUrl(t.id);
  document.getElementById("publicLinkPreview").textContent = link;
  document.getElementById("btnOpenPublic").href = `/public?t=${t.id}`;
}

// ---------------- TAB 1: STANDINGS ----------------
function renderStandings() {
  const t = currentTournamentData.tournament;
  const standings = currentTournamentData.standings || [];
  const tbody = document.getElementById("tableBodyStandings");
  const thead = document.getElementById("tableHeadStandings");
  tbody.innerHTML = "";

  const isBasket = t.sport === "basketball";

  thead.innerHTML = `
    <tr>
      <th style="width: 50px;">Rang</th>
      <th>Équipe</th>
      <th style="text-align: center;">Points</th>
      <th style="text-align: center;">J</th>
      <th style="text-align: center;">V</th>
      ${!isBasket ? '<th style="text-align: center;">N</th>' : ''}
      <th style="text-align: center;">D</th>
      <th style="text-align: center;">${isBasket ? 'Pts Marq.' : 'BP'}</th>
      <th style="text-align: center;">${isBasket ? 'Pts Enc.' : 'BC'}</th>
      <th style="text-align: center;">Diff</th>
      <th>Forme / Badges</th>
    </tr>
  `;

  if (standings.length === 0) {
    tbody.innerHTML = `<tr><td colspan="11" style="text-align: center; color: var(--text-muted); padding: 2rem;">Aucun match joué pour le moment.</td></tr>`;
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
      <td style="font-weight: 800; font-size: 1rem; color: ${s.rank === 1 ? '#eab308' : 'inherit'};">#${s.rank}</td>
      <td>
        <div style="display: flex; align-items: center; gap: 0.65rem;">
          <div style="width: 14px; height: 14px; border-radius: 3px; background: ${s.color};"></div>
          <strong>${s.name}</strong>
          <small style="color: var(--text-muted);">(${s.filiere})</small>
        </div>
      </td>
      <td style="text-align: center; font-weight: 900; font-size: 1.05rem; color: var(--primary);">${s.points}</td>
      <td style="text-align: center;">${s.played}</td>
      <td style="text-align: center; color: #16a34a; font-weight: 700;">${s.won}</td>
      ${!isBasket ? `<td style="text-align: center; color: #64748b;">${s.drawn}</td>` : ''}
      <td style="text-align: center; color: #dc2626;">${s.lost}</td>
      <td style="text-align: center;">${s.scored}</td>
      <td style="text-align: center;">${s.conceded}</td>
      <td style="text-align: center; font-weight: 700; color: ${s.diff > 0 ? '#16a34a' : (s.diff < 0 ? '#dc2626' : 'inherit')};">
        ${s.diff > 0 ? '+' : ''}${s.diff}
      </td>
      <td>${badgesHtml || '<span style="color: var(--text-muted); font-size: 0.8rem;">En compétition</span>'}</td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------------- TAB 2: MATCHES & F5.3 MATCH SHEET ----------------
function renderMatches() {
  const matches = currentTournamentData.matches || [];
  const container = document.getElementById("matchesContainer");
  container.innerHTML = "";

  if (matches.length === 0) {
    container.innerHTML = `<div style="text-align: center; padding: 2rem; color: var(--text-muted);">Aucune rencontre programmée. Cliquez sur « Programmer une Rencontre ».</div>`;
    return;
  }

  matches.forEach(m => {
    const card = document.createElement("div");
    card.className = "match-card";

    const isFinished = m.status === "finished";

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem; font-size: 0.85rem; color: var(--text-muted);">
        <span><strong>${m.round_name}</strong> • ${m.match_date || 'Date à fixer'} (${m.match_time || '--:--'})</span>
        <span class="status-pill ${isFinished ? 'status-approved' : 'status-pending'}">
          ${isFinished ? 'Terminé' : 'À venir'}
        </span>
      </div>

      <div style="display: flex; justify-content: space-between; align-items: center; margin: 1rem 0;">
        <div style="flex: 1; text-align: left;">
          <div style="font-weight: 800; font-size: 1rem;">${m.team_home_name}</div>
          <small style="color: var(--text-muted);">${m.team_home_short}</small>
        </div>
        
        <div style="padding: 0 1rem; text-align: center;">
          <div style="font-size: 1.5rem; font-weight: 900; letter-spacing: 2px;">
            ${m.score_home !== null ? m.score_home : '-'} : ${m.score_away !== null ? m.score_away : '-'}
          </div>
          <small style="color: var(--text-muted); display: block; margin-top: 2px;">${m.venue || 'Terrain'}</small>
        </div>

        <div style="flex: 1; text-align: right;">
          <div style="font-weight: 800; font-size: 1rem;">${m.team_away_name}</div>
          <small style="color: var(--text-muted);">${m.team_away_short}</small>
        </div>
      </div>

      ${m.mvp_name ? `
        <div style="background: rgba(245, 158, 11, 0.1); border: 1px dashed #f59e0b; padding: 0.4rem 0.6rem; border-radius: 6px; font-size: 0.8rem; margin-bottom: 0.75rem;">
          ⭐ <strong>Homme du match :</strong> ${m.mvp_name}
        </div>
      ` : ''}

      <div style="display: flex; gap: 0.4rem; justify-content: flex-end; flex-wrap: wrap;">
        <button class="btn btn-secondary btn-sm" onclick="openScoreModal(${m.id})">
          ${isFinished ? '✏️ Modifier Score' : '⚽ Saisir Score'}
        </button>
        <a href="/match_sheet.html?id=${m.id}" target="_blank" class="btn btn-secondary btn-sm" title="Imprimer la feuille officielle A4">
          📄 Feuille A4
        </a>
        <button class="btn btn-secondary btn-sm" style="color: #dc2626;" onclick="deleteMatch(${m.id})">🗑️</button>
      </div>
    `;
    container.appendChild(card);
  });
}

function openScoreModal(matchId) {
  const m = (currentTournamentData.matches || []).find(item => item.id === matchId);
  if (!m) return;

  document.getElementById("scoreMatchId").value = m.id;
  document.getElementById("scoreModalHomeName").textContent = m.team_home_name;
  document.getElementById("scoreModalAwayName").textContent = m.team_away_name;
  document.getElementById("scoreHome").value = m.score_home !== null ? m.score_home : 0;
  document.getElementById("scoreAway").value = m.score_away !== null ? m.score_away : 0;

  // Populate MVP select with players from both teams
  const mvpSelect = document.getElementById("scoreMvpSelect");
  mvpSelect.innerHTML = `<option value="">-- Aucun MVP désigné --</option>`;

  const players = currentTournamentData.players || [];
  const matchPlayers = players.filter(p => p.team_id === m.team_home_id || p.team_id === m.team_away_id);
  matchPlayers.forEach(p => {
    const opt = document.createElement("option");
    opt.value = p.id;
    opt.textContent = `${p.name} (#${p.number} - ${p.team_name})`;
    if (m.mvp_player_id === p.id) opt.selected = true;
    mvpSelect.appendChild(opt);
  });

  openModal("modalScore");
}

async function deleteMatch(matchId) {
  if (!confirm("Voulez-vous vraiment supprimer cette rencontre ?")) return;
  try {
    const res = await fetch(`/api/matches/${matchId}`, { method: "DELETE" });
    if (res.ok) {
      await loadTournamentFull();
      showToast("Match supprimé");
    }
  } catch (err) {
    showToast("Erreur lors de la suppression", "error");
  }
}

// ---------------- TAB 3: TEAMS & PLAYERS ----------------
function renderTeams() {
  const teams = currentTournamentData.teams || [];
  const players = currentTournamentData.players || [];
  const container = document.getElementById("teamsContainer");
  container.innerHTML = "";

  teams.forEach(t => {
    const tPlayers = players.filter(p => p.team_id === t.id);
    const card = document.createElement("div");
    card.className = "team-card";

    let badgesHtml = "";
    if (t.badges && t.badges.length > 0) {
      badgesHtml = t.badges.map(b => `<span class="badge-chip" style="background: ${b.color};">${b.label}</span>`).join(" ");
    }

    card.innerHTML = `
      <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 2px solid ${t.color}; padding-bottom: 0.6rem; margin-bottom: 0.75rem;">
        <div>
          <h3 style="font-size: 1.1rem; font-weight: 800; color: ${t.color};">${t.name}</h3>
          <small style="color: var(--text-muted);">${t.filiere} (${t.short_name})</small>
        </div>
        <button class="btn btn-primary btn-sm" onclick="openPlayerModal(${t.id})">➕ Joueur</button>
      </div>

      <div style="margin-bottom: 0.6rem;">${badgesHtml}</div>

      <div style="max-height: 220px; overflow-y: auto; font-size: 0.85rem;">
        ${tPlayers.length === 0 ? '<div style="color: var(--text-muted); padding: 0.5rem 0;">Aucun joueur inscrit.</div>' : ''}
        ${tPlayers.map(p => `
          <div style="display: flex; justify-content: space-between; align-items: center; padding: 0.5rem 0; border-bottom: 1px solid var(--border);">
            <div style="display: flex; align-items: center; gap: 0.65rem; min-width: 0; flex: 1;">
              ${p.photo_url ? `<img src="${p.photo_url}" style="width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 1.5px solid ${t.color}; flex-shrink: 0;" alt="${p.name}">` : `<div style="width: 32px; height: 32px; border-radius: 50%; background: #e2e8f0; display: flex; align-items: center; justify-content: center; font-size: 0.72rem; font-weight: 800; color: #475569; flex-shrink: 0;">#${p.number}</div>`}
              <div style="min-width: 0;">
                <div style="font-weight: 800; color: var(--text-main); font-size: 0.9rem;">#${p.number} ${p.name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); display: flex; gap: 0.4rem; flex-wrap: wrap;">
                  ${[p.position ? `<span style="font-weight: 600;">${p.position}</span>` : 'Joueur', p.age ? `<span>• ${p.age} ans</span>` : '', p.weight ? `<span>• ${p.weight}</span>` : '', p.height ? `<span>• ${p.height}</span>` : ''].filter(Boolean).join(' ')}
                </div>
              </div>
            </div>
            <div style="display: flex; gap: 0.35rem; align-items: center; margin-left: 0.5rem; flex-shrink: 0;">
              <button class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.55rem; font-size: 0.75rem;" onclick="editPlayer(${p.id})" title="Modifier ce joueur (dorsal, poids, âge, photo...)">✏️ Modifier</button>
              <button class="btn btn-secondary btn-sm" style="padding: 0.25rem 0.45rem; font-size: 0.75rem; color: #dc2626;" onclick="deletePlayer(${p.id})" title="Supprimer ce joueur">🗑️</button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
    container.appendChild(card);
  });
}

function openPlayerModal(teamId, playerId = null) {
  document.getElementById("playerTeamId").value = teamId;
  const form = document.getElementById("formPlayer");
  form.reset();
  uploadedPlayerPhotoUrl = "";

  const titleEl = document.getElementById("modalPlayerTitle");
  const submitBtn = document.getElementById("btnSubmitPlayer");
  const previewBox = document.getElementById("playerPhotoPreviewBox");
  const previewImg = document.getElementById("playerPhotoPreviewImg");
  const previewInfo = document.getElementById("playerPhotoPreviewInfo");
  const editIdInput = document.getElementById("playerEditId");
  const urlInput = document.getElementById("playerPhotoUrl");

  if (playerId) {
    if (editIdInput) editIdInput.value = playerId;
    if (titleEl) titleEl.textContent = "Modifier la fiche du Joueur";
    if (submitBtn) submitBtn.textContent = "Enregistrer les modifications";

    const players = currentTournamentData.players || [];
    const p = players.find(x => x.id === playerId);
    if (p) {
      document.getElementById("playerName").value = p.name || "";
      document.getElementById("playerNumber").value = p.number !== undefined ? p.number : 0;
      document.getElementById("playerPosition").value = p.position || "";
      document.getElementById("playerAge").value = p.age || "";
      document.getElementById("playerHeight").value = p.height || "";
      document.getElementById("playerWeight").value = p.weight || "";
      if (urlInput) urlInput.value = p.photo_url || "";
      uploadedPlayerPhotoUrl = p.photo_url || "";

      if (p.photo_url && previewImg && previewBox) {
        previewImg.src = p.photo_url;
        previewBox.style.display = "flex";
        if (previewInfo) previewInfo.textContent = "Photo actuelle";
      } else if (previewBox) {
        previewBox.style.display = "none";
      }
    }
  } else {
    if (editIdInput) editIdInput.value = "";
    if (titleEl) titleEl.textContent = "Ajouter un Joueur";
    if (submitBtn) submitBtn.textContent = "Inscrire le Joueur";
    if (previewBox) previewBox.style.display = "none";
  }

  openModal("modalPlayer");
}

window.editPlayer = function(playerId) {
  const players = currentTournamentData.players || [];
  const p = players.find(x => x.id === playerId);
  if (p) {
    openPlayerModal(p.team_id, p.id);
  }
};

window.removePlayerPhoto = function() {
  uploadedPlayerPhotoUrl = "";
  if (document.getElementById("playerPhotoUrl")) document.getElementById("playerPhotoUrl").value = "";
  if (document.getElementById("playerPhotoFile")) document.getElementById("playerPhotoFile").value = "";
  if (document.getElementById("playerPhotoPreviewBox")) document.getElementById("playerPhotoPreviewBox").style.display = "none";
};

window.deletePlayer = async function(playerId) {
  if (!confirm("Voulez-vous vraiment supprimer ce joueur ?")) return;
  try {
    const res = await fetch(`/api/players/${playerId}`, { method: "DELETE" });
    const data = await res.json();
    if (data.status === "ok") {
      await loadTournamentFull();
      showToast("Joueur supprimé.");
    } else {
      showToast(data.error || "Erreur lors de la suppression", "error");
    }
  } catch (err) {
    showToast("Erreur lors de la suppression du joueur", "error");
  }
};

// ---------------- TAB 4: F3.1 CHARTS (CHART.JS) ----------------
async function loadTeamChartsData() {
  const teamSelect = document.getElementById("selectChartTeam");
  const teams = currentTournamentData.teams || [];

  if (teams.length === 0) return;

  // Populate selector if empty
  if (teamSelect.children.length === 0) {
    teams.forEach(t => {
      const opt = document.createElement("option");
      opt.value = t.id;
      opt.textContent = t.name;
      teamSelect.appendChild(opt);
    });
  }

  const selectedTeamId = parseInt(teamSelect.value || teams[0].id);

  try {
    const res = await fetch(`/api/teams/${selectedTeamId}/charts-data`);
    const data = await res.json();
    renderCharts(data);
  } catch (err) {
    console.error("Erreur chargement graphiques :", err);
  }
}

function renderCharts(data) {
  const labels = data.labels || ["J1", "J2", "J3"];
  const pts = data.points_evolution || [0, 0, 0];
  const scored = data.scored_per_day || [0, 0, 0];
  const conceded = data.conceded_per_day || [0, 0, 0];
  const form = data.form || [];

  // 1. Line Chart: Points Evolution
  const ctxPts = document.getElementById("canvasChartPoints");
  if (ctxPts && window.Chart) {
    if (pointsChartInstance) pointsChartInstance.destroy();
    pointsChartInstance = new Chart(ctxPts, {
      type: "line",
      data: {
        labels: labels,
        datasets: [{
          label: "Points Cumulés",
          data: pts,
          borderColor: "#3b82f6",
          backgroundColor: "rgba(59, 130, 246, 0.15)",
          borderWidth: 3
        }]
      }
    });
  }

  // 2. Bar Chart: Scored vs Conceded
  const ctxGoals = document.getElementById("canvasChartGoals");
  if (ctxGoals && window.Chart) {
    if (goalsChartInstance) goalsChartInstance.destroy();
    goalsChartInstance = new Chart(ctxGoals, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Marqués (+)",
            data: scored,
            backgroundColor: "#16a34a"
          },
          {
            label: "Encaissés (-)",
            data: conceded,
            backgroundColor: "#dc2626"
          }
        ]
      }
    });
  }

  // 3. Form Badges
  const formContainer = document.getElementById("chartFormBadgesContainer");
  const formDetails = document.getElementById("chartFormDetails");
  if (formContainer) {
    if (form.length === 0) {
      formContainer.innerHTML = `<span style="color: var(--text-muted); font-size: 0.85rem;">Aucun match terminé</span>`;
      formDetails.innerHTML = "";
    } else {
      formContainer.innerHTML = form.map(f => `
        <span class="form-badge ${f.outcome.toLowerCase()}" title="${f.round}: ${f.score_text} vs ${f.opponent}">
          ${f.outcome}
        </span>
      `).join("");

      formDetails.innerHTML = form.map(f => `
        <div>• <strong>${f.round}</strong> (${f.date}) : ${f.score_text} vs ${f.opponent} [${f.outcome === 'V' ? 'Victoire' : (f.outcome === 'N' ? 'Nul' : 'Défaite')}]</div>
      `).join("");
    }
  }
}

// ---------------- TAB 5: STATS & MVPS ----------------
function renderStats() {
  const leaders = currentTournamentData.leaders || {};
  const scorers = leaders.scorers || [];
  const mvps = leaders.mvps || [];

  const tbodyScorers = document.getElementById("tableBodyScorers");
  tbodyScorers.innerHTML = "";
  scorers.slice(0, 10).forEach(sc => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 800;">#${sc.rank}</td>
      <td><strong>${sc.player_name}</strong> <small>(#${sc.player_number})</small></td>
      <td style="color: var(--text-muted);">${sc.team_name}</td>
      <td style="text-align: right; font-weight: 900; color: var(--primary);">${sc.total}</td>
    `;
    tbodyScorers.appendChild(tr);
  });

  const tbodyMvps = document.getElementById("tableBodyMvps");
  tbodyMvps.innerHTML = "";
  mvps.slice(0, 10).forEach(m => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td style="font-weight: 800;">#${m.rank}</td>
      <td><strong>${m.player_name}</strong></td>
      <td style="text-align: right; font-weight: 900; color: #f59e0b;">⭐ ${m.total}</td>
    `;
    tbodyMvps.appendChild(tr);
  });
}

// ---------------- TAB 6: F3.3 FAIR-PLAY ----------------
function renderFairPlay() {
  const fpList = currentTournamentData.fair_play || [];
  const thead = document.getElementById("tableHeadFairPlay");
  const tbody = document.getElementById("tableBodyFairPlay");
  tbody.innerHTML = "";

  const sport = (currentTournamentData.tournament && currentTournamentData.tournament.sport) ? currentTournamentData.tournament.sport.toLowerCase() : "football";
  const isBasketball = sport === "basketball";
  const isHandball = sport === "handball";

  if (thead) {
    if (isBasketball) {
      thead.innerHTML = `
        <tr>
          <th style="width: 60px;">Rang</th>
          <th>Équipe</th>
          <th>Fautes Perso. (0.5 pt)</th>
          <th>Fautes Techniques (2 pts)</th>
          <th>Antisportives / Disq. (3 pts)</th>
          <th style="text-align: right; font-weight: 800;">Points de Pénalité</th>
        </tr>
      `;
    } else if (isHandball) {
      thead.innerHTML = `
        <tr>
          <th style="width: 60px;">Rang</th>
          <th>Équipe</th>
          <th>Avertissements (1 pt)</th>
          <th>Exclusions 2 min (2 pts)</th>
          <th>Disqualifications (3 pts)</th>
          <th style="text-align: right; font-weight: 800;">Points de Pénalité</th>
        </tr>
      `;
    } else {
      thead.innerHTML = `
        <tr>
          <th style="width: 60px;">Rang</th>
          <th>Équipe</th>
          <th>Cartons Jaunes (1 pt)</th>
          <th>Cartons Rouges (3 pts)</th>
          <th style="text-align: right; font-weight: 800;">Points de Pénalité</th>
        </tr>
      `;
    }
  }

  // Update modalFairPlay labels contextually
  const lblYellow = document.getElementById("labelFpYellow");
  const lblRed = document.getElementById("labelFpRed");
  const lblSusp = document.getElementById("labelFpSuspension");
  const lblFoul = document.getElementById("labelFpFoul");

  if (lblYellow && lblRed && lblSusp && lblFoul) {
    if (isBasketball) {
      lblYellow.textContent = "Points Faute Personnelle :";
      lblSusp.textContent = "Points Faute Technique :";
      lblRed.textContent = "Points Faute Antisportive :";
      lblFoul.textContent = "Points Faute Disqualifiante :";
    } else if (isHandball) {
      lblYellow.textContent = "Points Avertissement (Jaune) :";
      lblSusp.textContent = "Points Exclusion 2 min :";
      lblRed.textContent = "Points Disqualification (Rouge) :";
      lblFoul.textContent = "Points Faute Ordinaire :";
    } else {
      lblYellow.textContent = "Points Carton Jaune :";
      lblRed.textContent = "Points Carton Rouge :";
      lblSusp.textContent = "Points Suspension 2 min :";
      lblFoul.textContent = "Points Faute Ordinaire :";
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
      <td style="font-weight: 800; color: ${fp.rank === 1 ? '#16a34a' : 'inherit'};">#${fp.rank}</td>
      <td>
        <div style="display: flex; align-items: center; gap: 0.5rem;">
          <div style="width: 12px; height: 12px; border-radius: 3px; background: ${fp.color};"></div>
          <strong>${fp.name}</strong>
          <small style="color: var(--text-muted);">(${fp.filiere})</small>
        </div>
      </td>
      ${statsCols}
      <td style="text-align: right; font-weight: 900; color: ${fp.penalty_points === 0 ? '#16a34a' : '#ea580c'};">
        ${fp.penalty_points} pts
      </td>
    `;
    tbody.appendChild(tr);
  });
}

// ---------------- TAB 7: F3.2 HEAD-TO-HEAD COMPARATOR ----------------
function prepareHeadToHeadSelectors() {
  const teams = currentTournamentData.teams || [];
  const s1 = document.getElementById("h2hSelectTeam1");
  const s2 = document.getElementById("h2hSelectTeam2");
  if (!s1 || !s2) return;

  s1.innerHTML = "";
  s2.innerHTML = "";

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

async function loadHeadToHeadComparison() {
  const t1 = parseInt(document.getElementById("h2hSelectTeam1").value);
  const t2 = parseInt(document.getElementById("h2hSelectTeam2").value);

  if (t1 === t2) {
    showToast("Veuillez sélectionner deux équipes différentes", "error");
    return;
  }

  try {
    const res = await fetch(`/api/head-to-head?team1=${t1}&team2=${t2}`);
    const data = await res.json();

    document.getElementById("h2hResultsContainer").style.display = "block";
    document.getElementById("h2hTeam1Name").textContent = data.team1.name;
    document.getElementById("h2hTeam2Name").textContent = data.team2.name;
    document.getElementById("h2hTeam1Wins").textContent = data.team1_wins;
    document.getElementById("h2hTeam2Wins").textContent = data.team2_wins;
    document.getElementById("h2hDrawsCount").textContent = `${data.draws} nuls`;
    document.getElementById("h2hTotalMatches").textContent = data.total_matches;
    document.getElementById("h2hTeam1Scored").textContent = `${data.team1_scored} buts/pts`;
    document.getElementById("h2hTeam2Scored").textContent = `${data.team2_scored} buts/pts`;

    const tbody = document.getElementById("tableBodyH2HMatches");
    tbody.innerHTML = "";

    if (data.matches.length === 0) {
      tbody.innerHTML = `<tr><td colspan="6" style="text-align: center; color: var(--text-muted); padding: 1.5rem;">Aucune rencontre historique enregistrée entre ces deux équipes.</td></tr>`;
      return;
    }

    data.matches.forEach(m => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${m.match_date || '--'}</td>
        <td>${m.tournament_name || 'Coupe Scolaire'}</td>
        <td>${m.round_name}</td>
        <td><strong>${m.team_home_name}</strong> vs <strong>${m.team_away_name}</strong></td>
        <td style="font-weight: 800;">${m.score_home} - ${m.score_away}</td>
        <td>${m.winner_id === t1 ? data.team1.name : (m.winner_id === t2 ? data.team2.name : 'Match Nul')}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast("Erreur lors de la comparaison Face-à-Face", "error");
  }
}

// ---------------- TAB 8: F4.1 PREDICTIONS ----------------
async function loadPredictionsTab() {
  if (!currentTournamentId) return;
  try {
    const res = await fetch(`/api/predictions?tournament_id=${currentTournamentId}`);
    const data = await res.json();

    const tbodyStudents = document.getElementById("tableBodyPredStudents");
    tbodyStudents.innerHTML = "";
    (data.students || []).forEach(st => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 800;">#${st.rank}</td>
        <td><strong>${st.student_name}</strong></td>
        <td style="color: var(--text-muted);">${st.student_school}</td>
        <td>${st.exact_scores}</td>
        <td style="text-align: right; font-weight: 900; color: #16a34a;">${st.total_points} pts</td>
      `;
      tbodyStudents.appendChild(tr);
    });

    const tbodySchools = document.getElementById("tableBodyPredSchools");
    tbodySchools.innerHTML = "";
    (data.schools || []).forEach(sc => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-weight: 800;">#${sc.rank}</td>
        <td><strong>${sc.student_school}</strong></td>
        <td>${sc.predictors_count}</td>
        <td>${sc.avg_points} pts/él.</td>
        <td style="text-align: right; font-weight: 900; color: var(--primary);">${sc.total_points} pts</td>
      `;
      tbodySchools.appendChild(tr);
    });

    // Populate Match select in modal
    const predMatchSelect = document.getElementById("predMatchSelect");
    if (predMatchSelect) {
      predMatchSelect.innerHTML = "";
      const matches = (currentTournamentData.matches || []).filter(m => m.status !== "finished");
      matches.forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.round_name} : ${m.team_home_name} vs ${m.team_away_name} (${m.match_date})`;
        predMatchSelect.appendChild(opt);
      });
      if (matches.length > 0) updatePredLabels(matches[0]);
      predMatchSelect.onchange = () => {
        const selM = matches.find(m => m.id === parseInt(predMatchSelect.value));
        if (selM) updatePredLabels(selM);
      };
    }
  } catch (err) {
    console.error("Erreur pronostics :", err);
  }
}

function updatePredLabels(m) {
  document.getElementById("predHomeTeamLabel").textContent = m.team_home_name;
  document.getElementById("predAwayTeamLabel").textContent = m.team_away_name;
}

// ---------------- TAB 9: F4.3 JOURNALISM ----------------
async function loadJournalismTab() {
  if (!currentTournamentId) return;
  try {
    const res = await fetch(`/api/match-reports`);
    const reports = await res.json();
    const container = document.getElementById("journalismArticlesList");
    container.innerHTML = "";

    if (reports.length === 0) {
      container.innerHTML = `<div style="text-align: center; color: var(--text-muted); padding: 2rem;">Aucun compte rendu soumis pour le moment.</div>`;
      return;
    }

    reports.forEach(r => {
      const card = document.createElement("div");
      card.className = "card";
      card.style.borderLeft = `4px solid ${r.status === 'approved' ? '#16a34a' : (r.status === 'rejected' ? '#dc2626' : '#f59e0b')}`;

      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <span style="font-size: 0.85rem; color: var(--text-muted);">
            Match : <strong>${r.team_home_name} vs ${r.team_away_name}</strong> (${r.round_name} - ${r.match_date})
          </span>
          <span class="status-pill status-${r.status}">${r.status}</span>
        </div>
        <h3 style="font-size: 1.15rem; font-weight: 800; margin-bottom: 0.4rem;">${r.title}</h3>
        <p style="font-size: 0.9rem; line-height: 1.5; color: var(--text-main); margin-bottom: 0.75rem;">${r.content}</p>
        <div style="display: flex; justify-content: space-between; align-items: center; font-size: 0.8rem; color: var(--text-muted);">
          <span>Par <strong>${r.author_name}</strong> (${r.author_school || 'Club Média'})</span>
          ${r.status === 'pending' ? `
            <div style="display: flex; gap: 0.5rem;">
              <button class="btn btn-sm btn-success" onclick="reviewReport(${r.id}, 'approved')">✅ Approuver</button>
              <button class="btn btn-sm btn-danger" onclick="reviewReport(${r.id}, 'rejected')">❌ Rejeter</button>
            </div>
          ` : `<span>Validé par : ${r.reviewed_by || 'Admin'}</span>`}
        </div>
      `;
      container.appendChild(card);
    });

    // Populate article match select
    const matchSelect = document.getElementById("articleMatchSelect");
    if (matchSelect) {
      matchSelect.innerHTML = "";
      (currentTournamentData.matches || []).forEach(m => {
        const opt = document.createElement("option");
        opt.value = m.id;
        opt.textContent = `${m.round_name} : ${m.team_home_name} vs ${m.team_away_name}`;
        matchSelect.appendChild(opt);
      });
    }
  } catch (err) {
    console.error("Erreur journalisme :", err);
  }
}

async function reviewReport(reportId, status) {
  try {
    const res = await fetch(`/api/match-reports/${reportId}/review`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status, reviewer_name: "Responsable Média" })
    });
    if (res.ok) {
      loadJournalismTab();
      showToast(`Article ${status === 'approved' ? 'approuvé' : 'rejeté'} !`);
    }
  } catch (err) {
    showToast("Erreur modération", "error");
  }
}

// ---------------- TAB 10: F5.1 SCHEDULER OPTIMIZER ----------------
function renderSchedulerPreview(data) {
  document.getElementById("schedulerEmptyPlaceholder").style.display = "none";
  document.getElementById("schedulerPreviewContainer").style.display = "block";
  document.getElementById("schedSummaryTitle").textContent = `${data.total_matches} matchs générés (${data.total_rounds} journées)`;
  document.getElementById("schedSummarySub").textContent = `Du ${data.start_date} au ${data.end_date} • Repos garanti : ${data.min_rest_days} jours • 0 conflit`;

  const tbody = document.getElementById("tableBodySchedPreview");
  tbody.innerHTML = "";

  (data.schedule || []).forEach(m => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td><strong>${m.round_name}</strong></td>
      <td>${m.match_date}</td>
      <td>${m.match_time}</td>
      <td>${m.venue}</td>
      <td><strong>${m.team_home_name}</strong> vs <strong>${m.team_away_name}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

async function commitGeneratedSchedule() {
  if (!currentTournamentId || !pendingGeneratedSchedule) return;

  try {
    const res = await fetch(`/api/tournament/${currentTournamentId}/generate-schedule`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        commit: true,
        venues: ["Terrain Principal", "Gymnase Central"],
        start_date: pendingGeneratedSchedule[0].match_date
      })
    });
    const data = await res.json();
    if (data.created_count) {
      document.getElementById("schedulerPreviewContainer").style.display = "none";
      document.getElementById("schedulerEmptyPlaceholder").style.display = "block";
      pendingGeneratedSchedule = null;
      await loadTournamentFull();
      showToast(`Calendrier publié avec succès (${data.created_count} rencontres enregistrées) !`);
    }
  } catch (err) {
    showToast("Erreur lors de la publication du calendrier", "error");
  }
}

// ---------------- TAB 11: F5.2 CSV IMPORTER & F5.4 BACKUPS & F6.5 AUDIT ----------------
async function loadAdminToolsData() {
  await loadAnalytics();
  await loadBackupsList();
  await loadAuditLogs();
}

async function loadAnalytics() {
  try {
    const res = await fetch("/api/analytics");
    if (res.ok) {
      const stats = await res.json();
      document.getElementById("statTodayUniques").textContent = stats.today_uniques;
      document.getElementById("statTodayTotal").textContent = stats.today_total;
      document.getElementById("statAllTime").textContent = stats.all_time;
    }
  } catch (e) {
    console.warn("Analytics load error", e);
  }
}

async function loadBackupsList() {
  try {
    const res = await fetch("/api/backups");
    const backups = await res.json();
    const container = document.getElementById("backupsListContainer");
    container.innerHTML = "";

    if (backups.length === 0) {
      container.innerHTML = `<span style="color: var(--text-muted);">Aucune sauvegarde</span>`;
      return;
    }

    backups.forEach(b => {
      const item = document.createElement("div");
      item.style.display = "flex";
      item.style.justifyContent = "space-between";
      item.style.alignItems = "center";
      item.style.padding = "0.25rem 0";
      item.style.borderBottom = "1px solid var(--border)";

      item.innerHTML = `
        <div>
          <strong>${b.filename}</strong>
          <small style="color: var(--text-muted); display: block;">${b.created_at} (${b.size_kb} KB)</small>
        </div>
        <button class="btn btn-secondary btn-sm" onclick="restoreBackup('${b.filename}')">Restaurer</button>
      `;
      container.appendChild(item);
    });
  } catch (e) {
    console.warn("Backups load error", e);
  }
}

async function createBackupNow() {
  try {
    const res = await fetch("/api/backups/create", { method: "POST" });
    const data = await res.json();
    if (data.status === "ok") {
      await loadBackupsList();
      showToast("Nouvelle sauvegarde créée avec succès !");
    }
  } catch (e) {
    showToast("Erreur création sauvegarde", "error");
  }
}

async function restoreBackup(filename) {
  if (!confirm(`ATTENTION : Restaurer la base de données depuis ${filename} ? Vos modifications récentes seront remplacées par cette archive.`)) return;
  try {
    const res = await fetch("/api/backups/restore", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename })
    });
    const data = await res.json();
    if (data.status === "ok") {
      await loadTournaments();
      showToast(data.message);
    } else {
      showToast(data.error || "Erreur restauration", "error");
    }
  } catch (e) {
    showToast("Erreur restauration", "error");
  }
}

async function loadAuditLogs() {
  try {
    const res = await fetch("/api/audit-logs?limit=50");
    const logs = await res.json();
    const tbody = document.getElementById("tableBodyAuditLogs");
    tbody.innerHTML = "";

    logs.forEach(l => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td style="font-size: 0.8rem; color: var(--text-muted);">${l.timestamp}</td>
        <td><strong>${l.author_name}</strong> <small>(${l.author_role})</small></td>
        <td><span class="status-pill status-approved">${l.action_type}</span></td>
        <td>${l.entity_type} #${l.entity_id || '-'}</td>
        <td style="color: #dc2626; font-size: 0.8rem;">${l.old_value || '-'}</td>
        <td style="color: #16a34a; font-weight: 700; font-size: 0.8rem;">${l.new_value || '-'}</td>
        <td style="font-size: 0.8rem; color: var(--text-muted);">${l.details || ''}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (e) {
    console.warn("Audit logs error", e);
  }
}

// ---------------- CSV IMPORTER PREVIEW & COMMIT (F5.2) ----------------
async function previewCsvFile() {
  const fileInput = document.getElementById("csvFileInput");
  if (!fileInput.files[0] || !currentTournamentId) {
    showToast("Veuillez sélectionner un fichier CSV", "error");
    return;
  }

  const reader = new FileReader();
  reader.onload = async () => {
    try {
      const res = await fetch(`/api/tournament/${currentTournamentId}/import-csv`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ csv_text: reader.result, dry_run: true })
      });
      const data = await res.json();

      if (data.success) {
        pendingCsvParsedData = reader.result;
        document.getElementById("csvReportWrapper").style.display = "block";
        document.getElementById("csvSummaryBanner").innerHTML = `
          Résultat de l'analyse : <span style="color: #16a34a;">${data.accepted_count} lignes acceptées</span>,
          <span style="color: #dc2626;">${data.rejected_count} lignes rejetées</span>.
        `;

        const reportBox = document.getElementById("csvReportBox");
        reportBox.innerHTML = (data.report || []).map(r => `
          <div class="${r.status === 'accepted' ? 'import-line-accepted' : 'import-line-rejected'}">
            Ligne ${r.line} [${r.status.toUpperCase()}] : ${r.reason || r.details}
          </div>
        `).join("");
      } else {
        showToast(data.error || "Erreur de format CSV", "error");
      }
    } catch (e) {
      showToast("Erreur lors de l'analyse du CSV", "error");
    }
  };
  reader.readAsText(fileInput.files[0], "utf-8");
}

async function commitCsvImport() {
  if (!currentTournamentId || !pendingCsvParsedData) return;

  try {
    const res = await fetch(`/api/tournament/${currentTournamentId}/import-csv`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ csv_text: pendingCsvParsedData, dry_run: false })
    });
    const data = await res.json();
    if (data.committed) {
      closeModal("modalImportCsv");
      pendingCsvParsedData = null;
      await loadTournamentFull();
      showToast(`Importation réussie : ${data.committed.created_teams} équipes et ${data.committed.created_players} joueurs ajoutés !`);
    }
  } catch (e) {
    showToast("Erreur enregistrement CSV", "error");
  }
}

// ---------------- TAB 12: HIGHLIGHTS ----------------
async function loadHighlights() {
  if (!currentTournamentId) return;
  try {
    const res = await fetch(`/api/highlights?tournament_id=${currentTournamentId}`);
    const highlights = await res.json();
    const container = document.getElementById("adminHighlightsList");
    container.innerHTML = "";

    highlights.forEach(h => {
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.5rem;">
          <span class="badge-chip" style="background: #ea580c;">${h.action_type.toUpperCase()}</span>
          <button class="btn btn-secondary btn-sm" style="color: #dc2626;" onclick="deleteHighlight(${h.id})">🗑️</button>
        </div>
        <h4 style="font-weight: 800; font-size: 1.05rem; margin-bottom: 0.35rem;">${h.title}</h4>
        <p style="font-size: 0.85rem; color: var(--text-muted); margin-bottom: 0.5rem;">${h.description}</p>
        <div style="font-size: 0.8rem; color: var(--primary); font-weight: 700;">❤️ ${h.likes_count} mentions J'aime</div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    console.warn("Highlights error", e);
  }
}

async function deleteHighlight(hlId) {
  if (!confirm("Supprimer cette action ?")) return;
  try {
    const res = await fetch(`/api/highlights/${hlId}`, { method: "DELETE" });
    if (res.ok) {
      loadHighlights();
      showToast("Action supprimée");
    }
  } catch (e) {
    showToast("Erreur suppression", "error");
  }
}

// ---------------- TAB 13: SHARE & WHATSAPP ----------------
function renderShareInfo() {
  const t = currentTournamentData.tournament;
  const link = getPublicTournamentUrl(t.id);
  document.getElementById("shareLinkInput").value = link;
}

function copyPublicLink() {
  const input = document.getElementById("shareLinkInput");
  input.select();
  document.execCommand("copy");
  showToast("Lien public copié dans le presse-papiers !");
}

function generateWhatsAppRecap() {
  const t = currentTournamentData.tournament;
  const standings = currentTournamentData.standings || [];
  const matches = currentTournamentData.matches || [];

  let msg = `🏆 *${t.name.toUpperCase()}* (${t.year})\n`;
  msg += `📍 Institut Universitaire Saint Jérôme de Douala\n\n`;

  msg += `📊 *CLASSEMENT OFFICIEL :*\n`;
  standings.forEach(s => {
    msg += `#${s.rank} ${s.name} — *${s.points} pts* (${s.played}J, ${s.won}V, diff: ${s.diff > 0 ? '+' : ''}${s.diff})\n`;
  });

  const finished = matches.filter(m => m.status === "finished");
  if (finished.length > 0) {
    msg += `\n⚽ *DERNIERS RÉSULTATS :*\n`;
    finished.slice(-4).forEach(m => {
      msg += `• ${m.team_home_name} ${m.score_home} - ${m.score_away} ${m.team_away_name}`;
      if (m.mvp_name) msg += ` (⭐ MVP: ${m.mvp_name})`;
      msg += `\n`;
    });
  }

  msg += `\n🔗 *Suivre les scores, pronostics et directs :*\n${getPublicTournamentUrl(t.id)}\n`;

  navigator.clipboard.writeText(msg).then(() => {
    showToast("Résumé WhatsApp copié ! Collez-le dans vos groupes WhatsApp.");
  });
}

function populateSelects() {
  const teams = currentTournamentData.teams || [];
  const homeSelect = document.getElementById("matchHomeTeam");
  const awaySelect = document.getElementById("matchAwayTeam");

  if (homeSelect && awaySelect) {
    homeSelect.innerHTML = "";
    awaySelect.innerHTML = "";
    teams.forEach((t, idx) => {
      const o1 = document.createElement("option");
      o1.value = t.id;
      o1.textContent = t.name;
      homeSelect.appendChild(o1);

      const o2 = document.createElement("option");
      o2.value = t.id;
      o2.textContent = t.name;
      if (idx === 1) o2.selected = true;
      awaySelect.appendChild(o2);
    });
  }

  // Populate Fair-Play rules modal inputs
  const fpRules = currentTournamentData.fair_play_rules || {};
  if (document.getElementById("fpYellowPts")) {
    document.getElementById("fpYellowPts").value = fpRules.yellow_card_points || 1.0;
    document.getElementById("fpRedPts").value = fpRules.red_card_points || 3.0;
    document.getElementById("fpSuspensionPts").value = fpRules.suspension_points || 2.0;
    document.getElementById("fpFoulPts").value = fpRules.foul_points || 0.5;
  }
}

// ---------------- Toast & Modal Helpers ----------------
function openModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.add("active");
}

function closeModal(id) {
  const m = document.getElementById(id);
  if (m) m.classList.remove("active");
}

function showToast(message, type = "success") {
  const container = document.getElementById("toastContainer");
  if (!container) return;
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.style.background = type === "error" ? "#dc2626" : "#16a34a";
  toast.style.color = "#ffffff";
  toast.style.padding = "0.75rem 1.25rem";
  toast.style.borderRadius = "8px";
  toast.style.boxShadow = "0 4px 6px rgba(0,0,0,0.15)";
  toast.style.marginBottom = "0.5rem";
  toast.textContent = message;
  container.appendChild(toast);
  setTimeout(() => toast.remove(), 4000);
}
