# src/auth_service.py
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel
from twscrape import AccountsPool, Account
from src.models.x_auth_models import AccountResponse
from src.models.api_models import GenericResponse
import os

app = FastAPI(title="SocialAgent Auth Service")

# Initialize the REAL pool connected to SQLite
db_path = os.getenv("TWITTER_DB_PATH", "/app/data/accounts.db")
pool = AccountsPool(db_file=db_path)

@app.post("/lock", response_model=AccountResponse)
async def lock_account(queue: str = Body(..., embed=True)):
    """
    Finds an available account, locks it in the DB, and returns its cookies.
    """
    account = await pool.get_for_queue(queue)
    if not account:
        raise HTTPException(status_code=404, detail="No accounts available")
    
    return AccountResponse(
        username=account.username,
        cookies=account.cookies,
        user_agent=account.user_agent,
        headers=account.headers,
        proxy=account.proxy
    )

@app.post("/unlock")
async def unlock_account(username: str = Body(...), queue: str = Body(...)):
    """
    Unlocks the account so others can use it.
    """
    await pool.unlock(username, queue)
    return GenericResponse(status="success", message="Account unlocked")

@app.get("/stats")
async def get_stats():
    return GenericResponse(status="success", data=await pool.stats())