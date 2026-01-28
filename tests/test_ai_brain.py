"""Unit tests for AI Brain modules"""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from src.features.ai_brain import (
    ProfileManager,
    MemoryManager,
    PromptBuilder,
    AISettingsService,
)


class TestProfileManager:
    """Test cases for ProfileManager"""
    
    def test_profile_initialization(self, tmp_path):
        """Test profile manager initialization"""
        profiles_file = tmp_path / "test_profiles.json"
        manager = ProfileManager(profiles_file=str(profiles_file))
        
        assert manager.get_profile("test_account")["brand_name"] == ""
        assert manager.get_profile("test_account")["tone"] == "friendly"
    
    def test_update_profile(self, tmp_path):
        """Test updating a profile"""
        profiles_file = tmp_path / "test_profiles.json"
        manager = ProfileManager(profiles_file=str(profiles_file))
        
        profile = manager.update_profile("test_account", {
            "brand_name": "Test Brand",
            "tone": "professional",
            "pricing": "$99/month",
        })
        
        assert profile["brand_name"] == "Test Brand"
        assert profile["tone"] == "professional"
        assert profile["pricing"] == "$99/month"
        assert "created_at" in profile
        assert "updated_at" in profile
    
    def test_has_profile(self, tmp_path):
        """Test checking if profile exists"""
        profiles_file = tmp_path / "test_profiles.json"
        manager = ProfileManager(profiles_file=str(profiles_file))
        
        assert not manager.has_profile("test_account")
        
        manager.update_profile("test_account", {"brand_name": "Test"})
        assert manager.has_profile("test_account")
    
    def test_delete_profile(self, tmp_path):
        """Test deleting a profile"""
        profiles_file = tmp_path / "test_profiles.json"
        manager = ProfileManager(profiles_file=str(profiles_file))
        
        manager.update_profile("test_account", {"brand_name": "Test"})
        assert manager.has_profile("test_account")
        
        assert manager.delete_profile("test_account") is True
        assert not manager.has_profile("test_account")
        assert manager.delete_profile("test_account") is False


class TestMemoryManager:
    """Test cases for MemoryManager"""
    
    def test_memory_initialization(self, tmp_path):
        """Test memory manager initialization"""
        memory_file = tmp_path / "test_memory.json"
        manager = MemoryManager(memory_file=str(memory_file))
        
        assert manager.get_context("account1", "user1") == []
    
    def test_store_and_get_message(self, tmp_path):
        """Test storing and retrieving messages"""
        memory_file = tmp_path / "test_memory.json"
        manager = MemoryManager(memory_file=str(memory_file))
        
        manager.store_message("account1", "user1", "Hello", role="user")
        manager.store_message("account1", "user1", "Hi there!", role="assistant", reply="Hi there!")
        
        context = manager.get_context("account1", "user1")
        assert len(context) == 2
        assert context[0]["text"] == "Hello"
        assert context[1]["text"] == "Hi there!"
    
    def test_max_messages_limit(self, tmp_path):
        """Test that max messages limit is enforced"""
        memory_file = tmp_path / "test_memory.json"
        manager = MemoryManager(memory_file=str(memory_file))
        
        # Store more than MAX_MESSAGES_PER_USER
        for i in range(60):
            manager.store_message("account1", "user1", f"Message {i}")
        
        context = manager.get_context("account1", "user1")
        assert len(context) <= 50  # MAX_MESSAGES_PER_USER
    
    def test_auto_tagging(self, tmp_path):
        """Test automatic user tagging"""
        memory_file = tmp_path / "test_memory.json"
        manager = MemoryManager(memory_file=str(memory_file))
        
        manager.store_message("account1", "user1", "What is your pricing?")
        
        user_info = manager.get_user_info("account1", "user1")
        assert "pricing" in user_info["tags"]
    
    def test_reset_user_memory(self, tmp_path):
        """Test resetting user memory"""
        memory_file = tmp_path / "test_memory.json"
        manager = MemoryManager(memory_file=str(memory_file))
        
        manager.store_message("account1", "user1", "Hello")
        assert len(manager.get_context("account1", "user1")) > 0
        
        assert manager.reset_user_memory("account1", "user1") is True
        assert len(manager.get_context("account1", "user1")) == 0


