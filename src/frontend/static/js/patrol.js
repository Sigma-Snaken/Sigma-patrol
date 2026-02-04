// patrol.js — Start/stop patrol, status polling, results display, camera stream
import state from './state.js';
import { renderAIResultHTML } from './ai.js';

let btnStartPatrol, btnStopPatrol;
let isStreamActive = true;

export function initPatrol() {
    btnStartPatrol = document.getElementById('btn-start-patrol');
    btnStopPatrol = document.getElementById('btn-stop-patrol');

    if (btnStartPatrol) btnStartPatrol.addEventListener('click', startPatrol);
    if (btnStopPatrol) btnStopPatrol.addEventListener('click', stopPatrol);

    loadResults();
    startPatrolPolling();
}

async function startPatrol() {
    const resultsContainer = document.getElementById('results-container');
    if (resultsContainer) resultsContainer.innerHTML = '';

    const res = await fetch(`/api/${state.selectedRobotId}/patrol/start`, { method: 'POST' });
    if (!res.ok) {
        const err = await res.json();
        alert(err.error);
    }
}

async function stopPatrol() {
    await fetch(`/api/${state.selectedRobotId}/patrol/stop`, { method: 'POST' });
}

function startPatrolPolling() {
    setInterval(async () => {
        if (!state.selectedRobotId) return;
        const res = await fetch(`/api/${state.selectedRobotId}/patrol/status`);
        const data = await res.json();

        if (data.is_patrolling) {
            if (btnStartPatrol) btnStartPatrol.disabled = true;
            if (btnStopPatrol) btnStopPatrol.disabled = false;
        } else {
            if (btnStartPatrol) btnStartPatrol.disabled = false;
            if (btnStopPatrol) btnStopPatrol.disabled = true;
        }

        const shouldStream = data.is_patrolling || state.currentIdleStreamEnabled;
        updateCameraStream(shouldStream);

        loadResults();
    }, 1000);
}

let lastStreamRobotId = null;

function updateCameraStream(shouldStream) {
    const robotChanged = lastStreamRobotId !== state.selectedRobotId;
    if (shouldStream === isStreamActive && !robotChanged) return;
    isStreamActive = shouldStream;
    lastStreamRobotId = state.selectedRobotId;

    const cams = [
        document.getElementById('front-camera-img'),
        document.getElementById('robot-vision-img')
    ];

    cams.forEach(img => {
        if (img) {
            if (shouldStream && state.selectedRobotId) {
                img.src = `/api/${state.selectedRobotId}/camera/front?t=` + new Date().getTime();
                img.style.opacity = 1;
            } else {
                img.src = '';
                img.alt = 'Stream Paused (Idle Mode)';
                img.style.opacity = 0.5;
            }
        }
    });
}

export async function loadResults() {
    const resultsContainer = document.getElementById('results-container');

    if (!state.selectedRobotId) return;
    const res = await fetch(`/api/${state.selectedRobotId}/patrol/results`);
    const results = await res.json();

    if (resultsContainer) {
        resultsContainer.innerHTML = '';
        results.slice().slice(-10).reverse().forEach(r => {
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

    // Update Latest Result Dashboard Widget
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
