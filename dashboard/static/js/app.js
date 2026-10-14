/**
 * Mini CDN Routing & Flow Simulator - Interactive Frontend
 * Features:
 * - Clean graph readability (edge weights on hover & active route only)
 * - Multi-hop path tracing & full node sequence display
 * - Live Dual-Algorithm Cross-Validation (Bellman-Ford vs Floyd-Warshall)
 * - Benchmark Analytics Modal with empirical plot and data table
 * - Fault adaptation Before-vs-After comparison diff
 * - Max Flow & Min-Cut calculation (Edmonds-Karp vs Ford-Fulkerson)
 * - Visual flow utilization on edges and bottleneck min-cut highlighting in RED
 */

let network = null;
let nodesDataSet = null;
let edgesDataSet = null;
let rawNetworkData = null;
let selectedUserId = null;
let currentPathEdgeIds = [];
let currentFlowEdgeIds = [];
let lastRouteState = null; // For Before/After Fault Diff
let currentMode = "routing"; // "routing" | "flow"

// DOM References
const activeTopoName = document.getElementById("active-topo-name");
const tabRouting = document.getElementById("tab-routing");
const tabFlow = document.getElementById("tab-flow");
const routingPanelGroup = document.getElementById("routing-panel-group");
const flowPanelGroup = document.getElementById("flow-panel-group");

const userSelect = document.getElementById("user-select");
const btnKillEdge = document.getElementById("btn-kill-edge");
const btnReset = document.getElementById("btn-reset");
const btnFit = document.getElementById("btn-fit");
const topoStats = document.getElementById("topo-stats");
const faultFeed = document.getElementById("fault-feed");

// Routing Telemetry DOM
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

// Max Flow DOM
const flowSourceSelect = document.getElementById("flow-source-select");
const flowSinksSelect = document.getElementById("flow-sinks-select");
const btnRunFlow = document.getElementById("btn-run-flow");
const flowSingleView = document.getElementById("flow-single-view");
const flowCompareView = document.getElementById("flow-compare-view");
const flowVal = document.getElementById("flow-val");
const flowMincutCap = document.getElementById("flow-mincut-cap");
const flowAug = document.getElementById("flow-aug");
const flowOps = document.getElementById("flow-ops");
const flowTime = document.getElementById("flow-time");
const flowCutCount = document.getElementById("flow-cut-count");
const flowCutEdges = document.getElementById("flow-cut-edges");
const flowAgreementBadge = document.getElementById("flow-agreement-badge");

const cmpEkFlow = document.getElementById("cmp-ek-flow");
const cmpEkAug = document.getElementById("cmp-ek-aug");
const cmpEkOps = document.getElementById("cmp-ek-ops");
const cmpEkTime = document.getElementById("cmp-ek-time");
const cmpFfFlow = document.getElementById("cmp-ff-flow");
const cmpFfAug = document.getElementById("cmp-ff-aug");
const cmpFfOps = document.getElementById("cmp-ff-ops");
const cmpFfTime = document.getElementById("cmp-ff-time");

// Modal DOM
const btnOpenBenchmark = document.getElementById("btn-open-benchmark");
const btnCloseModal = document.getElementById("btn-close-modal");
const benchmarkModal = document.getElementById("benchmark-modal");
const benchmarkTableBody = document.getElementById("benchmark-table-body");

// Mode Tab Switching
tabRouting.addEventListener("click", () => {
  currentMode = "routing";
  tabRouting.classList.add("active-tab");
  tabFlow.classList.remove("active-tab");
  routingPanelGroup.style.display = "block";
  flowPanelGroup.style.display = "none";
  clearVisualHighlights();
  if (selectedUserId) {
    triggerRouting(selectedUserId);
  }
});

