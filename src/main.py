import redis
import json
from fastapi import FastAPI, HTTPException, Body, Query, status, Depends, Path, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from typing import List, Optional, Dict, Any
from bson import ObjectId
from datetime import datetime, timezone

# --- PROJECT MODULES ---
from src.config import settings
from src.db.database import get_db
from src.utils.security import verify_api_key

# Data Models
from src.models.config_models import SocialTarget, SourceConfig
from src.models.db_models import SocialPost

# API Response Models
from src.models.api_models import (
    QueueStatus, 
    GenericResponse, 
    JobSubmissionResponse, 
    HealthResponse,
    ErrorResponse
)

app = FastAPI(
    title="SocialAgent API",
    version="1.0",
    description="Control Plane for Twitter Scraping & Governance",
    responses={
        400: {"model": ErrorResponse, "description": "Bad Request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden"},
        404: {"model": ErrorResponse, "description": "Not Found"},
        500: {"model": ErrorResponse, "description": "Internal Server Error"},
    }
)

# --- DEPENDENCIES ---
def get_redis():
    return redis.Redis.from_url(settings.REDIS_URL)

# ==========================================
# 1. SYSTEM HEALTH & METRICS
# ==========================================

@app.get(
    "/health", 
    response_model=HealthResponse, 
    tags=["System"],
    status_code=status.HTTP_200_OK,
    summary="System Health Check",
    description="Checks connectivity to Redis and MongoDB services."
)
def health_check():
    """
    Checks connectivity to Redis and MongoDB.
    """
    db = get_db()
    r = get_redis()
    
    health_data = {
        "status": "healthy",
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check Mongo
    try:
        db.command("ping")
        health_data["database"] = "connected"
    except Exception as e:
        health_data["database"] = f"error: {str(e)}"
        health_data["status"] = "unhealthy"

    # Check Redis
    try:
        if r.ping():
            health_data["redis"] = "connected"
    except Exception as e:
        health_data["redis"] = f"error: {str(e)}"
        health_data["status"] = "unhealthy"

    if health_data["status"] == "unhealthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, 
            detail=HealthResponse(**health_data).model_dump()
        )

    return HealthResponse(**health_data)


# ==========================================
# 2. QUEUE MANAGEMENT
# ==========================================

@app.get(
    "/queue/status",
    tags=["Queue Management"], 
    response_model=QueueStatus, 
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
    summary="Worker Queue Status",
    description="Returns the current load on the worker queue (Redis)."
)
def get_queue_status():
    """
    Returns the current load on the worker queue.
    """
    try:
        r = get_redis()
        count = r.llen(settings.QUEUE_NAME)
        
        health = "healthy"
        if count > 100: health = "busy"
        if count > 1000: health = "backlogged"

        return QueueStatus(
            queue_name=settings.QUEUE_NAME,
            pending_jobs=count,
            status=health
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check queue status: {str(e)}"
        )

@app.get(
    "/queue/dlq",
    tags=["Queue Management"],
    response_model=Dict[str, Any], # Returns a dict structure
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
    summary="View Dead Letter Queue",
    description="View items that failed processing."
)
def view_dlq(limit: int = 10):
    """
    Peek at the last N items in the Dead Letter Queue.
    """
    r = get_redis()
    # lrange 0 -1 fetches all, but we respect limit
    items = r.lrange(settings.DLQ_NAME, 0, limit - 1)
    
    parsed_items = []
    for item in items:
        try:
            parsed_items.append(json.loads(item))
        except:
            parsed_items.append({"raw": str(item)})
            
    return {
        "queue": settings.DLQ_NAME,
        "count": r.llen(settings.DLQ_NAME),
        "items": parsed_items
    }

