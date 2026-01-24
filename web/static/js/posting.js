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
    
    // DM file type toggle
    const dmFileTypeInputs = document.querySelectorAll('input[name="dm_file_type"]');
    dmFileTypeInputs.forEach(input => {
        input.addEventListener('change', handleDmFileTypeChange);
    });
    
    // DM file input handler
    const dmFileInput = document.getElementById('dmFileInput');
    if (dmFileInput) {
        dmFileInput.addEventListener('change', handleDmFileSelect);
    }
    
    // Initial setup
    handleMediaSourceChange();
    handleMediaTypeChange();
    handleDmFileTypeChange();
    
    // Ensure hidden URL inputs never have required attribute
    // This is a safety measure to prevent browser validation errors
    const urlSection = document.getElementById('urlSection');
    if (urlSection && urlSection.style.display === 'none') {
        const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
        urlInputs.forEach(input => {
            input.removeAttribute('required');
            input.required = false;
        });
    }
});

let dmFileData = null; // Store uploaded DM file

function handleDmFileTypeChange() {
    const dmFileType = document.querySelector('input[name="dm_file_type"]:checked')?.value;
    const uploadSection = document.getElementById('dmFileUploadSection');
    const urlSection = document.getElementById('dmFileUrlSection');
    
    if (dmFileType === 'upload') {
        if (uploadSection) uploadSection.style.display = 'block';
        if (urlSection) urlSection.style.display = 'none';
    } else {
        if (uploadSection) uploadSection.style.display = 'none';
        if (urlSection) urlSection.style.display = 'block';
        dmFileData = null; // Clear uploaded file when switching to URL
    }
}

function handleDmFileSelect(e) {
    const file = e.target.files[0];
    if (!file) return;
    
    if (file.type !== 'application/pdf' && !file.name.toLowerCase().endsWith('.pdf')) {
        alert('Please select a PDF file');
        e.target.value = '';
        return;
    }
    
    dmFileData = file;
    
    // Show preview
    const preview = document.getElementById('dmFilePreview');
    const fileName = document.getElementById('dmFileName');
    if (preview && fileName) {
        fileName.textContent = file.name;
        preview.style.display = 'block';
    }
}

function clearDmFile() {
    dmFileData = null;
    const dmFileInput = document.getElementById('dmFileInput');
    if (dmFileInput) dmFileInput.value = '';
    
    const preview = document.getElementById('dmFilePreview');
    if (preview) preview.style.display = 'none';
}

function handleMediaSourceChange() {
    const mediaSource = document.querySelector('input[name="media_source"]:checked')?.value;
    const uploadSection = document.getElementById('uploadSection');
    const urlSection = document.getElementById('urlSection');
    const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
    
    if (mediaSource === 'upload') {
        if (uploadSection) uploadSection.style.display = 'block';
        if (urlSection) urlSection.style.display = 'none';
        // Remove required attribute from ALL URL inputs when section is hidden
        // This is critical to prevent browser validation errors
        urlInputs.forEach(input => {
            input.removeAttribute('required');
            input.required = false;
            // Also set the input to not be required via setAttribute for maximum compatibility
            input.setAttribute('data-was-required', 'false');
        });
    } else {
        if (uploadSection) uploadSection.style.display = 'none';
        if (urlSection) urlSection.style.display = 'block';
        // Only set required on first input when section is visible
        const firstUrlInput = document.querySelector('input[name="media_urls[]"]');
        if (firstUrlInput) {
            firstUrlInput.setAttribute('required', 'required');
            firstUrlInput.required = true;
        }
        // Remove required from additional inputs (carousel will handle this)
        urlInputs.forEach((input, index) => {
            if (index > 0) {
                input.removeAttribute('required');
                input.required = false;
            }
        });
    }
}

