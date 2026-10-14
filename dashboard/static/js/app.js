/**
 * Mini CDN Routing Simulator - Interactive Frontend (Review 1 Polished)
 * Features:
 * - Clean graph readability (edge weights on hover & active route only)
 * - Multi-hop path tracing & full node sequence display
 * - Live Dual-Algorithm Cross-Validation (Bellman-Ford vs Floyd-Warshall)
 * - Benchmark Analytics Modal with empirical plot and data table
 * - Fault adaptation Before-vs-After comparison diff
 */

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let rawNetworkData = null;
let selectedUserId = null;
let currentPathEdgeIds = [];
let lastRouteState = null; // For Before/After Fault Diff

// DOM References
const userSelect = document.getElementById("user-select");
const btnKillEdge = document.getElementById("btn-kill-edge");
const btnReset = document.getElementById("btn-reset");
const btnFit = document.getElementById("btn-fit");
const topoStats = document.getElementById("topo-stats");
const faultFeed = document.getElementById("fault-feed");

// Telemetry DOM
const singleView = document.getElementById("telemetry-single-view");
const compareView = document.getElementById("telemetry-compare-view");
const teleEdge = document.getElementById("tele-edge");
const teleLatency = document.getElementById("tele-latency");
const teleAlgo = document.getElementById("tele-algo");
const teleOps = document.getElementById("tele-ops");
const teleTime = document.getElementById("tele-time");
const teleHops = document.getElementById("tele-hops");
const telePath = document.getElementById("tele-path");

// Compare DOM
const cmpAgreementBadge = document.getElementById("compare-agreement-badge");
const cmpBfLat = document.getElementById("cmp-bf-lat");
const cmpBfOps = document.getElementById("cmp-bf-ops");
const cmpBfTime = document.getElementById("cmp-bf-time");
const cmpFwLat = document.getElementById("cmp-fw-lat");
const cmpFwOps = document.getElementById("cmp-fw-ops");
const cmpFwTime = document.getElementById("cmp-fw-time");

// Fault Diff DOM
const faultDiffCard = document.getElementById("fault-diff-card");
const faultDiffSummary = document.getElementById("fault-diff-summary");
const diffBeforePath = document.getElementById("diff-before-path");
const diffBeforeLat = document.getElementById("diff-before-lat");
const diffAfterPath = document.getElementById("diff-after-path");
const diffAfterLat = document.getElementById("diff-after-lat");
const diffDelta = document.getElementById("diff-delta");

// Modal DOM
const btnOpenBenchmark = document.getElementById("btn-open-benchmark");
const btnCloseModal = document.getElementById("btn-close-modal");
const benchmarkModal = document.getElementById("benchmark-modal");
const benchmarkTableBody = document.getElementById("benchmark-table-body");

// Log feed helper
function logFault(message, type = "info") {
  const entry = document.createElement("div");
  entry.className = `log-entry log-${type}`;
  const time = new Date().toLocaleTimeString().split(" ")[0];
  entry.textContent = `[${time}] ${message}`;
  faultFeed.insertBefore(entry, faultFeed.firstChild);
}

// Fetch and render network
async function loadNetwork(preserveSelection = false) {
  try {
    const res = await fetch("/api/network");
    const data = await res.json();
    rawNetworkData = data;

    topoStats.textContent = `${data.nodes.length} Nodes | ${data.edges.length} Links`;

    // Populate user dropdown (filter to primary user endpoints)
    const prevSelected = userSelect.value;
    userSelect.innerHTML = '<option value="">-- Choose User Region --</option>';
    data.nodes
      .filter((n) => n.node_type === "user_region" && n.tier !== "transit")
      .forEach((u) => {
        const opt = document.createElement("option");
        opt.value = u.id;
        opt.textContent = `${u.label} (${u.id})`;
        userSelect.appendChild(opt);
      });

    if (preserveSelection && prevSelected) {
      userSelect.value = prevSelected;
      selectedUserId = prevSelected;
    }

    renderVisNetwork(data);

    if (preserveSelection && selectedUserId) {
      triggerRouting(selectedUserId);
    }
  } catch (err) {
    console.error("Failed to load network:", err);
    logFault("Failed to load network topology", "kill");
  }
}

