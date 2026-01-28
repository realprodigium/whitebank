from fastapi import FastAPI
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.requests import Request
from api import router
import sqlite3

app = FastAPI()
app.include_router(router=router)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

DB_PATH = 'bookmarks.db'

def get_username(user_id: str) -> str:
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT username FROM user_tokens WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row['username'] if row else 'Unknown'
    except Exception as e:
        return 'Unknown'

def user_exists(user_id: str) -> bool:
    """Check if user has valid token in database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT access_token FROM user_tokens WHERE user_id = ?', (user_id,))
        row = cursor.fetchone()
        conn.close()
        return row is not None and row['access_token'] is not None
    except Exception as e:
        return False


@app.get('/', response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse(request=request, name='index.html')

@app.get('/dashboard', response_class=HTMLResponse)
def dashboard(request: Request):
    user_id = request.query_params.get('user_id')
    username = get_username(user_id) if user_id else 'Unknown'
    return templates.TemplateResponse(request=request, name='dash.html', context={'username': username, 'request': request})

@app.get('/api/session')
async def get_session(user_id: str):
    """Validate and get session info"""
    if not user_id:
        return JSONResponse(
            status_code=401,
            content={'authenticated': False, 'user_id': None, 'username': None}
        )
    
    if not user_exists(user_id):
        return JSONResponse(
            status_code=401,
            content={'authenticated': False, 'user_id': None, 'username': None}
        )
    
    username = get_username(user_id)
    return JSONResponse(
        status_code=200,
        content={'authenticated': True, 'user_id': user_id, 'username': username}
    )

@app.get('/api/logout')
async def logout(user_id: str):
    """Logout user (clear from frontend localStorage)"""
    try:
        # Optionally delete token from database if you want to invalidate it
        # conn = sqlite3.connect(DB_PATH)
        # cursor = conn.cursor()
        # cursor.execute('DELETE FROM user_tokens WHERE user_id = ?', (user_id,))
        # conn.commit()
        # conn.close()
        
        return JSONResponse(
            status_code=200,
            content={'message': 'Logged out successfully'}
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={'error': str(e)}
        )