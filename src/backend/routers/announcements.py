"""
Announcements endpoints for the High School Management System API
"""

from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from datetime import datetime
from bson import ObjectId
import logging

from ..database import announcements_collection, teachers_collection, verify_password

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)

logger = logging.getLogger(__name__)


# Pydantic models for request validation
class AnnouncementCreate(BaseModel):
    title: str
    message: str
    start_date: Optional[str] = None
    expiration_date: str


class AnnouncementUpdate(BaseModel):
    title: Optional[str] = None
    message: Optional[str] = None
    start_date: Optional[str] = None
    expiration_date: Optional[str] = None


def serialize_announcement(announcement: Dict) -> Dict:
    """Convert MongoDB document to JSON-serializable format"""
    announcement["_id"] = str(announcement["_id"])
    return announcement


@router.get("")
def get_announcements() -> List[Dict[str, Any]]:
    """Get all active announcements (public endpoint)"""
    try:
        now = datetime.now().isoformat()
        
        # Find announcements where:
        # - expiration_date has not passed
        # - start_date has arrived (if set)
        announcements = list(announcements_collection.find(
            {
                "expiration_date": {"$gte": now},
                "$or": [
                    {"start_date": {"$exists": False}},
                    {"start_date": {"$lte": now}}
                ]
            }
        ).sort("created_at", -1))
        
        return [serialize_announcement(a) for a in announcements]
    except Exception as e:
        logger.error(f"Error fetching announcements: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch announcements")


@router.get("/all")
def get_all_announcements(username: str) -> List[Dict[str, Any]]:
    """Get all announcements (for management) - requires authentication"""
    # Verify user is signed in
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        announcements = list(announcements_collection.find().sort("created_at", -1))
        return [serialize_announcement(a) for a in announcements]
    except Exception as e:
        logger.error(f"Error fetching all announcements: {e}")
        raise HTTPException(status_code=500, detail="Failed to fetch announcements")


@router.post("")
def create_announcement(username: str, announcement: AnnouncementCreate) -> Dict[str, Any]:
    """Create a new announcement - requires authentication"""
    # Verify user is signed in
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Validate that expiration_date is provided
        if not announcement.expiration_date:
            raise HTTPException(status_code=400, detail="expiration_date is required")
        
        # Create announcement document
        new_announcement = {
            "title": announcement.title,
            "message": announcement.message,
            "start_date": announcement.start_date,
            "expiration_date": announcement.expiration_date,
            "created_at": datetime.now().isoformat(),
            "created_by": username
        }
        
        result = announcements_collection.insert_one(new_announcement)
        new_announcement["_id"] = str(result.inserted_id)
        
        return new_announcement
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating announcement: {e}")
        raise HTTPException(status_code=500, detail="Failed to create announcement")


@router.put("/{announcement_id}")
def update_announcement(
    username: str,
    announcement_id: str,
    announcement: AnnouncementUpdate
) -> Dict[str, Any]:
    """Update an announcement - requires authentication"""
    # Verify user is signed in
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Convert announcement_id to ObjectId
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")
        
        # Build update dictionary (only include provided fields)
        update_data = {}
        if announcement.title is not None:
            update_data["title"] = announcement.title
        if announcement.message is not None:
            update_data["message"] = announcement.message
        if announcement.start_date is not None:
            update_data["start_date"] = announcement.start_date
        if announcement.expiration_date is not None:
            update_data["expiration_date"] = announcement.expiration_date
        
        if not update_data:
            raise HTTPException(status_code=400, detail="No fields to update")
        
        update_data["updated_at"] = datetime.now().isoformat()
        
        # Update the announcement
        result = announcements_collection.find_one_and_update(
            {"_id": obj_id},
            {"$set": update_data},
            return_document=True
        )
        
        if not result:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        return serialize_announcement(result)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating announcement: {e}")
        raise HTTPException(status_code=500, detail="Failed to update announcement")


@router.delete("/{announcement_id}")
def delete_announcement(username: str, announcement_id: str) -> Dict[str, str]:
    """Delete an announcement - requires authentication"""
    # Verify user is signed in
    teacher = teachers_collection.find_one({"_id": username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Convert announcement_id to ObjectId
        try:
            obj_id = ObjectId(announcement_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid announcement ID")
        
        # Delete the announcement
        result = announcements_collection.delete_one({"_id": obj_id})
        
        if result.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Announcement not found")
        
        return {"message": "Announcement deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting announcement: {e}")
        raise HTTPException(status_code=500, detail="Failed to delete announcement")
