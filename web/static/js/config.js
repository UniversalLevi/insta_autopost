/** Configuration page JavaScript logic */

document.addEventListener('DOMContentLoaded', async () => {
    // Load configurations
    await loadAccountConfig();
    await loadAppSettings();
    
    // App settings form handler
    const appSettingsForm = document.getElementById('appSettingsForm');
    if (appSettingsForm) {
        appSettingsForm.addEventListener('submit', handleAppSettingsSubmit);
    }
});

async function loadAccountConfig() {
    const container = document.getElementById('accountsConfig');
    if (!container) return;
    
    try {
        const response = await apiRequest('/config/accounts');
        
        if (!response || !response.accounts) {
            container.innerHTML = '<p class="error-message">Failed to load account configuration</p>';
            return;
        }
        
        const accounts = response.accounts;
        
        let html = '';
        accounts.forEach(account => {
            const warmingEnabled = account.warming_enabled ? 'checked' : '';
            const actionTypes = account.action_types || [];
            
            html += `
                <div class="account-config-card">
                    <h3>${account.username} (${account.account_id})</h3>
                    
                    <div class="form-section">
                        <label class="checkbox-label">
                            <input type="checkbox" id="warming_${account.account_id}" ${warmingEnabled}>
                            <span>Warming Enabled</span>
                        </label>
                    </div>
                    
                    <div class="form-section">
                        <label class="form-label">Daily Actions</label>
                        <input type="number" id="daily_actions_${account.account_id}" 
                               value="${account.daily_actions}" min="0" class="form-input">
                    </div>
                    
                    <div class="form-section">
                        <label class="form-label">Action Types</label>
                        <div class="checkbox-group">
                            ${['like', 'comment', 'follow', 'story_view'].map(type => `
                                <label class="checkbox-label">
                                    <input type="checkbox" name="action_types_${account.account_id}" 
                                           value="${type}" ${actionTypes.includes(type) ? 'checked' : ''}>
                                    <span>${type}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                    
                    <button type="button" class="btn btn-primary" 
                            onclick="saveAccountConfig('${account.account_id}')">Save Account</button>
                    <div id="status_${account.account_id}" class="status-message" style="display: none;"></div>
                </div>
            `;
        });
        
        container.innerHTML = html;
    } catch (error) {
        console.error('Failed to load account config:', error);
        container.innerHTML = `<p class="error-message">Error loading configuration: ${error.message}</p>`;
    }
}

async function loadAppSettings() {
    try {
        const response = await apiRequest('/config/settings');
        
        if (!response) return;
        
        const scheduleTime = response.warming_schedule_time || '09:00';
        const timeInput = document.getElementById('warming_schedule_time');
        if (timeInput) {
            timeInput.value = scheduleTime;
        }
    } catch (error) {
        console.error('Failed to load app settings:', error);
    }
}

async function saveAccountConfig(accountId) {
    const statusDiv = document.getElementById(`status_${accountId}`);
    
    try {
        const warmingEnabled = document.getElementById(`warming_${accountId}`)?.checked;
        const dailyActions = parseInt(document.getElementById(`daily_actions_${accountId}`)?.value || '0');
        const actionTypeInputs = document.querySelectorAll(`input[name="action_types_${accountId}"]:checked`);
        const actionTypes = Array.from(actionTypeInputs).map(input => input.value);
        
        const body = {
            account_id: accountId,
            warming_enabled: warmingEnabled,
            daily_actions: dailyActions,
            action_types: actionTypes,
        };
        
        const response = await apiRequest('/config/accounts', {
            method: 'PUT',
            body: JSON.stringify(body),
        });
        
        if (response) {
            showStatus(`status_${accountId}`, 'Account configuration saved successfully!', 'success');
        }
    } catch (error) {
        showStatus(`status_${accountId}`, `Error: ${error.message}`, 'error');
    }
}

async function handleAppSettingsSubmit(e) {
    e.preventDefault();
    const statusDiv = document.getElementById('settingsStatus');
    
    try {
        const scheduleTime = document.getElementById('warming_schedule_time')?.value;
        
        if (!scheduleTime) {
            throw new Error('Schedule time is required');
        }
        
        const body = {
            warming_schedule_time: scheduleTime,
        };
        
        const response = await apiRequest('/config/settings', {
            method: 'PUT',
            body: JSON.stringify(body),
        });
        
        if (response) {
            showStatus('settingsStatus', 'Settings saved successfully!', 'success');
        }
    } catch (error) {
        showStatus('settingsStatus', `Error: ${error.message}`, 'error');
    }
}

// Make saveAccountConfig available globally
window.saveAccountConfig = saveAccountConfig;
