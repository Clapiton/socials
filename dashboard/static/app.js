/* ==========================================
   Social Listener Dashboard — App Logic
   ========================================== */

// ─── State ─────────────────────────────────────────
let currentTab = 'overview';
let postsPage = 0;
let leadsPage = 0;
const PAGE_SIZE = 25;
let refreshInterval = null;

// ─── Init ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
    loadOverview();
    startAutoRefresh();
});

// ─── Tab Switching ─────────────────────────────────
function switchTab(tabName) {
    currentTab = tabName;

    // Update tab buttons
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');

    // Update tab content
    document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');

    // Load tab data
    switch (tabName) {
        case 'overview': loadOverview(); break;
        case 'posts': loadPosts(); break;
        case 'leads': loadLeads(); break;
        case 'outreach': loadOutreach(); break;
        case 'settings': loadSettings(); break;
    }
}

// ─── Auto Refresh ──────────────────────────────────
function startAutoRefresh() {
    refreshInterval = setInterval(() => {
        if (currentTab === 'overview') loadOverview();
        else if (currentTab === 'posts') loadPosts();
        else if (currentTab === 'leads') loadLeads();
        else if (currentTab === 'outreach') loadOutreach();
        // Don't auto-refresh settings to avoid overwriting user edits
    }, 30000);
}

