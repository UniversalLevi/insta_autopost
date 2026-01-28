"""Unit tests for AI DM Auto Reply handler"""

import os
import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from src.features.ai_dm import AIDMHandler, get_ai_reply
from src.features.ai_dm.ai_dm_tracking import AIDMTracking


class TestAIDMHandler:
    """Test cases for AIDMHandler"""
    
    def test_handler_initialization_without_key(self):
        """Test handler initialization without API key"""
        with patch.dict(os.environ, {}, clear=True):
            handler = AIDMHandler()
            assert not handler.is_available()
    
    def test_handler_initialization_with_key(self):
        """Test handler initialization with API key"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key-123"}):
            with patch("src.features.ai_dm.ai_dm_handler.OpenAI") as mock_openai:
                handler = AIDMHandler()
                assert handler.is_available()
                mock_openai.assert_called_once_with(api_key="test-key-123")
    
    def test_sanitize_input(self):
        """Test input sanitization"""
        handler = AIDMHandler()
        
        # Normal text
        assert handler._sanitize_input("Hello world") == "Hello world"
        
        # Empty string
        assert handler._sanitize_input("") == ""
        assert handler._sanitize_input(None) == ""
        
        # Long text (should be truncated)
        long_text = "a" * 3000
        result = handler._sanitize_input(long_text)
        assert len(result) <= 2003  # max_length + "..."
        assert result.endswith("...")
        
        # Control characters
        assert handler._sanitize_input("Hello\x00world") == "Helloworld"
    
    @patch("src.features.ai_dm.ai_dm_handler.OpenAI")
    def test_get_ai_reply_success(self, mock_openai_class):
        """Test successful AI reply generation"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Hello! How can I help you? 😊"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            handler = AIDMHandler()
            handler._client = mock_client
            
            reply = handler.get_ai_reply(
                message="Hi there!",
                account_id="test_account",
                user_id="test_user",
            )
            
            assert reply == "Hello! How can I help you? 😊"
            mock_client.chat.completions.create.assert_called_once()
    
    @patch("src.features.ai_dm.ai_dm_handler.OpenAI")
    def test_get_ai_reply_rate_limited(self, mock_openai_class):
        """Test rate limiting"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            handler = AIDMHandler()
            
            # Mock tracking to return False (rate limited)
            handler.tracking.can_send_reply = Mock(return_value=False)
            handler.tracking.get_user_reply_count_today = Mock(return_value=10)
            
            reply = handler.get_ai_reply(
                message="Hi there!",
                account_id="test_account",
                user_id="test_user",
            )
            
            assert reply == "Sorry for the delay 😊 Please try again."
    
    @patch("src.features.ai_dm.ai_dm_handler.OpenAI")
    def test_get_ai_reply_empty_message(self, mock_openai_class):
        """Test handling of empty message"""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            handler = AIDMHandler()
            
            reply = handler.get_ai_reply(
                message="",
                account_id="test_account",
                user_id="test_user",
            )
            
            assert reply == "Sorry for the delay 😊 Please try again."
    
    @patch("src.features.ai_dm.ai_dm_handler.OpenAI")
    def test_get_ai_reply_api_error(self, mock_openai_class):
        """Test handling of API errors"""
        # Mock OpenAI client that raises exception
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai_class.return_value = mock_client
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            handler = AIDMHandler()
            handler._client = mock_client
            
            reply = handler.get_ai_reply(
                message="Hi there!",
                account_id="test_account",
                user_id="test_user",
            )
            
            assert reply == "Sorry for the delay 😊 Please try again."
    
    @patch("src.features.ai_dm.ai_dm_handler.OpenAI")
    @patch("time.sleep")  # Mock sleep to speed up tests
    def test_process_incoming_dm_success(self, mock_sleep, mock_openai_class):
        """Test processing incoming DM successfully"""
        # Mock OpenAI client
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_choice = MagicMock()
        mock_message = MagicMock()
        mock_message.content = "Thanks for your message!"
        mock_choice.message = mock_message
        mock_response.choices = [mock_choice]
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai_class.return_value = mock_client
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            handler = AIDMHandler()
            handler._client = mock_client
            
            result = handler.process_incoming_dm(
                account_id="test_account",
                user_id="test_user",
                message_text="Hello!",
            )
            
            assert result["status"] == "success"
            assert result["reply_text"] == "Thanks for your message!"
            assert mock_sleep.called  # Delay should be called


class TestAIDMTracking:
    """Test cases for AIDMTracking"""
    
    def test_tracking_initialization(self, tmp_path):
        """Test tracking initialization"""
        tracking_file = tmp_path / "test_tracking.json"
        tracking = AIDMTracking(tracking_file=str(tracking_file))
        
        assert tracking.get_user_reply_count_today("account1", "user1") == 0
    
    def test_record_and_count(self, tmp_path):
        """Test recording replies and counting"""
        tracking_file = tmp_path / "test_tracking.json"
        tracking = AIDMTracking(tracking_file=str(tracking_file))
        
        # Record a reply
        tracking.record_reply_sent("account1", "user1")
        
        # Check count
        assert tracking.get_user_reply_count_today("account1", "user1") == 1
        
        # Record another
        tracking.record_reply_sent("account1", "user1")
        assert tracking.get_user_reply_count_today("account1", "user1") == 2
    
    def test_rate_limit_check(self, tmp_path):
        """Test rate limit checking"""
        tracking_file = tmp_path / "test_tracking.json"
        tracking = AIDMTracking(tracking_file=str(tracking_file))
        
        # Should allow replies under limit
        assert tracking.can_send_reply("account1", "user1", max_per_day=10)
        
        # Record 10 replies
        for _ in range(10):
            tracking.record_reply_sent("account1", "user1")
        
        # Should block after limit
        assert not tracking.can_send_reply("account1", "user1", max_per_day=10)


class TestGetAIReplyFunction:
    """Test cases for convenience function"""
    
    @patch("src.features.ai_dm.ai_dm_handler.AIDMHandler")
    def test_get_ai_reply_function(self, mock_handler_class):
        """Test convenience function"""
        mock_handler = MagicMock()
        mock_handler.get_ai_reply.return_value = "Test reply"
        mock_handler_class.return_value = mock_handler
        
        with patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"}):
            reply = get_ai_reply(
                message="Hello",
                account_id="test_account",
                user_id="test_user",
            )
            
            assert reply == "Test reply"
            mock_handler.get_ai_reply.assert_called_once_with(
                message="Hello",
                account_id="test_account",
                user_id="test_user",
                account_username=None,
            )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
