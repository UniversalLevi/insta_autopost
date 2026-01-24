/** Published posts viewer page JavaScript logic */

let currentAccountId = null;
let currentMediaId = null;

document.addEventListener('DOMContentLoaded', async () => {
    // Load account info
    await loadAccountInfo();
    
    // Load published posts
    await loadPublishedPosts();
    
    // Refresh button
    const refreshBtn = document.getElementById('refreshBtn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', () => {
            loadPublishedPosts();
        });
    }
});

async function loadAccountInfo() {
    try {
        const accounts = await apiRequest('/config/accounts');
        if (accounts && accounts.accounts && accounts.accounts.length > 0) {
            const account = accounts.accounts[0];
            currentAccountId = account.account_id;
            const accountInfo = document.getElementById('accountInfo');
            if (accountInfo) {
                accountInfo.textContent = `Account: ${account.username}`;
            }
        }
    } catch (error) {
        console.error('Failed to load account info:', error);
    }
}

async function loadPublishedPosts() {
    const container = document.getElementById('postsContainer');
    const loadingIndicator = document.getElementById('loadingIndicator');
    
    if (!container) return;
    
    if (loadingIndicator) loadingIndicator.style.display = 'block';
    
    try {
        const response = await apiRequest('/posts/published?limit=50');
        
        if (!response) {
            container.innerHTML = '<p class="empty-state">No published posts available</p>';
            return;
        }
        
        if (response.posts && response.posts.length > 0) {
            displayPosts(response.posts);
        } else {
            container.innerHTML = '<p class="empty-state">No published posts found</p>';
        }
    } catch (error) {
        console.error('Failed to load published posts:', error);
        container.innerHTML = `<p class="error-message">Error loading posts: ${error.message}</p>`;
    } finally {
        if (loadingIndicator) loadingIndicator.style.display = 'none';
    }
}

function displayPosts(posts) {
    const container = document.getElementById('postsContainer');
    if (!container) return;
    
    if (posts.length === 0) {
        container.innerHTML = '<p class="empty-state">No posts found</p>';
        return;
    }
    
    const grid = document.createElement('div');
    grid.className = 'posts-grid';
    
    for (const post of posts) {
        const card = await createPostCard(post);
        grid.appendChild(card);
    }
    
    container.innerHTML = '';
    container.appendChild(grid);
}

async function createPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    
    const mediaType = post.media_type || 'unknown';
    const caption = post.caption || 'No caption';
    const timestamp = post.timestamp ? formatDate(post.timestamp) : 'Unknown date';
    const permalink = post.permalink || '#';
    const mediaId = post.id;
    
    // Check if file is attached for this post
    let hasFile = false;
    let attachedFileUrl = null;
    if (currentAccountId && mediaId) {
        try {
            const fileInfo = await apiRequest(`/comment-to-dm/post/${mediaId}/file?account_id=${currentAccountId}`);
            hasFile = fileInfo && fileInfo.has_file;
            attachedFileUrl = fileInfo && fileInfo.file_url;
        } catch (error) {
            console.error('Failed to check file:', error);
        }
    }
    
    card.innerHTML = `
        <div class="post-card-header">
            <span class="post-type-badge post-type-${mediaType.toLowerCase()}">${mediaType.toUpperCase()}</span>
            <span class="post-date">${timestamp}</span>
        </div>
        <div class="post-card-body">
            <div class="post-preview">
                <span class="post-preview-placeholder">Media Preview</span>
            </div>
            <div class="post-caption">
                <p>${escapeHtml(caption.length > 100 ? caption.substring(0, 100) + '...' : caption)}</p>
            </div>
        </div>
        <div class="post-card-footer">
            <div class="post-id">ID: ${post.id}</div>
            <div style="display: flex; gap: 0.5rem; margin-top: 0.5rem; align-items: center;">
                ${permalink !== '#' ? `<a href="${permalink}" target="_blank" class="post-link" style="flex: 1;">View on Instagram</a>` : ''}
                <button onclick="openAttachFileModal('${mediaId}')" class="btn btn-secondary" style="padding: 0.25rem 0.75rem; font-size: 0.875rem;">
                    ${hasFile ? '📎 File Attached' : '📎 Attach File'}
                </button>
            </div>
            ${hasFile && attachedFileUrl ? `<div style="margin-top: 0.5rem; padding: 0.5rem; background: #f0f9ff; border-radius: 4px; font-size: 0.875rem; color: #0369a1;">
                <strong>Auto-DM File:</strong> ${attachedFileUrl.substring(0, 50)}${attachedFileUrl.length > 50 ? '...' : ''}
            </div>` : ''}
        </div>
    `;
    
    return card;
}

