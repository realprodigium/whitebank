// Sample bookmark data - Replace with actual data from backend
const sampleBookmarks = [];

// State management
let bookmarks = [];
let currentSort = 'latest';
let currentView = 'compact';
let searchTerm = '';

// Get user_id from URL params or localStorage
let userId = new URLSearchParams(window.location.search).get('user_id');
if (userId) {
    // Save to localStorage when received from auth
    localStorage.setItem('user_id', userId);
} else {
    // Try to restore from localStorage
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

// Initialize
document.addEventListener('DOMContentLoaded', () => {
    validateSession();
    attachEventListeners();
});

// Validate session on page load
async function validateSession() {
    if (!userId) {
        redirectToLogin('No se encontró sesión');
        return;
    }
    
    try {
        const res = await fetch(`/api/session?user_id=${userId}`);
        const data = await res.json();
        
        if (!data.authenticated) {
            // Session invalid, clear localStorage and redirect
            localStorage.removeItem('user_id');
            redirectToLogin('Sesión expirada. Por favor, inicia sesión nuevamente');
            return;
        }
        
        // Update username display
        if (usernameEl && data.username) {
            usernameEl.textContent = data.username;
        }
        
        // Session valid, load bookmarks
        loadBookmarks();
    } catch (err) {
        console.error('Error validating session:', err);
        // Assume session might be valid, try to load anyway
        loadBookmarks();
    }
}

function redirectToLogin(message) {
    if (message) {
        alert(message);
    }
    window.location.href = '/';
}

// Load and render bookmarks
function loadBookmarks() {
    if (!userId) {
        console.error('No user_id found in URL');
        showError('No se pudo identificar el usuario');
        return;
    }
    
    // Show loading state
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.innerHTML = '<div style="text-align: center; padding: 40px;">Cargando bookmarks...</div>';
    emptyState.style.display = 'none';
    
    fetchBookmarksWithRetry(0);
}

// Fetch with retry logic
function fetchBookmarksWithRetry(retryCount = 0, maxRetries = 3) {
    const timeout = setTimeout(() => {
        console.warn('Request timeout, retrying...');
        if (retryCount < maxRetries) {
            fetchBookmarksWithRetry(retryCount + 1, maxRetries);
        } else {
            showError('Tiempo de espera agotado al cargar bookmarks');
        }
    }, 15000); // 15 second timeout
    
    fetch(`/api/bookmarks?user_id=${userId}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
    })
        .then(res => {
            clearTimeout(timeout);
            
            if (!res.ok) {
                throw new Error(`HTTP ${res.status}`);
            }
            return res.json();
        })
        .then(data => {
            // Validate response structure
            if (!data) {
                throw new Error('Empty response');
            }
            
            // Extract bookmarks data
            const bookmarksList = data.data || data.bookmarks || [];
            
            if (!Array.isArray(bookmarksList)) {
                throw new Error('Invalid data format');
            }
            
            // Map tweets to bookmarks format
            bookmarks = bookmarksList.map(tweet => ({
                id: tweet.id || 'unknown',
                content: tweet.text || 'Sin contenido',
                created_at: tweet.created_at || new Date().toISOString()
            })).filter(b => b.id && b.id !== 'unknown');
            
            if (bookmarks.length === 0) {
                showEmpty();
            } else {
                renderBookmarks();
            }
            updateStats();
        })
        .catch(err => {
            clearTimeout(timeout);
            console.error('Error loading bookmarks:', err);
            
            // Retry logic
            if (retryCount < maxRetries) {
                console.log(`Reintentando... (${retryCount + 1}/${maxRetries})`);
                setTimeout(() => {
                    fetchBookmarksWithRetry(retryCount + 1, maxRetries);
                }, Math.min(1000 * Math.pow(2, retryCount), 5000)); // Exponential backoff
            } else {
                showError(`No se pudieron cargar los bookmarks después de ${maxRetries} intentos. Por favor, recarga la página.`);
            }
        });
}

function showEmpty() {
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.style.display = 'none';
    emptyState.style.display = 'flex';
}

function showError(message) {
    const tableContainer = document.querySelector('.table-container');
    const emptyState = document.getElementById('emptyState');
    tableContainer.innerHTML = `
        <div style="text-align: center; padding: 40px; color: #e74c3c;">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="margin-bottom: 20px;">
                <circle cx="12" cy="12" r="10"></circle>
                <line x1="12" y1="8" x2="12" y2="12"></line>
                <line x1="12" y1="16" x2="12.01" y2="16"></line>
            </svg>
            <p>${message}</p>
            <button onclick="location.reload()" style="margin-top: 20px; padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer;">
                Recargar página
            </button>
        </div>
    `;
    emptyState.style.display = 'none';
}

// Render bookmarks to table
function renderBookmarks() {
    const filteredBookmarks = getFilteredBookmarks();
    const sortedBookmarks = getSortedBookmarks(filteredBookmarks);
    
    bookmarksBody.innerHTML = '';
    
    if (sortedBookmarks.length === 0) {
        emptyState.style.display = 'flex';
        document.querySelector('.table-container').style.display = 'none';
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

// Create bookmark row
function createBookmarkRow(bookmark, index) {
    const tr = document.createElement('tr');
    tr.style.animationDelay = `${index * 30}ms`;
    
    tr.innerHTML = `
        <td>
            <span class="bookmark-id">${bookmark.id}</span>
        </td>
        <td>
            <div class="bookmark-content">${bookmark.content}</div>
        </td>
        <td>
            <span class="bookmark-date">${formatDate(bookmark.created_at)}</span>
        </td>
        <td>
            <div class="actions">
                <button class="action-btn" onclick="editBookmark('${bookmark.id}')" aria-label="Editar">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                        <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                    </svg>
                </button>
                <button class="action-btn delete" onclick="deleteBookmark('${bookmark.id}')" aria-label="Eliminar">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <polyline points="3 6 5 6 21 6"></polyline>
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                    </svg>
                </button>
            </div>
        </td>
    `;
    
    return tr;
}

// Filter bookmarks by search term
function getFilteredBookmarks() {
    if (!searchTerm) return bookmarks;
    
    const term = searchTerm.toLowerCase();
    return bookmarks.filter(bookmark => 
        bookmark.id.toLowerCase().includes(term) ||
        bookmark.content.toLowerCase().includes(term)
    );
}

// Sort bookmarks
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

// Format date
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

// Update statistics
function updateStats() {
    const filtered = getFilteredBookmarks();
    totalBookmarksEl.textContent = bookmarks.length;
    visibleBookmarksEl.textContent = filtered.length;
}

// Event listeners
function attachEventListeners() {
    // Logout button
    if (logoutBtn) {
        logoutBtn.addEventListener('click', async (e) => {
            e.preventDefault();
            if (confirm('¿Estás seguro de que deseas cerrar sesión?')) {
                logout();
            }
        });
    }
    
    // Sort buttons
    sortButtons.forEach(btn => {
        btn.addEventListener('click', () => {
            currentSort = btn.dataset.sort;
            sortButtons.forEach(b => b.classList.remove('active'));
            btn.classList.add('active');
            renderBookmarks();
        });
    });
    
    // View buttons
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
    
    // Search input
    searchInput.addEventListener('input', (e) => {
        searchTerm = e.target.value;
        renderBookmarks();
    });
    
    // Add initial compact view class
    document.body.classList.add('view-compact');
}

async function logout() {
    try {
        await fetch(`/api/logout?user_id=${userId}`);
    } catch (err) {
        console.error('Error logging out:', err);
    } finally {
        // Clear session regardless
        localStorage.removeItem('user_id');
        redirectToLogin('Sesión cerrada');
    }
}

// Action handlers (to be implemented)
function editBookmark(id) {
    console.log('Edit bookmark:', id);
    // Implement edit functionality
    alert(`Editar bookmark ${id} - Funcionalidad a implementar`);
}

function deleteBookmark(id) {
    console.log('Delete bookmark:', id);
    if (confirm('¿Estás seguro de que deseas eliminar este bookmark?')) {
        bookmarks = bookmarks.filter(b => b.id !== id);
        renderBookmarks();
        // In production: send DELETE request to backend
        // fetch(`/api/bookmarks/${id}`, { method: 'DELETE' })
    }
}

// Keyboard shortcuts
document.addEventListener('keydown', (e) => {
    // Ctrl/Cmd + K to focus search
    if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
        e.preventDefault();
        searchInput.focus();
    }
    
    // Escape to clear search
    if (e.key === 'Escape' && document.activeElement === searchInput) {
        searchInput.value = '';
        searchTerm = '';
        renderBookmarks();
        searchInput.blur();
    }
});
