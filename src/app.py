"""
Backend HTTP Server and REST API for Sports Tournament Manager.
Built using standard library http.server for 100% reliable, zero-dependency offline execution.
Implements all 18 features from the specifications:
- F3.1: Team charts data (Points evolution, goals, form)
- F3.2: Head-to-Head confrontation history
- F3.3: Fair-play rules & standings
- F3.4: Rate-limited JSON API & Minor-safe CSV exports
- F4.1: Predictions game & leaderboards
- F4.2: Fan MVP vote with IP/device rate-limiting
- F4.3: School journalism match reports with moderation
- F4.4: Automatic team badges
- F5.1: Calendar generation and optimization
- F5.2: CSV import with validation report and dry-run
- F5.3: Official A4 printable match sheet
- F5.4: Automatic database backups (14 latest retention)
- F6.4: Privacy-friendly analytics
- F6.5: Immutable audit logs
"""

import os
import sys
import json
import time
import base64
import socket
import csv
import io
import urllib.parse
import secrets
from http.server import HTTPServer, SimpleHTTPRequestHandler
from typing import Dict, Any, List, Optional

from database import Database
from sports_engine import SportsEngine
from scheduler import TournamentScheduler
from csv_importer import CsvImporter

# Sessions Administrateur
ADMIN_SESSIONS: Dict[str, float] = {}

def generate_session_token() -> str:
    token = secrets.token_hex(24)
    ADMIN_SESSIONS[token] = time.time() + 86400 * 7  # 7 jours
    return token

def is_valid_admin_session(token: Optional[str]) -> bool:
    if not token:
        return False
    exp = ADMIN_SESSIONS.get(token)
    if not exp or time.time() > exp:
        if token in ADMIN_SESSIONS:
            del ADMIN_SESSIONS[token]
        return False
    return True

