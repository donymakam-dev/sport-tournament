"""
CSV Importer with Line-by-Line Validation and Dry-Run Reporting (F5.2).
Allows batch importing of schools/filieres, teams, and players from CSV files.
Provides downloadable templates and detailed reports before committing changes.
"""

import csv
import io
from typing import List, Dict, Any, Tuple


class CsvImporter:
    @classmethod
    def get_template_csv(cls) -> str:
        """Returns standard CSV template header and sample rows."""
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow([
            "type",
            "ecole_filiere",
            "equipe_nom",
            "equipe_abreviation",
            "equipe_couleur",
            "joueur_nom",
            "joueur_numero",
            "joueur_poste"
        ])
        writer.writerow([
            "equipe",
            "Génie Informatique",
            "Génie Info Lakers",
            "INF",
            "#7c3aed",
            "",
            "",
            ""
        ])
        writer.writerow([
            "joueur",
            "",
            "Génie Info Lakers",
            "",
            "",
            "NGOUE Nathalie",
            "10",
            "Meneuse"
        ])
        writer.writerow([
            "joueur",
            "",
            "Génie Info Lakers",
            "",
            "",
            "BEKOLO Steve",
            "30",
            "Ailier"
        ])
        writer.writerow([
            "equipe",
            "Génie Mécatronique",
            "Mécatronique Bulls",
            "MEC",
            "#dc2626",
            "",
            "",
            ""
        ])
        writer.writerow([
            "joueur",
            "",
            "Mécatronique Bulls",
            "",
            "",
            "KAMGA Jean-Paul",
            "23",
            "Arrière"
        ])
        return output.getvalue()

    @classmethod
    def parse_and_validate(cls, csv_text: str, existing_teams: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Parses CSV and validates each row.
        Returns a detailed report of accepted rows and rejected rows with reasons.
        """
        if not csv_text or not csv_text.strip():
            return {
                "success": False,
                "error": "Le fichier CSV est vide.",
                "accepted_count": 0,
                "rejected_count": 0,
                "report": []
            }

        # Auto-detect delimiter (, or ;)
        first_line = csv_text.strip().splitlines()[0]
        delimiter = ';' if ';' in first_line else ','

        reader = csv.reader(io.StringIO(csv_text.strip()), delimiter=delimiter)
        rows = list(reader)

        if not rows:
            return {"success": False, "error": "Aucune ligne trouvée dans le CSV."}

        header = [col.strip().lower() for col in rows[0]]
        # Required columns check
        required_cols = ["type", "equipe_nom"]
        for req in required_cols:
            if req not in header:
                return {
                    "success": False,
                    "error": f"Colonne obligatoire manquante dans l'en-tête CSV : '{req}'.",
                    "header_found": header
                }

        col_map = {name: idx for idx, name in enumerate(header)}

        existing_team_names = {t["name"].lower().strip(): t for t in existing_teams}
        parsed_teams: Dict[str, Dict[str, Any]] = {}
        parsed_players: List[Dict[str, Any]] = []

        report: List[Dict[str, Any]] = []
        accepted_count = 0
        rejected_count = 0

        for line_num, row in enumerate(rows[1:], start=2):
            if not row or all(c.strip() == "" for c in row):
                continue

            def get_val(col_name: str) -> str:
                idx = col_map.get(col_name)
                return row[idx].strip() if idx is not None and idx < len(row) else ""

            row_type = get_val("type").lower()
            team_name = get_val("equipe_nom")

            if not row_type:
                rejected_count += 1
                report.append({
                    "line": line_num,
                    "status": "rejected",
                    "reason": "Colonne 'type' vide (doit valoir 'equipe' ou 'joueur').",
                    "data": row
                })
                continue

            if not team_name:
                rejected_count += 1
                report.append({
                    "line": line_num,
                    "status": "rejected",
                    "reason": "Nom de l'équipe manquant.",
                    "data": row
                })
                continue

            if row_type == "equipe":
                team_key = team_name.lower()
                if team_key in parsed_teams or team_key in existing_team_names:
                    rejected_count += 1
                    report.append({
                        "line": line_num,
                        "status": "rejected",
                        "reason": f"Doublon : L'équipe '{team_name}' existe déjà dans ce tournoi ou dans ce fichier.",
                        "data": row
                    })
                    continue

                filiere = get_val("ecole_filiere")
                short_name = get_val("equipe_abreviation") or team_name[:3].upper()
                color = get_val("equipe_couleur") or "#1e3a8a"

                team_obj = {
                    "name": team_name,
                    "filiere": filiere,
                    "short_name": short_name,
                    "color": color
                }
                parsed_teams[team_key] = team_obj
                accepted_count += 1
                report.append({
                    "line": line_num,
                    "status": "accepted",
                    "type": "equipe",
                    "details": f"Équipe : {team_name} ({filiere})"
                })

            elif row_type == "joueur":
                player_name = get_val("joueur_nom")
                if not player_name:
                    rejected_count += 1
                    report.append({
                        "line": line_num,
                        "status": "rejected",
                        "reason": "Nom du joueur manquant.",
                        "data": row
                    })
                    continue

                raw_num = get_val("joueur_numero")
                try:
                    num = int(raw_num) if raw_num else 0
                    if num < 0 or num > 99:
                        num = 0
                except ValueError:
                    num = 0

                position = get_val("joueur_poste")

                player_obj = {
                    "team_name": team_name,
                    "name": player_name,
                    "number": num,
                    "position": position
                }
                parsed_players.append(player_obj)
                accepted_count += 1
                report.append({
                    "line": line_num,
                    "status": "accepted",
                    "type": "joueur",
                    "details": f"Joueur : #{num} {player_name} ({team_name})"
                })
            else:
                rejected_count += 1
                report.append({
                    "line": line_num,
                    "status": "rejected",
                    "reason": f"Type invalide '{row_type}' (attendu : 'equipe' ou 'joueur').",
                    "data": row
                })

        return {
            "success": True,
            "accepted_count": accepted_count,
            "rejected_count": rejected_count,
            "total_rows": len(rows) - 1,
            "teams_found": list(parsed_teams.values()),
            "players_found": parsed_players,
            "report": report
        }

    @classmethod
    def execute_commit(cls, tournament_id: int, parsed_result: Dict[str, Any], db_instance) -> Dict[str, Any]:
        """Commits accepted teams and players to SQLite database."""
        teams = parsed_result.get("teams_found", [])
        players = parsed_result.get("players_found", [])

        created_teams = 0
        created_players = 0

        # Mapping team_name.lower() -> team_id
        team_id_map: Dict[str, int] = {}

        # 1. Load existing teams
        for t in db_instance.list_teams(tournament_id):
            team_id_map[t["name"].lower().strip()] = t["id"]

        # 2. Insert new teams
        for t in teams:
            t_id = db_instance.create_team(
                tournament_id=tournament_id,
                name=t["name"],
                filiere=t.get("filiere", ""),
                short_name=t.get("short_name", ""),
                color=t.get("color", "#1e3a8a"),
                logo_url=""
            )
            team_id_map[t["name"].lower().strip()] = t_id
            created_teams += 1

        # 3. Insert players
        for p in players:
            t_key = p["team_name"].lower().strip()
            target_team_id = team_id_map.get(t_key)
            if target_team_id:
                db_instance.create_player(
                    team_id=target_team_id,
                    name=p["name"],
                    number=p.get("number", 0),
                    position=p.get("position", ""),
                    photo_url=""
                )
                created_players += 1

        db_instance.log_audit("admin", "Administrateur", "import_csv", "tournament", tournament_id,
                             "", f"{created_teams} équipes, {created_players} joueurs", "Import CSV validé")

        return {
            "created_teams": created_teams,
            "created_players": created_players
        }
