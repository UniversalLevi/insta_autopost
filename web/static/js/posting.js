let uploadedFiles = [];
let selectedAccounts = [];

document.addEventListener('DOMContentLoaded', () => {
    loadAccounts();
    setupFileUpload();
    setupCaptionCounters();
    toggleAutoDM();  // Show/hide Auto-DM settings based on default (checked)
    setupBatchUpload();  // Setup batch upload functionality
});

// Accounts
async function loadAccounts() {
    try {
        const response = await fetch('/api/config/accounts');
        const data = await response.json();
        const container = document.getElementById('account-selector');
        
        if (!data.accounts || data.accounts.length === 0) {
            container.innerHTML = '<div class="text-muted">No accounts found. Go to Settings to add one.</div>';
            return;
        }

        container.innerHTML = data.accounts.map(acc => `
            <label class="card flex items-center gap-2 p-2 cursor-pointer hover:bg-gray-50" style="padding: 0.75rem; border: 1px solid var(--border); margin: 0;">
                <input type="checkbox" name="account" value="${acc.account_id}" onchange="updateSelectedAccounts()">
                <div>
                    <div class="font-medium">${acc.username}</div>
                    <div class="text-sm text-muted">${acc.account_id}</div>
                </div>
            </label>
        `).join('');
    } catch (error) {
        console.error('Failed to load accounts:', error);
        document.getElementById('account-selector').innerHTML = '<div class="text-error">Failed to load accounts</div>';
    }
}

function updateSelectedAccounts() {
    selectedAccounts = Array.from(document.querySelectorAll('input[name="account"]:checked')).map(cb => cb.value);
}

function togglePostByUrl() {
    const useUrl = document.getElementById('post-by-url-toggle').checked;
    document.getElementById('post-by-url-section').classList.toggle('hidden', !useUrl);
    document.getElementById('upload-section').classList.toggle('hidden', useUrl);
    if (useUrl) {
        uploadedFiles = [];
        updateFileList();
    }
    updateVideoUrlWarning();
}

function updateVideoUrlWarning() {
    const mediaType = document.getElementById('media-type').value;
    const postByUrl = document.getElementById('post-by-url-toggle').checked;
    const warning = document.getElementById('video-url-warning');
    
    if (warning) {
        if (postByUrl && (mediaType === 'video' || mediaType === 'reels')) {
            warning.style.display = 'block';
        } else {
            warning.style.display = 'none';
        }
    }
}

// Media Type
function setMediaType(type) {
    document.getElementById('media-type').value = type;
    
    // Update buttons
    document.querySelectorAll('#media-type-buttons button').forEach(btn => {
        if (btn.dataset.type === type) {
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');
        } else {
            btn.classList.add('btn-secondary');
            btn.classList.remove('btn-primary');
        }
    });
    
    // Update video URL warning
    updateVideoUrlWarning();
    
    // Show Video & Reels note when Video or Reels is selected (same flow as posts: upload from device)
    const videoReelsNote = document.getElementById('video-reels-note');
    if (videoReelsNote) {
        videoReelsNote.style.display = (type === 'video' || type === 'reels') ? 'block' : 'none';
    }
}

// File Upload
function setupFileUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

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
        handleFiles(e.dataTransfer.files);
    };

    fileInput.onchange = (e) => handleFiles(e.target.files);
}

function handleFiles(files) {
    const newFiles = Array.from(files);
    // Validate types
    const validFiles = newFiles.filter(f => f.type.startsWith('image/') || f.type.startsWith('video/'));
    
    if (validFiles.length < newFiles.length) {
        alert('Some files were ignored. Only images and videos are allowed.');
    }

    uploadedFiles = [...uploadedFiles, ...validFiles];
    updateFileList();
}