// ─── Overview ──────────────────────────────────────
async function loadOverview() {
    try {
        const [stats, leads, posts] = await Promise.all([
            fetchAPI('/api/stats'),
            fetchAPI('/api/leads?limit=5'),
            fetchAPI('/api/posts?limit=5'),
        ]);

        // Update stat cards
        document.getElementById('stat-posts').textContent = formatNumber(stats.total_posts);
        document.getElementById('stat-analyzed').textContent = formatNumber(stats.total_analyzed);
        document.getElementById('stat-leads').textContent = formatNumber(stats.total_leads);
        document.getElementById('stat-outreach').textContent = formatNumber(stats.total_outreach);
        document.getElementById('stat-response-rate').textContent = stats.response_rate + '%';

        // Recent leads
        const leadsContainer = document.getElementById('recent-leads-list');
        if (leads.length === 0) {
            leadsContainer.innerHTML = '<p class="empty-state">No leads detected yet. Run Collect → Analyze to start.</p>';
        } else {
            leadsContainer.innerHTML = leads.map(lead => `
                <div class="panel-item">
                    <div class="panel-item-header">
                        <span class="panel-item-author">u/${lead.raw_posts?.author || '?'}</span>
                        <span class="badge badge-confidence ${getConfidenceClass(lead.confidence)}">${(lead.confidence * 100).toFixed(0)}%</span>
                    </div>
                    <p class="panel-item-content">${escapeHtml(lead.raw_posts?.title || lead.raw_posts?.content || '')}</p>
                    <div class="panel-item-tags">
                        <span class="badge badge-service">${escapeHtml(lead.suggested_service || 'none')}</span>
                        ${lead.raw_posts?.subreddit ? `<span class="badge badge-subreddit">r/${lead.raw_posts.subreddit}</span>` : ''}
                    </div>
                </div>
            `).join('');
        }

        // Recent posts
        const postsContainer = document.getElementById('recent-posts-list');
        if (posts.length === 0) {
            postsContainer.innerHTML = '<p class="empty-state">No posts collected yet. Click "Collect Now" to start.</p>';
        } else {
            postsContainer.innerHTML = posts.map(post => `
                <div class="panel-item">
                    <div class="panel-item-header">
                        <span class="panel-item-author">u/${escapeHtml(post.author || '?')}</span>
                        <span class="panel-item-meta">${timeAgo(post.collected_at)}</span>
                    </div>
                    <p class="panel-item-content">${escapeHtml(post.title || post.content || '')}</p>
                    <div class="panel-item-tags">
                        <span class="badge badge-platform ${post.platform}">${post.platform}</span>
                        ${post.subreddit ? `<span class="badge badge-subreddit">r/${post.subreddit}</span>` : ''}
                    </div>
                </div>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading overview:', err);
    }
}

// ─── Posts ──────────────────────────────────────────
async function loadPosts(direction) {
    if (direction === 'next') postsPage++;
    else if (direction === 'prev' && postsPage > 0) postsPage--;
    else if (!direction) postsPage = 0;

    const platform = document.getElementById('posts-filter-platform').value;
    const offset = postsPage * PAGE_SIZE;

    try {
        const posts = await fetchAPI(`/api/posts?limit=${PAGE_SIZE}&offset=${offset}${platform ? '&platform=' + platform : ''}`);
        const tbody = document.getElementById('posts-tbody');

        if (posts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="empty-state">No posts found</td></tr>';
        } else {
            tbody.innerHTML = posts.map(post => `
                <tr>
                    <td><span class="badge badge-platform ${post.platform}">${post.platform}</span></td>
                    <td>${post.subreddit ? `<span class="badge badge-subreddit">r/${post.subreddit}</span>` : '—'}</td>
                    <td class="text-truncate">${escapeHtml(post.author || '?')}</td>
                    <td class="text-clamp-2">${escapeHtml(post.title || post.content || '')}</td>
                    <td>${post.score || 0}</td>
                    <td>${timeAgo(post.collected_at)}</td>
                    <td>${post.url ? `<a href="${post.url}" target="_blank" rel="noopener">View ↗</a>` : '—'}</td>
                </tr>
            `).join('');
        }

        // Update pagination
        document.getElementById('posts-page-info').textContent = `Page ${postsPage + 1}`;
        document.getElementById('posts-prev').disabled = postsPage === 0;
        document.getElementById('posts-next').disabled = posts.length < PAGE_SIZE;
    } catch (err) {
        console.error('Error loading posts:', err);
    }
}

// ─── Leads ─────────────────────────────────────────
async function loadLeads(direction) {
    if (direction === 'next') leadsPage++;
    else if (direction === 'prev' && leadsPage > 0) leadsPage--;
    else if (!direction) leadsPage = 0;

    const offset = leadsPage * PAGE_SIZE;

    try {
        const leads = await fetchAPI(`/api/leads?limit=${PAGE_SIZE}&offset=${offset}`);
        const tbody = document.getElementById('leads-tbody');

        if (leads.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="empty-state">No leads detected yet</td></tr>';
        } else {
            tbody.innerHTML = leads.map(lead => `
                <tr>
                    <td><span class="badge badge-confidence ${getConfidenceClass(lead.confidence)}">${(lead.confidence * 100).toFixed(0)}%</span></td>
                    <td class="text-truncate">${escapeHtml(lead.raw_posts?.author || '?')}</td>
                    <td class="text-clamp-2">${escapeHtml(lead.raw_posts?.title || lead.raw_posts?.content || '')}</td>
                    <td class="text-clamp-2">${escapeHtml(lead.reason || '')}</td>
                    <td><span class="badge badge-service">${escapeHtml(lead.suggested_service || 'none')}</span></td>
                    <td>${lead.sentiment_score != null ? lead.sentiment_score.toFixed(2) : '—'}</td>
                    <td>${lead.raw_posts?.url ? `<a href="${lead.raw_posts.url}" target="_blank" rel="noopener">View ↗</a>` : '—'}</td>
                    <td><button class="btn btn-small btn-primary" onclick="openOutreachModal('${lead.id}')">📧 Send</button></td>
                </tr>
            `).join('');
        }

        document.getElementById('leads-page-info').textContent = `Page ${leadsPage + 1}`;
        document.getElementById('leads-prev').disabled = leadsPage === 0;
        document.getElementById('leads-next').disabled = leads.length < PAGE_SIZE;
    } catch (err) {
        console.error('Error loading leads:', err);
    }
}

// ─── Outreach ──────────────────────────────────────
async function loadOutreach() {
    try {
        const outreach = await fetchAPI('/api/outreach?limit=50');
        const tbody = document.getElementById('outreach-tbody');

        if (outreach.length === 0) {
            tbody.innerHTML = '<tr><td colspan="5" class="empty-state">No outreach data yet. This will populate in Phase 2.</td></tr>';
        } else {
            tbody.innerHTML = outreach.map(item => `
                <tr>
                    <td><span class="badge badge-platform">${item.channel}</span></td>
                    <td><span class="badge badge-status ${item.status}">${item.status}</span></td>
                    <td class="text-clamp-2">${escapeHtml(item.message_sent || '')}</td>
                    <td class="text-clamp-2">${escapeHtml(item.response_received || '—')}</td>
                    <td>${item.sent_at ? timeAgo(item.sent_at) : '—'}</td>
                </tr>
            `).join('');
        }
    } catch (err) {
        console.error('Error loading outreach:', err);
    }
}

// ─── Settings ──────────────────────────────────────
async function loadSettings() {
    try {
        const settings = await fetchAPI('/api/settings');

        // Tag inputs
        populateTags('subreddits', settings.subreddits || '');
        populateTags('services', settings.services || '');
        populateTags('keywords', settings.frustration_keywords || '');
        populateTags('mastodon', settings.mastodon_instances || 'mastodon.social,fosstodon.org,techhub.social');

        // Sliders
        const thresholdEl = document.getElementById('setting-threshold');
        thresholdEl.value = settings.confidence_threshold || '0.8';
        updateSliderLabel(thresholdEl);

        const sentimentEl = document.getElementById('setting-sentiment');
        sentimentEl.value = settings.sentiment_threshold || '-0.05';
        updateSliderLabel(sentimentEl);

        // Select
        document.getElementById('setting-model').value = settings.llm_model || 'gpt-4o-mini';

        // Number
        document.getElementById('setting-interval').value = settings.poll_interval_minutes || '10';

        // n8n webhook URL
        document.getElementById('setting-n8n').value = settings.n8n_webhook_url || '';

    } catch (err) {
        console.error('Error loading settings:', err);
        showToast('Failed to load settings', 'error');
    }
}

async function saveSettings(e) {
    e.preventDefault();

    const data = {
        subreddits: getTagValues('subreddits'),
        services: getTagValues('services'),
        frustration_keywords: getTagValues('keywords'),
        mastodon_instances: getTagValues('mastodon'),
        n8n_webhook_url: document.getElementById('setting-n8n').value.trim(),
        confidence_threshold: document.getElementById('setting-threshold').value,
        sentiment_threshold: document.getElementById('setting-sentiment').value,
        llm_model: document.getElementById('setting-model').value,
        poll_interval_minutes: document.getElementById('setting-interval').value,
    };

    try {
        await fetchAPI('/api/settings', { method: 'PUT', body: JSON.stringify(data) });
        showToast('✅ Settings saved successfully', 'success');

        const status = document.getElementById('save-status');
        status.textContent = '✓ Saved';
        status.classList.add('visible');
        setTimeout(() => status.classList.remove('visible'), 3000);
    } catch (err) {
        console.error('Error saving settings:', err);
        showToast('❌ Failed to save settings', 'error');
    }
}

// ─── Tag Input Logic ───────────────────────────────
function populateTags(name, csvValue) {
    const wrapper = document.getElementById(`${name}-tags-wrapper`);
    wrapper.innerHTML = '';

    const values = csvValue.split(',').map(v => v.trim()).filter(Boolean);
    values.forEach(val => addTag(name, val));

    // Set up Enter key handler
    const input = wrapper.parentElement.querySelector('.tag-input');
    input.onkeydown = (e) => {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = input.value.trim();
            if (val) {
                addTag(name, val);
                input.value = '';
            }
        } else if (e.key === 'Backspace' && !input.value) {
            const tags = wrapper.querySelectorAll('.tag');
            if (tags.length > 0) tags[tags.length - 1].remove();
        }
    };
}

function addTag(name, value) {
    const wrapper = document.getElementById(`${name}-tags-wrapper`);
    const tag = document.createElement('span');
    tag.className = 'tag';
    tag.innerHTML = `${escapeHtml(value)} <button class="tag-remove" onclick="this.parentElement.remove()" type="button">×</button>`;
    wrapper.appendChild(tag);
}

function getTagValues(name) {
    const wrapper = document.getElementById(`${name}-tags-wrapper`);
    const tags = wrapper.querySelectorAll('.tag');
    return Array.from(tags).map(t => {
        // Get text content minus the × button
        return t.firstChild.textContent.trim();
    }).join(',');
}

// ─── Slider Label ──────────────────────────────────
function updateSliderLabel(slider) {
    const labelId = slider.id.replace('setting-', '') + '-value';
    const label = document.getElementById(labelId);
    if (label) label.textContent = parseFloat(slider.value).toFixed(2);
}

// ─── Trigger Actions ───────────────────────────────
async function triggerCollect() {
    const btn = document.getElementById('btn-collect');
    btn.classList.add('loading');
    btn.querySelector('.btn-icon').textContent = '⏳';

    try {
        await fetchAPI('/api/collect', { method: 'POST' });
        showToast('🔍 Collection started across all platforms', 'info');
        setTimeout(() => loadOverview(), 5000); // Refresh after a delay
    } catch (err) {
        showToast('❌ Failed to start collection', 'error');
    } finally {
        setTimeout(() => {
            btn.classList.remove('loading');
            btn.querySelector('.btn-icon').textContent = '🔍';
        }, 3000);
    }
}

async function triggerAnalyze() {
    const btn = document.getElementById('btn-analyze');
    btn.classList.add('loading');
    btn.querySelector('.btn-icon').textContent = '⏳';

    try {
        await fetchAPI('/api/analyze', { method: 'POST' });
        showToast('🧠 Analysis started in background', 'info');
        setTimeout(() => loadOverview(), 10000); // Refresh after a delay
    } catch (err) {
        showToast('❌ Failed to start analysis', 'error');
    } finally {
        setTimeout(() => {
            btn.classList.remove('loading');
            btn.querySelector('.btn-icon').textContent = '🧠';
        }, 5000);
    }
}

// ─── Utilities ─────────────────────────────────────
async function fetchAPI(url, options = {}) {
    const response = await fetch(url, {
        headers: { 'Content-Type': 'application/json' },
        ...options,
    });
    if (!response.ok) throw new Error(`API error: ${response.status}`);
    return response.json();
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text || '';
    return div.innerHTML;
}

function formatNumber(n) {
    if (n == null) return '—';
    if (n >= 1000) return (n / 1000).toFixed(1) + 'k';
    return n.toString();
}

function timeAgo(dateStr) {
    if (!dateStr) return '—';
    const date = new Date(dateStr);
    const now = new Date();
    const seconds = Math.floor((now - date) / 1000);

    if (seconds < 60) return 'just now';
    if (seconds < 3600) return Math.floor(seconds / 60) + 'm ago';
    if (seconds < 86400) return Math.floor(seconds / 3600) + 'h ago';
    if (seconds < 604800) return Math.floor(seconds / 86400) + 'd ago';
    return date.toLocaleDateString();
}

function getConfidenceClass(confidence) {
    if (confidence >= 0.8) return '';
    if (confidence >= 0.5) return 'medium';
    return 'low';
}

function showToast(message, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    container.appendChild(toast);
    setTimeout(() => toast.remove(), 4000);
}

// ─── Import Handlers ───────────────────────────────
let importMode = 'text';

function setImportMode(mode) {
    importMode = mode;
    document.getElementById('import-text-panel').style.display = mode === 'text' ? 'block' : 'none';
    document.getElementById('import-csv-panel').style.display = mode === 'csv' ? 'block' : 'none';
    document.querySelectorAll('.import-mode-btn').forEach(b => b.classList.remove('active'));
    document.getElementById(`import-mode-${mode}`).classList.add('active');
}

async function submitImport() {
    let payload;

    if (importMode === 'csv') {
        const csv = document.getElementById('import-csv').value.trim();
        if (!csv) { showToast('Please paste some CSV data', 'error'); return; }
        payload = { type: 'csv', content: csv };
    } else {
        const text = document.getElementById('import-text').value.trim();
        if (!text) { showToast('Please enter some text', 'error'); return; }
        payload = {
            type: 'text',
            content: text,
            author: document.getElementById('import-author').value.trim() || 'manual',
            label: document.getElementById('import-label').value.trim(),
        };
    }

    try {
        const result = await fetchAPI('/api/import', {
            method: 'POST',
            body: JSON.stringify(payload),
        });

        const count = result.posts_inserted || 0;
        showToast(`📥 Imported ${count} post(s) successfully`, 'success');

        // Clear inputs
        document.getElementById('import-text').value = '';
        document.getElementById('import-csv').value = '';
        document.getElementById('import-author').value = '';
        document.getElementById('import-label').value = '';

        if (result.error) {
            showToast('⚠️ ' + result.error, 'error');
        }
    } catch (err) {
        showToast('❌ Import failed: ' + err.message, 'error');
    }
}

// ─── Outreach Modal ────────────────────────────────
let currentOutreachLeadId = null;
let currentOutreachMessage = null;

async function openOutreachModal(leadId) {
    currentOutreachLeadId = leadId;
    const modal = document.getElementById('outreach-modal');
    const statusEl = document.getElementById('modal-status');
    statusEl.textContent = 'Generating message...';
    document.getElementById('modal-subject').value = '';
    document.getElementById('modal-body').value = '';
    modal.style.display = 'flex';

    try {
        const message = await fetchAPI('/api/outreach/generate', {
            method: 'POST',
            body: JSON.stringify({ lead_id: leadId, channel: 'email' }),
        });

        currentOutreachMessage = message;
        document.getElementById('modal-subject').value = message.subject || '';
        document.getElementById('modal-body').value = message.body || '';
        statusEl.textContent = 'Review the message below, then click Save as Draft.';
    } catch (err) {
        statusEl.textContent = '❌ Failed to generate message.';
        showToast('❌ Message generation failed', 'error');
    }
}

async function confirmSendOutreach() {
    if (!currentOutreachLeadId || !currentOutreachMessage) return;

    try {
        await fetchAPI('/api/outreach/send', {
            method: 'POST',
            body: JSON.stringify({
                lead_id: currentOutreachLeadId,
                channel: 'email',
            }),
        });

        showToast('📧 Outreach draft saved!', 'success');
        closeOutreachModal();

        // Refresh outreach tab if visible
        if (currentTab === 'outreach') loadOutreach();
    } catch (err) {
        showToast('❌ Failed to save draft', 'error');
    }
}

function closeOutreachModal() {
    document.getElementById('outreach-modal').style.display = 'none';
    currentOutreachLeadId = null;
    currentOutreachMessage = null;
}
