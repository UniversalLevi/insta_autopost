document.addEventListener('DOMContentLoaded', () => {
    loadAccounts();
    loadSettings();
    loadCommentSettings();
});

// Accounts
async function loadAccounts() {
    const list = document.getElementById('accounts-list');
    list.innerHTML = '<div class="text-muted">Loading...</div>';

    try {
        const response = await fetch('/api/config/accounts');
        const data = await response.json();
        
        if (!data.accounts || data.accounts.length === 0) {
            list.innerHTML = '<div class="text-muted">No accounts added.</div>';
            return;
        }

        list.innerHTML = data.accounts.map(acc => `
            <div class="card flex justify-between items-center" style="margin-bottom: 0.5rem; padding: 1rem; border: 1px solid var(--border);">
                <div>
                    <div class="font-bold">${acc.username}</div>
                    <div class="text-sm text-muted">${acc.account_id}</div>
                    <div class="text-sm mt-1">
                        ${acc.warming && acc.warming.enabled ? '<span class="badge badge-info" style="background: #DBEAFE; color: #1E40AF;">Warming On</span>' : '<span class="text-muted">Warming Off</span>'}
                    </div>
                </div>
                <div class="flex gap-2">
                    <button class="btn btn-secondary" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" onclick="editAccount('${acc.account_id}')">Edit</button>
                    <button class="btn btn-danger" style="padding: 0.25rem 0.5rem; font-size: 0.8rem;" onclick="deleteAccount('${acc.account_id}')">Delete</button>
                </div>
            </div>
        `).join('');

    } catch (error) {
        console.error('Failed to load accounts:', error);
        list.innerHTML = '<div class="text-error">Failed to load accounts.</div>';
    }
}

// Global Settings
async function loadSettings() {
    try {
        const response = await fetch('/api/config/settings');
        const settings = await response.json();
        
        if (settings.warming) {
            document.getElementById('warming-schedule').value = settings.warming.schedule_time || "09:00";
        }
        if (settings.instagram && settings.instagram.rate_limit) {
            document.getElementById('rate-hour').value = settings.instagram.rate_limit.requests_per_hour || 200;
            document.getElementById('rate-minute').value = settings.instagram.rate_limit.requests_per_minute || 20;
        }
        if (settings.instagram && settings.instagram.posting) {
            document.getElementById('post-retries').value = settings.instagram.posting.max_retries || 3;
        }
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function saveGlobalSettings() {
    try {
        const currentSettingsRes = await fetch('/api/config/settings');
        const currentSettings = await currentSettingsRes.json();
        
        // Update fields
        if (!currentSettings.warming) currentSettings.warming = {};
        currentSettings.warming.schedule_time = document.getElementById('warming-schedule').value;
        
        if (!currentSettings.instagram) currentSettings.instagram = {};
        if (!currentSettings.instagram.rate_limit) currentSettings.instagram.rate_limit = {};
        currentSettings.instagram.rate_limit.requests_per_hour = parseInt(document.getElementById('rate-hour').value, 10) || 200;
        currentSettings.instagram.rate_limit.requests_per_minute = parseInt(document.getElementById('rate-minute').value, 10) || 20;

        if (!currentSettings.instagram.posting) currentSettings.instagram.posting = {};
        currentSettings.instagram.posting.max_retries = parseInt(document.getElementById('post-retries').value, 10) || 3;
        
        const response = await fetch('/api/config/settings', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(currentSettings)
        });

        if (!response.ok) {
            const errBody = await response.json().catch(() => ({}));
            const msg = Array.isArray(errBody.detail) ? errBody.detail.map(e => e.msg || JSON.stringify(e)).join('; ') : (errBody.detail || 'Failed to save settings');
            throw new Error(msg);
        }

        alert('Settings saved!');
    } catch (error) {
        alert('Error saving settings: ' + error.message);
    }
}

// Comment Settings
async function loadCommentSettings() {
    try {
        const response = await fetch('/api/config/settings');
        const settings = await response.json();
        const comments = settings.comments || {};
        
        document.getElementById('comment-enabled').checked = comments.enabled || false;
        document.getElementById('comment-delay').value = comments.delay_seconds || 30;
        
        if (comments.templates && Array.isArray(comments.templates)) {
            document.getElementById('comment-templates').value = comments.templates.join('\n');
        } else {
            document.getElementById('comment-templates').value = '';
        }
    } catch (error) {
        console.error('Failed to load comment settings:', error);
    }
}

async function saveCommentSettings() {
    try {
        // Fetch current settings first to preserve other sections
        const currentSettingsRes = await fetch('/api/config/settings');
        const currentSettings = await currentSettingsRes.json();
        
        // Prepare comment settings
        const enabled = document.getElementById('comment-enabled').checked;
        const delay = parseInt(document.getElementById('comment-delay').value) || 30;
        const templatesText = document.getElementById('comment-templates').value;
        const templates = templatesText.split('\n').map(t => t.trim()).filter(t => t.length > 0);
        
        // Update settings object
        currentSettings.comments = {
            enabled: enabled,
            delay_seconds: delay,
            templates: templates
        };
        
        // Save
        const response = await fetch('/api/config/settings', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(currentSettings)
        });
        
        if (!response.ok) {
            const errBody = await response.json().catch(() => ({}));
            const msg = Array.isArray(errBody.detail) ? errBody.detail.map(e => e.msg || JSON.stringify(e)).join('; ') : (errBody.detail || 'Failed to save comment settings');
            throw new Error(msg);
        }

        alert('Comment settings saved!');
    } catch (error) {
        alert('Error saving comment settings: ' + error.message);
    }
}

