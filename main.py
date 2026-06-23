from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os

app = FastAPI()

# Directory to save loops
DATA_DIR = "data"
os.makedirs(DATA_DIR, exist_ok=True)

# Metadata file (ratings, notes, etc.)
META_FILE = os.path.join(DATA_DIR, "_loop_meta.json")

def load_meta() -> dict:
    if os.path.exists(META_FILE):
        try:
            with open(META_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def save_meta(meta: dict):
    with open(META_FILE, "w", encoding="utf-8") as f:
        json.dump(meta, f, indent=2, ensure_ascii=False)

class Note(BaseModel):
    step: int
    note: str
    duration: str

class Loop(BaseModel):
    name: str
    bpm: int
    instrument: str
    steps: int
    notes: List[Note]

class LoopMeta(BaseModel):
    rating: Optional[int] = 0      # 0-5 stars
    tags: Optional[List[str]] = []
    notes: Optional[str] = ""

@app.get("/api/loops")
def get_loops():
    loops = []
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(DATA_DIR, filename)
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data["_filename"] = filename
                    loops.append(data)
            except Exception:
                pass
    return loops

@app.post("/api/loops")
def save_loop(loop: Loop):
    # simple sanitization
    safe_name = "".join([c for c in loop.name if c.isalnum() or c in (' ', '-', '_')]).rstrip()
    filename = f"{safe_name.replace(' ', '_').lower()}.json"
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop.dict(), f, indent=4)
    return {"status": "success", "filename": filename}

@app.delete("/api/loops/{filename}")
def delete_loop(filename: str):
    # secure delete
    safe_filename = os.path.basename(filename)
    filepath = os.path.join(DATA_DIR, safe_filename)
    if os.path.exists(filepath):
        os.remove(filepath)
        # Clean up metadata too
        meta = load_meta()
        if safe_filename in meta:
            del meta[safe_filename]
            save_meta(meta)
        return {"status": "success"}
    raise HTTPException(status_code=404, detail="File not found")

@app.get("/api/meta")
def get_meta():
    return load_meta()

@app.patch("/api/meta/{filename}")
def update_meta(filename: str, patch: LoopMeta):
    safe_filename = os.path.basename(filename)
    meta = load_meta()
    existing = meta.get(safe_filename, {})
    incoming = patch.dict(exclude_none=True)
    existing.update(incoming)
    meta[safe_filename] = existing
    save_meta(meta)
    return {"status": "success", "filename": safe_filename, "meta": existing}

# Create static directory if it doesn't exist
os.makedirs("static", exist_ok=True)

# Serve the static files
app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
