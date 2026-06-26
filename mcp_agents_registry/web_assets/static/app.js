const projectsNode = document.getElementById('projects');
const outputNode = document.getElementById('output');
const summaryNode = document.getElementById('summary');
const statusNode = document.getElementById('status');
const pathInput = document.getElementById('pathInput');
const searchInput = document.getElementById('search');
const filePathInput = document.getElementById('filePathInput');
const fileEditor = document.getElementById('fileEditor');
const projectDetailsNode = document.getElementById('projectDetails');
const adminStateNode = document.getElementById('adminState');
const diffPreviewNode = document.getElementById('diffPreview');
const accountsTableBody = document.getElementById('accountsTableBody');
const devicesTableBody = document.getElementById('devicesTableBody');
const installationsTableBody = document.getElementById('installationsTableBody');
const skillsOverviewNode = document.getElementById('skillsOverview');
const proposalProjectNode = document.getElementById('proposalProject');

let activeProjectName = null;
let loadedFileMeta = null;
let pendingPreviewContent = null;
let adminState = null;
let currentProjects = [];
let currentAccounts = [];
let currentDevices = [];
let currentInstallations = [];

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

function escapeHtml(str) {
  return String(str ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function parseCsvList(value) {
  return value
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseMetadata(value) {
  const metadata = {};
  for (const item of parseCsvList(value)) {
    const index = item.indexOf('=');
    if (index <= 0) continue;
    const key = item.slice(0, index).trim();
    const val = item.slice(index + 1).trim();
    if (key) metadata[key] = val;
  }
  return metadata;
}

function metadataToText(metadata) {
  return Object.entries(metadata || {})
    .map(([key, value]) => `${key}=${value}`)
    .join(', ');
}

function renderPills(items) {
  const list = Array.isArray(items) ? items : [];
  if (list.length === 0) return '<span class="muted">none</span>';
  return list.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join('');
}

function renderProjects(projects) {
  currentProjects = projects;
  const counter = document.getElementById('projectCount');
  if (counter) counter.textContent = `${projects.length} project${projects.length === 1 ? '' : 's'}`;
  projectsNode.innerHTML = '';
  for (const project of projects) {
    const li = document.createElement('li');
    li.innerHTML = `<strong>${escapeHtml(project.project_name)}</strong><small>${escapeHtml(project.project_root)}</small>`;
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
  renderProposalProjectOptions(projects);
}

function renderProposalProjectOptions(projects) {
  if (!proposalProjectNode) return;
  const previous = proposalProjectNode.value;
  proposalProjectNode.innerHTML = '<option value="">Select target project...</option>';
  for (const project of projects) {
    const option = document.createElement('option');
    option.value = project.project_name;
    option.textContent = project.project_name;
    proposalProjectNode.appendChild(option);
  }
  if (projects.some((project) => project.project_name === previous)) {
    proposalProjectNode.value = previous;
  } else if (activeProjectName) {
    proposalProjectNode.value = activeProjectName;
  }
}

async function loadAdminState() {
  try {
    adminState = await callApi('/api/admin/state');
    const writeText = adminState.allow_direct_writes
      ? 'Direct MCP writes enabled'
      : 'Direct MCP writes disabled; use proposals or reviewed admin saves';
    adminStateNode.innerHTML = `
      <span class="state-item"><strong>${escapeHtml(writeText)}</strong></span>
      <span class="state-item">Roots: ${adminState.roots.length}</span>
      <span class="state-item">Files: ${escapeHtml(adminState.agent_filenames.join(', '))}</span>
      <span class="state-item">Merge: ${escapeHtml(adminState.merge_mode)}</span>
    `;
  } catch (error) {
    setStatus('Error');
    adminStateNode.textContent = String(error);
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

function renderProjectDetails(project) {
  const sections = project.parsed_sections?.sections || {};
  const sectionNames = Object.keys(sections);
  projectDetailsNode.innerHTML = `
    <div class="detail-grid">
      <div><span class="label">Project</span><strong>${escapeHtml(project.project_name)}</strong></div>
      <div><span class="label">Root</span><code>${escapeHtml(project.project_root)}</code></div>
      <div><span class="label">Managed file</span><code>${escapeHtml(project.agent_file_path)}</code></div>
      <div><span class="label">Parent</span>${escapeHtml(project.parent_project_name || 'none')}</div>
      <div><span class="label">Children</span>${project.child_project_names?.length || 0}</div>
      <div><span class="label">Modified</span>${escapeHtml(project.last_modified || '')}</div>
    </div>
    <div class="detail-section"><span class="label">Tags</span>${renderPills(project.tags || [])}</div>
    <div class="detail-section"><span class="label">Parsed sections</span>${renderPills(sectionNames)}</div>
  `;
}

async function inspectProject(projectName) {
  try {
    activeProjectName = projectName;
    const payload = await callApi(`/api/projects/${encodeURIComponent(projectName)}`);
    renderProjectDetails(payload);
    filePathInput.value = payload.agent_file_path || '';
    pathInput.value = payload.project_root || '';
    if (proposalProjectNode) proposalProjectNode.value = projectName;
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

function renderInventoryTables(payload) {
  currentAccounts = payload.accounts || [];
  currentDevices = payload.devices || [];
  currentInstallations = payload.installations || [];

  accountsTableBody.innerHTML = currentAccounts.map((account) => `
    <tr>
      <td><code>${escapeHtml(account.account_id)}</code></td>
      <td>${escapeHtml(account.display_name)}</td>
      <td>${escapeHtml(account.provider || '')}</td>
      <td>${renderPills(account.tags || [])}</td>
      <td>
        <button class="mini secondary" data-action="edit-account" data-id="${escapeHtml(account.account_id)}">Edit</button>
        <button class="mini danger" data-action="delete-account" data-id="${escapeHtml(account.account_id)}">Delete</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="5" class="muted">No accounts.</td></tr>';

  devicesTableBody.innerHTML = currentDevices.map((device) => `
    <tr>
      <td><code>${escapeHtml(device.device_id)}</code></td>
      <td>${escapeHtml(device.display_name)}</td>
      <td>${escapeHtml(device.platform || '')}</td>
      <td>${renderPills(device.tags || [])}</td>
      <td>
        <button class="mini secondary" data-action="edit-device" data-id="${escapeHtml(device.device_id)}">Edit</button>
        <button class="mini danger" data-action="delete-device" data-id="${escapeHtml(device.device_id)}">Delete</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="5" class="muted">No devices.</td></tr>';

  installationsTableBody.innerHTML = currentInstallations.map((installation) => `
    <tr>
      <td><code>${escapeHtml(installation.account_id)}</code></td>
      <td><code>${escapeHtml(installation.device_id)}</code></td>
      <td>${escapeHtml(installation.agent_name)}</td>
      <td>${renderPills(installation.skills || [])}</td>
      <td>
        <button class="mini secondary" data-action="load-installation"
          data-account="${escapeHtml(installation.account_id)}"
          data-device="${escapeHtml(installation.device_id)}"
          data-agent="${escapeHtml(installation.agent_name)}">Edit</button>
        <button class="mini danger" data-action="remove-installation"
          data-account="${escapeHtml(installation.account_id)}"
          data-device="${escapeHtml(installation.device_id)}"
          data-agent="${escapeHtml(installation.agent_name)}">Remove</button>
      </td>
    </tr>
  `).join('') || '<tr><td colspan="5" class="muted">No installations.</td></tr>';

  renderSkillsOverview(currentInstallations);
  wireInventoryRowActions();
}

function renderSkillsOverview(installations) {
  const counts = new Map();
  for (const installation of installations) {
    for (const skill of installation.skills || []) {
      counts.set(skill, (counts.get(skill) || 0) + 1);
    }
  }
  if (counts.size === 0) {
    skillsOverviewNode.textContent = 'No skills assigned yet.';
    return;
  }
  const items = Array.from(counts.entries())
    .sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
    .map(([skill, count]) => `<span class="pill">${escapeHtml(skill)} (${count})</span>`)
    .join('');
  skillsOverviewNode.innerHTML = items;
}

function wireInventoryRowActions() {
  document.querySelectorAll('[data-action="edit-account"]').forEach((button) => {
    button.addEventListener('click', () => updateAccount(button.dataset.id));
  });
  document.querySelectorAll('[data-action="delete-account"]').forEach((button) => {
    button.addEventListener('click', () => deleteAccount(button.dataset.id));
  });
  document.querySelectorAll('[data-action="edit-device"]').forEach((button) => {
    button.addEventListener('click', () => updateDevice(button.dataset.id));
  });
  document.querySelectorAll('[data-action="delete-device"]').forEach((button) => {
    button.addEventListener('click', () => deleteDevice(button.dataset.id));
  });
  document.querySelectorAll('[data-action="load-installation"]').forEach((button) => {
    button.addEventListener('click', () => loadInstallationIntoForm(button.dataset.account, button.dataset.device, button.dataset.agent));
  });
  document.querySelectorAll('[data-action="remove-installation"]').forEach((button) => {
    button.addEventListener('click', () => removeInstallation(button.dataset.account, button.dataset.device, button.dataset.agent));
  });
}

async function loadInventory() {
  try {
    const [accounts, devices, installations] = await Promise.all([
      callApi('/api/accounts'),
      callApi('/api/devices'),
      callApi('/api/installations'),
    ]);
    const payload = {
      accounts: accounts.accounts || [],
      devices: devices.devices || [],
      installations: installations.installations || [],
    };
    renderInventoryTables(payload);
    outputNode.textContent = pretty(payload);
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
        tags: parseCsvList(document.getElementById('accountTags').value),
        metadata: parseMetadata(document.getElementById('accountMetadata').value),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Created account ${payload.account_id}.`;
    await loadInventory();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function updateAccount(accountId) {
  try {
    const account = currentAccounts.find((item) => item.account_id === accountId);
    if (!account) throw new Error(`Unknown account: ${accountId}`);
    const displayName = prompt('Account display name', account.display_name);
    if (displayName === null) return;
    const provider = prompt('Provider', account.provider || '');
    if (provider === null) return;
    const tags = prompt('Tags, comma separated', (account.tags || []).join(', '));
    if (tags === null) return;
    const metadata = prompt('Metadata key=value, comma separated', metadataToText(account.metadata));
    if (metadata === null) return;
    const payload = await callApi(`/api/accounts/${encodeURIComponent(accountId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_name: displayName,
        provider,
        tags: parseCsvList(tags),
        metadata: parseMetadata(metadata),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Updated account ${accountId}.`;
    await loadInventory();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function deleteAccount(accountId) {
  try {
    const impacted = currentInstallations.filter((item) => item.account_id === accountId).length;
    const ok = await confirmAction(
      'Delete account',
      `Delete account ${accountId}? This will remove ${impacted} related installation${impacted === 1 ? '' : 's'}.`
    );
    if (!ok) return;
    const payload = await callApi(`/api/accounts/${encodeURIComponent(accountId)}`, { method: 'DELETE' });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Deleted account ${accountId}.`;
    await loadInventory();
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
        tags: parseCsvList(document.getElementById('deviceTags').value),
        metadata: parseMetadata(document.getElementById('deviceMetadata').value),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Created device ${payload.device_id}.`;
    await loadInventory();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function updateDevice(deviceId) {
  try {
    const device = currentDevices.find((item) => item.device_id === deviceId);
    if (!device) throw new Error(`Unknown device: ${deviceId}`);
    const displayName = prompt('Device display name', device.display_name);
    if (displayName === null) return;
    const platform = prompt('Platform', device.platform || '');
    if (platform === null) return;
    const tags = prompt('Tags, comma separated', (device.tags || []).join(', '));
    if (tags === null) return;
    const metadata = prompt('Metadata key=value, comma separated', metadataToText(device.metadata));
    if (metadata === null) return;
    const payload = await callApi(`/api/devices/${encodeURIComponent(deviceId)}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        display_name: displayName,
        platform,
        tags: parseCsvList(tags),
        metadata: parseMetadata(metadata),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Updated device ${deviceId}.`;
    await loadInventory();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function deleteDevice(deviceId) {
  try {
    const impacted = currentInstallations.filter((item) => item.device_id === deviceId).length;
    const ok = await confirmAction(
      'Delete device',
      `Delete device ${deviceId}? This will remove ${impacted} related installation${impacted === 1 ? '' : 's'}.`
    );
    if (!ok) return;
    const payload = await callApi(`/api/devices/${encodeURIComponent(deviceId)}`, { method: 'DELETE' });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Deleted device ${deviceId}.`;
    await loadInventory();
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
    await loadInventory();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

function loadInstallationIntoForm(accountId, deviceId, agentName) {
  const installation = currentInstallations.find((item) => (
    item.account_id === accountId
    && item.device_id === deviceId
    && item.agent_name === agentName
  ));
  document.getElementById('instAccountId').value = accountId || '';
  document.getElementById('instDeviceId').value = deviceId || '';
  document.getElementById('instAgentName').value = agentName || '';
  document.getElementById('instSkills').value = (installation?.skills || []).join(', ');
  document.getElementById('instNotes').value = installation?.notes || '';
  summaryNode.textContent = `Loaded installation ${accountId}/${deviceId}/${agentName} into the form.`;
}

async function removeInstallation(accountId, deviceId, agentName) {
  try {
    const ok = await confirmAction(
      'Remove installation',
      `Remove ${agentName} from ${accountId}/${deviceId}?`
    );
    if (!ok) return;
    const query = new URLSearchParams({ account_id: accountId, device_id: deviceId, agent_name: agentName });
    const payload = await callApi(`/api/installations?${query.toString()}`, { method: 'DELETE' });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = payload.removed ? 'Installation removed.' : 'No matching installation found.';
    await loadInventory();
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
      const query = new URLSearchParams({ account_id: accountId, device_id: deviceId, agent_name: agentName });
      const payload = await callApi(`/api/installations?${query.toString()}`);
      installations.push(...(payload.installations || []));
    } else {
      const seen = new Set();
      for (const skill of skillFilters) {
        const query = new URLSearchParams({ account_id: accountId, device_id: deviceId, agent_name: agentName, skill });
        const payload = await callApi(`/api/installations?${query.toString()}`);
        for (const installation of payload.installations || []) {
          const key = `${installation.account_id}|${installation.device_id}|${String(installation.agent_name).toLowerCase()}`;
          if (seen.has(key)) continue;
          seen.add(key);
          installations.push(installation);
        }
      }
    }
    renderInventoryTables({ accounts: currentAccounts, devices: currentDevices, installations });
    outputNode.textContent = pretty({ installations });
    summaryNode.textContent = `Found ${installations.length} installation(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function searchInventory() {
  try {
    const query = new URLSearchParams({
      account_id: document.getElementById('instAccountId').value.trim(),
      device_id: document.getElementById('instDeviceId').value.trim(),
      agent_name: document.getElementById('instAgentName').value.trim(),
      skill: parseCsvList(document.getElementById('instSkills').value)[0] || '',
      path: document.getElementById('inventorySearchPath').value.trim(),
    });
    const payload = await callApi(`/api/inventory/search?${query.toString()}`);
    renderInventoryTables({ accounts: currentAccounts, devices: currentDevices, installations: payload.installations || [] });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Inventory search returned ${(payload.installations || []).length} installation(s) and ${(payload.files || []).length} file(s).`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function whereAgentInstalled() {
  try {
    const agentName = document.getElementById('instAgentName').value.trim();
    const payload = await callApi(`/api/inventory/where-agent?agent_name=${encodeURIComponent(agentName)}`);
    renderInventoryTables({ accounts: currentAccounts, devices: currentDevices, installations: payload.installations || [] });
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
    renderSkillsOverview(payload.agents || []);
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
    skillsOverviewNode.innerHTML = `
      <span class="pill">Accounts ${payload.totals.accounts}</span>
      <span class="pill">Devices ${payload.totals.devices}</span>
      <span class="pill">Installations ${payload.totals.installations}</span>
      <span class="pill">Skills ${payload.totals.skills}</span>
    `;
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = `Coverage loaded. Unassigned devices: ${payload.unassigned_devices.length}. Unused accounts: ${payload.unused_accounts.length}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function listManagedFiles() {
  try {
    const pathQuery = document.getElementById('inventorySearchPath')?.value.trim() || '';
    const url = pathQuery ? `/api/files?path_query=${encodeURIComponent(pathQuery)}` : '/api/files';
    const payload = await callApi(url);
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
    loadedFileMeta = { path: payload.path, sha256: payload.sha256, content: payload.content || '' };
    fileEditor.value = payload.content || '';
    pendingPreviewContent = null;
    diffPreviewNode.textContent = 'File loaded. Preview before saving to review line changes.';
    outputNode.textContent = pretty({ ...payload, content: `[${payload.content.length} chars]` });
    summaryNode.textContent = `Loaded ${payload.file_name}.`;
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

function previewDiff(original, updated) {
  const beforeLines = String(original || '').split('\n');
  const afterLines = String(updated || '').split('\n');
  let changed = 0;
  const max = Math.max(beforeLines.length, afterLines.length);
  for (let index = 0; index < max; index += 1) {
    if ((beforeLines[index] || '') !== (afterLines[index] || '')) changed += 1;
  }
  return {
    before_lines: beforeLines.length,
    after_lines: afterLines.length,
    changed_lines: changed,
    size_delta: String(updated || '').length - String(original || '').length,
  };
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
    const diff = previewDiff(loadedFileMeta?.content || '', content);
    diffPreviewNode.innerHTML = `
      <strong>Preview:</strong>
      ${diff.changed_lines} changed line${diff.changed_lines === 1 ? '' : 's'}.
      Lines ${diff.before_lines} -> ${diff.after_lines}.
      Size delta ${diff.size_delta >= 0 ? '+' : ''}${diff.size_delta} chars.
    `;
    outputNode.textContent = pretty({
      action: 'preview',
      path: filePath,
      expected_sha256: baseHash,
      ...diff,
      confirmation_required: true,
    });
    summaryNode.textContent = 'Preview generated. Review the line summary before committing.';
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
    const diff = previewDiff(loadedFileMeta?.content || '', content);
    const ok = await confirmAction(
      'Commit file save',
      `Write ${filePath}? This changes ${diff.changed_lines} line${diff.changed_lines === 1 ? '' : 's'}.`
    );
    if (!ok) return;
    const payload = await callApi('/api/files/write', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: filePath,
        content,
        expected_sha256: loadedFileMeta?.sha256 || '',
      }),
    });
    loadedFileMeta = { path: payload.path, sha256: payload.sha256, content: payload.content || '' };
    pendingPreviewContent = null;
    fileEditor.value = payload.content || '';
    diffPreviewNode.textContent = 'File saved. Index refreshed.';
    outputNode.textContent = pretty({ ...payload, content: `[${payload.content.length} chars]` });
    summaryNode.textContent = `Saved ${payload.file_name}.`;
    await loadProjects();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function saveManagedFileSection() {
  try {
    const filePath = filePathInput.value.trim();
    const sectionHeading = document.getElementById('sectionHeadingInput').value.trim();
    const sectionContent = document.getElementById('sectionContentInput').value;
    if (!filePath || !sectionHeading) {
      throw new Error('Enter a file path and section heading first.');
    }
    const ok = await confirmAction('Save section', `Upsert section "${sectionHeading}" in ${filePath}?`);
    if (!ok) return;
    const payload = await callApi('/api/files/write-section', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        path: filePath,
        section_heading: sectionHeading,
        section_content: sectionContent,
        expected_sha256: loadedFileMeta?.sha256 || '',
      }),
    });
    loadedFileMeta = { path: payload.path, sha256: payload.sha256, content: payload.content || '' };
    fileEditor.value = payload.content || '';
    diffPreviewNode.textContent = `Section "${sectionHeading}" saved.`;
    outputNode.textContent = pretty({ ...payload, content: `[${payload.content.length} chars]` });
    summaryNode.textContent = `Saved section ${sectionHeading}.`;
    await loadProjects();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

async function createProposal() {
  try {
    const payload = await callApi('/api/proposals', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_project: document.getElementById('proposalProject').value.trim(),
        section_heading: document.getElementById('proposalSection').value.trim(),
        proposed_content: document.getElementById('proposalContent').value,
        rationale: document.getElementById('proposalRationale').value.trim(),
        agent_id: document.getElementById('proposalAgentId').value.trim(),
      }),
    });
    outputNode.textContent = pretty(payload);
    summaryNode.textContent = payload.message || 'Proposal created.';
    await loadProposals();
  } catch (error) {
    setStatus('Error');
    outputNode.textContent = String(error);
  }
}

function confirmAction(title, message) {
  const modal = document.getElementById('confirmModal');
  const titleNode = document.getElementById('confirmTitle');
  const messageNode = document.getElementById('confirmMessage');
  const okButton = document.getElementById('confirmOkBtn');
  const cancelButton = document.getElementById('confirmCancelBtn');
  titleNode.textContent = title;
  messageNode.textContent = message;
  modal.hidden = false;
  return new Promise((resolve) => {
    function cleanup(value) {
      modal.hidden = true;
      okButton.removeEventListener('click', onOk);
      cancelButton.removeEventListener('click', onCancel);
      resolve(value);
    }
    function onOk() { cleanup(true); }
    function onCancel() { cleanup(false); }
    okButton.addEventListener('click', onOk);
    cancelButton.addEventListener('click', onCancel);
  });
}

document.getElementById('loadBtn').addEventListener('click', loadProjects);
document.getElementById('searchBtn').addEventListener('click', searchProjects);
document.getElementById('refreshBtn').addEventListener('click', refreshIndex);
document.getElementById('resolveBtn').addEventListener('click', resolveContext);
document.getElementById('effectiveBtn').addEventListener('click', loadEffectiveProjectContext);

document.getElementById('loadInventoryBtn').addEventListener('click', loadInventory);
document.getElementById('coverageBtn').addEventListener('click', showCoverage);
document.getElementById('inventorySearchBtn').addEventListener('click', searchInventory);
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
document.getElementById('writeSectionBtn').addEventListener('click', saveManagedFileSection);
document.getElementById('createProposalBtn').addEventListener('click', createProposal);

// Review Queue

const proposalListNode = document.getElementById('proposalList');
const proposalEmptyNode = document.getElementById('proposalEmpty');
const proposalBadgeNode = document.getElementById('proposalBadge');
const showHistoryNode = document.getElementById('showHistory');

function renderProposals(proposals) {
  proposalListNode.innerHTML = '';
  if (proposals.length === 0) {
    proposalEmptyNode.style.display = '';
    return;
  }
  proposalEmptyNode.style.display = 'none';
  for (const p of proposals) {
    const li = document.createElement('li');
    li.className = 'card';
    li.dataset.id = p.id;
    const isPending = p.status === 'pending';
    li.innerHTML = `
      <div class="card-head">
        <span class="pill">${escapeHtml(p.target_project)}</span>
        <span class="pill mono-small" title="${escapeHtml(p.target_path)}">${escapeHtml(p.section_heading)}</span>
        ${p.agent_id ? `<span class="pill">agent: ${escapeHtml(p.agent_id)}</span>` : ''}
        <span class="pill pill-status pill-${escapeHtml(p.status)}">${escapeHtml(p.status)}</span>
      </div>
      <p class="card-rationale"><em>${escapeHtml(p.rationale)}</em></p>
      ${isPending ? `
        <label class="field-label">Section heading</label>
        <input class="input-heading" type="text" value="${escapeHtml(p.section_heading)}" />
        <label class="field-label">Content</label>
        <textarea class="input-content" rows="6">${escapeHtml(p.proposed_content)}</textarea>
        <div class="card-actions">
          <button class="btn btn-primary btn-approve">Approve</button>
          <button class="btn danger btn-reject">Reject</button>
        </div>
      ` : `<pre class="proposal-content">${escapeHtml(p.proposed_content)}</pre>`}
    `;
    if (isPending) {
      li.querySelector('.btn-approve').addEventListener('click', () => {
        li.dataset.actioned = '1';
        approveProposal(p.id);
      });
      li.querySelector('.btn-reject').addEventListener('click', () => {
        li.dataset.actioned = '1';
        rejectProposal(p.id);
      });
      const contentArea = li.querySelector('.input-content');
      const headingInput = li.querySelector('.input-heading');
      contentArea.addEventListener('blur', () => {
        if (!li.dataset.actioned) saveProposalEdits(p.id, headingInput.value, contentArea.value);
      });
      headingInput.addEventListener('blur', () => {
        if (!li.dataset.actioned) saveProposalEdits(p.id, headingInput.value, contentArea.value);
      });
    }
    proposalListNode.appendChild(li);
  }
}

async function loadProposals() {
  try {
    const showHistory = showHistoryNode && showHistoryNode.checked;
    const url = showHistory ? '/api/proposals' : '/api/proposals?status=pending';
    const data = await callApi(url);
    renderProposals(data.proposals || []);
    updateProposalBadge(data.proposals ? data.proposals.filter((p) => p.status === 'pending').length : 0);
  } catch (err) {
    setStatus('Error loading proposals: ' + err.message);
  }
}

function updateProposalBadge(count) {
  if (!proposalBadgeNode) return;
  if (count > 0) {
    proposalBadgeNode.textContent = count;
    proposalBadgeNode.style.display = '';
  } else {
    proposalBadgeNode.style.display = 'none';
  }
}

async function approveProposal(id) {
  try {
    await callApi(`/api/proposals/${id}/approve`, { method: 'POST' });
    await loadProposals();
    await loadProjects();
  } catch (err) {
    setStatus('Approve failed: ' + err.message);
  }
}

async function rejectProposal(id) {
  try {
    await callApi(`/api/proposals/${id}/reject`, { method: 'POST' });
    await loadProposals();
  } catch (err) {
    setStatus('Reject failed: ' + err.message);
  }
}

async function saveProposalEdits(id, sectionHeading, proposedContent) {
  try {
    await callApi(`/api/proposals/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ section_heading: sectionHeading, proposed_content: proposedContent }),
    });
  } catch (err) {
    setStatus('Auto-save failed: ' + err.message);
  }
}

if (showHistoryNode) {
  showHistoryNode.addEventListener('change', loadProposals);
}

loadAdminState();
loadProjects();
loadInventory();
loadProposals();
