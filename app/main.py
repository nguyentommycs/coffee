from contextlib import asynccontextmanager

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.agents.input_parsing import AgentLoopError, LowConfidenceError
from app.agents.orchestrator import parse_and_persist, run_recommendations
from app.db.connection import close_pool, init_pool
from app.db.queries import (
    create_user,
    get_bean_profiles,
    get_recommendation_runs,
    get_taste_profile,
)
from app.models.bean_profile import BeanProfile
from app.models.recommendation import RecommendationResponse


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_pool()
    yield
    await close_pool()


app = FastAPI(title="Coffee Agent", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateUserRequest(BaseModel):
    user_id: str


class CreateUserResponse(BaseModel):
    user_id: str


class AddBeansRequest(BaseModel):
    user_id: str
    inputs: list[str]


class AddBeansResponse(BaseModel):
    parsed: list[BeanProfile]
    skipped: list[str]


@app.exception_handler(AgentLoopError)
async def agent_loop_handler(request, exc: AgentLoopError):
    return JSONResponse(
        status_code=500,
        content={
            "error": "agent_loop_exceeded",
            "message": str(exc),
            "partial_result": exc.partial_result,
        },
    )


@app.exception_handler(LowConfidenceError)
async def low_confidence_handler(request, exc: LowConfidenceError):
    return JSONResponse(
        status_code=422,
        content={
            "error": "low_confidence_parse",
            "message": "Could not extract enough information from input",
            "fields_missing": exc.missing_fields,
            "input_raw": exc.input_raw,
        },
    )


@app.exception_handler(ValueError)
async def value_error_handler(request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "bad_request", "message": str(exc)},
    )


@app.post("/users", response_model=CreateUserResponse)
async def post_users(body: CreateUserRequest):
    await create_user(body.user_id)
    return CreateUserResponse(user_id=body.user_id)


@app.post("/beans", response_model=AddBeansResponse)
async def post_beans(body: AddBeansRequest):
    try:
        parsed, skipped = await parse_and_persist(body.user_id, body.inputs)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail="user not found")
    return AddBeansResponse(parsed=parsed, skipped=skipped)


@app.get("/beans", response_model=list[BeanProfile])
async def get_beans(user_id: str = Query(...)):
    return await get_bean_profiles(user_id)


@app.get("/profile")
async def get_profile(user_id: str = Query(...)):
    profile = await get_taste_profile(user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="no profile found for user")
    return profile


@app.get("/recommendations", response_model=RecommendationResponse)
async def get_recommendations(
    user_id: str = Query(...),
    n: int = Query(default=5, ge=1, le=20),
):
    return await run_recommendations(user_id, n_final=n)


@app.get("/recommendation-runs")
async def get_recommendation_runs_endpoint(user_id: str = Query(...)):
    return await get_recommendation_runs(user_id)


@app.get("/health")
async def health():
    return {"status": "ok"}
