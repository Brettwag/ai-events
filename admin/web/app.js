const state = {
  runtime: null,
  sources: [],
  candidates: [],
  workflows: [],
  reviewRows: [],
  reviewSort: "date",
  reviewLaneStats: [],
  publicIcsFeedUrl: "",
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
document.getElementById("save-review").addEventListener("click", saveReviews);
document.getElementById("refresh-review").addEventListener("click", refreshReviewRows);
document.getElementById("review-sort").addEventListener("change", async (event) => {
  state.reviewSort = event.target.value;
  await refreshReviewRows();
});
document.getElementById("copy-ics-url").addEventListener("click", copyIcsUrl);

bootstrap();

async function bootstrap() {
  await Promise.all([loadRuntime(), loadSources(), loadCandidates(), loadWorkflows()]);
  setIcsFeedUrl();
  renderRuntime();
  renderSources();
  renderCandidates();
  renderWorkflows();
  await refreshReviewRows({ silent: true });
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

async function refreshReviewRows({ silent = false } = {}) {
  try {
    const payload = await fetchJson(`/api/review-queue?sort=${encodeURIComponent(state.reviewSort)}`);
    state.reviewRows = payload.rows || [];
    state.reviewLaneStats = payload.lane_stats || [];
    state.publicIcsFeedUrl = payload.public_ics_feed_url || "";
    setIcsFeedUrl();
    renderReview();
    if (!silent) {
      setStatus("Review refreshed");
    }
  } catch (error) {
    state.reviewRows = [];
    state.reviewLaneStats = [];
    renderReviewError(error.message);
    if (!silent) {
      setStatus("Review unavailable");
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
    review: "Review",
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

function renderReview() {
  renderReviewSummary();
  renderReviewLanes();
  const container = document.getElementById("review-list");
  container.innerHTML = "";

  if (!state.reviewRows.length) {
    container.innerHTML = `<div class="empty">No event rows are available from the workflow sheets yet.</div>`;
    return;
  }

  const table = document.createElement("table");
  table.className = "data-table review-table";
  table.innerHTML = `
    <thead>
      <tr>
        <th>Event</th>
        <th>Timing</th>
        <th>Location</th>
        <th>Source</th>
        <th>Quality</th>
        <th>Review</th>
      </tr>
    </thead>
    <tbody>
      ${state.reviewRows.map((row, index) => reviewRow(row, index)).join("")}
    </tbody>
  `;
  const scrollWrap = document.createElement("div");
  scrollWrap.className = "table-wrap review-scroll-wrap";
  scrollWrap.appendChild(table);
  container.appendChild(scrollWrap);

  container.querySelectorAll("[data-review-status]").forEach((input) => {
    input.addEventListener("change", handleReviewFieldChange);
  });
  container.querySelectorAll("[data-review-export]").forEach((input) => {
    input.addEventListener("change", handleReviewFieldChange);
  });
  container.querySelectorAll("[data-review-notes]").forEach((input) => {
    input.addEventListener("input", handleReviewFieldChange);
  });
}

function renderReviewError(message) {
  renderReviewSummary();
  renderReviewLanes();
  document.getElementById("review-list").innerHTML = `<div class="empty error-block">${escapeHtml(message)}</div>`;
}

function renderReviewSummary() {
  const container = document.getElementById("review-summary");
  const counts = countReviews();
  container.innerHTML = `
    <span class="meta-pill">${state.reviewRows.length} total</span>
    <span class="meta-pill">${counts.pending} pending</span>
    <span class="meta-pill">${counts.approved} approved</span>
    <span class="meta-pill">${counts.needsEdit} needs edit</span>
    <span class="meta-pill">${counts.rejected} rejected</span>
  `;
}

function renderReviewLanes() {
  const container = document.getElementById("review-lanes");
  container.innerHTML = state.reviewLaneStats
    .map(
      (lane) =>
        `<span class="meta-pill">${escapeHtml(lane.label)}: ${escapeHtml(String(lane.event_rows))}</span>`
    )
    .join("");
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

async function saveReviews() {
  syncReviewRowsFromDom();
  const updates = state.reviewRows.map((row) => ({
    record_id: row.record_id,
    sheet_name: row.sheet_name,
    review_status: row.review_status,
    approved_for_export: row.approved_for_export,
    reviewer_notes: row.reviewer_notes,
  }));
  await postJson("/api/review-queue", { updates });
  setStatus("Reviews saved");
  await refreshReviewRows({ silent: true });
}

function handleReviewFieldChange() {
  syncReviewRowsFromDom();
  renderReviewSummary();
}

function syncReviewRowsFromDom() {
  document.querySelectorAll("[data-review-index]").forEach((row) => {
    const index = Number(row.dataset.reviewIndex);
    const statusInput = row.querySelector("[data-review-status]");
    const exportInput = row.querySelector("[data-review-export]");
    const notesInput = row.querySelector("[data-review-notes]");
    if (!state.reviewRows[index]) {
      return;
    }
    state.reviewRows[index].review_status = statusInput.value;
    state.reviewRows[index].approved_for_export = exportInput.checked;
    state.reviewRows[index].reviewer_notes = notesInput.value;
  });
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

function setIcsFeedUrl() {
  const input = document.getElementById("ics-feed-url");
  input.value = state.publicIcsFeedUrl || `${window.location.origin}/api/approved-events.ics`;
}

async function copyIcsUrl() {
  const input = document.getElementById("ics-feed-url");
  input.select();
  input.setSelectionRange(0, input.value.length);
  try {
    await navigator.clipboard.writeText(input.value);
  } catch {
    document.execCommand("copy");
  }
  setStatus("ICS URL copied");
}

async function fetchJson(url) {
  const response = await fetch(url);
  const data = await response.json().catch(() => null);
  if (!response.ok) {
    throw new Error(data?.error || `${url} failed`);
  }
  return data;
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

function reviewRow(row, index) {
  return `
    <tr data-review-index="${index}">
      <td class="cell-title review-event">
        <div class="cell-stack">
          <strong>${escapeHtml(row.event_title || "Untitled event")}</strong>
          <div class="cell-subtitle">${escapeHtml(row.description || "")}</div>
          <div class="tag-list">
            <span class="meta-pill">${escapeHtml(row.record_id)}</span>
            <span class="meta-pill">${escapeHtml(row.queue_label)}</span>
          </div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(formatDateRange(row))}</strong>
          <div class="cell-subtitle">${escapeHtml(formatTimeRange(row))}</div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(row.venue_name || "Location pending")}</strong>
          <div class="cell-subtitle">${escapeHtml(formatLocation(row))}</div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <strong>${escapeHtml(row.source_name || "Unknown source")}</strong>
          <div class="cell-subtitle">${escapeHtml(row.source_method)}</div>
          <div class="review-links">
            ${row.source_url ? `<a href="${escapeHtml(row.source_url)}" target="_blank" rel="noreferrer">Source</a>` : ""}
            ${row.event_url ? `<a href="${escapeHtml(row.event_url)}" target="_blank" rel="noreferrer">Event</a>` : ""}
          </div>
        </div>
      </td>
      <td>
        <div class="cell-stack">
          <div class="tag-list">
            <span class="meta-pill">${escapeHtml(row.trust_level || "unrated")}</span>
            <span class="meta-pill">${escapeHtml(row.confidence_score ? `Score ${row.confidence_score}` : "Score n/a")}</span>
          </div>
          <div class="tag-list">
            ${row.missing_fields.map((item) => `<span class="meta-pill meta-pill-warn">${escapeHtml(item)}</span>`).join("")}
            ${row.risk_flags.map((item) => `<span class="meta-pill meta-pill-risk">${escapeHtml(item)}</span>`).join("")}
          </div>
        </div>
      </td>
      <td class="review-cell">
        <div class="cell-stack">
          <select class="table-select review-select" data-review-status>
            ${reviewStatusOptions(row.review_status)}
          </select>
          <label class="review-check">
            <input type="checkbox" data-review-export ${row.approved_for_export ? "checked" : ""} />
            <span>Approved for export</span>
          </label>
          <textarea class="table-textarea review-notes" data-review-notes placeholder="Reviewer notes">${escapeHtml(row.reviewer_notes || "")}</textarea>
        </div>
      </td>
    </tr>
  `;
}

function reviewStatusOptions(selectedValue) {
  const statuses = state.runtime?.review?.allowed_statuses || ["Pending", "Approved", "Rejected", "Needs Edit"];
  return statuses
    .map((status) => `<option value="${escapeHtml(status)}" ${status === selectedValue ? "selected" : ""}>${escapeHtml(status)}</option>`)
    .join("");
}

function formatDateRange(row) {
  if (row.end_date && row.end_date !== row.start_date) {
    return `${row.start_date} to ${row.end_date}`;
  }
  return row.start_date || "Date missing";
}

function formatTimeRange(row) {
  if (row.start_time && row.end_time) {
    return `${row.start_time} to ${row.end_time}`;
  }
  if (row.start_time) {
    return row.start_time;
  }
  return "Time missing";
}

function formatLocation(row) {
  return [row.address, row.city, row.state].filter(Boolean).join(", ") || "Address needs review";
}

function countReviews() {
  return state.reviewRows.reduce(
    (counts, row) => {
      const status = row.review_status || "Pending";
      if (status === "Approved") counts.approved += 1;
      else if (status === "Rejected") counts.rejected += 1;
      else if (status === "Needs Edit") counts.needsEdit += 1;
      else counts.pending += 1;
      return counts;
    },
    { pending: 0, approved: 0, rejected: 0, needsEdit: 0 }
  );
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
