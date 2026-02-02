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
    fetchModels: '/fetch_models/',
    // OCR Configuration endpoints
    getOcrConfig: '/get_ocr_config/',
    setOcrConfig: '/set_ocr_config/',
    getOcrPresets: '/get_ocr_presets/',
    getPaddleModels: '/get_paddle_models/',
    getRecModelDictMapping: '/get_rec_model_dict_mapping/',
    getAvailableDictionaries: '/get_available_dictionaries/',
    downloadPresetModels: '/download_preset_models/'
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

    // Layout info
    const layout = window.defaultPaths.layout_config?.type || '-';
    document.getElementById('summary-layout-upload').textContent = layout;

    // OCR info
    const ocrDet = document.getElementById('current-ocr-det')?.textContent || '-';
    const ocrRec = document.getElementById('current-ocr-rec')?.textContent || '-';
    document.getElementById('summary-ocr-upload').textContent = (ocrDet !== '-' || ocrRec !== '-') ? `Det: ${ocrDet} / Rec: ${ocrRec}` : '-';
    
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

    // Layout info
    const layout = window.defaultPaths.layout_config?.type || '-';
    document.getElementById('summary-layout-download').textContent = layout;

    // OCR info
    const ocrDet = document.getElementById('current-ocr-det')?.textContent || '-';
    const ocrRec = document.getElementById('current-ocr-rec')?.textContent || '-';
    document.getElementById('summary-ocr-download').textContent = (ocrDet !== '-' || ocrRec !== '-') ? `Det: ${ocrDet} / Rec: ${ocrRec}` : '-';
    
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
            window.defaultPaths.layout_config = config.layout_config;
            
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

// ============ OCR Settings ============

let ocrPresets = {};
let downloadedModels = [];
let recModelDictMapping = {};  // Maps rec model filename -> dict filename
let availableDictionaries = [];  // List of available dict files

async function initOCRSettings() {
    // Load rec model -> dict mapping
    await loadRecModelDictMapping();
    
    // Load available dictionaries
    await loadAvailableDictionaries();
    
    // Load OCR presets
    await loadOCRPresets();
    
    // Load current OCR config
    await loadCurrentOCRConfig();
    
    // Set up event listeners
    document.getElementById('ocr-preset-select').addEventListener('change', onOCRPresetChange);
    document.getElementById('ocr-rec-model').addEventListener('change', onRecModelChange);
    document.getElementById('save-ocr-settings-btn').addEventListener('click', saveOCRSettings);
}

async function loadRecModelDictMapping() {
    try {
        const response = await fetch(ENDPOINTS.getRecModelDictMapping);
        const data = await response.json();
        if (data.mapping) {
            recModelDictMapping = data.mapping;
        }
    } catch (error) {
        console.error('Error loading rec model dict mapping:', error);
    }
}

async function loadAvailableDictionaries() {
    try {
        const response = await fetch(ENDPOINTS.getAvailableDictionaries);
        const data = await response.json();
        if (data.dictionaries) {
            availableDictionaries = data.dictionaries;
            populateDictSelect();
        }
    } catch (error) {
        console.error('Error loading available dictionaries:', error);
    }
}

function populateDictSelect() {
    const select = document.getElementById('ocr-char-dict');
    select.innerHTML = '<option value="">-- Auto-detect from model --</option>';
    
    // Add available dictionaries
    for (const dict of availableDictionaries) {
        const option = document.createElement('option');
        option.value = dict.filename;
        
        // Show status icon and language info
        const statusIcon = dict.exists ? '' : ' (not downloaded)';
        const langInfo = dict.language ? ` [${dict.language}]` : '';
        option.textContent = `${dict.filename}${langInfo}${statusIcon}`;
        
        if (!dict.exists) {
            option.style.color = '#999';
        }
        
        select.appendChild(option);
    }
}

function onRecModelChange(e) {
    const recModel = e.target.value;
    const dictSelect = document.getElementById('ocr-char-dict');
    const hint = document.getElementById('ocr-char-dict-hint');
    
    if (recModel && recModel !== '__manual__') {
        // Auto-detect dictionary based on rec model
        const autoDict = recModelDictMapping[recModel];
        if (autoDict) {
            // Set the auto-detected dictionary
            dictSelect.value = autoDict;
            hint.textContent = `Auto-detected: ${autoDict}`;
            hint.style.color = '#4caf50';
        } else {
            hint.textContent = 'No dictionary mapping found for this model';
            hint.style.color = '#ff9800';
        }
    } else {
        hint.textContent = 'Dictionary is auto-selected based on recognition model';
        hint.style.color = '';
    }
}

