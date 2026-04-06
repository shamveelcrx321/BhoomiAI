/*
this file handles frontend logic for bhoomiai
it controls map, chat, and agent mode
*/

// setup scroll section opacity (kept from original, without frame animation)
(function initScrollOpacity() {
    let ticking = false;
    window.addEventListener('scroll', () => {
        if (!ticking) {
            window.requestAnimationFrame(() => {
                const scrollY = window.scrollY;
                const vh = window.innerHeight;
                const sections = document.querySelectorAll('.scroll-section');
                sections.forEach((sec, idx) => {
                    const secTop = idx * vh;
                    const dist = Math.abs(scrollY - secTop);
                    let opacity = 1 - (dist / (vh * 0.6));
                    sec.style.opacity = Math.max(0, Math.min(1, opacity));
                });
                ticking = false;
            });
            ticking = true;
        }
    }, { passive: true });

    // set initial opacity
    const sections = document.querySelectorAll('.scroll-section');
    sections.forEach((sec, idx) => {
        const dist = Math.abs(0 - idx * window.innerHeight);
        let opacity = 1 - (dist / (window.innerHeight * 0.6));
        sec.style.opacity = Math.max(0, Math.min(1, opacity));
    });
})();

// logic to switch between tabs
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.search-panel').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        document.getElementById(btn.dataset.target).classList.add('active');
    });
});

// logic to open and close chat box
function toggleChat() {
    document.getElementById('chat-panel').classList.toggle('open');
}

// logic to setup map display
let bhmMap     = null;
let bhmMarkers = [];
let satelliteLayer = null;
let terrainLayer = null;
let labelLayer = null;
let currentBase = 'satellite';
let layerToggleBound = false;
let analysisCircle = null;
let currentCenter = [0, 0];

function initMap(lat, lon) {
    currentCenter = [lat, lon];
    
    if (bhmMap) {
        bhmMap.setView([lat, lon], 13);
        bhmMarkers.forEach(m => bhmMap.removeLayer(m));
        bhmMarkers = [];
        if (analysisCircle) bhmMap.removeLayer(analysisCircle);
    } else {
        bhmMap = L.map('map-container',{maxZoom: 17,minZoom: 3}).setView([lat, lon], 13);

// Satellite layer
satelliteLayer = L.tileLayer(
  'https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
  {
    maxZoom: 17,
    attribution: '© Esri'
  }
);

// Terrain layer
terrainLayer = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}{r}.png',
  {
    maxZoom: 20,
    attribution: '© OpenStreetMap © CARTO'
  }
);

// Place-name labels overlay
labelLayer = L.tileLayer(
  'https://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}{r}.png',
  {
    maxZoom: 20,
    attribution: '© OpenStreetMap © CARTO',
    pane: 'overlayPane'
  }
);

// default = satellite
satelliteLayer.addTo(bhmMap);
labelLayer.addTo(bhmMap);

        // Add Recenter Control
        const recenterControl = L.control({position: 'bottomright'});
        recenterControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom');
            div.innerHTML = '🎯'; // User requested target icon
            div.title = 'Recenter to Analyzed Location';
            div.onclick = () => { map.setView(currentCenter, 14, {animate: true}); };
            return div;
        };
        recenterControl.addTo(bhmMap);

        // Add Layer Toggle Control
        const layerControl = L.control({position: 'bottomright'});
        layerControl.onAdd = function(map) {
            const div = L.DomUtil.create('div', 'leaflet-bar leaflet-control leaflet-control-custom');
            div.innerHTML = '🗺️';
            div.title = 'Toggle Satellite/Terrain';
            div.onclick = function() {
                if (currentBase === 'satellite') {
                    if (map.hasLayer(satelliteLayer)) map.removeLayer(satelliteLayer);
                    if (map.hasLayer(labelLayer)) map.removeLayer(labelLayer);
                    terrainLayer.addTo(map);
                    currentBase = 'terrain';
                    this.innerHTML = '🛰️';
                } else {
                    if (map.hasLayer(terrainLayer)) map.removeLayer(terrainLayer);
                    satelliteLayer.addTo(map);
                    labelLayer.addTo(map);
                    currentBase = 'satellite';
                    this.innerHTML = '🗺️';
                }
            };
            return div;
        };
        layerControl.addTo(bhmMap);
    }

    // Add 15km Radius Circle
    analysisCircle = L.circle([lat, lon], {
        radius: 15000,
        fillColor: 'rgba(0,100,200,0.2)',
        fillOpacity: 1, // the rgba already has 0.2 alpha
        color: 'blue',
        weight: 2,
        opacity: 0.8,
        interactive: false
    }).addTo(bhmMap);

    const siteIcon = L.divIcon({
        html: '<i class="fa-solid fa-location-crosshairs" style="color:#74C69D;font-size:26px;filter:drop-shadow(0 2px 6px rgba(0,0,0,0.5));"></i>',
        className: 'custom-div-icon',
        iconSize:   [26, 26],
        iconAnchor: [13, 13]
    });
    const m = L.marker([lat, lon], { icon: siteIcon }).addTo(bhmMap)
        .bindPopup('<b style="color:#74C69D">📍 Analysed Site</b>');
    bhmMarkers.push(m);
}

