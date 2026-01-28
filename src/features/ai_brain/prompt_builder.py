"""Prompt Builder - Builds customized system prompts from profiles and memory"""

from typing import Dict, Any, List, Optional

from .profile_manager import ProfileManager
from .memory_manager import MemoryManager
from ...utils.logger import get_logger

logger = get_logger(__name__)

# Base prompt (original system prompt)
BASE_PROMPT = """You are a friendly, professional Instagram DM assistant for InstaForge.

Rules:
- Sound human
- Be polite
- Be short and clear
- Never say you are AI
- Never mention OpenAI
- Never say you are a bot
- Use light emojis when appropriate

Context:
Brand: InstaForge
Location: India
Service: Instagram automation and growth tools

If user greets → greet back
If user asks price → explain briefly
If user asks location → say India, online service
If confused → help politely
If rude → stay calm

Never hallucinate.
If unsure → say you will check.

Always stay in character."""


class PromptBuilder:
    """Builds customized system prompts from profiles and memory"""
    
    def __init__(
        self,
        profile_manager: Optional[ProfileManager] = None,
        memory_manager: Optional[MemoryManager] = None,
    ):
        self.profile_manager = profile_manager or ProfileManager()
        self.memory_manager = memory_manager or MemoryManager()
    
    def build_prompt(
        self,
        account_id: str,
        user_id: str,
        message: str,
    ) -> str:
        """
        Build a customized system prompt for the conversation.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            message: Current message
            
        Returns:
            Complete system prompt string
        """
        # Start with base prompt
        prompt_parts = [BASE_PROMPT]
        
        # Load profile
        profile = self.profile_manager.get_profile(account_id)
        
        # Check if profile is customized
        has_custom_profile = self.profile_manager.has_profile(account_id) and any([
            profile.get("brand_name"),
            profile.get("business_type"),
            profile.get("pricing"),
            profile.get("location"),
            profile.get("about_business"),
        ])
        
        if has_custom_profile:
            # Add custom brand context
            custom_context = []
            
            if profile.get("brand_name"):
                custom_context.append(f"Brand: {profile['brand_name']}")
            
            if profile.get("business_type"):
                custom_context.append(f"Business Type: {profile['business_type']}")
            
            if profile.get("location"):
                custom_context.append(f"Location: {profile['location']}")
            
            if profile.get("about_business"):
                custom_context.append(f"About: {profile['about_business']}")
            
            if profile.get("pricing"):
                custom_context.append(f"Pricing: {profile['pricing']}")
            
            if custom_context:
                prompt_parts.append("\n\nCustom Business Context:")
                prompt_parts.append("\n".join(custom_context))
        
        # Add tone customization
        tone = profile.get("tone", "friendly")
        if tone != "friendly":
            tone_instructions = {
                "professional": "Use formal, business-like language. Avoid casual expressions.",
                "casual": "Use very casual, relaxed language. Be more conversational.",
                "enthusiastic": "Be very energetic and positive. Use more exclamation marks!",
                "helpful": "Focus on being helpful and solution-oriented. Ask clarifying questions.",
            }
            if tone in tone_instructions:
                prompt_parts.append(f"\n\nTone: {tone_instructions[tone]}")
        
        # Add custom rules
        custom_rules = profile.get("custom_rules", [])
        if custom_rules:
            prompt_parts.append("\n\nCustom Rules:")
            for rule in custom_rules:
                if rule.strip():
                    prompt_parts.append(f"- {rule.strip()}")
        
        # Add custom prompt override (if provided)
        custom_prompt = profile.get("custom_prompt", "").strip()
        if custom_prompt:
            prompt_parts.append(f"\n\nAdditional Instructions:\n{custom_prompt}")
        
        # Add memory context if enabled
        enable_memory = profile.get("enable_memory", True)
        if enable_memory:
            context = self.memory_manager.get_context(account_id, user_id, max_messages=5)
            user_info = self.memory_manager.get_user_info(account_id, user_id)
            
            if context or user_info.get("tags"):
                prompt_parts.append("\n\nConversation Context:")
                
                # Add tags if available
                tags = user_info.get("tags", [])
                if tags:
                    prompt_parts.append(f"User interests: {', '.join(tags)}")
                
                # Add recent conversation summary
                if context:
                    recent_messages = []
                    for msg in context[-3:]:  # Last 3 messages
                        role = msg.get("role", "user")
                        text = msg.get("text", "")[:100]  # Truncate
                        if text:
                            recent_messages.append(f"{role}: {text}")
                    
                    if recent_messages:
                        prompt_parts.append("Recent conversation:")
                        prompt_parts.append("\n".join(recent_messages))
        
        # Combine all parts
        final_prompt = "\n".join(prompt_parts)
        
        logger.debug(
            "Prompt built",
            account_id=account_id,
            user_id=user_id,
            has_profile=has_custom_profile,
            has_memory=enable_memory and bool(context) if enable_memory else False,
            prompt_length=len(final_prompt),
        )
        
        return final_prompt
    
    def get_user_context_summary(self, account_id: str, user_id: str) -> str:
        """
        Get a summary of user context for logging/debugging.
        
        Args:
            account_id: Account identifier
            user_id: User identifier
            
        Returns:
            Context summary string
        """
        user_info = self.memory_manager.get_user_info(account_id, user_id)
        context = self.memory_manager.get_context(account_id, user_id, max_messages=3)
        
        parts = []
        if user_info.get("tags"):
            parts.append(f"Tags: {', '.join(user_info['tags'])}")
        if context:
            parts.append(f"Recent messages: {len(context)}")
        
        return "; ".join(parts) if parts else "No context"
