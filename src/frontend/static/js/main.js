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

    // Get locations from robot button
    const btnGetRobotLocations = document.getElementById('btn-get-robot-locations');
    if (btnGetRobotLocations) {
        btnGetRobotLocations.addEventListener('click', getLocationsFromRobot);
    }

    async function getLocationsFromRobot() {
        const btn = document.getElementById('btn-get-robot-locations');
        const originalText = btn.innerHTML;

        btn.disabled = true;
        btn.innerHTML = '<span style="font-size: 12px;">⏳</span> Loading...';

        try {
            const res = await fetch('/api/points/from_robot');
            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || 'Failed to fetch locations');
            }

            // Build result message
            let message = '';
            if (data.added && data.added.length > 0) {
                message += `Added ${data.added.length} location(s):\n• ${data.added.join('\n• ')}\n\n`;
            }
            if (data.skipped && data.skipped.length > 0) {
                message += `Skipped ${data.skipped.length} duplicate(s):\n• ${data.skipped.join('\n• ')}`;
            }
            if (data.added.length === 0 && data.skipped.length === 0) {
                message = 'No locations found on robot.';
            }

            alert(message || 'Operation completed.');

            // Reload points to reflect changes
            if (data.added && data.added.length > 0) {
                loadPoints();
            }

        } catch (e) {
            alert('Error: ' + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    // Event listeners for patrol/settings (functions defined later)
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
        if (tabName === 'beds' && btns[4]) btns[4].classList.add('active');
        if (tabName === 'settings' && btns[5]) btns[5].classList.add('active');

        // Load specific data
        if (tabName === 'history') loadHistory();
        if (tabName === 'stats') loadStats();
        if (tabName === 'settings') loadSettings();
        if (tabName === 'beds') loadBedsConfig();

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
            if (dest && mapContainer.parentNode !== dest) {
                // Append map at the end (after the analysis panel)
                dest.appendChild(mapContainer);
            }
            setTimeout(resizeCanvas, 50);
        }
    };

    // --- COLLAPSIBLE PANELS ---

    // Toggle Analysis History (merged into Latest AI Analysis panel)
    window.toggleAnalysisHistory = function () {
        const container = document.getElementById('patrol-history-container');
        const icon = document.getElementById('history-toggle-icon');
        if (container) {
            const isCollapsed = container.style.display === 'none';
            container.style.display = isCollapsed ? 'block' : 'none';
            if (icon) icon.textContent = isCollapsed ? '▲' : '▼';
        }
    };

    window.toggleHistoryLog = function () {
        const frame = document.getElementById('history-log-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.togglePatrolRoute = function () {
        const frame = document.getElementById('patrol-route-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.toggleSchedulePanel = function () {
        const frame = document.getElementById('schedule-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.toggleAITestPanel = function () {
        const frame = document.getElementById('ai-test-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.togglePatrolPointsPanel = function () {
        const frame = document.getElementById('patrol-points-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.toggleFrontCameraPanel = function () {
        const frame = document.getElementById('front-camera-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    window.toggleRobotVisionPanel = function () {
        const frame = document.getElementById('robot-vision-frame');
        if (frame) {
            frame.classList.toggle('collapsed');
        }
    };

    // --- SCHEDULED PATROL ---
    let scheduledPatrols = [];
    const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

    async function loadSchedule() {
        try {
            const res = await fetch('/api/patrol/schedule');
            scheduledPatrols = await res.json();
            renderScheduleList();
        } catch (e) {
            console.error("Failed to load schedule:", e);
        }
    }

    function renderScheduleList() {
        const container = document.getElementById('schedule-list');
        if (!container) return;

        if (scheduledPatrols.length === 0) {
            container.innerHTML = '<div style="color: var(--text-muted); font-size: 12px; text-align: center; padding: 12px;">No scheduled patrols</div>';
            return;
        }

        container.innerHTML = '';
        scheduledPatrols.forEach(schedule => {
            const item = document.createElement('div');
            item.className = 'schedule-item';
            item.style.cssText = 'display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: var(--slate-dark); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);';

            // Time display
            const timeSpan = document.createElement('span');
            timeSpan.style.cssText = 'font-family: var(--font-mono); font-size: 16px; font-weight: 600; color: var(--cyan-glow); min-width: 60px;';
            timeSpan.textContent = schedule.time;

            // Days display
            const daysSpan = document.createElement('span');
            daysSpan.style.cssText = 'flex: 1; font-size: 11px; color: var(--text-secondary);';
            const activeDays = (schedule.days || [0, 1, 2, 3, 4, 5, 6]).map(d => dayNames[d]).join(', ');
            daysSpan.textContent = schedule.days && schedule.days.length < 7 ? activeDays : 'Every day';

            // Toggle switch
            const toggleLabel = document.createElement('label');
            toggleLabel.style.cssText = 'display: flex; align-items: center; cursor: pointer;';
            const toggleCheckbox = document.createElement('input');
            toggleCheckbox.type = 'checkbox';
            toggleCheckbox.checked = schedule.enabled !== false;
            toggleCheckbox.style.cssText = 'width: 18px; height: 18px;';
            toggleCheckbox.onchange = () => toggleSchedule(schedule.id, toggleCheckbox.checked);
            toggleLabel.appendChild(toggleCheckbox);

            // Delete button
            const deleteBtn = document.createElement('button');
            deleteBtn.innerHTML = '✕';
            deleteBtn.style.cssText = 'background: none; border: none; color: var(--red-alert); cursor: pointer; font-size: 14px; padding: 4px 8px; opacity: 0.7;';
            deleteBtn.onmouseover = () => deleteBtn.style.opacity = '1';
            deleteBtn.onmouseout = () => deleteBtn.style.opacity = '0.7';
            deleteBtn.onclick = () => deleteSchedule(schedule.id);

            item.appendChild(timeSpan);
            item.appendChild(daysSpan);
            item.appendChild(toggleLabel);
            item.appendChild(deleteBtn);
            container.appendChild(item);
        });
    }

    async function addSchedule() {
        const timeInput = document.getElementById('schedule-time-input');
        if (!timeInput || !timeInput.value) {
            alert('Please select a time');
            return;
        }

        try {
            const res = await fetch('/api/patrol/schedule', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    time: timeInput.value,
                    enabled: true
                })
            });

            if (res.ok) {
                timeInput.value = '';
                loadSchedule();
            } else {
                const data = await res.json();
                alert('Failed to add schedule: ' + (data.error || 'Unknown error'));
            }
        } catch (e) {
            alert('Failed to add schedule: ' + e);
        }
    }

    async function toggleSchedule(id, enabled) {
        try {
            await fetch(`/api/patrol/schedule/${id}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ enabled })
            });
            loadSchedule();
        } catch (e) {
            console.error("Failed to toggle schedule:", e);
        }
    }

    async function deleteSchedule(id) {
        try {
            await fetch(`/api/patrol/schedule/${id}`, {
                method: 'DELETE'
            });
            loadSchedule();
        } catch (e) {
            console.error("Failed to delete schedule:", e);
        }
    }

    // Add schedule button listener
    const btnAddSchedule = document.getElementById('btn-add-schedule');
    if (btnAddSchedule) {
        btnAddSchedule.addEventListener('click', addSchedule);
    }

    // Calculate and display next scheduled patrol
    function updateNextPatrolDisplay() {
        const display = document.getElementById('next-patrol-display');
        if (!display) return;

        const enabledSchedules = scheduledPatrols.filter(s => s.enabled !== false);
        if (enabledSchedules.length === 0) {
            display.innerHTML = '';
            return;
        }

        const now = new Date();
        const currentDay = now.getDay(); // 0=Sunday, need to convert to 0=Monday
        const todayIndex = currentDay === 0 ? 6 : currentDay - 1;
        const currentMinutes = now.getHours() * 60 + now.getMinutes();

        let nextPatrol = null;
        let minMinutesAway = Infinity;

        enabledSchedules.forEach(schedule => {
            const [hours, mins] = schedule.time.split(':').map(Number);
            const scheduleMinutes = hours * 60 + mins;
            const scheduleDays = schedule.days || [0, 1, 2, 3, 4, 5, 6];

            // Check each day starting from today
            for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
                const checkDayIndex = (todayIndex + dayOffset) % 7;

                if (!scheduleDays.includes(checkDayIndex)) continue;

                let minutesAway;
                if (dayOffset === 0) {
                    // Today
                    if (scheduleMinutes > currentMinutes) {
                        minutesAway = scheduleMinutes - currentMinutes;
                    } else {
                        continue; // Already passed today
                    }
                } else {
                    // Future day
                    minutesAway = (dayOffset * 24 * 60) + scheduleMinutes - currentMinutes;
                }

                if (minutesAway < minMinutesAway) {
                    minMinutesAway = minutesAway;
                    nextPatrol = {
                        time: schedule.time,
                        dayOffset: dayOffset
                    };
                }
            }
        });

        if (nextPatrol) {
            let timeText;
            if (nextPatrol.dayOffset === 0) {
                timeText = `Today at ${nextPatrol.time}`;
            } else if (nextPatrol.dayOffset === 1) {
                timeText = `Tomorrow at ${nextPatrol.time}`;
            } else {
                const nextDate = new Date(now);
                nextDate.setDate(nextDate.getDate() + nextPatrol.dayOffset);
                const dayName = dayNames[(todayIndex + nextPatrol.dayOffset) % 7];
                timeText = `${dayName} at ${nextPatrol.time}`;
            }
            display.innerHTML = `<span style="color: var(--cyan-dim);">⏰</span> Next: <span style="color: var(--text-primary);">${timeText}</span>`;
        } else {
            display.innerHTML = '';
        }
    }

    // Update next patrol display when schedule changes
    const originalRenderScheduleList = renderScheduleList;
    renderScheduleList = function () {
        originalRenderScheduleList();
        updateNextPatrolDisplay();
    };

    // Load schedule on page load
    loadSchedule();

    // Update next patrol display every minute
    setInterval(updateNextPatrolDisplay, 60000);

    // renderPointsTable and testAI functions are defined later in the file

    // State
    let mapImage = new Image();
    let mapInfo = null;
    let robotPose = { x: 0, y: 0, theta: 0 };
    let isMapLoaded = false;
    let isDragging = false;
    let dragStart = null;
    let canvasScale = 1; // Track CSS scale for consistent icon sizing
    let dragCurrent = null;
    let currentPatrolPoints = [];
    let currentSettingsTimezone = 'UTC';
    let currentIdleStreamEnabled = true;

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
            console.log("Map image LOADED. Image size:", mapImage.width, "x", mapImage.height);
            if (mapInfo) {
                console.log("Map info:", {
                    resolution: mapInfo.resolution,
                    width: mapInfo.width,
                    height: mapInfo.height,
                    origin_x: mapInfo.origin_x,
                    origin_y: mapInfo.origin_y
                });
                if (mapImage.width !== mapInfo.width || mapImage.height !== mapInfo.height) {
                    console.warn("WARNING: Image dimensions don't match mapInfo!",
                        "Image:", mapImage.width, "x", mapImage.height,
                        "MapInfo:", mapInfo.width, "x", mapInfo.height);
                }
            }
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
        // Always update mapInfo to ensure sync with backend
        if (data.map_info) {
            mapInfo = data.map_info;
        }
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

        // 4. Track scale factor for consistent icon sizing
        canvasScale = finalWidth / canvas.width;

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

        // Scale-independent size (constant visual size regardless of map zoom)
        const visualSize = 24; // Desired visual size in screen pixels
        const size = canvasScale > 0 ? visualSize / canvasScale : visualSize;
        const lineWidth = canvasScale > 0 ? 2 / canvasScale : 2;

        // Draw arrow shape pointing right (front direction)
        ctx.beginPath();
        ctx.moveTo(size, 0);           // Front tip (arrow point)
        ctx.lineTo(-size * 0.5, size * 0.6);   // Back left
        ctx.lineTo(-size * 0.2, 0);    // Back center notch
        ctx.lineTo(-size * 0.5, -size * 0.6);  // Back right
        ctx.closePath();

        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = 'white';
        ctx.lineWidth = lineWidth;
        ctx.stroke();

        ctx.restore();
    }

    // Coordinate transformations - use actual image dimensions for accuracy
    // These functions convert between world coordinates (meters) and pixel coordinates
    function getMapHeight() {
        // Prefer actual image height, fall back to mapInfo
        if (isMapLoaded && mapImage.height > 0) return mapImage.height;
        if (mapInfo && mapInfo.height > 0) return mapInfo.height;
        return 0;
    }

    function worldToPixelX(x) {
        if (!mapInfo || mapInfo.resolution <= 0) return 0;
        return (x - mapInfo.origin_x) / mapInfo.resolution;
    }

    function worldToPixelY(y) {
        if (!mapInfo || mapInfo.resolution <= 0) return 0;
        const imgHeight = getMapHeight();
        if (imgHeight <= 0) return 0;
        return imgHeight - (y - mapInfo.origin_y) / mapInfo.resolution;
    }

    function pixelToWorldX(u) {
        if (!mapInfo || mapInfo.resolution <= 0) return 0;
        return u * mapInfo.resolution + mapInfo.origin_x;
    }

    function pixelToWorldY(v) {
        if (!mapInfo || mapInfo.resolution <= 0) return 0;
        const imgHeight = getMapHeight();
        if (imgHeight <= 0) return 0;
        return (imgHeight - v) * mapInfo.resolution + mapInfo.origin_y;
    }

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

        // Multiday Report Prompt
        const multidayPrompt = document.getElementById('setting-multiday-report-prompt');
        if (multidayPrompt) multidayPrompt.value = data.multiday_report_prompt || '';

        // Turbo Mode
        const turboCheckbox = document.getElementById('setting-turbo-mode');
        if (turboCheckbox) turboCheckbox.checked = data.turbo_mode === true;

        // Video & Stream Settings
        const videoCheckbox = document.getElementById('setting-enable-video');
        if (videoCheckbox) videoCheckbox.checked = data.enable_video_recording === true;

        const videoPrompt = document.getElementById('setting-video-prompt');
        if (videoPrompt) videoPrompt.value = data.video_prompt || '';

        const idleStreamCheckbox = document.getElementById('setting-enable-idle-stream');
        if (idleStreamCheckbox) {
            idleStreamCheckbox.checked = data.enable_idle_stream !== false; // Default true
            currentIdleStreamEnabled = idleStreamCheckbox.checked;
        }

        // Telegram Settings
        const telegramCheckbox = document.getElementById('setting-enable-telegram');
        if (telegramCheckbox) telegramCheckbox.checked = data.enable_telegram === true;

        const telegramBotToken = document.getElementById('setting-telegram-bot-token');
        if (telegramBotToken) telegramBotToken.value = data.telegram_bot_token || '';

        const telegramUserId = document.getElementById('setting-telegram-user-id');
        if (telegramUserId) telegramUserId.value = data.telegram_user_id || '';

        // Handle robot_ip if element exists (will be added to HTML next)
        const ipInput = document.getElementById('setting-robot-ip');
        if (ipInput) ipInput.value = data.robot_ip || '192.168.50.133:26400';

        // MQTT Settings
        const mqttCheckbox = document.getElementById('setting-mqtt-enabled');
        if (mqttCheckbox) mqttCheckbox.checked = data.mqtt_enabled === true;

        const mqttBroker = document.getElementById('setting-mqtt-broker');
        if (mqttBroker) mqttBroker.value = data.mqtt_broker || '';

        const mqttPort = document.getElementById('setting-mqtt-port');
        if (mqttPort) mqttPort.value = data.mqtt_port || '';

        const mqttTopic = document.getElementById('setting-mqtt-topic');
        if (mqttTopic) mqttTopic.value = data.mqtt_topic || '';

        const mqttShelfId = document.getElementById('setting-mqtt-shelf-id');
        if (mqttShelfId) mqttShelfId.value = data.mqtt_shelf_id || '';

        const patrolMode = document.getElementById('setting-patrol-mode');
        if (patrolMode) patrolMode.value = data.patrol_mode || 'visual';

        // Bio-Sensor Timing Settings
        const bioScanWaitTime = document.getElementById('setting-bio-scan-wait-time');
        if (bioScanWaitTime) bioScanWaitTime.value = data.bio_scan_wait_time || 10;

        const bioScanRetryCount = document.getElementById('setting-bio-scan-retry-count');
        if (bioScanRetryCount) bioScanRetryCount.value = data.bio_scan_retry_count || 6;

        const bioScanInitialWait = document.getElementById('setting-bio-scan-initial-wait');
        if (bioScanInitialWait) bioScanInitialWait.value = data.bio_scan_initial_wait || 5;

        const bioScanValidStatus = document.getElementById('setting-bio-scan-valid-status');
        if (bioScanValidStatus) bioScanValidStatus.value = data.bio_scan_valid_status || 4;

        // Patrol Timing Settings
        const scheduleCheckInterval = document.getElementById('setting-schedule-check-interval');
        if (scheduleCheckInterval) scheduleCheckInterval.value = data.schedule_check_interval || 30;

        const inspectionDelay = document.getElementById('setting-inspection-delay');
        if (inspectionDelay) inspectionDelay.value = data.inspection_delay || 2;

        // Robot Retry Settings
        const robotMaxRetries = document.getElementById('setting-robot-max-retries');
        if (robotMaxRetries) robotMaxRetries.value = data.robot_max_retries || 3;

        const robotRetryBaseDelay = document.getElementById('setting-robot-retry-base-delay');
        if (robotRetryBaseDelay) robotRetryBaseDelay.value = data.robot_retry_base_delay || 2.0;

        const robotRetryMaxDelay = document.getElementById('setting-robot-retry-max-delay');
        if (robotRetryMaxDelay) robotRetryMaxDelay.value = data.robot_retry_max_delay || 10.0;
    }

    async function saveSettings() {
        const settings = {
            gemini_api_key: document.getElementById('setting-api-key').value,
            gemini_model: document.getElementById('setting-model').value,
            timezone: document.getElementById('setting-timezone').value,
            system_prompt: document.getElementById('setting-role').value,
            report_prompt: document.getElementById('setting-report-prompt').value,
            multiday_report_prompt: document.getElementById('setting-multiday-report-prompt')?.value || '',
            turbo_mode: document.getElementById('setting-turbo-mode').checked,
            enable_video_recording: document.getElementById('setting-enable-video').checked,
            video_prompt: document.getElementById('setting-video-prompt').value,
            enable_idle_stream: document.getElementById('setting-enable-idle-stream').checked,
            enable_idle_stream: document.getElementById('setting-enable-idle-stream').checked,
            enable_telegram: document.getElementById('setting-enable-telegram').checked,
            telegram_bot_token: document.getElementById('setting-telegram-bot-token').value,
            telegram_user_id: document.getElementById('setting-telegram-user-id').value,
            robot_ip: document.getElementById('setting-robot-ip') ? document.getElementById('setting-robot-ip').value : '192.168.50.133:26400',
            mqtt_enabled: document.getElementById('setting-mqtt-enabled').checked,
            mqtt_broker: document.getElementById('setting-mqtt-broker').value,
            mqtt_port: parseInt(document.getElementById('setting-mqtt-port').value) || 1883,
            mqtt_topic: document.getElementById('setting-mqtt-topic').value,
            mqtt_shelf_id: document.getElementById('setting-mqtt-shelf-id').value,
            patrol_mode: document.getElementById('setting-patrol-mode').value,
            // Bio-Sensor Timing Settings
            bio_scan_wait_time: parseInt(document.getElementById('setting-bio-scan-wait-time')?.value) || 10,
            bio_scan_retry_count: parseInt(document.getElementById('setting-bio-scan-retry-count')?.value) || 6,
            bio_scan_initial_wait: parseInt(document.getElementById('setting-bio-scan-initial-wait')?.value) || 5,
            bio_scan_valid_status: parseInt(document.getElementById('setting-bio-scan-valid-status')?.value) || 4,
            // Patrol Timing Settings
            schedule_check_interval: parseInt(document.getElementById('setting-schedule-check-interval')?.value) || 30,
            inspection_delay: parseInt(document.getElementById('setting-inspection-delay')?.value) || 2,
            // Robot Retry Settings
            robot_max_retries: parseInt(document.getElementById('setting-robot-max-retries')?.value) || 3,
            robot_retry_base_delay: parseFloat(document.getElementById('setting-robot-retry-base-delay')?.value) || 2.0,
            robot_retry_max_delay: parseFloat(document.getElementById('setting-robot-retry-max-delay')?.value) || 10.0
        };
        try {
            const res = await fetch('/api/settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(settings)
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                alert('Failed to save settings: ' + (data.error || 'Unknown error'));
                return;
            }
            currentSettingsTimezone = settings.timezone;
            currentIdleStreamEnabled = settings.enable_idle_stream;
            alert('Settings Saved! (Robot connection may reload)');
        } catch (e) {
            alert('Failed to save settings: ' + e.message);
        }
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
                    <td><input type="text" value="${p.name || ''}" onchange="updatePoint('${p.id}', 'name', this.value)" style="width:100px; background:rgba(0,0,0,0.03); border:1px solid #ccc; color:#333;"></td>
                    <td style="font-family:monospace; font-size:0.8rem; color:#333;">X:${p.x.toFixed(2)} Y:${p.y.toFixed(2)} T:${p.theta.toFixed(2)}</td>
                    <td><input type="text" value="${p.prompt || ''}" onchange="updatePoint('${p.id}', 'prompt', this.value)" style="width:200px; background:rgba(0,0,0,0.03); border:1px solid #ccc; color:#333;"></td>
                    <td><input type="checkbox" ${p.enabled !== false ? 'checked' : ''} onchange="updatePoint('${p.id}', 'enabled', this.checked)"></td>
                    <td><button onclick="deletePoint('${p.id}')" style="color:#dc3545; background:none; border:none; cursor:pointer;">del</button></td>
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
                            style="width:100%; min-width:80px; background:rgba(0,0,0,0.03); border:1px solid #ccc; border-radius:4px; color:#333; padding:4px;">
                        <br>
                        <span style="font-size:0.7rem; color:#555;">X:${p.x.toFixed(1)} Y:${p.y.toFixed(1)}</span>
                    </td>
                    <td>
                        <textarea onchange="updatePoint('${p.id}', 'prompt', this.value)"
                            style="width:100%; height:50px; background:rgba(0,0,0,0.03); border:1px solid #ccc; border-radius:4px; color:#333; padding:4px; resize:vertical;"
                            placeholder="Prompt...">${p.prompt || ''}</textarea>
                    </td>
                    <td>
                        <button onclick="testPoint('${p.id}')" class="btn-secondary" style="padding:4px 8px; font-size:0.8rem;">Test</button>
                    </td>
                    <td>
                        <button onclick="deletePoint('${p.id}')" style="color:#dc3545; background:none; border:none; cursor:pointer;">🗑</button>
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
                             <button onclick="movePoint(${index}, -1)" class="btn-sm" style="font-size:0.7rem; padding:0 4px; line-height:1;" ${index === 0 ? 'disabled' : ''}>▲</button>
                             <button onclick="movePoint(${index}, 1)" class="btn-sm" style="font-size:0.7rem; padding:0 4px; line-height:1;" ${index === currentPatrolPoints.length - 1 ? 'disabled' : ''}>▼</button>
                         </div>
                        <button onmousedown="setHighlight('${p.id}')" onmouseup="clearHighlight()" onmouseleave="clearHighlight()" 
                            class="btn-secondary" style="width:100%; text-align:left; font-size:0.85rem; margin:0;">
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
            outputResult.style.color = "#006b56";
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
                outputResult.style.color = "#dc3545";
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
            outputResult.innerHTML = '<span style="color:#006b56;">Analysing...</span>';
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
                        <div class="status-text" style="color:#dc3545;">Error: ${data.error}</div>
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
                outputResult.innerHTML = `<span style="color:#dc3545;">Network Error: ${e}</span>`;
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
        try {
            const res = await fetch('/api/points', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(point)
            });
            const data = await res.json();
            if (!res.ok || data.error) {
                alert('Failed to save point: ' + (data.error || 'Unknown error'));
                loadPoints(); // Reload to restore original values
            }
        } catch (e) {
            alert('Failed to save point: ' + e.message);
            loadPoints(); // Reload to restore original values
        }
    };

    window.deletePoint = async function (id) {
        // Removed confirm for smoother UX as requested
        // if (!confirm('Delete point?')) return;
        try {
            const res = await fetch(`/api/points?id=${id}`, { method: 'DELETE' });
            const data = await res.json();
            if (!res.ok || data.error) {
                alert('Failed to delete point: ' + (data.error || 'Unknown error'));
                return;
            }
        } catch (e) {
            alert('Failed to delete point: ' + e.message);
            return;
        }
        loadPoints();
    };

    async function startPatrol() {
        // Clear history on patrol start
        const resultsContainer = document.getElementById('results-container');
        if (resultsContainer) resultsContainer.innerHTML = '';

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

            // Handle Camera Stream Logic
            const shouldStream = data.is_patrolling || currentIdleStreamEnabled;
            updateCameraStream(shouldStream);

            // Also reload results periodically (simple polling)
            loadResults();
        }, 1000);
    }

    let isStreamActive = true;
    function updateCameraStream(shouldStream) {
        if (shouldStream === isStreamActive) return;
        isStreamActive = shouldStream;

        const cams = [
            document.querySelector('#front-camera-content img'),
            document.querySelector('#robot-vision-content img')
        ];

        cams.forEach(img => {
            if (img) {
                if (shouldStream) {
                    img.src = '/api/camera/front?t=' + new Date().getTime(); // timestamp to break cache check
                    img.style.opacity = 1;
                } else {
                    img.src = ''; // Stop stream
                    img.alt = 'Stream Paused (Idle Mode)';
                    // We can also replace with a placeholder image or overlay
                    img.style.opacity = 0.5;
                }
            }
        });
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
                card.style.background = 'rgba(0,0,0,0.03)';
                card.style.padding = '8px';
                card.style.borderRadius = '4px';

                const resultHTML = renderAIResultHTML(r.result);

                card.innerHTML = `
                     <div style="display:flex; justify-content:space-between; margin-bottom:4px;">
                         <span style="color:#006b56; font-weight:bold;">${r.point_name}</span>
                         <span style="font-size:0.7rem; color:#555;">${r.timestamp}</span>
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
                    <div style="font-weight:bold; color:#006b56; margin-bottom:4px;">
                        ${newest.point_name}
                        <span style="font-weight:normal; color:#555; font-size:0.8rem; float:right;">(${newest.timestamp})</span>
                    </div>
                    ${resultHTML}
                `;
            } else {
                latestBox.textContent = "No analysis data yet.";
                latestBox.style.color = "#666";
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

        listContainer.innerHTML = '<div style="color:#666; text-align:center;">Loading history...</div>';

        try {
            const res = await fetch('/api/history');
            const runs = await res.json();

            listContainer.innerHTML = '';

            if (runs.length === 0) {
                listContainer.innerHTML = '<div style="color:#666; text-align:center;">No patrol history found.</div>';
                return;
            }

            runs.forEach(run => {
                const card = document.createElement('div');
                card.className = 'result-card';
                card.style.background = 'rgba(0,0,0,0.03)';
                card.style.padding = '15px';
                card.style.borderRadius = '8px';
                card.style.cursor = 'pointer';
                card.style.border = '1px solid rgba(0,0,0,0.08)';
                card.style.transition = 'background 0.2s';

                card.onmouseover = () => card.style.background = 'rgba(0,0,0,0.06)';
                card.onmouseout = () => card.style.background = 'rgba(0,0,0,0.03)';
                card.onclick = () => viewHistoryDetail(run.id);

                const statusColor = run.status === 'Completed' ? '#28a745' : (run.status === 'Running' ? '#007bff' : '#dc3545');

                card.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                        <span style="font-weight:bold; font-size:1.1rem; color:#1a1a1a;">Patrol Run #${run.id}</span>
                        <span style="font-size:0.8rem; background:${statusColor}; color:#fff; padding:2px 8px; border-radius:4px; font-weight:bold;">${run.status}</span>
                    </div>
                    <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#555;">
                        <span>Started: ${run.start_time}</span>
                        <span>Tokens: ${run.total_tokens || 0}</span>
                    </div>
                    <!-- <span>Robot: ${run.robot_serial || 'N/A'}</span> -->
                    ${run.report_content ? `<div style="margin-top:10px; color:#333; font-size:0.85rem; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${run.report_content}</div>` : ''}
                `;
                listContainer.appendChild(card);
            });

        } catch (e) {
            listContainer.innerHTML = `<div style="color:#dc3545; text-align:center;">Error loading history: ${e}</div>`;
        }
    }

    window.viewHistoryDetail = async function (runId) {
        const modal = document.getElementById('history-modal');
        const contentDiv = document.getElementById('modal-report-content');
        const listDiv = document.getElementById('modal-inspections-list');
        const title = document.getElementById('modal-title');

        if (!modal) return;

        // Store current run ID for PDF generation
        window.currentReportRunId = runId;

        modal.style.display = 'flex';
        contentDiv.textContent = 'Loading details...';
        listDiv.innerHTML = '';
        title.textContent = `Patrol Report #${runId}`;

        try {
            const res = await fetch(`/api/history/${runId}`);
            if (!res.ok) throw new Error("Failed to load details");

            const data = await res.json();
            const { run, inspections } = data;

            // Store data for PDF generation
            window.currentReportData = { run, inspections };

            // Populate Report with Markdown rendering
            if (run.report_content) {
                contentDiv.innerHTML = marked.parse(run.report_content);
            } else {
                contentDiv.textContent = "No generated report available.";
            }

            // Populate Inspections
            listDiv.innerHTML = '';
            if (inspections.length === 0) {
                listDiv.innerHTML = '<div style="color:#666;">No inspections recorded for this run.</div>';
            } else {
                inspections.forEach(ins => {
                    const item = document.createElement('div');
                    item.style.background = 'rgba(0,0,0,0.04)';
                    item.style.padding = '10px';
                    item.style.borderRadius = '6px';
                    item.style.display = 'flex';
                    item.style.gap = '15px';
                    item.style.alignItems = 'flex-start';

                    // Image
                    let imgHtml = '';
                    if (ins.image_path) {
                        imgHtml = `<img src="/api/images/${ins.image_path}" style="width:120px; height:auto; border-radius:4px; border:1px solid #ccc;">`;
                    }

                    const resultHTML = renderAIResultHTML(ins.ai_response);

                    item.innerHTML = `
                        ${imgHtml}
                        <div style="flex:1;">
                            <div style="font-weight:bold; color:#006b56; margin-bottom:4px;">${ins.point_name}</div>
                            <div style="font-size:0.8rem; color:#555; margin-bottom:6px;">${ins.timestamp}</div>
                            <div style="background:rgba(0,0,0,0.03); padding:6px; border-radius:4px; font-size:0.85rem;">
                                <div style="color:#555; font-style:italic; margin-bottom:4px;">Q: ${ins.prompt}</div>
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

    // Save PDF functionality - Server-side generation
    window.currentReportRunId = null;
    window.currentReportData = null;  // Store full report data for reference

    window.saveReportAsPDF = function () {
        const runId = window.currentReportRunId;
        if (!runId) {
            alert('No report selected. Please reopen the report.');
            return;
        }
        // Trigger download from server-side PDF endpoint
        window.location.href = `/api/report/${runId}/pdf`;
    }

    // Add event listener for PDF button
    const btnSavePdf = document.getElementById('btn-save-pdf');
    if (btnSavePdf) {
        btnSavePdf.addEventListener('click', saveReportAsPDF);
    }

    // Close modal when clicking outside
    const modal = document.getElementById('history-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) window.closeHistoryModal();
        });
    }


    // --- REPORT GENERATION LOGIC ---
    window.closeGeneratedReport = function () {
        const container = document.getElementById('generated-report-container');
        if (container) container.style.display = 'none';
    }

    // Store generated report data for PDF export
    window.generatedReportData = null;

    window.saveGeneratedReportAsPDF = function () {
        const startDate = document.getElementById('history-start-date')?.value;
        const endDate = document.getElementById('history-end-date')?.value;

        if (!startDate || !endDate) {
            alert('No date range selected.');
            return;
        }

        // Trigger download from server-side PDF endpoint
        window.location.href = `/api/reports/generate/pdf?start_date=${startDate}&end_date=${endDate}`;
    }

    async function generateReport() {
        const startInput = document.getElementById('history-start-date');
        const endInput = document.getElementById('history-end-date');
        const btn = document.getElementById('btn-generate-report');
        const container = document.getElementById('generated-report-container');
        const contentDiv = document.getElementById('generated-report-content');

        if (!startInput.value || !endInput.value) {
            alert("Please select a date range.");
            return;
        }

        const originalText = btn.innerHTML;
        btn.disabled = true;
        btn.innerHTML = '<span class="icon">⏳</span> Generating...';

        if (container) container.style.display = 'none';

        try {
            const res = await fetch('/api/reports/generate', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_date: startInput.value,
                    end_date: endInput.value
                })
            });

            const data = await res.json();

            if (!res.ok) {
                throw new Error(data.error || "Failed to generate report");
            }

            // Display Report
            if (container) {
                container.style.display = 'block';
                contentDiv.innerHTML = marked.parse(data.report);

                // Update stats
                document.getElementById('report-prompt-tokens').innerText = data.usage.prompt_token_count || 0;
                document.getElementById('report-completion-tokens').innerText = data.usage.candidates_token_count || 0;
                document.getElementById('report-total-tokens').innerText = data.usage.total_token_count || 0;
            }

            // Refresh token stats chart if visible? maybe not needed immediately.

        } catch (e) {
            alert("Error: " + e.message);
        } finally {
            btn.disabled = false;
            btn.innerHTML = originalText;
        }
    }

    const btnGenerateReport = document.getElementById('btn-generate-report');
    if (btnGenerateReport) {
        btnGenerateReport.addEventListener('click', generateReport);

        // Initialize dates
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 7); // Last 7 days

        const formatDate = (date) => {
            const y = date.getFullYear();
            const m = String(date.getMonth() + 1).padStart(2, '0');
            const d = String(date.getDate()).padStart(2, '0');
            return `${y}-${m}-${d}`;
        };

        const startInput = document.getElementById('history-start-date');
        const endInput = document.getElementById('history-end-date');

        if (startInput && endInput) {
            startInput.value = formatDate(start);
            endInput.value = formatDate(end);
        }
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
                dataMap[d.date] = { input: d.input || 0, output: d.output || 0, total: d.total || 0 };
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
                    input: dataMap[dateStr]?.input || 0,
                    output: dataMap[dateStr]?.output || 0,
                    total: dataMap[dateStr]?.total || 0
                });

                currentDate.setDate(currentDate.getDate() + 1);
            }

            renderChart(filledData);
            updateStatsSummary(filledData);
        } catch (e) {
            console.error("Failed to load stats:", e);
        }
    }

    function updateStatsSummary(data) {
        const totalInput = data.reduce((sum, d) => sum + d.input, 0);
        const totalOutput = data.reduce((sum, d) => sum + d.output, 0);
        const totalAll = data.reduce((sum, d) => sum + d.total, 0);

        const summaryEl = document.getElementById('stats-summary');
        if (summaryEl) {
            summaryEl.innerHTML = `
                <div class="stat-item">
                    <span class="stat-label">Input Tokens</span>
                    <span class="stat-value" style="color: #28a745;">${totalInput.toLocaleString()}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Output Tokens</span>
                    <span class="stat-value" style="color: #e67e22;">${totalOutput.toLocaleString()}</span>
                </div>
                <div class="stat-item">
                    <span class="stat-label">Total Tokens</span>
                    <span class="stat-value" style="color: #007bff;">${totalAll.toLocaleString()}</span>
                </div>
            `;
        }
    }

    function renderChart(data) {
        const ctx = document.getElementById('tokenUsageChart').getContext('2d');

        if (tokenChart) {
            tokenChart.destroy();
        }

        const labels = data.map(d => d.date);
        const inputValues = data.map(d => d.input);
        const outputValues = data.map(d => d.output);
        const totalValues = data.map(d => d.total);

        tokenChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Input Tokens',
                        data: inputValues,
                        borderColor: '#28a745',
                        backgroundColor: 'rgba(40, 167, 69, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointBackgroundColor: '#28a745',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    },
                    {
                        label: 'Output Tokens',
                        data: outputValues,
                        borderColor: '#e67e22',
                        backgroundColor: 'rgba(230, 126, 34, 0.1)',
                        borderWidth: 2,
                        fill: false,
                        tension: 0.4,
                        pointBackgroundColor: '#e67e22',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 3,
                        pointHoverRadius: 5
                    },
                    {
                        label: 'Total Tokens',
                        data: totalValues,
                        borderColor: '#007bff',
                        backgroundColor: 'rgba(0, 123, 255, 0.1)',
                        borderWidth: 2,
                        fill: true,
                        tension: 0.4,
                        pointBackgroundColor: '#007bff',
                        pointBorderColor: '#fff',
                        pointBorderWidth: 2,
                        pointRadius: 4,
                        pointHoverRadius: 6
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: {
                    mode: 'index',
                    intersect: false
                },
                scales: {
                    x: {
                        ticks: {
                            color: '#555',
                            font: { family: "'IBM Plex Mono', monospace", size: 10 }
                        },
                        grid: { color: 'rgba(0, 0, 0, 0.08)' }
                    },
                    y: {
                        ticks: {
                            color: '#555',
                            font: { family: "'IBM Plex Mono', monospace", size: 10 }
                        },
                        grid: { color: 'rgba(0, 0, 0, 0.08)' },
                        beginAtZero: true
                    }
                },
                plugins: {
                    legend: {
                        labels: {
                            color: '#333',
                            font: { family: "'Chakra Petch', sans-serif", size: 11, weight: 600 }
                        }
                    },
                    tooltip: {
                        backgroundColor: '#f7f5f2',
                        titleColor: '#007bff',
                        bodyColor: '#333',
                        borderColor: 'rgba(0, 0, 0, 0.15)',
                        borderWidth: 1,
                        cornerRadius: 4,
                        padding: 12,
                        titleFont: { family: "'Chakra Petch', sans-serif", size: 11 },
                        bodyFont: { family: "'IBM Plex Mono', monospace", size: 12 }
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

    // === BEDS CONFIGURATION ===

    let currentBedsConfig = null;

    async function loadBedsConfig() {
        try {
            const res = await fetch('/api/beds');
            const data = await res.json();
            currentBedsConfig = data;

            // Update form fields
            document.getElementById('beds-room-count').value = data.room_count || 14;
            document.getElementById('beds-room-start').value = data.room_start || 101;
            document.getElementById('beds-bed-numbers').value = (data.bed_numbers || [1, 2, 3, 5, 6]).join(', ');

            renderBedsGrid();
        } catch (e) {
            console.error("Failed to load beds config:", e);
            document.getElementById('beds-grid').innerHTML = `
                <div style="color: var(--coral); text-align: center; padding: 40px;">
                    Error loading beds configuration: ${e.message}
                </div>
            `;
        }
    }

    function renderBedsGrid() {
        const container = document.getElementById('beds-grid');
        if (!currentBedsConfig || !currentBedsConfig.beds) {
            container.innerHTML = '<div style="color: var(--text-muted); text-align: center; padding: 40px;">No beds configured</div>';
            return;
        }

        const beds = currentBedsConfig.beds;
        const roomCount = currentBedsConfig.room_count || 14;
        const roomStart = currentBedsConfig.room_start || 101;
        const bedNumbers = currentBedsConfig.bed_numbers || [1, 2, 3, 5, 6];

        // Group beds by room
        const roomsMap = {};
        for (const [bedKey, bedInfo] of Object.entries(beds)) {
            const room = bedInfo.room;
            if (!roomsMap[room]) {
                roomsMap[room] = [];
            }
            roomsMap[room].push({ key: bedKey, ...bedInfo });
        }

        // Sort rooms
        const sortedRooms = Object.keys(roomsMap).map(Number).sort((a, b) => a - b);

        let html = '';
        sortedRooms.forEach(room => {
            const roomBeds = roomsMap[room].sort((a, b) => a.bed - b.bed);

            html += `
                <div class="room-section">
                    <div class="room-header">
                        <span>Room ${room}</span>
                        <span style="font-size: 11px; color: var(--text-muted);">${roomBeds.length} beds</span>
                    </div>
                    <div class="room-beds">
            `;

            roomBeds.forEach(bed => {
                const disabledClass = bed.enabled === false ? 'disabled' : '';
                html += `
                    <div class="bed-card ${disabledClass}" data-bed-key="${bed.key}">
                        <div class="bed-header">
                            <span class="bed-name">Bed ${bed.bed}</span>
                            <div class="bed-toggle">
                                <label for="bed-enabled-${bed.key}">Enabled</label>
                                <input type="checkbox" id="bed-enabled-${bed.key}"
                                    ${bed.enabled !== false ? 'checked' : ''}
                                    onchange="toggleBed('${bed.key}', this.checked)">
                            </div>
                        </div>
                        <div class="bed-field">
                            <label>Location ID</label>
                            <input type="text" value="${bed.location_id || ''}"
                                onchange="updateBedField('${bed.key}', 'location_id', this.value)"
                                placeholder="e.g., B_${bed.key}">
                        </div>
                    </div>
                `;
            });

            html += `
                    </div>
                </div>
            `;
        });

        container.innerHTML = html || '<div style="color: var(--text-muted); text-align: center; padding: 40px;">No beds configured</div>';
    }

    window.toggleBed = function(bedKey, enabled) {
        if (!currentBedsConfig || !currentBedsConfig.beds[bedKey]) return;
        currentBedsConfig.beds[bedKey].enabled = enabled;

        // Update visual state
        const card = document.querySelector(`.bed-card[data-bed-key="${bedKey}"]`);
        if (card) {
            if (enabled) {
                card.classList.remove('disabled');
            } else {
                card.classList.add('disabled');
            }
        }
    };

    window.updateBedField = function(bedKey, field, value) {
        if (!currentBedsConfig || !currentBedsConfig.beds[bedKey]) return;
        currentBedsConfig.beds[bedKey][field] = value;
    };

    async function regenerateBeds() {
        const roomCount = parseInt(document.getElementById('beds-room-count').value) || 14;
        const roomStart = parseInt(document.getElementById('beds-room-start').value) || 101;
        const bedNumbersStr = document.getElementById('beds-bed-numbers').value || '1, 2, 3, 5, 6';

        // Parse bed numbers
        const bedNumbers = bedNumbersStr.split(',')
            .map(s => parseInt(s.trim()))
            .filter(n => !isNaN(n));

        if (bedNumbers.length === 0) {
            alert('Please enter valid bed numbers (comma-separated)');
            return;
        }

        // Generate new beds config
        const beds = {};
        for (let i = 0; i < roomCount; i++) {
            const room = roomStart + i;
            for (const bed of bedNumbers) {
                const bedKey = `${room}-${bed}`;
                beds[bedKey] = {
                    room: room,
                    bed: bed,
                    location_id: `B_${bedKey}`,
                    enabled: true
                };
            }
        }

        currentBedsConfig = {
            room_count: roomCount,
            room_start: roomStart,
            bed_numbers: bedNumbers,
            beds: beds
        };

        renderBedsGrid();
    }

    async function saveBedsConfig() {
        if (!currentBedsConfig) {
            alert('No beds configuration to save');
            return;
        }

        // Update room settings from form
        currentBedsConfig.room_count = parseInt(document.getElementById('beds-room-count').value) || 14;
        currentBedsConfig.room_start = parseInt(document.getElementById('beds-room-start').value) || 101;
        const bedNumbersStr = document.getElementById('beds-bed-numbers').value || '1, 2, 3, 5, 6';
        currentBedsConfig.bed_numbers = bedNumbersStr.split(',')
            .map(s => parseInt(s.trim()))
            .filter(n => !isNaN(n));

        try {
            const res = await fetch('/api/beds', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(currentBedsConfig)
            });

            const data = await res.json();
            if (!res.ok || data.error) {
                alert('Failed to save beds configuration: ' + (data.error || 'Unknown error'));
                return;
            }

            alert('Beds configuration saved successfully!');
        } catch (e) {
            alert('Failed to save beds configuration: ' + e.message);
        }
    }

    // Beds button event listeners
    const btnRegenerateBeds = document.getElementById('btn-regenerate-beds');
    if (btnRegenerateBeds) {
        btnRegenerateBeds.addEventListener('click', regenerateBeds);
    }

    const btnSaveBeds = document.getElementById('btn-save-beds');
    if (btnSaveBeds) {
        btnSaveBeds.addEventListener('click', saveBedsConfig);
    }

});