async function loadOCRPresets() {
    try {
        const response = await fetch(ENDPOINTS.getOcrPresets);
        const data = await response.json();
        
        if (data.presets) {
            ocrPresets = data.presets;
            populateOCRPresetSelect();
        }
    } catch (error) {
        console.error('Error loading OCR presets:', error);
    }
}

function populateOCRPresetSelect() {
    const select = document.getElementById('ocr-preset-select');
    select.innerHTML = '<option value="">-- Select a preset --</option>';
    
    for (const [key, preset] of Object.entries(ocrPresets)) {
        const option = document.createElement('option');
        option.value = key;
        
        const readyIcon = preset.ready ? '' : '(needs download) ';
        option.textContent = `${preset.name} ${readyIcon}- ${preset.description}`;
        
        if (!preset.ready) {
            option.style.color = '#999';
        }
        
        select.appendChild(option);
    }
    
    // Add manual option
    const manualOption = document.createElement('option');
    manualOption.value = '__manual__';
    manualOption.textContent = '-- Configure Manually --';
    select.appendChild(manualOption);
}

async function loadCurrentOCRConfig() {
    try {
        // Load downloaded models for dropdown
        const modelsResponse = await fetch(ENDPOINTS.getPaddleModels);
        const modelsData = await modelsResponse.json();
        
        if (modelsData.models) {
            downloadedModels = modelsData.models.filter(m => m.status === 'downloaded');
            populateOCRModelSelects();
        }
        
        // Refresh available dictionaries (in case new ones were downloaded)
        await loadAvailableDictionaries();
        
        // Load current config
        const configResponse = await fetch(ENDPOINTS.getOcrConfig);
        const configData = await configResponse.json();
        
        if (configData.config) {
            updateOCRConfigDisplay(configData.config);
            
            // Set form values
            const detModel = configData.config.det?.model || '';
            const recModel = configData.config.rec?.model || '';
            const charDict = configData.config.rec?.char_dict || '';
            
            document.getElementById('ocr-det-model').value = detModel;
            document.getElementById('ocr-rec-model').value = recModel;
            document.getElementById('ocr-char-dict').value = charDict;
            
            // Update dictionary hint based on current rec model
            const hint = document.getElementById('ocr-char-dict-hint');
            if (charDict) {
                const autoDict = recModelDictMapping[recModel];
                if (autoDict === charDict) {
                    hint.textContent = `Auto-detected: ${charDict}`;
                    hint.style.color = '#4caf50';
                } else {
                    hint.textContent = `Custom dictionary: ${charDict}`;
                    hint.style.color = '#2196f3';
                }
            }
        }
    } catch (error) {
        console.error('Error loading OCR config:', error);
    }
}

function populateOCRModelSelects() {
    const detSelect = document.getElementById('ocr-det-model');
    const recSelect = document.getElementById('ocr-rec-model');
    
    // Clear existing options
    detSelect.innerHTML = '<option value="">-- Select detection model --</option>';
    recSelect.innerHTML = '<option value="">-- Select recognition model --</option>';
    
    // Add downloaded models
    for (const model of downloadedModels) {
        const filename = model.info?.filename || model.model_key;
        const version = model.info?.version?.toUpperCase() || '';
        
        if (model.info?.model_type === 'det') {
            const option = document.createElement('option');
            option.value = filename;
            option.textContent = `${filename} (${version})`;
            detSelect.appendChild(option);
        } else if (model.info?.model_type === 'rec') {
            const option = document.createElement('option');
            option.value = filename;
            
            // Show associated dictionary for rec models
            const dictFile = recModelDictMapping[filename];
            const dictInfo = dictFile ? ` -> ${dictFile}` : '';
            option.textContent = `${filename} (${version})${dictInfo}`;
            
            recSelect.appendChild(option);
        }
    }
}

function onOCRPresetChange(e) {
    const presetKey = e.target.value;
    const downloadBtnContainer = document.getElementById('preset-download-container');
    
    // Hide download button by default
    if (downloadBtnContainer) {
        downloadBtnContainer.style.display = 'none';
    }
    
    if (presetKey === '' || presetKey === '__manual__') {
        // Reset hint when switching to manual
        const hint = document.getElementById('ocr-char-dict-hint');
        hint.textContent = 'Dictionary is auto-selected based on recognition model';
        hint.style.color = '';
        return;
    }
    
    const preset = ocrPresets[presetKey];
    if (!preset) return;
    
    // Check if models are downloaded
    if (!preset.ready) {
        const missing = preset.missing_models.join(', ');
        showNotification(`Missing models: ${missing}. Click "Download Preset Models" to download.`, 'warning');
        
        // Show download button
        if (downloadBtnContainer) {
            downloadBtnContainer.style.display = 'block';
            downloadBtnContainer.dataset.preset = presetKey;
        }
    }
    
    // Set form values from preset
    if (preset.det?.model) {
        document.getElementById('ocr-det-model').value = preset.det.model;
    }
    if (preset.rec?.model) {
        document.getElementById('ocr-rec-model').value = preset.rec.model;
    }
    
    // Set dictionary and update hint
    const dictSelect = document.getElementById('ocr-char-dict');
    const hint = document.getElementById('ocr-char-dict-hint');
    
    if (preset.rec?.char_dict) {
        dictSelect.value = preset.rec.char_dict;
        hint.textContent = `Preset dictionary: ${preset.rec.char_dict}`;
        hint.style.color = '#4caf50';
    } else {
        dictSelect.value = '';
        hint.textContent = 'Dictionary is auto-selected based on recognition model';
        hint.style.color = '';
    }
}

