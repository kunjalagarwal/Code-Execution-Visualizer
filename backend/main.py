import os
import json
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sandbox import execute_code_in_sandbox

app = FastAPI(title="Code Execution Visualizer API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class CodeExecutionRequest(BaseModel):
    code: str
    stdin: str = ""

@app.post("/api/execute")
def execute_code(req: CodeExecutionRequest):
    if not req.code.strip():
        raise HTTPException(status_code=400, detail="Code cannot be empty.")
        
    try:
        # Run standard trace extraction in Docker Sandbox
        result = execute_code_in_sandbox(req.code, req.stdin)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
