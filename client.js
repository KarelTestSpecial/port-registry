/**
 * Port Registry — Node.js client
 * ================================
 * Gebruik in elk Node.js project om een poort op te vragen:
 *
 *   const { getPort, releasePort } = require('./port-registry/client');
 *   // of als ESM:
 *   import { getPort } from '~/port-registry/client.js';
 *
 *   const port = await getPort('mijn-service', { project: 'mijnproject' });
 *   app.listen(port);
 */

const REGISTRY_URL = process.env.PORT_REGISTRY_URL || 'http://localhost:4444';

async function _post(path, body) {
  const res = await fetch(`${REGISTRY_URL}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(`Port Registry fout ${res.status}: ${err.detail || res.statusText}`);
  }
  return res.json();
}

async function _get(path) {
  const res = await fetch(`${REGISTRY_URL}${path}`, {
    signal: AbortSignal.timeout(3000),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

/**
 * Vraag een poort op voor een service.
 * @param {string} service      - unieke naam, bv. "clawwork-frontend"
 * @param {object} opts
 * @param {string} opts.project      - projectnaam
 * @param {string} opts.description  - omschrijving
 * @param {number} opts.preferredPort - voorkeurs-poort (optioneel)
 * @param {number} opts.fallback     - fallback als register niet bereikbaar
 * @returns {Promise<number>}
 */
async function getPort(service, opts = {}) {
  const { project = '', description = '', preferredPort, fallback } = opts;
  try {
    const payload = { service, project, description };
    if (preferredPort) payload.preferred_port = preferredPort;
    const result = await _post('/ports/request', payload);
    const msg = result.assigned_now
      ? `[port-registry] Nieuwe poort: ${service} → :${result.port}`
      : `[port-registry] Bestaande poort: ${service} → :${result.port}`;
    console.error(msg);
    return result.port;
  } catch (err) {
    if (fallback !== undefined) {
      console.error(`[port-registry] Register niet bereikbaar (${err.message}), fallback: :${fallback}`);
      return fallback;
    }
    console.error(`[port-registry] FOUT: ${err.message}`);
    console.error('[port-registry] Start het register: cd ~/port-registry && python server.py');
    process.exit(1);
  }
}

/**
 * Geef een poort terug vrij (optioneel, bij afsluiten).
 */
async function releasePort(service) {
  try {
    await _post('/ports/release', { service });
    return true;
  } catch {
    return false;
  }
}

/**
 * Zoek de geregistreerde poort voor een service.
 * @returns {Promise<number|null>}
 */
async function getRegisteredPort(service) {
  try {
    const result = await _get(`/ports/${service}`);
    return result.port;
  } catch {
    return null;
  }
}

export { getPort, releasePort, getRegisteredPort };
// CommonJS fallback:
if (typeof module !== 'undefined') {
  module.exports = { getPort, releasePort, getRegisteredPort };
}
