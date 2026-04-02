const projectsNode = document.getElementById('projects');
const outputNode = document.getElementById('output');
const summaryNode = document.getElementById('summary');
const statusNode = document.getElementById('status');
const pathInput = document.getElementById('pathInput');
const searchInput = document.getElementById('search');

let activeProjectName = null;

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

document.getElementById('loadBtn').addEventListener('click', loadProjects);
document.getElementById('searchBtn').addEventListener('click', searchProjects);
document.getElementById('refreshBtn').addEventListener('click', refreshIndex);
document.getElementById('resolveBtn').addEventListener('click', resolveContext);
document.getElementById('effectiveBtn').addEventListener('click', loadEffectiveProjectContext);

loadProjects();
