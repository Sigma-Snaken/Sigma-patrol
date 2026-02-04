// controls.js — Manual control (d-pad), return home, cancel command
import state from './state.js';

export function initControls() {
    const btnHome = document.getElementById('btn-home');
    const btnCancelCommand = document.getElementById('btn-cancel-command');

    if (btnHome) btnHome.addEventListener('click', returnHome);
    if (btnCancelCommand) btnCancelCommand.addEventListener('click', cancelCommand);

    window.manualControl = manualControl;
}

export async function moveRobot(x, y, theta) {
    try {
        await fetch('/api/move', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ x, y, theta })
        });
    } catch (e) {
        console.error("Move Failed", e);
    }
}

async function returnHome() {
    try {
        await fetch('/api/return_home', { method: 'POST' });
    } catch (e) {
        console.error("Return Home Failed", e);
    }
}

async function cancelCommand() {
    try {
        await fetch('/api/cancel_command', { method: 'POST' });
    } catch (e) {
        console.error("Cancel Command Failed", e);
    }
}

async function manualControl(action) {
    try {
        await fetch('/api/manual_control', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action })
        });
    } catch (e) {
        console.error("Manual Control Failed", e);
    }
}
