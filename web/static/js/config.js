document.addEventListener('DOMContentLoaded', () => {
    loadAccounts();
    loadSettings();
    loadCommentSettings();
    loadGlobalProxy();
});

// Accounts
async function loadAccounts() {
    const list = document.getElementById('accounts-list');
    list.innerHTML = '<div class="text-muted">Loading...</div>';

    try {
        const response = await fetch('/api/config/accounts', { credentials: 'include' });
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
                        ${acc.warming && acc.warming.enabled ? '<span class="badge badge-info" style="background: rgba(59, 130, 246, 0.15); color: #93C5FD; border: 1px solid rgba(59, 130, 246, 0.3);">Warming On</span>' : '<span class="text-muted">Warming Off</span>'}
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
        loadGlobalProxyFromSettings(settings);
    } catch (error) {
        console.error('Failed to load settings:', error);
    }
}

async function loadGlobalProxy() {
    try {
        const response = await fetch('/api/config/settings');
        const settings = await response.json();
        loadGlobalProxyFromSettings(settings);
    } catch (error) {
        console.error('Failed to load global proxy:', error);
    }
}

function loadGlobalProxyFromSettings(settings) {
    const dp = settings.proxies?.default_proxy;
    const enabledEl = document.getElementById('global-proxy-enabled');
    const protocolEl = document.getElementById('global-proxy-protocol');
    const proxyEl = document.getElementById('global-proxy');
    if (enabledEl) enabledEl.checked = dp?.enabled || false;
    if (protocolEl) protocolEl.value = dp?.protocol || 'socks5';
    if (proxyEl && dp?.host && dp?.port) {
        proxyEl.value = dp.username && dp.password
            ? `${dp.host}:${dp.port}:${dp.username}:${dp.password}`
            : `${dp.host}:${dp.port}`;
    } else if (proxyEl) proxyEl.value = '';
}

