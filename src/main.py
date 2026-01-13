"""
Prediction Market Tracker - Ultra Minimal Version
This version has NO imports except FastAPI to diagnose startup issues.
"""
import sys
print("PYTHON STARTING", flush=True)

from fastapi import FastAPI

print("FASTAPI IMPORTED", flush=True)

app = FastAPI(title="Prediction Market Tracker")

print("APP CREATED", flush=True)

@app.get("/health")
async def health():
    return {"status": "ok", "message": "minimal version running"}

@app.get("/")
async def root():
    return {"status": "healthy", "version": "minimal"}

print("ENDPOINTS DEFINED", flush=True)
