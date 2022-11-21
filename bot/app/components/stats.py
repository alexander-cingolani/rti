"""
This module contains functions which calculate various driver statistics
"""

from statistics import stdev

from app.components.models import Driver, RaceResult
from cachetools import TTLCache, cached


@cached(cache=TTLCache(maxsize=50, ttl=30))
def consistency(driver: Driver) -> int:
    """This  a number from 0 to 99 calculated on the standard deviation of
    the set of relative finishing positions.

    Args:
        results (list[RaceResult]): The results to calculate the consistency of.

    Returns:
        int: Consistency rating. (0-99)
    """

    race_results: list[RaceResult] = list(
        filter(lambda x: x.participated, driver.race_results)
    )
    if len(race_results) < 2:
        return 0
    positions = [race_result.relative_position for race_result in race_results]
    participation_ratio = len(race_results) / len(driver.race_results)

    return round((99 - (stdev(positions) * 10)) * participation_ratio)


@cached(cache=TTLCache(maxsize=50, ttl=240))
def speed(driver: Driver) -> int:
    """This statistic is calculated based on the average gap between
    the driver's qualifying times and the pole man's.

    Args:
        driver (Driver): The Driver to calculate the speed rating of.

    Returns:
        int: Speed rating. (0-99)
    """

    percentages = []
    for quali_result in filter(lambda x: x.laptime, driver.qualifying_results):
        percentages.append(
            (
                quali_result.gap_to_first
                / (quali_result.gap_to_first + quali_result.laptime)
            )
            * 100
        )

    if percentages:
        return round(99 - sum(percentages) / len(percentages) * 9)
    return 0


@cached(cache=TTLCache(maxsize=50, ttl=240))
def experience(driver: Driver, max_races: int) -> int:
    """This statistic is calculated based on the maximum number of races
    completed by any driver in the database. The closer the amount of races
    completed by the given driver the closer the resulting score is to 99.

    Args:
        driver (Driver): The driver to calculate the experience of.
        max_races (int): Maximum number of races completed by any driver.

    Returns:
        int: Experience rating. (0-99)
    """

    if not max_races:
        return 0

    disputed_rounds = []
    for race_result in driver.race_results:
        if (
            race_result.gap_to_first != 0
            and race_result.round.round_id not in disputed_rounds
        ):
            disputed_rounds.append(race_result.round.round_id)

    if not disputed_rounds:
        return 0

    return round(99 - ((max_races - len(disputed_rounds)) / max_races * 99) * 0.6)


@cached(cache=TTLCache(maxsize=50, ttl=240))
def sportsmanship(driver: Driver) -> int:
    """This statistic is calculated based on the amount and gravity of reports received.

    Args:
        driver (Driver): The Driver to calculate the sportsmanship of.

    Returns:
        int: Sportsmanship rating. (0-99)
    """

    if len(driver.race_results) < 2:
        return 0

    if not driver.received_reports:
        return 99

    penalties = (
        rr.time_penalty
        + rr.warnings
        + rr.licence_points
        + rr.championship_penalty_points
        for rr in driver.received_reports
    )

    return round(99 - sum(penalties) * 7 / len(driver.race_results))


@cached(cache=TTLCache(maxsize=50, ttl=240))
def race_pace(driver: Driver) -> int:
    """This statistic is calculated based on the average gap from the race winner
    in all of the races completed by the driver.

    Args:
        driver (Driver): The Driver to calculate the race pace of.

    Return:
        int: Race pace score. (0-99)
    """
    race_results = list(filter(lambda x: x.participated, driver.race_results))
    if not race_results:
        return 0

    return round(
        99
        - (
            sum(race_result.gap_to_first for race_result in race_results)
            / (len(race_results) * 3)
        )
    )


@cached(cache=TTLCache(maxsize=50, ttl=240))
def stats(driver: Driver) -> tuple[int, int, int]:
    """Calculates the number of wins, podiums and poles achieved by the driver.

    Args:
        driver (Driver): The Driver to calculate the statistics of.

    Returns:
        tuple[int, int, int]: Tuple containing wins, podiums and poles in order.
    """
    wins = 0
    podiums = 0
    fastest_laps = 0
    poles = 0
    no_participation = 0
    average_position = 0
    if not driver.race_results:
        return 0, 0, 0, 0, 0, 0

    positions = []
    for race_result in driver.race_results:
        if not race_result.participated:
            no_participation += 1
            continue

        if race_result.relative_position:
            positions.append(race_result.relative_position)
        if race_result.relative_position == 1:
            wins += 1
        if race_result.relative_position <= 3:
            podiums += 1
        fastest_laps += race_result.fastest_lap_points

    for quali_result in driver.qualifying_results:
        if quali_result:
            if quali_result.relative_position == 1:
                poles += 1

    races_completed = len(driver.race_results) - no_participation
    if positions:
        average_position = round(sum(positions) / len(positions), 2)

    return wins, podiums, poles, fastest_laps, races_completed, average_position
