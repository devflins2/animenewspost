// State Store
let allPosts = [];
let selectedPost = null;
let currentFilter = 'all';
let searchQuery = '';
let isPublishing = false;

// API Endpoints
const BACKEND_BASE = window.location.origin.includes('http') ? window.location.origin : 'http://localhost:5000';
const DIRECT_API_URL = 'https://animeapinews.onrender.com/api/v1/posts';

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    initApp();
});

async function initApp() {
    await fetchStatus();
    await fetchFeed();
    await loadHistory();
}

// Fetch Bot Status & Stats
async function fetchStatus() {
    try {
        const res = await fetch(`${BACKEND_BASE}/api/status`);
        if (res.ok) {
            const data = await res.json();
            if (data.success && data.account) {
                document.getElementById('nav-handle').textContent = `@${data.account.username || 'anireport_'}`;
                document.getElementById('ig-preview-username').textContent = data.account.username || 'anireport_';
                document.getElementById('nav-acc-type').textContent = `${data.account.account_type || 'Business'} Connected`;
                document.getElementById('stat-total-published').textContent = data.stats.total_posted || '0';
                document.getElementById('stat-frequency').textContent = `Every ${data.stats.interval_minutes || 60}m`;
            }
        }
    } catch (e) {
        console.log('Running in static mode, using default handle.');
    }
}

// Fetch Anime News Feed
async function fetchFeed() {
    const container = document.getElementById('articles-container');
    container.innerHTML = `
        <div class="loading-state">
            <div class="spinner"></div>
            <p>Fetching real-time anime news from API...</p>
        </div>
    `;

    try {
        let data;
        try {
            const res = await fetch(`${BACKEND_BASE}/api/posts`);
            if (res.ok) data = await res.json();
        } catch (e) {
            console.log('Backend not detected, falling back to direct API...');
        }

        if (!data) {
            const directRes = await fetch(DIRECT_API_URL);
            const directData = await directRes.json();
            data = {
                success: true,
                posts: (directData.data || directData).map(p => ({
                    ...p,
                    is_posted: false,
                    generated_image_url: `https://animeapinews.onrender.com/api/v1/posts/${p.id}/image?ratio=4%3A5&handle=%40anireport_`
                }))
            };
        }

        allPosts = data.posts || [];
        updateStats();
        renderArticles();

        if (allPosts.length > 0 && !selectedPost) {
            selectArticle(allPosts[0].id);
        }
        
        showToast('Feed refreshed successfully!', 'info');
    } catch (err) {
        console.error('Feed error:', err);
        container.innerHTML = `
            <div class="loading-state">
                <p style="color: var(--danger)">❌ Failed to connect to Anime News API.</p>
                <button class="btn btn-sm btn-outline" onclick="fetchFeed()">Try Again</button>
            </div>
        `;
    }
}

// Update Header Counters
function updateStats() {
    const total = allPosts.length;
    const published = allPosts.filter(p => p.is_posted).length;
    const pending = total - published;

    document.getElementById('stat-total-articles').textContent = total;
    document.getElementById('stat-total-published').textContent = published;
    document.getElementById('stat-pending-queue').textContent = pending;
    document.getElementById('feed-count-badge').textContent = `${total} Articles`;
}

