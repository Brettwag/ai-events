const state = {
  runtime: null,
  sources: [],
  candidates: [],
  workflows: [],
  reviewQueue: [],
  reviewQueueSheetName: "",
  reviewQueueError: "",
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
document.getElementById("refresh-review-queue").addEventListener("click", () => refreshReviewQueue());

bootstrap();

async function bootstrap() {
  await Promise.all([loadRuntime(), loadSources(), loadCandidates(), loadWorkflows()]);
  renderRuntime();
  renderSources();
  renderCandidates();
  renderWorkflows();
  await refreshReviewQueue({ silent: true });
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

async function refreshReviewQueue({ silent = false } = {}) {
  try {
    const payload = await fetchJson("/api/review-queue");
    state.reviewQueue = payload.rows || [];
    state.reviewQueueSheetName = payload.sheet_name || "";
    state.reviewQueueError = "";
    renderReviewQueue();
    if (!silent) {
      setStatus("Review queue refreshed");
    }
  } catch (error) {
    state.reviewQueue = [];
    state.reviewQueueSheetName = "";
    state.reviewQueueError = error.message;
    renderReviewQueue();
    if (!silent) {
      setStatus("Review queue unavailable");
    }
  }
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
    review: "Review Queue",
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

function renderReviewQueue() {
  const container = document.getElementById("review-queue-list");
  const sheetName = document.getElementById("review-sheet-name");
  sheetName.textContent = state.reviewQueueSheetName
    ? `Backed by Google Sheet: ${state.reviewQueueSheetName}`
    : "Backed by Google Sheet once local credentials are available";

  container.innerHTML = "";
  if (state.reviewQueueError) {
    container.innerHTML = `<div class="empty error-block">${escapeHtml(state.reviewQueueError)}</div>`;
    return;
  }
  if (!state.reviewQueue.length) {
    container.innerHTML = `<div class="empty">No event rows are in the review queue yet.</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "data-table review-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Event</th>
        <th>When</th>
        <th>Location</th>
        <th>Source</th>
        <th>Quality</th>
        <th>Review</th>
        <th>Notes</th>
        <th>Links</th>
      </tr>
    </thead>
    <tbody>
      ${state.reviewQueue.map((row) => reviewRow(row)).join("")}
    </tbody>
  `;
  container.appendChild(table);

  container.querySelectorAll("[data-review-save]").forEach((button) => {
    button.addEventListener("click", async () => {
      await saveReviewRow(button.dataset.reviewSave);
    });
  });

  container.querySelectorAll("[data-quick-status]").forEach((button) => {
    button.addEventListener("click", async () => {
      await applyQuickReview(
        button.dataset.recordId,
        button.dataset.quickStatus,
        button.dataset.quickExport === "true"
      );
    });
  });
}

function renderSources() {
  const container = document.getElementById("sources-list");
  container.innerHTML = "";
  if (!state.sources.length) {
    container.innerHTML = `<div class="empty">No approved sources yet.</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Source</th>
        <th>Status</th>
        <th>Organization</th>
        <th>Base URL</th>
        <th>Seed URLs</th>
        <th>Mode</th>
        <th>Geography</th>
        <th>Notes</th>
        <th></th>
      </tr>
    </thead>
    <tbody>
      ${state.sources.map((source, index) => sourceRow(source, index)).join("")}
    </tbody>
  `;
  container.appendChild(table);

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
  const table = document.createElement("table");
  table.className = "data-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Source</th>
        <th>Status</th>
        <th>Priority</th>
        <th>Type</th>
        <th>Base URL</th>
        <th>Seed URL</th>
        <th>Geography</th>
        <th>Parser</th>
      </tr>
    </thead>
    <tbody>
      ${state.candidates.map((candidate) => candidateRow(candidate)).join("")}
    </tbody>
  `;
  container.appendChild(table);
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
      value = value
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
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
      value = value
        .split("\n")
        .map((item) => item.trim())
        .filter(Boolean);
    }
    acc[index][input.dataset.key] = value;
    return acc;
  }, []);
  state.sources = sources;
  await postJson("/api/sources", { sources });
  setStatus("Sources saved");
}

async function saveReviewRow(recordId) {
  const row = document.querySelector(`[data-review-row="${cssEscape(recordId)}"]`);
  if (!row) {
    return;
  }
  const payload = {
    updates: [
      {
        record_id: recordId,
        review_status: row.querySelector("[data-review-status]").value,
        approved_for_export: row.querySelector("[data-review-export]").checked,
        reviewer_notes: row.querySelector("[data-review-notes]").value,
      },
    ],
  };

  const button = row.querySelector("[data-review-save]");
  const previousLabel = button.textContent;
  button.disabled = true;
  button.textContent = "Saving...";
  try {
    await postJson("/api/review-queue", payload);
    setStatus("Review saved");
    await refreshReviewQueue({ silent: true });
  } finally {
    button.disabled = false;
    button.textContent = previousLabel;
  }
}

async function applyQuickReview(recordId, status, approvedForExport) {
  const row = document.querySelector(`[data-review-row="${cssEscape(recordId)}"]`);
  if (!row) {
    return;
  }
  row.querySelector("[data-review-status]").value = status;
  row.querySelector("[data-review-export]").checked = approvedForExport;
  await saveReviewRow(recordId);
}

function reviewRow(row) {
  return `
    <tr data-review-row="${escapeHtml(row.record_id)}">
      <td class="cell-title review-event-cell">
        <div class="cell-stack">
          <strong>${escapeHtml(row.event_title || "Untitled event")}</strong>
          <div class="cell-subtitle">${escapeHtml(formatWhen(row))}</div>
          <div class="tag-list compact">
            ${renderPill(row.source_method, "info")}
            ${renderPill(row.status_recommendation, "neutral")}
          </div>
          ${row.description ? `<div class="review-description">${escapeHtml(truncate(row.description, 180))}</div>` : ""}
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(row.start_date || "Missing date")}</strong>
          <div class="cell-subtitle">${escapeHtml(row.start_time || "Time missing")}</div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(row.venue_name || "Location pending")}</strong>
          <div class="cell-subtitle">${escapeHtml(row.location_display || row.city || "Needs location review")}</div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(row.source_organization || row.source_domain || "Unknown source")}</strong>
          <div class="cell-subtitle">${escapeHtml(row.source_domain || "")}</div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <div class="tag-list compact">
            ${renderPill(row.trust_level || "unrated", toneForTrust(row.trust_level))}
            ${renderPill(row.confidence_score ? `score ${row.confidence_score}` : "score n/a", "neutral")}
          </div>
          <div class="tag-list compact">
            ${row.missing_fields.map((item) => renderPill(item, "warning")).join("")}
            ${row.risk_flags.map((item) => renderPill(item, "danger")).join("")}
          </div>
        </div>
      </td>
      <td class="review-controls">
        <select class="table-select" data-review-status>
          ${reviewStatusOptions(row.review_status)}
        </select>
        <label class="checkbox-row">
          <input type="checkbox" data-review-export ${row.approved_for_export ? "checked" : ""} />
          <span>Approved for export</span>
        </label>
        <div class="row-actions">
          <button class="button button-small" data-quick-status="Approved" data-quick-export="true" data-record-id="${escapeHtml(row.record_id)}">Approve</button>
          <button class="button button-small" data-quick-status="Rejected" data-quick-export="false" data-record-id="${escapeHtml(row.record_id)}">Reject</button>
          <button class="button button-primary button-small" data-review-save="${escapeHtml(row.record_id)}">Save</button>
        </div>
      </td>
      <td>
        <textarea class="table-textarea review-notes" data-review-notes placeholder="Add reviewer notes...">${escapeHtml(row.reviewer_notes || "")}</textarea>
      </td>
      <td>
        <div class="cell-stack review-links">
          ${row.event_url ? `<a href="${escapeHtml(row.event_url)}" target="_blank" rel="noreferrer">Event page</a>` : ""}
          ${row.source_url ? `<a href="${escapeHtml(row.source_url)}" target="_blank" rel="noreferrer">Source page</a>` : ""}
        </div>
      </td>
    </tr>
  `;
}

function sourceInput(index, key, value, type = "text") {
  if (type === "select") {
    return `
      <select class="table-select" data-source-index="${index}" data-key="${key}">
          <option value="true" ${value === "true" ? "selected" : ""}>Enabled</option>
          <option value="false" ${value !== "true" ? "selected" : ""}>Disabled</option>
      </select>
    `;
  }
  return `<input class="table-input" data-source-index="${index}" data-key="${key}" value="${escapeHtml(value || "")}" />`;
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
  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(payload?.error || `${url} failed`);
  }
  return payload;
}

async function postJson(url, payload) {
  const response = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `${url} failed`);
  }
  return data;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function truncate(value, maxLength) {
  const text = String(value || "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, maxLength - 1)}…`;
}

function formatWhen(row) {
  const parts = [row.start_date, row.start_time].filter(Boolean);
  return parts.join(" at ") || "Date and time pending";
}

function toneForTrust(trustLevel) {
  const tone = String(trustLevel || "").toLowerCase();
  if (tone === "high") {
    return "success";
  }
  if (tone === "medium") {
    return "info";
  }
  if (tone === "low") {
    return "warning";
  }
  return "neutral";
}

function renderPill(value, tone) {
  if (!value) {
    return "";
  }
  return `<span class="meta-pill tone-${tone}">${escapeHtml(value)}</span>`;
}

function reviewStatusOptions(selectedValue) {
  const options = state.runtime?.review?.allowed_statuses || ["Pending", "Approved", "Rejected", "Needs Edit"];
  return options
    .map(
      (status) =>
        `<option value="${escapeHtml(status)}" ${status === selectedValue ? "selected" : ""}>${escapeHtml(status)}</option>`
    )
    .join("");
}

function candidateRow(candidate) {
  return `
    <tr>
      <td class="cell-title">
        <div class="cell-stack">
          <strong>${escapeHtml(candidate.label)}</strong>
          <div class="cell-subtitle">${escapeHtml(candidate.notes || "")}</div>
        </div>
      </td>
      <td><span class="meta-pill">${escapeHtml(candidate.status)}</span></td>
      <td><span class="meta-pill">${escapeHtml(candidate.priority)}</span></td>
      <td><span class="meta-pill">${escapeHtml(candidate.source_type)}</span></td>
      <td>${escapeHtml(candidate.base_url)}</td>
      <td>${escapeHtml(candidate.seed_url || "")}</td>
      <td>
        <div class="tag-list">
          ${(candidate.geography_tags || []).map((tag) => `<span class="meta-pill">${escapeHtml(tag)}</span>`).join("")}
        </div>
      </td>
      <td>
        <div class="tag-list">
          <span class="meta-pill">${escapeHtml(candidate.parser_difficulty || "unknown")}</span>
          <span class="meta-pill">${escapeHtml(candidate.discovery_shape || "")}</span>
        </div>
      </td>
    </tr>
  `;
}

function sourceRow(source, index) {
  return `
    <tr>
      <td class="cell-title">
        <div class="cell-stack">
          <strong>${escapeHtml(source.label || "Untitled source")}</strong>
          ${sourceInput(index, "label", source.label)}
          <div class="cell-subtitle">ID: ${escapeHtml(source.id || "unset")}</div>
          ${sourceInput(index, "id", source.id)}
        </div>
      </td>
      <td>${sourceInput(index, "enabled", String(Boolean(source.enabled)), "select")}</td>
      <td>${sourceInput(index, "source_organization", source.source_organization)}</td>
      <td>${sourceInput(index, "base_url", source.base_url)}</td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="seed_urls">${(source.seed_urls || []).join("\n")}</textarea>
      </td>
      <td>
        <div class="cell-stack">
          ${sourceInput(index, "type", source.type)}
          ${sourceInput(index, "discovery_mode", source.discovery_mode)}
        </div>
      </td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="geography_tags">${(source.geography_tags || []).join("\n")}</textarea>
      </td>
      <td>
        <textarea class="table-textarea" data-source-index="${index}" data-key="notes">${escapeHtml(source.notes || "")}</textarea>
      </td>
      <td>
        <div class="row-actions">
          <button class="button" data-remove-source="${index}">Remove</button>
        </div>
      </td>
    </tr>
  `;
}

function cssEscape(value) {
  if (window.CSS?.escape) {
    return window.CSS.escape(value);
  }
  return String(value).replaceAll('"', '\\"');
}
