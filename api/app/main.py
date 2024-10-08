from datetime import timedelta
import logging
import os
from typing import Annotated, Any, Awaitable, Callable

from fastapi.responses import FileResponse
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import create_engine
from app.components.schemas.calendar import RoundInfoSchema
from app.components.schemas.standings import DriverSummary
from queries import (
    fetch_championship_by_tag,
    fetch_championships,
)
from starlette.middleware.base import BaseHTTPMiddleware
from app.components.schemas.category import CategorySchema
from app.components.schemas.championship import ChampionshipSchema
from app.components.schemas.driver import DriverSchema
from app.components.schemas.penalty import PenaltySchema
from app.components.schemas.protest import ProtestSchema, CreateProtestSchema
from app.components.schemas.qualifyingresult import QualifyingResultSchema
from app.components.schemas.raceresult import RaceResultSchema
from app.components.schemas.resultsfile import RaceRoomResultsSchema
from app.components.schemas.team import EditTeamSchema, TeamSchema, TeamStandingsSchema
from app.components.schemas.session import SessionSchema
from app.components.schemas.round import RoundSchema
from app.components.schemas.token import TokenSchema
from app.components.auth import (
    authenticate_user,
    create_access_token,
    get_current_user,
)

from app.components.handlers import (
    fetch_standings,
    generate_protest_document,
    generate_protest_document_old,
    get_calendar,
    get_categories,
    get_drivers_points,
    get_standings_with_results,
    get_teams_list,
    save_rre_results,
    save_rre_results_old,
)
from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    HTTPException,
    Request,
    Response,
    UploadFile,
    status,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as DBSession

app = FastAPI()

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

app = FastAPI()

origin = r".*"

app.mount("/images", StaticFiles(directory="/api/app/public/images"), name="images")
app.mount("/fonts", StaticFiles(directory="/api/app/public/fonts"), name="fonts")

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=origin,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 * 2 + 240  # 2 weeks and 4 hours
DATABASE_URL = os.environ["DB_URL"]

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@app.middleware("http")
async def db_session_middleware(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
):
    response = Response("Internal server error", status_code=500)
    try:
        request.state.db = SessionLocal()
        response = await call_next(request)
    finally:
        request.state.db.close()
    return response


class DBSessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any):
        response = None
        try:
            # Create a new database session and store it in request.state.db
            request.state.db = SessionLocal()
            response = await call_next(request)
        finally:
            # Close the session after the request is completed
            request.state.db.close()

        return response


app.add_middleware(DBSessionMiddleware)


def get_db(request: Request) -> DBSession:
    return request.state.db


engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@app.get("/api-v2/standings/{championship_tag}")
async def read_standings(
    championship_tag: str | None = None, db: DBSession = Depends(get_db)
):
    """Returns all the data necessary for the /classifiche page. If no championship
    is specified, defaults to the latest."""
    return fetch_standings(db, championship_tag)


@app.get("/api-v2/championships/", response_model=list[ChampionshipSchema])
async def read_championships(active: bool = False, db: DBSession = Depends(get_db)):
    return fetch_championships(db, active)


@app.get("/api-v2/championships/{championship_tag}", response_model=ChampionshipSchema)
async def read_championship(championship_tag: str, db: DBSession = Depends(get_db)):
    return fetch_championship_by_tag(db, championship_tag)