tabFlow.addEventListener("click", () => {
  currentMode = "flow";
  tabFlow.classList.add("active-tab");
  tabRouting.classList.remove("active-tab");
  routingPanelGroup.style.display = "none";
  flowPanelGroup.style.display = "block";
  clearVisualHighlights();
});

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

    if (activeTopoName) {
      activeTopoName.textContent = `Topology: ${data.topology_name || "Active Network"}`;
    }
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

    // Populate flow source dropdown (origins or all nodes)
    flowSourceSelect.innerHTML = "";
    const origins = data.nodes.filter((n) => n.node_type === "origin");
    const sourceCandidates = origins.length > 0 ? origins : data.nodes;
    sourceCandidates.forEach((o) => {
      const opt = document.createElement("option");
      opt.value = o.id;
      opt.textContent = `${o.label} (${o.id})`;
      flowSourceSelect.appendChild(opt);
    });

    if (preserveSelection && prevSelected) {
      userSelect.value = prevSelected;
      selectedUserId = prevSelected;
    }

    renderVisNetwork(data);

    if (preserveSelection && selectedUserId && currentMode === "routing") {
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
        if (currentMode === "routing") {
          triggerRouting(clickedId);
        }
      }
    }
  });
}

function getSelectedAlgorithm() {
  const checked = document.querySelector('input[name="algorithm"]:checked');
  return checked ? checked.value : "bellman_ford";
}

function getSelectedFlowAlgorithm() {
  const checked = document.querySelector('input[name="flow_algorithm"]:checked');
  return checked ? checked.value : "edmonds_karp";
}

// Compute shortest-path route
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
      clearVisualHighlights();
      return;
    }

    displayTelemetry(data);
    highlightRoute(data.path);

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

// Update routing telemetry dashboard
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
      teleOps.textContent = (data.operations || 0).toLocaleString();
      teleTime.textContent = `${data.compute_time_ms || data.execution_time_ms} ms`;
      teleHops.textContent = "0";
    } else {
      const edgeNode = rawNetworkData.nodes.find((n) => n.id === data.best_edge);
      teleEdge.textContent = edgeNode ? edgeNode.label : data.best_edge;
      teleLatency.textContent = `${data.latency.toFixed(1)} ms`;
      teleAlgo.textContent = `${data.algorithm} (${data.complexity})`;
      teleOps.textContent = `${(data.operations || 0).toLocaleString()} ops`;
      teleTime.textContent = `${data.compute_time_ms || data.execution_time_ms} ms`;
      teleHops.textContent = `${data.hops !== undefined ? data.hops : (data.path ? data.path.length - 1 : 0)} hops`;
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
      else if (nodeObj && (nodeObj.tier === "transit" || nodeObj.node_type === "transit")) badgeClass = "badge-transit";

      const label = nodeObj ? nodeObj.label.split("·")[0].trim() : nodeId;
      return `<span class="path-node ${badgeClass}" title="${nodeId}">${label}</span>`;
    })
    .join(" <span class='path-arrow'>➔</span> ");
}

// Compute Maximum Flow
btnRunFlow.addEventListener("click", async () => {
  const source = flowSourceSelect.value;
  const sinksMode = flowSinksSelect.value;
  const algo = getSelectedFlowAlgorithm();

  let sinks = [];
  if (sinksMode === "all_edges") {
    sinks = rawNetworkData.nodes.filter((n) => n.node_type === "edge_server").map((n) => n.id);
  } else {
    sinks = rawNetworkData.nodes.filter((n) => n.node_type === "user_region" && n.tier !== "transit").map((n) => n.id);
  }

  try {
    const res = await fetch("/api/max-flow", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ source: source, sinks: sinks, algorithm: algo }),
    });

    const data = await res.json();
    if (!res.ok) {
      logFault(`Max flow computation error: ${data.error}`, "kill");
      return;
    }

    displayFlowTelemetry(data);
    highlightFlowAndMinCut(data.edge_flows, data.min_cut_edges);
  } catch (err) {
    console.error("Max flow request failed:", err);
  }
});

