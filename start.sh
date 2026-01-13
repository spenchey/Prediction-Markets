#!/bin/bash
echo "=== STARTUP SCRIPT ==="
echo "PORT=$PORT"
echo "PWD=$(pwd)"
echo "Python version: $(python --version)"
echo "Files in /app:"
ls -la /app/
echo ""
echo "Files in /app/src:"
ls -la /app/src/
echo ""
echo "Testing Python import:"
python -c "print('Python works'); from fastapi import FastAPI; print('FastAPI works')" 2>&1
echo ""
echo "Starting uvicorn on port ${PORT:-8000}..."
exec uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000} 2>&1
