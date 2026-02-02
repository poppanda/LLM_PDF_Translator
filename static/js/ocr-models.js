// OCR Models Management JavaScript

// API endpoints for OCR models
const OCR_ENDPOINTS = {
    getPaddleModels: '/get_paddle_models/',
    getPaddleModelStatus: '/get_paddle_model_status/',
    downloadPaddleModel: '/download_paddle_model/',
    downloadPaddleModelSet: '/download_paddle_model_set/',
    deletePaddleModel: '/delete_paddle_model/',
    getRecModelDictMapping: '/get_rec_model_dict_mapping/',
    getAvailableDictionaries: '/get_available_dictionaries/'
};

// Store current models data
let currentModels = [];
let currentModelSets = [];
let currentFilter = 'all';
let downloadingModels = new Set();
let pollInterval = null;
let modelDictMapping = {};  // rec model -> dict filename mapping
let dictStatus = {};  // dict filename -> exists status

// Model type display names
const MODEL_TYPE_NAMES = {
    'det': 'Detection',
    'rec': 'Recognition',
    'cls': 'Classification'
};

// Status display configuration
const STATUS_CONFIG = {
    'downloaded': { class: 'status-downloaded', text: 'Downloaded', icon: '✓' },
    'downloading': { class: 'status-downloading', text: 'Downloading', icon: '↓' },
    'converting': { class: 'status-converting', text: 'Converting', icon: '⚙' },
    'not_downloaded': { class: 'status-not-downloaded', text: 'Not Downloaded', icon: '○' },
    'error': { class: 'status-error', text: 'Error', icon: '✗' }
};

// Initialize OCR Models page
async function initOCRModelsPage() {
    // Load dictionary mapping first
    await loadDictMapping();
    
    // Set up filter buttons
    document.querySelectorAll('.filter-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
            e.target.classList.add('active');
            currentFilter = e.target.dataset.version;
            renderModelTable();
        });
    });
    
    // Load models on tab switch
    document.querySelector('[data-tab="ocr-models"]').addEventListener('click', () => {
        refreshModelList();
    });
}

// Load dictionary mapping and status
async function loadDictMapping() {
    try {
        // Load model -> dict mapping
        const mappingResponse = await fetch(OCR_ENDPOINTS.getRecModelDictMapping);
        const mappingData = await mappingResponse.json();
        if (mappingData.mapping) {
            modelDictMapping = mappingData.mapping;
        }
        
        // Load dictionary status (which ones exist)
        const dictResponse = await fetch(OCR_ENDPOINTS.getAvailableDictionaries);
        const dictData = await dictResponse.json();
        if (dictData.dictionaries) {
            dictStatus = {};
            for (const dict of dictData.dictionaries) {
                dictStatus[dict.filename] = dict.exists;
            }
        }
    } catch (error) {
        console.error('Error loading dictionary mapping:', error);
    }
}

// Refresh the model list from server
async function refreshModelList(preserveScroll = false) {
    const refreshBtn = document.getElementById('refresh-models-btn');
    if (refreshBtn) {
        toggleSpinner(refreshBtn, true);
    }
    
    const tbody = document.getElementById('models-tbody');
    const tableContainer = document.querySelector('.models-table-container');
    
    // Save scroll position if preserving
    let scrollTop = 0;
    if (preserveScroll && tableContainer) {
        scrollTop = tableContainer.scrollTop;
    }
    
    // Only show loading if not preserving scroll (initial load)
    if (!preserveScroll) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">Loading models...</td></tr>';
    }
    
    try {
        // Refresh dictionary status (important after downloads)
        await loadDictMapping();
        
        const response = await fetch(OCR_ENDPOINTS.getPaddleModels);
        const data = await response.json();
        
        if (data.error) {
            throw new Error(data.error);
        }
        
        currentModels = data.models || [];
        currentModelSets = data.model_sets || [];
        
        renderModelTable();
        renderModelSetCards();
        
        // Restore scroll position
        if (preserveScroll && tableContainer) {
            tableContainer.scrollTop = scrollTop;
        }
        
        // Start polling if any models are downloading
        checkAndStartPolling();
        
    } catch (error) {
        console.error('Error loading models:', error);
        tbody.innerHTML = `<tr><td colspan="7" class="no-data">Error loading models: ${error.message}</td></tr>`;
        showNotification(`Error loading models: ${error.message}`, 'error');
    } finally {
        if (refreshBtn) {
            toggleSpinner(refreshBtn, false);
        }
    }
}

