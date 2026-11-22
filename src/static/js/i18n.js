/**
 * Internationalization (FR / EN) & Dark Mode Controller (F6.1 & F6.2)
 * Persists preferences in localStorage and auto-detects system dark mode.
 */

const I18N_DICTIONARY = {
  fr: {
    // Header & Global
    "app_title": "Gestionnaire de Tournois Sportifs",
    "school_name": "Institut Universitaire Saint Jérôme",
    "btn_new_tournament": "➕ Nouveau Tournoi",
    "btn_public_portal": "📱 Portail Spectateur (Public)",
    "public_title": "Tournois Sportifs — Direct & Résultats",
    "btn_share": "🔗 Partager",
    "btn_print": "🖨️ Imprimer",
    "btn_copy": "📋 Copier",
    "btn_close": "Fermer",
    "btn_save": "Enregistrer",
    "btn_cancel": "Annuler",
    "loading": "Chargement en cours...",
    "no_data": "Aucune donnée disponible",

    // Tabs
    "tab_standings": "🏆 Classement",
    "tab_matches": "📅 Rencontres",
    "tab_teams": "👥 Équipes & Joueurs",
    "tab_stats": "📊 Statistiques & MVPs",
    "tab_awards": "🌟 Joueur de la Semaine",
    "tab_highlights": "⚡ Belles Actions",
    "tab_fairplay": "🤝 Fair-Play",
    "tab_h2h": "⚔️ Face-à-Face",
    "tab_predictions": "🎯 Pronostics",
    "tab_journalism": "📰 Journalisme",
    "tab_scheduler": "🗓️ Calendrier Optimisé",
    "tab_admin_tools": "⚙️ Sauvegardes & Audit",
    "tab_share": "🔗 Partage & Liens",

    // Table Columns
    "col_rank": "Rang",
    "col_team": "Équipe",
    "col_pts": "Pts",
    "col_played": "J",
    "col_won": "V",
    "col_drawn": "N",
    "col_lost": "D",
    "col_scored": "BP / Pts+",
    "col_conceded": "BC / Pts-",
    "col_diff": "Diff",
    "col_actions": "Actions",

    // Match status
    "status_scheduled": "À venir",
    "status_finished": "Terminé",
    "btn_sheet": "📄 Feuille A4",
    "btn_enter_score": "Saisir le score",
    "btn_vote_mvp": "⭐ Voter MVP",

    // Fair Play
    "fp_title": "🤝 Classement du Fair-Play",
    "fp_subtitle": "L'équipe avec le moins de points de pénalité est première au classement.",
    "col_yellow": "Cartons Jaunes (1 pt)",
    "col_red": "Cartons Rouges (3 pts)",
    "col_penalty_pts": "Points de pénalité",

    // Predictions
    "pred_title": "🎯 Jeu de Pronostics des Élèves",
    "pred_subtitle": "Pronostiquez les scores avant le coup d'envoi ! (3 pts score exact, 1 pt bonne issue)",
    "pred_name_label": "Votre Nom / Pseudo d'élève :",
    "pred_school_label": "Votre Filière / Établissement :",
    "btn_submit_pred": "Valider mon pronostic",
    "pred_rank_students": "Classement Général des Élèves",
    "pred_rank_schools": "Classement par Établissement",

    // H2H
    "h2h_title": "⚔️ Historique des Confrontations Directes",
    "h2h_select_help": "Sélectionnez deux équipes pour comparer leur palmarès et historique :",
    "h2h_matches_count": "Confrontations Directes",
    "h2h_wins": "Victoires",
    "h2h_draws": "Matchs Nuls",

    // Scheduler
    "sched_title": "🗓️ Optimisation et Génération du Calendrier (F5.1)",
    "sched_btn_generate": "⚡ Générer & Optimiser le Calendrier",
    "sched_venues_label": "Terrains disponibles (séparés par virgule) :",
    "sched_rest_label": "Repos minimal entre 2 matchs d'une équipe :",
    "sched_exam_label": "Jours d'examens exclus (séparés par virgule, ex: 2026-11-20) :",

    // Theme & Lang
    "theme_dark": "Mode Sombre",
    "theme_light": "Mode Clair"
  },

  en: {
    // Header & Global
    "app_title": "Sports Tournament Manager",
    "school_name": "Saint Jerome University Institute",
    "btn_new_tournament": "➕ New Tournament",
    "btn_public_portal": "📱 Spectator Portal (Public)",
    "public_title": "Sports Tournaments — Live & Results",
    "btn_share": "🔗 Share",
    "btn_print": "🖨️ Print",
    "btn_copy": "📋 Copy",
    "btn_close": "Close",
    "btn_save": "Save",
    "btn_cancel": "Cancel",
    "loading": "Loading in progress...",
    "no_data": "No data available",

    // Tabs
    "tab_standings": "🏆 Standings",
    "tab_matches": "📅 Fixtures",
    "tab_teams": "👥 Teams & Rosters",
    "tab_stats": "📊 Statistics & MVPs",
    "tab_awards": "🌟 Player of the Week",
    "tab_highlights": "⚡ Highlights",
    "tab_fairplay": "🤝 Fair-Play",
    "tab_h2h": "⚔️ Head-to-Head",
    "tab_predictions": "🎯 Predictions",
    "tab_journalism": "📰 News & Reports",
    "tab_scheduler": "🗓️ Calendar Optimizer",
    "tab_admin_tools": "⚙️ Backups & Audit",
    "tab_share": "🔗 Share & Links",

    // Table Columns
    "col_rank": "Rank",
    "col_team": "Team",
    "col_pts": "Pts",
    "col_played": "P",
    "col_won": "W",
    "col_drawn": "D",
    "col_lost": "L",
    "col_scored": "GF / Pts+",
    "col_conceded": "GA / Pts-",
    "col_diff": "Diff",
    "col_actions": "Actions",

    // Match status
    "status_scheduled": "Upcoming",
    "status_finished": "Finished",
    "btn_sheet": "📄 Match Sheet",
    "btn_enter_score": "Enter Score",
    "btn_vote_mvp": "⭐ Vote MVP",

    // Fair Play
    "fp_title": "🤝 Fair-Play Standings",
    "fp_subtitle": "The team with the fewest penalty points ranks 1st.",
    "col_yellow": "Yellow Cards (1 pt)",
    "col_red": "Red Cards (3 pts)",
    "col_penalty_pts": "Penalty Points",

    // Predictions
    "pred_title": "🎯 Student Predictions Game",
    "pred_subtitle": "Predict scores before kickoff! (3 pts exact score, 1 pt right outcome)",
    "pred_name_label": "Student Name / Nickname:",
    "pred_school_label": "School / Department:",
    "btn_submit_pred": "Submit Prediction",
    "pred_rank_students": "Overall Student Leaderboard",
    "pred_rank_schools": "School Leaderboard",

    // H2H
    "h2h_title": "⚔️ Head-to-Head Comparison",
    "h2h_select_help": "Select two teams to compare their history and statistics:",
    "h2h_matches_count": "Direct Encounters",
    "h2h_wins": "Wins",
    "h2h_draws": "Draws",

    // Scheduler
    "sched_title": "🗓️ Tournament Schedule Optimizer (F5.1)",
    "sched_btn_generate": "⚡ Generate & Optimize Schedule",
    "sched_venues_label": "Available venues (comma separated):",
    "sched_rest_label": "Minimum rest days between matches:",
    "sched_exam_label": "Excluded exam dates (e.g. 2026-11-20):",

    // Theme & Lang
    "theme_dark": "Dark Mode",
    "theme_light": "Light Mode"
  }
};

