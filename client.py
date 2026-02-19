"""
Port Registry — Python client
==============================
Gebruik in elk Python-project om een poort op te vragen:

    from client import get_port, release_port

    port = get_port("mijn-service", project="mijnproject", description="...")
    # → int, bv. 8003

    # Bij afsluiten (optioneel):
    release_port("mijn-service")
"""

import os
import sys
import json
import urllib.request
import urllib.error

REGISTRY_URL = os.environ.get("PORT_REGISTRY_URL", "http://localhost:4444")


def _post(path: str, data: dict) -> dict:
    url = f"{REGISTRY_URL}{path}"
    body = json.dumps(data).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(req, timeout=3) as resp:
        return json.loads(resp.read())


def _get(path: str) -> dict:
    url = f"{REGISTRY_URL}{path}"
    with urllib.request.urlopen(url, timeout=3) as resp:
        return json.loads(resp.read())


def get_port(
    service: str,
    project: str = "",
    description: str = "",
    preferred_port: int = None,
    fallback: int = None,
) -> int:
    """
    Vraag een poort op bij het centrale register.
    - Geeft altijd dezelfde poort terug voor dezelfde service (sticky).
    - Als het register niet beschikbaar is: gebruik `fallback` of stop.
    """
    try:
        payload = {"service": service, "project": project, "description": description}
        if preferred_port:
            payload["preferred_port"] = preferred_port
        result = _post("/ports/request", payload)
        port = result["port"]
        if result.get("assigned_now"):
            print(f"[port-registry] Nieuwe poort toegewezen: {service} → :{port}", file=sys.stderr)
        else:
            print(f"[port-registry] Bestaande poort: {service} → :{port}", file=sys.stderr)
        return port
    except Exception as e:
        if fallback is not None:
            print(f"[port-registry] Register niet bereikbaar ({e}), fallback: :{fallback}", file=sys.stderr)
            return fallback
        print(f"[port-registry] FOUT: Register niet bereikbaar op {REGISTRY_URL}: {e}", file=sys.stderr)
        print("[port-registry] Start het register: cd ~/port-registry && python server.py", file=sys.stderr)
        sys.exit(1)


def release_port(service: str) -> bool:
    """Geef een poort terug vrij (optioneel, bij afsluiten)."""
    try:
        _post("/ports/release", {"service": service})
        return True
    except Exception:
        return False


def get_registered_port(service: str) -> int | None:
    """Zoek de geregistreerde poort voor een service (None als onbekend)."""
    try:
        result = _get(f"/ports/{service}")
        return result["port"]
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    except Exception:
        return None


if __name__ == "__main__":
    # Gebruik als CLI: python client.py <service> [project] [description]
    import sys
    if len(sys.argv) < 2:
        print("Gebruik: python client.py <service> [project] [beschrijving]")
        sys.exit(1)
    service = sys.argv[1]
    project = sys.argv[2] if len(sys.argv) > 2 else ""
    desc = sys.argv[3] if len(sys.argv) > 3 else ""
    port = get_port(service, project, desc)
    print(port)  # Alleen het poortnummer op stdout — voor gebruik in shell scripts