// Render the models table based on current filter
function renderModelTable() {
    const tbody = document.getElementById('models-tbody');
    
    // Filter models
    let filteredModels = currentModels;
    if (currentFilter !== 'all') {
        filteredModels = currentModels.filter(m => m.info && m.info.version === currentFilter);
    }
    
    if (filteredModels.length === 0) {
        tbody.innerHTML = '<tr><td colspan="7" class="no-data">No models found</td></tr>';
        return;
    }
    
    // Sort models by version, then type
    filteredModels.sort((a, b) => {
        const versionOrder = { 'v3': 1, 'v4': 2, 'v5': 3 };
        const typeOrder = { 'det': 1, 'rec': 2, 'cls': 3 };
        
        const aVersion = versionOrder[a.info?.version] || 99;
        const bVersion = versionOrder[b.info?.version] || 99;
        if (aVersion !== bVersion) return aVersion - bVersion;
        
        const aType = typeOrder[a.info?.model_type] || 99;
        const bType = typeOrder[b.info?.model_type] || 99;
        return aType - bType;
    });
    
    tbody.innerHTML = filteredModels.map(model => {
        const info = model.info || {};
        const status = model.status || 'not_downloaded';
        const statusConfig = STATUS_CONFIG[status] || STATUS_CONFIG['not_downloaded'];
        
        const progress = model.progress || 0;
        const downloadedMB = (model.downloaded_mb || 0).toFixed(1);
        const totalMB = (model.total_mb || info.size_mb || 0).toFixed(1);
        
        // Status cell content
        let statusContent = '';
        if (status === 'downloading' || status === 'converting') {
            const statusText = status === 'converting' ? 'Converting to ONNX...' : `${progress}% (${downloadedMB}/${totalMB} MB)`;
            statusContent = `
                <div class="download-progress">
                    <div class="progress-bar">
                        <div class="progress-fill" style="width: ${progress}%"></div>
                    </div>
                    <span class="progress-text">${statusText}</span>
                </div>
            `;
        } else {
            statusContent = `
                <span class="status-badge ${statusConfig.class}">
                    <span class="status-icon">${statusConfig.icon}</span>
                    ${statusConfig.text}
                </span>
            `;
        }
        
        // Action buttons
        let actionContent = '';
        if (status === 'downloaded') {
            actionContent = `
                <button class="btn btn-danger btn-sm" onclick="deleteModel('${model.model_key}')" title="Delete model">
                    Delete
                </button>
            `;
        } else if (status === 'downloading') {
            actionContent = `
                <button class="btn btn-secondary btn-sm" disabled>
                    <span class="spinner-small"></span> Downloading...
                </button>
            `;
        } else {
            actionContent = `
                <button class="btn btn-primary btn-sm" onclick="downloadModel('${model.model_key}')">
                    <span class="btn-text">Download</span>
                    <span class="spinner" style="display: none;"></span>
                </button>
            `;
        }
        
        // For rec models, show dictionary info
        let dictInfo = '';
        if (info.model_type === 'rec') {
            const dictFile = modelDictMapping[info.filename];
            if (dictFile) {
                const dictExists = dictStatus[dictFile] === true;
                const dictIcon = dictExists ? '&#10003;' : '&#9888;';
                const dictClass = dictExists ? 'dict-ready' : 'dict-missing';
                dictInfo = `<div class="model-dict ${dictClass}" title="Dictionary: ${dictFile}"><span class="dict-icon">${dictIcon}</span> ${dictFile}</div>`;
            }
        }
        
        return `
            <tr data-model-key="${model.model_key}">
                <td class="cell-model">
                    <div class="model-name">${info.filename || model.model_key}</div>
                    <div class="model-desc">${info.description || ''}</div>
                    ${dictInfo}
                </td>
                <td class="cell-version">
                    <span class="version-badge version-${info.version || 'unknown'}">${(info.version || '').toUpperCase()}</span>
                </td>
                <td class="cell-type">${MODEL_TYPE_NAMES[info.model_type] || info.model_type || '-'}</td>
                <td class="cell-lang">${(info.language || '-').toUpperCase()}</td>
                <td class="cell-size">${totalMB} MB</td>
                <td class="cell-status">${statusContent}</td>
                <td class="cell-action">${actionContent}</td>
            </tr>
        `;
    }).join('');
}