class TestPromptBuilder:
    """Test cases for PromptBuilder"""
    
    def test_build_prompt_with_defaults(self, tmp_path):
        """Test building prompt with default profile"""
        profile_file = tmp_path / "test_profiles.json"
        memory_file = tmp_path / "test_memory.json"
        
        profile_manager = ProfileManager(profiles_file=str(profile_file))
        memory_manager = MemoryManager(memory_file=str(memory_file))
        builder = PromptBuilder(profile_manager, memory_manager)
        
        prompt = builder.build_prompt("account1", "user1", "Hello")
        
        assert "InstaForge" in prompt
        assert "friendly" in prompt.lower() or "professional" in prompt.lower()
    
    def test_build_prompt_with_custom_profile(self, tmp_path):
        """Test building prompt with custom profile"""
        profile_file = tmp_path / "test_profiles.json"
        memory_file = tmp_path / "test_memory.json"
        
        profile_manager = ProfileManager(profiles_file=str(profile_file))
        memory_manager = MemoryManager(memory_file=str(memory_file))
        builder = PromptBuilder(profile_manager, memory_manager)
        
        profile_manager.update_profile("account1", {
            "brand_name": "My Brand",
            "business_type": "E-commerce",
            "location": "USA",
            "pricing": "$99/month",
        })
        
        prompt = builder.build_prompt("account1", "user1", "Hello")
        
        assert "My Brand" in prompt
        assert "E-commerce" in prompt
        assert "USA" in prompt
    
    def test_build_prompt_with_memory(self, tmp_path):
        """Test building prompt with conversation memory"""
        profile_file = tmp_path / "test_profiles.json"
        memory_file = tmp_path / "test_memory.json"
        
        profile_manager = ProfileManager(profiles_file=str(profile_file))
        memory_manager = MemoryManager(memory_file=str(memory_file))
        builder = PromptBuilder(profile_manager, memory_manager)
        
        # Enable memory in profile
        profile_manager.update_profile("account1", {"enable_memory": True})
        
        # Store some messages
        memory_manager.store_message("account1", "user1", "What's your price?")
        memory_manager.store_message("account1", "user1", "Our pricing is $99", role="assistant")
        
        prompt = builder.build_prompt("account1", "user1", "Tell me more")
        
        assert "pricing" in prompt.lower() or "Recent conversation" in prompt


class TestAISettingsService:
    """Test cases for AISettingsService"""
    
    def test_service_initialization(self):
        """Test service initialization"""
        service = AISettingsService()
        
        assert service.profile_manager is not None
        assert service.memory_manager is not None
        assert service.prompt_builder is not None
    
    def test_store_conversation(self, tmp_path):
        """Test storing a conversation"""
        # Mock the managers to use temp files
        with patch('src.features.ai_brain.ai_settings_service.ProfileManager') as MockProfile, \
             patch('src.features.ai_brain.ai_settings_service.MemoryManager') as MockMemory:
            
            mock_profile = Mock()
            mock_memory = Mock()
            MockProfile.return_value = mock_profile
            MockMemory.return_value = mock_memory
            
            service = AISettingsService()
            service.profile_manager = mock_profile
            service.memory_manager = mock_memory
            
            service.store_conversation("account1", "user1", "Hello", "Hi there!")
            
            assert mock_memory.store_message.call_count == 2
    
    def test_get_memory_stats(self, tmp_path):
        """Test getting memory statistics"""
        with patch('src.features.ai_brain.ai_settings_service.MemoryManager') as MockMemory:
            mock_memory = Mock()
            mock_memory.get_stats.return_value = {
                "total_users": 10,
                "total_messages": 50,
                "users_with_tags": 5,
            }
            MockMemory.return_value = mock_memory
            
            service = AISettingsService()
            service.memory_manager = mock_memory
            
            stats = service.get_memory_stats("account1")
            
            assert stats["total_users"] == 10
            assert stats["total_messages"] == 50


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