let currentLang = localStorage.getItem("app_lang") || "fr";

function t(key) {
  const dict = I18N_DICTIONARY[currentLang] || I18N_DICTIONARY.fr;
  return dict[key] || key;
}

function setLanguage(lang) {
  if (lang !== "fr" && lang !== "en") lang = "fr";
  currentLang = lang;
  localStorage.setItem("app_lang", lang);
  applyTranslations();
  const btn = document.getElementById("btnLangToggle");
  if (btn) {
    btn.textContent = lang === "fr" ? "🇬🇧 EN" : "🇫🇷 FR";
    btn.title = lang === "fr" ? "Switch to English" : "Passer en Français";
  }
}

function toggleLanguage() {
  setLanguage(currentLang === "fr" ? "en" : "fr");
}

function applyTranslations() {
  document.querySelectorAll("[data-i18n]").forEach(el => {
    const key = el.getAttribute("data-i18n");
    const val = t(key);
    if (val) {
      if (el.tagName === "INPUT" && (el.type === "button" || el.type === "submit")) {
        el.value = val;
      } else {
        el.textContent = val;
      }
    }
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach(el => {
    const key = el.getAttribute("data-i18n-placeholder");
    const val = t(key);
    if (val) el.placeholder = val;
  });
}

// ---------------- F6.1: DARK MODE CONTROLLER ----------------
function initTheme() {
  const saved = localStorage.getItem("app_theme") || "light";
  setTheme(saved);
}

function setTheme(theme) {
  if (theme === "dark") {
    document.documentElement.setAttribute("data-theme", "dark");
    localStorage.setItem("app_theme", "dark");
  } else {
    document.documentElement.setAttribute("data-theme", "light");
    localStorage.setItem("app_theme", "light");
  }
  const btn = document.getElementById("btnThemeToggle");
  if (btn) {
    btn.textContent = theme === "dark" ? "☀️" : "🌙";
    btn.title = theme === "dark" ? "Mode Clair" : "Mode Sombre";
  }
}

function toggleTheme() {
  const isDark = document.documentElement.getAttribute("data-theme") === "dark";
  setTheme(isDark ? "light" : "dark");
}

document.addEventListener("DOMContentLoaded", () => {
  initTheme();
  setLanguage(currentLang);
});
