/** Posting page JavaScript logic */

let accounts = [];
let uploadedFiles = [];
let uploadedFileUrls = []; // Store URLs after upload

document.addEventListener('DOMContentLoaded', async () => {
    // Load accounts
    accounts = await loadAccounts();
    const accountSelect = document.getElementById('account_id');
    if (accountSelect && accounts.length > 0) {
        accountSelect.innerHTML = accounts.map(acc => 
            `<option value="${acc.account_id}">${acc.username}</option>`
        ).join('');
        if (accounts.length === 1) {
            accountSelect.value = accounts[0].account_id;
        }
    }
    
    // Media source toggle
    const mediaSourceInputs = document.querySelectorAll('input[name="media_source"]');
    mediaSourceInputs.forEach(input => {
        input.addEventListener('change', handleMediaSourceChange);
    });
    
    // Media type change handler
    const mediaTypeInputs = document.querySelectorAll('input[name="media_type"]');
    mediaTypeInputs.forEach(input => {
        input.addEventListener('change', handleMediaTypeChange);
    });
    
    // Caption character counter
    const captionInput = document.getElementById('caption');
    const charCount = document.getElementById('charCount');
    if (captionInput && charCount) {
        captionInput.addEventListener('input', () => {
            charCount.textContent = captionInput.value.length;
        });
    }
    
    // File input handler
    const fileInput = document.getElementById('fileInput');
    if (fileInput) {
        fileInput.addEventListener('change', handleFileSelect);
    }
    
    // Drag and drop handlers
    const dropZone = document.getElementById('dropZone');
    if (dropZone) {
        dropZone.addEventListener('dragover', handleDragOver);
        dropZone.addEventListener('dragleave', handleDragLeave);
        dropZone.addEventListener('drop', handleDrop);
        dropZone.addEventListener('click', () => fileInput?.click());
    }
    
    // Add more files button
    const addMoreFilesBtn = document.getElementById('addMoreFilesBtn');
    if (addMoreFilesBtn) {
        addMoreFilesBtn.addEventListener('click', () => fileInput?.click());
    }
    
    // Add media button (for URL input)
    const addMediaBtn = document.getElementById('addMediaBtn');
    if (addMediaBtn) {
        addMediaBtn.addEventListener('click', addMediaUrlInput);
    }
    
    // Form submit handler
    const postForm = document.getElementById('postForm');
    if (postForm) {
        postForm.addEventListener('submit', handleFormSubmit);
    }
    
    // Initial setup
    handleMediaSourceChange();
    handleMediaTypeChange();
});

function handleMediaSourceChange() {
    const mediaSource = document.querySelector('input[name="media_source"]:checked')?.value;
    const uploadSection = document.getElementById('uploadSection');
    const urlSection = document.getElementById('urlSection');
    const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
    
    if (mediaSource === 'upload') {
        if (uploadSection) uploadSection.style.display = 'block';
        if (urlSection) urlSection.style.display = 'none';
        urlInputs.forEach(input => input.removeAttribute('required'));
    } else {
        if (uploadSection) uploadSection.style.display = 'none';
        if (urlSection) urlSection.style.display = 'block';
        const firstUrlInput = document.querySelector('input[name="media_urls[]"]');
        if (firstUrlInput) firstUrlInput.setAttribute('required', 'required');
    }
}

