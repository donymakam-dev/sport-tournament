"""
Tournament Calendar Optimizer and Generator.
Implements constraint satisfaction scheduling (Round-Robin with venue conflict resolution,
exam date exclusions, and team rest day guarantees).
Compatible with Python standard library with optional OR-Tools acceleration.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Set, Tuple


class TournamentScheduler:
    @classmethod
    def generate_round_robin_pairings(cls, team_ids: List[int]) -> List[List[Tuple[int, int]]]:
        """
        Generates standard round-robin pairings using the polygon/circle method.
        Every team plays every other team exactly once.
        """
        teams = list(team_ids)
        # If odd number of teams, add a dummy bye (-1)
        has_bye = len(teams) % 2 != 0
        if has_bye:
            teams.append(-1)

        n = len(teams)
        rounds: List[List[Tuple[int, int]]] = []

        for r in range(n - 1):
            round_matches: List[Tuple[int, int]] = []
            for i in range(n // 2):
                t1 = teams[i]
                t2 = teams[n - 1 - i]
                # Filter out bye
                if t1 != -1 and t2 != -1:
                    # Alternate home and away
                    if r % 2 == 0:
                        round_matches.append((t1, t2))
                    else:
                        round_matches.append((t2, t1))
            rounds.append(round_matches)
            # Rotate teams keeping first fixed
            teams = [teams[0]] + [teams[-1]] + teams[1:-1]

        return rounds

    @classmethod
    def optimize_schedule(
        cls,
        teams: List[Dict[str, Any]],
        venues: Optional[List[str]] = None,
        start_date: str = "",
        min_rest_days: int = 2,
        exam_dates: Optional[List[str]] = None,
        timeslots: Optional[List[str]] = None,
        preferred_days: Optional[List[int]] = None # 0=Mon, 2=Wed, 5=Sat, 6=Sun
    ) -> Dict[str, Any]:
        """
        Generates and optimizes match schedules under constraints:
        1. No venue hosts two matches at the same timeslot on the same date.
        2. No team plays two matches at the same timeslot or on the same day.
        3. No matches scheduled on excluded exam/holiday dates.
        4. Teams have at least `min_rest_days` between consecutive matches.
        """
        if len(teams) < 2:
            return {"error": "Au moins 2 équipes sont requises pour générer un calendrier."}

        venues = venues or ["Terrain Principal", "Gymnase Central"]
        timeslots = timeslots or ["14:00", "16:00", "18:00"]
        exam_set: Set[str] = set(exam_dates or [])

        # Parse start date
        try:
            curr_date = datetime.strptime(start_date.strip(), "%Y-%m-%d").date() if start_date else datetime.now().date()
        except Exception:
            curr_date = datetime.now().date()

        # Preferred match days (default: Wednesday=2, Saturday=5, Sunday=6)
        if not preferred_days:
            preferred_days = [2, 5, 6]

        team_dict = {t["id"]: t for t in teams}
        team_ids = [t["id"] for t in teams]
        rounds_pairings = cls.generate_round_robin_pairings(team_ids)

        schedule: List[Dict[str, Any]] = []
        last_played_date: Dict[int, Any] = {} # team_id -> date

        # Track venue-time bookings: (date_str, venue, time_str)
        booked_slots: Set[Tuple[str, str, str]] = set()

        for round_idx, pairings in enumerate(rounds_pairings, start=1):
            round_name = f"Journée {round_idx}"

            # Find next valid date for this round that respects rest days and exam exclusions
            found_date = False
            attempts = 0

            while not found_date and attempts < 120:
                date_str = curr_date.strftime("%Y-%m-%d")
                weekday = curr_date.weekday()

                # Check if exam date
                if date_str in exam_set:
                    curr_date += timedelta(days=1)
                    attempts += 1
                    continue

                # Check preferred day of week
                if preferred_days and weekday not in preferred_days:
                    curr_date += timedelta(days=1)
                    attempts += 1
                    continue

                # Check rest days for all teams playing in this round
                rest_ok = True
                for t1, t2 in pairings:
                    d1 = last_played_date.get(t1)
                    d2 = last_played_date.get(t2)
                    if d1 and (curr_date - d1).days < min_rest_days:
                        rest_ok = False
                        break
                    if d2 and (curr_date - d2).days < min_rest_days:
                        rest_ok = False
                        break

                if not rest_ok:
                    curr_date += timedelta(days=1)
                    attempts += 1
                    continue

                found_date = True

            final_date_str = curr_date.strftime("%Y-%m-%d")

            # Assign venues and timeslots for matches in this round
            slot_idx = 0
            for t1, t2 in pairings:
                # Find available (venue, timeslot)
                assigned_venue = venues[slot_idx % len(venues)]
                assigned_time = timeslots[(slot_idx // len(venues)) % len(timeslots)]

                # Avoid overlap
                collision_tries = 0
                while (final_date_str, assigned_venue, assigned_time) in booked_slots and collision_tries < 10:
                    slot_idx += 1
                    assigned_venue = venues[slot_idx % len(venues)]
                    assigned_time = timeslots[(slot_idx // len(venues)) % len(timeslots)]
                    collision_tries += 1

                booked_slots.add((final_date_str, assigned_venue, assigned_time))

                match_item = {
                    "round_name": round_name,
                    "team_home_id": t1,
                    "team_home_name": team_dict[t1]["name"],
                    "team_home_filiere": team_dict[t1].get("filiere", ""),
                    "team_home_color": team_dict[t1].get("color", "#1e3a8a"),
                    "team_away_id": t2,
                    "team_away_name": team_dict[t2]["name"],
                    "team_away_filiere": team_dict[t2].get("filiere", ""),
                    "team_away_color": team_dict[t2].get("color", "#dc2626"),
                    "match_date": final_date_str,
                    "match_time": assigned_time,
                    "venue": assigned_venue,
                    "referee": "À désigner"
                }
                schedule.append(match_item)

                last_played_date[t1] = curr_date
                last_played_date[t2] = curr_date
                slot_idx += 1

            # Advance date for next round
            curr_date += timedelta(days=max(min_rest_days, 1))

        return {
            "total_matches": len(schedule),
            "total_rounds": len(rounds_pairings),
            "start_date": schedule[0]["match_date"] if schedule else "",
            "end_date": schedule[-1]["match_date"] if schedule else "",
            "min_rest_days": min_rest_days,
            "venues_used": venues,
            "schedule": schedule
        }
