// app.js — Entry point: init, tab switching
import { initMap, resizeCanvas, startPolling } from './map.js';
import { initControls } from './controls.js';
import { initAI } from './ai.js';
import { initPoints, loadPoints } from './points.js';
import { initPatrol } from './patrol.js';
import { initSchedule } from './schedule.js';
import { initHistory, loadHistory } from './history.js';
import { initSettings, loadSettings } from './settings.js';
import { initStats, loadStats } from './stats.js';

// --- TAB SWITCHING ---
window.switchTab = function (tabName) {
    document.querySelectorAll('.tab-content').forEach(el => el.style.display = 'none');
    document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));

    const target = document.getElementById(`view-${tabName}`);
    if (target) target.style.display = 'block';

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
            dest.prepend(mapContainer);
        }
        setTimeout(resizeCanvas, 50);
    } else if (tabName === 'patrol') {
        const dest = document.getElementById('patrol-left-panel');
        if (dest && mapContainer.parentNode !== dest) {
            dest.appendChild(mapContainer);
        }
        setTimeout(resizeCanvas, 50);
    }
};

// --- COLLAPSIBLE PANELS ---
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
    if (frame) frame.classList.toggle('collapsed');
};

window.togglePatrolRoute = function () {
    const frame = document.getElementById('patrol-route-frame');
    if (frame) frame.classList.toggle('collapsed');
};

window.toggleSchedulePanel = function () {
    const frame = document.getElementById('schedule-frame');
    if (frame) frame.classList.toggle('collapsed');
};

window.toggleAITestPanel = function () {
    const frame = document.getElementById('ai-test-frame');
    if (frame) frame.classList.toggle('collapsed');
};

window.togglePatrolPointsPanel = function () {
    const frame = document.getElementById('patrol-points-frame');
    if (frame) frame.classList.toggle('collapsed');
};

window.toggleFrontCameraPanel = function () {
    const frame = document.getElementById('front-camera-frame');
    if (frame) frame.classList.toggle('collapsed');
};

window.toggleRobotVisionPanel = function () {
    const frame = document.getElementById('robot-vision-frame');
    if (frame) frame.classList.toggle('collapsed');
};

// --- INITIALIZATION ---
document.addEventListener('DOMContentLoaded', () => {
    initMap();
    startPolling();
    initControls();
    initAI();
    initPoints();
    loadPoints();
    initPatrol();
    initSchedule();
    initHistory();
    initSettings();
    initStats();

    // Default tab
    window.switchTab('control');
});