@app.post("/api-v2/championships/")
async def create_championship(
    championship: ChampionshipSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return "api-v2/championships/championship-name"


@app.put("/api-v2/championships/{championship_tag}")
async def update_championship(
    championship_tag: str,
    championship: ChampionshipSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    """Updates the championship with the new information"""
    return


@app.delete("/api-v2/championships/{championship_tag}")
async def delete_championship(
    championship_tag: str,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    """Deletes the specified championship."""
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/",
    response_model=list[CategorySchema],
)
async def read_categories(championship_tag: str, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}",
    response_model=CategorySchema,
)
async def read_category(category_name: str, db: DBSession = Depends(get_db)):
    """Returns all info about a Category."""
    return


@app.post("/api-v2/championships/{championship_tag}/categories/")
async def create_category(
    category: CategorySchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put("/api-v2/championships/{championship_tag}/categories/{category_name}")
async def edit_category(
    category_name: str,
    category: CategorySchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete("/api-v2/championships/{championship_tag}/categories/{category_name}")
async def delete_category(
    category_name: str,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/",
    response_model=list[RoundSchema],
)
async def read_rounds(category_name: str, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}",
    response_model=RoundSchema,
)
async def read_round(round_id: int, db: DBSession = Depends(get_db)):
    return


@app.post("/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/")
async def create_round(
    round: RoundSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}"
)
async def edit_round(
    round_id: int,
    round: RoundSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/",
    response_model=list[SessionSchema],
)
async def read_sessions(round_id: int, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}",
    response_model=SessionSchema,
)
async def read_session(session_id: int, db: DBSession = Depends(get_db)):
    return


@app.post(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/"
)
async def create_session(
    session: SessionSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}"
)
async def edit_session(
    session_id: int,
    session: SessionSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}"
)
async def delete_session(
    session_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/race-results/",
    response_model=list[RaceResultSchema],
)
async def read_race_results(session_id: int, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/race-results/{race_result_id}",
    response_model=RaceResultSchema,
)
async def read_race_result(race_result_id: int, db: DBSession = Depends(get_db)):
    return


@app.post(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/race-results/"
)
async def create_race_result(
    race_result: RaceResultSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/race-results/{race_result_id}"
)
async def edit_race_result(
    race_result_id: int,
    race_result: RaceResultSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/race-results/{race_result_id}"
)
async def delete_race_result(race_result_id: int, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/qualifying-results/",
    response_model=list[QualifyingResultSchema],
)
async def read_quali_results(session_id: int, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/qualifying-results/{quali_result_id}",
    response_model=QualifyingResultSchema,
)
async def read_quali_result(quali_result_id: int, db: DBSession = Depends(get_db)):
    return


@app.post(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/qualifying-results/"
)
async def create_quali_result(
    quali_result: QualifyingResultSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/qualifying-results/{quali_result_id}"
)
async def edit_quali_result(
    quali_result_id: int,
    quali_result: QualifyingResultSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/sessions/{session_id}/qualifying-results/{quali_result_id}"
)
async def delete_quali_result(
    quali_result_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/protests/",
    response_model=list[ProtestSchema],
)
async def read_protests(round_id: int, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/protests/{protest_id}",
    response_model=ProtestSchema,
)
async def read_protest(protest_id: int, db: DBSession = Depends(get_db)):
    return


@app.post(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/protests/",
)
async def create_protest(
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    protest: CreateProtestSchema,
    db: DBSession = Depends(get_db),
) -> FileResponse:

    protest_document = await generate_protest_document(db, protest)

    if not protest.session_name in ("Qualifica", "Gara 1", "Gara 2", "Gara"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "Invalid value given for session_name.",
        )

    with open("temp.pdf", "wb") as file:
        file.write(protest_document[0])
    return FileResponse("temp.pdf")


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/protests/{protest_id}"
)
async def edit_protest(
    protest_id: int,
    protest: ProtestSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/protests/{protest_id}"
)
async def delete_protest(
    protest_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/penalties/",
    response_model=list[PenaltySchema],
)
async def read_penalties(reviewed: bool, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/penalties/{penalty_id}",
    response_model=PenaltySchema,
)
async def read_penalty(penalty_id: int, db: DBSession = Depends(get_db)):
    return


