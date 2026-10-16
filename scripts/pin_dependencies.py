"""Freeze direct dependency declarations to the resolved lockfiles."""
import json
import re
import tomllib
from pathlib import Path

root = Path(__file__).resolve().parents[1]
project = root / "backend/pyproject.toml"
versions = {p["name"]: p["version"] for p in tomllib.loads((root / "backend/uv.lock").read_text())["package"]}
project.write_text(re.sub(r'"([a-zA-Z][a-zA-Z0-9_-]*)(\[[^\]]+\])?>=([^"]+)"', lambda m: '"' + m[1] + (m[2] or "") + "==" + versions[m[1]] + '"', project.read_text()))
package = root / "frontend/package.json"
data = json.loads(package.read_text())
lock = json.loads((root / "frontend/package-lock.json").read_text())
for group in ("dependencies", "devDependencies"):
    for name in data[group]:
        data[group][name] = lock["packages"]["node_modules/" + name]["version"]
package.write_text(json.dumps(data, indent=2) + "\n")