// Display Max Flow Telemetry
function displayFlowTelemetry(data) {
  const isCompare = data.mode === "comparison";

  if (isCompare) {
    flowSingleView.style.display = "none";
    flowCompareView.style.display = "block";

    const ek = data.edmonds_karp;
    const ff = data.ford_fulkerson;
    const ag = data.agreement;

    cmpEkFlow.textContent = `${ek.max_flow.toFixed(1)} Mbps`;
    cmpEkAug.textContent = `${ek.augmenting_paths} paths`;
    cmpEkOps.textContent = `${ek.operations.toLocaleString()} ops`;
    cmpEkTime.textContent = `${ek.compute_time_ms.toFixed(2)} ms`;

    cmpFfFlow.textContent = `${ff.max_flow.toFixed(1)} Mbps`;
    cmpFfAug.textContent = `${ff.augmenting_paths} paths`;
    cmpFfOps.textContent = `${ff.operations.toLocaleString()} ops`;
    cmpFfTime.textContent = `${ff.compute_time_ms.toFixed(2)} ms`;

    if (ag.matched) {
      flowAgreementBadge.className = "agreement-badge";
      flowAgreementBadge.innerHTML = "✅ 100% Agreement: Both EK and FF Computed Identical Max Flow Value";
    } else {
      flowAgreementBadge.className = "agreement-badge agreement-mismatch";
      flowAgreementBadge.innerHTML = `⚠️ Difference: &Delta; ${ag.flow_diff} Mbps`;
    }
  } else {
    flowSingleView.style.display = "block";
    flowCompareView.style.display = "none";

    flowVal.textContent = `${data.max_flow.toFixed(1)} Mbps`;
    flowMincutCap.textContent = `${data.min_cut_capacity.toFixed(1)} Mbps`;
    flowAug.textContent = `${data.augmenting_paths} paths`;
    flowOps.textContent = `${data.operations.toLocaleString()} ops`;
    flowTime.textContent = `${data.compute_time_ms.toFixed(2)} ms`;
    flowCutCount.textContent = `${data.min_cut_edges.length} edges`;
  }

  // Display Min-Cut Edges List
  if (!data.min_cut_edges || data.min_cut_edges.length === 0) {
    flowCutEdges.innerHTML = '<span class="text-muted">No bottleneck cut edges (flow is 0).</span>';
  } else {
    flowCutEdges.innerHTML = data.min_cut_edges
      .map((e) => `<span class="path-node badge-mincut">${e.u} ➔ ${e.v}</span>`)
      .join(" ");
  }
}

// Highlight Flow Utilization and Min-Cut (in RED)
function highlightFlowAndMinCut(edgeFlows, minCutEdges) {
  clearVisualHighlights();

  const minCutSet = new Set(minCutEdges.map((e) => `${e.u}->${e.v}`));
  const updatedEdges = [];

  rawNetworkData.edges.forEach((origEdge) => {
    const forwardKey = `${origEdge.from}->${origEdge.to}`;
    const reverseKey = `${origEdge.to}->${origEdge.from}`;

    const isMinCut = minCutSet.has(forwardKey) || minCutSet.has(reverseKey);
    const flowForward = edgeFlows ? edgeFlows[forwardKey] || 0.0 : 0.0;
    const flowReverse = edgeFlows ? edgeFlows[reverseKey] || 0.0 : 0.0;
    const totalFlow = Math.max(flowForward, flowReverse);

    if (isMinCut) {
      // Bottleneck Min-Cut Edge: Red Highlight
      currentFlowEdgeIds.push(origEdge.id);
      updatedEdges.push({
        id: origEdge.id,
        label: `[CUT] ${totalFlow.toFixed(0)}/${origEdge.bandwidth}M`,
        color: { color: "#ef4444", highlight: "#dc2626" },
        width: 4.5,
        dashes: [6, 4],
      });
    } else if (totalFlow > 0) {
      // Flow Carrying Link
      currentFlowEdgeIds.push(origEdge.id);
      const ratio = Math.min(1.0, totalFlow / origEdge.bandwidth);
      updatedEdges.push({
        id: origEdge.id,
        label: `${totalFlow.toFixed(0)}/${origEdge.bandwidth}M`,
        color: { color: "#00b4d8", highlight: "#38bdf8" },
        width: 2.2 + ratio * 3.0,
      });
    }
  });

  if (updatedEdges.length > 0) {
    edgesDataSet.update(updatedEdges);
  }
}

