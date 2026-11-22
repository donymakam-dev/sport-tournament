"""
Static Site Exporter for Free Hosting (Cloudflare Pages, GitHub Pages) (F6.6).
Exports all active tournament data, standings, fixtures, and leaders to static JSON files
so the public site can run 100% serverless at 0 FCFA cost.
"""

import os
import json
import shutil
from database import Database
from sports_engine import SportsEngine

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DIST_DIR = os.path.join(BASE_DIR, "dist")
STATIC_SRC = os.path.join(os.path.dirname(__file__), "static")


def export_static_site():
    print(f"Exporting static site to: {DIST_DIR}")
    if os.path.exists(DIST_DIR):
        shutil.rmtree(DIST_DIR)
    os.makedirs(DIST_DIR, exist_ok=True)

    # 1. Copy static web assets
    shutil.copytree(STATIC_SRC, DIST_DIR, dirs_exist_ok=True)

    # 2. Export API endpoints as static JSON
    api_dir = os.path.join(DIST_DIR, "api")
    os.makedirs(api_dir, exist_ok=True)

    db = Database()
    tournaments = db.list_tournaments()
    with open(os.path.join(api_dir, "tournaments.json"), "w", encoding="utf-8") as f:
        json.dump(tournaments, f, ensure_ascii=False, indent=2)

    for t in tournaments:
        t_id = t["id"]
        t_dir = os.path.join(api_dir, "tournament", str(t_id))
        os.makedirs(t_dir, exist_ok=True)

        teams = db.list_teams(t_id)
        players = db.list_tournament_players(t_id)
        matches = db.list_matches(t_id)
        awards = db.list_weekly_awards(t_id)
        all_events = []
        for m in matches:
            all_events.extend(db.list_match_events(m["id"]))

        standings = SportsEngine.calculate_standings(t["sport"], teams, matches)
        leaders = SportsEngine.calculate_leaderboards(t["sport"], all_events, matches)
        fp_rules = db.get_fair_play_rules(t_id)
        fair_play = SportsEngine.calculate_fair_play(teams, all_events, fp_rules)

        for tm in teams:
            tm["badges"] = SportsEngine.calculate_team_badges(tm["id"], standings, fair_play)

        full_data = {
            "tournament": t,
            "teams": teams,
            "players": players,
            "matches": matches,
            "standings": standings,
            "leaders": leaders,
            "fair_play": fair_play,
            "fair_play_rules": fp_rules,
            "awards": awards
        }

        with open(os.path.join(t_dir, "full.json"), "w", encoding="utf-8") as f:
            json.dump(full_data, f, ensure_ascii=False, indent=2)

    print("Static site exported successfully to dist/")


if __name__ == "__main__":
    export_static_site()