function handleMediaTypeChange() {
    const mediaType = document.querySelector('input[name="media_type"]:checked')?.value;
    const addMediaBtn = document.getElementById('addMediaBtn');
    const addMoreFilesBtn = document.getElementById('addMoreFilesBtn');
    const mediaUrlsContainer = document.getElementById('mediaUrlsContainer');
    
    // For URL inputs
    if (mediaUrlsContainer) {
        const existingInputs = mediaUrlsContainer.querySelectorAll('input[type="url"]');
        if (existingInputs.length > 1) {
            for (let i = 1; i < existingInputs.length; i++) {
                existingInputs[i].remove();
            }
        }
        
        if (mediaType === 'carousel') {
            if (addMediaBtn) addMediaBtn.style.display = 'block';
            if (existingInputs.length === 1) {
                addMediaUrlInput();
            }
        } else {
            if (addMediaBtn) addMediaBtn.style.display = 'none';
        }
        
        const firstInput = mediaUrlsContainer.querySelector('input[type="url"]');
        if (firstInput) {
            if (mediaType === 'reels') {
                firstInput.placeholder = 'https://example.com/video.mp4 (Video URL for Reels)';
            } else if (mediaType === 'video') {
                firstInput.placeholder = 'https://example.com/video.mp4 (Video URL)';
            } else {
                firstInput.placeholder = 'https://example.com/image.jpg (Image URL)';
            }
        }
    }
    
    // For file uploads
    if (mediaType === 'carousel') {
        if (addMoreFilesBtn) addMoreFilesBtn.style.display = 'block';
    } else {
        if (addMoreFilesBtn) addMoreFilesBtn.style.display = 'none';
    }
}

function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.add('drag-over');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.remove('drag-over');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    const dropZone = document.getElementById('dropZone');
    if (dropZone) dropZone.classList.remove('drag-over');
    
    const files = Array.from(e.dataTransfer.files);
    processFiles(files);
}

function handleFileSelect(e) {
    const files = Array.from(e.target.files);
    processFiles(files);
    e.target.value = ''; // Reset input to allow selecting same file again
}

function processFiles(files) {
    const validFiles = files.filter(file => {
        const isImage = file.type.startsWith('image/');
        const isVideo = file.type.startsWith('video/');
        return isImage || isVideo;
    });
    
    if (validFiles.length === 0) {
        alert('Please select image or video files only.');
        return;
    }
    
    validFiles.forEach(file => {
        if (!uploadedFiles.find(f => f.name === file.name && f.size === file.size)) {
            uploadedFiles.push(file);
            displayUploadedFile(file);
        }
    });
}

function displayUploadedFile(file) {
    const container = document.getElementById('uploadedFiles');
    if (!container) return;
    
    const item = document.createElement('div');
    item.className = 'uploaded-file-item';
    item.dataset.fileName = file.name;
    
    const preview = document.createElement(file.type.startsWith('image/') ? 'img' : 'video');
    preview.className = 'uploaded-file-preview';
    if (preview.tagName === 'IMG') {
        preview.src = URL.createObjectURL(file);
        preview.alt = file.name;
    } else {
        preview.src = URL.createObjectURL(file);
        preview.controls = true;
    }
    
    const info = document.createElement('div');
    info.className = 'uploaded-file-info';
    
    const name = document.createElement('div');
    name.className = 'uploaded-file-name';
    name.textContent = file.name;
    
    const size = document.createElement('div');
    size.className = 'uploaded-file-size';
    size.textContent = formatFileSize(file.size);
    
    info.appendChild(name);
    info.appendChild(size);
    
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'uploaded-file-remove';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', () => {
        const index = uploadedFiles.findIndex(f => f.name === file.name && f.size === file.size);
        if (index > -1) {
            uploadedFiles.splice(index, 1);
            const urlIndex = uploadedFileUrls.findIndex(url => url.originalName === file.name);
            if (urlIndex > -1) uploadedFileUrls.splice(urlIndex, 1);
        }
        item.remove();
        URL.revokeObjectURL(preview.src);
    });
    
    item.appendChild(preview);
    item.appendChild(info);
    item.appendChild(removeBtn);
    container.appendChild(item);
}

function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
}

