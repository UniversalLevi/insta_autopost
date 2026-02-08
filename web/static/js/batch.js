let batchFiles = [];
let batchZipFile = null;

document.addEventListener('DOMContentLoaded', () => {
    loadBatchAccounts();
    setupBatchFileUpload();
    setupBatchZipUpload();
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    const dateStr = tomorrow.toISOString().slice(0, 16);
    const startEl = document.getElementById('batch-start-date');
    if (startEl) startEl.value = dateStr;
});

async function loadBatchAccounts() {
    try {
        const response = await fetch('/api/config/accounts', { credentials: 'include' });
        const data = await response.json();
        const select = document.getElementById('batch-account-select');
        if (!select) return;
        if (!data.accounts || data.accounts.length === 0) {
            select.innerHTML = '<option value="">No accounts found</option>';
            return;
        }
        select.innerHTML = data.accounts.map(acc =>
            `<option value="${acc.account_id}">${acc.username} (${acc.account_id})</option>`
        ).join('');
    } catch (error) {
        console.error('Failed to load accounts for batch upload:', error);
    }
}

function setBatchUploadMethod(method) {
    document.getElementById('batch-upload-method').value = method;
    document.querySelectorAll('#batch-upload-method-buttons button').forEach(btn => {
        if (btn.dataset.method === method) {
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');
        } else {
            btn.classList.add('btn-secondary');
            btn.classList.remove('btn-primary');
        }
    });
    document.getElementById('batch-files-section').classList.toggle('hidden', method !== 'files');
    document.getElementById('batch-zip-section').classList.toggle('hidden', method !== 'zip');
    if (method === 'files') {
        batchZipFile = null;
        const zipInput = document.getElementById('batch-zip-input');
        if (zipInput) zipInput.value = '';
        const zipInfo = document.getElementById('batch-zip-info');
        if (zipInfo) zipInfo.innerHTML = '';
    } else {
        batchFiles = [];
        const fileInput = document.getElementById('batch-file-input');
        if (fileInput) fileInput.value = '';
        updateBatchFileList();
    }
}

function setupBatchFileUpload() {
    const dropZone = document.getElementById('batch-drop-zone');
    const fileInput = document.getElementById('batch-file-input');
    if (!dropZone || !fileInput) return;
    dropZone.onclick = () => fileInput.click();
    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
        dropZone.style.background = 'rgba(220, 38, 38, 0.15)';
    };
    dropZone.ondragleave = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'transparent';
    };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        dropZone.style.background = 'transparent';
        handleBatchFiles(e.dataTransfer.files);
    };
    fileInput.onchange = (e) => handleBatchFiles(e.target.files);
}

function handleBatchFiles(files) {
    const validExts = ['.jpg', '.jpeg', '.png', '.mp4', '.mov', '.webp', '.avi', '.mkv', '.webm'];
    const validFiles = Array.from(files).filter(f => {
        const ext = f.name.toLowerCase();
        return validExts.some(e => ext.endsWith(e));
    });
    if (batchFiles.length + validFiles.length > 31) {
        alert('Maximum 31 files allowed. Some files were not added.');
        validFiles.splice(31 - batchFiles.length);
    }
    batchFiles = [...batchFiles, ...validFiles];
    updateBatchFileList();
}

function updateBatchFileList() {
    const container = document.getElementById('batch-file-list');
    if (!container) return;
    if (batchFiles.length === 0) {
        container.innerHTML = '';
        return;
    }
    container.innerHTML = batchFiles.map((file, index) => `
        <div class="flex items-center gap-2 p-2" style="background: var(--bg-hover); border-radius: 6px; border: 1px solid var(--border);">
            <span class="text-sm truncate flex-1" style="color: var(--text-main);">${file.name}</span>
            <span class="text-sm text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
            <button class="btn btn-danger btn-sm" onclick="removeBatchFile(${index})" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">×</button>
        </div>
    `).join('');
}

function removeBatchFile(index) {
    batchFiles.splice(index, 1);
    updateBatchFileList();
}

