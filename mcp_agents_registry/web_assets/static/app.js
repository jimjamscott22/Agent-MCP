const projectsNode = document.getElementById('projects');
const outputNode = document.getElementById('output');
const summaryNode = document.getElementById('summary');
const statusNode = document.getElementById('status');
const pathInput = document.getElementById('pathInput');
const searchInput = document.getElementById('search');
const filePathInput = document.getElementById('filePathInput');
const fileEditor = document.getElementById('fileEditor');

let activeProjectName = null;
let loadedFileMeta = null;
let pendingPreviewContent = null;

function pretty(data) {
  return JSON.stringify(data, null, 2);
}

function setStatus(text) {
  statusNode.textContent = text;
}

async function callApi(url, options) {
  setStatus('Working...');
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) {
    throw new Error(body.detail || 'Request failed');
  }
  setStatus('Ready');
  return body;
}

function parseCsvList(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function renderProjects(projects) {
  projectsNode.innerHTML = '';
  for (const project of projects) {
    const li = document.createElement('li');
    li.innerHTML = `<strong>${project.project_name}</strong><small>${project.project_root}</small>`;
    if (Array.isArray(project.tags)) {
      for (const tag of project.tags.slice(0, 4)) {
        const tagNode = document.createElement('span');
        tagNode.className = 'pill';
        tagNode.textContent = tag;
        li.appendChild(tagNode);
      }
    }
    li.addEventListener('click', () => inspectProject(project.project_name));
    projectsNode.appendChild(li);
  }
}

async function loadProjects() {
  try {
    const payload = await callApi('/api/projects');
    renderProjects(payload.projects || []);
    summaryNode.textContent = `Loaded ${payload.projects.length} project(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function inspectProject(projectName) {
  try {
    activeProjectName = projectName;
    const payload = await callApi(`/api/projects/${encodeURIComponent(projectName)}`);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = payload.summary || `Project: ${projectName}`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function refreshIndex() {
  try {
    const payload = await callApi('/api/refresh', { method: 'POST' });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Refresh complete. Added: ${payload.added}, Changed: ${payload.changed}, Removed: ${payload.removed}`;
    await loadProjects();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function searchProjects() {
  try {
    const query = searchInput.value.trim();
    const payload = await callApi(`/api/search?query=${encodeURIComponent(query)}`);
    renderProjects(payload.matches || []);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Search returned ${(payload.matches || []).length} project(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function resolveContext() {
  try {
    const path = pathInput.value.trim();
    if (!path) {
      throw new Error('Enter a path first.');
    }
    const payload = await callApi(`/api/context?path=${encodeURIComponent(path)}`);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Resolved context with ${(payload.matched_projects || []).length} matching project(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function loadEffectiveProjectContext() {
  try {
    if (!activeProjectName) {
      throw new Error('Select a project first.');
    }
    const payload = await callApi(`/api/projects/${encodeURIComponent(activeProjectName)}/effective`);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Effective context for ${activeProjectName}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function loadInventory() {
  try {
    const [accounts, devices, installations] = await Promise.all([
      callApi('/api/accounts'),
      callApi('/api/devices'),
      callApi('/api/installations'),
    ]);
    outputNode.textContent = pretty({
      accounts: accounts.accounts || [],
      devices: devices.devices || [],
      installations: installations.installations || [],
    });
    summaryNode.textContent = 'Loaded accounts/devices/installations.';
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function createAccount() {
  try {
    const payload = await callApi('/api/accounts', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id: document.getElementById('accountId').value.trim(),
        display_name: document.getElementById('accountName').value.trim(),
        provider: document.getElementById('accountProvider').value.trim(),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Created account ${payload.account_id}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function createDevice() {
  try {
    const payload = await callApi('/api/devices', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        device_id: document.getElementById('deviceId').value.trim(),
        display_name: document.getElementById('deviceName').value.trim(),
        platform: document.getElementById('devicePlatform').value.trim(),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Created device ${payload.device_id}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function assignInstallation() {
  try {
    const payload = await callApi('/api/installations', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        account_id: document.getElementById('instAccountId').value.trim(),
        device_id: document.getElementById('instDeviceId').value.trim(),
        agent_name: document.getElementById('instAgentName').value.trim(),
        skills: parseCsvList(document.getElementById('instSkills').value),
        notes: document.getElementById('instNotes').value,
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = 'Installation assigned.';
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function listInstallations() {
  try {
    const accountId = document.getElementById('instAccountId').value.trim();
    const deviceId = document.getElementById('instDeviceId').value.trim();
    const agentName = document.getElementById('instAgentName').value.trim();
    const skillFilters = parseCsvList(document.getElementById('instSkills').value);
    const installations = [];
    if (skillFilters.length === 0) {
      const query = new URLSearchParams({
        account_id: accountId,
        device_id: deviceId,
        agent_name: agentName,
      });
      const payload = await callApi(`/api/installations?${query.toString()}`);
      installations.push(...(payload.installations || []));
    } else {
      const seen = new Set();
      for (const skill of skillFilters) {
        const query = new URLSearchParams({
          account_id: accountId,
          device_id: deviceId,
          agent_name: agentName,
          skill,
        });
        const payload = await callApi(`/api/installations?${query.toString()}`);
        for (const installation of payload.installations || []) {
          const key = `${installation.account_id}|${installation.device_id}|${String(installation.agent_name).toLowerCase()}`;
          if (seen.has(key)) {
            continue;
          }
          seen.add(key);
          installations.push(installation);
        }
      }
    }
    const payload = { installations };
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Found ${installations.length} installation(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function whereAgentInstalled() {
  try {
    const agentName = document.getElementById('instAgentName').value.trim();
    const payload = await callApi(`/api/inventory/where-agent?agent_name=${encodeURIComponent(agentName)}`);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Locations for ${agentName}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function skillsForAccountDevice() {
  try {
    const accountId = document.getElementById('instAccountId').value.trim();
    const deviceId = document.getElementById('instDeviceId').value.trim();
    const payload = await callApi(`/api/inventory/skills?account_id=${encodeURIComponent(accountId)}&device_id=${encodeURIComponent(deviceId)}`);
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Skills for ${accountId}/${deviceId}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function showCoverage() {
  try {
    const payload = await callApi('/api/inventory/coverage');
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = 'Inventory coverage report loaded.';
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function listManagedFiles() {
  try {
    const payload = await callApi('/api/files');
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Found ${(payload.files || []).length} managed file(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function readManagedFile() {
  try {
    const filePath = filePathInput.value.trim();
    if (!filePath) {
      throw new Error('Enter a file path first.');
    }
    const payload = await callApi(`/api/files/read?path=${encodeURIComponent(filePath)}`);
    loadedFileMeta = { path: payload.path, sha256: payload.sha256 };
    fileEditor.value = payload.content || '';
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Loaded ${payload.file_name}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function previewSave() {
  try {
    const filePath = filePathInput.value.trim();
    const content = fileEditor.value;
    if (!filePath) {
      throw new Error('Enter a file path first.');
    }
    pendingPreviewContent = content;
    const baseHash = loadedFileMeta?.sha256 || '';
    outputNode.textContent = pretty({
      action: 'preview',
      path: filePath,
      expected_sha256: baseHash,
      preview_length: content.length,
      confirmation_required: true,
    });
    summaryNode.textContent = 'Preview generated. Click Save File to confirm.';
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function saveManagedFile() {
  try {
    const filePath = filePathInput.value.trim();
    if (!filePath) {
      throw new Error('Enter a file path first.');
    }
    const content = pendingPreviewContent ?? fileEditor.value;
    const payload = await callApi('/api/files/write', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: filePath,
        content,
        expected_sha256: loadedFileMeta?.sha256 || '',
      }),
    });
    loadedFileMeta = { path: payload.path, sha256: payload.sha256 };
    pendingPreviewContent = null;
    fileEditor.value = payload.content || '';
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Saved ${payload.file_name}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

document.getElementById('loadBtn').addEventListener('click', loadProjects);
document.getElementById('searchBtn').addEventListener('click', searchProjects);
document.getElementById('refreshBtn').addEventListener('click', refreshIndex);
document.getElementById('resolveBtn').addEventListener('click', resolveContext);
document.getElementById('effectiveBtn').addEventListener('click', loadEffectiveProjectContext);

document.getElementById('loadInventoryBtn').addEventListener('click', loadInventory);
document.getElementById('coverageBtn').addEventListener('click', showCoverage);
document.getElementById('createAccountBtn').addEventListener('click', createAccount);
document.getElementById('createDeviceBtn').addEventListener('click', createDevice);

document.getElementById('assignInstallationBtn').addEventListener('click', assignInstallation);
document.getElementById('listInstallationsBtn').addEventListener('click', listInstallations);
document.getElementById('whereAgentBtn').addEventListener('click', whereAgentInstalled);
document.getElementById('skillsBtn').addEventListener('click', skillsForAccountDevice);

document.getElementById('listFilesBtn').addEventListener('click', listManagedFiles);
document.getElementById('readFileBtn').addEventListener('click', readManagedFile);
document.getElementById('previewSaveBtn').addEventListener('click', previewSave);
document.getElementById('saveFileBtn').addEventListener('click', saveManagedFile);

loadProjects();
