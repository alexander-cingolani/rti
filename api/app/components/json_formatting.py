from app.components.models import RaceResult
from app.components.queries import get_championship


def get_categories(championship_id: int):
    championship = get_championship(championship_id)
    if not championship:
        return []

    categories = []
    for i, category in enumerate(championship.categories):
        categories.append(
            {
                "id": category.category_id,
                "categoria": category.name,
                "campionato": category.championship_id,
                "ordinamento": str(i),
            }
        )
    return categories


def get_calendar(championship_id: int, category_id: int):
    championship = get_championship(championship_id)

    category = None
    if not championship:
        return []
    if not championship.categories:
        return []
    for i, category in enumerate(championship.categories):
        if category.category_id == category_id:
            break

    if not category:
        return []

    calendar = []

    sprint_race = category.has_sprint_race()
    for round in category.rounds:

        if sprint_race:
            info = [
                {
                    "id": f"SR{round.round_id}",
                    "calendario": str(round.round_id),
                    "nome_gp": category.sprint_race.name,
                    "ordinamento": "1",
                    "campionato": str(category.championship_id),
                },
                {
                    "id": f"LR{round.round_id}",
                    "calendario": str(round.round_id),
                    "nome_gp": category.long_race.name,
                    "ordinamento": "2",
                    "campionato": str(category.championship_id),
                },
            ]
        else:
            info = [
                {
                    "id": f"LR{round.round_id}",
                    "calendario": str(round.round_id),
                    "nome_gp": category.long_race.name,
                    "ordinamento": "0",
                    "campionato": str(category.championship_id),
                }
            ]

        calendar.append(
            {
                "id": str(round.round_id),
                "categoria": str(round.category_id),
                "campionato": str(round.championship_id),
                "ordinamento": str(i),
                "info": info,
            }
        )
    return calendar


def _create_driver_result_list(race_results: list[RaceResult]) -> list[dict]:
    """Creates a list containing"""
    driver = race_results[0].driver
    driv_res = []
    double_race = race_results[0].category.has_sprint_race()
    for race_result in race_results:
        round = race_result.round

        # Makes changes to data in order to facilitate the front-end.
        if not double_race:
            info_gp = f"LR{race_result.round_id}"
            punti_extra = round.get_qualifying_result(driver.driver_id).points_earned
        elif (
            double_race
            and race_result.session_id == race_result.category.sprint_race.session_id
        ):
            info_gp = f"SR{race_result.round_id}"
            punti_extra = (
                round.get_qualifying_result(driver.driver_id).points_earned
                + race_result.fastest_lap_points
            )
        else:
            info_gp = f"LR{race_result.round_id}"
            punti_extra = race_result.fastest_lap_points

        driv_res.append(
            {
                "pilota": str(driver.driver_id),
                "calendario": str(race_result.round_id),
                "info_gp": info_gp,
                "posizione": str(race_result.finishing_position),
                "punti_extra": str(punti_extra).replace(".0", ""),
            }
        )
    return driv_res


def get_standings(championship_id: int, category_id: int):
    championship = get_championship(championship_id)
    for category in championship.categories:
        if category.category_id == category_id:
            break
    if not category:
        return []

    standings = []

    # Do I have to add empty lists for races that haven't been completed?
    for driver_results, points_tally in category.current_standings():
        driver = driver_results[0].driver
        driver_summary = {
            "id": str(driver.driver_id),
            "pilota": driver.psn_id,
            "punti_totali": str(points_tally).replace(".0", ""),
            "scuderia": driver.current_team().name,
            "info": _create_driver_result_list(
                driver_results,
            ),
        }
        standings.append(driver_summary)
    return standings


if __name__ == "__main__":
    print(get_calendar(3, 11))
    print(f"\n{get_standings(3, 11)}")
    print(f"\n{get_categories(3, 0)}")