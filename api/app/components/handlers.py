import json
import os
from collections import defaultdict
from decimal import Decimal
from typing import Any, cast

from fastapi import HTTPException, UploadFile
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import Driver, QualifyingResult, RaceResult, Round, Session
from queries import get_category, get_championship, get_teams, save_results

URL = os.environ["DB_URL"]

engine = create_engine(url=URL)
SQLASession = sessionmaker(engine)


def get_categories(championship_id: int | str | None):
    session = SQLASession()

    if championship_id == "latest":
        championship_id = None
    elif isinstance(championship_id, str):
        championship_id = int(championship_id)

    championship = get_championship(session, championship_id)

    if not championship:
        return []

    categories: list[dict[str, Any]] = []
    for i, category in enumerate(championship.categories):
        categories.append(
            {
                "category_id": category.id,
                "category_name": category.name,
                "championship": category.championship_id,
                "order": i,
            }
        )

    session.close()

    return categories


def get_calendar(category_id: int):
    session = SQLASession()

    category = get_category(session=session, category_id=category_id)

    if not category:
        return

    calendar: list[dict[str, Any]] = []
    for championship_round in category.rounds:
        if championship_round.sprint_race:
            info = [
                {
                    "session_id": f"SR{championship_round.id}",
                    "race_name": championship_round.sprint_race.name,
                    "order": 1,
                },
                {
                    "session_id": f"LR{championship_round.id}",
                    "race_name": championship_round.long_race.name,
                    "order": 2,
                },
            ]
        else:
            info = [
                {
                    "session_id": f"LR{championship_round.id}",
                    "race_name": championship_round.long_race.name,
                    "order": 0,
                }
            ]

        calendar.append(
            {
                "circuit_logo": championship_round.circuit.logo_url,
                "circuit": championship_round.circuit.abbreviated_name,
                "info": info,
            }
        )
    session.close()
    return calendar


# TODO: Optimize this function by removing quali results search
def _create_driver_result_list(race_results: list[RaceResult]) -> list[dict[str, Any]]:
    """Creates a list containing"""

    driver = race_results[0].driver
    quali_results = driver.qualifying_results

    driv_res: list[dict[str, Any]] = []
    for race_result in race_results:
        if "1" in race_result.session.name:
            info_gp = f"SR{race_result.round_id}"

            quali_result = None
            for quali_res in quali_results:
                if quali_res.session_id == race_result.session_id:
                    quali_result = quali_res

            extra_points: int | float = race_result.fastest_lap

            if quali_result:
                extra_points += quali_result.points_earned

            penalties = race_result.session.get_penalty_seconds_of(driver.id)

        else:
            info_gp = f"LR{race_result.round_id}"
            extra_points = race_result.fastest_lap
            penalties = race_result.session.get_penalty_seconds_of(driver.id)

        position = race_result.position if race_result.position is not None else "/"

        driv_res.append(
            {
                "info_gp": info_gp,
                "position": position,
                "extra_points": int(extra_points),
                "penalties": penalties,
            }
        )

    return driv_res


def get_standings_with_results(category_id: int):
    session = SQLASession()

    category = get_category(session=session, category_id=category_id)
    if not category:
        return

    results = category.standings_with_results()

    response = []

    if not results:
        for driver in category.active_drivers():
            team = driver.driver.current_team()

            if not team:
                team = driver.teams[-1].team

            response.append(
                {
                    "driver_id": driver.driver_id,
                    "driver_name": driver.driver.psn_id,
                    "points": 0,
                    "team": team.name,
                    "info": [],
                }
            )
        return response

    for driver_results, points_tally in results:
        driver = cast(Driver, driver_results[0].driver)
        team = driver.current_team()

        if not team:
            team = driver.contracts[-1].team

        driver_summary = {
            "driver_id": driver.id,
            "driver_name": driver.psn_id,
            "points": int(points_tally),
            "team": team.name,
            "info": _create_driver_result_list(
                driver_results,
            ),
        }
        response.append(driver_summary)

    session.close()

    return response


def get_drivers_points(championship_id: int):
    session = SQLASession()

    result: dict[int, list[list[float]]] = {}
    championship = get_championship(session, championship_id=championship_id)

    if not championship:
        return

    for category in championship.categories:
        result[category.id] = category.points_per_round()

    return result


def get_teams_list(championship_id: int):
    """Returns the teams participating to the championship ordered by position."""
    session = SQLASession()
    team_objs = get_teams(session, championship_id)

    teams = []
    for team in team_objs:
        teams.append(
            {"points": team.current_championship().points, "logo": team.logo_url}
        )

    return teams


