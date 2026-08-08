import uuid
from contextlib import asynccontextmanager
from typing import Literal, Optional

import asyncpg
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from app.agents.input_parsing import AgentLoopError, LowConfidenceError
from app.agents.orchestrator import parse_and_persist, run_recommendations
from app.db.connection import close_pool, init_pool
from app.db.queries import (
    create_user,
    get_bean_profiles,
    get_pipeline_trace,
    get_pipeline_traces,
    get_recommendation_runs,
    get_taste_profile,
    update_bean_profile,
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
    user_score: int | None = None


class AddBeansResponse(BaseModel):
    parsed: list[BeanProfile]
    skipped: list[str]


class UpdateBeanRequest(BaseModel):
    name: str
    roaster: str
    origin_country: Optional[str] = None
    origin_region: Optional[str] = None
    farm_or_cooperative: Optional[str] = None
    process: Optional[Literal["Washed", "Natural", "Honey", "Anaerobic"]] = None
    variety: Optional[str] = None
    roast_level: Optional[Literal["Light", "Medium-Light", "Medium", "Dark"]] = None
    tasting_notes: list[str] = []
    user_score: Optional[int] = None
    user_notes: Optional[str] = None

    @field_validator("user_score")
    @classmethod
    def score_in_range(cls, v):
        if v is not None and not (1 <= v <= 10):
            raise ValueError("user_score must be between 1 and 10")
        return v


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
        parsed, skipped = await parse_and_persist(body.user_id, body.inputs, body.user_score)
    except asyncpg.ForeignKeyViolationError:
        raise HTTPException(status_code=404, detail="user not found")
    return AddBeansResponse(parsed=parsed, skipped=skipped)


@app.get("/beans", response_model=list[BeanProfile])
async def get_beans(user_id: str = Query(...)):
    return await get_bean_profiles(user_id)


@app.patch("/beans/{bean_id}", response_model=BeanProfile)
async def patch_bean(bean_id: uuid.UUID, body: UpdateBeanRequest, user_id: str = Query(...)):
    updated = await update_bean_profile(bean_id, user_id, body.model_dump())
    if updated is None:
        raise HTTPException(status_code=404, detail="bean not found")
    return updated


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


def _summarize_trace(run: dict) -> dict:
    """
    Builds a run summary from a stored pipeline trace. Tolerates legacy traces
    written before spans carried `type`/`attrs` (those count as 0 llm calls).
    """
    trace = run.get("trace") or {}
    spans = trace.get("spans") or []
    llm_spans = [s for s in spans if s.get("type") == "llm"]

    def tokens(key: str) -> int:
        return sum((s.get("attrs") or {}).get(key) or 0 for s in llm_spans)

    return {
        "run_id": run["run_id"],
        "created_at": run["created_at"],
        "total_duration_ms": trace.get("total_duration_ms"),
        "status": "error" if any(s.get("status") == "error" for s in spans) else "ok",
        "llm_calls": len(llm_spans),
        "total_input_tokens": tokens("input_tokens"),
        "total_output_tokens": tokens("output_tokens"),
        "span_count": len(spans),
    }


@app.get("/traces")
async def get_traces(user_id: str = Query(...)):
    runs = await get_pipeline_traces(user_id)
    return [_summarize_trace(run) for run in runs]


@app.get("/traces/{run_id}")
async def get_trace(run_id: uuid.UUID, user_id: str = Query(...)):
    run = await get_pipeline_trace(run_id, user_id)
    if run is None:
        raise HTTPException(status_code=404, detail="trace not found")
    return run


@app.get("/health")
async def health():
    return {"status": "ok"}
