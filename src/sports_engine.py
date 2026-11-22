"""
Sports Calculation Engine
Computes standings, leaderboards (scorers, 3-pts, assists, rebounds, MVPs),
fair-play disciplinary rankings, automatic team badges, head-to-head comparisons,
and chart datasets for Football, Basketball, Handball, and Volleyball.
"""

from typing import List, Dict, Any, Optional


class SportsEngine:
    @classmethod
    def calculate_standings(cls, sport: str, teams: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Calculates standings table for a tournament according to official rules of the sport.
        """
        sport = sport.lower().strip()

        # Initialize table dict for all teams
        table: Dict[int, Dict[str, Any]] = {}
        for t in teams:
            table[t["id"]] = {
                "team_id": t["id"],
                "name": t["name"],
                "short_name": t.get("short_name", t["name"][:3].upper()),
                "filiere": t.get("filiere", ""),
                "color": t.get("color", "#1e3a8a"),
                "logo_url": t.get("logo_url", ""),
                "played": 0,
                "won": 0,
                "drawn": 0,
                "lost": 0,
                "scored": 0,    # Goals / Points / Sets For
                "conceded": 0,  # Goals / Points / Sets Against
                "diff": 0,
                "points": 0
            }

        finished_matches = [m for m in matches if m.get("status") == "finished" and m.get("score_home") is not None and m.get("score_away") is not None]

        for m in finished_matches:
            th_id = m["team_home_id"]
            ta_id = m["team_away_id"]
            sh = int(m["score_home"])
            sa = int(m["score_away"])

            if th_id not in table or ta_id not in table:
                continue

            th = table[th_id]
            ta = table[ta_id]

            th["played"] += 1
            ta["played"] += 1
            th["scored"] += sh
            th["conceded"] += sa
            ta["scored"] += sa
            ta["conceded"] += sh

            if sport == "basketball":
                # BASKETBALL RULES (Officiel FIBA / Exigence utilisateur):
                # Victoire = 2 pts, Défaite = 1 pt.
                if sh > sa:
                    th["won"] += 1
                    th["points"] += 2
                    ta["lost"] += 1
                    ta["points"] += 1
                else:
                    ta["won"] += 1
                    ta["points"] += 2
                    th["lost"] += 1
                    th["points"] += 1

            elif sport == "volleyball":
                # VOLLEYBALL RULES (Score en sets gagnés, ex: 3-1, 3-2):
                if sh > sa:
                    th["won"] += 1
                    ta["lost"] += 1
                    if sa == 2:  # Victoire 3-2
                        th["points"] += 2
                        ta["points"] += 1
                    else:        # Victoire 3-0 ou 3-1
                        th["points"] += 3
                        ta["points"] += 0
                else:
                    ta["won"] += 1
                    th["lost"] += 1
                    if sh == 2:  # Victoire 3-2
                        ta["points"] += 2
                        th["points"] += 1
                    else:        # Victoire 3-0 ou 3-1
                        ta["points"] += 3
                        th["points"] += 0

            elif sport == "handball":
                # HANDBALL RULES:
                # Victoire = 2 pts, Nul = 1 pt, Défaite = 0 pt
                if sh > sa:
                    th["won"] += 1
                    th["points"] += 2
                    ta["lost"] += 1
                elif sa > sh:
                    ta["won"] += 1
                    ta["points"] += 2
                    th["lost"] += 1
                else:
                    th["drawn"] += 1
                    ta["drawn"] += 1
                    th["points"] += 1
                    ta["points"] += 1

            else:
                # FOOTBALL (DEFAULT):
                # Victoire = 3 pts, Nul = 1 pt, Défaite = 0 pt
                if sh > sa:
                    th["won"] += 1
                    th["points"] += 3
                    ta["lost"] += 1
                elif sa > sh:
                    ta["won"] += 1
                    ta["points"] += 3
                    th["lost"] += 1
                else:
                    th["drawn"] += 1
                    ta["drawn"] += 1
                    th["points"] += 1
                    ta["points"] += 1

        # Calculate diff
        for entry in table.values():
            entry["diff"] = entry["scored"] - entry["conceded"]

        # Sort standings: Points DESC, Diff DESC, Scored DESC, Name ASC
        standings_list = list(table.values())
        standings_list.sort(key=lambda x: (
            -x["points"],
            -x["diff"],
            -x["scored"],
            x["name"]
        ))

        # Assign rank position
        for i, entry in enumerate(standings_list, start=1):
            entry["rank"] = i

        return standings_list

    @classmethod
    def calculate_leaderboards(cls, sport: str, events: List[Dict[str, Any]], matches: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates individual leaders:
        - Basketball: Points, 3-points, Assists, Rebounds, MVPs
        - Football: Goals, Assists, Cards, MVPs
        - Handball: Goals, 7m, 2min, MVPs
        - Volleyball: MVPs
        """
        sport = sport.lower().strip()

        scorers: Dict[int, Dict[str, Any]] = {}
        three_pointers: Dict[int, Dict[str, Any]] = {}
        assists: Dict[int, Dict[str, Any]] = {}
        rebounds: Dict[int, Dict[str, Any]] = {}
        mvp_counts: Dict[int, Dict[str, Any]] = {}

        # 1. Process Events
        for ev in events:
            pid = ev["player_id"]
            pname = ev.get("player_name", "Joueur")
            tname = ev.get("team_name", "Équipe")
            pnum = ev.get("player_number", 0)
            etype = ev.get("event_type", "")
            count = ev.get("count", 1)

            base_info = {
                "player_id": pid,
                "player_name": pname,
                "team_name": tname,
                "player_number": pnum,
                "total": 0
            }

            if etype in ("point", "goal"):
                scorers.setdefault(pid, dict(base_info))["total"] += count
            elif etype == "three_pointer":
                three_pointers.setdefault(pid, dict(base_info))["total"] += count
            elif etype == "assist":
                assists.setdefault(pid, dict(base_info))["total"] += count
            elif etype == "rebound":
                rebounds.setdefault(pid, dict(base_info))["total"] += count

        # 2. Process MVPs from matches
        for m in matches:
            if m.get("status") == "finished" and m.get("mvp_player_id"):
                pid = m["mvp_player_id"]
                pname = m.get("mvp_name", "Joueur")
                photo = m.get("mvp_photo", "")

                if pid not in mvp_counts:
                    mvp_counts[pid] = {
                        "player_id": pid,
                        "player_name": pname,
                        "photo_url": photo,
                        "total": 0
                    }
                mvp_counts[pid]["total"] += 1

        def sort_and_rank(d: Dict[int, Dict[str, Any]]) -> List[Dict[str, Any]]:
            res = sorted(d.values(), key=lambda x: -x["total"])
            for idx, item in enumerate(res, start=1):
                item["rank"] = idx
            return res

        return {
            "scorers": sort_and_rank(scorers),
            "three_pointers": sort_and_rank(three_pointers) if sport == "basketball" else [],
            "assists": sort_and_rank(assists),
            "rebounds": sort_and_rank(rebounds) if sport == "basketball" else [],
            "mvps": sort_and_rank(mvp_counts)
        }

    # ---------------- F3.3 : CLASSEMENT FAIR-PLAY ----------------
    @classmethod
    def calculate_fair_play(cls, teams: List[Dict[str, Any]], events: List[Dict[str, Any]], rules: Dict[str, Any], sport: str = "football") -> List[Dict[str, Any]]:
        """
        Calculates Fair-Play standings based on sanctions according to the sport discipline:
        - Basketball: Personal fouls, Technical fouls, Unsportsmanlike / Disqualifying fouls (NO cards).
        - Football: Yellow cards, Red cards, Fouls.
        - Handball: Yellow cards, 2min suspensions, Red cards / disqualifications.
        - Volleyball: Yellow cards, Red cards.
        Team with LEAST penalty points is ranked 1st.
        """
        yellow_w = float(rules.get("yellow_card_points", 1.0))
        red_w = float(rules.get("red_card_points", 3.0))
        susp_w = float(rules.get("suspension_points", 2.0))
        foul_w = float(rules.get("foul_points", 0.5))
        sport_clean = sport.lower().strip() if sport else "football"

        fp_map: Dict[int, Dict[str, Any]] = {}
        for t in teams:
            fp_map[t["id"]] = {
                "team_id": t["id"],
                "name": t["name"],
                "short_name": t.get("short_name", t["name"][:3].upper()),
                "filiere": t.get("filiere", ""),
                "color": t.get("color", "#1e3a8a"),
                "logo_url": t.get("logo_url", ""),
                "yellow_cards": 0,
                "red_cards": 0,
                "suspensions": 0,
                "fouls": 0,
                "technical_fouls": 0,
                "unsportsmanlike_fouls": 0,
                "disqualifying_fouls": 0,
                "penalty_points": 0.0
            }

        for ev in events:
            tid = ev.get("team_id")
            if tid not in fp_map:
                continue
            etype = ev.get("event_type", "")
            cnt = ev.get("count", 1)

            if etype in ("yellow_card", "avertissement"):
                fp_map[tid]["yellow_cards"] += cnt
            elif etype in ("red_card", "expulsion"):
                fp_map[tid]["red_cards"] += cnt
            elif etype in ("suspension_2min", "suspension"):
                fp_map[tid]["suspensions"] += cnt
            elif etype in ("technical_foul", "faute_technique"):
                fp_map[tid]["technical_fouls"] += cnt
            elif etype in ("unsportsmanlike_foul", "faute_antisportive", "anti_sportive"):
                fp_map[tid]["unsportsmanlike_fouls"] += cnt
            elif etype in ("disqualifying_foul", "faute_disqualifiante"):
                fp_map[tid]["disqualifying_fouls"] += cnt
            elif etype in ("foul", "faute", "personal_foul"):
                fp_map[tid]["fouls"] += cnt

        # Compute total penalty points
        for entry in fp_map.values():
            if sport_clean == "basketball":
                # Basketball: no cards, penalty points based on fouls, technicals, antisportives
                tech_w = susp_w if susp_w > 0 else 2.0
                antisp_w = red_w if red_w > 0 else 3.0
                disq_w = antisp_w + 2.0
                pts = (entry["fouls"] * foul_w +
                       entry["technical_fouls"] * tech_w +
                       entry["unsportsmanlike_fouls"] * antisp_w +
                       entry["disqualifying_fouls"] * disq_w)
            else:
                pts = (entry["yellow_cards"] * yellow_w +
                       entry["red_cards"] * red_w +
                       entry["suspensions"] * susp_w +
                       entry["technical_fouls"] * susp_w +
                       entry["unsportsmanlike_fouls"] * red_w +
                       entry["disqualifying_fouls"] * (red_w + 2.0) +
                       entry["fouls"] * foul_w)
            entry["penalty_points"] = round(pts, 1)

        # Sort: least penalty points first
        if sport_clean == "basketball":
            ranked = sorted(fp_map.values(), key=lambda x: (
                x["penalty_points"],
                x["disqualifying_fouls"],
                x["unsportsmanlike_fouls"],
                x["technical_fouls"],
                x["fouls"],
                x["name"]
            ))
        else:
            ranked = sorted(fp_map.values(), key=lambda x: (
                x["penalty_points"],
                x["red_cards"],
                x["yellow_cards"],
                x["fouls"],
                x["name"]
            ))

        for idx, item in enumerate(ranked, start=1):
            item["rank"] = idx

        return ranked

    # ---------------- F4.4 : BADGES AUTOMATIQUES ----------------
    @classmethod
    def calculate_team_badges(cls, team_id: int, standings: List[Dict[str, Any]], fair_play_list: List[Dict[str, Any]]) -> List[Dict[str, str]]:
        """
        Determines automatic badges for a team:
        - 🛡️ Meilleure Défense (least conceded goals/points)
        - ⚡ Invaincu (0 losses, minimum 2 games)
        - 🔥 Attaque de Feu (most scored goals/points)
        - 🤝 Fair-Play d'Or (ranked 1st in fair-play)
        """
        badges = []
        if not standings:
            return badges

        # Find team in standings
        team_entry = next((s for s in standings if s["team_id"] == team_id), None)
        if not team_entry or team_entry.get("played", 0) == 0:
            return badges

        # 1. Invaincu (0 losses, min 2 games)
        if team_entry.get("played", 0) >= 2 and team_entry.get("lost", 0) == 0:
            badges.append({
                "id": "invincible",
                "label": "⚡ Invaincu",
                "color": "#8b5cf6",
                "description": f"Aucune défaite en {team_entry['played']} matchs joués !"
            })

        # 2. Leader du Championnat (1er au classement avec au moins 1 match)
        if team_entry.get("rank") == 1 and team_entry.get("played", 0) >= 1:
            badges.append({
                "id": "leader",
                "label": "👑 Leader",
                "color": "#eab308",
                "description": "Actuellement en tête du championnat."
            })

        # 3. Meilleure Attaque
        max_scored = max((s.get("scored", 0) for s in standings), default=0)
        if max_scored > 0 and team_entry.get("scored", 0) == max_scored:
            badges.append({
                "id": "best_attack",
                "label": "🔥 Attaque de Feu",
                "color": "#ef4444",
                "description": f"Attaque la plus prolifique avec {max_scored} points/buts inscrits."
            })

        # 4. Meilleure Défense
        played_teams = [s for s in standings if s.get("played", 0) > 0]
        if played_teams:
            min_conceded = min(s.get("conceded", 0) for s in played_teams)
            if team_entry.get("conceded", 0) == min_conceded:
                badges.append({
                    "id": "best_defense",
                    "label": "🛡️ Meilleure Défense",
                    "color": "#0284c7",
                    "description": f"Défense la plus solide avec seulement {min_conceded} points/buts concédés."
                })

        # 5. Fair-Play d'Or
        if fair_play_list:
            fp_first = fair_play_list[0]
            if fp_first.get("team_id") == team_id and fp_first.get("penalty_points", 0) <= 2.0:
                badges.append({
                    "id": "fair_play",
                    "label": "🤝 Fair-Play d'Or",
                    "color": "#10b981",
                    "description": f"Équipe exemplaire au classement de la discipline ({fp_first['penalty_points']} pts)."
                })

        return badges

    # ---------------- F3.2 : HISTORIQUE DES CONFRONTATIONS (HEAD-TO-HEAD) ----------------
    @classmethod
    def calculate_head_to_head(cls, team1_id: int, team2_id: int, all_matches: List[Dict[str, Any]], all_teams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculates Head-to-Head statistics between two teams across all matches.
        """
        t1 = next((t for t in all_teams if t["id"] == team1_id), None)
        t2 = next((t for t in all_teams if t["id"] == team2_id), None)

        if not t1 or not t2:
            return {"error": "Équipes introuvables"}

        direct_matches = []
        t1_wins = 0
        t2_wins = 0
        draws = 0
        t1_scored = 0
        t2_scored = 0

        for m in all_matches:
            th_id = m.get("team_home_id")
            ta_id = m.get("team_away_id")

            # Check if this match is between team1 and team2
            if (th_id == team1_id and ta_id == team2_id) or (th_id == team2_id and ta_id == team1_id):
                sh = m.get("score_home")
                sa = m.get("score_away")

                match_info = dict(m)
                if sh is not None and sa is not None and m.get("status") == "finished":
                    sh = int(sh)
                    sa = int(sa)

                    if th_id == team1_id:
                        s1, s2 = sh, sa
                    else:
                        s1, s2 = sa, sh

                    t1_scored += s1
                    t2_scored += s2

                    if s1 > s2:
                        t1_wins += 1
                        match_info["winner_id"] = team1_id
                    elif s2 > s1:
                        t2_wins += 1
                        match_info["winner_id"] = team2_id
                    else:
                        draws += 1
                        match_info["winner_id"] = None

                direct_matches.append(match_info)

        return {
            "team1": t1,
            "team2": t2,
            "total_matches": len(direct_matches),
            "team1_wins": t1_wins,
            "team2_wins": t2_wins,
            "draws": draws,
            "team1_scored": t1_scored,
            "team2_scored": t2_scored,
            "matches": direct_matches
        }

    # ---------------- F3.1 : GRAPHIQUES CHART.JS (ÉVOLUTION, BUTS, FORME) ----------------
    @classmethod
    def calculate_team_charts_data(cls, team_id: int, matches: List[Dict[str, Any]], sport: str) -> Dict[str, Any]:
        """
        Generates structured data for the 3 team charts:
        1. Points evolution by matchday
        2. Scored & Conceded goals/points by matchday
        3. Form of the last 5 matches (W/D/L)
        """
        sport = sport.lower().strip()
        finished = [
            m for m in matches
            if m.get("status") == "finished"
            and (m.get("team_home_id") == team_id or m.get("team_away_id") == team_id)
            and m.get("score_home") is not None
            and m.get("score_away") is not None
        ]

        # Sort chronologically
        finished.sort(key=lambda x: (x.get("match_date", ""), x.get("id", 0)))

        labels = []
        points_evolution = []
        scored_per_day = []
        conceded_per_day = []
        form_matches = []

        cumulative_pts = 0

        for idx, m in enumerate(finished, start=1):
            day_label = m.get("round_name") or f"J{idx}"
            labels.append(day_label)

            is_home = (m["team_home_id"] == team_id)
            my_score = int(m["score_home"] if is_home else m["score_away"])
            opp_score = int(m["score_away"] if is_home else m["score_home"])
            opp_name = m.get("team_away_name" if is_home else "team_home_name", "Adversaire")

            scored_per_day.append(my_score)
            conceded_per_day.append(opp_score)

            # Determine points gained based on sport
            match_outcome = "D"
            if sport == "basketball":
                if my_score > opp_score:
                    pts = 2
                    match_outcome = "V"
                else:
                    pts = 1
                    match_outcome = "D"
            elif sport == "volleyball":
                if my_score > opp_score:
                    match_outcome = "V"
                    pts = 2 if opp_score == 2 else 3
                else:
                    match_outcome = "D"
                    pts = 1 if my_score == 2 else 0
            elif sport == "handball":
                if my_score > opp_score:
                    match_outcome = "V"
                    pts = 2
                elif my_score == opp_score:
                    match_outcome = "N"
                    pts = 1
                else:
                    match_outcome = "D"
                    pts = 0
            else:
                # Football
                if my_score > opp_score:
                    match_outcome = "V"
                    pts = 3
                elif my_score == opp_score:
                    match_outcome = "N"
                    pts = 1
                else:
                    match_outcome = "D"
                    pts = 0

            cumulative_pts += pts
            points_evolution.append(cumulative_pts)

            form_matches.append({
                "outcome": match_outcome, # 'V', 'N', 'D'
                "score_text": f"{my_score}-{opp_score}",
                "opponent": opp_name,
                "round": day_label,
                "date": m.get("match_date", "")
            })

        # Form of the last 5 matches
        recent_form = form_matches[-5:] if len(form_matches) >= 5 else form_matches

        return {
            "labels": labels,
            "points_evolution": points_evolution,
            "scored_per_day": scored_per_day,
            "conceded_per_day": conceded_per_day,
            "form": recent_form
        }
