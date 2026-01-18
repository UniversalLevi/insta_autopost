/** Published posts viewer page JavaScript logic */

document.addEventListener('DOMContentLoaded', async () => {
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
    
    posts.forEach(post => {
        const card = createPostCard(post);
        grid.appendChild(card);
    });
    
    container.innerHTML = '';
    container.appendChild(grid);
}

function createPostCard(post) {
    const card = document.createElement('div');
    card.className = 'post-card';
    
    const mediaType = post.media_type || 'unknown';
    const caption = post.caption || 'No caption';
    const timestamp = post.timestamp ? formatDate(post.timestamp) : 'Unknown date';
    const permalink = post.permalink || '#';
    
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
            ${permalink !== '#' ? `<a href="${permalink}" target="_blank" class="post-link">View on Instagram</a>` : ''}
        </div>
    `;
    
    return card;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
