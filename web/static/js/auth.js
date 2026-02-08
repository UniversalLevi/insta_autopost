// Authentication functions for InstaForge (var allows safe redeclaration if script loaded twice)
var API_BASE = window.API_BASE || '/api';
var AUTH_BASE = window.AUTH_BASE || '/auth';
window.API_BASE = API_BASE;
window.AUTH_BASE = AUTH_BASE;

// Get session token from localStorage or cookie
function getSessionToken() {
    // Try localStorage first
    const token = localStorage.getItem('session_token');
    if (token) {
        return token;
    }
    
    // Fallback to cookie (for server-set cookies)
    const cookies = document.cookie.split(';');
    for (let cookie of cookies) {
        const [name, value] = cookie.trim().split('=');
        if (name === 'session_token') {
            return value;
        }
    }
    
    return null;
}

// Set session token
function setSessionToken(token) {
    localStorage.setItem('session_token', token);
}

// Clear session token
function clearSessionToken() {
    localStorage.removeItem('session_token');
}

// Check if user is authenticated
async function checkAuth() {
    try {
        const user = await getCurrentUser();
        return user !== null;
    } catch (error) {
        return false;
    }
}

// Login
async function login(username, password) {
    const response = await fetch(`${AUTH_BASE}/login`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        credentials: 'include',
        body: JSON.stringify({ username, password }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.detail || 'Login failed');
    }
    
    // Store token if provided
    if (data.token) {
        setSessionToken(data.token);
    }
    
    return data;
}

// Logout
async function logout() {
    try {
        const token = getSessionToken();
        
        await fetch(`${AUTH_BASE}/logout`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : '',
            },
            credentials: 'include',
        });
    } catch (error) {
        console.error('Logout error:', error);
    } finally {
        clearSessionToken();
        window.location.href = '/login';
    }
}

// Register
async function register(userData) {
    const response = await fetch(`${AUTH_BASE}/register`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(userData),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.detail || 'Registration failed');
    }
    
    return data;
}

// Get current user
async function getCurrentUser() {
    try {
        const token = getSessionToken();
        
        const response = await fetch(`${AUTH_BASE}/me`, {
            method: 'GET',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': token ? `Bearer ${token}` : '',
            },
            credentials: 'include',
        });
        
        if (!response.ok) {
            if (response.status === 401) {
                clearSessionToken();
                return null;
            }
            throw new Error('Failed to get user info');
        }
        
        const data = await response.json();
        return data;
    } catch (error) {
        console.error('Get current user error:', error);
        clearSessionToken();
        return null;
    }
}

// Change password
async function changePassword(currentPassword, newPassword) {
    const token = getSessionToken();
    
    const response = await fetch(`${AUTH_BASE}/change-password`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Authorization': token ? `Bearer ${token}` : '',
        },
        credentials: 'include',
        body: JSON.stringify({
            current_password: currentPassword,
            new_password: newPassword,
        }),
    });
    
    const data = await response.json();
    
    if (!response.ok) {
        throw new Error(data.detail || 'Failed to change password');
    }
    
    return data;
}

// Make authenticated fetch request
async function authenticatedFetch(url, options = {}) {
    const token = getSessionToken();
    
    const headers = {
        'Content-Type': 'application/json',
        ...options.headers,
    };
    
    if (token) {
        headers['Authorization'] = `Bearer ${token}`;
    }
    
    const response = await fetch(url, {
        ...options,
        headers,
        credentials: 'include',
    });
    
    // If unauthorized, clear token and redirect to login
    if (response.status === 401) {
        clearSessionToken();
        if (window.location.pathname !== '/login' && window.location.pathname !== '/register') {
            window.location.href = '/login';
        }
        throw new Error('Unauthorized');
    }
    
    return response;
}