async function saveGlobalProxy() {
    try {
        const currentSettingsRes = await fetch('/api/config/settings');
        const currentSettings = await currentSettingsRes.json();
        const enabled = document.getElementById('global-proxy-enabled')?.checked || false;
        const protocol = document.getElementById('global-proxy-protocol')?.value || 'socks5';
        const proxyStr = (document.getElementById('global-proxy')?.value || '').trim();
        if (!currentSettings.proxies) currentSettings.proxies = {};
        if (!currentSettings.proxies.default_proxy) currentSettings.proxies.default_proxy = {};
        if (enabled && proxyStr) {
            const parts = proxyStr.split(':');
            if (parts.length >= 4) {
                currentSettings.proxies.default_proxy = {
                    enabled: true,
                    host: parts[0],
                    port: parseInt(parts[1], 10) || 80,
                    username: parts[2],
                    password: parts.slice(3).join(':'),
                    protocol: protocol,
                };
            } else {
                alert('Proxy format must be host:port:username:password');
                return;
            }
        } else {
            currentSettings.proxies.default_proxy = {
                enabled: enabled,
                host: null,
                port: null,
                username: null,
                password: null,
                protocol: protocol,
            };
        }
        const response = await fetch('/api/config/settings', {
            method: 'PUT',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(currentSettings)
        });
        if (!response.ok) {
            const errBody = await response.json().catch(() => ({}));
            throw new Error(errBody.detail || 'Failed to save proxy');
        }
        alert('Global proxy saved!');
    } catch (error) {
        alert('Error saving proxy: ' + error.message);
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
    const dmEl = document.getElementById('acc-dm-enabled');
    if (dmEl) dmEl.checked = true;  // Default Auto-DM on for new accounts
    const proxyCheck = document.getElementById('acc-proxy-enabled');
    if (proxyCheck) proxyCheck.checked = false;
    const proxyInp = document.getElementById('acc-proxy');
    if (proxyInp) proxyInp.value = '';
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
    const passwordEl = document.getElementById('acc-password');
    const password = passwordEl ? passwordEl.value.trim() : '';
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
    if (password) accountData.password = password;

    // If editing, merge with existing data to preserve fields like comment_to_dm
    if (mode === 'edit' && window.currentEditingAccount) {
        accountData = {
            ...window.currentEditingAccount,
            ...accountData,
            comment_to_dm: window.currentEditingAccount.comment_to_dm || { enabled: false },
            warming: {
                ...window.currentEditingAccount.warming,
                enabled: warming
            }
        };
        if (!password) delete accountData.password;
    } else {
         // New account default config (Auto-DM on by default)
         accountData.comment_to_dm = { enabled: true };
    }
    
    const dmEnabled = document.getElementById('acc-dm-enabled');
    const dmLinkEl = document.getElementById('acc-dm-link');
    if (dmEnabled) {
        if (!accountData.comment_to_dm) accountData.comment_to_dm = {};
        accountData.comment_to_dm.enabled = dmEnabled.checked;
        if (dmLinkEl) accountData.comment_to_dm.link_to_send = (dmLinkEl.value || '').trim() || null;
    }
    const aiDmEnabled = document.getElementById('acc-ai-dm-enabled');
    if (aiDmEnabled) {
        if (!accountData.ai_dm) accountData.ai_dm = {};
        accountData.ai_dm.enabled = aiDmEnabled.checked;
        if (accountData.ai_dm.auto_send === undefined) accountData.ai_dm.auto_send = true;
    }

    // Proxy: parse host:port:username:password
    const proxyEnabled = document.getElementById('acc-proxy-enabled')?.checked || false;
    const proxyStr = (document.getElementById('acc-proxy')?.value || '').trim();
    if (proxyEnabled && proxyStr) {
        const parts = proxyStr.split(':');
        if (parts.length >= 4) {
            accountData.proxy = {
                enabled: true,
                host: parts[0],
                port: parseInt(parts[1], 10) || 80,
                username: parts[2],
                password: parts.slice(3).join(':')
            };
        } else {
            alert('Proxy format must be host:port:username:password (at least 4 parts)');
            return;
        }
    } else {
        accountData.proxy = { enabled: false, host: null, port: null, username: null, password: null };
    }
    
    try {
        const url = mode === 'add' ? '/api/config/accounts/add' : `/api/config/accounts/${accountId}`;
        const method = mode === 'add' ? 'POST' : 'PUT';
        
        const response = await fetch(url, {
            method: method,
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(accountData),
            credentials: 'include'
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
        const response = await fetch('/api/config/accounts', { credentials: 'include' });
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
        const passwordInput = document.getElementById('acc-password');
        if (passwordInput) {
            passwordInput.value = '';
            passwordInput.placeholder = 'Leave blank to keep current password';
        }
        document.getElementById('acc-warming').checked = account.warming?.enabled || false;

        const proxyCheckbox = document.getElementById('acc-proxy-enabled');
        const proxyInput = document.getElementById('acc-proxy');
        if (proxyCheckbox) proxyCheckbox.checked = account.proxy?.enabled || false;
        if (proxyInput) {
            const p = account.proxy;
            if (p && p.enabled && p.host && p.port) {
                proxyInput.value = p.username && p.password
                    ? `${p.host}:${p.port}:${p.username}:${p.password}`
                    : `${p.host}:${p.port}`;
            } else {
                proxyInput.value = '';
            }
        }
        
        const dmCheckbox = document.getElementById('acc-dm-enabled');
        if (dmCheckbox) dmCheckbox.checked = account.comment_to_dm?.enabled || false;
        const dmLinkInput = document.getElementById('acc-dm-link');
        if (dmLinkInput) dmLinkInput.value = account.comment_to_dm?.link_to_send || '';
        const aiDmCheckbox = document.getElementById('acc-ai-dm-enabled');
        if (aiDmCheckbox) aiDmCheckbox.checked = account.ai_dm?.enabled !== false;
    } catch (error) {
        console.error('Failed to load account details:', error);
    }
}

async function deleteAccount(accountId) {
    if (!confirm('Are you sure you want to delete this account?')) return;
    
    try {
        const response = await fetch(`/api/config/accounts/${accountId}`, {
            method: 'DELETE',
            credentials: 'include'
        });
        
        if (!response.ok) throw new Error('Failed to delete');
        
        loadAccounts();
    } catch (error) {
        alert('Error deleting account: ' + error.message);
    }
}
