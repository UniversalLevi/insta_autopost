/** Logs viewer page JavaScript logic */

let autoRefreshInterval = null;

document.addEventListener('DOMContentLoaded', async () => {
    // Load initial logs
    await loadLogs();
    
    // Auto-refresh checkbox
    const autoRefreshCheckbox = document.getElementById('autoRefresh');
    if (autoRefreshCheckbox) {
        autoRefreshCheckbox.addEventListener('change', (e) => {
            if (e.target.checked) {
                startAutoRefresh();
            } else {
                stopAutoRefresh();
            }
        });
        
        if (autoRefreshCheckbox.checked) {
            startAutoRefresh();
        }
    }
    
    // Manual refresh button
    const refreshBtn = document.getElementById('refreshLogsBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadLogs();
        });
    }
    
    // Level filter
    const levelSelect = document.getElementById('logLevel');
    if (levelSelect) {
        levelSelect.addEventListener('change', () => {
            loadLogs();
        });
    }
});

async function loadLogs() {
    const container = document.getElementById('logsContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    if (!container) return;
    
    if (loadingIndicator) loadingIndicator.style.display = 'block';
    
    try {
        const level = document.getElementById('logLevel')?.value || null;
        const params = new URLSearchParams({ lines: '100' });
        if (level) params.append('level', level);
        
        const response = await apiRequest(`/logs?${params}`);
        
        if (!response) {
            container.innerHTML = '<p class="empty-state">No logs available</p>';
            return;
        }
        
        if (response.logs && response.logs.length > 0) {
            displayLogs(response.logs);
        } else {
            container.innerHTML = '<p class="empty-state">No logs found</p>';
        }
    } catch (error) {
        console.error('Failed to load logs:', error);
        container.innerHTML = `<p class="error-message">Error loading logs: ${error.message}</p>`;
    } finally {
        if (loadingIndicator) loadingIndicator.style.display = 'none';
    }
}

function displayLogs(logs) {
    const container = document.getElementById('logsContainer');
    if (!container) return;
    
    const logTable = document.createElement('table');
    logTable.className = 'logs-table';
    
    // Header
    const header = document.createElement('thead');
    header.innerHTML = `
        <tr>
            <th>Timestamp</th>
            <th>Level</th>
            <th>Event</th>
            <th>Message</th>
        </tr>
    `;
    logTable.appendChild(header);
    
    // Body
    const body = document.createElement('tbody');
    logs.forEach(log => {
        const row = document.createElement('tr');
        row.className = `log-entry log-${log.level.toLowerCase()}`;
        
        const timestamp = formatDate(log.timestamp);
        const levelClass = `log-level log-level-${log.level.toLowerCase()}`;
        
        row.innerHTML = `
            <td class="log-timestamp">${timestamp}</td>
            <td><span class="${levelClass}">${log.level}</span></td>
            <td class="log-event">${escapeHtml(log.event)}</td>
            <td class="log-message">${escapeHtml(log.message || '')}</td>
        `;
        
        body.appendChild(row);
    });
    
    logTable.appendChild(body);
    container.innerHTML = '';
    container.appendChild(logTable);
}

function startAutoRefresh() {
    stopAutoRefresh(); // Clear any existing interval
    autoRefreshInterval = setInterval(() => {
        loadLogs();
    }, 5000); // Refresh every 5 seconds
}

function stopAutoRefresh() {
    if (autoRefreshInterval) {
        clearInterval(autoRefreshInterval);
        autoRefreshInterval = null;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
    stopAutoRefresh();
});