// Render News Cards List
function renderArticles() {
    const container = document.getElementById('articles-container');
    
    let filtered = allPosts.filter(p => {
        if (currentFilter === 'unposted') return !p.is_posted;
        if (currentFilter === 'posted') return p.is_posted;
        return true;
    });

    if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        filtered = filtered.filter(p => 
            (p.title && p.title.toLowerCase().includes(q)) || 
            (p.source && p.source.toLowerCase().includes(q)) ||
            (p.tags && p.tags.some(t => t.toLowerCase().includes(q)))
        );
    }

    if (filtered.length === 0) {
        container.innerHTML = `
            <div class="loading-state">
                <p>No articles found matching filter.</p>
            </div>
        `;
        return;
    }

    container.innerHTML = filtered.map(p => {
        const isSelected = selectedPost && selectedPost.id === p.id;
        const statusBadge = p.is_posted 
            ? `<span class="badge badge-success">✓ Published</span>` 
            : `<span class="badge badge-warning">⏳ In Queue</span>`;

        return `
            <div class="article-item ${isSelected ? 'selected' : ''}" onclick="selectArticle('${p.id}')" id="article-${p.id}">
                <img class="article-thumb" src="${p.original_image_url || 'https://via.placeholder.com/80x100'}" alt="News Thumbnail" onerror="this.src='https://via.placeholder.com/80x100?text=News'">
                <div class="article-body">
                    <div class="article-meta-row">
                        <span class="article-badge">${p.badge || 'NEWS'}</span>
                        ${statusBadge}
                    </div>
                    <h4 class="article-headline">${escapeHtml(p.title || 'Untitled News')}</h4>
                    <div class="article-source-row">
                        <span>📌 ${escapeHtml(p.source || 'Anime News Network')}</span>
                        <span>•</span>
                        <span>${formatDate(p.date)}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
}

// Select Article and Update Instagram Visualizer
function selectArticle(id) {
    const post = allPosts.find(p => p.id === id);
    if (!post) return;

    selectedPost = post;

    document.querySelectorAll('.article-item').forEach(el => el.classList.remove('selected'));
    const itemEl = document.getElementById(`article-${id}`);
    if (itemEl) itemEl.classList.add('selected');

    const imgEl = document.getElementById('ig-preview-image');
    const badgeOverlay = document.getElementById('ig-preview-badge-overlay');
    const captionEl = document.getElementById('ig-preview-caption');

    const handle = encodeURIComponent('@anireport_');
    const imgUrl = `https://animeapinews.onrender.com/api/v1/posts/${post.id}/image?ratio=4%3A5&handle=${handle}`;
    
    imgEl.src = imgUrl;
    badgeOverlay.textContent = post.badge || 'BREAKING NEWS';
    
    captionEl.textContent = post.custom_caption || buildClientCaption(post);

    const btnPublish = document.getElementById('btn-publish-selected');
    if (post.is_posted) {
        btnPublish.innerHTML = `<span class="btn-icon">✓</span><span>Already Published to Instagram</span>`;
        btnPublish.disabled = true;
    } else {
        btnPublish.innerHTML = `<span class="btn-icon">🚀</span><span>Publish This Post to Instagram</span>`;
        btnPublish.disabled = false;
    }
}

// Client Fallback Caption Builder with Full Details & Dates
function buildClientCaption(post) {
    const badge = (post.badge || 'BREAKING NEWS').toUpperCase();
    const title = post.title || 'Untitled News';
    const excerpt = post.excerpt || '';
    const source = post.source || 'Anime News Network';
    const dateFormatted = post.date ? new Date(post.date).toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' }) : 'Recently Announced';
    const tags = (post.tags || []).map(t => `#${t.replace(/[^a-zA-Z0-9]/g, '')}`).join(' ');

    let lines = [
        `📢 ${badge}: ${title}`,
        '',
        '━━━━━━━━━━━━━━━━━━━━━',
        `📅 Announced: ${dateFormatted}`,
        `🎬 Release / Debut: Official Broadcast Timing`,
        `📌 Source: ${source}`,
        `🏷️ Category: ${badge}`,
        '━━━━━━━━━━━━━━━━━━━━━',
        '',
        '📖 FULL STORY & DETAILS:',
        excerpt || title,
        '',
        '━━━━━━━━━━━━━━━━━━━━━',
        '💬 What are your thoughts on this? Are you excited for this release? Let us know in the comments below! 👇',
        '',
        '👉 Follow @anireport_ for daily breaking anime news, release dates & trailer updates!',
        '.',
        '.',
        '.',
        `#animenews #anime #manga #otaku #animecommunity ${tags}`
    ];

    return lines.join('\n');
}

// Publish Selected Article
async function publishSelectedArticle() {
    if (!selectedPost || isPublishing) return;
    
    const btn = document.getElementById('btn-publish-selected');
    
    isPublishing = true;
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner" style="width:18px;height:18px;border-width:2px;display:inline-block"></div> Publishing to Instagram...`;

    try {
        const res = await fetch(`${BACKEND_BASE}/api/publish-specific`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ post_id: selectedPost.id })
        });

        const data = await res.json();
        if (data.success) {
            showToast(`🎉 Published "${selectedPost.title.slice(0, 30)}..." successfully!`, 'success');
            selectedPost.is_posted = true;
            await fetchFeed();
            await loadHistory();
        } else {
            showToast(`❌ Publish failed: ${data.error || 'Unknown error'}`, 'error');
        }
    } catch (e) {
        showToast(`❌ Error: Ensure local server is running (python server.py)`, 'error');
    } finally {
        isPublishing = false;
        selectArticle(selectedPost.id);
    }
}