// Highlight shortest path and show edge weight labels only along the route
function highlightRoute(path) {
  clearVisualHighlights();

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

// Clear visual highlights (route and flow)
function clearVisualHighlights() {
  if (!edgesDataSet || !nodesDataSet || !rawNetworkData) return;

  const resetEdgeIds = new Set([...currentPathEdgeIds, ...currentFlowEdgeIds]);

  resetEdgeIds.forEach((edgeId) => {
    const origEdge = rawNetworkData.edges.find((e) => e.id === edgeId);
    if (origEdge) {
      edgesDataSet.update({
        id: edgeId,
        label: "",
        color: origEdge.color,
        width: 1.5,
        dashes: false,
      });
    }
  });
  currentPathEdgeIds = [];
  currentFlowEdgeIds = [];

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
    clearVisualHighlights();
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
    if (selectedUserId && currentMode === "routing") {
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

    const btnGenPm = document.getElementById("btn-generate-postmortem");
    if (btnGenPm) btnGenPm.style.display = "block";

    await loadNetwork(true);

    if (previousState && selectedUserId && currentMode === "routing") {
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
    const btnGenPm = document.getElementById("btn-generate-postmortem");
    if (btnGenPm) btnGenPm.style.display = "none";
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

// Topology Upload & Sample Modal
const btnOpenUpload = document.getElementById("btn-open-upload");
const btnCloseUploadModal = document.getElementById("btn-close-upload-modal");
const uploadModal = document.getElementById("upload-modal");
const btnLoadCampus = document.getElementById("btn-load-campus");
const btnLoadCloud = document.getElementById("btn-load-cloud");
const btnLoadCdn = document.getElementById("btn-load-cdn");
const uploadJsonFile = document.getElementById("upload-json-file");
const uploadNodesFile = document.getElementById("upload-nodes-file");
const uploadEdgesFile = document.getElementById("upload-edges-file");
const btnSubmitUpload = document.getElementById("btn-submit-upload");
const uploadStatusBox = document.getElementById("upload-status-box");

if (btnOpenUpload) {
  btnOpenUpload.addEventListener("click", () => {
    uploadModal.style.display = "flex";
    uploadStatusBox.style.display = "none";
  });
}

if (btnCloseUploadModal) {
  btnCloseUploadModal.addEventListener("click", () => {
    uploadModal.style.display = "none";
  });
}

if (uploadModal) {
  uploadModal.addEventListener("click", (e) => {
    if (e.target === uploadModal) {
      uploadModal.style.display = "none";
    }
  });
}

async function loadSampleTopology(sampleId) {
  try {
    const res = await fetch("/api/topology/load-sample", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sample_id: sampleId }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(`Error loading sample: ${data.error}`);
      return;
    }
    uploadModal.style.display = "none";
    logFault(`Loaded topology: ${data.topology_name}`, "info");
    await loadNetwork(false);
  } catch (err) {
    console.error("Failed to load sample:", err);
  }
}

if (btnLoadCampus) {
  btnLoadCampus.addEventListener("click", () => loadSampleTopology("campus_network.json"));
}
if (btnLoadCloud) {
  btnLoadCloud.addEventListener("click", () => loadSampleTopology("multi_region_cloud.json"));
}
if (btnLoadCdn) {
  btnLoadCdn.addEventListener("click", async () => {
    await fetch("/api/network/reset", { method: "POST" });
    uploadModal.style.display = "none";
    logFault("Reset to default 20-node CDN topology", "info");
    await loadNetwork(false);
  });
}

if (btnSubmitUpload) {
  btnSubmitUpload.addEventListener("click", async () => {
    uploadStatusBox.style.display = "block";
    uploadStatusBox.innerHTML = '<span class="text-muted">Uploading and validating topology...</span>';

    const formData = new FormData();

    if (uploadJsonFile && uploadJsonFile.files.length > 0) {
      formData.append("file", uploadJsonFile.files[0]);
    } else if (
      uploadNodesFile &&
      uploadNodesFile.files.length > 0 &&
      uploadEdgesFile &&
      uploadEdgesFile.files.length > 0
    ) {
      formData.append("nodes_file", uploadNodesFile.files[0]);
      formData.append("edges_file", uploadEdgesFile.files[0]);
      formData.append("name", "Custom CSV Network");
    } else {
      uploadStatusBox.innerHTML =
        '<span style="color: #f87171;">Please select either a JSON file OR both nodes.csv and edges.csv files.</span>';
      return;
    }

    try {
      const res = await fetch("/api/topology/upload", {
        method: "POST",
        body: formData,
      });

      const data = await res.json();

      if (!res.ok) {
        let errHtml = `<strong style="color: #f87171;">Validation Failed:</strong><ul style="color: #fca5a5; padding-left: 18px; margin-top: 4px; font-size: 0.78rem;">`;
        if (data.errors && data.errors.length > 0) {
          data.errors.forEach((e) => {
            errHtml += `<li>${e}</li>`;
          });
        } else {
          errHtml += `<li>${data.error || "Unknown validation error"}</li>`;
        }
        errHtml += "</ul>";
        uploadStatusBox.innerHTML = errHtml;
        return;
      }

      uploadStatusBox.innerHTML = `<span style="color: #34d399;">Success! Loaded "${data.topology_name}" with ${data.node_count} nodes and ${data.edge_count} edges.</span>`;
      setTimeout(async () => {
        uploadModal.style.display = "none";
        logFault(`Applied custom topology: ${data.topology_name}`, "info");
        await loadNetwork(false);
      }, 700);
    } catch (err) {
      uploadStatusBox.innerHTML = `<span style="color: #f87171;">Upload request failed: ${err.message}</span>`;
    }
  });
}

// ==========================================
// NetPilot Copilot Chat Drawer
// ==========================================
const btnOpenChat = document.getElementById("btn-open-chat");
const btnCloseChat = document.getElementById("btn-close-chat");
const copilotDrawer = document.getElementById("copilot-drawer");
const chatMessages = document.getElementById("chat-messages");
const chatInput = document.getElementById("chat-input");
const btnSendChat = document.getElementById("btn-send-chat");
const chipButtons = document.querySelectorAll(".chip-btn");

let chatHistory = [];

if (btnOpenChat && copilotDrawer) {
  btnOpenChat.addEventListener("click", () => {
    copilotDrawer.style.display = copilotDrawer.style.display === "none" ? "flex" : "none";
    if (copilotDrawer.style.display === "flex" && chatInput) {
      chatInput.focus();
    }
  });
}

if (btnCloseChat && copilotDrawer) {
  btnCloseChat.addEventListener("click", () => {
    copilotDrawer.style.display = "none";
  });
}

function escapeHtml(str) {
  if (!str) return "";
  return String(str)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function formatMarkdown(text) {
  if (!text) return "";
  let s = escapeHtml(text);
  s = s.replace(/\*\*(.*?)\*\*/g, "<strong>$1</strong>");
  s = s.replace(/`([^`]+)`/g, "<code style='background: rgba(255,255,255,0.1); padding: 2px 4px; border-radius: 4px;'>$1</code>");
  s = s.replace(/\n/g, "<br>");
  return s;
}

async function sendChatMessage(confirmedAction = null) {
  const text = chatInput ? chatInput.value.trim() : "";
  if (!text && !confirmedAction) return;

  if (chatInput && !confirmedAction) {
    chatInput.value = "";
  }

  // Render user message if not confirmation
  if (!confirmedAction && chatMessages) {
    const userMsgEl = document.createElement("div");
    userMsgEl.className = "chat-msg chat-user";
    userMsgEl.innerHTML = `<div class="msg-bubble">${escapeHtml(text)}</div>`;
    chatMessages.appendChild(userMsgEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  // Render loading indicator
  const loadingEl = document.createElement("div");
  loadingEl.className = "chat-msg chat-assistant";
  loadingEl.innerHTML = `<div class="msg-bubble" style="opacity: 0.7;">⚡ NetPilot is running network tools and verifying facts...</div>`;
  if (chatMessages) {
    chatMessages.appendChild(loadingEl);
    chatMessages.scrollTop = chatMessages.scrollHeight;
  }

  try {
    const payload = confirmedAction
      ? { confirm_action: confirmedAction, history: chatHistory }
      : { message: text, history: chatHistory };

    const res = await fetch("/api/copilot/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const data = await res.json();
    loadingEl.remove();

    if (!res.ok) {
      const errEl = document.createElement("div");
      errEl.className = "chat-msg chat-assistant";
      errEl.innerHTML = `<div class="msg-bubble" style="color: #f87171;">⚠️ ${escapeHtml(data.error || "Copilot request failed.")}</div>`;
      chatMessages.appendChild(errEl);
      return;
    }

    const assistantMsgEl = document.createElement("div");
    assistantMsgEl.className = "chat-msg chat-assistant";

    let toolsHtml = "";
    if (data.tools_used && data.tools_used.length > 0) {
      toolsHtml = `
        <details class="tools-accordion">
          <summary>🛠️ Tools Used (${data.tools_used.length})</summary>
          <div class="tools-body"><pre>${escapeHtml(JSON.stringify(data.tools_used, null, 2))}</pre></div>
        </details>
      `;
    }

    let confirmationHtml = "";
    if (data.requires_confirmation && data.confirmation_action) {
      const actJson = escapeHtml(JSON.stringify(data.confirmation_action));
      confirmationHtml = `
        <div style="margin-top: 10px; display: flex; gap: 8px;">
          <button class="btn btn-primary btn-confirm-action" data-action='${actJson}' style="background: #ef4444; font-size: 0.75rem; padding: 4px 10px;">
            ⚠️ Confirm & Execute
          </button>
          <button class="btn btn-secondary btn-cancel-action" style="font-size: 0.75rem; padding: 4px 10px;">
            Cancel
          </button>
        </div>
      `;
    }

    const groundBadge = data.grounding_verified
      ? '<span style="color: #34d399;">✅ Grounded</span>'
      : '<span style="color: #fbbf24;">⚠️ Ungrounded</span>';

    assistantMsgEl.innerHTML = `
      <div class="msg-bubble">
        ${formatMarkdown(data.answer)}
        ${confirmationHtml}
        ${toolsHtml}
        <div class="msg-footer">
          <span>${data.latency_ms} ms</span>
          <span>${data.tokens} tokens</span>
          <span>${groundBadge}</span>
        </div>
      </div>
    `;

    chatMessages.appendChild(assistantMsgEl);

    // Wire confirmation buttons if present
    const confirmBtn = assistantMsgEl.querySelector(".btn-confirm-action");
    if (confirmBtn) {
      confirmBtn.addEventListener("click", async () => {
        const actData = JSON.parse(confirmBtn.getAttribute("data-action"));
        actData.confirmed = true;
        confirmBtn.disabled = true;
        await sendChatMessage(actData);
        await loadNetwork(false);
      });
    }
    const cancelBtn = assistantMsgEl.querySelector(".btn-cancel-action");
    if (cancelBtn) {
      cancelBtn.addEventListener("click", () => {
        const cBtn = assistantMsgEl.querySelector(".btn-confirm-action");
        if (cBtn) cBtn.remove();
        cancelBtn.remove();
        const cancelNote = document.createElement("div");
        cancelNote.style.color = "#94a3b8";
        cancelNote.style.fontSize = "0.75rem";
        cancelNote.style.marginTop = "6px";
        cancelNote.textContent = "Operation cancelled.";
        assistantMsgEl.querySelector(".msg-bubble").appendChild(cancelNote);
      });
    }

    chatMessages.scrollTop = chatMessages.scrollHeight;

    // Update history
    if (!confirmedAction) {
      chatHistory.push({ role: "user", content: text });
    }
    chatHistory.push({ role: "assistant", content: data.answer });
    if (chatHistory.length > 10) {
      chatHistory = chatHistory.slice(-10);
    }
  } catch (err) {
    if (loadingEl.parentNode) loadingEl.remove();
    console.error("Copilot chat error:", err);
  }
}

if (chipButtons) {
  chipButtons.forEach((chip) => {
    chip.addEventListener("click", () => {
      const prompt = chip.getAttribute("data-prompt");
      if (prompt && chatInput) {
        chatInput.value = prompt;
        sendChatMessage();
      }
    });
  });
}

if (btnSendChat) {
  btnSendChat.addEventListener("click", () => sendChatMessage());
}

if (chatInput) {
  chatInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      sendChatMessage();
    }
  });
}

// ==========================================
// Incident Postmortem Modal & Download
// ==========================================
const btnGenPostmortem = document.getElementById("btn-generate-postmortem");
const postmortemModal = document.getElementById("postmortem-modal");
const btnClosePostmortem = document.getElementById("btn-close-postmortem");
const btnClosePostmortemFooter = document.getElementById("btn-close-postmortem-footer");
const btnDownloadPostmortem = document.getElementById("btn-download-postmortem");
const postmortemContent = document.getElementById("postmortem-content");
const postmortemModalTitle = document.getElementById("postmortem-modal-title");

let currentPostmortemMarkdown = "";
let currentPostmortemId = "incident";

if (btnGenPostmortem) {
  btnGenPostmortem.addEventListener("click", async () => {
    if (postmortemModal) postmortemModal.style.display = "flex";
    if (postmortemContent) postmortemContent.textContent = "Synthesizing postmortem report from event telemetry...";

    try {
      const res = await fetch("/api/postmortem/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({}),
      });
      const data = await res.json();
      if (!res.ok) {
        if (postmortemContent) postmortemContent.textContent = `Error generating postmortem: ${data.error}`;
        return;
      }

      currentPostmortemMarkdown = data.markdown;
      currentPostmortemId = data.event_id || "incident";
      if (postmortemModalTitle) {
        postmortemModalTitle.textContent = `Incident Postmortem (${currentPostmortemId})`;
      }
      if (postmortemContent) {
        postmortemContent.textContent = data.markdown;
      }
    } catch (err) {
      if (postmortemContent) postmortemContent.textContent = `Request failed: ${err.message}`;
    }
  });
}

function closePostmortemModal() {
  if (postmortemModal) postmortemModal.style.display = "none";
}

if (btnClosePostmortem) btnClosePostmortem.addEventListener("click", closePostmortemModal);
if (btnClosePostmortemFooter) btnClosePostmortemFooter.addEventListener("click", closePostmortemModal);

if (postmortemModal) {
  postmortemModal.addEventListener("click", (e) => {
    if (e.target === postmortemModal) closePostmortemModal();
  });
}

if (btnDownloadPostmortem) {
  btnDownloadPostmortem.addEventListener("click", () => {
    if (!currentPostmortemMarkdown) return;
    const blob = new Blob([currentPostmortemMarkdown], { type: "text/markdown;charset=utf-8;" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `postmortem_${currentPostmortemId}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });
}

// ==========================================
// Propose, Simulate, Verify Mitigations Modal
// ==========================================
const btnOpenMitigations = document.getElementById("btn-open-mitigations");
const mitigationsModal = document.getElementById("mitigations-modal");
const btnCloseMitigations = document.getElementById("btn-close-mitigations");
const btnRunProposals = document.getElementById("btn-run-proposals");
const mitigationGoalSelect = document.getElementById("mitigation-goal-select");
const mitigationsTableContainer = document.getElementById("mitigations-table-container");

if (btnOpenMitigations && mitigationsModal) {
  btnOpenMitigations.addEventListener("click", () => {
    mitigationsModal.style.display = "flex";
  });
}

function closeMitigationsModal() {
  if (mitigationsModal) mitigationsModal.style.display = "none";
}

if (btnCloseMitigations) btnCloseMitigations.addEventListener("click", closeMitigationsModal);
if (mitigationsModal) {
  mitigationsModal.addEventListener("click", (e) => {
    if (e.target === mitigationsModal) closeMitigationsModal();
  });
}

if (btnRunProposals) {
  btnRunProposals.addEventListener("click", async () => {
    const goal = mitigationGoalSelect ? mitigationGoalSelect.value : "maximize throughput";
    if (mitigationsTableContainer) {
      mitigationsTableContainer.innerHTML = '<div style="color: var(--text-muted); font-size: 0.8rem; text-align: center; padding: 20px;">⚡ Simulating candidates on isolated graph copies...</div>';
    }

    try {
      const res = await fetch("/api/mitigations/propose", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ goal: goal }),
      });
      const data = await res.json();
      if (!res.ok) {
        if (mitigationsTableContainer) {
          mitigationsTableContainer.innerHTML = `<div style="color: #f87171; padding: 10px;">Error: ${escapeHtml(data.error)}</div>`;
        }
        return;
      }

      const cands = data.ranked_candidates || [];
      if (cands.length === 0) {
        if (mitigationsTableContainer) {
          mitigationsTableContainer.innerHTML = '<div style="color: #cbd5e1; padding: 10px;">No valid candidates generated.</div>';
        }
        return;
      }

      let tableHtml = `
        <table class="benchmark-table" style="width: 100%; font-size: 0.78rem;">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Action</th>
              <th>Target</th>
              <th>Value</th>
              <th>Rationale</th>
              <th>Measured Impact</th>
              <th>Apply</th>
            </tr>
          </thead>
          <tbody>
      `;

      cands.forEach((c) => {
        const impact = c.measured_impact;
        const impactText = `ΔFlow: +${impact.delta_max_flow_mbps} Mbps | ΔLat: ${impact.delta_avg_latency_ms} ms | ΔCut: +${impact.delta_bottleneck_capacity_mbps} Mbps`;
        const cJson = escapeHtml(JSON.stringify(c));

        tableHtml += `
          <tr>
            <td><strong style="color: #34d399;">#${c.rank}</strong></td>
            <td><code>${escapeHtml(c.action)}</code></td>
            <td><strong>${escapeHtml(c.target)}</strong></td>
            <td>${c.proposed_value}</td>
            <td style="color: #cbd5e1; font-size: 0.72rem;">${escapeHtml(c.rationale)}</td>
            <td style="color: #93c5fd; font-family: monospace; font-size: 0.72rem;">${escapeHtml(impactText)}</td>
            <td>
              <button class="btn btn-primary btn-apply-cand" data-cand='${cJson}' style="background: #10b981; font-size: 0.72rem; padding: 3px 8px;">
                Apply
              </button>
            </td>
          </tr>
        `;
      });

      tableHtml += `</tbody></table>`;
      if (mitigationsTableContainer) {
        mitigationsTableContainer.innerHTML = tableHtml;

        // Wire apply buttons
        const applyBtns = mitigationsTableContainer.querySelectorAll(".btn-apply-cand");
        applyBtns.forEach((btn) => {
          btn.addEventListener("click", async () => {
            const candData = JSON.parse(btn.getAttribute("data-cand"));
            const confirmed = confirm(
              `⚠️ DESTRUCTIVE ACTION CONFIRMATION:\n\nApply ${candData.action} on ${candData.target} with value ${candData.proposed_value}?\n\nThis will modify the live network topology.`
            );
            if (!confirmed) return;

            btn.disabled = true;
            btn.textContent = "Applying...";
            try {
              const appRes = await fetch("/api/mitigations/apply", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ candidate: candData, confirmed: true }),
              });
              const appData = await appRes.json();
              if (!appRes.ok) {
                alert(`Error: ${appData.error}`);
                btn.disabled = false;
                btn.textContent = "Apply";
                return;
              }

              btn.textContent = "Applied ✅";
              logFault(`Mitigation applied: ${candData.action} on ${candData.target}`, "info");
              await loadNetwork(false);
            } catch (err) {
              alert(`Apply request failed: ${err.message}`);
              btn.disabled = false;
              btn.textContent = "Apply";
            }
          });
        });
      }
    } catch (err) {
      if (mitigationsTableContainer) {
        mitigationsTableContainer.innerHTML = `<div style="color: #f87171; padding: 10px;">Request failed: ${err.message}</div>`;
      }
    }
  });
}

// Initialize on DOM load
document.addEventListener("DOMContentLoaded", () => {
  loadNetwork();
});
