// State management
let bookmarks = [];
let currentSort = 'latest';
let currentView = 'compact';
let searchTerm = '';

// Get user_id from URL params or localStorage
let userId = new URLSearchParams(window.location.search).get('user_id');
if (userId) {
    localStorage.setItem('user_id', userId);
} else {
    userId = localStorage.getItem('user_id');
}

// DOM Elements
const bookmarksBody = document.getElementById('bookmarksBody');
const emptyState = document.getElementById('emptyState');
const totalBookmarksEl = document.getElementById('totalBookmarks');
const visibleBookmarksEl = document.getElementById('visibleBookmarks');
const searchInput = document.getElementById('search');
const sortButtons = document.querySelectorAll('.sort-btn');
const viewButtons = document.querySelectorAll('.view-btn');
const logoutBtn = document.querySelector('.logout-btn');
const usernameEl = document.getElementById('username');

document.addEventListener('DOMContentLoaded', () => {
    validateSession();
    attachEventListeners();
});

async function validateSession() {
    if (!userId) {
        redirectToLogin('No se encontró sesión');
        return;
    }
    
    try {
        const res = await fetch(`/api/session?user_id=${userId}`);
        const data = await res.json();
        
        if (!data.authenticated) {
            localStorage.removeItem('user_id');
            redirectToLogin('Sesión expirada. Por favor, inicia sesión nuevamente');
            return;
        }
        
        if (usernameEl && data.username) {
            usernameEl.textContent = `@${data.username}`;
        }
        
        loadBookmarks();
    } catch (err) {
        console.error('Error validating session:', err);
        loadBookmarks();
    }
}

function redirectToLogin(message) {
    if (message) {
        alert(message);
    }
    window.location.href = '/';
}

