#!/bin/bash
# Port Registry — Bash client
# ============================
# Gebruik in shell scripts om een poort op te vragen:
#
#   source ~/port-registry/client.sh
#   PORT=$(registry_get_port "mijn-service" "mijnproject" "Beschrijving")
#   uvicorn myapp:app --port $PORT
#
# Of direct aanroepen:
#   PORT=$(~/port-registry/client.sh get "mijn-service")
#   PORT=$(~/port-registry/client.sh get "mijn-service" "mijnproject" "Beschrijving" 8005)

REGISTRY_URL="${PORT_REGISTRY_URL:-http://localhost:4444}"

registry_get_port() {
    local SERVICE="$1"
    local PROJECT="${2:-}"
    local DESCRIPTION="${3:-}"
    local PREFERRED="${4:-}"
    local FALLBACK="${5:-}"

    local PAYLOAD
    if [ -n "$PREFERRED" ]; then
        PAYLOAD="{\"service\":\"$SERVICE\",\"project\":\"$PROJECT\",\"description\":\"$DESCRIPTION\",\"preferred_port\":$PREFERRED}"
    else
        PAYLOAD="{\"service\":\"$SERVICE\",\"project\":\"$PROJECT\",\"description\":\"$DESCRIPTION\"}"
    fi

    local RESULT
    RESULT=$(curl -sf -X POST "$REGISTRY_URL/ports/request" \
        -H "Content-Type: application/json" \
        -d "$PAYLOAD" 2>/dev/null)

    if [ $? -ne 0 ] || [ -z "$RESULT" ]; then
        if [ -n "$FALLBACK" ]; then
            echo >&2 "[port-registry] Register niet bereikbaar, fallback: :$FALLBACK"
            echo "$FALLBACK"
            return 0
        fi
        echo >&2 "[port-registry] FOUT: Kan register niet bereiken op $REGISTRY_URL"
        echo >&2 "[port-registry] Start het register: cd ~/port-registry && python server.py"
        return 1
    fi

    local PORT
    PORT=$(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin)['port'])" 2>/dev/null)

    if [ -z "$PORT" ]; then
        # Fallback: parse met grep als python3 niet beschikbaar is
        PORT=$(echo "$RESULT" | grep -o '"port":[0-9]*' | grep -o '[0-9]*')
    fi

    echo >&2 "[port-registry] $SERVICE → :$PORT"
    echo "$PORT"
}

registry_release_port() {
    local SERVICE="$1"
    curl -sf -X POST "$REGISTRY_URL/ports/release" \
        -H "Content-Type: application/json" \
        -d "{\"service\":\"$SERVICE\"}" >/dev/null 2>&1
}

registry_check_port() {
    local PORT="$1"
    curl -sf "$REGISTRY_URL/ports/check/$PORT" 2>/dev/null | \
        python3 -c "import sys,json; d=json.load(sys.stdin); print('vrij' if d['free'] else f'bezet door {d[\"registered_to\"] or \"onbekend proces\"}')" 2>/dev/null
}

# Direct aanroepen als script (niet als source)
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    CMD="${1:-get}"
    shift
    case "$CMD" in
        get)     registry_get_port "$@" ;;
        release) registry_release_port "$@" ;;
        check)   registry_check_port "$@" ;;
        *)
            echo "Gebruik: client.sh [get|release|check] <service> [project] [beschrijving] [voorkeur_poort] [fallback]"
            exit 1
            ;;
    esac
fi