@app.post(
    "/queue/dlq/requeue",
    tags=["Queue Management"],
    response_model=GenericResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
    summary="Requeue Failed Jobs",
    description="Move all items from DLQ back to the Main Queue to be retried."
)
def requeue_dlq():
    """
    Atomically move all items from DLQ back to Main Queue.
    """
    r = get_redis()
    count = 0
    
    # RPOPLPUSH is atomic: pops from DLQ, pushes to Main
    while True:
        # Use rpoplpush(source, destination)
        item = r.rpoplpush(settings.DLQ_NAME, settings.QUEUE_NAME)
        if not item:
            break
        count += 1
        
    return GenericResponse(
        status="success",
        message=f"Requeued {count} jobs from DLQ to {settings.QUEUE_NAME}."
    )

@app.delete(
    "/queue/dlq",
    tags=["Queue Management"],
    response_model=GenericResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
    summary="Purge DLQ",
    description="Permanently delete all items in the Dead Letter Queue."
)
def purge_dlq():
    """
    Clear the DLQ.
    """
    r = get_redis()
    r.delete(settings.DLQ_NAME)
    return GenericResponse(
        status="success",
        message="Dead Letter Queue purged."
    )

@app.delete(
    "/queue/main",
    tags=["Queue Management"],
    response_model=GenericResponse,
    status_code=status.HTTP_200_OK,
    dependencies=[Depends(verify_api_key)],
    summary="Purge Main Queue",
    description="Permanently delete all pending jobs."
)
def purge_main_queue():
    """
    Clear the Main Queue.
    """
    r = get_redis()
    r.delete(settings.QUEUE_NAME)
    return GenericResponse(
        status="success",
        message="Main Queue purged."
    )

# ==========================================
# 3. SOURCE MANAGEMENT
# ==========================================

@app.post(
    "/sources", 
    response_model=GenericResponse, 
    status_code=status.HTTP_201_CREATED, 
    tags=["Sources"], 
    dependencies=[Depends(verify_api_key)],
    summary="Add New Source",
    description="Register a new Twitter profile to scrape."
)
def add_source(target: SocialTarget):
    """
    Register a new Twitter profile to scrape.
    """
    db = get_db()
    
    # Check for duplicates
    if db.targets.find_one({"username": target.username, "platform": target.platform}):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, 
            detail=f"Source @{target.username} already exists."
        )

    # Convert Pydantic -> Dict
    data = target.model_dump(by_alias=True, exclude=["id"])
    
    # Insert
    result = db.targets.insert_one(data)
    
    return GenericResponse(
        status="success",
        message=f"Source @{target.username} added successfully.",
        data={"id": str(result.inserted_id)}
    )

@app.get(
    "/sources", 
    response_model=List[SocialTarget], 
    tags=["Sources"], 
    dependencies=[Depends(verify_api_key)],
    summary="List Sources",
    description="List all configured sources, optionally filtering by enabled status."
)
def list_sources(enabled_only: bool = False):
    """
    List configured sources.
    """
    db = get_db()
    query = {"enabled": True} if enabled_only else {}
    
    sources = []
    for doc in db.targets.find(query):
        # Map ObjectId to string ID for Pydantic
        if "_id" in doc:
            doc["_id"] = str(doc["_id"])
        sources.append(doc)
        
    return sources

@app.patch(
    "/sources/{source_id}/toggle", 
    response_model=GenericResponse, 
    tags=["Sources"], 
    dependencies=[Depends(verify_api_key)],
    summary="Toggle Source",
    description="Enable or Disable a specific source."
)
def toggle_source(
    source_id: str = Path(..., title="The ID of the source to toggle"), 
    enabled: bool = Body(..., embed=True)
):
    """
    Enable or Disable a source.
    """
    db = get_db()
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

    oid = ObjectId(source_id)
    result = db.targets.update_one({"_id": oid}, {"$set": {"enabled": enabled}})
    
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        
    action = "enabled" if enabled else "disabled"
    return GenericResponse(
        status="success", 
        message=f"Source {action} successfully.",
        data={"source_id": source_id, "enabled": enabled}
    )