// Initialize Vis.js Network with optimized spacing
function renderVisNetwork(data) {
  const container = document.getElementById("network-canvas");

  nodesDataSet = new vis.DataSet(data.nodes);
  edgesDataSet = new vis.DataSet(data.edges);

  const networkData = {
    nodes: nodesDataSet,
    edges: edgesDataSet,
  };

  const options = {
    nodes: {
      borderWidth: 2,
      font: { color: "#ffffff", size: 12 },
    },
    edges: {
      width: 1.5,
      color: { color: "#334155", highlight: "#f97316" },
      hoverWidth: 3,
      selectionWidth: 3.5,
    },
    physics: {
      solver: "forceAtlas2Based",
      forceAtlas2Based: {
        gravitationalConstant: -130,
        centralGravity: 0.006,
        springLength: 170,
        springConstant: 0.08,
        damping: 0.85,
        avoidOverlap: 0.8,
      },
      stabilization: { iterations: 220, fit: true },
    },
    interaction: {
      hover: true,
      tooltipDelay: 80,
      zoomView: true,
      dragView: true,
    },
  };

  network = new vis.Network(container, networkData, options);

  // Click on node
  network.on("click", (params) => {
    if (params.nodes.length > 0) {
      const clickedId = params.nodes[0];
      const nodeObj = nodesDataSet.get(clickedId);
      if (nodeObj && nodeObj.node_type === "user_region" && nodeObj.tier !== "transit") {
        selectedUserId = clickedId;
        userSelect.value = clickedId;
        triggerRouting(clickedId);
      }
    }
  });
}

function getSelectedAlgorithm() {
  const checked = document.querySelector('input[name="algorithm"]:checked');
  return checked ? checked.value : "bellman_ford";
}

// Compute route and update UI
async function triggerRouting(userId) {
  if (!userId) return;

  const algo = getSelectedAlgorithm();

  try {
    const res = await fetch("/api/route", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ user_id: userId, algorithm: algo }),
    });

    const data = await res.json();
    if (!res.ok) {
      logFault(`Routing error: ${data.error}`, "kill");
      clearRouteHighlight();
      return;
    }

    displayTelemetry(data);
    highlightRoute(data.path);

    // Save active route state for before/after diffing
    lastRouteState = {
      userId: userId,
      path: data.path ? [...data.path] : [],
      latency: data.latency,
      best_edge: data.best_edge,
      hops: data.path ? data.path.length - 1 : 0,
    };
  } catch (err) {
    console.error("Routing request failed:", err);
  }
}

