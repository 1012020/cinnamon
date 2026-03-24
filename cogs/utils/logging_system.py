"""Enhanced logging system with rotation and severity levels"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class LogLevel(Enum):
    """Log severity levels"""
    DEBUG = 0
    INFO = 1
    WARNING = 2
    ERROR = 3
    CRITICAL = 4


class Logger:
    """Enhanced logger with file rotation and structured logging"""
    
    def __init__(self, name: str = "cinnamon", log_dir: str = "data/logs", 
                 max_size_mb: float = 10.0, max_files: int = 10):
        """
        Initialize logger.
        
        Args:
            name: Logger name (used for log filename)
            log_dir: Directory for log files
            max_size_mb: Maximum log file size before rotation
            max_files: Maximum number of log files to keep
        """
        self.name = name
        self.log_dir = log_dir
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.max_files = max_files
        self.min_level = LogLevel.INFO
        
        # Create log directory if needed
        os.makedirs(log_dir, exist_ok=True)
        
        # Log file paths
        self.main_log = os.path.join(log_dir, f"{name}.log")
        self.error_log = os.path.join(log_dir, "errors.log")
        self.json_log = os.path.join(log_dir, f"{name}_structured.jsonl")
    
    def set_level(self, level: LogLevel) -> None:
        """Set minimum logging level"""
        self.min_level = level
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level"""
        return level.value >= self.min_level.value
    
    def _rotate_if_needed(self, log_path: str) -> None:
        """Rotate log file if it exceeds max size"""
        if not os.path.exists(log_path):
            return
        
        if os.path.getsize(log_path) < self.max_size_bytes:
            return
        
        # Rotate existing logs
        base = log_path
        for i in range(self.max_files - 1, 0, -1):
            old_path = f"{base}.{i}" if i > 1 else base
            new_path = f"{base}.{i + 1}"
            
            if os.path.exists(old_path):
                if i == self.max_files - 1:
                    os.remove(old_path)  # Delete oldest
                else:
                    try:
                        os.replace(old_path, new_path)
                    except Exception as e:
                        print(f"Rotate rename error: {e}")
        
        # Rename current to .1
        try:
            os.replace(log_path, f"{base}.1")
        except Exception as e:
            print(f"Rotate replace error: {e}")
    
    def _format_message(self, level: LogLevel, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """Format log message"""
        timestamp = datetime.now().isoformat()
        level_name = level.name.ljust(8)
        
        formatted = f"[{timestamp}] [{level_name}] {message}"
        
        if context:
            context_str = " | ".join([f"{k}={v}" for k, v in context.items()])
            formatted += f" | {context_str}"
        
        return formatted
    
    def _write_to_file(self, filepath: str, content: str) -> None:
        """Write to log file with rotation"""
        self._rotate_if_needed(filepath)
        try:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(content + "\n")
        except Exception as e:
            print(f"Failed to write log: {e}")
    
    def _write_json(self, data: Dict[str, Any]) -> None:
        """Write structured JSON log entry"""
        try:
            self._rotate_if_needed(self.json_log)
            with open(self.json_log, "a", encoding="utf-8") as f:
                json.dump(data, f, separators=(',', ':'))
                f.write("\n")
        except Exception as e:
            print(f"Failed to write structured log: {e}")
    
    def log(self, level: LogLevel, message: str, **context) -> None:
        """
        Log a message with optional context.
        
        Args:
            level: Log level
            message: Log message
            **context: Additional context key-value pairs
        """
        if not self._should_log(level):
            return
        
        # Format message
        formatted = self._format_message(level, message, context if context else None)
        
        # Write to main log
        self._write_to_file(self.main_log, formatted)
        
        # Write errors to separate error log
        if level.value >= LogLevel.ERROR.value:
            self._write_to_file(self.error_log, formatted)
        
        # Write structured JSON
        json_entry = {
            "timestamp": datetime.now().isoformat(),
            "level": level.name,
            "message": message,
            "logger": self.name
        }
        if context:
            json_entry["context"] = context
        self._write_json(json_entry)
        
        # Also print critical errors
        if level == LogLevel.CRITICAL:
            print(f"CRITICAL: {message}")
    
    def debug(self, message: str, **context) -> None:
        """Log debug message"""
        self.log(LogLevel.DEBUG, message, **context)
    
    def info(self, message: str, **context) -> None:
        """Log info message"""
        self.log(LogLevel.INFO, message, **context)
    
    def warning(self, message: str, **context) -> None:
        """Log warning message"""
        self.log(LogLevel.WARNING, message, **context)
    
    def error(self, message: str, **context) -> None:
        """Log error message"""
        self.log(LogLevel.ERROR, message, **context)
    
    def critical(self, message: str, **context) -> None:
        """Log critical message"""
        self.log(LogLevel.CRITICAL, message, **context)
    
    def command(self, user_id: str, username: str, command: str, **context) -> None:
        """Log command execution"""
        self.info(f"Command executed: {command}", 
                 user_id=user_id, username=username, **context)
    
    def command_error(self, user_id: str, username: str, command: str, error: str, **context) -> None:
        """Log command error"""
        self.error(f"Command error: {command} - {error}",
                  user_id=user_id, username=username, **context)


# Global logger instance
_global_logger: Optional[Logger] = None


def get_logger() -> Logger:
    """Get or create global logger instance"""
    global _global_logger
    if _global_logger is None:
        _global_logger = Logger()
    return _global_logger


def init_logger(name: str = "cinnamon", log_dir: str = "data/logs", 
                max_size_mb: float = 10.0, max_files: int = 10) -> Logger:
    """
    Initialize global logger.
    
    Args:
        name: Logger name
        log_dir: Log directory
        max_size_mb: Max size before rotation
        max_files: Max number of files to keep
    
    Returns:
        Logger instance
    """
    global _global_logger
    _global_logger = Logger(name, log_dir, max_size_mb, max_files)
    return _global_logger


def cleanup_old_logs(log_dir: str = "data/logs", days: int = 30) -> int:
    """
    Clean up log files older than specified days.
    
    Args:
        log_dir: Log directory
        days: Files older than this will be deleted
    
    Returns:
        Number of files deleted
    """
    if not os.path.exists(log_dir):
        return 0
    
    import time
    cutoff = time.time() - (days * 86400)
    deleted = 0
    
    for filename in os.listdir(log_dir):
        filepath = os.path.join(log_dir, filename)
        if os.path.isfile(filepath):
            if os.path.getmtime(filepath) < cutoff:
                try:
                    os.remove(filepath)
                    deleted += 1
                except Exception as e:
                    print(f"Failed to remove old log {filepath}: {e}")
    
    return deleted


def analyze_logs(log_path: str = "data/logs/cinnamon_structured.jsonl", 
                 hours: int = 24) -> Dict[str, Any]:
    """
    Analyze structured log file for insights.
    
    Args:
        log_path: Path to structured JSON log
        hours: Number of hours to analyze
    
    Returns:
        Dictionary with analysis results
    """
    if not os.path.exists(log_path):
        return {"error": "log file not found"}
    
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(hours=hours)
    
    stats = {
        "total_entries": 0,
        "by_level": {},
        "errors": [],
        "time_range": {"start": None, "end": None}
    }
    
    try:
        with open(log_path, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    entry = json.loads(line.strip())
                    entry_time = datetime.fromisoformat(entry["timestamp"])
                    
                    if entry_time < cutoff:
                        continue
                    
                    stats["total_entries"] += 1
                    
                    # Track by level
                    level = entry.get("level", "UNKNOWN")
                    stats["by_level"][level] = stats["by_level"].get(level, 0) + 1
                    
                    # Collect errors
                    if level in ["ERROR", "CRITICAL"]:
                        stats["errors"].append({
                            "timestamp": entry["timestamp"],
                            "message": entry.get("message", ""),
                            "level": level
                        })
                    
                    # Track time range
                    if stats["time_range"]["start"] is None:
                        stats["time_range"]["start"] = entry["timestamp"]
                    stats["time_range"]["end"] = entry["timestamp"]
                    
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        return {"error": str(e)}
    
    return stats
