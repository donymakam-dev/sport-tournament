"""
SQLite Database Layer for Sports Tournament Manager.
Handles tournaments, teams, players, fixtures, match events, awards,
audit logs, fair-play rules, predictions, fan MVP votes, journalism reports,
visit stats, and automated database backups with 14-day retention.
"""

import sqlite3
import os
import json
import shutil
import hashlib
import hmac
import secrets
from datetime import datetime
from contextlib import contextmanager
from typing import List, Dict, Any, Optional

DEFAULT_DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "tournament.db"))
BACKUPS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", "backups"))


class Database:
    def __init__(self, db_path: str = DEFAULT_DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        os.makedirs(BACKUPS_DIR, exist_ok=True)
        self.init_schema()

    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_schema(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executescript("""
            CREATE TABLE IF NOT EXISTS tournaments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                sport TEXT NOT NULL, -- 'football', 'basketball', 'handball', 'volleyball'
                year TEXT DEFAULT '2025-2026',
                format TEXT DEFAULT 'league', -- 'league', 'playoffs'
                status TEXT DEFAULT 'active', -- 'active', 'finished'
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS teams (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                filiere TEXT DEFAULT '',
                short_name TEXT DEFAULT '',
                color TEXT DEFAULT '#1e3a8a',
                logo_url TEXT DEFAULT '',
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                number INTEGER DEFAULT 0,
                position TEXT DEFAULT '',
                photo_url TEXT DEFAULT '',
                height TEXT DEFAULT '',
                age INTEGER DEFAULT NULL,
                weight TEXT DEFAULT '',
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS matches (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_name TEXT DEFAULT 'Journée 1',
                team_home_id INTEGER NOT NULL,
                team_away_id INTEGER NOT NULL,
                score_home INTEGER DEFAULT NULL,
                score_away INTEGER DEFAULT NULL,
                sets_detail TEXT DEFAULT NULL,
                match_date TEXT DEFAULT '',
                match_time TEXT DEFAULT '',
                venue TEXT DEFAULT '',
                referee TEXT DEFAULT '',
                status TEXT DEFAULT 'scheduled', -- 'scheduled', 'finished'
                mvp_player_id INTEGER DEFAULT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (team_home_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (team_away_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (mvp_player_id) REFERENCES players(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS match_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                event_type TEXT NOT NULL, -- 'goal', 'point', 'three_pointer', 'assist', 'rebound', 'yellow_card', 'red_card', 'suspension_2min', 'foul'
                minute_or_period TEXT DEFAULT '',
                count INTEGER DEFAULT 1,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS weekly_awards (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                week_label TEXT NOT NULL,
                player_id INTEGER NOT NULL,
                title TEXT DEFAULT 'Joueur de la Semaine',
                description TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS highlights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                match_id INTEGER DEFAULT NULL,
                player_id INTEGER DEFAULT NULL,
                title TEXT NOT NULL,
                description TEXT DEFAULT '',
                action_type TEXT DEFAULT 'action', -- 'goal', 'dunk', 'three_pointer', 'save', 'assist', 'skill', 'celebration'
                media_type TEXT NOT NULL, -- 'photo', 'video', 'embed'
                media_url TEXT NOT NULL,
                likes_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE SET NULL,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS highlight_comments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                highlight_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                author_filiere TEXT DEFAULT '',
                comment_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (highlight_id) REFERENCES highlights(id) ON DELETE CASCADE
            );

            -- F6.5 : Journal des modifications (Audit log immuable)
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                author_role TEXT DEFAULT 'admin',
                author_name TEXT DEFAULT 'Administrateur',
                action_type TEXT NOT NULL,
                entity_type TEXT NOT NULL,
                entity_id INTEGER DEFAULT NULL,
                old_value TEXT DEFAULT '',
                new_value TEXT DEFAULT '',
                details TEXT DEFAULT ''
            );

            -- F3.3 : Barème et configuration Fair-play
            CREATE TABLE IF NOT EXISTS fair_play_rules (
                tournament_id INTEGER PRIMARY KEY,
                yellow_card_points REAL DEFAULT 1.0,
                red_card_points REAL DEFAULT 3.0,
                suspension_points REAL DEFAULT 2.0,
                foul_points REAL DEFAULT 0.5,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE
            );

            -- F4.1 : Jeu de pronostics
            CREATE TABLE IF NOT EXISTS predictions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                student_name TEXT NOT NULL,
                student_school TEXT NOT NULL,
                predicted_score_home INTEGER NOT NULL,
                predicted_score_away INTEGER NOT NULL,
                predicted_outcome TEXT NOT NULL, -- 'home', 'draw', 'away'
                points_awarded INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments(id) ON DELETE CASCADE,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
                UNIQUE(match_id, student_name)
            );

            -- F4.2 : Vote du joueur du match par le public (Fan MVP Vote)
            CREATE TABLE IF NOT EXISTS match_mvp_votes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                voter_ip TEXT NOT NULL,
                voter_fingerprint TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                UNIQUE(match_id, voter_ip, voter_fingerprint)
            );

            -- F4.3 : Comptes rendus du club de journalisme
            CREATE TABLE IF NOT EXISTS match_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                author_name TEXT NOT NULL,
                author_school TEXT DEFAULT '',
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                status TEXT DEFAULT 'pending', -- 'pending', 'approved', 'rejected'
                reviewed_by TEXT DEFAULT '',
                reviewed_at TIMESTAMP DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE
            );

            -- F6.4 : Statistiques de visites (anonymes, respectueuses de la vie privée)
            CREATE TABLE IF NOT EXISTS visit_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                visit_date DATE DEFAULT (DATE('now')),
                page_path TEXT NOT NULL,
                device_type TEXT DEFAULT 'desktop',
                ip_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Authentification Administrateur / Organisateur
            CREATE TABLE IF NOT EXISTS admin_users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Historique & Palmarès des Éditions (Hall of Fame)
            CREATE TABLE IF NOT EXISTS tournament_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year TEXT NOT NULL,
                sport TEXT NOT NULL,
                tournament_title TEXT NOT NULL,
                champion_team TEXT NOT NULL,
                champion_logo TEXT DEFAULT '',
                runner_up_team TEXT DEFAULT '',
                final_score TEXT DEFAULT '',
                top_scorer_name TEXT DEFAULT '',
                top_scorer_stat TEXT DEFAULT '',
                mvp_name TEXT DEFAULT '',
                summary TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            -- Statistiques individuelles et évaluation des joueurs par match
            CREATE TABLE IF NOT EXISTS player_match_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                points INTEGER DEFAULT 0,
                assists INTEGER DEFAULT 0,
                rebounds INTEGER DEFAULT 0,
                blocks INTEGER DEFAULT 0,
                fouls INTEGER DEFAULT 0,
                technical_fouls INTEGER DEFAULT 0,
                coach_appreciation REAL DEFAULT 0.0,
                rating REAL DEFAULT 5.0,
                rating_manual INTEGER DEFAULT 0,
                is_mvp INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (match_id) REFERENCES matches(id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams(id) ON DELETE CASCADE,
                UNIQUE(match_id, player_id)
            );
            """)
            conn.commit()

            # Initialiser le compte administrateur par défaut si absent
            cursor.execute("SELECT COUNT(*) AS cnt FROM admin_users")
            if cursor.fetchone()["cnt"] == 0:
                salt = secrets.token_hex(16)
                pw_hash = hashlib.pbkdf2_hmac("sha256", "admin2026".encode("utf-8"), salt.encode("utf-8"), 100000).hex()
                cursor.execute(
                    "INSERT INTO admin_users (username, password_hash, salt) VALUES (?, ?, ?)",
                    ("admin", pw_hash, salt)
                )
                conn.commit()

            # Ensure columns exist if table was created in an older schema
            try:
                conn.execute("ALTER TABLE matches ADD COLUMN referee TEXT DEFAULT ''")
                conn.commit()
            except Exception:
                pass

            for col, col_type in [("height", "TEXT DEFAULT ''"), ("age", "INTEGER DEFAULT NULL"), ("weight", "TEXT DEFAULT ''")]:
                try:
                    conn.execute(f"ALTER TABLE players ADD COLUMN {col} {col_type}")
                    conn.commit()
                except Exception:
                    pass

            # Initialiser des exemples d'historique de tournois si la table est vide
            try:
                cursor.execute("SELECT COUNT(*) AS cnt FROM tournament_history")
                if cursor.fetchone()["cnt"] == 0:
                    cursor.execute("""
                        INSERT INTO tournament_history (
                            year, sport, tournament_title, champion_team, champion_logo,
                            runner_up_team, final_score, top_scorer_name, top_scorer_stat,
                            mvp_name, summary, image_url
                        ) VALUES 
                        (
                            '2024-2025', 'football', 'Super Cup Saint Jérôme 2024', 'Génie Informatique FC', '',
                            'Génie Industriel', '3 - 1', 'Karl Ewandé', '9 buts',
                            'Arthur Mbianda', 'Une finale mémorable devant plus de 800 étudiants. Le Génie Informatique a dominé la seconde période grâce à un doublé décisif.',
                            'https://images.unsplash.com/photo-1508098682722-e99c43a406b2?w=800&auto=format&fit=crop&q=60'
                        ),
                        (
                            '2024-2025', 'basketball', 'Saint Jérôme Basket Trophy 2024', 'Bulls SJD', '',
                            'Lakers Saint Jérôme', '78 - 72', 'Yannick Noah Jr.', '24.5 pts/m',
                            'Cédric Kamga', 'Un derby électrique indécis jusqu au buzzer final avec un shoot primé à 3 points à 15 secondes de la fin.',
                            'https://images.unsplash.com/photo-1546519638-68e109498ffc?w=800&auto=format&fit=crop&q=60'
                        )
                    """)
                    conn.commit()
            except Exception:
                pass

    # ---------------- AUTHENTIFICATION ADMIN ----------------
    def verify_admin(self, username: str, password: str) -> bool:
        if not username or not password:
            return False
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT password_hash, salt FROM admin_users WHERE LOWER(username) = LOWER(?)", (username.strip(),))
            row = cursor.fetchone()
            if not row:
                return False
            expected_hash = hashlib.pbkdf2_hmac(
                "sha256", password.encode("utf-8"), row["salt"].encode("utf-8"), 100000
            ).hex()
            return hmac.compare_digest(row["password_hash"], expected_hash)

    def change_admin_password(self, username: str, old_password: str, new_password: str) -> tuple[bool, str]:
        if not self.verify_admin(username, old_password):
            return False, "Ancien mot de passe incorrect."
        if not new_password or len(new_password) < 4:
            return False, "Le nouveau mot de passe doit comporter au moins 4 caractères."
        with self.get_connection() as conn:
            cursor = conn.cursor()
            salt = secrets.token_hex(16)
            pw_hash = hashlib.pbkdf2_hmac("sha256", new_password.encode("utf-8"), salt.encode("utf-8"), 100000).hex()
            cursor.execute("UPDATE admin_users SET password_hash = ?, salt = ? WHERE LOWER(username) = LOWER(?)",
                           (pw_hash, salt, username.strip()))
            conn.commit()
        self.log_audit("admin", username, "change_password", "admin_user", None, "***", "***", "Mot de passe modifié")
        return True, "Mot de passe modifié avec succès."

    # ---------------- HISTORIQUE & PALMARES DES EDITIONS ----------------
    def list_tournament_history(self, sport: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            if sport and sport.strip() != "" and sport.lower() != "all":
                cursor.execute("""
                    SELECT * FROM tournament_history
                    WHERE LOWER(sport) = LOWER(?)
                    ORDER BY year DESC, id DESC
                """, (sport.strip(),))
            else:
                cursor.execute("""
                    SELECT * FROM tournament_history
                    ORDER BY year DESC, id DESC
                """)
            return [dict(row) for row in cursor.fetchall()]

    def get_tournament_history(self, history_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM tournament_history WHERE id = ?", (history_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def create_tournament_history(self, data: Dict[str, Any]) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO tournament_history (
                    year, sport, tournament_title, champion_team, champion_logo,
                    runner_up_team, final_score, top_scorer_name, top_scorer_stat,
                    mvp_name, summary, image_url
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                data.get("year", "2024-2025").strip(),
                data.get("sport", "football").strip(),
                data.get("tournament_title", "Édition Précédente").strip(),
                data.get("champion_team", "").strip(),
                data.get("champion_logo", "").strip(),
                data.get("runner_up_team", "").strip(),
                data.get("final_score", "").strip(),
                data.get("top_scorer_name", "").strip(),
                data.get("top_scorer_stat", "").strip(),
                data.get("mvp_name", "").strip(),
                data.get("summary", "").strip(),
                data.get("image_url", "").strip(),
            ))
            h_id = cursor.lastrowid
            conn.commit()
        self.log_audit("admin", "Administrateur", "create_history", "history", h_id, "", data.get("tournament_title", ""))
        return h_id

    def update_tournament_history(self, history_id: int, data: Dict[str, Any]) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                UPDATE tournament_history SET
                    year = ?,
                    sport = ?,
                    tournament_title = ?,
                    champion_team = ?,
                    champion_logo = ?,
                    runner_up_team = ?,
                    final_score = ?,
                    top_scorer_name = ?,
                    top_scorer_stat = ?,
                    mvp_name = ?,
                    summary = ?,
                    image_url = ?
                WHERE id = ?
            """, (
                data.get("year", "").strip(),
                data.get("sport", "football").strip(),
                data.get("tournament_title", "").strip(),
                data.get("champion_team", "").strip(),
                data.get("champion_logo", "").strip(),
                data.get("runner_up_team", "").strip(),
                data.get("final_score", "").strip(),
                data.get("top_scorer_name", "").strip(),
                data.get("top_scorer_stat", "").strip(),
                data.get("mvp_name", "").strip(),
                data.get("summary", "").strip(),
                data.get("image_url", "").strip(),
                history_id
            ))
            conn.commit()
        self.log_audit("admin", "Administrateur", "update_history", "history", history_id, "", data.get("tournament_title", ""))
        return True

    def delete_tournament_history(self, history_id: int) -> bool:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM tournament_history WHERE id = ?", (history_id,))
            conn.commit()
        self.log_audit("admin", "Administrateur", "delete_history", "history", history_id, "", "")
        return True

    # ---------------- TOURNAMENTS ----------------
    def list_tournaments(self) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM tournaments ORDER BY id DESC").fetchall()
            return [dict(r) for r in rows]

    def get_tournament(self, t_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM tournaments WHERE id = ?", (t_id,)).fetchone()
            return dict(row) if row else None

    def create_tournament(self, name: str, sport: str, year: str = "2025-2026", tournament_format: str = "league") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO tournaments (name, sport, year, format) VALUES (?, ?, ?, ?)",
                (name.strip(), sport.lower().strip(), year.strip(), tournament_format.strip())
            )
            conn.commit()
            t_id = cursor.lastrowid
            # Initialize default fair play rules
            cursor.execute(
                "INSERT OR IGNORE INTO fair_play_rules (tournament_id, yellow_card_points, red_card_points) VALUES (?, 1.0, 3.0)",
                (t_id,)
            )
            conn.commit()

        self.log_audit("admin", "Administrateur", "create_tournament", "tournament", t_id, "", name.strip(), f"Sport: {sport}")
        return t_id

    def update_tournament(self, t_id: int, name: str, year: str, status: str = "active") -> bool:
        old = self.get_tournament(t_id)
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE tournaments SET name = ?, year = ?, status = ? WHERE id = ?",
                (name.strip(), year.strip(), status, t_id)
            )
            conn.commit()
        self.log_audit("admin", "Administrateur", "update_tournament", "tournament", t_id,
                       json.dumps(old) if old else "", f"{name} ({year}, {status})", "")
        return True

    def delete_tournament(self, t_id: int) -> bool:
        old = self.get_tournament(t_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM tournaments WHERE id = ?", (t_id,))
            conn.commit()
        self.log_audit("admin", "Administrateur", "delete_tournament", "tournament", t_id,
                       old["name"] if old else "", "", "")
        return True

    # ---------------- TEAMS ----------------
    def list_teams(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT t.*, (SELECT COUNT(*) FROM players p WHERE p.team_id = t.id) as player_count
                FROM teams t
                WHERE t.tournament_id = ?
                ORDER BY t.name ASC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_team(self, team_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM teams WHERE id = ?", (team_id,)).fetchone()
            return dict(row) if row else None

    def create_team(self, tournament_id: int, name: str, filiere: str = "", short_name: str = "",
                    color: str = "#1e3a8a", logo_url: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO teams (tournament_id, name, filiere, short_name, color, logo_url) VALUES (?, ?, ?, ?, ?, ?)",
                (tournament_id, name.strip(), filiere.strip(), short_name.strip().upper(), color.strip(), logo_url.strip())
            )
            conn.commit()
            team_id = cursor.lastrowid
        self.log_audit("admin", "Administrateur", "create_team", "team", team_id, "", name.strip(), f"Tournoi #{tournament_id}")
        return team_id

    def update_team(self, team_id: int, name: str, filiere: str, short_name: str, color: str, logo_url: str) -> bool:
        old = self.get_team(team_id)
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE teams SET name = ?, filiere = ?, short_name = ?, color = ?, logo_url = ? WHERE id = ?",
                (name.strip(), filiere.strip(), short_name.strip().upper(), color.strip(), logo_url.strip(), team_id)
            )
            conn.commit()
        self.log_audit("admin", "Administrateur", "update_team", "team", team_id,
                       old["name"] if old else "", name.strip(), "")
        return True

    def delete_team(self, team_id: int) -> bool:
        old = self.get_team(team_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM teams WHERE id = ?", (team_id,))
            conn.commit()
        self.log_audit("admin", "Administrateur", "delete_team", "team", team_id,
                       old["name"] if old else "", "", "")
        return True

    # ---------------- PLAYERS ----------------
    def list_players(self, team_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM players WHERE team_id = ? ORDER BY number ASC, name ASC", (team_id,)).fetchall()
            return [dict(r) for r in rows]

    def list_tournament_players(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT p.*, t.name as team_name, t.short_name as team_short, t.color as team_color
                FROM players p
                JOIN teams t ON p.team_id = t.id
                WHERE t.tournament_id = ?
                ORDER BY t.name ASC, p.number ASC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_player(self, player_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM players WHERE id = ?", (player_id,)).fetchone()
            return dict(row) if row else None

    def create_player(self, team_id: int, name: str, number: int = 0, position: str = "", photo_url: str = "", height: str = "", age: Optional[int] = None, weight: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO players (team_id, name, number, position, photo_url, height, age, weight) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (team_id, name.strip(), number, position.strip(), photo_url.strip(), height.strip(), age, weight.strip())
            )
            conn.commit()
            return cursor.lastrowid

    def update_player(self, player_id: int, name: str, number: int, position: str, photo_url: str, height: str = "", age: Optional[int] = None, weight: str = "") -> bool:
        with self.get_connection() as conn:
            conn.execute(
                "UPDATE players SET name = ?, number = ?, position = ?, photo_url = ?, height = ?, age = ?, weight = ? WHERE id = ?",
                (name.strip(), number, position.strip(), photo_url.strip(), height.strip(), age, weight.strip(), player_id)
            )
            conn.commit()
            return True

    def delete_player(self, player_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM players WHERE id = ?", (player_id,))
            conn.commit()
            return True

    # ---------------- MATCHES ----------------
    def list_matches(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT m.*,
                       th.name as team_home_name, th.short_name as team_home_short, th.color as team_home_color, th.logo_url as team_home_logo,
                       ta.name as team_away_name, ta.short_name as team_away_short, ta.color as team_away_color, ta.logo_url as team_away_logo,
                       p.name as mvp_name, p.photo_url as mvp_photo,
                       (SELECT COUNT(*) FROM match_mvp_votes mv WHERE mv.match_id = m.id) as fan_votes_count,
                       (SELECT COUNT(*) FROM match_reports mr WHERE mr.match_id = m.id AND mr.status = 'approved') as approved_reports_count
                FROM matches m
                JOIN teams th ON m.team_home_id = th.id
                JOIN teams ta ON m.team_away_id = ta.id
                LEFT JOIN players p ON m.mvp_player_id = p.id
                WHERE m.tournament_id = ?
                ORDER BY m.id ASC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_match(self, match_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT m.*,
                       th.name as team_home_name, th.short_name as team_home_short, th.color as team_home_color, th.logo_url as team_home_logo, th.filiere as team_home_filiere,
                       ta.name as team_away_name, ta.short_name as team_away_short, ta.color as team_away_color, ta.logo_url as team_away_logo, ta.filiere as team_away_filiere,
                       p.name as mvp_name, p.photo_url as mvp_photo
                FROM matches m
                JOIN teams th ON m.team_home_id = th.id
                JOIN teams ta ON m.team_away_id = ta.id
                LEFT JOIN players p ON m.mvp_player_id = p.id
                WHERE m.id = ?
            """, (match_id,)).fetchone()
            return dict(row) if row else None

    def create_match(self, tournament_id: int, team_home_id: int, team_away_id: int, round_name: str = "Journée 1",
                     match_date: str = "", match_time: str = "", venue: str = "", referee: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO matches (tournament_id, team_home_id, team_away_id, round_name, match_date, match_time, venue, referee, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'scheduled')
            """, (tournament_id, team_home_id, team_away_id, round_name.strip(), match_date.strip(), match_time.strip(), venue.strip(), referee.strip()))
            conn.commit()
            m_id = cursor.lastrowid

        self.log_audit("admin", "Organisateur", "create_match", "match", m_id, "",
                       f"{round_name} : Team #{team_home_id} vs Team #{team_away_id}", f"Date: {match_date} {match_time}")
        return m_id

    def update_match_score(self, match_id: int, score_home: int, score_away: int, sets_detail: str = "",
                           status: str = "finished", mvp_player_id: Optional[int] = None, author_role: str = "admin") -> bool:
        old = self.get_match(match_id)
        old_val = f"{old.get('score_home', '-')}-{old.get('score_away', '-')} ({old.get('status', 'scheduled')})" if old else ""

        with self.get_connection() as conn:
            conn.execute("""
                UPDATE matches
                SET score_home = ?, score_away = ?, sets_detail = ?, status = ?, mvp_player_id = ?
                WHERE id = ?
            """, (score_home, score_away, sets_detail.strip() if sets_detail else None, status, mvp_player_id, match_id))
            conn.commit()

        new_val = f"{score_home}-{score_away} ({status})"
        self.log_audit(author_role, "Responsable / Arbitre", "update_score", "match", match_id, old_val, new_val, f"MVP: {mvp_player_id}")

        # F4.1 : Evaluate predictions for this match automatically when finished
        if status == "finished":
            self.evaluate_match_predictions(match_id, score_home, score_away)

        return True

    # ---------------- STATISTIQUES & NOTES DES JOUEURS (MATCH STATS) ----------------
    def save_match_player_stats(self, match_id: int, stats_list: List[Dict[str, Any]]) -> bool:
        """
        Enregistre ou met à jour les statistiques détaillées (points, passes, rebonds, contres, fautes,
        appréciation et note sur 10) de chaque joueur pour un match donné.
        """
        if not stats_list:
            return True
        with self.get_connection() as conn:
            cursor = conn.cursor()
            for s in stats_list:
                player_id = int(s["player_id"])
                team_id = int(s.get("team_id", 0))
                if not team_id:
                    # Trouver le team_id à partir de players
                    p_row = conn.execute("SELECT team_id FROM players WHERE id = ?", (player_id,)).fetchone()
                    team_id = p_row["team_id"] if p_row else 0

                points = int(s.get("points", 0))
                assists = int(s.get("assists", 0))
                rebounds = int(s.get("rebounds", 0))
                blocks = int(s.get("blocks", 0))
                fouls = int(s.get("fouls", 0))
                tech_fouls = int(s.get("technical_fouls", 0))
                coach_app = float(s.get("coach_appreciation", 0.0))
                rating = float(s.get("rating", 5.0))
                rating_manual = 1 if s.get("rating_manual") else 0
                is_mvp = 1 if s.get("is_mvp") else 0

                cursor.execute("""
                    INSERT INTO player_match_stats (
                        match_id, player_id, team_id, points, assists, rebounds, blocks,
                        fouls, technical_fouls, coach_appreciation, rating, rating_manual, is_mvp
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(match_id, player_id) DO UPDATE SET
                        points = excluded.points,
                        assists = excluded.assists,
                        rebounds = excluded.rebounds,
                        blocks = excluded.blocks,
                        fouls = excluded.fouls,
                        technical_fouls = excluded.technical_fouls,
                        coach_appreciation = excluded.coach_appreciation,
                        rating = excluded.rating,
                        rating_manual = excluded.rating_manual,
                        is_mvp = excluded.is_mvp
                """, (match_id, player_id, team_id, points, assists, rebounds, blocks,
                      fouls, tech_fouls, coach_app, rating, rating_manual, is_mvp))
            conn.commit()
        return True

    def get_match_player_stats(self, match_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT pms.*,
                       p.name as player_name, p.number as player_number, p.position as player_position, p.photo_url as player_photo,
                       t.name as team_name, t.short_name as team_short, t.color as team_color, t.logo_url as team_logo
                FROM player_match_stats pms
                JOIN players p ON pms.player_id = p.id
                JOIN teams t ON pms.team_id = t.id
                WHERE pms.match_id = ?
                ORDER BY t.id, pms.points DESC, pms.rating DESC
            """, (match_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_tournament_player_stats_summary(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT p.id as player_id, p.name as player_name, p.number as player_number,
                       p.position as player_position, p.photo_url as player_photo,
                       t.id as team_id, t.name as team_name, t.color as team_color, t.logo_url as team_logo,
                       COUNT(pms.id) as matches_played,
                       COALESCE(SUM(pms.points), 0) as total_points,
                       COALESCE(ROUND(AVG(pms.points), 1), 0.0) as ppg,
                       COALESCE(SUM(pms.assists), 0) as total_assists,
                       COALESCE(ROUND(AVG(pms.assists), 1), 0.0) as apg,
                       COALESCE(SUM(pms.rebounds), 0) as total_rebounds,
                       COALESCE(ROUND(AVG(pms.rebounds), 1), 0.0) as rpg,
                       COALESCE(SUM(pms.blocks), 0) as total_blocks,
                       COALESCE(SUM(pms.fouls), 0) as total_fouls,
                       COALESCE(ROUND(AVG(pms.rating), 1), 5.0) as avg_rating,
                       COALESCE(SUM(pms.is_mvp), 0) as mvp_count,
                       COALESCE(SUM(pms.is_mvp), 0) as mvp_titles_count
                FROM players p
                JOIN teams t ON p.team_id = t.id
                LEFT JOIN player_match_stats pms ON pms.player_id = p.id
                WHERE t.tournament_id = ?
                GROUP BY p.id
                HAVING matches_played > 0 OR total_points > 0
                ORDER BY avg_rating DESC, total_points DESC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def delete_match(self, match_id: int) -> bool:
        old = self.get_match(match_id)
        with self.get_connection() as conn:
            conn.execute("DELETE FROM matches WHERE id = ?", (match_id,))
            conn.commit()
        self.log_audit("admin", "Administrateur", "delete_match", "match", match_id,
                       f"{old.get('team_home_name')} vs {old.get('team_away_name')}" if old else "", "", "")
        return True

    # ---------------- MATCH EVENTS ----------------
    def list_match_events(self, match_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT me.*, p.name as player_name, p.number as player_number, t.name as team_name
                FROM match_events me
                JOIN players p ON me.player_id = p.id
                JOIN teams t ON me.team_id = t.id
                WHERE me.match_id = ?
                ORDER BY me.id ASC
            """, (match_id,)).fetchall()
            return [dict(r) for r in rows]

    def add_match_event(self, match_id: int, team_id: int, player_id: int, event_type: str,
                        minute_or_period: str = "", count: int = 1) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO match_events (match_id, team_id, player_id, event_type, minute_or_period, count)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (match_id, team_id, player_id, event_type.strip(), minute_or_period.strip(), count))
            conn.commit()
            return cursor.lastrowid

    def delete_match_event(self, event_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM match_events WHERE id = ?", (event_id,))
            conn.commit()
            return True

    # ---------------- WEEKLY AWARDS ----------------
    def list_weekly_awards(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT wa.*, p.name as player_name, p.number as player_number, p.photo_url as player_photo,
                       t.name as team_name, t.short_name as team_short, t.color as team_color, t.logo_url as team_logo
                FROM weekly_awards wa
                JOIN players p ON wa.player_id = p.id
                JOIN teams t ON p.team_id = t.id
                WHERE wa.tournament_id = ?
                ORDER BY wa.id DESC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def create_weekly_award(self, tournament_id: int, week_label: str, player_id: int, title: str, description: str = "") -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO weekly_awards (tournament_id, week_label, player_id, title, description)
                VALUES (?, ?, ?, ?, ?)
            """, (tournament_id, week_label.strip(), player_id, title.strip(), description.strip()))
            conn.commit()
            return cursor.lastrowid

    def delete_weekly_award(self, award_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM weekly_awards WHERE id = ?", (award_id,))
            conn.commit()
            return True

    # ---------------- HIGHLIGHTS ----------------
    def create_highlight(self, tournament_id: int, title: str, description: str, action_type: str,
                         media_type: str, media_url: str, match_id: Optional[int] = None, player_id: Optional[int] = None) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO highlights (tournament_id, match_id, player_id, title, description, action_type, media_type, media_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (tournament_id, match_id, player_id, title.strip(), description.strip(), action_type.strip(), media_type.strip(), media_url.strip()))
            conn.commit()
            return cursor.lastrowid

    def list_highlights(self, tournament_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    h.*,
                    p.name as player_name,
                    p.number as player_number,
                    p.position as player_position,
                    p.photo_url as player_photo_url,
                    tm.name as team_name,
                    tm.color as team_color,
                    tm.short_name as team_short_name,
                    (SELECT COUNT(*) FROM highlight_comments c WHERE c.highlight_id = h.id) as comments_count
                FROM highlights h
                LEFT JOIN players p ON h.player_id = p.id
                LEFT JOIN teams tm ON p.team_id = tm.id
                WHERE h.tournament_id = ?
                ORDER BY h.id DESC
            """, (tournament_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_highlight(self, highlight_id: int) -> Optional[Dict[str, Any]]:
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    h.*,
                    p.name as player_name,
                    p.number as player_number,
                    p.position as player_position,
                    p.photo_url as player_photo_url,
                    tm.name as team_name,
                    tm.color as team_color,
                    tm.short_name as team_short_name,
                    (SELECT COUNT(*) FROM highlight_comments c WHERE c.highlight_id = h.id) as comments_count
                FROM highlights h
                LEFT JOIN players p ON h.player_id = p.id
                LEFT JOIN teams tm ON p.team_id = tm.id
                WHERE h.id = ?
            """, (highlight_id,)).fetchone()
            return dict(row) if row else None

    def like_highlight(self, highlight_id: int) -> int:
        with self.get_connection() as conn:
            conn.execute("UPDATE highlights SET likes_count = likes_count + 1 WHERE id = ?", (highlight_id,))
            conn.commit()
            res = conn.execute("SELECT likes_count FROM highlights WHERE id = ?", (highlight_id,)).fetchone()
            return res[0] if res else 0

    def delete_highlight(self, highlight_id: int) -> bool:
        with self.get_connection() as conn:
            conn.execute("DELETE FROM highlights WHERE id = ?", (highlight_id,))
            conn.commit()
            return True

    def add_highlight_comment(self, highlight_id: int, author_name: str, author_filiere: str, comment_text: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO highlight_comments (highlight_id, author_name, author_filiere, comment_text)
                VALUES (?, ?, ?, ?)
            """, (highlight_id, author_name.strip(), author_filiere.strip(), comment_text.strip()))
            conn.commit()
            return cursor.lastrowid

    def list_highlight_comments(self, highlight_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("SELECT * FROM highlight_comments WHERE highlight_id = ? ORDER BY id ASC", (highlight_id,)).fetchall()
            return [dict(r) for r in rows]

    # =========================================================================
    # NOUVELLES FONCTIONNALITÉS DU CAHIER DES CHARGES
    # =========================================================================

    # ---------------- F6.5 : JOURNAL DES MODIFICATIONS (AUDIT LOGS) ----------------
    def log_audit(self, author_role: str, author_name: str, action_type: str,
                  entity_type: str, entity_id: Optional[int], old_value: str, new_value: str, details: str = "") -> int:
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO audit_logs (author_role, author_name, action_type, entity_type, entity_id, old_value, new_value, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (author_role, author_name, action_type, entity_type, entity_id, str(old_value), str(new_value), details))
                conn.commit()
                return cursor.lastrowid
        except Exception:
            return 0

    def list_audit_logs(self, limit: int = 100, entity_type: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            if entity_type:
                rows = conn.execute("""
                    SELECT * FROM audit_logs
                    WHERE entity_type = ?
                    ORDER BY id DESC LIMIT ?
                """, (entity_type, limit)).fetchall()
            else:
                rows = conn.execute("""
                    SELECT * FROM audit_logs
                    ORDER BY id DESC LIMIT ?
                """, (limit,)).fetchall()
            return [dict(r) for r in rows]

    # ---------------- F3.3 : FAIR-PLAY CONFIG & STANDINGS ----------------
    def get_fair_play_rules(self, tournament_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            row = conn.execute("SELECT * FROM fair_play_rules WHERE tournament_id = ?", (tournament_id,)).fetchone()
            if row:
                return dict(row)
            return {
                "tournament_id": tournament_id,
                "yellow_card_points": 1.0,
                "red_card_points": 3.0,
                "suspension_points": 2.0,
                "foul_points": 0.5
            }

    def set_fair_play_rules(self, tournament_id: int, yellow: float, red: float, suspension: float = 2.0, foul: float = 0.5) -> bool:
        old = self.get_fair_play_rules(tournament_id)
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO fair_play_rules (tournament_id, yellow_card_points, red_card_points, suspension_points, foul_points, updated_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(tournament_id) DO UPDATE SET
                    yellow_card_points = excluded.yellow_card_points,
                    red_card_points = excluded.red_card_points,
                    suspension_points = excluded.suspension_points,
                    foul_points = excluded.foul_points,
                    updated_at = CURRENT_TIMESTAMP
            """, (tournament_id, float(yellow), float(red), float(suspension), float(foul)))
            conn.commit()

        self.log_audit("admin", "Administrateur", "update_fair_play_rules", "rules", tournament_id,
                       json.dumps(old), f"Jaune:{yellow}, Rouge:{red}", "")
        return True

    # ---------------- F4.1 : PRONOSTICS ----------------
    def submit_prediction(self, tournament_id: int, match_id: int, student_name: str,
                          student_school: str, score_home: int, score_away: int) -> int:
        student_name = student_name.strip()
        student_school = student_school.strip() or "Élève"

        match = self.get_match(match_id)
        if not match:
            raise ValueError("Match introuvable")
        if match.get("status") == "finished":
            raise ValueError("Le match est déjà terminé, les pronostics sont clos.")

        # Determine outcome
        if score_home > score_away:
            outcome = "home"
        elif score_away > score_home:
            outcome = "away"
        else:
            outcome = "draw"

        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO predictions (tournament_id, match_id, student_name, student_school, predicted_score_home, predicted_score_away, predicted_outcome)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(match_id, student_name) DO UPDATE SET
                    predicted_score_home = excluded.predicted_score_home,
                    predicted_score_away = excluded.predicted_score_away,
                    predicted_outcome = excluded.predicted_outcome,
                    student_school = excluded.student_school,
                    created_at = CURRENT_TIMESTAMP
            """, (tournament_id, match_id, student_name, student_school, score_home, score_away, outcome))
            conn.commit()
            return cursor.lastrowid

    def evaluate_match_predictions(self, match_id: int, score_home: int, score_away: int) -> int:
        """Calculates points awarded: 3 pts exact score, 1 pt correct outcome (1/N/2), 0 otherwise."""
        if score_home > score_away:
            actual_outcome = "home"
        elif score_away > score_home:
            actual_outcome = "away"
        else:
            actual_outcome = "draw"

        count = 0
        with self.get_connection() as conn:
            preds = conn.execute("SELECT * FROM predictions WHERE match_id = ?", (match_id,)).fetchall()
            for p in preds:
                ph = int(p["predicted_score_home"])
                pa = int(p["predicted_score_away"])
                po = p["predicted_outcome"]

                if ph == score_home and pa == score_away:
                    pts = 3
                elif po == actual_outcome:
                    pts = 1
                else:
                    pts = 0

                conn.execute("UPDATE predictions SET points_awarded = ? WHERE id = ?", (pts, p["id"]))
                count += 1
            conn.commit()
        return count

    def get_predictions_leaderboard(self, tournament_id: int, school: Optional[str] = None) -> Dict[str, Any]:
        with self.get_connection() as conn:
            # 1. Students rankings
            query = """
                SELECT student_name, student_school,
                       COUNT(*) as total_predictions,
                       SUM(CASE WHEN points_awarded IS NOT NULL THEN points_awarded ELSE 0 END) as total_points,
                       SUM(CASE WHEN points_awarded = 3 THEN 1 ELSE 0 END) as exact_scores,
                       SUM(CASE WHEN points_awarded = 1 THEN 1 ELSE 0 END) as good_outcomes
                FROM predictions
                WHERE tournament_id = ?
            """
            params = [tournament_id]
            if school:
                query += " AND student_school = ?"
                params.append(school)
            query += " GROUP BY student_name, student_school ORDER BY total_points DESC, exact_scores DESC, total_predictions DESC LIMIT 100"

            rows = conn.execute(query, params).fetchall()
            students = []
            for idx, r in enumerate(rows, start=1):
                d = dict(r)
                d["rank"] = idx
                students.append(d)

            # 2. Schools rankings
            school_rows = conn.execute("""
                SELECT student_school,
                       COUNT(DISTINCT student_name) as predictors_count,
                       SUM(CASE WHEN points_awarded IS NOT NULL THEN points_awarded ELSE 0 END) as total_points,
                       SUM(CASE WHEN points_awarded = 3 THEN 1 ELSE 0 END) as exact_scores
                FROM predictions
                WHERE tournament_id = ?
                GROUP BY student_school
                ORDER BY total_points DESC, exact_scores DESC
            """, (tournament_id,)).fetchall()

            schools = []
            for idx, r in enumerate(school_rows, start=1):
                d = dict(r)
                d["rank"] = idx
                d["avg_points"] = round(d["total_points"] / max(d["predictors_count"], 1), 1)
                schools.append(d)

            return {
                "students": students,
                "schools": schools
            }

    def list_match_predictions(self, match_id: int) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT id, student_name, student_school, predicted_score_home, predicted_score_away, predicted_outcome, points_awarded, created_at
                FROM predictions
                WHERE match_id = ?
                ORDER BY id DESC
            """, (match_id,)).fetchall()
            return [dict(r) for r in rows]

    # ---------------- F4.2 : VOTE JOUEUR DU MATCH DU PUBLIC ----------------
    def submit_mvp_vote(self, match_id: int, player_id: int, voter_ip: str, voter_fingerprint: str = "") -> bool:
        voter_ip = voter_ip.strip() or "127.0.0.1"
        voter_fingerprint = voter_fingerprint.strip()

        # Check if voted in last 24h
        with self.get_connection() as conn:
            existing = conn.execute("""
                SELECT id FROM match_mvp_votes
                WHERE match_id = ? AND (voter_ip = ? OR (voter_fingerprint != '' AND voter_fingerprint = ?))
            """, (match_id, voter_ip, voter_fingerprint)).fetchone()

            if existing:
                return False

            conn.execute("""
                INSERT INTO match_mvp_votes (match_id, player_id, voter_ip, voter_fingerprint)
                VALUES (?, ?, ?, ?)
            """, (match_id, player_id, voter_ip, voter_fingerprint))
            conn.commit()
            return True

    def get_match_mvp_votes(self, match_id: int) -> Dict[str, Any]:
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT mv.player_id, p.name as player_name, p.number as player_number, p.photo_url,
                       t.name as team_name, t.color as team_color,
                       COUNT(*) as votes_count
                FROM match_mvp_votes mv
                JOIN players p ON mv.player_id = p.id
                JOIN teams t ON p.team_id = t.id
                WHERE mv.match_id = ?
                GROUP BY mv.player_id
                ORDER BY votes_count DESC
            """, (match_id,)).fetchall()

            total_votes = sum(r["votes_count"] for r in rows)
            results = []
            for r in rows:
                d = dict(r)
                d["percent"] = round((d["votes_count"] / total_votes * 100), 1) if total_votes > 0 else 0
                results.append(d)

            winner = results[0] if results else None
            return {
                "match_id": match_id,
                "total_votes": total_votes,
                "winner": winner,
                "votes": results
            }

    # ---------------- F4.3 : COMPTES RENDUS CLUB DE JOURNALISME ----------------
    def submit_match_report(self, match_id: int, author_name: str, author_school: str, title: str, content: str) -> int:
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO match_reports (match_id, author_name, author_school, title, content, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
            """, (match_id, author_name.strip(), author_school.strip(), title.strip(), content.strip()))
            conn.commit()
            r_id = cursor.lastrowid

        self.log_audit("journaliste", author_name.strip(), "submit_match_report", "report", r_id, "", title.strip(), f"Match #{match_id}")
        return r_id

    def review_match_report(self, report_id: int, status: str, reviewer_name: str = "Administrateur") -> bool:
        if status not in ("approved", "rejected", "pending"):
            status = "approved"

        with self.get_connection() as conn:
            conn.execute("""
                UPDATE match_reports
                SET status = ?, reviewed_by = ?, reviewed_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, reviewer_name.strip(), report_id))
            conn.commit()

        self.log_audit("admin", reviewer_name, "review_match_report", "report", report_id, "", status, "")
        return True

    def list_match_reports(self, match_id: Optional[int] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        with self.get_connection() as conn:
            query = """
                SELECT mr.*, m.round_name, m.match_date,
                       th.name as team_home_name, ta.name as team_away_name
                FROM match_reports mr
                JOIN matches m ON mr.match_id = m.id
                JOIN teams th ON m.team_home_id = th.id
                JOIN teams ta ON m.team_away_id = ta.id
                WHERE 1=1
            """
            params = []
            if match_id:
                query += " AND mr.match_id = ?"
                params.append(match_id)
            if status:
                query += " AND mr.status = ?"
                params.append(status)
            query += " ORDER BY mr.id DESC"

            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    # ---------------- F6.4 : STATISTIQUES DE VISITE (PRIVACY-FRIENDLY) ----------------
    def record_visit(self, page_path: str, user_agent: str, client_ip: str) -> bool:
        try:
            # Determine device type
            ua = user_agent.lower()
            if "mobile" in ua or "android" in ua or "iphone" in ua:
                device = "mobile"
            elif "ipad" in ua or "tablet" in ua:
                device = "tablet"
            else:
                device = "desktop"

            # Salted IP hash to respect privacy without tracking
            today_str = datetime.now().strftime("%Y-%m-%d")
            ip_hash = hashlib.sha256(f"{client_ip}_{today_str}".encode("utf-8")).hexdigest()[:16]

            with self.get_connection() as conn:
                conn.execute("""
                    INSERT INTO visit_stats (visit_date, page_path, device_type, ip_hash)
                    VALUES (DATE('now'), ?, ?, ?)
                """, (page_path[:100], device, ip_hash))
                conn.commit()
            return True
        except Exception:
            return False

    def get_visit_stats(self) -> Dict[str, Any]:
        with self.get_connection() as conn:
            # Total visits and unique visitors today
            today_total = conn.execute("SELECT COUNT(*) FROM visit_stats WHERE visit_date = DATE('now')").fetchone()[0]
            today_uniques = conn.execute("SELECT COUNT(DISTINCT ip_hash) FROM visit_stats WHERE visit_date = DATE('now')").fetchone()[0]
            all_time = conn.execute("SELECT COUNT(*) FROM visit_stats").fetchone()[0]

            # Top pages
            top_pages = conn.execute("""
                SELECT page_path, COUNT(*) as count
                FROM visit_stats
                GROUP BY page_path
                ORDER BY count DESC LIMIT 5
            """).fetchall()

            # Devices breakdown
            devices = conn.execute("""
                SELECT device_type, COUNT(*) as count
                FROM visit_stats
                GROUP BY device_type
            """).fetchall()

            return {
                "today_total": today_total,
                "today_uniques": today_uniques,
                "all_time": all_time,
                "top_pages": [dict(r) for r in top_pages],
                "devices": {r["device_type"]: r["count"] for r in devices}
            }

    # ---------------- F5.4 : SAUVEGARDES & RESTAURATION (14 DERNIÈRES) ----------------
    def create_backup(self, reason: str = "manuel") -> str:
        """Creates a timestamped backup and prunes old backups keeping the 14 latest."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"backup_tournament_{timestamp}.db"
        target_path = os.path.join(BACKUPS_DIR, backup_filename)

        with self.get_connection() as conn:
            # Backup using SQLite backup API for zero corruption risk
            backup_conn = sqlite3.connect(target_path)
            conn.backup(backup_conn)
            backup_conn.close()

        # Enforce 14-days retention policy
        self._prune_old_backups(keep_count=14)

        size_kb = round(os.path.getsize(target_path) / 1024, 1)
        self.log_audit("admin", "Système", "create_backup", "backup", None, "", backup_filename, f"Taille: {size_kb} KB, Raison: {reason}")
        return backup_filename

    def _prune_old_backups(self, keep_count: int = 14):
        files = []
        for f in os.listdir(BACKUPS_DIR):
            if f.startswith("backup_tournament_") and f.endswith(".db"):
                full_p = os.path.join(BACKUPS_DIR, f)
                files.append((os.path.getmtime(full_p), full_p))

        files.sort(reverse=True)
        # Remove files beyond keep_count
        for _, path in files[keep_count:]:
            try:
                os.remove(path)
            except Exception:
                pass

    def list_backups(self) -> List[Dict[str, Any]]:
        backups = []
        if not os.path.exists(BACKUPS_DIR):
            return []

        for f in sorted(os.listdir(BACKUPS_DIR), reverse=True):
            if f.startswith("backup_tournament_") and f.endswith(".db"):
                fp = os.path.join(BACKUPS_DIR, f)
                stat = os.stat(fp)
                backups.append({
                    "filename": f,
                    "size_kb": round(stat.st_size / 1024, 1),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
                })
        return backups

    def restore_backup(self, backup_filename: str) -> bool:
        """Restores the database from a backup file after verifying integrity."""
        backup_filename = os.path.basename(backup_filename)
        source_path = os.path.join(BACKUPS_DIR, backup_filename)

        if not os.path.exists(source_path):
            raise FileNotFoundError(f"Fichier de sauvegarde {backup_filename} introuvable.")

        # Test integrity of source
        test_conn = sqlite3.connect(source_path)
        check = test_conn.execute("PRAGMA integrity_check").fetchone()[0]
        test_conn.close()
        if check != "ok":
            raise ValueError(f"Fichier de sauvegarde corrompu : {check}")

        # Safety copy of current db before restore
        safety_path = os.path.join(BACKUPS_DIR, f"pre_restore_safety_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db")
        if os.path.exists(self.db_path):
            shutil.copy2(self.db_path, safety_path)

        # Restore
        shutil.copy2(source_path, self.db_path)
        self.log_audit("admin", "Administrateur", "restore_backup", "backup", None, "", backup_filename, "Restauration effectuée avec succès")
        return True

    # ---------------- INITIAL DEMO SEED ----------------
    def seed_initial_demo_if_empty(self):
        """Pre-populate a realistic basketball tournament and football tournament if DB is new."""
        with self.get_connection() as conn:
            count = conn.execute("SELECT COUNT(*) FROM tournaments").fetchone()[0]
            if count > 0:
                return

        # 1. Basketball Tournament (Inter-Filières)
        t_bb_id = self.create_tournament("Tournoi Inter-Filières de Basketball", "basketball", "2025-2026")
        
        # Teams
        tm_id = self.create_team(t_bb_id, "Mécatronique Bulls", "Génie Mécatronique", "MEC", "#dc2626")
        ti_id = self.create_team(t_bb_id, "Génie Info Lakers", "Génie Informatique", "INF", "#7c3aed")
        te_id = self.create_team(t_bb_id, "Électrotechnique Warriors", "Génie Électrique", "ELE", "#2563eb")
        tc_id = self.create_team(t_bb_id, "Génie Civil Celtics", "Génie Civil", "CIV", "#16a34a")

        # Players
        p_m1 = self.create_player(tm_id, "KAMGA Jean-Paul", 23, "Arrière", "")
        p_m2 = self.create_player(tm_id, "FOTSO Christian", 7, "Ailier", "")
        p_m3 = self.create_player(tm_id, "TCHOUA Kevin", 11, "Meneur", "")

        p_i1 = self.create_player(ti_id, "NGOUE Nathalie", 10, "Meneuse", "")
        p_i2 = self.create_player(ti_id, "BEKOLO Steve", 30, "Ailier Fort", "")
        p_i3 = self.create_player(ti_id, "YONGA Vanessa", 8, "Pivot", "")

        p_e1 = self.create_player(te_id, "ONANA Joseph", 15, "Pivot", "")
        p_c1 = self.create_player(tc_id, "MOUKOKO Diane", 5, "Meneuse", "")

        # Matches & Results
        m1 = self.create_match(t_bb_id, tm_id, ti_id, "Journée 1", "2026-10-05", "15:30", "Gymnase Central", "Arbitre National")
        self.update_match_score(m1, 74, 68, status="finished", mvp_player_id=p_m1)
        self.add_match_event(m1, tm_id, p_m1, "point", "Match", 28)
        self.add_match_event(m1, tm_id, p_m1, "three_pointer", "Match", 4)
        self.add_match_event(m1, tm_id, p_m1, "assist", "Match", 6)
        self.add_match_event(m1, tm_id, p_m2, "rebound", "Match", 9)
        self.add_match_event(m1, ti_id, p_i1, "point", "Match", 22)
        self.add_match_event(m1, ti_id, p_i1, "assist", "Match", 8)
        self.add_match_event(m1, ti_id, p_i2, "rebound", "Match", 12)
        self.add_match_event(m1, tm_id, p_m2, "foul", "2Q", 2)
        self.add_match_event(m1, tm_id, p_m2, "unsportsmanlike_foul", "4Q", 1)
        self.add_match_event(m1, ti_id, p_i1, "technical_foul", "3Q", 1)
        self.add_match_event(m1, ti_id, p_i2, "foul", "1Q", 3)

        m2 = self.create_match(t_bb_id, te_id, tc_id, "Journée 1", "2026-10-05", "17:00", "Gymnase Central", "Arbitre Ligue")
        self.update_match_score(m2, 65, 62, status="finished", mvp_player_id=p_e1)

        m3 = self.create_match(t_bb_id, tm_id, te_id, "Journée 2", "2026-10-12", "16:00", "Gymnase Central", "Arbitre Fédéral")

        # Award
        self.create_weekly_award(
            t_bb_id,
            "Semaine 1",
            p_m1,
            "MVP de la Semaine 1",
            "Performance magistrale face aux Lakers : 28 pts, 4 tirs primés à 3-pts et 6 passes décisives."
        )

        # 2. Football Tournament
        t_fb_id = self.create_tournament("Coupe du Doyen — Football", "football", "2025-2026")
        fb_m = self.create_team(t_fb_id, "FC Mécatronique", "Mécatronique", "MEC", "#dc2626")
        fb_i = self.create_team(t_fb_id, "AS Informatique", "Informatique", "INF", "#2563eb")
        fb_p1 = self.create_player(fb_m, "ZANGA Patrick", 9, "Attaquant", "")
        fb_p2 = self.create_player(fb_i, "KENMOE Arthur", 10, "Milieu", "")

        m_fb = self.create_match(t_fb_id, fb_m, fb_i, "Poule A - J1", "2026-10-06", "16:00", "Stade Campus", "Arbitre Régional")
        self.update_match_score(m_fb, 2, 1, status="finished", mvp_player_id=fb_p1)
        self.add_match_event(m_fb, fb_m, fb_p1, "goal", "24'", 1)
        self.add_match_event(m_fb, fb_m, fb_p1, "goal", "68'", 1)
        self.add_match_event(m_fb, fb_i, fb_p2, "goal", "41'", 1)
        self.add_match_event(m_fb, fb_m, fb_p1, "yellow_card", "55'", 1)

        # Seed Predictions demo
        self.submit_prediction(t_bb_id, m1, "David N.", "Génie Mécatronique", 74, 68)
        self.submit_prediction(t_bb_id, m1, "Sandrine M.", "Génie Informatique", 65, 70)
        self.submit_prediction(t_bb_id, m1, "Brice T.", "Génie Civil", 70, 64)
        self.evaluate_match_predictions(m1, 74, 68)

        # Seed Journalism report demo
        self.submit_match_report(
            m1,
            author_name="Club Média Saint Jérôme",
            author_school="Génie Informatique",
            title="Les Bulls s'imposent dans un derby électrique face aux Lakers",
            content="Quelle rencontre d'ouverture ! Portés par un Jean-Paul KAMGA étincelant (28 points), les Bulls de Mécatronique ont fait la différence dans le dernier quart-temps malgré la combativité héroïque de Nathalie NGOUE."
        )
        reports = self.list_match_reports(m1)
        if reports:
            self.review_match_report(reports[0]["id"], "approved", "Responsable Média")

        # Seed initial backup
        self.create_backup("initialisation")