def get_local_ip() -> str:
    """Detect local Wi-Fi / Hotspot / LAN IP of this PC."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("172.20.10.1", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    try:
        ip = socket.gethostbyname(socket.gethostname())
        if ip and not ip.startswith("127."):
            return ip
    except Exception:
        pass
    return "127.0.0.1"


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA_DIR = os.path.join(BASE_DIR, "data")
UPLOADS_DIR = os.path.join(DATA_DIR, "uploads")
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(UPLOADS_DIR, exist_ok=True)

# Initialize database and seed demo data if empty
db = Database()
db.seed_initial_demo_if_empty()

# Rate limiting storage (F3.4): IP -> list of request timestamps
RATE_LIMIT_STORE: Dict[str, List[float]] = {}
MAX_REQUESTS_PER_MINUTE = 180


def check_rate_limit(client_ip: str) -> bool:
    """Returns True if within rate limit, False if exceeded."""
    now = time.time()
    timestamps = RATE_LIMIT_STORE.setdefault(client_ip, [])
    # Keep only timestamps within last 60 seconds
    timestamps = [t for t in timestamps if now - t < 60]
    RATE_LIMIT_STORE[client_ip] = timestamps
    if len(timestamps) >= MAX_REQUESTS_PER_MINUTE:
        return False
    timestamps.append(now)
    return True


class SportsAppRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=STATIC_DIR, **kwargs)

    def get_client_ip(self) -> str:
        forwarded = self.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "127.0.0.1"

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def _send_json(self, data: Any, status: int = 200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(body)

    def _send_bytes(self, data: bytes, content_type: str, filename: Optional[str] = None):
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", "*")
        if filename:
            self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
        self.end_headers()
        self.wfile.write(data)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, DELETE, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        client_ip = self.get_client_ip()

        # F3.4: Rate Limiting
        if not check_rate_limit(client_ip):
            self._send_json({"error": "Trop de requêtes. Veuillez patienter une minute (Rate Limit F3.4)."}, 429)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        # ---------------- F6.4: PRIVACY ANALYTICS TRACKING ----------------
        if not path.startswith("/api/") and not path.startswith("/uploads/"):
            user_agent = self.headers.get("User-Agent", "")
            db.record_visit(path, user_agent, client_ip)

        # ---------------- API ROUTES ----------------
        if path == "/api/auth/verify":
            token = self.headers.get("X-Admin-Token") or self.headers.get("Authorization", "").replace("Bearer ", "").strip()
            self._send_json({"authenticated": is_valid_admin_session(token)})
            return

        elif path == "/api/tournaments":
            tournaments = db.list_tournaments()
            self._send_json(tournaments)
            return

        elif path == "/api/network-info":
            ip = get_local_ip()
            self._send_json({
                "local_ip": ip,
                "port": 8080,
                "local_url": "http://127.0.0.1:8080",
                "network_url": f"http://{ip}:8080/public"
            })
            return

        elif path.startswith("/api/tournament/") and path.endswith("/full"):
            t_id = int(path.split("/")[3])
            t = db.get_tournament(t_id)
            if not t:
                self._send_json({"error": "Tournament not found"}, 404)
                return

            teams = db.list_teams(t_id)
            players = db.list_tournament_players(t_id)
            matches = db.list_matches(t_id)
            awards = db.list_weekly_awards(t_id)

            # Collect match events for all matches in tournament
            all_events = []
            for m in matches:
                evs = db.list_match_events(m["id"])
                all_events.extend(evs)

            standings = SportsEngine.calculate_standings(t["sport"], teams, matches)
            leaders = SportsEngine.calculate_leaderboards(t["sport"], all_events, matches)

            # F3.3: Fair Play Standings
            fp_rules = db.get_fair_play_rules(t_id)
            fair_play = SportsEngine.calculate_fair_play(teams, all_events, fp_rules, sport=t.get("sport", "football"))

            # F4.4: Team Badges
            for team in teams:
                team["badges"] = SportsEngine.calculate_team_badges(team["id"], standings, fair_play)

            self._send_json({
                "tournament": t,
                "teams": teams,
                "players": players,
                "matches": matches,
                "standings": standings,
                "leaders": leaders,
                "fair_play": fair_play,
                "fair_play_rules": fp_rules,
                "awards": awards
            })
            return

        elif path.startswith("/api/tournament/") and path.endswith("/standings"):
            t_id = int(path.split("/")[3])
            t = db.get_tournament(t_id)
            if not t:
                self._send_json({"error": "Tournament not found"}, 404)
                return
            teams = db.list_teams(t_id)
            matches = db.list_matches(t_id)
            standings = SportsEngine.calculate_standings(t["sport"], teams, matches)
            self._send_json(standings)
            return

        # F3.3: Fair-Play Standings
        elif path.startswith("/api/tournament/") and path.endswith("/fair-play"):
            t_id = int(path.split("/")[3])
            t = db.get_tournament(t_id)
            sport = t.get("sport", "football") if t else "football"
            teams = db.list_teams(t_id)
            matches = db.list_matches(t_id)
            all_events = []
            for m in matches:
                all_events.extend(db.list_match_events(m["id"]))
            rules = db.get_fair_play_rules(t_id)
            fp_list = SportsEngine.calculate_fair_play(teams, all_events, rules, sport=sport)
            self._send_json({"sport": sport, "rules": rules, "standings": fp_list})
            return

        # Player Details
        elif path.startswith("/api/players/"):
            p_id = int(path.split("/")[3])
            player = db.get_player(p_id)
            if not player:
                self._send_json({"error": "Player not found"}, 404)
                return
            self._send_json(player)
            return

        # F3.1: Team Charts Data (3 charts per team)
        elif path.startswith("/api/teams/") and path.endswith("/charts-data"):
            team_id = int(path.split("/")[3])
            team = db.get_team(team_id)
            if not team:
                self._send_json({"error": "Team not found"}, 404)
                return
            t_id = team["tournament_id"]
            tourn = db.get_tournament(t_id)
            sport = tourn["sport"] if tourn else "football"
            matches = db.list_matches(t_id)
            charts_data = SportsEngine.calculate_team_charts_data(team_id, matches, sport)
            self._send_json(charts_data)
            return

        # F3.2: Head-to-Head Confrontation History
        elif path == "/api/head-to-head":
            t1_id = int(query.get("team1", [0])[0])
            t2_id = int(query.get("team2", [0])[0])
            if not t1_id or not t2_id:
                self._send_json({"error": "Identifiants des deux équipes requis."}, 400)
                return

            # Gather all matches and teams across database
            all_tournaments = db.list_tournaments()
            all_matches = []
            all_teams = []
            for tr in all_tournaments:
                all_matches.extend(db.list_matches(tr["id"]))
                all_teams.extend(db.list_teams(tr["id"]))

            h2h = SportsEngine.calculate_head_to_head(t1_id, t2_id, all_matches, all_teams)
            self._send_json(h2h)
            return

        # F4.1: Predictions Leaderboard
        elif path == "/api/predictions":
            t_id = int(query.get("tournament_id", [0])[0])
            school = query.get("school", [None])[0]
            leaderboard = db.get_predictions_leaderboard(t_id, school)
            self._send_json(leaderboard)
            return

        elif path.startswith("/api/matches/") and path.endswith("/predictions"):
            m_id = int(path.split("/")[3])
            preds = db.list_match_predictions(m_id)
            self._send_json(preds)
            return

        # F4.2: Fan MVP Votes
        elif path.startswith("/api/matches/") and path.endswith("/mvp-votes"):
            m_id = int(path.split("/")[3])
            votes_data = db.get_match_mvp_votes(m_id)
            self._send_json(votes_data)
            return

        # F4.3: Match Reports
        elif path == "/api/match-reports":
            m_id = int(query.get("match_id", [0])[0]) if query.get("match_id") else None
            status = query.get("status", [None])[0]
            reports = db.list_match_reports(m_id, status)
            self._send_json(reports)
            return

        # F5.2: Download CSV Template
        elif path == "/api/templates/import-csv":
            csv_content = CsvImporter.get_template_csv()
            self._send_bytes(csv_content.encode("utf-8-sig"), "text/csv; charset=utf-8", "Modele_Import_Equipes_Joueurs.csv")
            return

        # F5.3: Official Match Sheet Data
        elif path.startswith("/api/matches/") and path.endswith("/sheet"):
            m_id = int(path.split("/")[3])
            m = db.get_match(m_id)
            if not m:
                self._send_json({"error": "Match not found"}, 404)
                return
            t = db.get_tournament(m["tournament_id"])
            home_players = db.list_players(m["team_home_id"])
            away_players = db.list_players(m["team_away_id"])
            events = db.list_match_events(m_id)
            self._send_json({
                "match": m,
                "tournament": t,
                "home_players": home_players,
                "away_players": away_players,
                "events": events
            })
            return

        # F5.4: Backups List
        elif path == "/api/backups":
            backups = db.list_backups()
            self._send_json(backups)
            return

        # F6.5: Audit Logs List
        elif path == "/api/audit-logs":
            limit = int(query.get("limit", [100])[0])
            entity = query.get("entity", [None])[0]
            logs = db.list_audit_logs(limit, entity)
            self._send_json(logs)
            return

        # F6.4: Analytics Stats
        elif path == "/api/analytics":
            stats = db.get_visit_stats()
            self._send_json(stats)
            return

        # F3.4: CSV EXPORTS (Safe for minors, sports data only)
        elif path.startswith("/api/export/"):
            t_id = int(query.get("tournament_id", [0])[0])
            t = db.get_tournament(t_id)
            if not t:
                self._send_json({"error": "Tournoi non spécifié ou introuvable"}, 400)
                return

            export_type = path.split("/")[3] # 'matches.csv', 'standings.csv', 'teams.csv', 'scorers.csv'

            out = io.StringIO()
            writer = csv.writer(out, delimiter=';')

            if export_type == "matches.csv":
                matches = db.list_matches(t_id)
                writer.writerow(["ID", "Tournoi", "Journee", "Date", "Heure", "Lieu", "Arbitre", "Equipe_Domicile", "Score_Dom", "Score_Ext", "Equipe_Exterieur", "Statut", "MVP"])
                for m in matches:
                    writer.writerow([
                        m["id"], t["name"], m["round_name"], m["match_date"], m["match_time"],
                        m["venue"], m.get("referee", ""), m["team_home_name"],
                        m["score_home"] if m["score_home"] is not None else "",
                        m["score_away"] if m["score_away"] is not None else "",
                        m["team_away_name"], m["status"], m.get("mvp_name", "")
                    ])
                self._send_bytes(out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"Matchs_{t['name']}.csv")
                return

            elif export_type == "standings.csv":
                teams = db.list_teams(t_id)
                matches = db.list_matches(t_id)
                standings = SportsEngine.calculate_standings(t["sport"], teams, matches)
                writer.writerow(["Rang", "Equipe", "Filiere", "Points", "Joues", "Victoires", "Nuls", "Defaites", "Marques", "Encaisses", "Diff"])
                for s in standings:
                    writer.writerow([
                        s["rank"], s["name"], s.get("filiere", ""), s["points"], s["played"],
                        s["won"], s["drawn"], s["lost"], s["scored"], s["conceded"], s["diff"]
                    ])
                self._send_bytes(out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"Classement_{t['name']}.csv")
                return

            elif export_type == "teams.csv":
                teams = db.list_teams(t_id)
                writer.writerow(["ID", "Equipe", "Filiere_Ecole", "Abreviation", "Couleur", "Nb_Joueurs"])
                for tm in teams:
                    writer.writerow([tm["id"], tm["name"], tm.get("filiere", ""), tm.get("short_name", ""), tm.get("color", ""), tm.get("player_count", 0)])
                self._send_bytes(out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"Equipes_{t['name']}.csv")
                return

            elif export_type == "scorers.csv":
                matches = db.list_matches(t_id)
                all_events = []
                for m in matches:
                    all_events.extend(db.list_match_events(m["id"]))
                leaders = SportsEngine.calculate_leaderboards(t["sport"], all_events, matches)
                writer.writerow(["Rang", "Nom_Sportif", "Equipe", "Numero", "Total"])
                for sc in leaders.get("scorers", []):
                    writer.writerow([sc["rank"], sc["player_name"], sc["team_name"], sc["player_number"], sc["total"]])
                self._send_bytes(out.getvalue().encode("utf-8-sig"), "text/csv; charset=utf-8", f"Buteurs_{t['name']}.csv")
                return

        elif path.startswith("/api/match/") and path.endswith("/events"):
            m_id = int(path.split("/")[3])
            events = db.list_match_events(m_id)
            self._send_json(events)
            return

        elif path == "/api/highlights":
            t_id = int(query.get("tournament_id", [0])[0])
            highlights = db.list_highlights(t_id)
            for h in highlights:
                h["comments"] = db.list_highlight_comments(h["id"])
            self._send_json(highlights)
            return

        elif path.startswith("/api/highlights/") and path.endswith("/comments"):
            h_id = int(path.split("/")[3])
            comments = db.list_highlight_comments(h_id)
            self._send_json(comments)
            return

        elif path.startswith("/uploads/"):
            filename = os.path.basename(path)
            file_path = os.path.join(UPLOADS_DIR, filename)
            if os.path.exists(file_path) and os.path.isfile(file_path):
                ext = os.path.splitext(filename)[1].lower()
                mime = {
                    ".png": "image/png",
                    ".jpg": "image/jpeg",
                    ".jpeg": "image/jpeg",
                    ".webp": "image/webp",
                    ".gif": "image/gif",
                    ".svg": "image/svg+xml",
                    ".mp4": "video/mp4",
                    ".webm": "video/webm",
                    ".mov": "video/quicktime",
                    ".m4v": "video/x-m4v"
                }.get(ext, "application/octet-stream")
                with open(file_path, "rb") as f:
                    self._send_bytes(f.read(), mime)
                return
            else:
                self.send_error(404, "File not found")
                return

        # ---------------- HTML VIEWS ----------------
        if path in ("/", "/public", "/public.html"):
            self.path = "/public.html"
        elif path in ("/admin", "/admin.html", "/index.html"):
            self.path = "/index.html"
        elif path in ("/match-sheet", "/match_sheet.html"):
            self.path = "/match_sheet.html"

        return super().do_GET()

    def do_POST(self):
        client_ip = self.get_client_ip()

        if not check_rate_limit(client_ip):
            self._send_json({"error": "Trop de requêtes. Veuillez patienter une minute (Rate Limit F3.4)."}, 429)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}

        if path == "/api/auth/login":
            username = data.get("username", "")
            password = data.get("password", "")
            if db.verify_admin(username, password):
                token = generate_session_token()
                self._send_json({"success": True, "token": token, "username": username})
            else:
                self._send_json({"success": False, "error": "Identifiant ou mot de passe incorrect."}, 401)
            return

        elif path == "/api/auth/change-password":
            token = self.headers.get("X-Admin-Token") or self.headers.get("Authorization", "").replace("Bearer ", "").strip()
            if not is_valid_admin_session(token):
                self._send_json({"success": False, "error": "Session expirée ou non autorisée."}, 401)
                return
            username = data.get("username", "admin")
            old_pw = data.get("old_password", "")
            new_pw = data.get("new_password", "")
            success, msg = db.change_admin_password(username, old_pw, new_pw)
            self._send_json({"success": success, "message": msg}, 200 if success else 400)
            return

        elif path == "/api/tournaments":
            t_id = db.create_tournament(
                name=data.get("name", "Nouveau Tournoi"),
                sport=data.get("sport", "football"),
                year=data.get("year", "2025-2026"),
                tournament_format=data.get("format", "league")
            )
            self._send_json({"status": "ok", "id": t_id})
            return

        elif path == "/api/teams":
            team_id = db.create_team(
                tournament_id=int(data.get("tournament_id")),
                name=data.get("name", ""),
                filiere=data.get("filiere", ""),
                short_name=data.get("short_name", ""),
                color=data.get("color", "#1e3a8a"),
                logo_url=data.get("logo_url", "")
            )
            self._send_json({"status": "ok", "id": team_id})
            return

        elif path == "/api/players":
            age_val = data.get("age")
            try:
                age_val = int(age_val) if age_val is not None and str(age_val).strip() != "" else None
            except ValueError:
                age_val = None

            p_id = db.create_player(
                team_id=int(data.get("team_id")),
                name=data.get("name", ""),
                number=int(data.get("number", 0)),
                position=data.get("position", ""),
                photo_url=data.get("photo_url", ""),
                height=data.get("height", ""),
                age=age_val,
                weight=data.get("weight", "")
            )
            self._send_json({"status": "ok", "id": p_id})
            return

        elif path == "/api/matches":
            m_id = db.create_match(
                tournament_id=int(data.get("tournament_id")),
                team_home_id=int(data.get("team_home_id")),
                team_away_id=int(data.get("team_away_id")),
                round_name=data.get("round_name", "Journée 1"),
                match_date=data.get("match_date", ""),
                match_time=data.get("match_time", ""),
                venue=data.get("venue", ""),
                referee=data.get("referee", "")
            )
            self._send_json({"status": "ok", "id": m_id})
            return

        # F5.1: Automatic Schedule Generation & Optimization
        elif path.startswith("/api/tournament/") and path.endswith("/generate-schedule"):
            t_id = int(path.split("/")[3])
            t = db.get_tournament(t_id)
            if not t:
                self._send_json({"error": "Tournoi introuvable"}, 404)
                return

            teams = db.list_teams(t_id)
            venues = data.get("venues") or ["Terrain Principal", "Gymnase Central"]
            start_date = data.get("start_date", "")
            min_rest_days = int(data.get("min_rest_days", 2))
            exam_dates = data.get("exam_dates") or []
            timeslots = data.get("timeslots") or ["14:00", "16:00", "18:00"]
            commit = bool(data.get("commit", False))

            schedule_result = TournamentScheduler.optimize_schedule(
                teams=teams,
                venues=venues,
                start_date=start_date,
                min_rest_days=min_rest_days,
                exam_dates=exam_dates,
                timeslots=timeslots
            )

            if commit and "schedule" in schedule_result:
                # Save generated matches to DB
                created_ids = []
                for m in schedule_result["schedule"]:
                    mid = db.create_match(
                        tournament_id=t_id,
                        team_home_id=m["team_home_id"],
                        team_away_id=m["team_away_id"],
                        round_name=m["round_name"],
                        match_date=m["match_date"],
                        match_time=m["match_time"],
                        venue=m["venue"],
                        referee="Arbitre Officiel"
                    )
                    created_ids.append(mid)
                schedule_result["created_count"] = len(created_ids)

            self._send_json(schedule_result)
            return

        # F5.2: CSV Import (Dry-Run and Commit)
        elif path.startswith("/api/tournament/") and path.endswith("/import-csv"):
            t_id = int(path.split("/")[3])
            csv_text = data.get("csv_text", "")
            dry_run = bool(data.get("dry_run", True))

            existing_teams = db.list_teams(t_id)
            parsed = CsvImporter.parse_and_validate(csv_text, existing_teams)

            if not dry_run and parsed.get("success"):
                commit_res = CsvImporter.execute_commit(t_id, parsed, db)
                parsed["committed"] = commit_res

            self._send_json(parsed)
            return

        # F4.1: Submit Prediction
        elif path == "/api/predictions":
            t_id = int(data.get("tournament_id"))
            m_id = int(data.get("match_id"))
            student_name = data.get("student_name", "").strip()
            student_school = data.get("student_school", "").strip()
            score_home = int(data.get("predicted_score_home", 0))
            score_away = int(data.get("predicted_score_away", 0))

            if not student_name:
                self._send_json({"error": "Votre nom ou pseudo d'élève est obligatoire."}, 400)
                return

            try:
                pid = db.submit_prediction(t_id, m_id, student_name, student_school, score_home, score_away)
                self._send_json({"status": "ok", "id": pid})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        # F4.2: Submit Fan MVP Vote
        elif path.startswith("/api/matches/") and path.endswith("/vote-mvp"):
            m_id = int(path.split("/")[3])
            player_id = int(data.get("player_id"))
            fingerprint = data.get("fingerprint", "")

            success = db.submit_mvp_vote(m_id, player_id, client_ip, fingerprint)
            if not success:
                self._send_json({"error": "Vous avez déjà voté pour le joueur du match sur cette rencontre (1 vote autorisé par visiteur)."}, 409)
            else:
                self._send_json({"status": "ok", "message": "Votre vote a été enregistré avec succès !"})
            return

        # F4.3: Submit Match Report
        elif path == "/api/match-reports":
            m_id = int(data.get("match_id"))
            author = data.get("author_name", "").strip()
            school = data.get("author_school", "").strip()
            title = data.get("title", "").strip()
            content = data.get("content", "").strip()

            if not author or not title or not content:
                self._send_json({"error": "Auteur, titre et contenu sont obligatoires."}, 400)
                return

            r_id = db.submit_match_report(m_id, author, school, title, content)
            self._send_json({"status": "ok", "id": r_id, "message": "Compte rendu soumis avec succès ! Il sera publié dès validation par l'organisation."})
            return

        # F5.4: Create Backup
        elif path == "/api/backups/create":
            filename = db.create_backup(reason="demande_utilisateur")
            self._send_json({"status": "ok", "filename": filename})
            return

        # F5.4: Restore Backup
        elif path == "/api/backups/restore":
            filename = data.get("filename", "")
            try:
                db.restore_backup(filename)
                self._send_json({"status": "ok", "message": f"Base restaurée avec succès depuis {filename}"})
            except Exception as e:
                self._send_json({"error": str(e)}, 400)
            return

        elif path == "/api/match-events":
            ev_id = db.add_match_event(
                match_id=int(data.get("match_id")),
                team_id=int(data.get("team_id")),
                player_id=int(data.get("player_id")),
                event_type=data.get("event_type", "point"),
                minute_or_period=data.get("minute_or_period", ""),
                count=int(data.get("count", 1))
            )
            self._send_json({"status": "ok", "id": ev_id})
            return

        elif path == "/api/awards":
            aw_id = db.create_weekly_award(
                tournament_id=int(data.get("tournament_id")),
                week_label=data.get("week_label", "Semaine 1"),
                player_id=int(data.get("player_id")),
                title=data.get("title", "Joueur de la Semaine"),
                description=data.get("description", "")
            )
            self._send_json({"status": "ok", "id": aw_id})
            return

        elif path == "/api/highlights":
            h_id = db.create_highlight(
                tournament_id=int(data.get("tournament_id")),
                title=data.get("title", ""),
                description=data.get("description", ""),
                action_type=data.get("action_type", "action"),
                media_type=data.get("media_type", "photo"),
                media_url=data.get("media_url", ""),
                match_id=int(data.get("match_id")) if data.get("match_id") else None,
                player_id=int(data.get("player_id")) if data.get("player_id") else None
            )
            self._send_json({"status": "ok", "id": h_id})
            return

        elif path.startswith("/api/highlights/") and path.endswith("/like"):
            h_id = int(path.split("/")[3])
            likes = db.like_highlight(h_id)
            self._send_json({"status": "ok", "likes_count": likes})
            return

        elif path.startswith("/api/highlights/") and path.endswith("/comments"):
            h_id = int(path.split("/")[3])
            c_id = db.add_highlight_comment(
                highlight_id=h_id,
                author_name=data.get("author_name", "Étudiant"),
                author_filiere=data.get("author_filiere", ""),
                comment_text=data.get("comment_text", "")
            )
            self._send_json({"status": "ok", "comment_id": c_id})
            return

        elif path in ("/api/upload-image", "/api/upload-media"):
            filename = data.get("filename", "upload.jpg")
            b64_data = data.get("data", "")
            if "," in b64_data:
                b64_data = b64_data.split(",", 1)[1]
            file_bytes = base64.b64decode(b64_data)

            ext = os.path.splitext(filename)[1].lower() or ".jpg"
            clean_name = f"media_{abs(hash(filename + str(len(file_bytes))))}{ext}"
            file_path = os.path.join(UPLOADS_DIR, clean_name)
            with open(file_path, "wb") as f:
                f.write(file_bytes)

            self._send_json({"status": "ok", "url": f"/uploads/{clean_name}"})
            return

        self.send_error(404, "Endpoint not found")

    def do_PUT(self):
        client_ip = self.get_client_ip()

        if not check_rate_limit(client_ip):
            self._send_json({"error": "Trop de requêtes. Veuillez patienter une minute (Rate Limit F3.4)."}, 429)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)
        try:
            data = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            data = {}

        if path.startswith("/api/matches/") and path.endswith("/score"):
            m_id = int(path.split("/")[3])
            db.update_match_score(
                match_id=m_id,
                score_home=int(data.get("score_home", 0)),
                score_away=int(data.get("score_away", 0)),
                sets_detail=data.get("sets_detail", ""),
                status=data.get("status", "finished"),
                mvp_player_id=int(data.get("mvp_player_id")) if data.get("mvp_player_id") else None,
                author_role=data.get("author_role", "admin")
            )
            self._send_json({"status": "ok"})
            return

        # F3.3: Fair Play Rules Update
        elif path.startswith("/api/tournament/") and path.endswith("/fair-play-rules"):
            t_id = int(path.split("/")[3])
            db.set_fair_play_rules(
                tournament_id=t_id,
                yellow=float(data.get("yellow_card_points", 1.0)),
                red=float(data.get("red_card_points", 3.0)),
                suspension=float(data.get("suspension_points", 2.0)),
                foul=float(data.get("foul_points", 0.5))
            )
            self._send_json({"status": "ok"})
            return

        # F4.3: Review Journalism Match Report
        elif path.startswith("/api/match-reports/") and path.endswith("/review"):
            r_id = int(path.split("/")[3])
            status = data.get("status", "approved")
            reviewer = data.get("reviewer_name", "Administrateur")
            db.review_match_report(r_id, status, reviewer)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/teams/"):
            team_id = int(path.split("/")[3])
            db.update_team(
                team_id=team_id,
                name=data.get("name", ""),
                filiere=data.get("filiere", ""),
                short_name=data.get("short_name", ""),
                color=data.get("color", "#1e3a8a"),
                logo_url=data.get("logo_url", "")
            )
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/players/"):
            p_id = int(path.split("/")[3])
            age_val = data.get("age")
            try:
                age_val = int(age_val) if age_val is not None and str(age_val).strip() != "" else None
            except ValueError:
                age_val = None

            db.update_player(
                player_id=p_id,
                name=data.get("name", ""),
                number=int(data.get("number", 0)),
                position=data.get("position", ""),
                photo_url=data.get("photo_url", ""),
                height=data.get("height", ""),
                age=age_val,
                weight=data.get("weight", "")
            )
            self._send_json({"status": "ok"})
            return

        self.send_error(404, "Endpoint not found")

    def do_DELETE(self):
        client_ip = self.get_client_ip()

        if not check_rate_limit(client_ip):
            self._send_json({"error": "Trop de requêtes. Veuillez patienter une minute (Rate Limit F3.4)."}, 429)
            return

        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/tournaments/"):
            t_id = int(path.split("/")[3])
            db.delete_tournament(t_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/teams/"):
            team_id = int(path.split("/")[3])
            db.delete_team(team_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/players/"):
            p_id = int(path.split("/")[3])
            db.delete_player(p_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/matches/"):
            m_id = int(path.split("/")[3])
            db.delete_match(m_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/match-events/"):
            ev_id = int(path.split("/")[3])
            db.delete_match_event(ev_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/awards/"):
            aw_id = int(path.split("/")[3])
            db.delete_weekly_award(aw_id)
            self._send_json({"status": "ok"})
            return

        elif path.startswith("/api/highlights/"):
            h_id = int(path.split("/")[3])
            db.delete_highlight(h_id)
            self._send_json({"status": "ok"})
            return

        self.send_error(404, "Endpoint not found")


def release_port_if_busy(port: int) -> None:
    """Libère le port sous Windows si un ancien processus orphelin écoute dessus."""
    if sys.platform == "win32":
        try:
            import subprocess
            out = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True, stderr=subprocess.DEVNULL)
            curr_pid = os.getpid()
            for line in out.strip().splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and "LISTENING" in parts:
                    pid = int(parts[-1])
                    if pid != curr_pid and pid > 4:
                        subprocess.run(f"taskkill /F /PID {pid}", shell=True, capture_output=True)
                        time.sleep(0.3)
        except Exception:
            pass


class ReusableHTTPServer(HTTPServer):
    allow_reuse_address = True
    daemon_threads = True


def run(port: int = 8080):
    release_port_if_busy(port)
    ip = get_local_ip()
    server_address = ("0.0.0.0", port)
    ReusableHTTPServer.allow_reuse_address = True

    try:
        httpd = ReusableHTTPServer(server_address, SportsAppRequestHandler)
    except OSError as e:
        print(f"\n[ERREUR] Impossible d'ouvrir le port {port} : {e}")
        print("Veuillez vérifier qu'aucune autre application n'utilise ce port.")
        sys.exit(1)

    print("=" * 68)
    print("   INSTITUT UNIVERSITAIRE SAINT JEROME DE DOUALA")
    print("   GESTIONNAIRE DE TOURNOIS SPORTIFS EN LIGNE (Foot, Basket, Hand, Volley)")
    print("=" * 68)
    print(f" -> Sur ce PC (Edge / Chrome) :            http://127.0.0.1:{port}")
    print(f" -> Sur votre iPhone/smartphone (Safari) : http://{ip}:{port}/public")
    print("=" * 68)
    print(" ACCES DEPUIS VOTRE IPHONE / TELEPHONE :")
    print(" 1. Votre telephone et votre PC doivent etre sur le meme reseau")
    print("    (ex: partage de connexion iPhone ou meme Wi-Fi).")
    print(" 2. Sur Safari, ouvrez l'adresse réseau :")
    print(f"    http://{ip}:{port}/public")
    print("=" * 68)
    print(" Pour arreter le serveur, fermez simplement cette fenetre ou faites Ctrl+C.")
    print("=" * 68)

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nArrêt du serveur Tournois...")
    finally:
        httpd.server_close()
        print("Serveur arrêté et port libéré proprement.")


if __name__ == "__main__":
    env_port = os.environ.get("PORT")
    if env_port:
        port = int(env_port)
    else:
        port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080
    run(port)
