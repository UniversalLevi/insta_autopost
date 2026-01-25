// Global Application Logic

document.addEventListener('DOMContentLoaded', () => {
    checkSystemStatus();
    setInterval(checkSystemStatus, 30000); // Check every 30s
});

async function checkSystemStatus() {
    const statusEl = document.getElementById('system-status');
    const dotEl = document.querySelector('.status-dot');

    if (!statusEl) return;

    function setOk() {
        statusEl.textContent = 'System Operational';
        if (dotEl) { dotEl.classList.add('active'); dotEl.style.backgroundColor = 'var(--success)'; }
    }
    function setWarn() {
        statusEl.textContent = 'System Issues';
        if (dotEl) { dotEl.classList.remove('active'); dotEl.style.backgroundColor = 'var(--warning)'; }
    }
    function setErr() {
        statusEl.textContent = 'Connection Lost';
        if (dotEl) { dotEl.classList.remove('active'); dotEl.style.backgroundColor = 'var(--error)'; }
    }

    try {
        const response = await fetch('/api/status');
        const data = await response.json();
        if (data.app_status === 'running') setOk();
        else setWarn();
    } catch (error) {
        console.error('Status check failed:', error);
        setErr();
    }
}

// Utility to format dates
function formatDate(dateString) {
    if (!dateString) return '-';
    return new Date(dateString).toLocaleString();
}

// Modal Utilities
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'block';
        modal.classList.remove('hidden');
    }
}

function closeModal(modalId) {
    // If no ID provided, try to find open modals
    if (!modalId) {
        document.querySelectorAll('.modal').forEach(m => {
            m.style.display = 'none';
            m.classList.add('hidden');
        });
        return;
    }
    
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.style.display = 'none';
        modal.classList.add('hidden');
    }
}

// Close modal when clicking outside
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.style.display = 'none';
        event.target.classList.add('hidden');
    }
}
