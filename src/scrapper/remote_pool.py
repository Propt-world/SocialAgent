# src/scrapper/remote_pool.py
import httpx
from twscrape import Account
# We don't inherit from AccountsPool to avoid initializing SQLite, 
# but we implement the methods 'twscrape' needs.

class RemoteAccountsPool:
    def __init__(self, auth_service_url: str):
        self.auth_url = auth_service_url
    
    async def get_for_queue(self, queue: str):
        """
        Asks the Auth Service for an account.
        """
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(
                    f"{self.auth_url}/lock", 
                    json={"queue": queue},
                    timeout=10.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    # Reconstruct the Account object locally
                    # API expects an Account object to work
                    acc = Account(
                        username=data["username"],
                        password="", # Not needed for cookies
                        email="",
                        email_password="",
                        cookies=data["cookies"],
                        user_agent=data["user_agent"],
                        headers=data["headers"],
                        proxy=data["proxy"]
                    )
                    return acc
            except Exception as e:
                print(f"[RemotePool] Error getting account: {e}")
        return None

    async def unlock(self, username: str, queue: str):
        """
        Tells Auth Service to unlock.
        """
        async with httpx.AsyncClient() as client:
            try:
                await client.post(
                    f"{self.auth_url}/unlock", 
                    json={"username": username, "queue": queue}
                )
            except Exception as e:
                print(f"[RemotePool] Error unlocking: {e}")