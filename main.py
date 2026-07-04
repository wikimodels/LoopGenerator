from fastapi import FastAPI, HTTPException, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional
import json
import os
import uuid

from melodies_generator import generate_loop as _ml_generate, STYLE_META

app = FastAPI()

# Directory to save loops
DATA_DIR = "data"
LOOPS_DIR = os.path.join(DATA_DIR, "loops")
os.makedirs(LOOPS_DIR, exist_ok=True)

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
def get_loops(response: Response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    loops = []
    meta_filename = os.path.basename(META_FILE)
    for filename in os.listdir(LOOPS_DIR):
        if filename.endswith(".json") and filename != meta_filename:
            filepath = os.path.join(LOOPS_DIR, filename)
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
    if not safe_name:
        import uuid
        safe_name = f"loop_{uuid.uuid4().hex[:8]}"
        
    filename = f"{safe_name.replace(' ', '_').lower()}.json"
    
    if filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Reserved filename")
        
    base_name = safe_name.replace(' ', '_').lower()
    filepath = os.path.join(LOOPS_DIR, filename)
    counter = 1
    while os.path.exists(filepath):
        counter += 1
        filename = f"{base_name}_{counter}.json"
        filepath = os.path.join(LOOPS_DIR, filename)
        
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop.dict(), f, indent=4)
    return {"status": "success", "filename": filename}


# -----------------------------------------------------------------
# STYLE-BASED GENERATION via melodies_generator
# -----------------------------------------------------------------
VALID_KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

class GenerateRequest(BaseModel):
    style: str
    key: str
    bpm: int = 100
    steps: int = 64
    beats_per_bar: int = 4
    seed: Optional[int] = None
    name: Optional[str] = None
    is_batch: bool = False

@app.get("/api/styles")
def get_styles():
    """Return list of available generation styles."""
    return list(STYLE_META.keys())

@app.post("/api/generate")
def generate_loop_endpoint(req: GenerateRequest):
    """Generate a loop with melodies_generator and save it to the loops directory."""
    if req.style not in STYLE_META:
        raise HTTPException(status_code=400, detail=f"Unknown style '{req.style}'")
    if req.key not in VALID_KEYS:
        raise HTTPException(status_code=400, detail=f"Invalid key '{req.key}'")
    if not (40 <= req.bpm <= 240):
        raise HTTPException(status_code=400, detail="BPM must be 40–240")

    try:
        loop = _ml_generate(
            req.style, req.key,
            name=req.name if req.name and req.name.strip() else None,
            bpm=req.bpm,
            steps=req.steps,
            beats_per_bar=req.beats_per_bar,
            seed=req.seed,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Persist to disk
    if req.is_batch:
        # Build a smart, non-redundant name
        style_parts = req.style.split('_')
        scale_parts = loop["scale"].lower().replace('-', ' ').replace('_', ' ').split()
        
        words = []
        for p in style_parts:
            words.append(p.title())
            
        for p in scale_parts:
            pt = p.title()
            # Add scale parts only if they aren't already in the style name
            if pt not in words:
                words.append(pt)
                
        # Key
        words.append(req.key)
        # Seed
        seed_str = str(req.seed) if req.seed is not None else "Rand"
        words.append(seed_str)
        
        loop["name"] = " ".join(words)
        
        # For filename, lower case and use underscores, replace # with sharp
        safe_key = req.key.replace('#', 'sharp').lower()
        fn_words = [w.lower() if w != req.key else safe_key for w in words]
        base = "_".join(fn_words)
    else:
        safe = "".join(c for c in loop["name"] if c.isalnum() or c in " -_").strip()
        base = safe.replace(" ", "_").lower() or f"loop_{uuid.uuid4().hex[:8]}"
        
    filename = f"{base}.json"
    filepath = os.path.join(LOOPS_DIR, filename)
    ctr = 1
    while os.path.exists(filepath):
        ctr += 1
        filename = f"{base}_{ctr}.json"
        filepath = os.path.join(LOOPS_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(loop, f, indent=4, ensure_ascii=False)

    return {"status": "success", "filename": filename, "loop": loop}

@app.delete("/api/loops/{filename}")
def delete_loop(filename: str):
    # secure delete
    safe_filename = os.path.basename(filename)
    if safe_filename == os.path.basename(META_FILE):
        raise HTTPException(status_code=400, detail="Cannot delete metadata file")
        
    filepath = os.path.join(LOOPS_DIR, safe_filename)
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