function updateFileList() {
    const container = document.getElementById('file-list');
    
    if (uploadedFiles.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = uploadedFiles.map((file, index) => `
        <div class="flex items-center gap-2 p-2 bg-gray-50 border rounded">
            <span class="text-sm font-medium truncate flex-1">${file.name}</span>
            <span class="text-sm text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
            <button class="btn btn-danger btn-sm" onclick="removeFile(${index})" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">×</button>
        </div>
    `).join('');
}

function removeFile(index) {
    uploadedFiles.splice(index, 1);
    updateFileList();
}

// Caption
function setupCaptionCounters() {
    const caption = document.getElementById('caption');
    const charCount = document.getElementById('char-count');
    const hashCount = document.getElementById('hashtag-count');

    caption.oninput = () => {
        const text = caption.value;
        charCount.textContent = `${text.length} / 2200`;
        
        const hashtags = (text.match(/#[a-zA-Z0-9_]+/g) || []).length;
        hashCount.textContent = `${hashtags} / 30 hashtags`;
        
        if (text.length > 2200) charCount.classList.add('text-error');
        else charCount.classList.remove('text-error');
        
        if (hashtags > 30) hashCount.classList.add('text-error');
        else hashCount.classList.remove('text-error');
    };
}

// Auto DM
function toggleAutoDM() {
    const toggle = document.getElementById('auto-dm-toggle');
    const settings = document.getElementById('auto-dm-settings');
    if (toggle.checked) {
        settings.classList.remove('hidden');
    } else {
        settings.classList.add('hidden');
    }
}

// Submit
async function submitPost() {
    if (selectedAccounts.length === 0) {
        alert('Please select at least one account');
        return;
    }

    const mediaType = document.getElementById('media-type').value;
    const postByUrl = document.getElementById('post-by-url-toggle').checked;
    let urls = [];

    if (postByUrl) {
        const raw = (document.getElementById('media-urls').value || '').trim();
        urls = raw.split(/\n/).map(s => s.trim()).filter(Boolean);
        if (urls.length === 0) {
            alert('Enter at least one public HTTPS media URL (one per line).');
            return;
        }
        for (const u of urls) {
            if (!u.startsWith('https://')) {
                alert('All URLs must be HTTPS. For your own server, ensure BASE_URL is set to your public HTTPS domain.');
                return;
            }
            // Check if URL is from same origin (own server) - allow it
            try {
                const urlObj = new URL(u);
                const currentHost = window.location.hostname;
                const urlHost = urlObj.hostname;
                const isSameOrigin = urlHost === currentHost || urlHost.endsWith('.' + currentHost) || currentHost.endsWith('.' + urlHost);
                
                // If same-origin, allow it (no blocking)
                if (isSameOrigin) {
                    continue;
                }
            } catch (e) {
                // Invalid URL format, continue to check below
            }
            
            // Block localhost/tunnel URLs (use Upload Media instead so file goes to your server)
            if (/localhost|127\.0\.0\.1|trycloudflare\.com|ngrok/i.test(u)) {
                alert('Use "Upload Media" above to upload from your device — the file will be stored on your server and published to Instagram.');
                return;
            }
        }
        if (mediaType === 'carousel' && urls.length < 2) {
            alert('Carousel requires at least 2 URLs.');
            return;
        }
        if (mediaType !== 'carousel' && urls.length > 1) {
            alert(`Single ${mediaType} post can only have 1 URL. Use Carousel for multiple.`);
            return;
        }
    } else {
        if (uploadedFiles.length === 0) {
            alert('Please upload media or enable "Post by URL" and add URLs.');
            return;
        }
        if (mediaType === 'carousel' && uploadedFiles.length < 2) {
            alert('Carousel requires at least 2 files');
            return;
        }
        if (mediaType !== 'carousel' && uploadedFiles.length > 1) {
            alert(`Single ${mediaType} post can only have 1 file. Use Carousel for multiple.`);
            return;
        }
    }

    const btn = document.getElementById('submit-btn');
    btn.disabled = true;
    btn.textContent = postByUrl ? 'Posting...' : 'Uploading media...';

    try {
        if (!postByUrl) {
            const formData = new FormData();
            uploadedFiles.forEach(f => formData.append('files', f));
            const uploadRes = await fetch('/api/upload', { method: 'POST', body: formData });
            if (!uploadRes.ok) throw new Error('Upload failed');
            const uploadData = await uploadRes.json();
            urls = uploadData.urls.map(u => u.url);
        }

        // 2. Prepare Post Data
        const caption = document.getElementById('caption').value;
        const scheduledTime = document.getElementById('scheduled-time').value;
        
        // Auto DM Data
        const autoDM = document.getElementById('auto-dm-toggle').checked;
        const dmLink = document.getElementById('dm-link').value;
        const dmTrigger = document.getElementById('dm-trigger').value;
        const aiReplies = document.getElementById('auto-dm-ai-toggle')?.checked ?? false;

        // 3. Post for each account
        btn.textContent = 'Posting...';
        let successCount = 0;
        let errors = [];

        const POST_TIMEOUT_MS = 180000;

        for (const accountId of selectedAccounts) {
            try {
                const postData = {
                    account_id: accountId,
                    media_type: mediaType,
                    urls: urls,
                    caption: caption,
                    scheduled_time: scheduledTime || null,
                    // Include Auto-DM config (will be stored with scheduled post if scheduled)
                    auto_dm_enabled: autoDM || false,
                    auto_dm_link: dmLink || null,
                    auto_dm_mode: dmTrigger ? 'KEYWORD' : 'AUTO',
                    auto_dm_trigger: dmTrigger || null,
                    auto_dm_ai_enabled: aiReplies || false
                };

                const ac = new AbortController();
                const timeoutId = setTimeout(() => ac.abort(), POST_TIMEOUT_MS);

                let postRes;
                try {
                    postRes = await fetch('/api/posts/create', {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify(postData),
                        signal: ac.signal
                    });
                } catch (fetchErr) {
                    clearTimeout(timeoutId);
                    if (fetchErr.name === 'AbortError') {
                        throw new Error('Post is taking longer than usual. Instagram may still be processing. Check History or try again.');
                    }
                    throw fetchErr;
                }
                clearTimeout(timeoutId);

                if (!postRes.ok) {
                    const err = await postRes.json();
                    throw new Error(err.detail || 'Post failed');
                }

                const postResult = await postRes.json();

                // 4. Configure Auto DM if enabled
                if (autoDM && dmLink && postResult.instagram_media_id) {
                    await fetch(`/api/comment-to-dm/post/${postResult.instagram_media_id}/file?account_id=${accountId}`, {
                        method: 'POST',
                        headers: {'Content-Type': 'application/json'},
                        body: JSON.stringify({
                            file_url: dmLink,
                            trigger_mode: dmTrigger ? 'KEYWORD' : 'AUTO',
                            trigger_word: dmTrigger || 'AUTO',
                            ai_enabled: aiReplies || false
                        })
                    });
                }

                successCount++;
            } catch (err) {
                console.error(`Account ${accountId} error:`, err);
                errors.push(`${accountId}: ${err.message}`);
            }
        }

        // 5. Result
        let msg = `Successfully posted to ${successCount} accounts.`;
        if (errors.length > 0) {
            msg += `\nErrors:\n${errors.join('\n')}`;
        }
        
        alert(msg);
        
        if (successCount === selectedAccounts.length) {
            uploadedFiles = [];
            updateFileList();
            document.getElementById('caption').value = '';
            document.getElementById('scheduled-time').value = '';
            if (document.getElementById('post-by-url-toggle').checked) {
                document.getElementById('media-urls').value = '';
            }
        }

    } catch (error) {
        alert('Error: ' + error.message);
    } finally {
        btn.disabled = false;
        btn.textContent = 'Post Now';
    }
}

// ========== Batch Upload (30 Days) Functions ==========

let batchFiles = [];
let batchZipFile = null;

async function loadBatchAccounts() {
    try {
        const response = await fetch('/api/config/accounts');
        const data = await response.json();
        const select = document.getElementById('batch-account-select');
        
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
    
    // Update buttons
    document.querySelectorAll('#batch-upload-method-buttons button').forEach(btn => {
        if (btn.dataset.method === method) {
            btn.classList.remove('btn-secondary');
            btn.classList.add('btn-primary');
        } else {
            btn.classList.add('btn-secondary');
            btn.classList.remove('btn-primary');
        }
    });
    
    // Toggle sections
    document.getElementById('batch-files-section').classList.toggle('hidden', method !== 'files');
    document.getElementById('batch-zip-section').classList.toggle('hidden', method !== 'zip');
    
    // Clear selections when switching
    if (method === 'files') {
        batchZipFile = null;
        document.getElementById('batch-zip-input').value = '';
        document.getElementById('batch-zip-info').innerHTML = '';
    } else {
        batchFiles = [];
        document.getElementById('batch-file-input').value = '';
        updateBatchFileList();
    }
}

function setupBatchUpload() {
    loadBatchAccounts();
    setupBatchFileUpload();
    setupBatchZipUpload();
    
    // Set default start date to tomorrow at 9 AM
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);
    tomorrow.setHours(9, 0, 0, 0);
    const dateStr = tomorrow.toISOString().slice(0, 16);
    document.getElementById('batch-start-date').value = dateStr;
}

function setupBatchFileUpload() {
    const dropZone = document.getElementById('batch-drop-zone');
    const fileInput = document.getElementById('batch-file-input');

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
    const newFiles = Array.from(files);
    const validFiles = newFiles.filter(f => {
        const ext = f.name.toLowerCase();
        return ext.endsWith('.jpg') || ext.endsWith('.jpeg') || ext.endsWith('.png') || 
               ext.endsWith('.mp4') || ext.endsWith('.mov') || ext.endsWith('.webp') ||
               ext.endsWith('.avi') || ext.endsWith('.mkv') || ext.endsWith('.webm');
    });
    
    if (validFiles.length < newFiles.length) {
        const skippedCount = newFiles.length - validFiles.length;
        // Only show alert if significant number of files were skipped
        if (skippedCount > 0 && newFiles.length > 1) {
            console.warn(`${skippedCount} file(s) were skipped. Only JPG, PNG, MP4, MOV, WEBP, AVI, MKV, WEBM are allowed.`);
        }
    }
    
    if (batchFiles.length + validFiles.length > 31) {
        alert('Maximum 31 files allowed. Some files were not added.');
        validFiles.splice(31 - batchFiles.length);
    }
    
    batchFiles = [...batchFiles, ...validFiles];
    updateBatchFileList();
}

function updateBatchFileList() {
    const container = document.getElementById('batch-file-list');
    
    if (batchFiles.length === 0) {
        container.innerHTML = '';
        return;
    }

    container.innerHTML = batchFiles.map((file, index) => `
        <div class="flex items-center gap-2 p-2 bg-gray-50 border rounded">
            <span class="text-sm font-medium truncate flex-1">${file.name}</span>
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

    dropZone.onclick = () => zipInput.click();

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
        handleBatchZip(e.dataTransfer.files[0]);
    };

    zipInput.onchange = (e) => {
        if (e.target.files.length > 0) {
            handleBatchZip(e.target.files[0]);
        }
    };
}

function handleBatchZip(file) {
    if (!file.name.toLowerCase().endsWith('.zip')) {
        alert('Please select a ZIP file.');
        return;
    }
    
    batchZipFile = file;
    const infoDiv = document.getElementById('batch-zip-info');
    infoDiv.innerHTML = `
        <div class="flex items-center gap-2 p-2 bg-gray-50 border rounded">
            <span class="text-sm font-medium">${file.name}</span>
            <span class="text-sm text-muted">${(file.size / 1024 / 1024).toFixed(2)} MB</span>
            <button class="btn btn-danger btn-sm" onclick="removeBatchZip()" style="padding: 0.25rem 0.5rem; font-size: 0.75rem;">×</button>
        </div>
    `;
}

function removeBatchZip() {
    batchZipFile = null;
    document.getElementById('batch-zip-input').value = '';
    document.getElementById('batch-zip-info').innerHTML = '';
}

async function submitBatchUpload() {
    const accountId = document.getElementById('batch-account-select').value;
    if (!accountId) {
        alert('Please select an account');
        return;
    }

    const method = document.getElementById('batch-upload-method').value;
    const startDate = document.getElementById('batch-start-date').value;
    const endDate = document.getElementById('batch-end-date').value;
    
    if (!startDate) {
        alert('Please select a start date');
        return;
    }

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

    if (method === 'files' && batchFiles.length > 31) {
        alert('Maximum 31 files allowed');
        return;
    }

    const btn = document.getElementById('batch-submit-btn');
    btn.disabled = true;
    btn.textContent = 'Processing...';

    const resultDiv = document.getElementById('batch-result');
    resultDiv.innerHTML = '<div class="text-muted">Processing batch upload...</div>';

    try {
        const formData = new FormData();
        formData.append('account_id', accountId);
        formData.append('start_date', startDate);
        
        if (endDate) {
            formData.append('end_date', endDate);
        }
        
        const caption = document.getElementById('batch-caption').value;
        if (caption) {
            formData.append('caption', caption);
        }
        
        const hashtagsInput = document.getElementById('batch-hashtags').value;
        if (hashtagsInput) {
            // Parse hashtags (space-separated)
            const hashtags = hashtagsInput.split(/\s+/).filter(h => h.trim());
            if (hashtags.length > 0) {
                hashtags.forEach(tag => formData.append('hashtags', tag));
            }
        }

        if (method === 'files') {
            batchFiles.forEach(file => formData.append('files', file));
        } else {
            formData.append('zip_file', batchZipFile);
        }

        const response = await fetch('/api/batch/upload', {
            method: 'POST',
            body: formData,
        });

        const result = await response.json();

        if (!response.ok) {
            throw new Error(result.detail || 'Batch upload failed');
        }

        // Show success message
        let message = `✅ Campaign created successfully!\n\n`;
        message += `Campaign ID: ${result.campaign_id}\n`;
        message += `Scheduled: ${result.scheduled_count} / ${result.total_files} posts\n`;
        message += `Start Date: ${startDate}\n`;
        
        if (result.errors && result.errors.length > 0) {
            message += `\n⚠️ Errors:\n${result.errors.join('\n')}`;
        }

        resultDiv.innerHTML = `
            <div class="p-4 bg-green-50 border border-green-200 rounded">
                <h4 class="font-medium text-green-800">Batch Campaign Created</h4>
                <p class="text-sm text-green-700 mt-2">${message.replace(/\n/g, '<br>')}</p>
            </div>
        `;

        // Clear form
        batchFiles = [];
        batchZipFile = null;
        updateBatchFileList();
        removeBatchZip();
        document.getElementById('batch-caption').value = '';
        document.getElementById('batch-hashtags').value = '';
        document.getElementById('batch-end-date').value = '';

    } catch (error) {
        resultDiv.innerHTML = `
            <div class="p-4 bg-red-50 border border-red-200 rounded">
                <h4 class="font-medium text-red-800">Error</h4>
                <p class="text-sm text-red-700 mt-2">${error.message}</p>
            </div>
        `;
    } finally {
        btn.disabled = false;
        btn.textContent = 'Schedule Batch Campaign';
    }
}