function addInfraMarker(lat, lon, name, type) {
    const config = {
        factory:  { color: '#e8a838', icon: 'fa-industry' },
        hospital: { color: '#48cae4', icon: 'fa-hospital' },
        school:   { color: '#a3e635', icon: 'fa-graduation-cap' },
        power:    { color: '#c084fc', icon: 'fa-bolt' },
        railway:  { color: '#74C69D', icon: 'fa-train-subway' },
        airport:  { color: '#fbbf24', icon: 'fa-plane' },
        market:   { color: '#fb923c', icon: 'fa-store' },
    };
    const c = config[type] || { color: '#aaa', icon: 'fa-circle-dot' };
    const markerIcon = L.divIcon({
        html: `<i class="fa-solid ${c.icon}" style="color:${c.color};font-size:15px;"></i>`,
        className: 'custom-div-icon',
        iconSize: [16, 16], iconAnchor: [8, 8]
    });
    const m = L.marker([lat, lon], { icon: markerIcon }).addTo(bhmMap)
        .bindPopup(`<b>${name}</b><br><span style="color:${c.color}">${type}</span>`);
    bhmMarkers.push(m);
}

// store analyzed location for agent context
let currentAnalysisContext = null;

// logic to send site coordinates to backend and fetch data
async function analyzeLocation(type) {
    const payload = {};
    if (type === 'text') {
        const query = document.getElementById('loc-input').value.trim();
        if (!query) return alert('Enter a location name');
        payload.query = query;
    } else {
        const lat = document.getElementById('lat-input').value;
        const lon = document.getElementById('lon-input').value;
        if (!lat || !lon) return alert('Enter valid coordinates');
        payload.lat = parseFloat(lat);
        payload.lon = parseFloat(lon);
    }

    // show loading screen while backend is working
    // Clear existing markers immediately before fetch
    if (bhmMap) {
        bhmMarkers.forEach(m => bhmMap.removeLayer(m));
        bhmMarkers = [];
        if (analysisCircle) {
            bhmMap.removeLayer(analysisCircle);
            analysisCircle = null;
        }
    }
    
    document.getElementById('global-loader').classList.remove('hidden');
    document.getElementById('hero-section').style.display = 'none';
    document.getElementById('dashboard-section').classList.add('hidden');

    try {
        const res = await fetch('/api/analyze_location', {
            method:  'POST',
            headers: { 'Content-Type': 'application/json' },
            body:    JSON.stringify(payload)
        });
        const data = await res.json();

        if (data.error) {
            alert(data.error);
            resetSearch();
            return;
        }

        // save context for agent mode
        const ctx = data.context;
        currentAnalysisContext = {
            location: ctx.address?.display || payload.query || '',
            lat: ctx.coordinates?.lat,
            lon: ctx.coordinates?.lon,
        };

        populateDashboard(ctx);

        document.getElementById('global-loader').classList.add('hidden');
        document.getElementById('dashboard-section').classList.remove('hidden');
        setTimeout(() => { if (bhmMap) bhmMap.invalidateSize(); }, 150);

    } catch (e) {
        console.error(e);
        const msg = e.message || 'Unknown error occurred.';
        if (window.showNotification) showNotification(`Error: ${msg}`, 'error');
        else alert(`Error: ${msg}`);
        resetSearch();
    }
}

