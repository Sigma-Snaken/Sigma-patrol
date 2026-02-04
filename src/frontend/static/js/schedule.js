// schedule.js — Schedule CRUD, render list, next-patrol display
import state from './state.js';

let scheduledPatrols = [];
const dayNames = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

export function initSchedule() {
    const btnAddSchedule = document.getElementById('btn-add-schedule');
    if (btnAddSchedule) {
        btnAddSchedule.addEventListener('click', addSchedule);
    }

    loadSchedule();
    setInterval(updateNextPatrolDisplay, 60000);
}

export async function loadSchedule() {
    if (!state.selectedRobotId) return;
    try {
        const res = await fetch(`/api/${state.selectedRobotId}/patrol/schedule`);
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
        updateNextPatrolDisplay();
        return;
    }

    container.innerHTML = '';
    scheduledPatrols.forEach(schedule => {
        const item = document.createElement('div');
        item.className = 'schedule-item';
        item.style.cssText = 'display: flex; align-items: center; gap: 10px; padding: 10px 12px; background: var(--slate-dark); border-radius: var(--radius-sm); border: 1px solid var(--border-subtle);';

        const timeSpan = document.createElement('span');
        timeSpan.style.cssText = 'font-family: var(--font-mono); font-size: 16px; font-weight: 600; color: var(--cyan-glow); min-width: 60px;';
        timeSpan.textContent = schedule.time;

        const daysSpan = document.createElement('span');
        daysSpan.style.cssText = 'flex: 1; font-size: 11px; color: var(--text-secondary);';
        const activeDays = (schedule.days || [0, 1, 2, 3, 4, 5, 6]).map(d => dayNames[d]).join(', ');
        daysSpan.textContent = schedule.days && schedule.days.length < 7 ? activeDays : 'Every day';

        const toggleLabel = document.createElement('label');
        toggleLabel.style.cssText = 'display: flex; align-items: center; cursor: pointer;';
        const toggleCheckbox = document.createElement('input');
        toggleCheckbox.type = 'checkbox';
        toggleCheckbox.checked = schedule.enabled !== false;
        toggleCheckbox.style.cssText = 'width: 18px; height: 18px;';
        toggleCheckbox.onchange = () => toggleSchedule(schedule.id, toggleCheckbox.checked);
        toggleLabel.appendChild(toggleCheckbox);

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

    updateNextPatrolDisplay();
}

async function addSchedule() {
    const timeInput = document.getElementById('schedule-time-input');
    if (!timeInput || !timeInput.value) {
        alert('Please select a time');
        return;
    }

    try {
        const res = await fetch(`/api/${state.selectedRobotId}/patrol/schedule`, {
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
        await fetch(`/api/${state.selectedRobotId}/patrol/schedule/${id}`, {
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
        await fetch(`/api/${state.selectedRobotId}/patrol/schedule/${id}`, {
            method: 'DELETE'
        });
        loadSchedule();
    } catch (e) {
        console.error("Failed to delete schedule:", e);
    }
}

function updateNextPatrolDisplay() {
    const display = document.getElementById('next-patrol-display');
    if (!display) return;

    const enabledSchedules = scheduledPatrols.filter(s => s.enabled !== false);
    if (enabledSchedules.length === 0) {
        display.innerHTML = '';
        return;
    }

    const now = new Date();
    const currentDay = now.getDay();
    const todayIndex = currentDay === 0 ? 6 : currentDay - 1;
    const currentMinutes = now.getHours() * 60 + now.getMinutes();

    let nextPatrol = null;
    let minMinutesAway = Infinity;

    enabledSchedules.forEach(schedule => {
        const [hours, mins] = schedule.time.split(':').map(Number);
        const scheduleMinutes = hours * 60 + mins;
        const scheduleDays = schedule.days || [0, 1, 2, 3, 4, 5, 6];

        for (let dayOffset = 0; dayOffset < 7; dayOffset++) {
            const checkDayIndex = (todayIndex + dayOffset) % 7;

            if (!scheduleDays.includes(checkDayIndex)) continue;

            let minutesAway;
            if (dayOffset === 0) {
                if (scheduleMinutes > currentMinutes) {
                    minutesAway = scheduleMinutes - currentMinutes;
                } else {
                    continue;
                }
            } else {
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
            const dayName = dayNames[(todayIndex + nextPatrol.dayOffset) % 7];
            timeText = `${dayName} at ${nextPatrol.time}`;
        }
        display.innerHTML = `<span style="color: var(--cyan-dim);">⏰</span> Next: <span style="color: var(--text-primary);">${timeText}</span>`;
    } else {
        display.innerHTML = '';
    }
}
