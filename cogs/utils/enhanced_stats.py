"""Enhanced statistics system with visualizations and analytics"""

import discord
import json
import os
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional, Any
from collections import defaultdict


class StatsAnalyzer:
    """Analyze bot usage statistics"""
    
    def __init__(self, stats_file: str = "data/stats.json", history_file: str = "data/history.json"):
        """Initialize stats analyzer"""
        self.stats_file = stats_file
        self.history_file = history_file
    
    def load_stats(self) -> Dict[str, Any]:
        """Load stats from file"""
        if os.path.exists(self.stats_file):
            try:
                with open(self.stats_file, "r") as f:
                    return json.load(f)
            except:
                return {}
        return {}
    
    def load_history(self) -> List[List]:
        """Load command history"""
        if os.path.exists(self.history_file):
            try:
                with open(self.history_file, "r") as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def get_top_commands(self, limit: int = 10) -> List[Tuple[str, int]]:
        """Get most used commands"""
        stats = self.load_stats()
        commands = stats.get("commands", {})
        sorted_cmds = sorted(commands.items(), key=lambda x: x[1], reverse=True)
        return sorted_cmds[:limit]
    
    def get_top_users(self, limit: int = 10) -> List[Tuple[str, Dict]]:
        """Get most active users"""
        stats = self.load_stats()
        users = stats.get("users", {})
        sorted_users = sorted(users.items(), key=lambda x: x[1].get("commands", 0), reverse=True)
        return sorted_users[:limit]
    
    def get_hourly_distribution(self, hours: int = 24) -> Dict[int, int]:
        """Get command distribution by hour"""
        history = self.load_history()
        cutoff = datetime.now() - timedelta(hours=hours)
        
        hourly = defaultdict(int)
        for entry in history:
            try:
                timestamp = datetime.fromisoformat(entry[1])
                if timestamp >= cutoff:
                    hour = timestamp.hour
                    hourly[hour] += 1
            except:
                continue
        
        return dict(hourly)
    
    def get_daily_stats(self, days: int = 7) -> Dict[str, int]:
        """Get daily command counts"""
        history = self.load_history()
        cutoff = datetime.now() - timedelta(days=days)
        
        daily = defaultdict(int)
        for entry in history:
            try:
                timestamp = datetime.fromisoformat(entry[1])
                if timestamp >= cutoff:
                    date_key = timestamp.strftime("%Y-%m-%d")
                    daily[date_key] += 1
            except:
                continue
        
        return dict(daily)
    
    def get_command_trends(self, hours: int = 24) -> Dict[str, List[int]]:
        """Get command usage trends"""
        history = self.load_history()
        cutoff = datetime.now() - timedelta(hours=hours)
        
        # Initialize hourly buckets
        trends = defaultdict(lambda: [0] * 24)
        
        for entry in history:
            try:
                cmd_name = entry[0]
                timestamp = datetime.fromisoformat(entry[1])
                if timestamp >= cutoff:
                    hour = timestamp.hour
                    trends[cmd_name][hour] += 1
            except:
                continue
        
        return dict(trends)
    
    def get_error_rate(self) -> Dict[str, float]:
        """Calculate error rate per command"""
        stats = self.load_stats()
        commands = stats.get("commands", {})
        errors = stats.get("errors", {})
        
        error_rates = {}
        for cmd, count in commands.items():
            error_count = errors.get(cmd, 0)
            if count > 0:
                error_rates[cmd] = (error_count / count) * 100
        
        return error_rates
    
    def get_user_stats(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get stats for specific user"""
        stats = self.load_stats()
        users = stats.get("users", {})
        return users.get(user_id)
    
    def get_recent_activity(self, hours: int = 1) -> List[Dict]:
        """Get recent command activity"""
        history = self.load_history()
        cutoff = datetime.now() - timedelta(hours=hours)
        
        recent = []
        for entry in history:
            try:
                timestamp = datetime.fromisoformat(entry[1])
                if timestamp >= cutoff:
                    recent.append({
                        "command": entry[0],
                        "timestamp": entry[1],
                        "hour": entry[2]
                    })
            except:
                continue
        
        return sorted(recent, key=lambda x: x["timestamp"], reverse=True)


def create_bar_chart(data: Dict[str, int], max_width: int = 20, max_items: int = 10) -> str:
    """
    Create ASCII bar chart.
    
    Args:
        data: Dictionary of labels and values
        max_width: Maximum width of bars in characters
        max_items: Maximum number of items to show
    
    Returns:
        Formatted bar chart string
    """
    if not data:
        return "no data available."
    
    # Sort by value and limit
    sorted_data = sorted(data.items(), key=lambda x: x[1], reverse=True)[:max_items]
    
    # Find max value for scaling
    max_val = max(v for _, v in sorted_data) if sorted_data else 1
    
    lines = []
    for label, value in sorted_data:
        # Calculate bar length
        bar_length = int((value / max_val) * max_width) if max_val > 0 else 0
        bar = "█" * bar_length
        
        # Format line
        lines.append(f"{label:<15} {bar} {value}")
    
    return "\n".join(lines)


def create_sparkline(values: List[int], width: int = 10) -> str:
    """
    Create a simple sparkline visualization.
    
    Args:
        values: List of numeric values
        width: Width in characters
    
    Returns:
        Sparkline string
    """
    if not values or all(v == 0 for v in values):
        return "▁" * width
    
    # Normalize to width
    if len(values) > width:
        # Downsample
        chunk_size = len(values) / width
        normalized = [
            int(sum(values[int(i * chunk_size):int((i + 1) * chunk_size)]) / chunk_size)
            for i in range(width)
        ]
    else:
        normalized = values + [0] * (width - len(values))
    
    # Map to sparkline characters
    chars = "▁▂▃▄▅▆▇█"
    max_val = max(normalized) if normalized else 1
    
    sparkline = ""
    for val in normalized:
        idx = min(int((val / max_val) * (len(chars) - 1)), len(chars) - 1) if max_val > 0 else 0
        sparkline += chars[idx]
    
    return sparkline


def create_stats_embed(analyzer: StatsAnalyzer, timeframe: str = "all") -> discord.Embed:
    """
    Create enhanced stats embed.
    
    Args:
        analyzer: StatsAnalyzer instance
        timeframe: "hour", "day", "week", or "all"
    
    Returns:
        Discord embed with stats
    """
    stats = analyzer.load_stats()
    
    # Determine timeframe
    if timeframe == "hour":
        hours = 1
        title = "stats - last hour"
    elif timeframe == "day":
        hours = 24
        title = "stats - last 24 hours"
    elif timeframe == "week":
        hours = 168
        title = "stats - last week"
    else:
        hours = None
        title = "stats - all time"
    
    embed = discord.Embed(
        title=title,
        color=0xE1F6FF,
        timestamp=datetime.now()
    )
    
    # Total commands
    if hours:
        recent = analyzer.get_recent_activity(hours)
        total_cmds = len(recent)
        embed.description = f"**{total_cmds:,}** commands executed"
    else:
        total_cmds = stats.get("total_commands", 0)
        embed.description = f"**{total_cmds:,}** total commands executed"
    
    # Top commands
    top_commands = analyzer.get_top_commands(8)
    if top_commands:
        cmd_chart = create_bar_chart(dict(top_commands), max_width=15, max_items=8)
        embed.add_field(
            name="top commands",
            value=f"```\n{cmd_chart}\n```",
            inline=False
        )
    
    # Top users
    top_users = analyzer.get_top_users(5)
    if top_users:
        user_lines = []
        for user_id, user_data in top_users[:5]:
            username = user_data.get("username", "unknown")
            cmd_count = user_data.get("commands", 0)
            user_lines.append(f"**{username}** - {cmd_count:,} commands")
        
        embed.add_field(
            name="top users",
            value="\n".join(user_lines),
            inline=False
        )
    
    # Hourly distribution (for recent timeframes)
    if hours and hours <= 24:
        hourly = analyzer.get_hourly_distribution(hours)
        if hourly:
            # Create 24-hour sparkline
            hour_values = [hourly.get(h, 0) for h in range(24)]
            sparkline = create_sparkline(hour_values, width=24)
            peak_hour = max(hourly, key=hourly.get)
            
            embed.add_field(
                name="activity by hour",
                value=f"```\n{sparkline}\n```\npeak: {peak_hour}:00 ({hourly[peak_hour]} commands)",
                inline=False
            )
    
    # Error rate
    error_rates = analyzer.get_error_rate()
    if error_rates:
        high_error_cmds = [(cmd, rate) for cmd, rate in error_rates.items() if rate > 5.0]
        if high_error_cmds:
            high_error_cmds.sort(key=lambda x: x[1], reverse=True)
            error_lines = [f"**!{cmd}** - {rate:.1f}%" for cmd, rate in high_error_cmds[:5]]
            embed.add_field(
                name="⚠️ commands with errors",
                value="\n".join(error_lines),
                inline=False
            )
    
    embed.set_footer(text="use !stats <hour/day/week> for different timeframes")
    
    return embed


def create_user_profile_embed(analyzer: StatsAnalyzer, user_id: str, username: str) -> discord.Embed:
    """
    Create user profile embed.
    
    Args:
        analyzer: StatsAnalyzer instance
        user_id: User ID
        username: Username for display
    
    Returns:
        Discord embed with user profile
    """
    user_stats = analyzer.get_user_stats(user_id)
    
    if not user_stats:
        embed = discord.Embed(
            title=f"profile - {username}",
            description="no activity recorded yet.",
            color=0xE1F6FF
        )
        return embed
    
    embed = discord.Embed(
        title=f"profile - {username}",
        color=0xE1F6FF
    )
    
    # Basic stats
    total_cmds = user_stats.get("commands", 0)
    embed.add_field(
        name="total commands",
        value=f"**{total_cmds:,}**",
        inline=True
    )
    
    # Last activity
    last_cmd = user_stats.get("last_command")
    if last_cmd:
        try:
            last_time = datetime.fromisoformat(last_cmd)
            time_ago = datetime.now() - last_time
            if time_ago.total_seconds() < 3600:
                time_str = f"{int(time_ago.total_seconds() / 60)} minutes ago"
            elif time_ago.total_seconds() < 86400:
                time_str = f"{int(time_ago.total_seconds() / 3600)} hours ago"
            else:
                time_str = f"{int(time_ago.total_seconds() / 86400)} days ago"
            
            embed.add_field(
                name="last active",
                value=time_str,
                inline=True
            )
        except:
            pass
    
    # Recent activity
    recent = analyzer.get_recent_activity(24)
    user_recent = [r for r in recent if str(user_id) in str(r.get("timestamp", ""))]
    
    if user_recent:
        embed.add_field(
            name="activity (24h)",
            value=f"**{len(user_recent)}** commands",
            inline=True
        )
    
    return embed