function resetSearch() {
    document.getElementById('global-loader').classList.add('hidden');
    document.getElementById('dashboard-section').classList.add('hidden');
    document.getElementById('hero-section').style.display = 'flex';
    currentAnalysisContext = null;

    // reset input fields
    const locInput = document.getElementById('loc-input');
    if (locInput) locInput.value = '';
    const latInput = document.getElementById('lat-input');
    if (latInput) latInput.value = '';
    const lonInput = document.getElementById('lon-input');
    if (lonInput) lonInput.value = '';

    // reset metric display values
    ['val-temp','val-humidity','val-wind','val-elevation','val-aqi','val-pm25'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.innerHTML = '--';
    });
    const valAqi = document.getElementById('val-aqi');
    if (valAqi) valAqi.className = 'metric-value';
    const valLanduse = document.getElementById('val-landuse');
    if (valLanduse) valLanduse.innerText = '--';
    const terrainChips = document.getElementById('terrain-chips');
    if (terrainChips) terrainChips.innerHTML = '';

    // reset infra cards — remove stale color classes, reset text
    ['infra-road','infra-rail','infra-hospital','infra-school','infra-power','infra-factory','infra-airport','infra-market'].forEach(id => {
        const el = document.getElementById(id);
        if (!el) return;
        el.classList.remove('found', 'found-sky', 'found-amber');
        const distEl = el.querySelector('.infra-dist');
        const nameEl = el.querySelector('.infra-name');
        if (distEl) distEl.innerText = '--';
        if (nameEl) nameEl.innerText = '--';
    });

    // reset demographics and context text
    const demoText = document.getElementById('demo-text');
    if (demoText) demoText.innerText = 'Gathering district data from government sources...';
    const demoBadge = document.getElementById('demo-badge');
    if (demoBadge) demoBadge.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> <span>Fetching...</span>';
    const demoLabel = document.getElementById('demo-source-label');
    if (demoLabel) demoLabel.innerText = 'Loading...';
    const wikiText = document.getElementById('wiki-text');
    if (wikiText) wikiText.innerHTML = 'Pending...';
    const webText = document.getElementById('web-text');
    if (webText) webText.innerHTML = 'Pending...';

    // reset location display
    const locDisplay = document.getElementById('loc-display-name');
    if (locDisplay) locDisplay.innerText = 'Scanning...';

    // clear map markers (keep the map instance alive)
    if (bhmMap) {
        bhmMarkers.forEach(m => bhmMap.removeLayer(m));
        bhmMarkers = [];
        if (analysisCircle) {
            bhmMap.removeLayer(analysisCircle);
            analysisCircle = null;
        }
    }

    // reset chat
    const chatMessages = document.getElementById('chat-messages');
    if (chatMessages) chatMessages.innerHTML = '<div class="message sys-msg">🌱 Earth context loaded. Ask me about the site\'s infrastructure, demographics, or environmental suitability.</div>';
}

// this function returns color class based on air quality
function aqiClass(v) {
    if (!v && v !== 0) return '';
    if (v <= 20) return 'aqi-good';
    if (v <= 40) return 'aqi-fair';
    if (v <= 60) return 'aqi-moderate';
    if (v <= 80) return 'aqi-poor';
    return 'aqi-very-poor';
}