// Update telemetry dashboard
function displayTelemetry(data) {
  const isCompare = data.mode === "comparison";

  if (isCompare) {
    singleView.style.display = "none";
    compareView.style.display = "block";

    const bf = data.bellman_ford;
    const fw = data.floyd_warshall;
    const ag = data.agreement;

    cmpBfLat.textContent = bf.latency !== null ? `${bf.latency.toFixed(1)} ms` : "∞";
    cmpBfOps.textContent = `${bf.operations.toLocaleString()} ops`;
    cmpBfTime.textContent = `${bf.execution_time_ms} ms`;

    cmpFwLat.textContent = fw.latency !== null ? `${fw.latency.toFixed(1)} ms` : "∞";
    cmpFwOps.textContent = `${fw.operations.toLocaleString()} ops`;
    cmpFwTime.textContent = `${fw.execution_time_ms} ms`;

    if (ag.matched) {
      cmpAgreementBadge.className = "agreement-badge";
      cmpAgreementBadge.innerHTML = "✅ 100% Agreement: Both Algorithms Found Identical Shortest Distance";
    } else {
      cmpAgreementBadge.className = "agreement-badge agreement-mismatch";
      cmpAgreementBadge.innerHTML = `⚠️ Difference: &Delta; ${ag.latency_diff} ms`;
    }
  } else {
    singleView.style.display = "block";
    compareView.style.display = "none";

    if (!data.best_edge) {
      teleEdge.textContent = "UNREACHABLE";
      teleLatency.textContent = "∞";
      teleOps.textContent = data.operations.toLocaleString();
      teleTime.textContent = `${data.execution_time_ms} ms`;
      teleHops.textContent = "0";
    } else {
      const edgeNode = rawNetworkData.nodes.find((n) => n.id === data.best_edge);
      teleEdge.textContent = edgeNode ? edgeNode.label : data.best_edge;
      teleLatency.textContent = `${data.latency.toFixed(1)} ms`;
      teleAlgo.textContent = `${data.algorithm} (${data.complexity})`;
      teleOps.textContent = `${data.operations.toLocaleString()} ops`;
      teleTime.textContent = `${data.execution_time_ms} ms`;
      teleHops.textContent = `${data.path.length - 1} hops`;
    }
  }

  // Render Full Path Sequence
  if (!data.path || data.path.length === 0) {
    telePath.innerHTML = '<span class="text-danger">No route found! Link failure severed path.</span>';
    return;
  }

  telePath.innerHTML = data.path
    .map((nodeId, idx) => {
      const nodeObj = rawNetworkData.nodes.find((n) => n.id === nodeId);
      const isStart = idx === 0;
      const isEnd = idx === data.path.length - 1;

      let badgeClass = "badge-hop";
      if (isStart) badgeClass = "badge-user";
      else if (isEnd) badgeClass = "badge-edge";
      else if (nodeObj && nodeObj.tier === "transit") badgeClass = "badge-transit";

      const label = nodeObj ? nodeObj.label.split("·")[0].trim() : nodeId;
      return `<span class="path-node ${badgeClass}" title="${nodeId}">${label}</span>`;
    })
    .join(" <span class='path-arrow'>➔</span> ");
}

// Highlight shortest path and show edge weight labels only along the route
function highlightRoute(path) {
  clearRouteHighlight();

  if (!path || path.length < 2) return;

  const pathEdgeIds = [];

  for (let i = 0; i < path.length - 1; i++) {
    const u = path[i];
    const v = path[i + 1];

    const edge = edgesDataSet.get({
      filter: (e) => (e.from === u && e.to === v) || (e.from === v && e.to === u),
    })[0];

    if (edge) {
      pathEdgeIds.push(edge.id);
      // Prominently display latency label on active path edges only!
      edgesDataSet.update({
        id: edge.id,
        label: `${edge.latency}ms`,
        color: { color: "#f97316", highlight: "#ea580c" },
        width: 4.2,
      });
    }
  }

  currentPathEdgeIds = pathEdgeIds;

  // Node glowing shadow
  path.forEach((nodeId, index) => {
    let haloColor = "#f97316";
    if (index === 0) haloColor = "#10b981"; // user
    if (index === path.length - 1) haloColor = "#00b4d8"; // best edge

    nodesDataSet.update({
      id: nodeId,
      shadow: { enabled: true, color: haloColor, size: 14 },
    });
  });
}

// Clear route highlighting and reset edge labels to blank
function clearRouteHighlight() {
  if (!edgesDataSet || !nodesDataSet) return;

  currentPathEdgeIds.forEach((edgeId) => {
    const origEdge = rawNetworkData.edges.find((e) => e.id === edgeId);
    if (origEdge) {
      edgesDataSet.update({
        id: edgeId,
        label: "", // Remove label on inactive edges
        color: origEdge.color,
        width: 1.5,
      });
    }
  });
  currentPathEdgeIds = [];

  rawNetworkData.nodes.forEach((n) => {
    nodesDataSet.update({
      id: n.id,
      shadow: { enabled: false },
    });
  });
}

// Event Listeners
userSelect.addEventListener("change", (e) => {
  selectedUserId = e.target.value;
  if (selectedUserId) {
    triggerRouting(selectedUserId);
  } else {
    clearRouteHighlight();
    lastRouteState = null;
    faultDiffCard.style.display = "none";
    teleEdge.textContent = "--";
    teleLatency.textContent = "--";
    teleAlgo.textContent = "--";
    teleOps.textContent = "--";
    teleTime.textContent = "--";
    teleHops.textContent = "--";
    telePath.innerHTML = '<span class="text-muted">Select a user region above</span>';
  }
});

