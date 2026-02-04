document.addEventListener('DOMContentLoaded', () => {
    loadLogs();
    // Auto-refresh every 10 seconds
    setInterval(loadLogs, 10000);
});

async function loadLogs() {
    const tbody = document.getElementById('logs-body');
    const level = document.getElementById('log-level').value;
    
    // Don't clear content if auto-refreshing, just update
    // But if manual refresh (via button calling this), we might want to show loading state? 
    // For now, let's just replace content silently.
    
    try {
        const url = level ? `/api/logs?level=${level}` : '/api/logs';
        const response = await fetch(url);
        const data = await response.json();
        
        if (!data.logs || data.logs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-muted" style="padding: 1rem;">No logs found.</td></tr>';
            return;
        }

        tbody.innerHTML = data.logs.map(log => {
            let badgeStyle = '';
            if (log.level === 'WARNING') badgeStyle = 'background: rgba(245, 158, 11, 0.15); color: #FCD34D; border: 1px solid rgba(245, 158, 11, 0.3);';
            if (log.level === 'ERROR') badgeStyle = 'background: rgba(239, 68, 68, 0.15); color: #FCA5A5; border: 1px solid rgba(239, 68, 68, 0.3);';
            if (log.level === 'INFO') badgeStyle = 'background: rgba(59, 130, 246, 0.15); color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.3);';

            let timeStr = '—';
            try {
                if (log.timestamp) timeStr = new Date(log.timestamp).toLocaleTimeString();
            } catch (_) {}

            let message = log.message || log.event || '';
            if (log.data && Object.keys(log.data).length > 0) {
                message += `<br><span class="text-muted text-sm" style="font-size: 0.8rem;">${JSON.stringify(log.data).replace(/</g, '&lt;')}</span>`;
            }

            return `
            <tr class="log-row">
                <td class="text-sm font-mono" style="white-space: nowrap;">${timeStr}</td>
                <td><span class="badge" style="${badgeStyle}">${log.level || 'INFO'}</span></td>
                <td class="font-mono text-sm" style="word-break: break-all;">${message.replace(/</g, '&lt;')}</td>
            </tr>
        `}).join('');

    } catch (error) {
        console.error('Failed to load logs:', error);
        // Only show error if table is empty
        if (tbody.children.length <= 1) {
            tbody.innerHTML = '<tr><td colspan="3" class="text-error" style="padding: 1rem;">Failed to load logs.</td></tr>';
        }
    }
}
