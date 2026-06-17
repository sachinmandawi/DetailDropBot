// ==========================================================
// CONFIGURATION & DOM REFERENCES
// ==========================================================
const API_ENDPOINTS = {
    mobile: "https://numberto-info-noobster.com-dashbord63hh7qe4.workers.dev/?number=",
    vehicle1: "https://vehicleto-adavanceinfo-noobster.com-dashbord63hh7qe4.workers.dev/?rc=",
    vehicle2: "https://vehicle-api-pkbw.onrender.com/api/rc?vehicle_no=",
    pan: "https://pan-info-api-1098.onrender.com/pan=",
    leak: "https://lynn-tracker-ref-contained.trycloudflare.com/leak=",
    github: "https://api.github.com/users/"
};

const TAB_METADATA = {
    mobile: {
        title: "Mobile Intelligence Search",
        desc: "Lookup location, operator, and database details for any mobile number"
    },
    vehicle: {
        title: "Vehicle Registration Search",
        desc: "Query vehicle registration cards (RC), owner names, models, and finance details"
    },
    pan: {
        title: "PAN Card Information Lookup",
        desc: "Verify Permanent Account Number (PAN) database records and owner names"
    },
    leak: {
        title: "Cyber Intelligence Leak Tracker",
        desc: "Check data breaches for compromised passwords, emails, usernames, and phones"
    },
    github: {
        title: "GitHub Developer Intel Search",
        desc: "Analyze public profile, repositories, events, and creation metrics of any GitHub developer"
    },
    settings: {
        title: "Intelligence Hub Settings",
        desc: "Configure CORS proxy bypass rules, custom endpoints, and connectivity nodes"
    }
};

// DOM Elements
const navButtons = document.querySelectorAll(".nav-btn");
const tabPanels = document.querySelectorAll(".tab-panel");
const currentTabTitle = document.getElementById("current-tab-title");
const currentTabDesc = document.getElementById("current-tab-desc");

// Search Forms & Inputs
const formMobile = document.getElementById("form-mobile");
const formVehicle = document.getElementById("form-vehicle");
const formPan = document.getElementById("form-pan");
const formLeak = document.getElementById("form-leak");
const formGithub = document.getElementById("form-github");

// Results Panel
const resultsArea = document.getElementById("results-area");
const resultsLoading = document.getElementById("results-loading");
const resultsDisplay = document.getElementById("results-display");
const btnCopyRaw = document.getElementById("btn-copy-raw");

// Settings Elements
const useCorsProxyCheck = document.getElementById("use-cors-proxy");
const corsProxyUrlInput = document.getElementById("cors-proxy-url");
const proxyUrlGroup = document.getElementById("proxy-url-group");

// History Elements
const historyItemsContainer = document.getElementById("history-items");
const btnClearHistory = document.getElementById("btn-clear-history");
const globalQueriesCountDisplay = document.getElementById("global-queries-count");

// State Variables
let appHistory = [];
let queryCount = 0;
let lastRawResponse = null;

// ==========================================================
// INITIALIZATION
// ==========================================================
document.addEventListener("DOMContentLoaded", () => {
    loadSettings();
    loadHistory();
    setupEventListeners();
});

// ==========================================================
// SETTINGS & LOCAL STORAGE
// ==========================================================
function loadSettings() {
    const savedUseProxy = localStorage.getItem("dd_use_proxy");
    const savedProxyUrl = localStorage.getItem("dd_proxy_url");
    const savedQueryCount = localStorage.getItem("dd_query_count");

    if (savedUseProxy !== null) {
        useCorsProxyCheck.checked = savedUseProxy === "true";
    }
    if (savedProxyUrl !== null) {
        if (savedProxyUrl === "https://api.allorigins.win/raw?url=") {
            corsProxyUrlInput.value = "https://corsproxy.io/?";
            localStorage.setItem("dd_proxy_url", "https://corsproxy.io/?");
        } else {
            corsProxyUrlInput.value = savedProxyUrl;
        }
    }
    if (savedQueryCount !== null) {
        queryCount = parseInt(savedQueryCount) || 0;
    }
    
    globalQueriesCountDisplay.textContent = queryCount;
    toggleProxyInputState();
}