function setupBatchZipUpload() {
    const dropZone = document.getElementById('batch-zip-drop-zone');
    const zipInput = document.getElementById('batch-zip-input');
    if (!dropZone || !zipInput) return;
    dropZone.onclick = () => zipInput.click();
    dropZone.ondragover = (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--primary)'; };
    dropZone.ondragleave = (e) => { e.preventDefault(); dropZone.style.borderColor = 'var(--border)'; };
    dropZone.ondrop = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--border)';
        if (e.dataTransfer.files.length) handleBatchZip(e.dataTransfer.files[0]);
    };
    zipInput.onchange = (e) => { if (e.target.files.length) handleBatchZip(e.target.files[0]); };
}

function handleBatchZip(file) {
    if (!file || !file.name.toLowerCase().endsWith('.zip')) {
        alert('Please select a ZIP file.');
        return;
    }
    batchZipFile = file;
    const infoDiv = document.getElementById('batch-zip-info');
    if (infoDiv) infoDiv.innerHTML = `
        <div class="flex items-center gap-2 p-2" style="background: var(--bg-hover); border-radius: 6px; border: 1px solid var(--border);">
            <span class="text-sm" style="color: var(--text-main);">${file.name}</span>
            <span class="text-sm text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
            <button class="btn btn-danger btn-sm" onclick="removeBatchZip()" style="padding: 0.25rem 0.5rem;">×</button>
        </div>
    `;
}

function removeBatchZip() {
    batchZipFile = null;
    const zipInput = document.getElementById('batch-zip-input');
    if (zipInput) zipInput.value = '';
    const infoDiv = document.getElementById('batch-zip-info');
    if (infoDiv) infoDiv.innerHTML = '';
}

async function submitBatchUpload() {
    const accountId = document.getElementById('batch-account-select')?.value;
    if (!accountId) { alert('Please select an account'); return; }
    const method = document.getElementById('batch-upload-method')?.value;
    const startDate = document.getElementById('batch-start-date')?.value;
    const endDate = document.getElementById('batch-end-date')?.value;
    if (!startDate) { alert('Please select a start date'); return; }
    if (endDate && new Date(endDate) <= new Date(startDate)) {
        alert('End date must be after start date');
        return;
    }
    if (method === 'files' && batchFiles.length === 0) {
        alert('Please select at least one file');
        return;
    }
    if (method === 'zip' && !batchZipFile) {
        alert('Please select a ZIP file');
        return;
    }
    const btn = document.getElementById('batch-submit-btn');
    const resultDiv = document.getElementById('batch-result');
    btn.disabled = true;
    btn.textContent = 'Processing...';
    resultDiv.innerHTML = '<div class="text-muted">Processing batch upload...</div>';
    try {
        const formData = new FormData();
        formData.append('account_id', accountId);
        formData.append('start_date', startDate);
        if (endDate) formData.append('end_date', endDate);
        const caption = document.getElementById('batch-caption')?.value;
        if (caption) formData.append('caption', caption);
        const hashtagsInput = document.getElementById('batch-hashtags')?.value || '';
        const hashtags = hashtagsInput.split(/\s+/).filter(h => h.trim());
        hashtags.forEach(tag => formData.append('hashtags', tag));
        if (method === 'files') {
            batchFiles.forEach(file => formData.append('files', file));
        } else {
            formData.append('zip_file', batchZipFile);
        }
        const response = await fetch('/api/batch/upload', { method: 'POST', body: formData, credentials: 'include' });
        const result = await response.json();
        if (!response.ok) throw new Error(result.detail || 'Batch upload failed');
        let message = `Campaign created: ${result.scheduled_count} / ${result.total_files} posts scheduled.`;
        if (result.errors && result.errors.length) message += '\nErrors: ' + result.errors.join('; ');
        resultDiv.innerHTML = `<div class="success-message">${message.replace(/\n/g, '<br>')}</div>`;
        batchFiles = [];
        batchZipFile = null;
        updateBatchFileList();
        removeBatchZip();
        document.getElementById('batch-caption').value = '';
        document.getElementById('batch-hashtags').value = '';
        document.getElementById('batch-end-date').value = '';
    } catch (error) {
        resultDiv.innerHTML = `<div class="error-message">${error.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Schedule Batch Campaign';
    }
}
