from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse, JSONResponse
import httpx
import asyncio
import secrets
import os
import hashlib
import base64
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from typing import Optional
import json
import time

load_dotenv()

router = APIRouter()
DB_PATH = 'bookmarks.db'

bookmarks_cache = {}

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS oauth_states (
            state TEXT PRIMARY KEY,
            code_verifier TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            expires_at TIMESTAMP
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS user_tokens (
            user_id TEXT PRIMARY KEY,
            access_token TEXT NOT NULL,
            refresh_token TEXT,
            username TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn 

def generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


async def refresh_access_token(user_id: str) -> Optional[str]:
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT refresh_token FROM user_tokens WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row or not row['refresh_token']:
            print(f'No refresh token found for user {user_id}')
            return None
        
        refresh_token = row['refresh_token']
        client_id = os.getenv('CLIENT_ID')
        client_secret = os.getenv('CLIENT_SECRET')
        
        if not client_id or not client_secret:
            print(f'Missing CLIENT_ID or CLIENT_SECRET in environment')
            return None
        
        token_url = 'https://api.x.com/2/oauth2/token'
        
        credentials = f'{client_id}:{client_secret}'
        b64_credentials = base64.b64encode(credentials.encode()).decode()
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {b64_credentials}'
        }
        
        data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token
        }
        
        print(f'Attempting to refresh token for user {user_id}')
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(token_url, headers=headers, data=data)
            
            print(f'Token refresh response status: {response.status_code}')
            
            if response.status_code == 200:
                tokens = response.json()
                new_access_token = tokens.get('access_token')
                new_refresh_token = tokens.get('refresh_token', refresh_token)
                
                if not new_access_token:
                    print('No access_token in refresh response')
                    return None
                
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute(
                    'UPDATE user_tokens SET access_token = ?, refresh_token = ?, updated_at = ? WHERE user_id = ?',
                    (new_access_token, new_refresh_token, datetime.now().isoformat(), user_id)
                )
                conn.commit()
                conn.close()
                
                print(f'Token refreshed successfully for user {user_id}')
                return new_access_token
            else:
                print(f'Token refresh failed: {response.status_code} - {response.text}')
                return None
    except Exception as e:
        print(f'Error refreshing token: {str(e)}')
        import traceback
        traceback.print_exc()
        return None


@router.get('/auth/x/login')
def login():
    client_id = os.getenv('CLIENT_ID')
    redirect_uri = 'http://localhost:8000/auth/x/callback'

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()

    conn = get_db_connection()
    cursor = conn.cursor()
    expires_at = (datetime.now() + timedelta(minutes=10)).isoformat()
    cursor.execute(
        'INSERT INTO oauth_states (state, code_verifier, expires_at) VALUES (?, ?, ?)',
        (state, code_verifier, expires_at)
    )
    conn.commit()
    conn.close()

    scopes = 'tweet.read users.read bookmark.read offline.access'
    auth_url = (
        f"https://x.com/i/oauth2/authorize?"
        f"response_type=code&"
        f"client_id={client_id}&"
        f"redirect_uri={redirect_uri}&"
        f"scope={scopes}&"
        f"state={state}&"
        f"code_challenge={code_challenge}&"
        f"code_challenge_method=S256"
    )
    return RedirectResponse(auth_url)