// logic to fill dashboard with fetched data
function populateDashboard(ctx) {
    // show location name
    const addr  = ctx.address || {};
    const parts = [
        addr.place, addr.road, addr.neighbourhood,
        addr.village, addr.town, addr.district, addr.state,
    ].filter(Boolean);
    const title = parts.length > 0
        ? parts.slice(0, 4).join(', ')
        : `${ctx.coordinates.lat.toFixed(5)}, ${ctx.coordinates.lon.toFixed(5)}`;

    const locEl = document.getElementById('loc-display-name');
    locEl.innerText = title;
    if (addr.postcode) locEl.innerText += ` — PIN ${addr.postcode}`;

    // setup map for the site
    initMap(ctx.coordinates.lat, ctx.coordinates.lon);

    // show weather info
    const clim = ctx.climate || {};
    document.getElementById('val-temp').innerHTML =
        clim.temperature_2m != null
            ? `${clim.temperature_2m}<span class="metric-unit">°C</span>` : '--';
    document.getElementById('val-humidity').innerHTML =
        clim.relative_humidity_2m != null
            ? `${clim.relative_humidity_2m}<span class="metric-unit">%</span>` : '--';
    document.getElementById('val-wind').innerHTML =
        clim.wind_speed_10m != null
            ? `${clim.wind_speed_10m}<span class="metric-unit"> km/h</span>` : '--';

    // show height above sea level
    document.getElementById('val-elevation').innerHTML =
        ctx.elevation_m != null
            ? `${ctx.elevation_m}<span class="metric-unit">m</span>` : '--';

    // show air pollution data
    const aqi    = ctx.air_quality || {};
    const aqiVal = aqi.european_aqi;
    const aqiEl  = document.getElementById('val-aqi');
    aqiEl.innerHTML  = aqiVal != null ? `${aqiVal}` : '--';
    aqiEl.className  = 'metric-value ' + aqiClass(aqiVal);

    document.getElementById('val-pm25').innerHTML =
        aqi.pm2_5 != null
            ? `${aqi.pm2_5}<span class="metric-unit"> μg</span>` : '--';

    // show how the land is used
    const landuse = ctx.landuse || [];
    document.getElementById('val-landuse').innerText =
        landuse.length > 0 ? landuse.join(', ') : 'No specific zone data';

    // create small tags for terrain type
    const tc      = ctx.terrain_counts || {};
    const chipsEl = document.getElementById('terrain-chips');
    chipsEl.innerHTML = '';
    const chipDefs = [
        { key: 'forest_wood',    label: 'Forest',   icon: 'fa-tree',     cls: 'chip-forest' },
        { key: 'water',          label: 'Water',    icon: 'fa-water',    cls: 'chip-water'  },
        { key: 'mountain_peak',  label: 'Peaks',    icon: 'fa-mountain', cls: 'chip-peak'   },
        { key: 'farmland',       label: 'Farmland', icon: 'fa-seedling', cls: 'chip-farm'   },
    ];
    chipDefs.forEach(({ key, label, icon, cls }) => {
        const count = tc[key] || 0;
        const chip  = document.createElement('span');
        chip.className  = `terrain-chip ${cls}`;
        chip.innerHTML  = `<i class="fa-solid ${icon}"></i> ${label}: ${count}`;
        chipsEl.appendChild(chip);
    });

    // show nearby facilities like hospitals and schools
    function setInfra(id, obj, mapType, colorClass) {
        const el = document.getElementById(id);
        if (!el) return;
        if (obj && obj.distance_km != null) {
            el.querySelector('.infra-dist').innerText = `${obj.distance_km} km`;
            el.querySelector('.infra-name').innerText = (obj.name || 'Unnamed').substring(0, 28);
            el.classList.add(colorClass || 'found');
            if (mapType && obj.lat && obj.lon) {
                addInfraMarker(obj.lat, obj.lon, obj.name, mapType);
            }
        } else {
            el.querySelector('.infra-dist').innerText = '>15 km';
            el.querySelector('.infra-name').innerText = 'None found';
        }
    }

    const infra = ctx.infrastructure || {};
    setInfra('infra-road',     infra.road,               null,       'found');
    setInfra('infra-rail',     infra.railway_station,    'railway',  'found');
    setInfra('infra-hospital', infra.hospital,           'hospital', 'found-sky');
    setInfra('infra-school',   infra.school,             'school',   'found');
    setInfra('infra-power',    infra.power_substation,   'power',    'found-amber');
    setInfra('infra-factory',  infra.factory_building,   'factory',  'found-amber');
    setInfra('infra-airport',  infra.airport,            'airport',  'found-amber');
    setInfra('infra-market',   infra.market,             'market',   'found');

    // show district population data
    const demo    = ctx.demographics || {};
    const demoSrc = demo.source || 'none';

    const sourceLabels = {
        'nic_gov_site':       { label: 'Government NIC Portal', icon: 'fa-building-columns' },
        'wikipedia_district': { label: 'Wikipedia District',    icon: 'fa-book-open'        },
        'ddg_page':           { label: 'Web Research',          icon: 'fa-globe'            },
        'wikidata':           { label: 'Wikidata',              icon: 'fa-database'         },
        'ddg_snippets':       { label: 'Search Snippets',       icon: 'fa-magnifying-glass' },
        'none':               { label: 'Not Available',         icon: 'fa-triangle-exclamation' },
    };
    const srcInfo = sourceLabels[demoSrc] || sourceLabels['none'];

    document.getElementById('demo-source-label').innerText = srcInfo.label;
    document.getElementById('demo-badge').innerHTML =
        `<i class="fa-solid ${srcInfo.icon}"></i> <span>${srcInfo.label}</span>`;

    const demoText = demo.text || 'Not available.';
    const formattedDemo = demoText !== 'Not available.'
        ? demoText.replace(/\|/g, '\n').substring(0, 2000)
        : '⚠️ District demographic data could not be retrieved. Try a different location.';
    document.getElementById('demo-text').innerText = formattedDemo;

    // show extra details from wikipedia and web
    const wiki    = ctx.wikipedia || {};
    const wikiHtml = wiki.summary
        ? `<strong style="color:var(--text-accent)">${wiki.title}:</strong> ${wiki.summary.substring(0, 1500)}`
        : 'No Wikipedia article found near these coordinates.';

    const webCtx  = ctx.web_context;
    const webHtml = webCtx
        ? `<strong style="color:var(--sky-blue)">📡 Web Context:</strong> ${webCtx}`
        : 'No web context available.';

    document.getElementById('wiki-text').innerHTML = wikiHtml;
    document.getElementById('web-text').innerHTML  = webHtml;

    // clear chat history for new site
    document.getElementById('chat-messages').innerHTML =
        '<div class="message sys-msg">🌱 Earth context loaded. Ask me about the site\'s suitability, demographics, or infrastructure.</div>';
}

