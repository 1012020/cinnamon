"""Progress bar utilities for Discord messages"""

import discord
from typing import Optional
import asyncio


class ProgressBar:
    """Creates and updates progress bars in Discord messages"""
    
    def __init__(self, total: int = 100, length: int = 20, fill_char: str = "█", empty_char: str = "░"):
        """
        Initialize progress bar.
        
        Args:
            total: Total number of steps
            length: Length of the progress bar in characters
            fill_char: Character for filled portion
            empty_char: Character for empty portion
        """
        self.total = total
        self.current = 0
        self.length = length
        self.fill_char = fill_char
        self.empty_char = empty_char
    
    def update(self, current: int) -> None:
        """Update current progress"""
        self.current = min(current, self.total)
    
    def increment(self, amount: int = 1) -> None:
        """Increment progress by amount"""
        self.current = min(self.current + amount, self.total)
    
    def get_percentage(self) -> float:
        """Get current percentage (0-100)"""
        if self.total == 0:
            return 100.0
        return (self.current / self.total) * 100
    
    def render(self, show_percentage: bool = True, show_count: bool = False, prefix: str = "") -> str:
        """
        Render progress bar as string.
        
        Args:
            show_percentage: Show percentage at end
            show_count: Show current/total count
            prefix: Text to show before bar
        
        Returns:
            Formatted progress bar string
        """
        percentage = self.get_percentage()
        filled_length = int(self.length * self.current / self.total) if self.total > 0 else self.length
        
        bar = self.fill_char * filled_length + self.empty_char * (self.length - filled_length)
        
        result = f"{prefix}{bar}"
        
        if show_percentage:
            result += f" {percentage:.0f}%"
        
        if show_count:
            result += f" ({self.current}/{self.total})"
        
        return result
    
    def __str__(self) -> str:
        return self.render()


class DiscordProgressBar:
    """Progress bar that updates Discord messages"""
    
    def __init__(self, ctx, total: int, message: Optional[discord.Message] = None, 
                 update_interval: float = 2.0, prefix: str = ""):
        """
        Initialize Discord progress bar.
        
        Args:
            ctx: Discord context
            total: Total number of steps
            message: Existing message to update (creates new if None)
            update_interval: Minimum seconds between Discord updates
            prefix: Text prefix for progress bar
        """
        self.ctx = ctx
        self.message = message
        self.bar = ProgressBar(total=total)
        self.update_interval = update_interval
        self.prefix = prefix
        self.last_update = 0
        self._lock = asyncio.Lock()
    
    async def start(self, initial_text: str = "processing...") -> None:
        """Start progress bar by creating or updating message"""
        from cogs.utils.helpers import send_status
        if self.message is None:
            self.message = await send_status(self.ctx, initial_text)
        else:
            await send_status(self.ctx, initial_text, status_msg=self.message)
    
    async def update(self, current: int, force: bool = False, text: Optional[str] = None) -> None:
        """
        Update progress bar.
        
        Args:
            current: Current progress value
            force: Force update even if interval hasn't elapsed
            text: Optional text to show below progress bar
        """
        import time
        from cogs.utils.helpers import send_status
        
        self.bar.update(current)
        
        # Rate limit updates
        current_time = time.time()
        if not force and (current_time - self.last_update) < self.update_interval:
            return
        
        async with self._lock:
            try:
                bar_text = self.bar.render(show_percentage=True, prefix=self.prefix)
                if text:
                    full_text = f"{bar_text}\n{text}"
                else:
                    full_text = bar_text
                
                await send_status(self.ctx, full_text, status_msg=self.message)
                self.last_update = current_time
            except Exception:
                pass  # Ignore update errors
    
    async def increment(self, amount: int = 1, text: Optional[str] = None) -> None:
        """Increment progress and update"""
        new_current = self.bar.current + amount
        await self.update(new_current, text=text)
    
    async def complete(self, final_text: str = "complete!") -> None:
        """Mark as complete and show final message"""
        from cogs.utils.helpers import send_status
        self.bar.update(self.bar.total)
        await send_status(self.ctx, final_text, status_msg=self.message)


def create_simple_progress(current: int, total: int, length: int = 15) -> str:
    """
    Create a simple progress bar string.
    
    Args:
        current: Current progress
        total: Total steps
        length: Bar length in characters
    
    Returns:
        Progress bar string with percentage
    """
    bar = ProgressBar(total=total, length=length)
    bar.update(current)
    return bar.render(show_percentage=True)


def create_stage_indicator(current_stage: int, total_stages: int, stage_names: Optional[list] = None) -> str:
    """
    Create a stage indicator (e.g., "step 2/5: processing")
    
    Args:
        current_stage: Current stage number (1-indexed)
        total_stages: Total number of stages
        stage_names: Optional list of stage names
    
    Returns:
        Stage indicator string
    """
    base = f"step {current_stage}/{total_stages}"
    
    if stage_names and 0 < current_stage <= len(stage_names):
        stage_name = stage_names[current_stage - 1]
        return f"{base}: {stage_name}"
    
    return base


def create_spinner(step: int, states: Optional[list] = None) -> str:
    """
    Create an animated spinner character.
    
    Args:
        step: Current animation step
        states: Optional list of spinner states
    
    Returns:
        Current spinner character
    """
    if states is None:
        states = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
    
    return states[step % len(states)]