document.querySelectorAll('input[name="algorithm"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    if (selectedUserId) {
      triggerRouting(selectedUserId);
    }
  });
});

// Kill Random Edge (Failure Injection with Before/After Diff)
btnKillEdge.addEventListener("click", async () => {
  const previousState = lastRouteState ? { ...lastRouteState } : null;

  try {
    const res = await fetch("/api/network/kill-edge", { method: "POST" });
    const data = await res.json();

    if (!res.ok) {
      logFault(`Failure injection failed: ${data.error}`, "kill");
      return;
    }

    const k = data.killed_edge;
    logFault(`💥 LINK FAILURE: Severed ${k.u} ↔ ${k.v} (${k.latency}ms)`, "kill");

    await loadNetwork(true);

    // If user had an active route, compute and display the before/after adaptation diff
    if (previousState && selectedUserId) {
      setTimeout(() => {
        if (lastRouteState) {
          faultDiffCard.style.display = "block";
          faultDiffSummary.textContent = `Link ${k.u} ↔ ${k.v} (${k.latency}ms) Severed`;

          diffBeforePath.textContent = previousState.path.join(" ➔ ");
          diffBeforeLat.textContent = previousState.latency ? `${previousState.latency.toFixed(1)} ms` : "∞";

          const newPath = lastRouteState.path.length > 0 ? lastRouteState.path.join(" ➔ ") : "NO ROUTE (Unreachable)";
          diffAfterPath.textContent = newPath;
          diffAfterLat.textContent = lastRouteState.latency ? `${lastRouteState.latency.toFixed(1)} ms` : "∞";

          if (previousState.latency && lastRouteState.latency) {
            const delta = lastRouteState.latency - previousState.latency;
            if (delta > 0) {
              diffDelta.textContent = `+${delta.toFixed(1)} ms detour latency adaptation (${lastRouteState.hops} hops)`;
            } else if (delta === 0) {
              diffDelta.textContent = `Identical latency route selected via alternate path (${lastRouteState.hops} hops)`;
            } else {
              diffDelta.textContent = `${delta.toFixed(1)} ms latency via new path`;
            }
          } else {
            diffDelta.textContent = "Route severed - node isolated";
          }
        }
      }, 100);
    }
  } catch (err) {
    console.error("Kill edge error:", err);
  }
});

// Reset Network
btnReset.addEventListener("click", async () => {
  try {
    const res = await fetch("/api/network/reset", { method: "POST" });
    const data = await res.json();
    logFault("🔄 Network restored to baseline topology", "info");
    faultDiffCard.style.display = "none";
    await loadNetwork(true);
  } catch (err) {
    console.error("Reset error:", err);
  }
});

// Fit View
btnFit.addEventListener("click", () => {
  if (network) {
    network.fit({ animation: { duration: 600, easingFunction: "easeInOutQuad" } });
  }
});

// Benchmark Analytics Modal
btnOpenBenchmark.addEventListener("click", async () => {
  benchmarkModal.style.display = "flex";
  try {
    const res = await fetch("/api/benchmark-data");
    const data = await res.json();
    if (data.benchmarks) {
      benchmarkTableBody.innerHTML = data.benchmarks
        .map(
          (b) => `
          <tr>
            <td><strong>${b.N}</strong></td>
            <td>${b.Edges}</td>
            <td>${b.BF_Time_ms.toFixed(2)} ms</td>
            <td>${b.BF_Operations.toLocaleString()}</td>
            <td>${b.FW_Time_ms.toFixed(2)} ms</td>
            <td>${b.FW_Operations.toLocaleString()}</td>
          </tr>`
        )
        .join("");
    }
  } catch (err) {
    console.error("Failed to load benchmark table:", err);
  }
});

btnCloseModal.addEventListener("click", () => {
  benchmarkModal.style.display = "none";
});

benchmarkModal.addEventListener("click", (e) => {
  if (e.target === benchmarkModal) {
    benchmarkModal.style.display = "none";
  }
});

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  loadNetwork();
});
