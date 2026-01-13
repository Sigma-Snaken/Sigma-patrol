document.addEventListener('DOMContentLoaded', () => {
    // DOM Elements
    const canvas = document.getElementById('map-canvas');
    const ctx = canvas.getContext('2d');
    const loadingOverlay = document.getElementById('map-loading');
    const batteryValue = document.getElementById('battery-value');
    const timeValue = document.getElementById('time-value');
    const connectionStatus = document.getElementById('connection-status');
    const btnHome = document.getElementById('btn-home');
    const poseDisplay = document.getElementById('pose-display');

    // New Elements
    const btnStartPatrol = document.getElementById('btn-start-patrol');
    const btnStopPatrol = document.getElementById('btn-stop-patrol');
    const btnAddPoint = document.getElementById('btn-add-point');
    const btnAddPointQuick = document.getElementById('btn-add-point-quick');
    const btnSaveSettings = document.getElementById('btn-save-settings');
    const btnTestAI = document.getElementById('btn-test-ai');
    const patrolStatusDisplay = document.getElementById('patrol-status-display');
    const resultsContainer = document.getElementById('results-container');
    const pointsTableBody = document.querySelector('#points-table tbody');
    const pointsTableQuickBody = document.querySelector('#points-table-quick tbody');
    const aiTestOutput = document.getElementById('ai-test-output');


    // ... [Previous State & Constants code] ...
    // Note: To avoid repeating entire file, I will assume the user has the code.
    // However, for safety in this tool, I should replace large chunks or be careful.
    // The replace block here is replacing the top section of `main.js` which defines elements.
    // I also need to add the listeners.

    // ... Assuming standard `State` and `Constants` blocks are unchanged ...

    // Event Listeners
    if (btnHome) btnHome.addEventListener('click', returnHome);

    // Canvas Interactions
    if (canvas) {
        canvas.addEventListener('mousedown', handleMouseDown);
        canvas.addEventListener('mousemove', handleMouseMove);
        canvas.addEventListener('mouseup', handleMouseUp);
    }

    // New Listeners
    if (btnAddPoint) btnAddPoint.addEventListener('click', addCurrentPoint);
    if (btnAddPointQuick) btnAddPointQuick.addEventListener('click', addCurrentPoint);
    if (btnSaveSettings) btnSaveSettings.addEventListener('click', saveSettings);
    if (btnStartPatrol) btnStartPatrol.addEventListener('click', startPatrol);
    if (btnStopPatrol) btnStopPatrol.addEventListener('click', stopPatrol);
    if (btnTestAI) btnTestAI.addEventListener('click', testAI);

    // --- TABS ---
    window.switchTab = function (tabName) {
        document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
        document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

        const target = document.getElementById(`view-${tabName}`);
        if (target) target.style.display = 'block';

        // Hacky selector for active button
        const btns = document.querySelectorAll('.tab-btn');
        if (tabName === 'patrol' && btns[0]) btns[0].classList.add('active');
        if (tabName === 'control' && btns[1]) btns[1].classList.add('active');
        if (tabName === 'history' && btns[2]) btns[2].classList.add('active');
        if (tabName === 'stats' && btns[3]) btns[3].classList.add('active');
        if (tabName === 'settings' && btns[4]) btns[4].classList.add('active');

        // Load specific data
        if (tabName === 'history') loadHistory();
        if (tabName === 'stats') loadStats();
        if (tabName === 'settings') loadSettings();

        // Reparent Map Container
        const mapContainer = document.getElementById('map-container');
        if (tabName === 'control') {
            const dest = document.querySelector('#view-control .left-panel');
            if (dest && mapContainer.parentNode !== dest) {
                // Insert at top so it sits above the controls
                dest.prepend(mapContainer);
            }
            setTimeout(resizeCanvas, 50);
        } else if (tabName === 'patrol') {
            const dest = document.getElementById('patrol-left-panel');
            if (dest && mapContainer.parentNode !== dest) dest.appendChild(mapContainer);
            setTimeout(resizeCanvas, 50);
        } else if (tabName === 'history') {
            // Already handled above
        }
    };

    // ... [Previous Map, Polling, Draw, Input logic] ... 
    // I will use replace_file_content to inject the renderPointsTable update and testAI function
    // effectively by rewriting the end of the file or relevant functions.

    // Let's rewrite `renderPointsTable` to handle both tables
    function renderPointsTable() {
        if (pointsTableBody) {
            pointsTableBody.innerHTML = '';
            currentPatrolPoints.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="text" value="${p.name || ''}" onchange="updatePoint('${p.id}', 'name', this.value)" style="width:100px; background:rgba(0,0,0,0.2); border:none; color:white;"></td>
                    <td style="font-family:monospace; font-size:0.8rem;">X:${p.x.toFixed(2)} Y:${p.y.toFixed(2)} T:${p.theta.toFixed(2)}</td>
                    <td><input type="text" value="${p.prompt || ''}" onchange="updatePoint('${p.id}', 'prompt', this.value)" style="width:200px; background:rgba(0,0,0,0.2); border:none; color:white;"></td>
                    <td><input type="checkbox" ${p.enabled !== false ? 'checked' : ''} onchange="updatePoint('${p.id}', 'enabled', this.checked)"></td>
                    <td><button onclick="deletePoint('${p.id}')" style="color:red; background:none; border:none; cursor:pointer;">del</button></td>
                `;
                pointsTableBody.appendChild(tr);
            });
        }

        if (pointsTableQuickBody) {
            pointsTableQuickBody.innerHTML = '';
            currentPatrolPoints.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="color: ${p.enabled !== false ? 'white' : 'gray'}">${p.name || 'Unnamed'}</td>
                    <td>
                        <button onclick="deletePoint('${p.id}')" style="color:red; background:none; border:none; cursor:pointer;">del</button>
                    </td>
                `;
                pointsTableQuickBody.appendChild(tr);
            });
        }
    }

    // Test AI Function
    async function testAI() {
        if (!aiTestOutput) return;
        aiTestOutput.innerText = "Capturing and analyzing...";
        aiTestOutput.style.color = "#26c6da";

        try {
            const res = await fetch('/api/test_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({}) // Use default prompt
            });

            const data = await res.json();
            if (data.error) {
                aiTestOutput.innerText = "Error: " + data.error;
                aiTestOutput.style.color = "#ff3b30";
            } else {
                aiTestOutput.innerText = data.result;
                aiTestOutput.style.color = "#00e676";
            }
        } catch (e) {
            aiTestOutput.innerText = "Network Error: " + e;
            aiTestOutput.style.color = "#ff3b30";
        }
    }

    // ... [Rest of the file] ...

    // State
    let mapImage = new Image();
    let mapInfo = null;
    let robotPose = { x: 0, y: 0, theta: 0 };
    let isMapLoaded = false;
    let isDragging = false;
    let dragStart = null;
    let dragCurrent = null;
    let currentPatrolPoints = [];
    let currentSettingsTimezone = 'UTC';

    // Constants
    const ROBOT_COLOR = '#00bcd4';
    const GHOST_ROBOT_COLOR = 'rgba(0, 188, 212, 0.5)';

    // Initialization
    loadMap();
    startPolling();
    loadSettings();
    loadPoints();
    loadResults();
    startPatrolPolling();

    // Event Listeners
    if (btnHome) btnHome.addEventListener('click', returnHome);
    const btnCancelCommand = document.getElementById('btn-cancel-command');
    if (btnCancelCommand) btnCancelCommand.addEventListener('click', cancelCommand);

    // Canvas Interactions
    canvas.addEventListener('mousedown', handleMouseDown);
    canvas.addEventListener('mousemove', handleMouseMove);
    canvas.addEventListener('mouseup', handleMouseUp);

    // New Listeners
    if (btnAddPoint) btnAddPoint.addEventListener('click', addCurrentPoint);
    if (btnSaveSettings) btnSaveSettings.addEventListener('click', saveSettings);
    if (btnStartPatrol) btnStartPatrol.addEventListener('click', startPatrol);
    if (btnStopPatrol) btnStopPatrol.addEventListener('click', stopPatrol);

    // Export/Import Points
    const btnSavePoints = document.getElementById('btn-save-points');
    const btnExportPoints = document.getElementById('btn-export-points');
    const btnImportPoints = document.getElementById('btn-import-points');
    const importFileInput = document.getElementById('import-file-input');

    if (btnSavePoints) {
        btnSavePoints.addEventListener('click', async () => {
            const originalText = btnSavePoints.innerText;
            btnSavePoints.innerText = 'Saving...';
            try {
                await saveAllPoints();
                btnSavePoints.innerText = 'Saved!';
            } catch (e) {
                btnSavePoints.innerText = 'Error';
                alert('Save failed: ' + e);
            }
            setTimeout(() => {
                btnSavePoints.innerText = originalText;
            }, 1500);
        });
    }

    if (btnExportPoints) {
        btnExportPoints.addEventListener('click', () => {
            window.location.href = '/api/points/export';
        });
    }

    if (btnImportPoints && importFileInput) {
        btnImportPoints.addEventListener('click', () => {
            importFileInput.click();
        });

        importFileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            const formData = new FormData();
            formData.append('file', file);

            try {
                const res = await fetch('/api/points/import', {
                    method: 'POST',
                    body: formData
                });
                const data = await res.json();
                if (data.status === 'imported') {
                    alert(`Successfully imported ${data.count} points.`);
                    loadPoints(); // Refresh table
                } else {
                    alert('Import failed: ' + (data.error || 'Unknown error'));
                }
            } catch (err) {
                alert('Import error: ' + err);
            }
            // Reset input
            importFileInput.value = '';
        });
    }

    // --- TABS (Duplicate removed, logic consolidated above) ---
    // The previous switchTab implementation at line 52 is the authoritative one.
    // This block was a duplicate in the original file view or an artifact of reading.
    // I will remove the duplicate definition and keep the initialization.

    // Default
    window.switchTab('control');

    // --- MAP & POLLING (Existing) ---
    function loadMap() {
        console.log("Attempting to load map from /api/map...");
        const url = '/api/map?t=' + new Date().getTime();
        console.log("Map URL:", url);
        mapImage.src = url;

        // Debug: Append to see if it renders
        mapImage.style.display = 'none';
        // document.body.appendChild(mapImage); 
        // (Commented out to keep UI clean, but uncomment if desperate)

        window.debugMapImage = mapImage; // Expose

        mapImage.onload = () => {
            console.log("Map image LOADED. Size:", mapImage.width, mapImage.height);
            isMapLoaded = true;
            if (loadingOverlay) loadingOverlay.style.display = 'none';
            resizeCanvas();
        };

        mapImage.onerror = (e) => {
            console.error("Map image ERROR", e);
            setTimeout(loadMap, 2000);
        };
    }

    function startPolling() {
        setInterval(async () => {
            try {
                const response = await fetch('/api/state');
                if (response.ok) {
                    const data = await response.json();
                    updateState(data);
                    if (connectionStatus) connectionStatus.classList.add('connected');
                } else {
                    if (connectionStatus) connectionStatus.classList.remove('connected');
                }
            } catch (e) {
                if (connectionStatus) connectionStatus.classList.remove('connected');
            }
        }, 100);
    }

    function updateState(data) {
        if (data.battery !== undefined) batteryValue.textContent = Math.floor(data.battery) + '%';
        if (data.pose) {
            robotPose = data.pose;
            poseDisplay.textContent = `X: ${robotPose.x.toFixed(2)} Y: ${robotPose.y.toFixed(2)} T: ${robotPose.theta.toFixed(2)}`;
        }
        if (data.map_info && !mapInfo) mapInfo = data.map_info;
        draw();
    }

    function resizeCanvas() {
        if (!isMapLoaded) return;

        // 1. Set internal resolution to native map size
        canvas.width = mapImage.width;
        canvas.height = mapImage.height;

        // 2. Calculate scaling to fit container (Contain)
        const container = document.getElementById('map-container');
        const containerWidth = container.clientWidth;
        const containerHeight = container.clientHeight;
        const imageRatio = mapImage.width / mapImage.height;
        const containerRatio = containerWidth / containerHeight;

        let finalWidth, finalHeight;

        if (containerRatio > imageRatio) {
            // Container is wider than image -> Constrain by height
            finalHeight = containerHeight;
            finalWidth = finalHeight * imageRatio;
        } else {
            // Container is taller/narrower -> Constrain by width
            finalWidth = containerWidth;
            finalHeight = finalWidth / imageRatio;
        }

        // 3. Apply CSS style to scale visual presentation (can be > 100%)
        canvas.style.width = `${finalWidth}px`;
        canvas.style.height = `${finalHeight}px`;

        draw();
    }

    // Add window resize listener
    window.addEventListener('resize', () => {
        resizeCanvas();
    });

    function draw() {
        if (!isMapLoaded) return;
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        ctx.drawImage(mapImage, 0, 0);

        // Draw Patrol Points
        if (mapInfo && currentPatrolPoints) {
            currentPatrolPoints.forEach(p => {
                const u = worldToPixelX(p.x);
                const v = worldToPixelY(p.y);

                // Highlight logic
                if (highlightedPoint && highlightedPoint.id === p.id) {
                    // Pulse or big marker
                    ctx.beginPath();
                    ctx.arc(u, v, 10, 0, 2 * Math.PI);
                    ctx.fillStyle = 'rgba(255, 235, 59, 0.7)'; // Yellow
                    ctx.fill();
                    ctx.strokeStyle = 'white';
                    ctx.lineWidth = 2;
                    ctx.stroke();
                }
                // else {
                //     // Hide normal points to avoid clutter/"strange dots"
                //     // Only show when requested via button
                // }
            });
        }

        if (mapInfo) {
            drawRobot(robotPose, ROBOT_COLOR);
            if (isDragging && dragStart && dragCurrent) {
                const ghostPose = {
                    x: pixelToWorldX(dragStart.u),
                    y: pixelToWorldY(dragStart.v),
                    theta: Math.atan2(-(dragCurrent.v - dragStart.v), (dragCurrent.u - dragStart.u))
                };
                drawRobotFromPixels(dragStart.u, dragStart.v, ghostPose.theta, GHOST_ROBOT_COLOR);

                ctx.beginPath();
                ctx.moveTo(dragStart.u, dragStart.v);
                ctx.lineTo(dragCurrent.u, dragCurrent.v);
                ctx.strokeStyle = '#26c6da';
                ctx.setLineDash([5, 5]);
                ctx.stroke();
                ctx.setLineDash([]);
            }
        }
    }

    function drawRobot(pose, color) {
        const u = worldToPixelX(pose.x);
        const v = worldToPixelY(pose.y);
        drawRobotFromPixels(u, v, pose.theta, color);
    }

    function drawRobotFromPixels(u, v, theta, color) {
        ctx.save();
        ctx.translate(u, v);
        ctx.rotate(-theta);
        ctx.beginPath();
        const size = 15;
        ctx.moveTo(size, 0);
        ctx.lineTo(-size / 2, size / 2);
        ctx.lineTo(-size / 2, -size / 2);
        ctx.closePath();
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.moveTo(0, 0);
        ctx.lineTo(size, 0);
        ctx.stroke();
        ctx.restore();
    }

    function worldToPixelX(x) { if (!mapInfo) return 0; return (x - mapInfo.origin_x) / mapInfo.resolution; }
    function worldToPixelY(y) { if (!mapInfo) return 0; return mapInfo.height - (y - mapInfo.origin_y) / mapInfo.resolution; }
    function pixelToWorldX(u) { if (!mapInfo) return 0; return u * mapInfo.resolution + mapInfo.origin_x; }
    function pixelToWorldY(v) { if (!mapInfo) return 0; return (mapInfo.height - v) * mapInfo.resolution + mapInfo.origin_y; }

    function handleMouseDown(e) {
        if (!isMapLoaded || !mapInfo) return;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const u = (e.clientX - rect.left) * scaleX;
        const v = (e.clientY - rect.top) * scaleY;
        isDragging = true;
        dragStart = { u, v };
        dragCurrent = { u, v };
    }

    function handleMouseMove(e) {
        if (!isDragging) return;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const u = (e.clientX - rect.left) * scaleX;
        const v = (e.clientY - rect.top) * scaleY;
        dragCurrent = { u, v };
        draw();
    }

    function handleMouseUp(e) {
        if (!isDragging) return;
        isDragging = false;
        const rect = canvas.getBoundingClientRect();
        const scaleX = canvas.width / rect.width;
        const scaleY = canvas.height / rect.height;
        const u = (e.clientX - rect.left) * scaleX;
        const v = (e.clientY - rect.top) * scaleY;

        const targetX = pixelToWorldX(dragStart.u);
        const targetY = pixelToWorldY(dragStart.v);
        let theta = 0;
        const dx = u - dragStart.u;
        const dy = v - dragStart.v;
        const dist = Math.sqrt(dx * dx + dy * dy);

        if (dist > 10) {
            theta = Math.atan2(-dy, dx);
        } else {
            theta = robotPose.theta;
        }

        moveRobot(targetX, targetY, theta);
        dragStart = null;
        dragCurrent = null;
        draw();
    }

    async function moveRobot(x, y, theta) {
        try {
            await fetch('/api/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x, y, theta })
            });
        } catch (e) { console.error("Move Failed", e); }
    }

    async function returnHome() {
        try { await fetch('/api/return_home', { method: 'POST' }); }
        catch (e) { console.error("Return Home Failed", e); }
    }

    async function cancelCommand() {
        try { await fetch('/api/cancel_command', { method: 'POST' }); }
        catch (e) { console.error("Cancel Command Failed", e); }
    }

    // --- PATROL & SETTINGS LOGIC ---

    async function loadSettings() {
        const res = await fetch('/api/settings');
        const data = await res.json();
        document.getElementById('setting-api-key').value = data.gemini_api_key || '';
        document.getElementById('setting-model').value = data.gemini_model || 'gemini-1.5-flash';
        const tz = data.timezone || 'UTC';
        document.getElementById('setting-timezone').value = tz;
        currentSettingsTimezone = tz;
        document.getElementById('setting-role').value = data.system_prompt || '';
        document.getElementById('setting-report-prompt').value = data.report_prompt || '';

        // Turbo Mode
        const turboCheckbox = document.getElementById('setting-turbo-mode');
        if (turboCheckbox) turboCheckbox.checked = data.turbo_mode === true;

        // Handle robot_ip if element exists (will be added to HTML next)
        const ipInput = document.getElementById('setting-robot-ip');
        if (ipInput) ipInput.value = data.robot_ip || '192.168.50.133:26400';
    }

    async function saveSettings() {
        const settings = {
            gemini_api_key: document.getElementById('setting-api-key').value,
            gemini_model: document.getElementById('setting-model').value,
            timezone: document.getElementById('setting-timezone').value,
            system_prompt: document.getElementById('setting-role').value,
            report_prompt: document.getElementById('setting-report-prompt').value,
            turbo_mode: document.getElementById('setting-turbo-mode').checked,
            robot_ip: document.getElementById('setting-robot-ip') ? document.getElementById('setting-robot-ip').value : '192.168.50.133:26400'
        };
        await fetch('/api/settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settings)
        });
        currentSettingsTimezone = settings.timezone;
        alert('Settings Saved! (Robot connection may reload)');
    }

    function startClock() {
        setInterval(() => {
            if (timeValue) {
                try {
                    timeValue.textContent = new Date().toLocaleTimeString('en-US', {
                        timeZone: currentSettingsTimezone,
                        hour12: false,
                        hour: '2-digit',
                        minute: '2-digit'
                    });
                } catch (e) {
                    timeValue.textContent = "--:--";
                }
            }
        }, 1000);
    }
    startClock();

    async function loadPoints() {
        const res = await fetch('/api/points');
        currentPatrolPoints = await res.json();
        renderPointsTable();
    }

    // --- RENDER POINTS ---
    function renderPointsTable() {
        // Detailed Table (Settings - if kept)
        if (pointsTableBody) {
            pointsTableBody.innerHTML = '';
            currentPatrolPoints.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td><input type="text" value="${p.name || ''}" onchange="updatePoint('${p.id}', 'name', this.value)" style="width:100px; background:rgba(0,0,0,0.2); border:none; color:white;"></td>
                    <td style="font-family:monospace; font-size:0.8rem;">X:${p.x.toFixed(2)} Y:${p.y.toFixed(2)} T:${p.theta.toFixed(2)}</td>
                    <td><input type="text" value="${p.prompt || ''}" onchange="updatePoint('${p.id}', 'prompt', this.value)" style="width:200px; background:rgba(0,0,0,0.2); border:none; color:white;"></td>
                    <td><input type="checkbox" ${p.enabled !== false ? 'checked' : ''} onchange="updatePoint('${p.id}', 'enabled', this.checked)"></td>
                    <td><button onclick="deletePoint('${p.id}')" style="color:red; background:none; border:none; cursor:pointer;">del</button></td>
                `;
                pointsTableBody.appendChild(tr);
            });
        }

        // Quick Table (Control View)
        if (pointsTableQuickBody) {
            pointsTableQuickBody.innerHTML = '';
            currentPatrolPoints.forEach(p => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td>
                        <input type="text" value="${p.name || ''}" onchange="updatePoint('${p.id}', 'name', this.value)" 
                            style="width:100%; min-width:80px; background:rgba(255,255,255,0.1); border:1px solid #444; border-radius:4px; color:white; padding:4px;">
                        <br>
                        <span style="font-size:0.7rem; color:#888;">X:${p.x.toFixed(1)} Y:${p.y.toFixed(1)}</span>
                    </td>
                    <td>
                        <textarea onchange="updatePoint('${p.id}', 'prompt', this.value)" 
                            style="width:100%; height:50px; background:rgba(255,255,255,0.1); border:1px solid #444; border-radius:4px; color:white; padding:4px; resize:vertical;"
                            placeholder="Prompt...">${p.prompt || ''}</textarea>
                    </td>
                    <td>
                        <button onclick="testPoint('${p.id}')" class="btn-secondary" style="padding:4px 8px; font-size:0.8rem;">Test</button>
                    </td>
                    <td>
                        <button onclick="deletePoint('${p.id}')" style="color:#ef5350; background:none; border:none; cursor:pointer;">🗑</button>
                    </td>
                `;
                pointsTableQuickBody.appendChild(tr);
            });
        }

        // --- NEW: Patrol View Simplified Table ---
        const patrolViewBody = document.querySelector('#patrol-view-points-table tbody');
        if (patrolViewBody) {
            patrolViewBody.innerHTML = '';
            currentPatrolPoints.forEach((p, index) => {
                const tr = document.createElement('tr');
                tr.innerHTML = `
                    <td style="display:flex; align-items:center; gap:5px;">
                         <div style="display:flex; flex-direction:column; gap:2px;">
                             <button onclick="movePoint(${index}, -1)" class="btn-sm" style="font-size:0.6rem; padding:0 4px; line-height:1;" ${index === 0 ? 'disabled' : ''}>▲</button>
                             <button onclick="movePoint(${index}, 1)" class="btn-sm" style="font-size:0.6rem; padding:0 4px; line-height:1;" ${index === currentPatrolPoints.length - 1 ? 'disabled' : ''}>▼</button>
                         </div>
                        <button onmousedown="setHighlight('${p.id}')" onmouseup="clearHighlight()" onmouseleave="clearHighlight()" 
                            class="btn-secondary" style="width:100%; text-align:left; font-size:0.9rem; margin:0;">
                            📍 ${p.name || 'Unnamed Point'}
                        </button>
                    </td>
                    <td style="text-align:center;">
                        <input type="checkbox" ${p.enabled !== false ? 'checked' : ''} onchange="updatePoint('${p.id}', 'enabled', this.checked)">
                    </td>
                `;
                patrolViewBody.appendChild(tr);
            });
        }
    }

    // --- MAP HIGHLIGHT ---
    let highlightedPoint = null;

    window.setHighlight = function (id) {
        const point = currentPatrolPoints.find(p => p.id === id);
        if (point) {
            highlightedPoint = point;
            draw();
        }
    }

    window.clearHighlight = function () {
        if (highlightedPoint) {
            highlightedPoint = null;
            draw();
        }
    }

    window.movePoint = async function (index, direction) {
        if (direction === -1 && index > 0) {
            // Swap with previous
            [currentPatrolPoints[index], currentPatrolPoints[index - 1]] = [currentPatrolPoints[index - 1], currentPatrolPoints[index]];
        } else if (direction === 1 && index < currentPatrolPoints.length - 1) {
            // Swap with next
            [currentPatrolPoints[index], currentPatrolPoints[index + 1]] = [currentPatrolPoints[index + 1], currentPatrolPoints[index]];
        } else {
            return;
        }

        // Save full list order
        // Note: The API currently supports updating single point or list? 
        // `updatePoint` updates single. `save_json` in `handle_points` handles post of single point.
        // We need an endpoint to save ALL points or loop update?
        // App.py `handle_points` POST appends or updates single.
        // We need to implement a 'save all points' or modify backend to accept list.
        // Or simply delete all and re-add? No that's risky.

        // Let's modify backend to accept a LIST of points to replace the file.
        // Currently `handle_points` POST expects a single point dict.
        // I should check `app.py`.

        // FOR NOW: I will just re-render and saving might fail if I don't update backend.
        // Let's try to update backend first or if I can't...
        // Actually, if I just re-render, it works in memory.
        // But refreshing page will lose order.

        // I will implement `saveAllPoints` in JS and modify `app.py`.
        // Let's first modify JS here assuming `saveAllPoints` exists.

        renderPointsTable();
        await saveAllPoints();
    }

    async function saveAllPoints() {
        await fetch('/api/points/reorder', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(currentPatrolPoints)
        });
    }

    // Test specific point prompt
    window.testPoint = async function (id) {
        const point = currentPatrolPoints.find(p => p.id === id);
        if (!point) return;

        // Auto-fill the input prompt
        const promptInput = document.getElementById('ai-test-prompt-input');
        if (promptInput) promptInput.value = point.prompt || '';

        // Update UI status
        const outputResult = document.getElementById('ai-output-result');
        if (outputResult) {
            outputResult.textContent = `Moving to point "${point.name}"...`;
            outputResult.style.color = "#26c6da";
        }

        // 1. Move to Point
        try {
            const moveRes = await fetch('/api/move', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ x: point.x, y: point.y, theta: point.theta })
            });

            if (!moveRes.ok) {
                throw new Error("Failed to move to point");
            }

        } catch (e) {
            if (outputResult) {
                outputResult.textContent = "Move Error: " + e.message;
                outputResult.style.color = "#ef5350";
            }
            return; // Stop if move failed
        }

        // 2. Run AI Test
        await testAI(point.prompt);
    }

    // Test AI Function
    async function testAI(overridePrompt = null) {
        // Fix: If called from event listener, first arg is Event object, not string.
        if (overridePrompt && typeof overridePrompt !== 'string') {
            overridePrompt = null;
        }

        const promptInput = document.getElementById('ai-test-prompt-input');
        const outputPrompt = document.getElementById('ai-output-prompt');
        const outputResult = document.getElementById('ai-output-result');

        // Determine prompt
        let promptToSend = overridePrompt;
        if (promptToSend === null && promptInput) {
            promptToSend = promptInput.value;
        }
        if (!promptToSend) promptToSend = "";

        // UI Loading State
        if (outputPrompt) outputPrompt.textContent = promptToSend || "(Default)";
        if (outputResult) {
            outputResult.innerHTML = '<span style="color:#26c6da;">Analysing...</span>';
        }

        try {
            const res = await fetch('/api/test_ai', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt: promptToSend })
            });

            const data = await res.json();

            if (data.error) {
                if (outputResult) {
                    outputResult.innerHTML = `<div class="ai-result-row">
                        <div class="status-indicator ng">!</div>
                        <div class="status-text" style="color:#ef5350;">Error: ${data.error}</div>
                    </div>`;
                }
            } else {
                if (outputPrompt) outputPrompt.textContent = data.prompt;
                if (outputResult) {
                    // Expect data.result to be {is_NG: ..., Description: ...}
                    // But if old format or string, handle gracefully
                    let isExampleDict = false;
                    let isNG = false;
                    let desc = "";

                    if (typeof data.result === 'object' && data.result !== null) {
                        isExampleDict = true;
                        isNG = data.result.is_NG;
                        desc = data.result.Description;
                    } else {
                        // Fallback string
                        desc = String(data.result);
                        // Simple heuristic for demo if structured parsing fails on backend (shouldn't happen with updated backend)
                        isNG = desc.toLowerCase().includes("ng");
                    }

                    const statusClass = isNG ? 'ng' : 'ok';
                    const statusLabel = isNG ? 'NG' : 'OK';

                    outputResult.innerHTML = `
                    <div class="ai-result-row">
                        <div class="status-indicator ${statusClass}">${statusLabel}</div>
                        <div class="status-text">${desc || (isNG ? "Anomaly Detected" : "Normal")}</div>
                    </div>`;
                }
            }
        } catch (e) {
            if (outputResult) {
                outputResult.innerHTML = `<span style="color:#ef5350;">Network Error: ${e}</span>`;
            }
        }
    }

    async function addCurrentPoint() {
        const name = `Point ${currentPatrolPoints.length + 1}`;
        const point = {
            name: name,
            x: robotPose.x,
            y: robotPose.y,
            theta: robotPose.theta,
            prompt: 'Is this normal?',
            enabled: true
        };

        await fetch('/api/points', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(point)
        });
        loadPoints();
    }

    window.updatePoint = async function (id, key, value) {
        const point = currentPatrolPoints.find(p => p.id === id);
        if (!point) return;
        point[key] = value;
        await fetch('/api/points', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(point)
        });
        // loadPoints(); // No need to reload entire list, just update local?
    };

    window.deletePoint = async function (id) {
        // Removed confirm for smoother UX as requested
        // if (!confirm('Delete point?')) return;
        await fetch(`/api/points?id=${id}`, { method: 'DELETE' });
        loadPoints();
    };

    async function startPatrol() {
        const res = await fetch('/api/patrol/start', { method: 'POST' });
        if (!res.ok) {
            const err = await res.json();
            alert(err.error);
        }
    }

    async function stopPatrol() {
        await fetch('/api/patrol/stop', { method: 'POST' });
    }

    // Manual Control
    window.manualControl = async function (action) {
        try {
            await fetch('/api/manual_control', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ action: action })
            });
        } catch (e) {
            console.error("Manual Control Failed", e);
        }
    }

    function startPatrolPolling() {
        setInterval(async () => {
            const res = await fetch('/api/patrol/status');
            const data = await res.json();

            if (patrolStatusDisplay) {
                patrolStatusDisplay.textContent = `Status: ${data.status}`;
            }

            if (data.is_patrolling) {
                btnStartPatrol.disabled = true;
                btnStopPatrol.disabled = false;
            } else {
                btnStartPatrol.disabled = false;
                btnStopPatrol.disabled = true;
            }

            // Also reload results periodically (simple polling)
            loadResults();
        }, 1000);
    }

    // Helper to parse AI result
    function parseAIResponse(responseStr) {
        let isNG = false;
        let desc = responseStr;

        try {
            // Try valid JSON first
            const data = JSON.parse(responseStr);
            if (data && typeof data === 'object') {
                if (data.is_NG !== undefined) {
                    isNG = data.is_NG;
                    desc = data.Description;
                }
            }
        } catch (e) {
            // Fallback/Legacy string format logic
            if (typeof responseStr === 'string') {
                isNG = responseStr.toLowerCase().includes("ng");
            }
        }
        return { isNG, desc };
    }

    function renderAIResultHTML(responseStr) {
        const { isNG, desc } = parseAIResponse(responseStr);
        const statusClass = isNG ? 'ng' : 'ok';
        const statusLabel = isNG ? 'NG' : 'OK';

        return `
            <div class="ai-result-row" style="margin-top:5px;">
                <div class="status-indicator ${statusClass}">${statusLabel}</div>
                <div class="status-text">${desc || (isNG ? "Anomaly Detected" : "Normal")}</div>
            </div>
        `;
    }

    async function loadResults() {
        // if (document.getElementById('view-patrol').style.display === 'none') return; 
        // Allow background update or ensure dashboard is up to date when switching?
        // Let's keep the check but make sure we update if active.

        const res = await fetch('/api/patrol/results'); // Changed to match standard API
        const results = await res.json();

        // Update Log List
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
            // Show newest first
            results.slice().slice(-10).reverse().forEach(r => { // Show last 10 reversed
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.background = 'rgba(255,255,255,0.05)';
                card.style.padding = '8px';
                card.style.borderRadius = '4px';

                const resultHTML = renderAIResultHTML(r.result);

                card.innerHTML = `
                     <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                         <span style="color:#26c6da; font-weight:bold;">${r.point_name}</span>
                         <span style="font-size:0.75rem; color:#888;">${r.timestamp}</span>
                     </div>
                     ${resultHTML}
                 `;
                resultsContainer.appendChild(card);
            });
        }

        // Update Latest Result Dashboard Widget (Multiple locations)
        const latestBoxes = document.querySelectorAll('.patrol-latest-result-display, #patrol-latest-result');
        latestBoxes.forEach(latestBox => {
            if (results.length > 0) {
                const newest = results[results.length - 1];
                const resultHTML = renderAIResultHTML(newest.result);

                latestBox.innerHTML = `
                    <div style="font-weight:bold; color:#26c6da; margin-bottom:4px;">
                        ${newest.point_name} 
                        <span style="font-weight:normal; color:#888; font-size:0.8rem; float:right;">(${newest.timestamp})</span>
                    </div>
                    ${resultHTML}
                `;
            } else {
                latestBox.textContent = "No analysis data yet.";
                latestBox.style.color = "#888";
                latestBox.style.display = "flex";
                latestBox.style.alignItems = "center";
                latestBox.style.justifyContent = "center";
            }
        });
    }

    // --- HISTORY LOGIC ---

    async function loadHistory() {
        const listContainer = document.getElementById('history-list');
        if (!listContainer) return;

        listContainer.innerHTML = '<div style="color:#888; text-align:center;">Loading history...</div>';

        try {
            const res = await fetch('/api/history');
            const runs = await res.json();

            listContainer.innerHTML = '';

            if (runs.length === 0) {
                listContainer.innerHTML = '<div style="color:#888; text-align:center;">No patrol history found.</div>';
                return;
            }

            runs.forEach(run => {
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.background = 'rgba(255,255,255,0.08)';
                card.style.padding = '15px';
                card.style.borderRadius = '8px';
                card.style.cursor = 'pointer';
                card.style.border = '1px solid rgba(255,255,255,0.1)';
                card.style.transition = 'background 0.2s';

                card.onmouseover = () => card.style.background = 'rgba(255,255,255,0.15)';
                card.onmouseout = () => card.style.background = 'rgba(255,255,255,0.08)';
                card.onclick = () => viewHistoryDetail(run.id);

                const statusColor = run.status === 'Completed' ? '#00e676' : (run.status === 'Running' ? '#29b6f6' : '#ef5350');

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-weight:bold; font-size:1.1rem; color:#fff;">Patrol Run #${run.id}</span>
                        <span style="font-size:0.8rem; background:${statusColor}; color:#000; padding:2px 8px; border-radius:4px; font-weight:bold;">${run.status}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.9rem; color:#aaa;">
                        <span>Started: ${run.start_time}</span>
                        <span>Tokens: ${run.total_tokens || 0}</span>
                    </div>
                    <!-- <span>Robot: ${run.robot_serial || 'N/A'}</span> -->
                    ${run.report_content ? `<div style="margin-top:10px; color:#ddd; font-size:0.9rem; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${run.report_content}</div>` : ''}
                `;
                listContainer.appendChild(card);
            });

        } catch (e) {
            listContainer.innerHTML = `<div style="color:#ef5350; text-align:center;">Error loading history: ${e}</div>`;
        }
    }

    window.viewHistoryDetail = async function (runId) {
        const modal = document.getElementById('history-modal');
        const contentDiv = document.getElementById('modal-report-content');
        const listDiv = document.getElementById('modal-inspections-list');
        const title = document.getElementById('modal-title');

        if (!modal) return;

        modal.style.display = 'flex';
        contentDiv.textContent = 'Loading details...';
        listDiv.innerHTML = '';
        title.textContent = `Patrol Report #${runId}`;

        try {
            const res = await fetch(`/api/history/${runId}`);
            if (!res.ok) throw new Error("Failed to load details");

            const data = await res.json();
            const { run, inspections } = data;

            // Populate Report
            contentDiv.textContent = run.report_content || "No generated report available.";

            // Populate Inspections
            listDiv.innerHTML = '';
            if (inspections.length === 0) {
                listDiv.innerHTML = '<div style="color:#888;">No inspections recorded for this run.</div>';
            } else {
                inspections.forEach(ins => {
                    const item = document.createElement('div');
                    item.style.background = 'rgba(0,0,0,0.3)';
                    item.style.padding = '10px';
                    item.style.borderRadius = '6px';
                    item.style.display = 'flex';
                    item.style.gap = '15px';
                    item.style.alignItems = 'flex-start';

                    // Image
                    let imgHtml = '';
                    if (ins.image_path) {
                        imgHtml = `<img src="/api/images/${ins.image_path}" style="width:120px; height:auto; border-radius:4px; border:1px solid #555;">`;
                    }

                    const resultHTML = renderAIResultHTML(ins.ai_response);

                    item.innerHTML = `
                        ${imgHtml}
                        <div style="flex:1;">
                            <div style="font-weight:bold; color:#26c6da; margin-bottom:4px;">${ins.point_name}</div>
                            <div style="font-size:0.8rem; color:#888; margin-bottom:6px;">${ins.timestamp}</div>
                            <div style="background:rgba(255,255,255,0.05); padding:6px; border-radius:4px; font-size:0.9rem;">
                                <div style="color:#aaa; font-style:italic; margin-bottom:4px;">Q: ${ins.prompt}</div>
                                ${resultHTML}
                            </div>
                        </div>
                    `;
                    listDiv.appendChild(item);
                });
            }

        } catch (e) {
            contentDiv.textContent = `Error: ${e}`;
        }
    }

    window.closeHistoryModal = function () {
        const modal = document.getElementById('history-modal');
        if (modal) modal.style.display = 'none';
    }

    // Close modal when clicking outside
    const modal = document.getElementById('history-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) window.closeHistoryModal();
        });
    }

    // --- STATS LOGIC ---
    let tokenChart = null;

    async function loadStats() {
        // Initialize dates if empty
        const startInput = document.getElementById('stats-start-date');
        const endInput = document.getElementById('stats-end-date');

        if (!startInput.value) {
            const end = new Date();
            const start = new Date();
            start.setMonth(start.getMonth() - 1); // Last month

            // Format to YYYY-MM-DD for input value
            const formatDate = (date) => {
                const y = date.getFullYear();
                const m = String(date.getMonth() + 1).padStart(2, '0');
                const d = String(date.getDate()).padStart(2, '0');
                return `${y}-${m}-${d}`;
            };

            endInput.value = formatDate(end);
            startInput.value = formatDate(start);
        }

        // Fetch Data
        try {
            const res = await fetch('/api/stats/token_usage');
            const data = await res.json();

            // Parse dates
            const startDate = new Date(startInput.value);
            const endDate = new Date(endInput.value);
            // End date should be inclusive, set to end of day
            const endDateInclusive = new Date(endDate);
            endDateInclusive.setHours(23, 59, 59, 999);

            // Create a map of existing data
            const dataMap = {};
            data.forEach(d => {
                dataMap[d.date] = d.total;
            });

            // Generate full date range with zero filling
            const filledData = [];
            let currentDate = new Date(startDate);

            while (currentDate <= endDateInclusive) {
                const y = currentDate.getFullYear();
                const m = String(currentDate.getMonth() + 1).padStart(2, '0');
                const d = String(currentDate.getDate()).padStart(2, '0');
                const dateStr = `${y}-${m}-${d}`;

                filledData.push({
                    date: dateStr,
                    total: dataMap[dateStr] || 0
                });

                currentDate.setDate(currentDate.getDate() + 1);
            }

            renderChart(filledData);
        } catch (e) {
            console.error("Failed to load stats:", e);
        }
    }

    function renderChart(data) {
        const ctx = document.getElementById('tokenUsageChart').getContext('2d');

        if (tokenChart) {
            tokenChart.destroy();
        }

        const labels = data.map(d => d.date);
        const values = data.map(d => d.total);

        tokenChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Total Token Usage',
                    data: values,
                    borderColor: '#26c6da',
                    backgroundColor: 'rgba(38, 198, 218, 0.2)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.3
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: {
                        ticks: { color: '#aaa' },
                        grid: { color: '#333' }
                    },
                    y: {
                        ticks: { color: '#aaa' },
                        grid: { color: '#333' },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        labels: { color: '#fff' }
                    }
                }
            }
        });
    }

    // Date change listeners
    if (document.getElementById('stats-start-date')) {
        document.getElementById('stats-start-date').addEventListener('change', loadStats);
        document.getElementById('stats-end-date').addEventListener('change', loadStats);
    }

    // Default
    window.switchTab('control');

});
