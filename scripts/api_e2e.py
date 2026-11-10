"""Chạy một hợp đồng demo qua API N lần liên tiếp, in số Điều chưa kiểm mỗi lần.

  python api_e2e.py [base_url] [runs]
Tạo tài khoản thử trên API cục bộ (email *.test, mật khẩu ngẫu nhiên, không in ra).
"""
import io
import json
import secrets
import sys
import time
from pathlib import Path

import httpx
from docx import Document

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8011"
RUNS = int(sys.argv[2]) if len(sys.argv) > 2 else 5
DEMO = next(Path("data/demo_contracts").glob("*.md"))

doc = Document()
for line in DEMO.read_text(encoding="utf-8").splitlines():
    if line.strip():
        doc.add_paragraph(line.strip().lstrip("#* ").rstrip("*"))
buf = io.BytesIO()
doc.save(buf)

c = httpx.Client(base_url=BASE + "/api/v1", timeout=600)
email, pw = f"e2e-{secrets.token_hex(4)}@example.com", secrets.token_urlsafe(16)
r = c.post("/auth/register", json={"email": email, "password": pw})
r.raise_for_status()
tok = r.json().get("access_token") or c.post("/auth/login", json={"email": email, "password": pw}).json()["access_token"]
c.headers["Authorization"] = f"Bearer {tok}"

results = []
for i in range(1, RUNS + 1):
    t0 = time.time()
    up = c.post("/upload", files={"file": (f"demo_run{i}.docx", buf.getvalue(),
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document")})
    up.raise_for_status()
    cid = up.json().get("contract_id") or up.json().get("id")
    an = c.post("/analyze", json={"contract_id": cid, "force": True})
    row = {"run": i, "http": an.status_code, "seconds": round(time.time() - t0)}
    if an.status_code == 200:
        body = an.json()
        cov = (body.get("analysis") or body).get("coverage") or {}
        risks = body.get("risks") or body.get("risk_items") or []
        row.update(chua_kiem=cov.get("chua_kiem"), da_kiem=cov.get("da_kiem"), tong=cov.get("tong_so_dieu"),
                   chi_tiet=cov.get("chua_kiem_chi_tiet"), so_rui_ro=len(risks))
    else:
        row["error"] = an.text[:300]
    results.append(row)
    print(json.dumps(row, ensure_ascii=False), flush=True)
print("UNCHECKED_PER_RUN:", [r.get("chua_kiem") for r in results])
