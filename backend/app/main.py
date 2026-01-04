from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .pipeline import run_pipeline


class FetchRequest(BaseModel):
    query: str = Field(min_length=1)
    page_size: int = Field(default=5, ge=1, le=100)
    language: str = Field(default="en", min_length=2, max_length=5)
    sort_by: str = Field(default="publishedAt")


app = FastAPI(title="News MiniProject API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.post("/api/fetch")
def fetch(req: FetchRequest):
    try:
        dataset = run_pipeline(
            query=req.query,
            page_size=req.page_size,
            language=req.language,
            sort_by=req.sort_by,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    if not dataset.get("articles"):
        raise HTTPException(status_code=404, detail="검색 결과가 없습니다.")

    return dataset
