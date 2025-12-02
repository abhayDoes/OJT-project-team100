lucide.createIcons(); //create icons for the website

const API_BASE_URL = 'http://localhost:5002'; //base url for the api

async function callApi(endpoint, method, body) {
    const maxRetries = 3;
    for (let attempt = 0; attempt < maxRetries; attempt++) {
        try {
            const response = await fetch(`${API_BASE_URL}${endpoint}`, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                // Ensure body is stringified correctly
                body: body ? JSON.stringify(body) : undefined, 
            });

            const result = await response.json();

            if (!response.ok) {
                // If it's a 4xx or 5xx error that is not a temporary failure, stop retrying
                displayMessage(`API Error [${response.status}]: ${result.error || response.statusText}`, 'error');
                throw new Error(`[${response.status}] ${result.error || response.statusText}`);
            }
            
            return result;

        } catch (error) {
            if (attempt < maxRetries - 1) {
                // Exponential backoff: Wait 1s, 2s, 4s...
                await new Promise(resolve => setTimeout(resolve, Math.pow(2, attempt) * 1000));
            } else {
                // Final error handling
                console.error("API Call Failed:", error);
                if (!error.message.includes('API Error')) {
                     displayMessage(`Connection Error: Ensure the Python server is running on ${API_BASE_URL}.`, 'error');
                }
                return null;
            }
        }
    }
}

// Error message box
function displayMessage(text, type = 'info') {
    let msgBox = document.getElementById('temp-message-box');
    if (!msgBox) {
        msgBox = document.createElement('div');
        msgBox.id = 'temp-message-box';
        msgBox.style.cssText = `
            position: fixed; top: 20px; right: 20px; z-index: 1000;
            padding: 15px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            font-family: 'Inter', sans-serif; transition: opacity 0.5s ease-in-out;
            opacity: 0; max-width: 350px; color: #0D1117; font-weight: 600;
        `;
        document.body.appendChild(msgBox);
    }

    if (type === 'error') {
        msgBox.style.backgroundColor = '#FF6347'; // Tomato Red
    } else if (type === 'success') {
        msgBox.style.backgroundColor = '#3CB371'; // Medium Sea Green
    } else {
        msgBox.style.backgroundColor = '#87CEFA'; // Light Sky Blue
    }

    msgBox.textContent = text;
    msgBox.style.opacity = 1;

    setTimeout(() => {
        msgBox.style.opacity = 0;
        setTimeout(() => msgBox.remove(), 600);
    }, 4000);
}

//API calling
async function takeSnapshot(path, snapshotId) {
    document.getElementById('snapshot-status').textContent = `Capturing snapshot for path: ${path}...`;
    
    const result = await callApi('/snapshot', 'POST', { 
        path: path, 
        id: snapshotId 
    });

    if (result) {
        displayMessage(`Snapshot ${result.id} created with ${result.file_count} files!`, 'success');
        document.getElementById('snapshot-status').textContent = `Snapshot ${result.id} is ready. File Count: ${result.file_count}`;
    } else {
        document.getElementById('snapshot-status').textContent = `Snapshot failed. Check console for errors.`;
    }
}

async function runDiff(idA, idB) {
    document.getElementById('diff-summary').innerHTML = '<li>Status: <span style="color: var(--primary-cyan);">Comparing...</span></li>';

    const result = await callApi('/diff', 'POST', { 
        id_a: idA, 
        id_b: idB 
    });

    if (result) {
        displayMessage(`Diff Complete: ${idA} vs ${idB}`, 'success');
        
        const summary = result.summary;
        // The Python backend is designed to return the counts directly.

        const summaryHtml = `
            <li>Added: <span style="color: #3CB371;">${summary.added || 0}</span> file(s)</li>
            <li>Deleted: <span style="color: #FF6347;">${summary.deleted || 0}</span> file(s)</li>
            <li>Modified: <span style="color: #FFA500;">${summary.modified || 0}</span> file(s)</li>
        `;
        document.getElementById('diff-summary').innerHTML = summaryHtml;

        // Log detailed changes to console for the user to inspect
        const details = result.diff_details;
        console.groupCollapsed(`Diff Details for ${idA} vs ${idB} (Click to expand)`);
        if (details.added.length > 0) console.log('ADDED:', details.added);
        if (details.deleted.length > 0) console.log('DELETED:', details.deleted);
        if (details.modified.length > 0) console.log('MODIFIED:', details.modified);
        console.groupEnd();
    } else {
        document.getElementById('diff-summary').innerHTML = '<li>Status: <span style="color: #FF6347;">**Diff Failed.**</span></li>';
    }
}

//ADDING PAGE RESPONSE (HTML CONTENT)

document.addEventListener('DOMContentLoaded', () => {


    // Handle Snapshot Capture Click
    const captureBtn = document.getElementById('capture-snapshot-btn');
    if (captureBtn) {
        captureBtn.addEventListener('click', () => {
            const path = document.getElementById('file-path').value.trim(); // Get path from input
            const id = document.getElementById('snapshot-id').value.trim();
            
            if (!path) {
                displayMessage('Please enter the directory path.', 'error');
                return;
            }
            if (!id) {
                displayMessage('Please enter a Snapshot ID.', 'error');
                return;
            }
            
            takeSnapshot(path, id);
        });
    }
    
    // Handle Diff Run Click
    const diffBtn = document.getElementById('run-diff-btn');
    if (diffBtn) {
        diffBtn.addEventListener('click', () => {
            const idA = document.getElementById('diff-id-a').value.trim();
            const idB = document.getElementById('diff-id-b').value.trim();
            
            if (idA && idB) {
                runDiff(idA, idB);
            } else {
                displayMessage('Please enter both Snapshot A and Snapshot B IDs.', 'error');
            }
        });
    }
});