function saveSettings() {
    localStorage.setItem("dd_use_proxy", useCorsProxyCheck.checked);
    localStorage.setItem("dd_proxy_url", corsProxyUrlInput.value.trim());
}

function toggleProxyInputState() {
    if (useCorsProxyCheck.checked) {
        proxyUrlGroup.style.display = "flex";
    } else {
        proxyUrlGroup.style.display = "none";
    }
}

// ==========================================================
// QUERY HISTORY
// ==========================================================
function loadHistory() {
    const savedHistory = localStorage.getItem("dd_query_history");
    if (savedHistory) {
        try {
            appHistory = JSON.parse(savedHistory);
        } catch (e) {
            appHistory = [];
        }
    }
    renderHistory();
}

function saveHistory() {
    localStorage.setItem("dd_query_history", JSON.stringify(appHistory));
}

function addHistoryItem(type, query) {
    const timestamp = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    // Remove if duplicate exists
    appHistory = appHistory.filter(item => !(item.type === type && item.query === query));
    
    // Insert at top
    appHistory.unshift({ type, query, timestamp });
    
    // Limit to 10 items
    if (appHistory.length > 10) {
        appHistory.pop();
    }
    
    saveHistory();
    renderHistory();
}

function renderHistory() {
    if (appHistory.length === 0) {
        historyItemsContainer.innerHTML = `
            <div class="no-history">
                <p>No queries executed in this session yet.</p>
            </div>`;
        return;
    }

    historyItemsContainer.innerHTML = "";
    appHistory.forEach(item => {
        const div = document.createElement("div");
        div.className = "history-item";
        div.innerHTML = `
            <div class="history-left">
                <span class="history-type-tag">${item.type}</span>
                <span class="history-query">${escapeHtml(item.query)}</span>
            </div>
            <span class="history-time">${item.timestamp}</span>
        `;
        div.addEventListener("click", () => {
            triggerHistoryQuery(item.type, item.query);
        });
        historyItemsContainer.appendChild(div);
    });
}

function triggerHistoryQuery(type, query) {
    // Switch to target tab
    const tabName = (type === "vehicle1" || type === "vehicle2") ? "vehicle" : type;
    switchTab(tabName);
    
    // Fill input and submit
    if (tabName === "mobile") {
        document.getElementById("mobile-number").value = query;
        formMobile.dispatchEvent(new Event("submit"));
    } else if (tabName === "vehicle") {
        document.getElementById("vehicle-no").value = query;
        // Select matching radio source
        const radio = document.querySelector(`input[name="vehicle-source"][value="${type}"]`);
        if (radio) radio.checked = true;
        formVehicle.dispatchEvent(new Event("submit"));
    } else if (tabName === "pan") {
        document.getElementById("pan-number").value = query;
        formPan.dispatchEvent(new Event("submit"));
    } else if (tabName === "leak") {
        document.getElementById("leak-query").value = query;
        formLeak.dispatchEvent(new Event("submit"));
    } else if (tabName === "github") {
        document.getElementById("github-username").value = query;
        formGithub.dispatchEvent(new Event("submit"));
    }
}