// Publish Next Unposted Article in Queue
async function publishNextInQueue() {
    if (isPublishing) return;
    
    const btn = document.getElementById('btn-publish-next');
    isPublishing = true;
    btn.disabled = true;
    btn.innerHTML = `<div class="spinner" style="width:16px;height:16px;border-width:2px;display:inline-block"></div> Posting...`;

    try {
        const res = await fetch(`${BACKEND_BASE}/api/publish-next`, { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            showToast(`🎉 Successfully posted next news to Instagram!`, 'success');
            await fetchFeed();
            await loadHistory();
        } else {
            showToast(`⚠️ ${data.error || 'No unposted news available'}`, 'warning');
        }
    } catch (e) {
        showToast(`❌ Error: Ensure local server is running (python server.py)`, 'error');
    } finally {
        isPublishing = false;
        btn.disabled = false;
        btn.innerHTML = `<span class="btn-icon">⚡</span><span>Post Next Unposted</span>`;
    }
}

// Load Published History
async function loadHistory() {
    const tbody = document.getElementById('history-tbody');
    try {
        const res = await fetch(`${BACKEND_BASE}/api/history`);
        if (res.ok) {
            const data = await res.json();
            const history = data.history || [];
            
            if (history.length === 0) {
                tbody.innerHTML = `<tr><td colspan="5" class="empty-state">No published posts in history yet.</td></tr>`;
                return;
            }

            tbody.innerHTML = history.slice().reverse().map((h, i) => `
                <tr>
                    <td><strong>#${history.length - i}</strong></td>
                    <td><strong>${escapeHtml(h.title || 'Anime News Post')}</strong></td>
                    <td style="color: var(--text-dim)">${h.posted_at ? h.posted_at.replace('T', ' ').slice(0, 19) : '--'}</td>
                    <td><code>${h.instagram_media_id || 'N/A'}</code></td>
                    <td><span class="badge badge-success">✓ Published</span></td>
                </tr>
            `).join('');
        }
    } catch (e) {
        tbody.innerHTML = `<tr><td colspan="5" class="empty-state">Unable to load history. Start server with python server.py.</td></tr>`;
    }
}

// Filter Tabs
function setFilter(filter) {
    currentFilter = filter;
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.filter === filter);
    });
    renderArticles();
}

// Search Handler
function handleSearch(val) {
    searchQuery = val;
    renderArticles();
}

// Copy Caption to Clipboard
function copyCaption() {
    const caption = document.getElementById('ig-preview-caption').textContent;
    navigator.clipboard.writeText(caption).then(() => {
        showToast('📋 Detailed caption copied to clipboard!', 'success');
    }).catch(() => {
        showToast('Failed to copy caption.', 'error');
    });
}

// Open Original Source Link
function openOriginalSource() {
    if (selectedPost && selectedPost.link) {
        window.open(selectedPost.link, '_blank');
    } else {
        showToast('No external source link available.', 'info');
    }
}

// Open Generated Graphic Full Image
function openGeneratedImage() {
    const imgEl = document.getElementById('ig-preview-image');
    if (imgEl && imgEl.src) {
        window.open(imgEl.src, '_blank');
    }
}

// Toast Notifications
function showToast(msg, type = 'info') {
    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icon = type === 'success' ? '✅' : (type === 'error' ? '❌' : 'ℹ️');
    toast.innerHTML = `<span>${icon}</span><span>${escapeHtml(msg)}</span>`;
    
    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateX(100%)';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// Utilities
function escapeHtml(str) {
    if (!str) return '';
    return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function formatDate(dStr) {
    if (!dStr) return 'Recent';
    try {
        const d = new Date(dStr);
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    } catch {
        return 'Recent';
    }
}
