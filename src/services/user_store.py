"""
User storage service with JSON-based persistence.
Handles user CRUD operations and creates default admin user on first run.
"""

import json
import os
import shutil
import tempfile
import uuid
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime

from src.models.user import User
from src.utils.exceptions import ConfigError
from src.utils.logger import get_logger


DATA_DIR = Path("data")
USERS_FILE = DATA_DIR / "users.json"


class UserStore:
    """Singleton user storage manager"""
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(UserStore, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.users_path = USERS_FILE
        
        # Create data directory if it doesn't exist
        DATA_DIR.mkdir(exist_ok=True, parents=True)
        
        # Initialize default admin user if no users exist
        if not self.users_path.exists():
            self._create_default_admin()
        else:
            # Migration: Activate any inactive self-registered users (migration for existing installations)
            self._activate_inactive_self_registered_users()
        
        self._initialized = True
    
    def _activate_inactive_self_registered_users(self):
        """Activate any inactive self-registered users (migration helper)"""
        try:
            users = self.load_users()
            updated = False
            
            for user in users:
                # If user is inactive and was self-registered (created_by is None), activate them
                if not user.is_active and user.created_by is None and user.role == "user":
                    self.update_user(user.id, is_active=True)
                    updated = True
            
            if updated:
                logger = get_logger(__name__)
                logger.info("Activated inactive self-registered users (migration)")
        except Exception as e:
            # Don't fail initialization if migration fails
            pass
    
    def _create_default_admin(self):
        """Create default admin user on first run"""
        # Lazy import to avoid circular dependency
        from src.auth.user_auth import hash_password
        
        default_password = os.getenv("WEB_PASSWORD", "admin")
        admin_user = User(
            id=str(uuid.uuid4()),
            username="admin",
            email=None,
            password_hash=hash_password(default_password),
            role="admin",
            created_at=datetime.utcnow().isoformat(),
            is_active=True,
            created_by=None,
        )
        
        users_data = {"users": [admin_user.dict()]}
        self._atomic_write(self.users_path, users_data)
    
    def load_users(self) -> List[User]:
        """Load all users from storage"""
        if not self.users_path.exists():
            return []
        
        try:
            with open(self.users_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            users = []
            for user_data in data.get("users", []):
                users.append(User(**user_data))
            
            return users
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            raise ConfigError(f"Failed to load users from {self.users_path}: {str(e)}")
    
    def save_users(self, users: List[User]) -> None:
        """Atomically save users to JSON"""
        users_data = {"users": [user.dict() for user in users]}
        self._atomic_write(self.users_path, users_data)
    
    def find_by_username(self, username: str) -> Optional[User]:
        """Find user by username"""
        users = self.load_users()
        for user in users:
            if user.username == username:
                return user
        return None
    
    def find_by_id(self, user_id: str) -> Optional[User]:
        """Find user by ID"""
        users = self.load_users()
        for user in users:
            if user.id == user_id:
                return user
        return None
    
    def create_user(self, user: User) -> User:
        """Create a new user"""
        users = self.load_users()
        
        # Check for duplicate username
        if any(u.username == user.username for u in users):
            raise ValueError(f"Username '{user.username}' already exists")
        
        users.append(user)
        self.save_users(users)
        return user
    
    def update_user(self, user_id: str, **updates) -> User:
        """Update user fields"""
        users = self.load_users()
        
        for i, user in enumerate(users):
            if user.id == user_id:
                # Create updated user dict
                user_dict = user.dict()
                user_dict.update(updates)
                
                # If username is being updated, check for duplicates
                if "username" in updates:
                    if any(u.username == updates["username"] and u.id != user_id for u in users):
                        raise ValueError(f"Username '{updates['username']}' already exists")
                
                # Create new User instance with updated data
                updated_user = User(**user_dict)
                users[i] = updated_user
                self.save_users(users)
                return updated_user
        
        raise ValueError(f"User with ID '{user_id}' not found")
    
    def delete_user(self, user_id: str) -> None:
        """Delete a user"""
        users = self.load_users()
        
        # Prevent deleting the last admin
        admins = [u for u in users if u.role == "admin" and u.is_active]
        user_to_delete = self.find_by_id(user_id)
        
        if user_to_delete and user_to_delete.role == "admin" and len(admins) == 1:
            raise ValueError("Cannot delete the last active admin user")
        
        users = [u for u in users if u.id != user_id]
        self.save_users(users)
    
    def _atomic_write(self, path: Path, data: Dict[str, Any]) -> None:
        """Write JSON file atomically"""
        dir_path = path.parent
        with tempfile.NamedTemporaryFile(mode='w', dir=dir_path, delete=False, encoding='utf-8') as tf:
            json.dump(data, tf, indent=2, ensure_ascii=False)
            temp_path = Path(tf.name)
        
        try:
            # Atomic move/replace
            shutil.move(str(temp_path), str(path))
        except Exception as e:
            # Clean up temp file if move failed
            if temp_path.exists():
                temp_path.unlink()
            raise ConfigError(f"Failed to save users to {path}: {str(e)}")


# Global instance
user_store = UserStore()
