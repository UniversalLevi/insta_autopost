let uploadedFiles = [];
let selectedAccounts = [];

document.addEventListener('DOMContentLoaded', () => {
    loadAccounts();
    setupFileUpload();
    setupCaptionCounters();
    toggleAutoDM();  // Show/hide Auto-DM settings based on default (checked)
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
}

// File Upload
function setupFileUpload() {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');

    dropZone.onclick = () => fileInput.click();

    dropZone.ondragover = (e) => {
        e.preventDefault();
        dropZone.style.borderColor = 'var(--primary)';
        dropZone.style.background = '#EFF6FF';
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
                alert('All URLs must be HTTPS. Use Cloudinary, Imgur, S3, etc.');
                return;
            }
            if (/localhost|127\.0\.0\.1|trycloudflare\.com/i.test(u)) {
                alert('Avoid localhost and Cloudflare tunnel URLs. Use a static host (Cloudinary, Imgur, S3).');
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
                    scheduled_time: scheduledTime || null
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
                            trigger_word: dmTrigger || 'AUTO'
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