// ==========================================================
// EVENT LISTENERS
// ==========================================================
function setupEventListeners() {
    // Tab switching
    navButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            const tabName = btn.getAttribute("data-tab");
            switchTab(tabName);
        });
    });

    // Forms submission
    formMobile.addEventListener("submit", (e) => {
        e.preventDefault();
        const num = document.getElementById("mobile-number").value.trim();
        if (/^\d{10}$/.test(num)) {
            executeQuery("mobile", num, API_ENDPOINTS.mobile + num);
        } else {
            showToast("⚠️ Please enter a valid 10-digit mobile number!");
        }
    });

    formVehicle.addEventListener("submit", (e) => {
        e.preventDefault();
        const rc = document.getElementById("vehicle-no").value.trim().toUpperCase();
        const source = document.querySelector('input[name="vehicle-source"]:checked').value;
        const baseEndpoint = API_ENDPOINTS[source];
        
        if (rc.length >= 4) {
            executeQuery(source, rc, baseEndpoint + encodeURIComponent(rc));
        } else {
            showToast("⚠️ Registration number must be at least 4 characters!");
        }
    });

    formPan.addEventListener("submit", (e) => {
        e.preventDefault();
        const pan = document.getElementById("pan-number").value.trim().toUpperCase();
        if (pan.length === 10) {
            executeQuery("pan", pan, API_ENDPOINTS.pan + encodeURIComponent(pan));
        } else {
            showToast("⚠️ PAN number must be exactly 10 characters!");
        }
    });

    formLeak.addEventListener("submit", (e) => {
        e.preventDefault();
        const q = document.getElementById("leak-query").value.trim();
        if (q.length > 0) {
            executeQuery("leak", q, API_ENDPOINTS.leak + encodeURIComponent(q));
        } else {
            showToast("⚠️ Please enter a leak search query!");
        }
    });

    formGithub.addEventListener("submit", (e) => {
        e.preventDefault();
        const user = document.getElementById("github-username").value.trim();
        if (user.length > 0) {
            executeQuery("github", user, API_ENDPOINTS.github + encodeURIComponent(user));
        } else {
            showToast("⚠️ Please enter a GitHub username!");
        }
    });

    // CORS Settings changes
    useCorsProxyCheck.addEventListener("change", () => {
        toggleProxyInputState();
        saveSettings();
    });
    corsProxyUrlInput.addEventListener("input", saveSettings);

    // Clear history
    btnClearHistory.addEventListener("click", () => {
        appHistory = [];
        saveHistory();
        renderHistory();
        showToast("🗑️ Search history cleared!");
    });

    // Copy raw response
    btnCopyRaw.addEventListener("click", () => {
        if (lastRawResponse) {
            navigator.clipboard.writeText(JSON.stringify(lastRawResponse, null, 2))
                .then(() => showToast("📋 Raw JSON copied to clipboard!"))
                .catch(() => showToast("❌ Failed to copy to clipboard"));
        }
    });
}

function switchTab(tabName) {
    navButtons.forEach(b => b.classList.remove("active"));
    tabPanels.forEach(p => p.classList.remove("active"));

    const targetBtn = document.querySelector(`.nav-btn[data-tab="${tabName}"]`);
    const targetPanel = document.getElementById(`panel-${tabName}`);

    if (targetBtn && targetPanel) {
        targetBtn.classList.add("active");
        targetPanel.classList.add("active");
        
        // Update header texts
        const meta = TAB_METADATA[tabName];
        currentTabTitle.textContent = meta.title;
        currentTabDesc.textContent = meta.desc;
    }
}

// ==========================================================
// API EXECUTION ENGINE
// ==========================================================
async function executeQuery(type, queryVal, endpointUrl) {
    // Show results panel and scroll to it
    resultsArea.style.display = "flex";
    resultsLoading.style.display = "flex";
    resultsDisplay.style.display = "none";
    resultsDisplay.innerHTML = "";
    lastRawResponse = null;
    
    resultsArea.scrollIntoView({ behavior: 'smooth' });

    // Build URL using CORS proxy if enabled
    let finalUrl = endpointUrl;
    const useProxy = useCorsProxyCheck.checked;
    const proxyUrl = corsProxyUrlInput.value.trim();

    if (useProxy && proxyUrl) {
        finalUrl = proxyUrl + encodeURIComponent(endpointUrl);
    }

    try {
        const response = await fetch(finalUrl);
        
        let data = null;
        let responseText = "";
        
        try {
            responseText = await response.text();
        } catch (readErr) {
            // Failed to read body
        }
        
        if (responseText) {
            try {
                const parsed = JSON.parse(responseText);
                // Check if it's a wrapped proxy response (like AllOrigins /get)
                if (parsed && typeof parsed === "object" && "contents" in parsed) {
                    try {
                        data = JSON.parse(parsed.contents);
                    } catch (innerErr) {
                        data = { raw_text: parsed.contents };
                    }
                } else {
                    data = parsed;
                }
            } catch (e) {
                // If it's HTML or plain text, treat it as raw text
                data = { raw_text: responseText };
            }
        }
        
        lastRawResponse = data;
        
        if (!response.ok) {
            if (response.status === 404) {
                renderResults(data, 404);
            } else {
                throw new Error(`Server returned HTTP status ${response.status}`);
            }
        } else {
            // Render
            renderResults(data, 200);
        }
        
        // Increment search count
        queryCount++;
        globalQueriesCountDisplay.textContent = queryCount;
        localStorage.setItem("dd_query_count", queryCount);
        
        // Save query in history
        addHistoryItem(type, queryVal);

    } catch (error) {
        console.error("Query Execution Failed:", error);
        renderError(error.message);
    } finally {
        resultsLoading.style.display = "none";
        resultsDisplay.style.display = "grid";
    }
}

