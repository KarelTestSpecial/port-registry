#!/bin/bash
# Port Registry — installatie
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Port Registry installatie"
echo "  Bootstrap-poort: 4444 (enige hardcoded waarde)"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Venv
if [ ! -d "$DIR/venv" ]; then
    python3 -m venv "$DIR/venv"
fi
"$DIR/venv/bin/pip" install -q --upgrade pip
"$DIR/venv/bin/pip" install -q -r "$DIR/requirements.txt"
echo "✓  Dependencies geïnstalleerd"

chmod +x "$DIR/client.sh"

# Symlink in ~/bin
mkdir -p "$HOME/bin"
cat > "$HOME/bin/port-registry" << WRAPPER
#!/bin/bash
source "$DIR/venv/bin/activate"
exec python "$DIR/server.py" "\$@"
WRAPPER
chmod +x "$HOME/bin/port-registry"
echo "✓  port-registry beschikbaar in ~/bin"

# Voeg toe aan pmctl
PMCTL_PROJECTS="$HOME/pmctl/projects.json"
if [ -f "$PMCTL_PROJECTS" ] && ! grep -q "port-registry" "$PMCTL_PROJECTS"; then
    echo "✓  Voeg port-registry toe aan pmctl... (handmatig via pmctl add)"
fi

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Klaar! Start het register:"
echo ""
echo "    port-registry                  # als daemon"
echo "    python $DIR/server.py          # direct"
echo ""
echo "  Gebruik in projecten:"
echo "    Bash:   source ~/port-registry/client.sh"
echo "            PORT=\$(registry_get_port \"mijn-service\" \"project\")"
echo ""
echo "    Python: from client import get_port"
echo "            port = get_port('mijn-service', project='project')"
echo ""
echo "    Node:   import { getPort } from '~/port-registry/client.js'"
echo "            const port = await getPort('mijn-service')"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
