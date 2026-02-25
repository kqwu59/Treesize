const diskListEl = document.getElementById('disk-list');
const statusEl = document.getElementById('status');
const chartEl = document.getElementById('chart');
const tableBodyEl = document.getElementById('results-body');
const barTemplate = document.getElementById('bar-template');

function formatBytes(bytes) {
  if (!bytes) return '0 B';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  const size = bytes / 1024 ** i;
  return `${size.toFixed(size >= 100 ? 0 : 1)} ${units[i]}`;
}

function selectedMounts() {
  return [...document.querySelectorAll('.disk-check:checked')].map((input) => input.value);
}

async function loadDisks() {
  statusEl.textContent = 'Chargement des lecteurs…';
  diskListEl.innerHTML = '';
  const response = await fetch('/api/disks');
  const { disks } = await response.json();

  disks.forEach((disk) => {
    const wrapper = document.createElement('label');
    wrapper.className = 'disk-item';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.className = 'disk-check';
    checkbox.value = disk.mountpoint;

    const text = document.createElement('span');
    text.textContent = disk.label;

    wrapper.append(checkbox, text);
    diskListEl.append(wrapper);
  });

  statusEl.textContent = `${disks.length} lecteur(s) détecté(s).`;
}

function updateGraph(scans) {
  chartEl.innerHTML = '';
  if (!scans.length) {
    chartEl.textContent = 'Aucune donnée à afficher.';
    return;
  }

  const max = Math.max(...scans.map((scan) => scan.totalBytes), 1);
  scans.forEach((scan) => {
    const row = barTemplate.content.firstElementChild.cloneNode(true);
    row.querySelector('.bar-label').textContent = scan.mountpoint;
    row.querySelector('.bar-fill').style.width = `${(scan.totalBytes / max) * 100}%`;
    row.querySelector('.bar-value').textContent = formatBytes(scan.totalBytes);
    chartEl.append(row);
  });
}

function updateTable(scans) {
  tableBodyEl.innerHTML = '';

  scans.forEach((scan) => {
    scan.entries.forEach((entry) => {
      const row = document.createElement('tr');
      row.innerHTML = `
        <td>${scan.mountpoint}</td>
        <td>${entry.name}</td>
        <td>${entry.path}</td>
        <td class="right">${formatBytes(entry.bytes)}</td>
      `;
      tableBodyEl.append(row);
    });
  });
}

async function scanSelected() {
  const mountpoints = selectedMounts();
  if (!mountpoints.length) {
    statusEl.textContent = 'Sélectionnez au moins un lecteur.';
    return;
  }

  statusEl.textContent = 'Analyse en cours…';

  const response = await fetch('/api/scan', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mountpoints }),
  });

  if (!response.ok) {
    const payload = await response.json();
    statusEl.textContent = payload.error || 'Erreur pendant l’analyse.';
    return;
  }

  const { scans } = await response.json();
  updateGraph(scans);
  updateTable(scans);
  statusEl.textContent = `Analyse terminée sur ${scans.length} lecteur(s).`;
}

document.getElementById('scan').addEventListener('click', scanSelected);
document.getElementById('refresh-disks').addEventListener('click', loadDisks);
document.getElementById('select-all').addEventListener('click', () => {
  document.querySelectorAll('.disk-check').forEach((input) => {
    input.checked = true;
  });
});
document.getElementById('unselect-all').addEventListener('click', () => {
  document.querySelectorAll('.disk-check').forEach((input) => {
    input.checked = false;
  });
});

loadDisks().catch(() => {
  statusEl.textContent = 'Impossible de charger les lecteurs.';
});
