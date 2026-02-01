// API endpoints - use relative URLs to avoid CORS issues
const ENDPOINTS = {
    translate: '/translate_pdf/',
    getFiles: '/get_files/',
    downloadFile: '/download_file/',
    clearTemp: '/clear_temp_dir/',
    getConfig: '/get_config/',
    browseDirectory: '/browse_directory/',
    createDirectory: '/create_directory/',
    deleteDirectory: '/delete_directory/',
    getTranslatorConfig: '/get_translator_config/',
    setTranslatorConfig: '/set_translator_config/',
    fetchModels: '/fetch_models/'
};

// Store default paths (use window to make it globally accessible)
window.defaultPaths = {
    download_folder: '/tmp',
    translate_folder: '/tmp'
};

// Utility functions
function showNotification(message, type = 'info') {
    const notification = document.getElementById('notification');
    notification.textContent = message;
    notification.className = `notification ${type} show`;
    
    setTimeout(() => {
        notification.classList.remove('show');
    }, 5000);
}

function toggleSpinner(button, show) {
    const btnText = button.querySelector('.btn-text');
    const spinner = button.querySelector('.spinner');
    
    if (show) {
        btnText.style.display = 'none';
        spinner.style.display = 'block';
        button.disabled = true;
    } else {
        btnText.style.display = 'block';
        spinner.style.display = 'none';
        button.disabled = false;
    }
}

// Tab switching
document.querySelectorAll('.tab-button').forEach(button => {
    button.addEventListener('click', () => {
        const tabName = button.dataset.tab;
        
        // Update active tab button
        document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
        button.classList.add('active');
        
        // Update active tab content
        document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
        document.getElementById(`${tabName}-tab`).classList.add('active');
        
        // Auto-refresh results when switching to results tab
        if (tabName === 'results') {
            refreshResults();
        }
    });
});

// File input handler
document.getElementById('file-input').addEventListener('change', (e) => {
    const fileName = e.target.files[0]?.name || 'No file selected';
    document.getElementById('file-name').textContent = fileName;
});

// Page range toggle for upload form
document.getElementById('translate-all-upload').addEventListener('change', (e) => {
    document.getElementById('page-range-upload').style.display = e.target.checked ? 'none' : 'grid';
});

// Page range toggle for download form
document.getElementById('translate-all-download').addEventListener('change', (e) => {
    document.getElementById('page-range-download').style.display = e.target.checked ? 'none' : 'grid';
});

// Use temp path toggle for upload form
document.getElementById('use-temp-path-upload').addEventListener('change', (e) => {
    const displayInput = document.getElementById('output-path-display-upload');
    const hiddenInput = document.getElementById('output-path-upload');
    const browseBtn = document.getElementById('browse-btn-upload');
    const customCheckbox = document.getElementById('custom-output-path-upload');
    
    if (e.target.checked) {
        // Use temp path
        customCheckbox.checked = false;
        browseBtn.disabled = true;
        displayInput.value = window.defaultPaths.temp_dir || '/tmp';
        hiddenInput.value = window.defaultPaths.temp_dir || '/tmp';
    } else {
        // Use default path
        displayInput.value = window.defaultPaths.translate_folder;
        hiddenInput.value = '';
    }
    updateUploadSummary();
});

// Custom output path toggle for upload form
document.getElementById('custom-output-path-upload').addEventListener('change', (e) => {
    const displayInput = document.getElementById('output-path-display-upload');
    const hiddenInput = document.getElementById('output-path-upload');
    const tempCheckbox = document.getElementById('use-temp-path-upload');
    
    if (e.target.checked) {
        // Enable custom path - load from config
        tempCheckbox.checked = false;
        displayInput.value = window.defaultPaths.translate_folder;
        hiddenInput.value = window.defaultPaths.translate_folder;
    } else {
        // Use default path
        displayInput.value = window.defaultPaths.translate_folder;
        hiddenInput.value = '';
    }
    updateUploadSummary();
});

