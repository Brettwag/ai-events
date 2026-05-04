const state = {
  runtime: null,
  sources: [],
  candidates: [],
  workflows: [],
};

const runtimeFieldSpec = [
  ["project.name", "Project Name", "text"],
  ["project.time_zone", "Time Zone", "text"],
  ["project.run_time_local", "Run Time", "text"],
  ["pilot.radius_miles_min", "Min Radius", "number"],
  ["pilot.radius_miles_max", "Max Radius", "number"],
  ["quality.lookahead_days", "Lookahead Days", "number"],
  ["ai_event_scout.max_events_per_run", "AI Event Target", "number"],
  ["ai_event_scout.max_passes", "AI Event Max Passes", "number"],
  ["ai_event_scout.stop_after_consecutive_empty_passes", "AI Scout Empty Stop", "number"],
  ["source_scout.max_candidates_per_run", "Source Scout Target", "number"],
  ["ai_event_scout.minimum_trust_level", "AI Trust Floor", "select", ["low", "medium", "high"]],
  ["project.review_sheet_name", "Main Queue Sheet", "text"],
  ["project.source_scout_sheet_name", "Source Scout Sheet", "text"],
  ["project.ai_event_scout_sheet_name", "AI Event Sheet", "text"],
  ["pilot.geography", "Geography", "list"],
  ["ai_event_scout.query_focuses", "AI Event Focuses", "list"],
  ["ai_event_scout.source_type_focuses", "Source Type Focuses", "list"],
  ["source_scout.approved_domains", "Approved Domains", "list"],
  ["pilot.geography_notes", "Geography Notes", "textarea"],
];

document.querySelectorAll(".nav-link").forEach((button) => {
  button.addEventListener("click", () => activateView(button.dataset.view));
});

document.getElementById("save-runtime").addEventListener("click", saveRuntime);
document.getElementById("save-sources").addEventListener("click", saveSources);
document.getElementById("add-source").addEventListener("click", () => {
  state.sources.push(blankSource());
  renderSources();
});

bootstrap();

async function bootstrap() {
  await Promise.all([loadRuntime(), loadSources(), loadCandidates(), loadWorkflows()]);
  renderRuntime();
  renderSources();
  renderCandidates();
  renderWorkflows();
}

async function loadRuntime() {
  state.runtime = await fetchJson("/api/runtime");
}

async function loadSources() {
  const payload = await fetchJson("/api/sources");
  state.sources = payload.sources;
}

async function loadCandidates() {
  const payload = await fetchJson("/api/source-candidates");
  state.candidates = payload.candidates;
}

async function loadWorkflows() {
  const payload = await fetchJson("/api/workflows");
  state.workflows = payload.workflows;
}

function activateView(view) {
  document.querySelectorAll(".nav-link").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  document.querySelectorAll(".view").forEach((section) => {
    section.classList.toggle("active", section.id === `view-${view}`);
  });
  document.getElementById("view-title").textContent = {
    inputs: "Inputs",
    sources: "Approved Sources",
    candidates: "Candidate Sources",
    workflows: "Workflows",
  }[view];
}

function renderRuntime() {
  const form = document.getElementById("runtime-form");
  form.innerHTML = "";
  runtimeFieldSpec.forEach(([path, label, type, options]) => {
    const field = document.createElement("div");
    field.className = "field";
    if (type === "textarea" || type === "list") {
      field.classList.add("full");
    }
    const labelEl = document.createElement("label");
    labelEl.textContent = label;
    field.appendChild(labelEl);

    let input;
    const value = getPath(state.runtime, path);
    if (type === "textarea") {
      input = document.createElement("textarea");
      input.value = value ?? "";
    } else if (type === "select") {
      input = document.createElement("select");
      options.forEach((optionValue) => {
        const option = document.createElement("option");
        option.value = optionValue;
        option.textContent = optionValue;
        option.selected = optionValue === value;
        input.appendChild(option);
      });
    } else if (type === "list") {
      input = document.createElement("textarea");
      input.value = Array.isArray(value) ? value.join("\n") : "";
    } else {
      input = document.createElement("input");
      input.type = type;
      input.value = value ?? "";
    }
    input.dataset.path = path;
    input.dataset.kind = type;
    field.appendChild(input);
    form.appendChild(field);
  });
}

function renderSources() {
  const container = document.getElementById("sources-list");
  container.innerHTML = "";
  if (!state.sources.length) {
    container.innerHTML = `<div class="empty">No approved sources yet.</div>`;
    return;
  }

  state.sources.forEach((source, index) => {
    const card = document.createElement("div");
    card.className = "source-card";
    card.innerHTML = `
      <div class="meta-row">
        <span class="meta-pill">${source.enabled ? "Enabled" : "Disabled"}</span>
        <span class="meta-pill">${escapeHtml(source.type || "website")}</span>
        <span class="meta-pill">${escapeHtml(source.discovery_mode || "listing_page")}</span>
      </div>
      <div class="field"><label>Label</label><input data-source-index="${index}" data-key="label" value="${escapeHtml(source.label || "")}" /></div>
      <div class="source-grid">
        ${sourceInput(index, "id", source.id)}
        ${sourceInput(index, "base_url", source.base_url)}
        ${sourceInput(index, "source_organization", source.source_organization)}
        ${sourceInput(index, "type", source.type)}
        ${sourceInput(index, "discovery_mode", source.discovery_mode)}
        ${sourceInput(index, "enabled", String(Boolean(source.enabled)), "select")}
      </div>
      <div class="field full"><label>Seed URLs</label><textarea data-source-index="${index}" data-key="seed_urls">${(source.seed_urls || []).join("\n")}</textarea></div>
      <div class="field full"><label>Geography Tags</label><textarea data-source-index="${index}" data-key="geography_tags">${(source.geography_tags || []).join("\n")}</textarea></div>
      <div class="field full"><label>Notes</label><textarea data-source-index="${index}" data-key="notes">${escapeHtml(source.notes || "")}</textarea></div>
      <div class="panel-actions"><button class="button" data-remove-source="${index}">Remove</button></div>
    `;
    container.appendChild(card);
  });

  container.querySelectorAll("[data-remove-source]").forEach((button) => {
    button.addEventListener("click", () => {
      state.sources.splice(Number(button.dataset.removeSource), 1);
      renderSources();
    });
  });
}