// Render model set cards dynamically
function renderModelSetCards() {
    const container = document.getElementById('model-sets-grid');
    if (!container || currentModelSets.length === 0) {
        return;
    }
    
    container.innerHTML = currentModelSets.map(set => {
        // Determine badge HTML
        let badgeHtml = '';
        if (set.badge) {
            const badgeClass = set.badge_type === 'new' ? 'set-badge-new' : 
                              set.badge_type === 'accuracy' ? 'set-badge-new' : '';
            badgeHtml = `<span class="set-badge ${badgeClass}">${set.badge}</span>`;
        }
        
        // Determine button state
        let buttonHtml = '';
        if (set.is_complete) {
            buttonHtml = `
                <button class="btn btn-success btn-sm" disabled>
                    <span class="btn-text">Downloaded</span>
                </button>
            `;
        } else {
            const progressText = set.downloaded_count > 0 
                ? `(${set.downloaded_count}/${set.total_count})` 
                : '';
            buttonHtml = `
                <button class="btn btn-primary btn-sm" onclick="downloadModelSet('${set.key}')">
                    <span class="btn-text">Download ${progressText}</span>
                    <span class="spinner" style="display: none;"></span>
                </button>
            `;
        }
        
        return `
            <div class="model-set-card" data-set="${set.key}">
                <div class="set-header">
                    <span class="set-name">${set.name}</span>
                    ${badgeHtml}
                </div>
                <p class="set-description">${set.description}</p>
                <div class="set-models">${set.models_desc}</div>
                ${buttonHtml}
            </div>
        `;
    }).join('');
}

// Download a single model
async function downloadModel(modelKey) {
    if (downloadingModels.has(modelKey)) {
        showNotification('This model is already downloading', 'info');
        return;
    }
    
    downloadingModels.add(modelKey);
    
    // Update UI immediately
    const row = document.querySelector(`tr[data-model-key="${modelKey}"]`);
    if (row) {
        const actionCell = row.querySelector('.cell-action');
        if (actionCell) {
            actionCell.innerHTML = `
                <button class="btn btn-secondary btn-sm" disabled>
                    <span class="spinner-small"></span> Starting...
                </button>
            `;
        }
    }
    
    try {
        const formData = new FormData();
        formData.append('model_key', modelKey);
        
        const response = await fetch(OCR_ENDPOINTS.downloadPaddleModel, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Download started: ${modelKey}`, 'success');
            // Start polling for progress
            startProgressPolling();
        } else {
            throw new Error(data.error || 'Download failed');
        }
        
    } catch (error) {
        console.error('Error downloading model:', error);
        showNotification(`Error: ${error.message}`, 'error');
        downloadingModels.delete(modelKey);
        refreshModelList();
    }
}

// Download a model set
async function downloadModelSet(setName) {
    const setCard = document.querySelector(`.model-set-card[data-set="${setName}"]`);
    const btn = setCard?.querySelector('button');
    
    if (btn) {
        toggleSpinner(btn, true);
    }
    
    try {
        const formData = new FormData();
        formData.append('set_name', setName);
        
        const response = await fetch(OCR_ENDPOINTS.downloadPaddleModelSet, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Model set "${setName}" download started`, 'success');
            // Start polling for progress
            startProgressPolling();
        } else {
            throw new Error(data.error || 'Download failed');
        }
        
    } catch (error) {
        console.error('Error downloading model set:', error);
        showNotification(`Error: ${error.message}`, 'error');
    } finally {
        if (btn) {
            toggleSpinner(btn, false);
        }
    }
}

// Delete a model
async function deleteModel(modelKey) {
    if (!confirm(`Are you sure you want to delete the model "${modelKey}"?`)) {
        return;
    }
    
    try {
        const formData = new FormData();
        formData.append('model_key', modelKey);
        
        const response = await fetch(OCR_ENDPOINTS.deletePaddleModel, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (data.success) {
            showNotification(`Model deleted: ${modelKey}`, 'success');
            refreshModelList();
        } else {
            throw new Error(data.error || 'Delete failed');
        }
        
    } catch (error) {
        console.error('Error deleting model:', error);
        showNotification(`Error: ${error.message}`, 'error');
    }
}

// Start polling for download progress
function startProgressPolling() {
    if (pollInterval) {
        return; // Already polling
    }
    
    pollInterval = setInterval(async () => {
        // Preserve scroll position during polling updates
        await refreshModelList(true);
        
        // Check if any models are still downloading or converting
        const stillDownloading = currentModels.some(m => m.status === 'downloading' || m.status === 'converting');
        if (!stillDownloading) {
            stopProgressPolling();
            downloadingModels.clear();
        }
    }, 2000); // Poll every 2 seconds
}

// Stop polling
function stopProgressPolling() {
    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }
}

// Check if we need to start polling on page load
function checkAndStartPolling() {
    const anyDownloading = currentModels.some(m => m.status === 'downloading');
    if (anyDownloading) {
        startProgressPolling();
    } else {
        stopProgressPolling();
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', initOCRModelsPage);

// Clean up on page unload
window.addEventListener('beforeunload', stopProgressPolling);