// Use temp path toggle for download form
document.getElementById('use-temp-path-download').addEventListener('change', (e) => {
    const displayInput = document.getElementById('output-path-display-download');
    const hiddenInput = document.getElementById('output-path-download');
    const browseBtn = document.getElementById('browse-btn-download');
    const customCheckbox = document.getElementById('custom-output-path-download');
    
    if (e.target.checked) {
        // Use temp path
        customCheckbox.checked = false;
        browseBtn.disabled = true;
        displayInput.value = window.defaultPaths.temp_dir || '/tmp';
        hiddenInput.value = window.defaultPaths.temp_dir || '/tmp';
    } else {
        // Use default path
        displayInput.value = window.defaultPaths.download_folder;
        hiddenInput.value = '';
    }
    updateDownloadSummary();
});

// Custom output path toggle for download form
document.getElementById('custom-output-path-download').addEventListener('change', (e) => {
    const displayInput = document.getElementById('output-path-display-download');
    const hiddenInput = document.getElementById('output-path-download');
    const tempCheckbox = document.getElementById('use-temp-path-download');
    
    if (e.target.checked) {
        // Enable custom path - load from config
        tempCheckbox.checked = false;
        displayInput.value = window.defaultPaths.download_folder;
        hiddenInput.value = window.defaultPaths.download_folder;
    } else {
        // Use default path
        displayInput.value = window.defaultPaths.download_folder;
        hiddenInput.value = '';
    }
    updateDownloadSummary();
});

// ============ Summary Update Functions ============

function updateUploadSummary() {
    // Source file
    const fileInput = document.getElementById('file-input');
    const fileName = fileInput.files[0]?.name || 'No file selected';
    document.getElementById('summary-source-upload').textContent = fileName;
    
    // Output path
    const outputPath = document.getElementById('output-path-display-upload').value || '-';
    document.getElementById('summary-output-upload').textContent = outputPath;
    
    // Language
    const fromLang = document.getElementById('from-lang-upload').value;
    const toLang = document.getElementById('to-lang-upload').value;
    document.getElementById('summary-lang-upload').textContent = `${fromLang} → ${toLang}`;
    
    // Model info
    const provider = document.getElementById('current-provider')?.textContent || '-';
    const model = document.getElementById('current-model')?.textContent || '-';
    document.getElementById('summary-model-upload').textContent = provider !== '-' ? `${provider} / ${model}` : '-';
    
    // Page range
    const translateAll = document.getElementById('translate-all-upload').checked;
    if (translateAll) {
        document.getElementById('summary-pages-upload').textContent = 'All pages';
    } else {
        const from = document.getElementById('from-page-upload').value || 0;
        const to = document.getElementById('to-page-upload').value || 0;
        document.getElementById('summary-pages-upload').textContent = `Pages ${from} - ${to}`;
    }
    
    // Render mode
    const renderMode = document.getElementById('render-mode-upload').value;
    const renderModeText = renderMode.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    document.getElementById('summary-render-upload').textContent = renderModeText;
    
    // Add blank page
    const addBlank = document.getElementById('add-blank-page-upload').checked;
    document.getElementById('summary-blank-upload').textContent = addBlank ? 'Yes' : 'No';
}

function updateDownloadSummary() {
    // Source URL
    const url = document.getElementById('pdf-url').value || 'No URL entered';
    const displayUrl = url.length > 50 ? url.substring(0, 50) + '...' : url;
    document.getElementById('summary-source-download').textContent = displayUrl;
    
    // Output path
    const outputPath = document.getElementById('output-path-display-download').value || '-';
    document.getElementById('summary-output-download').textContent = outputPath;
    
    // Language
    const fromLang = document.getElementById('from-lang-download').value;
    const toLang = document.getElementById('to-lang-download').value;
    document.getElementById('summary-lang-download').textContent = `${fromLang} → ${toLang}`;
    
    // Model info
    const provider = document.getElementById('current-provider')?.textContent || '-';
    const model = document.getElementById('current-model')?.textContent || '-';
    document.getElementById('summary-model-download').textContent = provider !== '-' ? `${provider} / ${model}` : '-';
    
    // Page range
    const translateAll = document.getElementById('translate-all-download').checked;
    if (translateAll) {
        document.getElementById('summary-pages-download').textContent = 'All pages';
    } else {
        const from = document.getElementById('from-page-download').value || 0;
        const to = document.getElementById('to-page-download').value || 0;
        document.getElementById('summary-pages-download').textContent = `Pages ${from} - ${to}`;
    }
    
    // Render mode
    const renderMode = document.getElementById('render-mode-download').value;
    const renderModeText = renderMode.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase());
    document.getElementById('summary-render-download').textContent = renderModeText;
    
    // File suffix
    const suffix = document.getElementById('suffix').value || '_translated';
    document.getElementById('summary-suffix-download').textContent = suffix;
}

