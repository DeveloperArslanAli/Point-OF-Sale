import re
import pathlib

root = pathlib.Path(__file__).resolve().parent.parent / "app" / "api" / "routers"
entries = []
for file in root.glob("*.py"):
    text = file.read_text(encoding="utf-8")
    m = re.search(r"APIRouter\([^)]*prefix=['\"]([^'\"]*)", text)
    prefix = m.group(1) if m else ""
    for method, path in re.findall(r"@router\.(get|post|put|patch|delete)\(\s*['\"]([^'\"]*)", text):
        full = (prefix.rstrip("/") + "/" + path.lstrip("/")) if path else (prefix or "/")
        full = re.sub(r"//+", "/", "/" + full.lstrip("/"))
        entries.append((file.name, method.upper(), full))

entries = sorted(entries, key=lambda x: (x[2], x[1]))
for fname, method, full in entries:
    print(f"{method:6} {full}   # {fname}")