function addMediaUrlInput() {
    const container = document.getElementById('mediaUrlsContainer');
    if (!container) return;
    
    const input = document.createElement('input');
    input.type = 'url';
    input.name = 'media_urls[]';
    input.className = 'form-input';
    input.placeholder = 'https://example.com/image.jpg';
    input.required = true;
    
    const wrapper = document.createElement('div');
    wrapper.className = 'media-url-wrapper';
    wrapper.appendChild(input);
    
    const removeBtn = document.createElement('button');
    removeBtn.type = 'button';
    removeBtn.className = 'btn btn-small btn-danger';
    removeBtn.textContent = 'Remove';
    removeBtn.addEventListener('click', () => wrapper.remove());
    wrapper.appendChild(removeBtn);
    
    container.appendChild(wrapper);
}

async function uploadFilesToServer() {
    if (uploadedFiles.length === 0) return [];
    
    showStatus('postStatus', 'Uploading files...', 'info');
    
    const formData = new FormData();
    uploadedFiles.forEach(file => {
        formData.append('files', file);
    });
    
    try {
        const response = await fetch('/api/upload', {
            method: 'POST',
            credentials: 'include',
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'File upload failed');
        }
        
        const result = await response.json();
        uploadedFileUrls = result.urls || [];
        return uploadedFileUrls.map(u => u.url);
    } catch (error) {
        console.error('File upload error:', error);
        throw error;
    }
}

async function handleFormSubmit(e) {
    e.preventDefault();
    
    const submitBtn = document.getElementById('submitBtn');
    const statusDiv = document.getElementById('postStatus');
    
    if (submitBtn) submitBtn.disabled = true;
    showStatus('postStatus', 'Processing...', 'info');
    
    try {
        // Collect form data
        const mediaType = document.querySelector('input[name="media_type"]:checked')?.value;
        const accountId = document.getElementById('account_id')?.value;
        const caption = document.getElementById('caption')?.value || '';
        const hashtagsInput = document.getElementById('hashtags')?.value || '';
        const publishNow = document.getElementById('publish_now')?.checked ?? true;
        const mediaSource = document.querySelector('input[name="media_source"]:checked')?.value;
        
        let urls = [];
        
        // Handle file uploads
        if (mediaSource === 'upload') {
            if (uploadedFiles.length === 0) {
                throw new Error('Please upload at least one file');
            }
            
            urls = await uploadFilesToServer();
            if (urls.length === 0) {
                throw new Error('Failed to upload files');
            }
        } else {
            // Handle URL inputs
            const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
            urls = Array.from(urlInputs).map(input => input.value.trim()).filter(url => url);
            
            if (urls.length === 0) {
                throw new Error('At least one media URL is required');
            }
        }
        
        // Parse hashtags
        const hashtags = hashtagsInput.split(',')
            .map(tag => tag.trim().replace('#', ''))
            .filter(tag => tag);
        
        // Create post request
        const postData = {
            media_type: mediaType,
            urls: urls,
            caption: caption,
            hashtags: hashtags,
            account_id: accountId,
        };
        
        // Create post
        const response = await apiRequest('/posts/create', {
            method: 'POST',
            body: JSON.stringify(postData),
        });
        
        if (!response) {
            throw new Error('Failed to create post');
        }
        
        showStatus('postStatus', `Post created successfully! Post ID: ${response.post_id}`, 'success');
        
        // If publish now, publish the post
        if (publishNow && response.post_id) {
            showStatus('postStatus', 'Publishing post...', 'info');
            // Note: API endpoint for publishing needs post storage - for now just show created message
            showStatus('postStatus', 'Post created. Note: Publishing requires post storage implementation.', 'warning');
        }
        
        // Reset form after success
        setTimeout(() => {
            document.getElementById('postForm')?.reset();
            document.getElementById('charCount').textContent = '0';
            uploadedFiles = [];
            uploadedFileUrls = [];
            const uploadedFilesContainer = document.getElementById('uploadedFiles');
            if (uploadedFilesContainer) uploadedFilesContainer.innerHTML = '';
            handleMediaSourceChange();
        }, 3000);
        
    } catch (error) {
        showStatus('postStatus', `Error: ${error.message}`, 'error');
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}
