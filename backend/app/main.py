"""TRINETRA backend — FastAPI entrypoint.

This is intentionally minimal for Phase 1: just enough to prove the backend
runs and can (eventually) reach the database. Real cyclone/forecast endpoints
get added in Phase 7.
"""
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

app = FastAPI(title="TRINETRA API", version="0.1.0")

# Allow the local React dev server to call this API during development.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health():
    return {"status": "ok", "database_url_set": bool(os.getenv("DATABASE_URL"))}


@app.get("/")
def root():
    return {"message": "TRINETRA API — see /docs for available endpoints"}
