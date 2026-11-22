"""
Unit Tests for the 18 Features of the Cahier des Charges.
Tests Chart data, Head-to-Head, Fair-play, Predictions, Fan MVP votes,
Journalism moderation, Badges, Scheduler optimization, CSV import, Backups, and Audit logs.
"""

import unittest
import os
import sys
import uuid
import gc

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from sports_engine import SportsEngine
from database import Database
from scheduler import TournamentScheduler
from csv_importer import CsvImporter


class TestCahierCharges(unittest.TestCase):
    def setUp(self):
        gc.collect()
        self.test_db_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data", f"test_cc_{uuid.uuid4().hex}.db"))
        self.db = Database(self.test_db_path)

    def tearDown(self):
        gc.collect()
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    # F3.1: Team charts data (Points evolution, goals, 5-match form)
    def test_team_charts_data(self):
        matches = [
            {"id": 1, "round_name": "J1", "team_home_id": 1, "team_away_id": 2, "score_home": 3, "score_away": 1, "status": "finished", "match_date": "2026-10-01", "team_away_name": "Team 2"},
            {"id": 2, "round_name": "J2", "team_home_id": 3, "team_away_id": 1, "score_home": 1, "score_away": 1, "status": "finished", "match_date": "2026-10-05", "team_home_name": "Team 3"},
            {"id": 3, "round_name": "J3", "team_home_id": 1, "team_away_id": 4, "score_home": 0, "score_away": 2, "status": "finished", "match_date": "2026-10-10", "team_away_name": "Team 4"}
        ]
        charts = SportsEngine.calculate_team_charts_data(1, matches, "football")
        self.assertEqual(len(charts["labels"]), 3)
        # J1 Win (+3) -> 3, J2 Draw (+1) -> 4, J3 Loss (+0) -> 4
        self.assertEqual(charts["points_evolution"], [3, 4, 4])
        self.assertEqual(charts["scored_per_day"], [3, 1, 0])
        self.assertEqual(charts["conceded_per_day"], [1, 1, 2])
        self.assertEqual(charts["form"][0]["outcome"], "V")
        self.assertEqual(charts["form"][1]["outcome"], "N")
        self.assertEqual(charts["form"][2]["outcome"], "D")

    # F3.2: Head-to-Head Comparison
    def test_head_to_head_comparison(self):
        teams = [{"id": 10, "name": "Bulls"}, {"id": 20, "name": "Lakers"}]
        matches = [
            {"team_home_id": 10, "team_away_id": 20, "score_home": 75, "score_away": 70, "status": "finished", "tournament_name": "T1"},
            {"team_home_id": 20, "team_away_id": 10, "score_home": 82, "score_away": 68, "status": "finished", "tournament_name": "T2"},
            {"team_home_id": 10, "team_away_id": 20, "score_home": 60, "score_away": 58, "status": "finished", "tournament_name": "T3"}
        ]
        h2h = SportsEngine.calculate_head_to_head(10, 20, matches, teams)
        self.assertEqual(h2h["total_matches"], 3)
        self.assertEqual(h2h["team1_wins"], 2) # Bulls won 2
        self.assertEqual(h2h["team2_wins"], 1) # Lakers won 1
        self.assertEqual(h2h["team1_scored"], 75 + 68 + 60)
        self.assertEqual(h2h["team2_scored"], 70 + 82 + 58)

    # F3.3: Fair-Play Standings and Custom Rules
    def test_fair_play_standings(self):
        teams = [{"id": 1, "name": "Gentle FC"}, {"id": 2, "name": "Aggressive FC"}]
        events = [
            {"team_id": 1, "event_type": "yellow_card", "count": 1},
            {"team_id": 2, "event_type": "yellow_card", "count": 3},
            {"team_id": 2, "event_type": "red_card", "count": 1}
        ]
        # Default: yellow=1, red=3
        rules = {"yellow_card_points": 1.0, "red_card_points": 3.0}
        fp = SportsEngine.calculate_fair_play(teams, events, rules)
        # Gentle FC: 1 pt (rank 1)
        self.assertEqual(fp[0]["name"], "Gentle FC")
        self.assertEqual(fp[0]["penalty_points"], 1.0)
        self.assertEqual(fp[0]["rank"], 1)
        # Aggressive FC: 3*1 + 1*3 = 6 pts (rank 2)
        self.assertEqual(fp[1]["name"], "Aggressive FC")
        self.assertEqual(fp[1]["penalty_points"], 6.0)
        self.assertEqual(fp[1]["rank"], 2)

    def test_basketball_fair_play_fouls(self):
        teams = [{"id": 1, "name": "Bulls"}, {"id": 2, "name": "Lakers"}]
        events = [
            {"team_id": 1, "event_type": "foul", "count": 2},
            {"team_id": 2, "event_type": "technical_foul", "count": 1},
            {"team_id": 2, "event_type": "unsportsmanlike_foul", "count": 1}
        ]
        rules = {"foul_points": 0.5, "suspension_points": 2.0, "red_card_points": 3.0}
        fp = SportsEngine.calculate_fair_play(teams, events, rules, sport="basketball")
        self.assertEqual(fp[0]["name"], "Bulls")
        self.assertEqual(fp[0]["penalty_points"], 1.0)
        self.assertEqual(fp[0]["fouls"], 2)
        self.assertEqual(fp[1]["name"], "Lakers")
        self.assertEqual(fp[1]["penalty_points"], 5.0)
        self.assertEqual(fp[1]["technical_fouls"], 1)
        self.assertEqual(fp[1]["unsportsmanlike_fouls"], 1)

    # F4.1: Predictions Game (3 pts exact, 1 pt good outcome)
    def test_predictions_scoring(self):
        t_id = self.db.create_tournament("Tournoi Pred", "football")
        t1 = self.db.create_team(t_id, "T1")
        t2 = self.db.create_team(t_id, "T2")
        m_id = self.db.create_match(t_id, t1, t2, "J1")

        # Student 1: predicts 2 - 1 (Exact score)
        self.db.submit_prediction(t_id, m_id, "Alice", "Informatique", 2, 1)
        # Student 2: predicts 3 - 0 (Correct outcome win for home, but not exact score)
        self.db.submit_prediction(t_id, m_id, "Bob", "Meca", 3, 0)
        # Student 3: predicts 1 - 2 (Wrong outcome)
        self.db.submit_prediction(t_id, m_id, "Charlie", "Civil", 1, 2)

        # Match finishes 2 - 1
        self.db.update_match_score(m_id, 2, 1, status="finished")

        board = self.db.get_predictions_leaderboard(t_id)
        students = {s["student_name"]: s for s in board["students"]}

        self.assertEqual(students["Alice"]["total_points"], 3)
        self.assertEqual(students["Alice"]["exact_scores"], 1)
        self.assertEqual(students["Bob"]["total_points"], 1)
        self.assertEqual(students["Bob"]["good_outcomes"], 1)
        self.assertEqual(students["Charlie"]["total_points"], 0)

    # F4.2: Fan MVP Vote (1 vote per visitor/IP)
    def test_fan_mvp_vote_unique(self):
        t_id = self.db.create_tournament("Tournoi MVP", "football")
        t1 = self.db.create_team(t_id, "T1")
        t2 = self.db.create_team(t_id, "T2")
        p1 = self.db.create_player(t1, "Star Player", 10)
        m_id = self.db.create_match(t_id, t1, t2, "J1")

        # First vote succeeds
        v1 = self.db.submit_mvp_vote(m_id, p1, "192.168.1.50", "fp_123")
        self.assertTrue(v1)

        # Second vote from same IP/fingerprint must be rejected
        v2 = self.db.submit_mvp_vote(m_id, p1, "192.168.1.50", "fp_123")
        self.assertFalse(v2)

        votes = self.db.get_match_mvp_votes(m_id)
        self.assertEqual(votes["total_votes"], 1)
        self.assertEqual(votes["winner"]["player_name"], "Star Player")

    # F4.3: School Journalism Reports & Moderation
    def test_journalism_report_workflow(self):
        t_id = self.db.create_tournament("Tournoi Media", "football")
        t1 = self.db.create_team(t_id, "T1")
        t2 = self.db.create_team(t_id, "T2")
        m_id = self.db.create_match(t_id, t1, t2, "J1")

        # Submit report
        rep_id = self.db.submit_match_report(m_id, "Paul", "Club Média", "Victoire éclatante", "Superbe match...")
        self.assertGreater(rep_id, 0)

        # Initially status is pending
        reports = self.db.list_match_reports(m_id)
        self.assertEqual(reports[0]["status"], "pending")

        # Admin approves
        self.db.review_match_report(rep_id, "approved", "Admin Sports")
        approved_reports = self.db.list_match_reports(m_id, status="approved")
        self.assertEqual(len(approved_reports), 1)
        self.assertEqual(approved_reports[0]["title"], "Victoire éclatante")
        self.assertEqual(approved_reports[0]["reviewed_by"], "Admin Sports")

    # F4.4: Automatic Team Badges
    def test_team_badges(self):
        standings = [
            {"team_id": 1, "rank": 1, "played": 3, "won": 3, "lost": 0, "scored": 15, "conceded": 2},
            {"team_id": 2, "rank": 2, "played": 3, "won": 1, "lost": 2, "scored": 6, "conceded": 10}
        ]
        fair_play = [
            {"team_id": 1, "penalty_points": 0.0}
        ]
        badges = SportsEngine.calculate_team_badges(1, standings, fair_play)
        badge_ids = [b["id"] for b in badges]
        self.assertIn("invincible", badge_ids) # 0 losses in 3 games
        self.assertIn("leader", badge_ids)     # 1st in standings
        self.assertIn("best_attack", badge_ids) # 15 goals scored
        self.assertIn("best_defense", badge_ids) # 2 goals conceded
        self.assertIn("fair_play", badge_ids)  # 0 penalty points

    # F5.1: Scheduler with rest days and exam exclusions
    def test_scheduler_optimization(self):
        teams = [{"id": 1, "name": "A"}, {"id": 2, "name": "B"}, {"id": 3, "name": "C"}, {"id": 4, "name": "D"}]
        res = TournamentScheduler.optimize_schedule(
            teams=teams,
            venues=["Stade A", "Stade B"],
            start_date="2026-11-15",
            min_rest_days=2,
            exam_dates=["2026-11-18"] # Excluded date
        )
        self.assertEqual(res["total_matches"], 6)
        match_dates = [m["match_date"] for m in res["schedule"]]
        self.assertNotIn("2026-11-18", match_dates) # Exam date avoided!

    # F5.2: CSV Importer Dry-run and Commit
    def test_csv_importer(self):
        sample_csv = """type;ecole_filiere;equipe_nom;equipe_abreviation;equipe_couleur;joueur_nom;joueur_numero;joueur_poste
equipe;Génie Info;Info Warriors;INF;#123456;;;
joueur;;Info Warriors;;;Arthur;7;Meneur
"""
        parsed = CsvImporter.parse_and_validate(sample_csv, [])
        self.assertTrue(parsed["success"])
        self.assertEqual(parsed["accepted_count"], 2)
        self.assertEqual(parsed["rejected_count"], 0)

        t_id = self.db.create_tournament("Tournoi CSV", "basketball")
        res = CsvImporter.execute_commit(t_id, parsed, self.db)
        self.assertEqual(res["created_teams"], 1)
        self.assertEqual(res["created_players"], 1)

    # F5.4: Database Backups with 14-days retention
    def test_database_backups(self):
        filename = self.db.create_backup("test")
        self.assertTrue(filename.startswith("backup_tournament_"))
        backups = self.db.list_backups()
        self.assertGreaterEqual(len(backups), 1)

    # F6.5: Immutable Audit Logs
    def test_audit_logs(self):
        self.db.log_audit("arbitre", "M. Kamga", "update_score", "match", 12, "0-0", "2-1", "Score validé")
        logs = self.db.list_audit_logs(limit=10)
        self.assertGreaterEqual(len(logs), 1)
        self.assertEqual(logs[0]["author_name"], "M. Kamga")
        self.assertEqual(logs[0]["action_type"], "update_score")
        self.assertEqual(logs[0]["new_value"], "2-1")


if __name__ == "__main__":
    unittest.main()