let isDownloadingPreset = false;

async function downloadPresetModels() {
    // Prevent double-click
    if (isDownloadingPreset) {
        showNotification('Download already in progress, please wait...', 'info');
        return;
    }
    
    const container = document.getElementById('preset-download-container');
    const presetKey = container?.dataset.preset;
    
    if (!presetKey) {
        showNotification('No preset selected', 'error');
        return;
    }
    
    const btn = document.getElementById('download-preset-btn');
    const hint = container.querySelector('.download-hint');
    
    isDownloadingPreset = true;
    if (btn) {
        toggleSpinner(btn, true);
        btn.disabled = true;
    }
    if (hint) {
        hint.textContent = 'Downloading models... This may take a few minutes.';
    }
    
    try {
        const formData = new FormData();
        formData.append('preset', presetKey);
        
        const response = await fetch(ENDPOINTS.downloadPresetModels, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Models for preset "${presetKey}" downloaded successfully!`, 'success');
            // Refresh presets and config
            await loadOCRPresets();
            await loadCurrentOCRConfig();
            // Hide download button
            container.style.display = 'none';
        } else {
            // Show detailed error including individual model results
            let errorMsg = data.error || data.message || 'Download failed';
            if (data.results) {
                const failed = data.results.filter(r => !r.success);
                if (failed.length > 0) {
                    errorMsg = `Failed models: ${failed.map(r => `${r.model} (${r.message})`).join(', ')}`;
                }
            }
            throw new Error(errorMsg);
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
        if (hint) {
            hint.textContent = 'Download failed. Please try again.';
        }
    } finally {
        isDownloadingPreset = false;
        if (btn) {
            toggleSpinner(btn, false);
            btn.disabled = false;
        }
    }
}

function updateOCRConfigDisplay(config) {
    document.getElementById('current-ocr-det').textContent = config.det?.model || '-';
    document.getElementById('current-ocr-rec').textContent = config.rec?.model || '-';
    document.getElementById('current-ocr-dict').textContent = config.rec?.char_dict || '-';
    
    // Update summaries with new OCR info
    updateUploadSummary();
    updateDownloadSummary();
}

async function saveOCRSettings() {
    const saveBtn = document.getElementById('save-ocr-settings-btn');
    toggleSpinner(saveBtn, true);
    
    try {
        const presetValue = document.getElementById('ocr-preset-select').value;
        const formData = new FormData();
        
        if (presetValue && presetValue !== '__manual__') {
            // Use preset
            formData.append('preset', presetValue);
        } else {
            // Manual configuration
            const detModel = document.getElementById('ocr-det-model').value;
            const recModel = document.getElementById('ocr-rec-model').value;
            let charDict = document.getElementById('ocr-char-dict').value;
            
            if (detModel && detModel !== '__manual__') {
                formData.append('det_model', detModel);
            }
            if (recModel && recModel !== '__manual__') {
                formData.append('rec_model', recModel);
                
                // Auto-detect dictionary if not manually selected
                if (!charDict && recModelDictMapping[recModel]) {
                    charDict = recModelDictMapping[recModel];
                }
            }
            if (charDict) {
                formData.append('rec_char_dict', charDict);
            }
        }
        
        const response = await fetch(ENDPOINTS.setOcrConfig, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            if (data.warnings && data.warnings.length > 0) {
                showNotification(`Settings saved with warnings: ${data.warnings.join('; ')}`, 'warning');
            } else {
                showNotification('OCR settings saved successfully', 'success');
            }
            if (data.config) {
                updateOCRConfigDisplay(data.config);
            }
        } else {
            throw new Error(data.error || 'Failed to save OCR settings');
        }
    } catch (error) {
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        toggleSpinner(saveBtn, false);
    }
}

// Initialize OCR settings when page loads
document.addEventListener('DOMContentLoaded', initOCRSettings);