// ==========================================================
// DOM RENDERING HELPERS
// ==========================================================
function renderResults(data, status = 200) {
    resultsDisplay.innerHTML = "";
    
    if (status === 404) {
        resultsDisplay.innerHTML = `
            <div class="result-error" style="color: var(--text-secondary); padding: 3rem 1.5rem; grid-column: 1 / -1;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="width: 52px; height: 52px; stroke: var(--accent-violet); margin-bottom: 0.5rem;"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span style="font-size: 1.25rem; font-weight: 600; color: #fff;">No Records Found</span>
                <p style="font-size: 0.9rem; color: var(--text-muted); margin-top: 0.5rem; max-width: 450px; margin-left: auto; margin-right: auto; line-height: 1.5;">The query executed successfully, but no matching intelligence records were found in the database registry.</p>
            </div>`;
        return;
    }
    
    // If empty or empty object
    if (!data || Object.keys(data).length === 0) {
        resultsDisplay.innerHTML = `
            <div class="result-error" style="grid-column: 1 / -1;">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
                <span>No intelligence data found for this query in registries.</span>
            </div>`;
        return;
    }

    // Special formats or recursive flat values
    if (data.raw_text) {
        createFullCard("Raw Output", data.raw_text);
    } else {
        // Iterate through all key-values
        let cardsCreated = 0;
        
        for (const [key, value] of Object.entries(data)) {
            // Skip large nested configurations or format them nicely
            if (typeof value === "object" && value !== null) {
                // If it is a nested object, we render it formatted
                createFullCard(formatLabel(key), JSON.stringify(value, null, 2), true);
                cardsCreated++;
            } else {
                createValueCard(formatLabel(key), value);
                cardsCreated++;
            }
        }
        
        if (cardsCreated === 0) {
            createFullCard("Raw Payload JSON", JSON.stringify(data, null, 2), true);
        }
    }
}

function createValueCard(label, val) {
    const card = document.createElement("div");
    card.className = "result-card";
    
    // Mask display fallback if empty
    const displayVal = (val === null || val === undefined || val === "") ? "N/A" : val;
    
    card.innerHTML = `
        <span class="result-label">${escapeHtml(label)}</span>
        <span class="result-value">${escapeHtml(String(displayVal))}</span>
    `;
    resultsDisplay.appendChild(card);
}

function createFullCard(label, content, isPre = false) {
    const card = document.createElement("div");
    card.className = "result-card-full";
    card.innerHTML = `
        <span class="result-label" style="display:block; margin-bottom: 0.75rem;">${escapeHtml(label)}</span>
        ${isPre ? `<pre><code>${escapeHtml(content)}</code></pre>` : `<p style="word-break: break-all; line-height: 1.5; color: #fff;">${escapeHtml(content)}</p>`}
    `;
    resultsDisplay.appendChild(card);
}

function renderError(message) {
    resultsDisplay.innerHTML = `
        <div class="result-error">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="7.86 2 16.14 2 22 7.86 22 16.14 16.14 22 7.86 22 2 16.14 2 7.86 7.86 2"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
            <span>Query execution failed: ${escapeHtml(message)}</span>
            <p style="font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">If this is a CORS error, make sure the CORS Proxy checkbox is checked in settings, or check your internet connection.</p>
        </div>`;
}

// ==========================================================
// STRING & UI UTILITIES
// ==========================================================
function formatLabel(str) {
    // Convert snake_case or camelCase to clean labels
    return str
        .replace(/_/g, ' ')
        .replace(/([a-z])([A-Z])/g, '$1 $2')
        .replace(/^\w/, c => c.toUpperCase());
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

function showToast(message) {
    const toast = document.getElementById("toast");
    toast.querySelector(".toast-message").textContent = message;
    toast.classList.add("show");
    
    setTimeout(() => {
        toast.classList.remove("show");
    }, 3000);
}
