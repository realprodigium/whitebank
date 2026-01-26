from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import httpx
import secrets
import os
import hashlib
import base64
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

#provisional
oauth_states = {}

def generate_pkce():
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode('utf-8').rstrip('=')
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode('utf-8')).digest()
    ).decode('utf-8').rstrip('=')
    return code_verifier, code_challenge


@router.get('/auth/x/login')
def login():
    client_id = os.getenv('CLIENT_ID')
    redirect_uri = 'http://127.0.0.1:8000/auth/x/callback'

    state = secrets.token_urlsafe(32)
    code_verifier, code_challenge = generate_pkce()

    oauth_states[state] = code_verifier

    scopes = 'tweet.read users.read bookmarks.read offline.access'
    auth_url = (
        f"https://twitter.com/i/oauth2/authorize?"
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

    if not code or not state not in oauth_states:
        return {'error': 'invalid request'}
    code_verifier = oauth_states.pop(state)

    client_id = os.getenv('CLIENT_ID')
    client_secret = os.getenv('CLIENT_SECRET')
    redirect_uri = 'http://127.0.0.1:8000/auth/x/callback'
    token_url = 'https://api.twitter.com/2/oauth2/token'

    credentials = f'{client_id}:{client_secret}'
    b64_credentials = base64.b64encode(credentials.encode()).decode()

    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {b64_credentials}'
    }

    data = {
        'code':code,
        'grant-type':'authorization_code',
        'redirect_uri':redirect_uri,
        code_verifier:code_verifier
    }
    async with httpx.AsyncClient() as client:
        response = await client.post(token_url, headers=headers, data=data)
        if response.status_code != 200:
            return {'error': 'token request failed', 'details': response.json()}
        tokens = response.json()
        return {
            "message": "Login successful",
            "access_token": tokens.get('access_token'),
            "expires_in": tokens.get('expires_in')
        }
        