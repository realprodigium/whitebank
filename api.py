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

load_dotenv()

router = APIRouter()
DB_PATH = 'bookmarks.db'

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
        
        user_info_headers = {'Authorization': f'Bearer {access_token}'}
        user_response = await client.get('https://api.x.com/2/users/me', headers=user_info_headers)
        
        if user_response.status_code == 200:
            user_data = user_response.json()
            user_id = user_data['data']['id']
            username = user_data['data']['username']
            
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                'INSERT OR REPLACE INTO user_tokens (user_id, access_token, username, updated_at) VALUES (?, ?, ?, ?)',
                (user_id, access_token, username, datetime.now().isoformat())
            )
            conn.commit()
            conn.close()
            
            return RedirectResponse(url=f'/dashboard?user_id={user_id}', status_code=303)
        else:
            return {'error': 'failed to get user info', 'details': user_response.json()}

@router.get('/api/bookmarks')
async def get_bookmarks(user_id: str, query: Optional[str] = None, max_results: int = 10):
    try:
        # Validate user_id format
        if not user_id or not isinstance(user_id, str):
            return JSONResponse(
                status_code=400,
                content={'error': 'Invalid user_id', 'data': []}
            )
        
        # Get token from database
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT access_token, username FROM user_tokens WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return JSONResponse(
                status_code=401,
                content={'error': 'User not authenticated', 'data': []}
            )
        
        access_token = row['access_token']
        username = row['username']
        
        if not access_token or not access_token.strip():
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
        
        # Fetch with timeout and retry logic
        max_retries = 3
        timeout_seconds = 10
        last_error = None
        
        async with httpx.AsyncClient(timeout=timeout_seconds) as client:
            for attempt in range(max_retries):
                try:
                    response = await client.get(url, headers=headers, params=params)
                    
                    if response.status_code == 200:
                        data = response.json()
                        # Ensure response has proper structure
                        if not isinstance(data, dict):
                            data = {'data': []}
                        if 'data' not in data:
                            data['data'] = []
                        return data
                    
                    elif response.status_code == 401:
                        # Token expired, return empty but not an error
                        return JSONResponse(
                            status_code=200,
                            content={'data': [], 'message': 'Token may need refresh'}
                        )
                    
                    elif response.status_code == 429:
                        # Rate limited, wait and retry
                        if attempt < max_retries - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        else:
                            last_error = 'Rate limited by X API'
                    
                    else:
                        # Other errors, try to parse
                        try:
                            error_details = response.json()
                            last_error = error_details.get('errors', [{}])[0].get('message', f'HTTP {response.status_code}')
                        except:
                            last_error = f'HTTP {response.status_code}'
                        
                        if attempt < max_retries - 1:
                            await asyncio.sleep(1)
                            continue
                
                except httpx.TimeoutException:
                    last_error = 'Request timeout'
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                except httpx.NetworkError as e:
                    last_error = f'Network error: {str(e)}'
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
                except Exception as e:
                    last_error = f'Unexpected error: {str(e)}'
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
                        continue
        
        # If all retries failed, return empty data instead of error
        return JSONResponse(
            status_code=200,
            content={
                'data': [],
                'message': f'Could not fetch bookmarks: {last_error}. Showing cached data if available.'
            }
        )
    
    except Exception as e:
        print(f'Error in get_bookmarks: {str(e)}')
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
        'max_results': 100,
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