// Add event listeners for upload form to update summary
document.getElementById('file-input').addEventListener('change', updateUploadSummary);
document.getElementById('from-lang-upload').addEventListener('change', updateUploadSummary);
document.getElementById('to-lang-upload').addEventListener('change', updateUploadSummary);
document.getElementById('translate-all-upload').addEventListener('change', updateUploadSummary);
document.getElementById('from-page-upload').addEventListener('input', updateUploadSummary);
document.getElementById('to-page-upload').addEventListener('input', updateUploadSummary);
document.getElementById('render-mode-upload').addEventListener('change', updateUploadSummary);
document.getElementById('add-blank-page-upload').addEventListener('change', updateUploadSummary);
document.getElementById('output-path-display-upload').addEventListener('change', updateUploadSummary);
document.getElementById('custom-output-path-upload').addEventListener('change', updateUploadSummary);

// Add event listeners for download form to update summary
document.getElementById('pdf-url').addEventListener('input', updateDownloadSummary);
document.getElementById('from-lang-download').addEventListener('change', updateDownloadSummary);
document.getElementById('to-lang-download').addEventListener('change', updateDownloadSummary);
document.getElementById('translate-all-download').addEventListener('change', updateDownloadSummary);
document.getElementById('from-page-download').addEventListener('input', updateDownloadSummary);
document.getElementById('to-page-download').addEventListener('input', updateDownloadSummary);
document.getElementById('render-mode-download').addEventListener('change', updateDownloadSummary);
document.getElementById('suffix').addEventListener('input', updateDownloadSummary);
document.getElementById('output-path-display-download').addEventListener('change', updateDownloadSummary);

