/* LAB-ONLY: deliberately exposed local MQTT/API credentials for this exercise. */
const LAB_MQTT_CONFIG = {
  url: `ws://${location.hostname}:18885`,
  username: 'dashboard',
  password: 'dashboard-lab-only',
};
const LAB_API_TOKEN = 'tenant-a-demo-token';

const telemetryRoot = document.querySelector('#telemetry');
const apiOutput = document.querySelector('#api-output');

function renderTelemetry(messages) {
  const cards = Object.entries(messages).map(([topic, value]) => {
    const card = document.createElement('article');
    const heading = document.createElement('h2');
    const payload = document.createElement('pre');
    heading.textContent = topic;
    payload.textContent = JSON.stringify(value, null, 2);
    card.append(heading, payload);
    return card;
  });
  telemetryRoot.replaceChildren(...cards);
}

async function refreshTelemetry() {
  try {
    const response = await fetch('/api/telemetry', {
      headers: { Authorization: `Bearer ${LAB_API_TOKEN}` },
    });
    const result = await response.json();
    renderTelemetry(result.messages);
    document.querySelector('#connection').textContent = result.mqtt_connected
      ? 'Local MQTT bridge connected'
      : 'Waiting for the local MQTT broker';
  } catch (_error) {
    document.querySelector('#connection').textContent = 'Local telemetry API unavailable';
  }
}

async function loadApiData() {
  const tenant = document.querySelector('#tenant').value;
  const headers = { Authorization: `Bearer ${LAB_API_TOKEN}`, 'X-Tenant-ID': tenant };
  const results = await Promise.all([
    fetch(`/api/warehouse/details?tenant=${encodeURIComponent(tenant)}`, { headers }),
    fetch(`/api/devices?tenant=${encodeURIComponent(tenant)}`, { headers }),
    fetch(`/api/config?tenant=${encodeURIComponent(tenant)}`, { headers }),
  ]);
  const cards = await Promise.all(results.map(async (response) => {
    const card = document.createElement('pre');
    card.textContent = JSON.stringify(await response.json(), null, 2);
    return card;
  }));
  apiOutput.replaceChildren(...cards);
}

document.querySelector('#load-api').addEventListener('click', loadApiData);
refreshTelemetry();
window.setInterval(refreshTelemetry, 1000);

// The browser dashboard uses the HTTP bridge; learners can inspect these values
// and connect to the same local broker with an MQTT client during the exercise.
window.labConnectionInfo = { mqtt: LAB_MQTT_CONFIG, apiToken: LAB_API_TOKEN };