function handleMediaTypeChange() {
    const mediaType = document.querySelector('input[name="media_type"]:checked')?.value;
    const addMediaBtn = document.getElementById('addMediaBtn');
    const addMoreFilesBtn = document.getElementById('addMoreFilesBtn');
    
    // Carousel requires 2+ files - show/hide Add More Files button
    if (mediaType === 'carousel') {
        if (addMoreFilesBtn) {
            addMoreFilesBtn.style.display = 'inline-block';
        }
    } else {
        // For single media types, hide "Add More Files" initially
        // (but show if user already has multiple files)
        if (uploadedFiles.length <= 1 && addMoreFilesBtn) {
            addMoreFilesBtn.style.display = 'none';
        }
    }
    
    // Validate carousel has enough files
    if (mediaType === 'carousel' && uploadedFiles.length === 1) {
        const statusDiv = document.getElementById('postStatus');
        if (statusDiv) {
            showStatus('postStatus', '⚠️ Carousel requires 2-10 files. You have 1 file. Please add more files or select "Image"/"Video" instead.', 'warning');
        }
    }
    const mediaUrlsContainer = document.getElementById('mediaUrlsContainer');
    
    // For URL inputs
    if (mediaUrlsContainer) {
        const existingInputs = mediaUrlsContainer.querySelectorAll('input[type="url"]');
        const urlSection = document.getElementById('urlSection');
        const isUrlSectionVisible = urlSection && 
            urlSection.style.display !== 'none' && 
            window.getComputedStyle(urlSection).display !== 'none';
        
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
            
            // ALWAYS check visibility and update required attribute accordingly
            // Remove required if section is hidden to prevent browser validation errors
            if (isUrlSectionVisible) {
                firstInput.setAttribute('required', 'required');
                firstInput.required = true;
            } else {
                firstInput.removeAttribute('required');
                firstInput.required = false;
            }
        }
        
        // Also ensure all URL inputs (including dynamically added ones) respect visibility
        const allUrlInputs = mediaUrlsContainer.querySelectorAll('input[type="url"]');
        if (!isUrlSectionVisible) {
            allUrlInputs.forEach(input => {
                input.removeAttribute('required');
                input.required = false;
            });
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
    
    // Update UI based on file count and media type
    const mediaType = document.querySelector('input[name="media_type"]:checked')?.value;
    const addMoreFilesBtn = document.getElementById('addMoreFilesBtn');
    
    if (mediaType === 'carousel') {
        // Always show Add More Files for carousel
        if (addMoreFilesBtn) addMoreFilesBtn.style.display = 'inline-block';
        
        // Warn if only 1 file for carousel
        if (uploadedFiles.length === 1) {
            const statusDiv = document.getElementById('postStatus');
            if (statusDiv) {
                showStatus('postStatus', '⚠️ Carousel requires 2-10 files. Currently have 1. Add more files or select "Image"/"Video".', 'warning');
            }
        }
    } else if (uploadedFiles.length > 1) {
        // Multiple files but not carousel - suggest carousel
        const statusDiv = document.getElementById('postStatus');
        if (statusDiv && mediaType !== 'carousel') {
            showStatus('postStatus', `ℹ️ You have ${uploadedFiles.length} file(s). Select "Carousel" to post all of them, or remove files to post as single ${mediaType}.`, 'info');
        }
        if (addMoreFilesBtn) addMoreFilesBtn.style.display = 'inline-block';
    }
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
    
    // Check if URL section is visible before adding required attribute
    const urlSection = document.getElementById('urlSection');
    const isUrlSectionVisible = urlSection && urlSection.style.display !== 'none';
    
    const input = document.createElement('input');
    input.type = 'url';
    input.name = 'media_urls[]';
    input.className = 'form-input';
    input.placeholder = 'https://example.com/image.jpg';
    // Only set required if URL section is visible
    if (isUrlSectionVisible) {
        input.required = true;
    }
    
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
    
    // ALWAYS remove required attribute from URL inputs if URL section is hidden
    // This prevents browser validation errors for hidden required fields
    const urlSection = document.getElementById('urlSection');
    const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
    
    // Check if URL section is actually visible (not just display:none, but also check computed style)
    const isUrlSectionVisible = urlSection && 
        urlSection.style.display !== 'none' && 
        window.getComputedStyle(urlSection).display !== 'none';
    
    if (!isUrlSectionVisible) {
        // Remove required from all URL inputs when section is hidden
        urlInputs.forEach(input => {
            input.removeAttribute('required');
            input.required = false;
        });
    } else {
        // Even if visible, only require the first input (for single media types)
        // Additional inputs for carousel should not be required
        urlInputs.forEach((input, index) => {
            if (index === 0) {
                // Keep required on first input if section is visible
                input.required = true;
            } else {
                // Remove required from additional inputs
                input.removeAttribute('required');
                input.required = false;
            }
        });
    }
    
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
        
        // Validate carousel requires 2-10 files
        if (mediaType === 'carousel') {
            if (mediaSource === 'upload') {
                if (uploadedFiles.length < 2) {
                    throw new Error('Carousel posts require 2-10 files. You have ' + uploadedFiles.length + '. Please add more files or select "Image"/"Video" instead.');
                }
                if (uploadedFiles.length > 10) {
                    throw new Error('Carousel posts can have maximum 10 files. You have ' + uploadedFiles.length + '. Please remove ' + (uploadedFiles.length - 10) + ' file(s).');
                }
            } else {
                // URL mode - validate URLs
                const urlInputs = document.querySelectorAll('input[name="media_urls[]"]');
                const validUrls = Array.from(urlInputs).map(input => input.value.trim()).filter(url => url);
                if (validUrls.length < 2) {
                    throw new Error('Carousel posts require 2-10 media URLs. You have ' + validUrls.length + '. Please add more URLs or select "Image"/"Video" instead.');
                }
                if (validUrls.length > 10) {
                    throw new Error('Carousel posts can have maximum 10 media URLs. You have ' + validUrls.length + '. Please remove ' + (validUrls.length - 10) + ' URL(s).');
                }
            }
        } else {
            // Single media types should have exactly 1 file/URL
            if (mediaSource === 'upload' && uploadedFiles.length > 1) {
                throw new Error(mediaType.charAt(0).toUpperCase() + mediaType.slice(1) + ' posts require exactly 1 file. You have ' + uploadedFiles.length + '. Select "Carousel" to post all files, or remove ' + (uploadedFiles.length - 1) + ' file(s).');
            }
        }
        
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
        
        // Collect DM file info
        const dmFileType = document.querySelector('input[name="dm_file_type"]:checked')?.value;
        let dmFilePath = null;
        
        if (dmFileType === 'upload' && dmFileData) {
            // Upload PDF file first
            showStatus('postStatus', 'Uploading DM file...', 'info');
            const dmFormData = new FormData();
            dmFormData.append('files', dmFileData);
            
            try {
                const dmUploadResponse = await fetch('/api/upload', {
                    method: 'POST',
                    credentials: 'include',
                    body: dmFormData,
                });
                
                if (dmUploadResponse.ok) {
                    const dmResult = await dmUploadResponse.json();
                    if (dmResult.urls && dmResult.urls.length > 0) {
                        dmFilePath = dmResult.urls[0].url;
                    }
                }
            } catch (error) {
                console.warn('DM file upload failed, will use local path if provided:', error);
                // Continue with post creation even if DM file upload fails
            }
        } else {
            // Use file path/URL
            const dmPathInput = document.getElementById('dm_file_path');
            dmFilePath = dmPathInput ? dmPathInput.value.trim() : null;
        }
        
        // Create post request
        const postData = {
            media_type: mediaType,
            urls: urls,
            caption: caption,
            hashtags: hashtags,
            account_id: accountId,
        };
        
        // Create post
        showStatus('postStatus', 'Creating post...', 'info');
        const response = await apiRequest('/posts/create', {
            method: 'POST',
            body: JSON.stringify(postData),
        });
        
        if (!response) {
            throw new Error('Failed to create post');
        }
        
        // Attach DM file to the post if provided
        if (dmFilePath && response.instagram_media_id) {
            try {
                showStatus('postStatus', 'Attaching DM file to post...', 'info');
                await apiRequest(
                    `/comment-to-dm/post/${response.instagram_media_id}/file?account_id=${accountId}`,
                    {
                        method: 'POST',
                        body: JSON.stringify({
                            file_url: dmFilePath.startsWith('http://') || dmFilePath.startsWith('https://') ? dmFilePath : null,
                            file_path: !dmFilePath.startsWith('http') ? dmFilePath : null,
                        }),
                    }
                );
                showStatus('postStatus', `Post created and DM file attached! Comments will trigger auto-DM.`, 'success');
            } catch (error) {
                console.error('Failed to attach DM file:', error);
                showStatus('postStatus', `Post created successfully! (DM file attachment failed: ${error.message})`, 'warning');
            }
        } else {
            if (dmFilePath) {
                showStatus('postStatus', `Post created! Note: DM file will be attached once post is published.`, 'info');
            } else {
                showStatus('postStatus', `Post created successfully! Post ID: ${response.post_id}`, 'success');
            }
        }
        
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
            dmFileData = null;
            const uploadedFilesContainer = document.getElementById('uploadedFiles');
            if (uploadedFilesContainer) uploadedFilesContainer.innerHTML = '';
            const dmFilePreview = document.getElementById('dmFilePreview');
            if (dmFilePreview) dmFilePreview.style.display = 'none';
            handleMediaSourceChange();
            handleDmFileTypeChange();
        }, 3000);
        
    } catch (error) {
        showStatus('postStatus', `Error: ${error.message}`, 'error');
    } finally {
        if (submitBtn) submitBtn.disabled = false;
    }
}