// agent mode state
let agentMode = false;
document.getElementById('agent-mode-toggle').addEventListener('change', function() {
    agentMode = this.checked;
    const chatEl = document.getElementById('chat-messages');
    if (agentMode) {
        chatEl.innerHTML += '<div class="message sys-msg">🤖 Agent Mode ON — Using Qwen3 with live tool-calling. Responses may take longer.</div>';
    } else {
        chatEl.innerHTML += '<div class="message sys-msg">🌱 Standard Mode — Using Gemma3 RAG pipeline.</div>';
    }
    chatEl.scrollTop = chatEl.scrollHeight;
});

// logic to handle user questions and show ai answers
async function sendChat() {
    const inputEl = document.getElementById('chat-input');
    const msg     = inputEl.value.trim();
    if (!msg) return;
    inputEl.value = '';

    const chatEl = document.getElementById('chat-messages');
    chatEl.innerHTML += `<div class="message user-msg">${msg}</div>`;
    chatEl.scrollTop  = chatEl.scrollHeight;

    const loaderId = 'ld-' + Date.now();
    const loaderText = agentMode ? '<i class="fa-solid fa-robot fa-spin"></i> Agent thinking...' : '<i class="fa-solid fa-spinner fa-spin"></i> Thinking...';
    chatEl.innerHTML += `<div class="message sys-msg" id="${loaderId}">${loaderText}</div>`;
    chatEl.scrollTop  = chatEl.scrollHeight;

    try {
        let responseHtml = '';

        if (agentMode) {
            // agent mode — route to /api/agent
            const payload = {
                query: msg,
                location: currentAnalysisContext?.location || '',
                coordinates: currentAnalysisContext ? {
                    lat: currentAnalysisContext.lat,
                    lon: currentAnalysisContext.lon
                } : null,
            };

            const res = await fetch('/api/agent', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify(payload)
            });
            const data = await res.json();
            document.getElementById(loaderId)?.remove();

            if (data.error) {
                chatEl.innerHTML += `<div class="message sys-msg" style="color:#f87171">${data.error}</div>`;
            } else {
                // build agent response with reasoning trace
                const answerHtml = marked.parse(data.answer || 'No answer generated.');
                const toolsHtml = data.tools_used && data.tools_used.length > 0
                    ? `<div class="agent-tools-used"><i class="fa-solid fa-wrench"></i> Tools: ${data.tools_used.join(', ')}</div>`
                    : '';
                const traceHtml = data.reasoning_trace && data.reasoning_trace.length > 0
                    ? `<details class="agent-trace"><summary><i class="fa-solid fa-list-check"></i> Reasoning Trace (${data.reasoning_trace.length} steps)</summary><pre>${data.reasoning_trace.join('\n')}</pre></details>`
                    : '';

                chatEl.innerHTML += `<div class="message ai-msg agent-response">${answerHtml}${toolsHtml}${traceHtml}</div>`;
            }
        } else {
            // standard mode — route to /api/chat
            const res = await fetch('/api/chat', {
                method:  'POST',
                headers: { 'Content-Type': 'application/json' },
                body:    JSON.stringify({ question: msg })
            });
            const data = await res.json();
            document.getElementById(loaderId)?.remove();

            if (data.error) {
                chatEl.innerHTML += `<div class="message sys-msg" style="color:#f87171">${data.error}</div>`;
            } else {
                chatEl.innerHTML += `<div class="message ai-msg">${marked.parse(data.response)}</div>`;
            }
        }
    } catch (e) {
        document.getElementById(loaderId)?.remove();
        chatEl.innerHTML += `<div class="message sys-msg" style="color:#f87171">Connection failed.</div>`;
    }
    chatEl.scrollTop = chatEl.scrollHeight;
}

// let user press enter to send message
document.getElementById('chat-input').addEventListener('keypress', e => {
    if (e.key === 'Enter') sendChat();
});