@app.put(
    "/sources/{source_id}/config", 
    response_model=GenericResponse, 
    tags=["Sources"], 
    dependencies=[Depends(verify_api_key)],
    summary="Update Source Config",
    description="Update fetching rules (interval, limits) for a specific source."
)
def update_source_config(
    source_id: str = Path(..., title="The ID of the source to update"), 
    config: SourceConfig = Body(...)
):
    """
    Update fetching rules (interval, limits).
    """
    db = get_db()
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

    oid = ObjectId(source_id)
    result = db.targets.update_one(
        {"_id": oid}, 
        {"$set": {"config": config.model_dump()}}
    )
    
    if result.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        
    return GenericResponse(
        status="success",
        message="Configuration updated.",
        data=config.model_dump()
    )

@app.delete(
    "/sources/{source_id}", 
    response_model=GenericResponse, 
    tags=["Sources"], 
    dependencies=[Depends(verify_api_key)],
    summary="Delete Source",
    description="Permanently remove a source from the registry."
)
def delete_source(
    source_id: str = Path(..., title="The ID of the source to delete")
):
    """
    Hard delete a source from the registry.
    """
    db = get_db()
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

    oid = ObjectId(source_id)
    result = db.targets.delete_one({"_id": oid})
    
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")
        
    return GenericResponse(
        status="success",
        message="Source deleted permanently.",
        data={"id": source_id}
    )

# ==========================================
# 3. JOB EXECUTION
# ==========================================

@app.post(
    "/queue/trigger/{source_id}", 
    response_model=JobSubmissionResponse, 
    status_code=status.HTTP_202_ACCEPTED, 
    tags=["Queue"], 
    dependencies=[Depends(verify_api_key)],
    summary="Trigger Manual Job",
    description="Force a job immediately (Bypasses Governance)."
)
def force_trigger_job(
    source_id: str = Path(..., title="The ID of the source to trigger")
):
    """
    Force a job immediately (Bypasses Governance).
    """
    db = get_db()
    r = get_redis()
    
    if not ObjectId.is_valid(source_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid ID format")

    oid = ObjectId(source_id)
    target_doc = db.targets.find_one({"_id": oid})

    if not target_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Source not found")

    # Manually construct job using Pydantic validation
    # Pydantic alias will handle _id -> id conversion
    if "_id" in target_doc:
         target_doc["_id"] = str(target_doc["_id"])
    
    target = SocialTarget(**target_doc)
    
    job_payload = {
        "task": "scrape_profile",
        "username": target.username,
        "limit": target.config.max_tweets,
        "target_id": str(target.id)
    }
    
    # Push to Redis
    r.lpush(settings.QUEUE_NAME, json.dumps(job_payload))
    
    return JobSubmissionResponse(
        status="queued",
        job_id=f"manual-{str(target.id)}",
        message=f"Forced scrape job created for @{target.username}",
        target=target.username
    )

# ==========================================
# 4. DATA ACCESS
# ==========================================

@app.get(
    "/tweets", 
    response_model=List[SocialPost], 
    tags=["Data"], 
    dependencies=[Depends(verify_api_key)],
    summary="List Extracted Tweets",
    description="View extracted tweets with pagination and filtering."
)
def list_tweets(
    username: Optional[str] = Query(None, description="Filter by source username"), 
    limit: int = Query(20, le=100, ge=1, description="Number of tweets to return (max 100)"), 
    offset: int = Query(0, ge=0, description="Number of tweets to skip")
):
    """
    View extracted tweets.
    """
    db = get_db()
    query = {}
    if username:
        query["source_username"] = username
        
    cursor = db.posts.find(query).sort("published_at", -1).skip(offset).limit(limit)
    
    results = []
    for doc in cursor:
        results.append(doc)
        
    return results

# ==========================================
# 5. EXCEPTION HANDLERS
# ==========================================

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=ErrorResponse(
            status="error",
            message=str(exc.detail),
            code=str(exc.status_code)
        ).model_dump()
    )

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=ErrorResponse(
            status="error",
            message="Validation Error",
            code="422",
            details=exc.errors()
        ).model_dump()
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    # In production, log the error here
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=ErrorResponse(
            status="error",
            message="Internal Server Error",
            code="500",
            details=str(exc) # Caution: Exposing details in prod might be sensitive
        ).model_dump()
    )

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)