function loadBookmarks(retryCount = 0) {
    if (!userId) {
        console.error('No user_id found');
        showError('No se pudo identificar el usuario');
        return;
    }
    
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.innerHTML = '<div style="text-align: center; padding: 40px; color: #6C757D;">Cargando bookmarks...</div>';
    emptyState.style.display = 'none';
    
    console.log('Fetching bookmarks for user:', userId, `(Attempt ${retryCount + 1})`);
    
    fetch(`/api/bookmarks?user_id=${userId}&max_results=100`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(res => {
            console.log('Response status:', res.status);
            
            if (res.status === 401) {
                localStorage.removeItem('user_id');
                redirectToLogin('Sesión expirada. Por favor, inicia sesión nuevamente');
                throw new Error('Unauthorized');
            }
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            console.log('API Response:', data);
            
            if (!data) {
                throw new Error('Empty response');
            }
            
            const bookmarksList = data.data || [];
            const message = data.message || '';
            
            console.log('Bookmarks received:', bookmarksList.length);
            console.log('Response message:', message);
            
            if (message && message.includes('Rate limited') && retryCount < 3) {
                console.log('Rate limited, retrying in 2 seconds...');
                setTimeout(() => {
                    loadBookmarks(retryCount + 1);
                }, 2000 * (retryCount + 1));
                return;
            }
            
            if (!Array.isArray(bookmarksList)) {
                console.error('Invalid data format:', typeof bookmarksList);
                throw new Error('Invalid data format');
            }
            
            bookmarks = bookmarksList.map(tweet => ({
                id: tweet.id || 'unknown',
                content: tweet.text || 'Sin contenido',
                created_at: tweet.created_at || new Date().toISOString(),
                author_id: tweet.author_id
            })).filter(b => b.id && b.id !== 'unknown');
            
            console.log(`Processed ${bookmarks.length} bookmarks`);
            
            if (bookmarks.length === 0) {
                if (message && message.includes('Rate limited')) {
                    showError('La API está siendo utilizada intensamente. Intenta más tarde.');
                } else {
                    showEmpty(
                        'No tienes bookmarks guardados en X',
                        'Ve a X (Twitter), haz clic en el ícono de bookmark en cualquier tweet para guardarlo, y luego recarga esta página.'
                    );
                }
            } else {
                renderBookmarks();
            }
            updateStats();
        })
        .catch(err => {
            console.error('Error loading bookmarks:', err);
            if (err.message !== 'Unauthorized') {
                showError('Error al cargar bookmarks. Verifica tu conexión e intenta nuevamente.');
            }
        });
}

function showEmpty(message = 'No se encontraron bookmarks', hint = '') {
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.style.display = 'none';
    emptyState.style.display = 'flex';
    
    emptyState.innerHTML = `
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: #ADB5BD;">
            <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
        </svg>
        <p style="color: #6C757D; margin-bottom: 8px; font-weight: 500;">${message}</p>
        ${hint ? `<p style="color: #ADB5BD; font-size: 0.875rem; max-width: 400px; text-align: center;">${hint}</p>` : ''}
        <a href="https://x.com" target="_blank" style="margin-top: 20px; padding: 10px 20px; background: #1B2434; color: white; border: none; border-radius: 8px; cursor: pointer; text-decoration: none; font-family: inherit; display: inline-block;">
            Ir a X para guardar bookmarks
        </a>
    `;
}

function showError(message) {
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #DC2626;">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-bottom: 20px;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <p style="margin-bottom: 20px;">${message}</p>
            <button onclick="loadBookmarks()" style="padding: 10px 20px; background: #1B2434; color: white; border: none; border-radius: 8px; cursor: pointer; font-family: inherit;">
                Reintentar
            </button>
        </div>
    `;
    emptyState.style.display = 'none';
}

function renderBookmarks() {
    const filteredBookmarks = getFilteredBookmarks();
    const sortedBookmarks = getSortedBookmarks(filteredBookmarks);
    
    bookmarksBody.innerHTML = '';
    
    if (sortedBookmarks.length === 0) {
        if (searchTerm) {
            emptyState.style.display = 'flex';
            emptyState.innerHTML = `
                <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: #ADB5BD;">
                    <circle cx="11" cy="11" r="8"></circle>
                    <path d="m21 21-4.35-4.35"></path>
                </svg>
                <p style="color: #6C757D;">No se encontraron resultados para "${searchTerm}"</p>
            `;
            document.querySelector('.table-container').style.display = 'none';
        } else {
            showEmpty('No tienes bookmarks guardados en X');
        }
    } else {
        emptyState.style.display = 'none';
        document.querySelector('.table-container').style.display = 'block';
        
        sortedBookmarks.forEach((bookmark, index) => {
            const row = createBookmarkRow(bookmark, index);
            bookmarksBody.appendChild(row);
        });
    }
    
    updateStats();
}

function createBookmarkRow(bookmark, index) {
    const tr = document.createElement('tr');
    tr.style.animationDelay = `${index * 30}ms`;
    
    tr.innerHTML = `
        <td>
            <span class="bookmark-id">${bookmark.id}</span>
        </td>
        <td>
            <div class="bookmark-content">${escapeHtml(bookmark.content)}</div>
        </td>
        <td>
            <span class="bookmark-date">${formatDate(bookmark.created_at)}</span>
        </td>
        <td>
            <div class="actions">
                <a href="https://x.com/i/web/status/${bookmark.id}" target="_blank" class="action-btn" aria-label="Ver en X">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                        <polyline points="15 3 21 3 21 9"></polyline>
                        <line x1="10" y1="14" x2="21" y2="3"></line>
                    </svg>
                </a>
            </div>
        </td>
    `;
    
    return tr;
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function getFilteredBookmarks() {
    if (!searchTerm) return bookmarks;
    
    const term = searchTerm.toLowerCase();
    return bookmarks.filter(bookmark => 
        bookmark.id.toLowerCase().includes(term) ||
        bookmark.content.toLowerCase().includes(term)
    );
}
function getSortedBookmarks(bookmarksToSort) {
    const sorted = [...bookmarksToSort];
    
    switch (currentSort) {
        case 'latest':
            return sorted.sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
        case 'oldest':
            return sorted.sort((a, b) => new Date(a.created_at) - new Date(b.created_at));
        case 'alpha':
            return sorted.sort((a, b) => a.content.localeCompare(b.content));
        case 'reverse_alpha':
            return sorted.sort((a, b) => b.content.localeCompare(a.content));
        default:
            return sorted;
    }
}

function formatDate(dateString) {
    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);
    
    if (diffMins < 60) {
        return `Hace ${diffMins} min`;
    } else if (diffHours < 24) {
        return `Hace ${diffHours}h`;
    } else if (diffDays < 7) {
        return `Hace ${diffDays}d`;
    } else {
        return date.toLocaleDateString('es-ES', {
            day: '2-digit',
            month: 'short',
            year: 'numeric'
        });
    }
}

function updateStats() {
    const filtered = getFilteredBookmarks();
    totalBookmarksEl.textContent = bookmarks.length;
    visibleBookmarksEl.textContent = filtered.length;
}

function attachEventListeners() {
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (confirm('¿Estás seguro de que deseas cerrar sesión?')) {
                logout();
            }
        });
    }
    
    sortButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            currentSort = btn.dataset.sort;
            sortButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderBookmarks();
        });
    });
    
    viewButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            currentView = btn.dataset.view;
            viewButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            
            if (currentView === 'compact') {
                document.body.classList.add('view-compact');
            } else {
                document.body.classList.remove('view-compact');
            }
        });
    });
    
    searchInput.addEventListener('input', (e) => {
        searchTerm = e.target.value;
        renderBookmarks();
    });
    
    document.body.classList.add('view-compact');
}

async function logout() {
    try {
        await fetch(`/api/logout?user_id=${userId}`);
    } catch (err) {
        console.error('Error logging out:', err);
    } finally {
        localStorage.removeItem('user_id');
        redirectToLogin('Sesión cerrada');
    }
}

document.addEventListener('keydown', (e) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
    }
    
    if (e.key === 'Escape' && document.activeElement === searchInput) {
        searchInput.value = '';
        searchTerm = '';
        renderBookmarks();
        searchInput.blur();
    }
});
window.loadBookmarks = loadBookmarks;