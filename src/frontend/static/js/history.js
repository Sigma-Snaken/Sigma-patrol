// history.js — History list, detail modal, report generation, PDF
import state, { escapeHtml } from './state.js';
import { renderAIResultHTML } from './ai.js';

let robotsCache = null;

async function loadRobotsList() {
    if (robotsCache) return robotsCache;
    try {
        const res = await fetch('/api/robots');
        robotsCache = await res.json();
        return robotsCache;
    } catch (e) {
        return [];
    }
}

function getRobotName(robotId) {
    if (!robotsCache) return robotId || '';
    const robot = robotsCache.find(r => r.robot_id === robotId);
    return robot ? robot.robot_name : (robotId || '');
}

export function initHistory() {
    const btnSavePdf = document.getElementById('btn-save-pdf');
    if (btnSavePdf) {
        btnSavePdf.addEventListener('click', saveReportAsPDF);
    }

    const modal = document.getElementById('history-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closeHistoryModal();
        });
    }

    const btnGenerateReport = document.getElementById('btn-generate-report');
    if (btnGenerateReport) {
        btnGenerateReport.addEventListener('click', generateReport);

        // Initialize dates
        const end = new Date();
        const start = new Date();
        start.setDate(start.getDate() - 7);

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

    // Robot filter
    const robotFilter = document.getElementById('history-robot-filter');
    if (robotFilter) {
        robotFilter.addEventListener('change', loadHistory);
    }

    // Expose to window for inline onclick handlers
    window.viewHistoryDetail = viewHistoryDetail;
    window.closeHistoryModal = closeHistoryModal;
    window.saveReportAsPDF = saveReportAsPDF;
    window.closeGeneratedReport = closeGeneratedReport;
    window.saveGeneratedReportAsPDF = saveGeneratedReportAsPDF;

    // Internal state for PDF generation
    window.currentReportRunId = null;
    window.currentReportData = null;
    window.generatedReportData = null;
}

async function populateRobotFilter(selectId) {
    const select = document.getElementById(selectId);
    if (!select) return;

    const robots = await loadRobotsList();

    // Preserve current value
    const currentVal = select.value;

    // Clear all except first option (All Robots)
    while (select.options.length > 1) {
        select.remove(1);
    }

    robots.forEach(robot => {
        const opt = document.createElement('option');
        opt.value = robot.robot_id;
        opt.textContent = robot.robot_name;
        select.appendChild(opt);
    });

    // Restore value if it still exists
    if (currentVal) select.value = currentVal;
}

export async function loadHistory() {
    const listContainer = document.getElementById('history-list');
    if (!listContainer) return;

    await populateRobotFilter('history-robot-filter');

    listContainer.innerHTML = '<div style="color:#666; text-align:center;">Loading history...</div>';

    try {
        const robotFilter = document.getElementById('history-robot-filter');
        const robotId = robotFilter ? robotFilter.value : '';
        const url = robotId ? `/api/history?robot_id=${encodeURIComponent(robotId)}` : '/api/history';

        const res = await fetch(url);
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
            const robotName = getRobotName(run.robot_id);
            const robotTag = robotName ? `<span class="robot-tag">${escapeHtml(robotName)}</span>` : '';

            card.innerHTML = `
                <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:8px;">
                    <span style="font-weight:bold; font-size:1.1rem; color:#1a1a1a;">Patrol Run #${run.id} ${robotTag}</span>
                    <span style="font-size:0.8rem; background:${statusColor}; color:#fff; padding:2px 8px; border-radius:4px; font-weight:bold;">${escapeHtml(run.status)}</span>
                </div>
                <div style="display:flex; justify-content:space-between; font-size:0.85rem; color:#555;">
                    <span>Started: ${escapeHtml(run.start_time)}</span>
                    <span>Tokens: ${run.total_tokens || 0}</span>
                </div>
                ${run.report_content ? `<div style="margin-top:10px; color:#333; font-size:0.85rem; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden;">${escapeHtml(run.report_content)}</div>` : ''}
            `;
            listContainer.appendChild(card);
        });

    } catch (e) {
        listContainer.innerHTML = `<div style="color:#dc3545; text-align:center;">Error loading history: ${escapeHtml(String(e))}</div>`;
    }
}

async function viewHistoryDetail(runId) {
    const modal = document.getElementById('history-modal');
    const contentDiv = document.getElementById('modal-report-content');
    const listDiv = document.getElementById('modal-inspections-list');
    const title = document.getElementById('modal-title');

    if (!modal) return;

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

        window.currentReportData = { run, inspections };

        // Determine image base URL based on robot_id
        const imgBase = run.robot_id ? `/api/${run.robot_id}/images/` : '/api/images/';

        if (run.report_content) {
            contentDiv.innerHTML = marked.parse(run.report_content);
        } else {
            contentDiv.textContent = "No generated report available.";
        }

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

                let imgHtml = '';
                if (ins.image_path) {
                    imgHtml = `<img src="${imgBase}${ins.image_path}" style="width:120px; height:auto; border-radius:4px; border:1px solid #ccc;">`;
                }

                const resultHTML = renderAIResultHTML(ins.ai_response);

                item.innerHTML = `
                    ${imgHtml}
                    <div style="flex:1;">
                        <div style="font-weight:bold; color:#006b56; margin-bottom:4px;">${escapeHtml(ins.point_name)}</div>
                        <div style="font-size:0.8rem; color:#555; margin-bottom:6px;">${escapeHtml(ins.timestamp)}</div>
                        <div style="background:rgba(0,0,0,0.03); padding:6px; border-radius:4px; font-size:0.85rem;">
                            <div style="color:#555; font-style:italic; margin-bottom:4px;">Q: ${escapeHtml(ins.prompt)}</div>
                            ${resultHTML}
                        </div>
                    </div>
                `;
                listDiv.appendChild(item);
            });
        }

    } catch (e) {
        contentDiv.textContent = `Error: ${String(e)}`;
    }
}

function closeHistoryModal() {
    const modal = document.getElementById('history-modal');
    if (modal) modal.style.display = 'none';
}

function saveReportAsPDF() {
    const runId = window.currentReportRunId;
    if (!runId) {
        alert('No report selected. Please reopen the report.');
        return;
    }
    window.location.href = `/api/report/${runId}/pdf`;
}

function closeGeneratedReport() {
    const container = document.getElementById('generated-report-container');
    if (container) container.style.display = 'none';
}

function saveGeneratedReportAsPDF() {
    const startDate = document.getElementById('history-start-date')?.value;
    const endDate = document.getElementById('history-end-date')?.value;

    if (!startDate || !endDate) {
        alert('No date range selected.');
        return;
    }

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

        if (container) {
            container.style.display = 'block';
            contentDiv.innerHTML = marked.parse(data.report);

            document.getElementById('report-prompt-tokens').innerText = data.usage.prompt_token_count || 0;
            document.getElementById('report-completion-tokens').innerText = data.usage.candidates_token_count || 0;
            document.getElementById('report-total-tokens').innerText = data.usage.total_token_count || 0;
        }

    } catch (e) {
        alert("Error: " + e.message);
    } finally {
        btn.disabled = false;
        btn.innerHTML = originalText;
    }
}