// Upload & Translate form submission
document.getElementById('upload-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const fileInput = document.getElementById('file-input');
    const file = fileInput.files[0];
    
    if (!file) {
        showNotification('Please select a PDF file', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('input_pdf', file);
    formData.append('from_lang', document.getElementById('from-lang-upload').value);
    formData.append('to_lang', document.getElementById('to-lang-upload').value);
    formData.append('translate_all', document.getElementById('translate-all-upload').checked);
    formData.append('p_from', document.getElementById('from-page-upload').value || 0);
    formData.append('p_to', document.getElementById('to-page-upload').value || 0);
    formData.append('render_mode', document.getElementById('render-mode-upload').value);
    formData.append('add_blank_page', document.getElementById('add-blank-page-upload').checked);
    
    // Add custom output path if specified
    const customPath = document.getElementById('output-path-upload').value;
    if (customPath) {
        formData.append('output_file_path', customPath);
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    toggleSpinner(submitBtn, true);
    
    try {
        const response = await fetch(ENDPOINTS.translate, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showNotification(data.message || 'Translation submitted successfully!', 'success');
            fileInput.value = '';
            document.getElementById('file-name').textContent = 'No file selected';
        } else {
            throw new Error(data.message || 'Translation failed');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        toggleSpinner(submitBtn, false);
    }
});

// Download & Translate form submission
document.getElementById('download-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData();
    formData.append('input_pdf_path', document.getElementById('pdf-url').value);
    formData.append('from_lang', document.getElementById('from-lang-download').value);
    formData.append('to_lang', document.getElementById('to-lang-download').value);
    formData.append('translate_all', document.getElementById('translate-all-download').checked);
    formData.append('p_from', document.getElementById('from-page-download').value || 0);
    formData.append('p_to', document.getElementById('to-page-download').value || 0);
    formData.append('render_mode', document.getElementById('render-mode-download').value);
    formData.append('add_blank_page', document.getElementById('add-blank-page-download').checked);
    
    // Add custom output path if specified
    const customPath = document.getElementById('output-path-download').value;
    if (customPath) {
        formData.append('output_file_path', customPath);
    }
    
    const submitBtn = e.target.querySelector('button[type="submit"]');
    toggleSpinner(submitBtn, true);
    
    try {
        const response = await fetch(ENDPOINTS.translate, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            showNotification(data.message || 'Download and translation submitted successfully!', 'success');
            e.target.reset();
        } else {
            throw new Error(data.message || 'Operation failed');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        toggleSpinner(submitBtn, false);
    }
});

// Refresh results
async function refreshResults() {
    const tbody = document.getElementById('results-tbody');
    tbody.innerHTML = '<tr><td colspan="5" class="no-data">Loading...</td></tr>';
    
    try {
        const response = await fetch(ENDPOINTS.getFiles, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/x-www-form-urlencoded',
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to fetch results');
        }
        
        const data = await response.json();
        
        if (data.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="no-data">No translation results yet</td></tr>';
            return;
        }
        
        tbody.innerHTML = data.map(item => {
            const statusClass = item.status === 2 ? 'translated' : 
                               item.status === 1 ? 'translating' : 'not-translated';
            const statusText = item.status === 2 ? 'Translated' : 
                              item.status === 1 ? 'Translating' : 'Pending';
            
            const downloadBtn = item.status === 2 ? 
                `<button class="btn btn-success btn-sm" onclick="downloadFile('${item.target_path}')">Download</button>` :
                '-';
            
            // Extract just the filename from paths for compact display
            const srcFileName = item.src_path.split('/').pop();
            const targetFileName = item.target_path.split('/').pop();
            
            return `
                <tr>
                    <td class="cell-file">${item.file}</td>
                    <td class="cell-status"><span class="status-badge status-${statusClass}">${statusText}</span></td>
                    <td class="cell-path" title="${item.src_path}">${srcFileName}</td>
                    <td class="cell-path" title="${item.target_path}">${targetFileName}</td>
                    <td class="cell-action">${downloadBtn}</td>
                </tr>
            `;
        }).join('');
        
    } catch (error) {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">Error loading results</td></tr>';
        showNotification(`Error: ${error.message}`, 'error');
    }
}

// Download file function
async function downloadFile(filePath) {
    try {
        const formData = new FormData();
        formData.append('file_path', filePath);
        
        const response = await fetch(ENDPOINTS.downloadFile, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            throw new Error('Download failed');
        }
        
        const blob = await response.blob();
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filePath.split('/').pop();
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
        showNotification('Download started!', 'success');
    } catch (error) {
        showNotification(`Download error: ${error.message}`, 'error');
    }
}

// Refresh button
document.getElementById('refresh-btn').addEventListener('click', refreshResults);

// Load default paths from config
async function loadDefaultPaths(retryCount = 0) {
    try {
        console.log('Loading default paths from config...');
        const response = await fetch(ENDPOINTS.getConfig, {
            method: 'GET',
            headers: {
                'Accept': 'application/json',
            }
        });
        
        console.log('Response status:', response.status);
        
        if (response.ok) {
            const config = await response.json();
            console.log('Config loaded:', config);
            
            window.defaultPaths.download_folder = config.download_folder;
            window.defaultPaths.translate_folder = config.translate_folder;
            window.defaultPaths.temp_dir = config.temp_dir;
            
            // Update upload form display
            document.getElementById('output-path-display-upload').value = config.translate_folder;
            document.getElementById('output-path-display-upload').placeholder = config.translate_folder;
            
            // Update download form display
            document.getElementById('output-path-display-download').value = config.download_folder;
            document.getElementById('output-path-display-download').placeholder = config.download_folder;
            
            console.log('Default paths loaded successfully:', window.defaultPaths);
            
            // Initialize summaries
            updateUploadSummary();
            updateDownloadSummary();
        } else {
            const errorText = await response.text();
            console.error('Server returned error:', response.status, errorText);
            throw new Error(`Server error: ${response.status}`);
        }
    } catch (error) {
        console.error('Error loading default paths:', error);
        
        // Retry up to 3 times with delay
        if (retryCount < 3) {
            console.log(`Retrying (${retryCount + 1}/3)...`);
            setTimeout(() => loadDefaultPaths(retryCount + 1), 1000);
            return;
        }
        
        showNotification('Failed to load default paths. Using fallback values.', 'error');
        
        // Set fallback values to project root
        const fallbackPath = '/home/home/SysUse/LLM_PDF_Translator';
        window.defaultPaths.download_folder = fallbackPath;
        window.defaultPaths.translate_folder = fallbackPath;
        
        document.getElementById('output-path-display-upload').value = fallbackPath;
        document.getElementById('output-path-display-upload').placeholder = fallbackPath;
        document.getElementById('output-path-display-download').value = fallbackPath;
        document.getElementById('output-path-display-download').placeholder = fallbackPath;
        
        // Initialize summaries even on error
        updateUploadSummary();
        updateDownloadSummary();
    }
}

// Initial load - refresh results on page load
window.addEventListener('DOMContentLoaded', () => {
    // Load default paths first
    loadDefaultPaths();
    
    // Initialize resizable table columns
    initResizableTable();
    
    // Don't auto-load results on page load, wait for user to switch to results tab
    console.log('PDF Translator loaded');
});

// ============ Resizable Table Columns ============

function initResizableTable() {
    const table = document.getElementById('results-table');
    if (!table) return;
    
    const headers = table.querySelectorAll('th.resizable');
    
    headers.forEach(header => {
        const handle = header.querySelector('.resize-handle');
        if (!handle) return;
        
        let startX, startWidth;
        
        handle.addEventListener('mousedown', (e) => {
            startX = e.pageX;
            startWidth = header.offsetWidth;
            handle.classList.add('resizing');
            
            document.addEventListener('mousemove', onMouseMove);
            document.addEventListener('mouseup', onMouseUp);
            
            e.preventDefault();
        });
        
        function onMouseMove(e) {
            const diff = e.pageX - startX;
            const newWidth = Math.max(50, startWidth + diff);
            header.style.width = newWidth + 'px';
        }
        
        function onMouseUp() {
            handle.classList.remove('resizing');
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }
    });
}

// ============ Model Settings ============

const PROVIDER_DEFAULTS = {
    ollama: {
        baseUrl: 'http://localhost:11434/v1/',
        needsApiKey: false,
        hint: 'Default: http://localhost:11434/v1/'
    },
    openai: {
        baseUrl: 'https://api.openai.com/v1',
        needsApiKey: true,
        hint: 'Default: https://api.openai.com/v1'
    },
    qwen: {
        baseUrl: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
        needsApiKey: true,
        hint: 'Default: https://dashscope.aliyuncs.com/compatible-mode/v1'
    },
    claude: {
        baseUrl: 'https://api.anthropic.com/v1',
        needsApiKey: true,
        hint: 'Default: https://api.anthropic.com/v1'
    },
    deepseek: {
        baseUrl: 'https://api.deepseek.com/v1',
        needsApiKey: true,
        hint: 'Default: https://api.deepseek.com/v1'
    },
    custom: {
        baseUrl: '',
        needsApiKey: true,
        hint: 'Enter your custom OpenAI-compatible API endpoint'
    }
};

// Initialize settings page
function initSettingsPage() {
    const providerSelect = document.getElementById('provider-select');
    const apiKeyInput = document.getElementById('api-key-input');
    const baseUrlInput = document.getElementById('base-url-input');
    const baseUrlHint = document.getElementById('base-url-hint');
    const apiKeyGroup = document.getElementById('api-key-group');
    const modelSelect = document.getElementById('model-select');
    const customModelGroup = document.getElementById('custom-model-group');
    const customModelInput = document.getElementById('custom-model-input');
    const fetchModelsBtn = document.getElementById('fetch-models-btn');
    const saveSettingsBtn = document.getElementById('save-settings-btn');
    const toggleApiKeyBtn = document.getElementById('toggle-api-key');

    // Toggle API key visibility
    toggleApiKeyBtn.addEventListener('click', () => {
        if (apiKeyInput.type === 'password') {
            apiKeyInput.type = 'text';
            toggleApiKeyBtn.textContent = '🙈';
        } else {
            apiKeyInput.type = 'password';
            toggleApiKeyBtn.textContent = '👁️';
        }
    });

    // Provider change handler
    providerSelect.addEventListener('change', () => {
        const provider = providerSelect.value;
        const defaults = PROVIDER_DEFAULTS[provider];
        
        // Update base URL placeholder and hint
        baseUrlInput.placeholder = defaults.baseUrl || 'https://api.example.com/v1';
        baseUrlHint.textContent = defaults.hint;
        
        // Show/hide API key field
        if (defaults.needsApiKey) {
            apiKeyGroup.style.display = 'block';
        } else {
            apiKeyGroup.style.display = 'none';
            apiKeyInput.value = '';
        }
        
        // Clear model selection
        modelSelect.innerHTML = '<option value="">-- Select a model --</option>';
    });

    // Model select change - show custom input if needed
    modelSelect.addEventListener('change', () => {
        if (modelSelect.value === '__custom__') {
            customModelGroup.style.display = 'block';
            customModelInput.focus();
        } else {
            customModelGroup.style.display = 'none';
        }
    });

    // Fetch models button
    fetchModelsBtn.addEventListener('click', async () => {
        const provider = providerSelect.value;
        const apiKey = apiKeyInput.value;
        const baseUrl = baseUrlInput.value;
        
        toggleSpinner(fetchModelsBtn, true);
        
        try {
            const formData = new FormData();
            formData.append('provider', provider);
            formData.append('api_key', apiKey);
            formData.append('base_url', baseUrl);
            
            const response = await fetch(ENDPOINTS.fetchModels, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (data.error) {
                showNotification(`Error: ${data.error}`, 'error');
            }
            
            // Populate model select
            modelSelect.innerHTML = '<option value="">-- Select a model --</option>';
            
            if (data.models && data.models.length > 0) {
                data.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = model;
                    option.textContent = model;
                    modelSelect.appendChild(option);
                });
                showNotification(`Loaded ${data.models.length} models`, 'success');
            } else {
                showNotification('No models found. You can enter a model name manually.', 'info');
            }
            
            // Add custom option
            const customOption = document.createElement('option');
            customOption.value = '__custom__';
            customOption.textContent = '-- Enter custom model --';
            modelSelect.appendChild(customOption);
            
        } catch (error) {
            showNotification(`Error fetching models: ${error.message}`, 'error');
        } finally {
            toggleSpinner(fetchModelsBtn, false);
        }
    });

    // Save settings button
    saveSettingsBtn.addEventListener('click', async () => {
        const provider = providerSelect.value;
        const apiKey = apiKeyInput.value;
        const baseUrl = baseUrlInput.value;
        let model = modelSelect.value;
        
        // Use custom model if selected
        if (model === '__custom__') {
            model = customModelInput.value;
        }
        
        if (!model) {
            showNotification('Please select or enter a model', 'error');
            return;
        }
        
        toggleSpinner(saveSettingsBtn, true);
        
        try {
            const formData = new FormData();
            formData.append('provider', provider);
            formData.append('api_key', apiKey);
            formData.append('base_url', baseUrl);
            formData.append('model', model);
            
            const response = await fetch(ENDPOINTS.setTranslatorConfig, {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                showNotification(data.message, 'success');
                updateCurrentConfig(provider, model, 'Active');
            } else {
                throw new Error(data.error || 'Failed to save settings');
            }
        } catch (error) {
            showNotification(`Error: ${error.message}`, 'error');
            updateCurrentConfig(provider, model, 'Error');
        } finally {
            toggleSpinner(saveSettingsBtn, false);
        }
    });

    // Load current config on page load
    loadCurrentTranslatorConfig();
}

function updateCurrentConfig(provider, model, status) {
    document.getElementById('current-provider').textContent = provider || '-';
    document.getElementById('current-model').textContent = model || '-';
    document.getElementById('current-status').textContent = status || '-';
    
    // Update summaries with new model info
    updateUploadSummary();
    updateDownloadSummary();
}

async function loadCurrentTranslatorConfig() {
    try {
        const response = await fetch(ENDPOINTS.getTranslatorConfig);
        if (response.ok) {
            const config = await response.json();
            
            // Update form
            const providerSelect = document.getElementById('provider-select');
            providerSelect.value = config.type || 'ollama';
            providerSelect.dispatchEvent(new Event('change'));
            
            document.getElementById('api-key-input').value = config.api_key || '';
            document.getElementById('base-url-input').value = config.base_url || '';
            
            // Update current config display
            updateCurrentConfig(config.type, config.model, 'Active');
            
            // If there's a current model, add it to the select
            if (config.model) {
                const modelSelect = document.getElementById('model-select');
                const option = document.createElement('option');
                option.value = config.model;
                option.textContent = config.model;
                option.selected = true;
                modelSelect.appendChild(option);
            }
        }
    } catch (error) {
        console.error('Error loading translator config:', error);
    }
}

// Initialize settings page when DOM is loaded
document.addEventListener('DOMContentLoaded', initSettingsPage);