@router.get('/auth/x/callback')
async def callback(request: Request):
    code = request.query_params.get('code')
    state = request.query_params.get('state')

    if not code or not state:
        return {'error': 'invalid request'}
    
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT code_verifier FROM oauth_states WHERE state = ?', (state,))
    row = cursor.fetchone()
    
    if not row:
        conn.close()
        return {'error': 'invalid state'}
    
    code_verifier = row['code_verifier']
    
    cursor.execute('DELETE FROM oauth_states WHERE state = ?', (state,))
    conn.commit()
    conn.close()

    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = 'http://localhost:8000/auth/x/callback'
    token_url = 'https://api.x.com/2/oauth2/token'

    credentials = f'{client_id}:{client_secret}'
    b64_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {b64_credentials}'
    }

    data = {
        'code': code,
        'grant_type': 'authorization_code',
        'redirect_uri': redirect_uri,
        'code_verifier': code_verifier
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)
        if response.status_code != 200:
            return {'error': 'token request failed', 'details': response.json()}
        tokens = response.json()
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token') 
        
        user_info_headers = {'Authorization': f'Bearer {access_token}'}
        user_response = await client.get('https://api.x.com/2/users/me', headers=user_info_headers)
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            user_id = user_data['data']['id']
            username = user_data['data']['username']
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO user_tokens (user_id, access_token, refresh_token, username, updated_at) VALUES (?, ?, ?, ?, ?)',
                (user_id, access_token, refresh_token, username, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            
            return RedirectResponse(url=f'/dashboard?user_id={user_id}', status_code=303)
        else:
            return {'error': 'failed to get user info', 'details': user_response.json()}

@router.get('/api/bookmarks')
async def get_bookmarks(user_id: str, query: Optional[str] = None, max_results: int = 0):
    try:
        print(f'\n---- BOOKMARKS REQUEST ----')
        print(f'User ID: {user_id}')
        print(f'Max Results: {max_results}')
        
        if not user_id or not isinstance(user_id, str):
            print('Invalid user_id')
            return JSONResponse(
                status_code=400,
                content={'error': 'Invalid user_id', 'data': []}
            )
        
        if user_id in bookmarks_cache:
            cache_time = bookmarks_cache[user_id].get('timestamp', 0)
            cache_age = time.time() - cache_time
            if cache_age < 300:  
                print(f'Using cached bookmarks (age: {cache_age:.1f}s)')
                return JSONResponse(
                    status_code=200,
                    content={'data': bookmarks_cache[user_id]['bookmarks'], 'cached': True}
                )
            else:
                print(f'Cache expired ({cache_age:.1f}s old), fetching fresh data')
                del bookmarks_cache[user_id]
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT access_token, refresh_token, username FROM user_tokens WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            print('User not authenticated (not in DB)')
            return JSONResponse(
                status_code=401,
                content={'error': 'User not authenticated', 'data': []}
            )
        
        access_token = row['access_token']
        refresh_token = row['refresh_token']
        username = row['username']
        
        print(f'User found: {username}')
        print(f'Access Token: {access_token[:50] if access_token else "NULL"}...')
        print(f'Refresh Token exists: {"YES" if refresh_token else "NO"}')
        
        if not access_token or not access_token.strip():
            print('Invalid or empty access_token')
            return JSONResponse(
                status_code=401,
                content={'error': 'Invalid token', 'data': []}
            )
        
        headers = {'Authorization': f'Bearer {access_token}'}
        
        params = {
            'max_results': min(max_results, 100),
            'tweet.fields': 'author_id,created_at,public_metrics,lang',
            'expansions': 'author_id',
            'user.fields': 'name,username,verified'
        }
        
        url = f'https://api.x.com/2/users/{user_id}/bookmarks'
        print(f'Requesting: {url}')
        
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.get(url, headers=headers, params=params)
            
            print(f'API Response Status: {response.status_code}')
            
            if response.status_code == 401:
                print('Token expired (401), attempting refresh...')
                new_token = await refresh_access_token(user_id)
                
                if new_token:
                    print(f'Token refreshed successfully for user {user_id}')
                    headers['Authorization'] = f'Bearer {new_token}'
                    response = await client.get(url, headers=headers, params=params)
                    print(f'Retry response status: {response.status_code}')
                else:
                    print(f'Failed to refresh token for user {user_id} - refresh_token may be invalid')
                    return JSONResponse(
                        status_code=401,
                        content={'error': 'Session expired, please login again', 'data': []}
                    )
            
            if response.status_code == 200:
                data = response.json()
                bookmarks_data = data.get('data', [])
                bookmarks_count = len(bookmarks_data)
                print(f'API Response Status: 200')
                print(f'Bookmarks count: {bookmarks_count}')
                if bookmarks_count > 0:
                    print(f'First bookmark: {bookmarks_data[0]}')
                   
                    bookmarks_cache[user_id] = {
                        'bookmarks': bookmarks_data,
                        'timestamp': time.time()
                    }
                if not isinstance(data, dict):
                    data = {'data': []}
                if 'data' not in data:
                    data['data'] = []
                return data
            
            elif response.status_code == 429:
                print('Rate limited (429)')
                if user_id in bookmarks_cache:
                    print(f'Returning stale cache due to rate limit')
                    return JSONResponse(
                        status_code=200,
                        content={'data': bookmarks_cache[user_id]['bookmarks'], 'message': 'Using cached data due to rate limit'}
                    )
                return JSONResponse(
                    status_code=200,
                    content={'data': [], 'message': 'Rate limited, try again later'}
                )
            
            else:
                print(f'Unexpected status: {response.status_code}')
                print(f'Response: {response.text}')
                return JSONResponse(
                    status_code=200,
                    content={'data': [], 'message': f'Error fetching bookmarks: {response.status_code}'}
                )
    
    except Exception as e:
        print(f'Error in get_bookmarks: {str(e)}')
        import traceback
        traceback.print_exc()
        return JSONResponse(
            status_code=500,
            content={'error': 'Server error', 'data': []}
        )

@router.get('/api/bookmarks/search')
async def search_bookmarks(user_id: str, query: str, max_results: int = 10):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('SELECT access_token FROM user_tokens WHERE user_id = ?', (user_id,))
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        return {'error': 'User not authenticated'}
    
    access_token = row['access_token']
    headers = {'Authorization': f'Bearer {access_token}'}
    
    params = {
        'max_results': 10,
        'tweet.fields': 'author_id,created_at,public_metrics,lang',
        'expansions': 'author_id',
        'user.fields': 'name,username,verified'
    }
    
    url = f'https://api.x.com/2/users/{user_id}/bookmarks'
    
    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers=headers, params=params)
        
        if response.status_code != 200:
            return {'error': 'Failed to fetch bookmarks'}
        
        bookmarks_data = response.json()
        
        if 'data' in bookmarks_data:
            filtered = [
                tweet for tweet in bookmarks_data['data']
                if query.lower() in tweet.get('text', '').lower()
            ]
            bookmarks_data['data'] = filtered[:max_results]
        
        return bookmarks_data