async def save_rre_results_file(file: UploadFile):
    """Saves the results contained in the file."""

    sqla_session = SQLASession()

    current_championship = get_championship(sqla_session)

    if not current_championship:
        raise HTTPException(
            500, "Championship was not configured correctly in the database."
        )

    current_category = current_championship.current_racing_category()
    if not current_category:
        raise HTTPException(500, "No race was scheduled for today.")

    # current_round can't be None, current_racing_category() already checks for that.
    current_round = cast(Round, current_category.first_non_completed_round())

    json_str = await file.read()
    data = json.loads(json_str)

    driver_objs = current_category.active_drivers()
    drivers = {d.driver.rre_id: d.driver for d in driver_objs}

    qualifying_results: list[QualifyingResult] = []
    races: defaultdict[Session, list[RaceResult]] = defaultdict(list)

    qualifying_data = data["Sessions"][1]
    pole_lap = Decimal(qualifying_data["Players"][0]["BestLapTime"]) / 1000

    if session := current_round.qualifying_session:
        for player in qualifying_data["Players"]:
            rre_id = cast(int, player["UserId"])
            position = cast(int, player["Position"])
            laptime = Decimal(player["BestLapTime"]) / 1000
            gap_to_first = laptime - pole_lap

            driver = drivers[rre_id]

            qualifying_results.append(
                QualifyingResult(
                    session=session,
                    round_id=current_round.id,
                    category_id=current_category.id,
                    gap_to_first=gap_to_first,
                    laptime=laptime,
                    driver_id=driver.id,
                    driver=driver,
                    participated=True,
                )
            )
        # Add qualifying results for drivers who didn't participate to quali
        for driver in driver_objs:
            for result in qualifying_results:
                if result.driver_id == driver.driver_id:
                    break
            else:
                qualifying_results.append(
                    QualifyingResult(
                        driver_id=driver.driver_id,
                        driver=driver.driver,
                        participated=False,
                        round_id=current_round.id,
                        session=session,
                        category_id=current_category.id,
                    )
                )

    for i, race_data in enumerate(data["Sessions"][2:]):
        fastest_lap = float("inf")
        driver_race_results: dict[int, RaceResult] = {}
        fastest_lap_player_id: int
        winners_time = Decimal(race_data["Players"][0]["TotalTime"]) / 1000

        if current_round.has_sprint_race and i == 0:
            session = cast(Session, current_round.sprint_race)
        else:
            session = current_round.long_race

        deferred_penalty_applied = False
        # Create a RaceResult for every player in the session and check fastest lap

        for player in race_data["Players"]:
            gap_to_first = 0
            for winners_lap, players_lap in zip(
                race_data["Players"][0]["RaceSessionLaps"], player["RaceSessionLaps"]
            ):
                if players_lap["Time"] > 0:
                    gap_to_first += (
                        Decimal(players_lap["Time"] - winners_lap["Time"]) / 1000
                    )
                    continue
                for winner_sector, player_sector in zip(
                    reversed(winners_lap["SectorTimes"]),
                    reversed(players_lap["SectorTimes"]),
                ):
                    if player_sector > 0:
                        gap_to_first += Decimal(player_sector - winner_sector) / 1000
                        break

            rre_id = cast(int, player["UserId"])
            position = cast(int, player["Position"])
            total_racetime = (
                Decimal(race_data["Players"][0]["TotalTime"]) / 1000
            ) + gap_to_first

            player_fastest_lap = cast(int, player["BestLapTime"]) / 1000
            driver = drivers[rre_id]

            if player_fastest_lap < fastest_lap:
                fastest_lap = player_fastest_lap
                fastest_lap_player_id = driver.id

            # Apply any deferred penalties

            for def_penalty in driver.deferred_penalties:
                total_racetime += def_penalty.penalty.time_penalty
                deferred_penalty_applied = True

            race_res = RaceResult(
                position=position,
                driver_id=driver.id,
                driver=driver,
                total_racetime=total_racetime,
                gap_to_first=gap_to_first,
                participated=True,
                round_id=current_round.id,
                session=session,
                category_id=current_category.id,
            )

            driver_race_results[driver.id] = race_res
            races[session].append(race_res)

        # If deferred penalty was applied, recalculate session results.
        if deferred_penalty_applied:
            races[session].sort(key=lambda rr: rr.total_racetime)
            winners_time = Decimal(0)
            for pos, result in enumerate(races[session], start=1):
                if pos == 1:
                    winners_time = result.total_racetime

                result.gap_to_first = result.total_racetime - winners_time
                result.position = pos

        # Add raceresults for drivers who didn't participate to this session
        for driver in driver_objs:
            for result in races[session]:
                if result.driver_id == driver.driver_id:
                    break
            else:
                races[session].append(
                    RaceResult(
                        driver_id=driver.driver_id,
                        driver=driver.driver,
                        participated=False,
                        round_id=current_round.id,
                        session=session,
                        category_id=current_category.id,
                    )
                )

        driver_race_results[fastest_lap_player_id].fastest_lap = True

    current_round.is_completed = True
    save_results(sqla_session, qualifying_results, races)

    if not current_round:
        raise HTTPException(500, "No race expected.")
    return 200