// Account Modal
function showAddAccountModal() {
    const modal = document.getElementById('account-modal');
    modal.style.display = 'block';
    modal.classList.remove('hidden');
    document.getElementById('modal-title').textContent = 'Add Account';
    document.getElementById('acc-mode').value = 'add';
    document.getElementById('account-form').reset();
    document.getElementById('acc-id').disabled = false;
}

function closeAccountModal() {
    const modal = document.getElementById('account-modal');
    modal.style.display = 'none';
    modal.classList.add('hidden');
}

async function saveAccount() {
    const mode = document.getElementById('acc-mode').value;
    const accountId = document.getElementById('acc-id').value;
    const username = document.getElementById('acc-username').value;
    const token = document.getElementById('acc-token').value;
    const warming = document.getElementById('acc-warming').checked;
    
    if (!accountId || !username || !token) {
        alert("Please fill all fields");
        return;
    }

    // Base account object
    let accountData = {
        account_id: accountId,
        username: username,
        access_token: token,
        warming: {
            enabled: warming,
            daily_actions: 10,
            action_types: ["like", "comment"]
        },
        proxy: { enabled: false }
    };

    // If editing, merge with existing data to preserve fields like comment_to_dm
    if (mode === 'edit' && window.currentEditingAccount) {
        accountData = {
            ...window.currentEditingAccount,
            ...accountData,
            // Ensure nested objects are merged carefully if needed, but top-level replacement is mostly what we do here.
            // Exception: comment_to_dm might be in currentEditingAccount but not in the form.
            comment_to_dm: window.currentEditingAccount.comment_to_dm || { enabled: false },
            warming: {
                ...window.currentEditingAccount.warming,
                enabled: warming
            }
        };
    } else {
         // New account default config
         accountData.comment_to_dm = { enabled: false };
    }
    
    // Also capture the new DM Enabled checkbox if we add it
    const dmEnabled = document.getElementById('acc-dm-enabled');
    if (dmEnabled) {
        if (!accountData.comment_to_dm) accountData.comment_to_dm = {};
        accountData.comment_to_dm.enabled = dmEnabled.checked;
    }
    
    try {
        const url = mode === 'add' ? '/api/config/accounts/add' : `/api/config/accounts/${accountId}`;
        const method = mode === 'add' ? 'POST' : 'PUT';
        
        const response = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(accountData)
        });
        
        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || 'Failed to save account');
        }
        
        closeAccountModal();
        loadAccounts();
        alert('Account saved!');
    } catch (error) {
        alert('Error: ' + error.message);
    }
}

async function editAccount(accountId) {
    try {
        const response = await fetch('/api/config/accounts');
        const data = await response.json();
        const account = data.accounts.find(a => a.account_id === accountId);
        
        if (!account) return;
        
        // Store for merging in saveAccount
        window.currentEditingAccount = account;
        
        showAddAccountModal();
        document.getElementById('modal-title').textContent = 'Edit Account';
        document.getElementById('acc-mode').value = 'edit';
        document.getElementById('acc-id').value = account.account_id;
        document.getElementById('acc-id').disabled = true;
        document.getElementById('acc-username').value = account.username;
        document.getElementById('acc-token').value = account.access_token;
        document.getElementById('acc-warming').checked = account.warming?.enabled || false;
        
        // DM Enabled checkbox
        const dmCheckbox = document.getElementById('acc-dm-enabled');
        if (dmCheckbox) {
            dmCheckbox.checked = account.comment_to_dm?.enabled || false;
        }
    } catch (error) {
        console.error('Failed to load account details:', error);
    }
}

async function deleteAccount(accountId) {
    if (!confirm('Are you sure you want to delete this account?')) return;
    
    try {
        const response = await fetch(`/api/config/accounts/${accountId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Failed to delete');
        
        loadAccounts();
    } catch (error) {
        alert('Error deleting account: ' + error.message);
    }
}
