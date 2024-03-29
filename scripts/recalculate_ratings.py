"""
This module is for recalculating ratings in the database from scratch.
"""

from decimal import Decimal
import os

import trueskill as ts  # type: ignore
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from models import RaceResult
from queries import get_championship

TrueSkillEnv = ts.TrueSkill(
    draw_probability=0,
)
DB_URL = os.environ.get("DB_URL")
if not DB_URL:
    raise RuntimeError("DB_URL not found.")

engine = create_engine(DB_URL)

DBSession = sessionmaker(bind=engine, autoflush=False)


def recalculate_ratings():
    """Only used to recalculate all the ratings in the last championship."""
    sqla_session = DBSession()
    championship = get_championship(sqla_session, championship_id=1)

    if not championship:
        return

    for category in championship.categories:
        for round in category.rounds:
            for session in round.sessions:
                if session.is_quali:
                    continue

                initial_ratings: list[tuple[ts.Rating]] = []
                finishing_positions: list[int] = []
                race_results: list[RaceResult] = []
                for result in session.race_results:
                    if result.participated:
                        rtg = (
                            ts.Rating(
                                mu=float(result.driver.mu),
                                sigma=float(result.driver.sigma),
                            ),
                        )
                        initial_ratings.append(rtg)
                        finishing_positions.append(result.position)
                        race_results.append(result)
                        result.mu = rtg[0].mu
                        result.sigma = rtg[0].sigma
                print(initial_ratings)
                print(finishing_positions)
                if initial_ratings:
                    new_ratings = ts.rate(initial_ratings, finishing_positions)
                    for i, result in enumerate(race_results):
                        result.driver.mu = Decimal.from_float(
                            new_ratings[i][0].mu
                        ).quantize(Decimal("1.000000"))
                        result.driver.sigma = Decimal.from_float(
                            new_ratings[i][0].sigma
                        ).quantize(Decimal("1.000000"))

    sqla_session.commit()
    sqla_session.expire_all()

    championship = get_championship(sqla_session)

    if not championship:
        return

    drivers = championship.driver_list

    drivers.sort(key=lambda x: x.rating if x.rating else 0, reverse=True)

    for driver in drivers:
        print(f"{driver.psn_id}: {driver.mu} - {driver.sigma}")


if __name__ == "__main__":
    recalculate_ratings()