async function openAttachFileModal(mediaId) {
    currentMediaId = mediaId;
    const modal = document.getElementById('attachFileModal');
    const filePathInput = document.getElementById('filePathInput');
    const removeFileBtn = document.getElementById('removeFileBtn');
    
    if (modal) {
        modal.style.display = 'block';
        filePathInput.value = '';
        
        // Load current file if exists
        try {
            const fileInfo = await apiRequest(`/comment-to-dm/post/${mediaId}/file?account_id=${currentAccountId}`);
            if (fileInfo && fileInfo.file_url) {
                filePathInput.value = fileInfo.file_url;
                removeFileBtn.style.display = 'inline-block';
            } else {
                removeFileBtn.style.display = 'none';
            }
        } catch (error) {
            console.error('Failed to load file info:', error);
            removeFileBtn.style.display = 'none';
        }
    }
}

function closeAttachFileModal() {
    const modal = document.getElementById('attachFileModal');
    if (modal) {
        modal.style.display = 'none';
    }
    currentMediaId = null;
}

async function savePostDMFile() {
    const filePathInput = document.getElementById('filePathInput');
    const statusDiv = document.getElementById('attachFileStatus');
    
    if (!filePathInput || !filePathInput.value.trim()) {
        showStatus(statusDiv, 'Please enter a file path or URL', 'error');
        return;
    }
    
    const filePath = filePathInput.value.trim();
    
    try {
        const result = await apiRequest(
            `/comment-to-dm/post/${currentMediaId}/file?account_id=${currentAccountId}`,
            {
                method: 'POST',
                body: JSON.stringify({
                    file_path: filePath.startsWith('file:///') || filePath.match(/^[A-Za-z]:/) ? filePath : null,
                    file_url: filePath.startsWith('http://') || filePath.startsWith('https://') ? filePath : null,
                }),
            }
        );
        
        if (result && result.status === 'success') {
            showStatus(statusDiv, 'File attached successfully! Comments on this post will trigger DM with this file.', 'success');
            setTimeout(() => {
                closeAttachFileModal();
                loadPublishedPosts(); // Reload to show updated status
            }, 1500);
        }
    } catch (error) {
        showStatus(statusDiv, `Error: ${error.message || 'Failed to save file'}`, 'error');
    }
}

async function removePostDMFile() {
    const statusDiv = document.getElementById('attachFileStatus');
    
    try {
        const result = await apiRequest(
            `/comment-to-dm/post/${currentMediaId}/file?account_id=${currentAccountId}`,
            {
                method: 'DELETE',
            }
        );
        
        if (result && result.status === 'success') {
            showStatus(statusDiv, 'File removed successfully', 'success');
            setTimeout(() => {
                closeAttachFileModal();
                loadPublishedPosts(); // Reload to show updated status
            }, 1500);
        }
    } catch (error) {
        showStatus(statusDiv, `Error: ${error.message || 'Failed to remove file'}`, 'error');
    }
}

function showStatus(element, message, type) {
    if (!element) return;
    element.textContent = message;
    element.className = `status-message ${type}`;
    element.style.display = 'block';
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