function renderCandidates() {
  const container = document.getElementById("candidate-list");
  container.innerHTML = "";
  if (!state.candidates.length) {
    container.innerHTML = `<div class="empty">No candidate sources yet.</div>`;
    return;
  }
  state.candidates.forEach((candidate) => {
    const card = document.createElement("div");
    card.className = "candidate-card";
    card.innerHTML = `
      <h3>${escapeHtml(candidate.label)}</h3>
      <p>${escapeHtml(candidate.notes || "")}</p>
      <div class="meta-row">
        <span class="meta-pill">${escapeHtml(candidate.status)}</span>
        <span class="meta-pill">${escapeHtml(candidate.priority)}</span>
        <span class="meta-pill">${escapeHtml(candidate.source_type)}</span>
        <span class="meta-pill">${escapeHtml((candidate.geography_tags || []).join(", "))}</span>
      </div>
      <div class="meta-row">
        <span class="meta-pill">${escapeHtml(candidate.base_url)}</span>
      </div>
    `;
    container.appendChild(card);
  });
}

function renderWorkflows() {
  const container = document.getElementById("workflow-list");
  container.innerHTML = "";
  state.workflows.forEach((workflow) => {
    const card = document.createElement("div");
    card.className = "workflow-card";
    card.innerHTML = `
      <h3>${escapeHtml(workflow.name)}</h3>
      <p>${escapeHtml(workflow.purpose)}</p>
      <div class="meta-row">
        <span class="meta-pill">${escapeHtml(workflow.id)}</span>
        <span class="meta-pill">${escapeHtml(workflow.sheet)}</span>
        <span class="meta-pill">Active lane</span>
      </div>
    `;
    container.appendChild(card);
  });
}

async function saveRuntime() {
  const payload = structuredClone(state.runtime);
  document.querySelectorAll("#runtime-form [data-path]").forEach((input) => {
    const kind = input.dataset.kind;
    let value = input.value;
    if (kind === "number") {
      value = Number(value);
    } else if (kind === "list") {
      value = value.split("\n").map((item) => item.trim()).filter(Boolean);
    }
    setPath(payload, input.dataset.path, value);
  });
  await postJson("/api/runtime", payload);
  state.runtime = payload;
  setStatus("Inputs saved");
}

async function saveSources() {
  const sources = Array.from(document.querySelectorAll("[data-source-index]")).reduce((acc, input) => {
    const index = Number(input.dataset.sourceIndex);
    acc[index] ||= structuredClone(state.sources[index]);
    let value = input.value;
    if (input.dataset.key === "enabled") {
      value = value === "true";
    } else if (input.dataset.key === "seed_urls" || input.dataset.key === "geography_tags") {
      value = value.split("\n").map((item) => item.trim()).filter(Boolean);
    }
    acc[index][input.dataset.key] = value;
    return acc;
  }, []);
  state.sources = sources;
  await postJson("/api/sources", { sources });
  setStatus("Sources saved");
}

function sourceInput(index, key, value, type = "text") {
  if (type === "select") {
    return `
      <div class="field">
        <label>${prettyLabel(key)}</label>
        <select data-source-index="${index}" data-key="${key}">
          <option value="true" ${value === "true" ? "selected" : ""}>Enabled</option>
          <option value="false" ${value !== "true" ? "selected" : ""}>Disabled</option>
        </select>
      </div>
    `;
  }
  return `
    <div class="field">
      <label>${prettyLabel(key)}</label>
      <input data-source-index="${index}" data-key="${key}" value="${escapeHtml(value || "")}" />
    </div>
  `;
}

function blankSource() {
  return {
    id: "",
    label: "",
    enabled: true,
    type: "website",
    discovery_mode: "listing_page",
    base_url: "",
    seed_urls: [],
    source_organization: "",
    geography_tags: [],
    notes: "",
  };
}

function getPath(object, path) {
  return path.split(".").reduce((acc, key) => acc?.[key], object);
}

function setPath(object, path, value) {
  const keys = path.split(".");
  const last = keys.pop();
  const target = keys.reduce((acc, key) => acc[key], object);
  target[last] = value;
}

function setStatus(message) {
  document.getElementById("save-status").textContent = message;
  setTimeout(() => {
    document.getElementById("save-status").textContent = "Ready";
  }, 2200);
}

async function fetchJson(url) {
  const response = await fetch(url);
  if (!response.ok) {
    throw new Error(`${url} failed`);
  }
  return response.json();
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw new Error(`${url} failed`);
  }
  return response.json();
}

function prettyLabel(key) {
  return key.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}
