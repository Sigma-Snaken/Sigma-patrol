// ai.js — AI test, parseAIResponse, renderAIResultHTML (shared utility)
import state from './state.js';

export function initAI() {
    const btnTestAI = document.getElementById('btn-test-ai');
    if (btnTestAI) btnTestAI.addEventListener('click', testAI);
}

export async function testAI(overridePrompt = null) {
    // If called from event listener, first arg is Event object, not string
    if (overridePrompt && typeof overridePrompt !== 'string') {
        overridePrompt = null;
    }

    const promptInput = document.getElementById('ai-test-prompt-input');
    const outputPrompt = document.getElementById('ai-output-prompt');
    const outputResult = document.getElementById('ai-output-result');

    let promptToSend = overridePrompt;
    if (promptToSend === null && promptInput) {
        promptToSend = promptInput.value;
    }
    if (!promptToSend) promptToSend = "";

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
                let isNG = false;
                let desc = "";

                if (typeof data.result === 'object' && data.result !== null) {
                    isNG = data.result.is_NG;
                    desc = data.result.Description;
                } else {
                    desc = String(data.result);
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

export function parseAIResponse(responseStr) {
    let isNG = false;
    let desc = responseStr;

    try {
        const data = JSON.parse(responseStr);
        if (data && typeof data === 'object') {
            if (data.is_NG !== undefined) {
                isNG = data.is_NG;
                desc = data.Description;
            }
        }
    } catch (e) {
        if (typeof responseStr === 'string') {
            isNG = responseStr.toLowerCase().includes("ng");
        }
    }
    return { isNG, desc };
}

export function renderAIResultHTML(responseStr) {
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
