// Global Application Logic

document.addEventListener('DOMContentLoaded', async () => {
    // Check authentication first (unless on login/register pages)
    if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
        try {
            // Load auth.js if available
            if (typeof getCurrentUser === 'function') {
                const user = await getCurrentUser();
                if (!user) {
                    window.location.href = '/login';
                    return;
                }
            }
        } catch (error) {
            // If auth check fails, redirect to login
            if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
                window.location.href = '/login';
                return;
            }
        }
    }
    
    checkSystemStatus();
    setInterval(checkSystemStatus, 30000); // Check every 30s
});

async function checkSystemStatus() {
    const statusEl = document.getElementById('system-status');
    const dotEl = document.querySelector('.status-dot');

    if (!statusEl) return;

    function setOk() {
        statusEl.textContent = 'System Operational';
        if (dotEl) { dotEl.classList.add('active'); dotEl.style.backgroundColor = 'var(--primary)'; }
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
        // Use authenticated fetch if available
        const fetchFn = typeof authenticatedFetch === 'function' ? authenticatedFetch : fetch;
        const response = await fetchFn('/api/status');
        
        if (!response.ok && response.status === 401) {
            // Unauthorized, redirect to login
            if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
                window.location.href = '/login';
            }
            return;
        }
        
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
        modal.classList.remove('hidden');
        modal.classList.add('show');
        document.body.style.overflow = 'hidden'; // Prevent background scrolling
    }
}

function closeModal(modalId) {
    // If no ID provided, try to find open modals
    if (!modalId) {
        document.querySelectorAll('.modal').forEach(m => {
            m.classList.remove('show');
            m.classList.add('hidden');
        });
        document.body.style.overflow = '';
        return;
    }
    
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('show');
        modal.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// Close modal when clicking outside or pressing Escape
window.onclick = function(event) {
    if (event.target.classList.contains('modal')) {
        event.target.classList.remove('show');
        event.target.classList.add('hidden');
        document.body.style.overflow = '';
    }
}

// Close modal on Escape key
document.addEventListener('keydown', function(event) {
    if (event.key === 'Escape') {
        document.querySelectorAll('.modal.show').forEach(modal => {
            modal.classList.remove('show');
            modal.classList.add('hidden');
            document.body.style.overflow = '';
        });
    }
});