@app.post(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/penalties/"
)
async def create_penalty(
    penalty: PenaltySchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/penalties/{penalty_id}"
)
async def edit_penalty(
    penalty_id: int,
    penalty: PenaltySchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete(
    "/api-v2/championships/{championship_tag}/categories/{category_name}/rounds/{round_id}/penalties/{penalty_id}"
)
async def delete_penalty(
    penalty_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/teams/",
    response_model=list[TeamSchema],
)
async def read_teams(active: bool = True, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/teams/{team_id}",
    response_model=TeamSchema,
)
async def read_team(team_id: int, db: DBSession = Depends(get_db)):
    return


@app.post("/api-v2/teams/")
async def create_team(
    team: TeamSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put("/api-v2/teams/{team_id}")
async def edit_team(
    team_id: int,
    team: EditTeamSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete("/api-v2/teams/{team_id}")
async def delete_team(
    team_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.get(
    "/api-v2/drivers/",
    response_model=list[DriverSchema],
)
async def read_drivers(active: bool = True, db: DBSession = Depends(get_db)):
    return


@app.get(
    "/api-v2/drivers/{driver_id}",
    response_model=DriverSchema,
)
async def read_driver(driver_id: int, db: DBSession = Depends(get_db)):
    return


@app.post("/api-v2/drivers/")
async def create_driver(
    driver: DriverSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.put("/api-v2/drivers/{driver_id}")
async def edit_driver(
    driver_id: int,
    driver: DriverSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.delete("/api-v2/drivers/{driver_id}")
async def delete_driver(
    driver_id: int,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    return


@app.post("/api-v2/token", response_model=TokenSchema)
async def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession = Depends(get_db),
):
    logger.info("login was called")
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api-v2/rre-results/", response_model=TokenSchema)
async def upload_rre_results(
    results: RaceRoomResultsSchema,
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    db: DBSession = Depends(get_db),
):
    logger.info("upload_rre_results was called.")

    await save_rre_results(db, results)

    access_token = create_access_token({"sub": current_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


##### Old endpoints left for temporary backwards compatibility


@app.post("/api/teams", response_model=list[TeamStandingsSchema])
async def teams(championship_id: int = Form(), db: DBSession = Depends(get_db)):
    return get_teams_list(db, int(championship_id))


@app.post("/api/categories", response_model=list[CategorySchema])
async def categories(championship_id: int = Form(), db: DBSession = Depends(get_db)):
    return get_categories(db, championship_id)


@app.post("/api/calendar", response_model=list[RoundInfoSchema])
async def calendar(category_id: int = Form(), db: DBSession = Depends(get_db)):
    return get_calendar(db, int(category_id))


@app.post("/api/standings", response_model=list[DriverSummary])
async def standings(category_id: int = Form(), db: DBSession = Depends(get_db)):
    return get_standings_with_results(db, int(category_id))


@app.post("/api/driver-points")
async def driver_points(championship_id: int = Form(), db: DBSession = Depends(get_db)):
    return get_drivers_points(db, int(championship_id))


@app.post("/api/token", response_model=TokenSchema)
async def login_old(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DBSession = Depends(get_db),
):
    logger.info("login was called")
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.email}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/upload-rre-results", response_model=TokenSchema)
async def upload_rre_results_old(
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    file: UploadFile = File(),
    db: DBSession = Depends(get_db),
):
    logger.info("upload_rre_results was called.")

    json_str = await file.read()
    await save_rre_results_old(db, json_str)

    access_token = create_access_token({"sub": current_user.email})
    return {"access_token": access_token, "token_type": "bearer"}


@app.post("/api/upload-protest", response_model=TokenSchema)
async def upload_protest(
    current_user: Annotated[DriverSchema, Depends(get_current_user)],
    protesting_driver_discord_id: int = Form(),
    protested_driver_discord_id: int = Form(),
    protest_reason: str = Form(),
    incident_time: str = Form(),
    session_name: str = Form(),
    db: DBSession = Depends(get_db),
) -> FileResponse:

    protest_document = await generate_protest_document_old(
        db,
        protesting_driver_discord_id,
        protested_driver_discord_id,
        protest_reason,
        incident_time,
        session_name,
    )

    if not session_name in ("Qualifica", "Gara 1", "Gara 2", "Gara"):
        raise HTTPException(422, "Invalid value given for session_name.")

    with open("temp.pdf", "wb") as file:
        file.write(protest_document[0])
    return FileResponse("temp.pdf")
