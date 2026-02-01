// File Browser Module
class FileBrowser {
    constructor() {
        this.currentPath = null; // Will be set based on form type
        this.currentFormType = null; // 'upload' or 'download'
        this.modal = document.getElementById('file-browser-modal');
        this.fileList = document.getElementById('file-list');
        this.currentPathText = document.getElementById('current-path-text');
        this.projectRoot = null; // Will be fetched from server
        
        this.initEventListeners();
        this.fetchProjectRoot();
    }

    async fetchProjectRoot() {
        try {
            const response = await fetch('/get_config/');
            if (response.ok) {
                const config = await response.json();
                // Use translate_folder as default, or extract project root from it
                this.projectRoot = config.translate_folder || config.download_folder || '/tmp';
                console.log('FileBrowser: Project root set to:', this.projectRoot);
            }
        } catch (error) {
            console.error('FileBrowser: Failed to fetch project root:', error);
            this.projectRoot = '/tmp';
        }
    }

    initEventListeners() {
        // Open browser buttons
        document.getElementById('browse-btn-upload').addEventListener('click', () => {
            this.currentFormType = 'upload';
            this.open();
        });
        
        document.getElementById('browse-btn-download').addEventListener('click', () => {
            this.currentFormType = 'download';
            this.open();
        });

        // Close modal
        document.getElementById('close-browser').addEventListener('click', () => this.close());
        document.getElementById('cancel-select').addEventListener('click', () => this.close());
        
        // Click outside to close
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });

        // Navigation buttons
        document.getElementById('go-parent').addEventListener('click', () => this.goToParent());
        document.getElementById('refresh-browser').addEventListener('click', () => this.loadDirectory(this.currentPath));
        
        // New folder
        document.getElementById('new-folder-btn').addEventListener('click', () => this.showNewFolderInput());
        document.getElementById('create-folder-btn').addEventListener('click', () => this.createFolder());
        document.getElementById('cancel-folder-btn').addEventListener('click', () => this.hideNewFolderInput());
        
        // Confirm selection
        document.getElementById('confirm-select').addEventListener('click', () => this.confirmSelection());
        
        // Enter key in new folder input
        document.getElementById('new-folder-name').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') {
                this.createFolder();
            }
        });
    }

    open(path = null) {
        // If no path specified, use the default path based on form type
        console.log('FileBrowser: Opening browser for form type:', this.currentFormType);
        console.log('FileBrowser: defaultPaths:', window.defaultPaths);
        console.log('FileBrowser: projectRoot:', this.projectRoot);
        
        if (path === null) {
            // Use defaultPaths from config, fallback to projectRoot
            const fallback = this.projectRoot || '/tmp';
            if (this.currentFormType === 'upload') {
                path = window.defaultPaths?.translate_folder || fallback;
            } else if (this.currentFormType === 'download') {
                path = window.defaultPaths?.download_folder || fallback;
            } else {
                path = fallback;
            }
        }
        
        console.log('FileBrowser: Using path:', path);
        this.currentPath = path;
        this.modal.classList.add('show');
        this.loadDirectory(path);
    }

    close() {
        this.modal.classList.remove('show');
        this.hideNewFolderInput();
    }

    async loadDirectory(path) {
        this.fileList.innerHTML = '<div class="loading">Loading...</div>';
        
        try {
            console.log('FileBrowser: Loading directory:', path);
            
            const formData = new FormData();
            formData.append('path', path);
            
            console.log('FileBrowser: Sending request to /browse_directory/');
            
            const response = await fetch('/browse_directory/', {
                method: 'POST',
                body: formData
            });
            
            console.log('FileBrowser: Response status:', response.status);
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error('FileBrowser: Error response:', errorText);
                let errorMsg = 'Failed to load directory';
                try {
                    const errorJson = JSON.parse(errorText);
                    errorMsg = errorJson.error || errorMsg;
                } catch (e) {
                    errorMsg = errorText || errorMsg;
                }
                throw new Error(errorMsg);
            }
            
            const data = await response.json();
            console.log('FileBrowser: Loaded', data.items.length, 'items');
            
            this.currentPath = data.current_path;
            this.currentPathText.textContent = this.currentPath;
            
            this.renderFileList(data.items);
            
        } catch (error) {
            console.error('FileBrowser: Error loading directory:', error);
            this.fileList.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
            showNotification(`Error loading directory: ${error.message}`, 'error');
        }
    }

    renderFileList(items) {
        if (items.length === 0) {
            this.fileList.innerHTML = '<div class="loading">Empty directory</div>';
            return;
        }

        // Sort: directories first, then files
        const sorted = items.sort((a, b) => {
            if (a.is_directory && !b.is_directory) return -1;
            if (!a.is_directory && b.is_directory) return 1;
            return a.name.localeCompare(b.name);
        });

        this.fileList.innerHTML = sorted.map(item => {
            const icon = item.is_directory ? '📁' : '📄';
            const sizeText = item.is_directory ? '' : this.formatSize(item.size);
            
            return `
                <div class="file-item" data-path="${item.path}" data-is-dir="${item.is_directory}">
                    <div class="file-icon">${icon}</div>
                    <div class="file-info">
                        <div class="file-name">${item.name}</div>
                        ${sizeText ? `<div class="file-meta">${sizeText}</div>` : ''}
                    </div>
                    ${item.is_directory ? `
                        <div class="file-actions">
                            <button class="file-action-btn delete-btn" data-path="${item.path}" title="Delete">🗑️</button>
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');

        // Add click listeners
        this.fileList.querySelectorAll('.file-item').forEach(item => {
            item.addEventListener('click', (e) => {
                // Don't trigger if clicking delete button
                if (e.target.closest('.delete-btn')) {
                    return;
                }
                
                const path = item.dataset.path;
                const isDir = item.dataset.isDir === 'true';
                
                if (isDir) {
                    // Double click to enter directory
                    if (item.classList.contains('selected')) {
                        this.loadDirectory(path);
                    } else {
                        // Single click to select
                        this.fileList.querySelectorAll('.file-item').forEach(i => i.classList.remove('selected'));
                        item.classList.add('selected');
                    }
                }
            });
        });

        // Add delete button listeners
        this.fileList.querySelectorAll('.delete-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                const path = btn.dataset.path;
                this.deleteFolder(path);
            });
        });
    }

    formatSize(bytes) {
        if (bytes === 0) return '0 B';
        const k = 1024;
        const sizes = ['B', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
    }

    goToParent() {
        const parent = this.currentPath.split('/').slice(0, -1).join('/') || '/';
        this.loadDirectory(parent);
    }

    showNewFolderInput() {
        document.getElementById('new-folder-section').style.display = 'flex';
        document.getElementById('new-folder-name').focus();
    }

    hideNewFolderInput() {
        document.getElementById('new-folder-section').style.display = 'none';
        document.getElementById('new-folder-name').value = '';
    }

    async createFolder() {
        const name = document.getElementById('new-folder-name').value.trim();
        
        if (!name) {
            showNotification('Please enter a folder name', 'error');
            return;
        }

        // Validate folder name
        if (name.includes('/') || name.includes('\\')) {
            showNotification('Folder name cannot contain / or \\', 'error');
            return;
        }

        try {
            const formData = new FormData();
            formData.append('path', this.currentPath);
            formData.append('name', name);
            
            const response = await fetch('/create_directory/', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to create folder');
            }
            
            showNotification('Folder created successfully', 'success');
            this.hideNewFolderInput();
            this.loadDirectory(this.currentPath);
            
        } catch (error) {
            showNotification(`Error: ${error.message}`, 'error');
        }
    }

    async deleteFolder(path) {
        if (!confirm(`Are you sure you want to delete this folder?\n${path}\n\nNote: Only empty folders can be deleted.`)) {
            return;
        }

        try {
            const formData = new FormData();
            formData.append('path', path);
            
            const response = await fetch('/delete_directory/', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to delete folder');
            }
            
            showNotification('Folder deleted successfully', 'success');
            this.loadDirectory(this.currentPath);
            
        } catch (error) {
            showNotification(`Error: ${error.message}`, 'error');
        }
    }

    confirmSelection() {
        const displayId = `output-path-display-${this.currentFormType}`;
        const hiddenId = `output-path-${this.currentFormType}`;
        
        document.getElementById(displayId).value = this.currentPath;
        document.getElementById(hiddenId).value = this.currentPath;
        
        // Update summary after path selection
        if (this.currentFormType === 'upload' && typeof updateUploadSummary === 'function') {
            updateUploadSummary();
        } else if (this.currentFormType === 'download' && typeof updateDownloadSummary === 'function') {
            updateDownloadSummary();
        }
        
        showNotification(`Output path set to: ${this.currentPath}`, 'success');
        this.close();
    }
}

// Initialize file browser when DOM is loaded
let fileBrowser;
document.addEventListener('DOMContentLoaded', () => {
    fileBrowser = new FileBrowser();
});
