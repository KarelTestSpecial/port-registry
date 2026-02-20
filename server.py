#!/usr/bin/env python3
"""
Port Registry Service
=====================
Centraal poortenregister voor alle projecten op deze machine.

Bootstrap-poort: 4444 — de ENIGE hardcoded poort in het hele systeem.
Alle andere poorten worden door dit register uitgegeven.

API:
  GET  /                         service-info
  GET  /ports                    alle geregistreerde poorten
  GET  /ports/{service}          poort opvragen voor service (404 als onbekend)
  POST /ports/request            poort aanvragen
  POST /ports/release            poort vrijgeven
  GET  /ports/check/{port}       controleer of een poort vrij is
"""

import json
import socket
import threading
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, HTMLResponse
from pydantic import BaseModel

REGISTRY_FILE = Path(__file__).parent / "registry.json"
BOOTSTRAP_PORT = 4444

lock = threading.Lock()
app = FastAPI(title="Port Registry", version="1.0.0", docs_url="/docs")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


# ── Data ──────────────────────────────────────────────────────────────────────
def load() -> dict:
    with open(REGISTRY_FILE) as f:
        return json.load(f)


def save(data: dict):
    with open(REGISTRY_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ── Poortcheck ────────────────────────────────────────────────────────────────
def port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def find_next_free(data: dict, start: Optional[int] = None) -> int:
    start = start or data.get("next_available", 8002)
    used = {v["port"] for v in data["services"].values()}
    port = start
    while port in used or port_in_use(port):
        port += 1
    return port


# ── Modellen ──────────────────────────────────────────────────────────────────
class RequestBody(BaseModel):
    service: str
    project: str
    description: str = ""
    preferred_port: Optional[int] = None  # optioneel: vraag een specifieke poort


class ReleaseBody(BaseModel):
    service: str


# ── Routes ────────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def root():
    data = load()
    services_html = "".join([
        f"<li><strong>{name}</strong>: <a href='http://localhost:{info['port']}'>:{info['port']}</a> ({info['project']})</li>"
        for name, info in data["services"].items()
    ])
    
    html_content = f"""
    <html>
        <head>
            <title>⚓ Port Registry</title>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; line-height: 1.6; max-width: 800px; margin: 40px auto; padding: 20px; background: #f8f9fa; color: #212529; }}
                h1 {{ color: #0d6efd; border-bottom: 2px solid #0d6efd; padding-bottom: 10px; display: flex; align-items: center; gap: 10px; }}
                .status {{ background: #e7f1ff; padding: 15px; border-radius: 8px; border-left: 5px solid #0d6efd; margin-bottom: 20px; }}
                ul {{ list-style-type: none; padding: 0; }}
                li {{ background: #fff; margin: 8px 0; padding: 12px; border-radius: 6px; box-shadow: 0 1px 2px rgba(0,0,0,0.05); border: 1px solid #dee2e6; }}
                a {{ color: #0d6efd; text-decoration: none; font-weight: 600; }}
                a:hover {{ text-decoration: underline; }}
                .footer {{ margin-top: 40px; font-size: 0.85em; color: #6c757d; border-top: 1px solid #dee2e6; padding-top: 20px; }}
                .badge {{ background: #0d6efd; color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.8em; font-weight: bold; }}
            </style>
        </head>
        <body>
            <h1>⚓ Port Registry</h1>
            <div class="status">
                <p>Bootstrap Port: <strong>{BOOTSTRAP_PORT}</strong></p>
                <p>Registered Services: <span class="badge">{len(data["services"])}</span></p>
                <p>API Documentation: <a href="/docs">/docs</a></p>
            </div>
            <h2>Geregistreerde Services</h2>
            <ul>
                {services_html}
            </ul>
            <div class="footer">
                Karel's Assistant Ecosystem &mdash; Centralized Port Management
            </div>
        </body>
    </html>
    """
    return HTMLResponse(content=html_content)


@app.get("/ports")
def get_all_ports():
    data = load()
    services = data["services"]
    result = {}
    for name, info in services.items():
        result[name] = {**info, "in_use": port_in_use(info["port"])}
    return JSONResponse(result)


@app.get("/ports/{service}")
def get_service_port(service: str):
    data = load()
    if service not in data["services"]:
        raise HTTPException(status_code=404, detail=f"Service '{service}' niet geregistreerd")
    info = data["services"][service]
    return {**info, "in_use": port_in_use(info["port"])}


@app.post("/ports/request")
def request_port(body: RequestBody):
    with lock:
        data = load()
        services = data["services"]

        # Al geregistreerd → geef dezelfde poort terug (sticky)
        if body.service in services:
            existing = services[body.service]
            return {
                "port": existing["port"],
                "service": body.service,
                "assigned_now": False,
                "message": f"Bestaande toewijzing: :{existing['port']}",
            }

        # Voorkeur opgegeven?
        if body.preferred_port:
            used = {v["port"] for v in services.values()}
            if body.preferred_port in used:
                # Conflict — wie heeft deze poort?
                owner = next(k for k, v in services.items() if v["port"] == body.preferred_port)
                raise HTTPException(
                    status_code=409,
                    detail=f"Poort :{body.preferred_port} is al in gebruik door '{owner}'",
                )
            if port_in_use(body.preferred_port):
                raise HTTPException(
                    status_code=409,
                    detail=f"Poort :{body.preferred_port} is bezet door een proces buiten het register",
                )
            assigned_port = body.preferred_port
        else:
            assigned_port = find_next_free(data)

        # Registreer
        services[body.service] = {
            "port": assigned_port,
            "project": body.project,
            "description": body.description,
        }
        data["next_available"] = find_next_free(data, assigned_port + 1)
        save(data)

        return {
            "port": assigned_port,
            "service": body.service,
            "assigned_now": True,
            "message": f"Nieuwe toewijzing: :{assigned_port}",
        }


@app.post("/ports/release")
def release_port(body: ReleaseBody):
    with lock:
        data = load()
        if body.service not in data["services"]:
            raise HTTPException(status_code=404, detail=f"Service '{body.service}' niet gevonden")
        removed = data["services"].pop(body.service)
        save(data)
        return {"released": body.service, "port": removed["port"]}


@app.get("/ports/check/{port}")
def check_port(port: int):
    data = load()
    used_by = next(
        (name for name, v in data["services"].items() if v["port"] == port), None
    )
    return {
        "port": port,
        "in_use": port_in_use(port),
        "registered_to": used_by,
        "free": not used_by and not port_in_use(port),
    }


# ── Main ──────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    print(f"\n  Port Registry draait op http://localhost:{BOOTSTRAP_PORT}")
    print(f"  Docs: http://localhost:{BOOTSTRAP_PORT}/docs\n")
    uvicorn.run(app, host="0.0.0.0", port=BOOTSTRAP_PORT, log_level="warning")
