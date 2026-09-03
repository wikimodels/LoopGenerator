#!/usr/bin/env python3
import json
import re
from pathlib import Path

LOOPS_DIR = Path(r"D:\GitHub\LoopGenerator\data\loops")
MAX_LEN = len("Neoclassical Piano Loop - Call-and-Response (Eb Lydian, Frost)")

def make_new_name(old_name: str) -> str:
    # unique part after " - ", else strip neoclassical prefix
    if " - " in old_name:
        unique = old_name.split(" - ", 1)[1].strip()
    else:
        unique = re.sub(r"(?i)^neoclassical\s+(lydian\s+)?", "", old_name).strip(" -")
        if not unique:
            unique = old_name.strip()
    new_name = f"Neoclassical Lydian - {unique}"
    if len(new_name) > MAX_LEN:
        # trim by words
        allowed_unique = MAX_LEN - len("Neoclassical Lydian - ")
        # cut and rstrip incomplete word
        trimmed = unique[:allowed_unique].rsplit(" ", 1)[0] if " " in unique[:allowed_unique] else unique[:allowed_unique]
        new_name = f"Neoclassical Lydian - {trimmed}".strip(" -")
    return new_name

def make_new_style(old_style: str) -> str:
    if not old_style:
        return "lydian"
    new_style = re.sub(r"(?i)\bneoclassical\b", "", old_style).strip()
    new_style = re.sub(r"\s+", " ", new_style).strip(" -")
    return new_style if new_style else "lydian"

def is_candidate(data: dict, path: Path) -> bool:
    name = data.get("name","")
    style = data.get("style","")
    fname = path.name.lower()
    return "lydian" in name.lower() or "lydian" in style.lower() or "lydian" in fname

def main():
    files = sorted(LOOPS_DIR.glob("*.json"))
    candidates = []
    for f in files:
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except:
            continue
        if is_candidate(data, f):
            candidates.append(f)
    print(f"Найдено {len(candidates)} кандидатов из {len(files)} файлов (MAX_LEN={MAX_LEN})")
    changed = 0
    for f in candidates:
        data = json.loads(f.read_text(encoding="utf-8"))
        old_name = data.get("name","")
        old_style = data.get("style","")
        new_name = make_new_name(old_name)
        new_style = make_new_style(old_style)
        if old_name != new_name or old_style != new_style:
            data["name"] = new_name
            data["style"] = new_style
            f.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding="utf-8")
            print(f"[CHANGED] {f.name}")
            print(f"  name:  '{old_name}' -> '{new_name}' ({len(new_name)}/{MAX_LEN})")
            print(f"  style: '{old_style}' -> '{new_style}'")
            changed += 1
        else:
            print(f"[OK] {f.name}: '{old_name}'")
    print(f"\nГотово. Изменено {changed}/{len(candidates)} кандидатов.")

if __name__ == "__main__":
    main()
