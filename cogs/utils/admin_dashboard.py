"""Admin dashboard web interface"""

from flask import Flask, render_template, jsonify, request, redirect, url_for
import asyncio
import os
import json
import shutil
import subprocess
import io
import contextlib
import traceback
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple
import secrets
import discord


class AdminDashboard:
    """Web-based admin dashboard for bot monitoring"""
    
    def __init__(self, bot, host: str = "127.0.0.1", port: int = 5000):
        """
        Initialize admin dashboard.
        
        Args:
            bot: Discord bot instance
            host: Host address
            port: Port number
        """
        self.bot = bot
        self.host = host
        self.port = port
        
        # Get absolute paths to project root and data folder
        self.project_root = os.getcwd()
        self.data_dir = os.path.join(self.project_root, "data")
        self.logs_dir = os.path.join(self.data_dir, "logs")
        
        # Get absolute path to templates folder (from project root)
        template_dir = os.path.join(self.project_root, "dashboard", "templates")
        self.app = Flask(__name__, template_folder=template_dir)
        self.app.secret_key = secrets.token_hex(32)
        
        # ADMIN_TOKEN env var with fallback for convenience
        # Note: setting a default here is less secure; consider using an env var in production.
        self.auth_token = os.getenv("ADMIN_TOKEN", "cinnamon-admin")

        # Simple per-request auth for all /api/* endpoints
        @self.app.before_request
        def _require_api_auth():
            try:
                if request.path.startswith("/api/"):
                    # Allow local browser access without token for convenience
                    remote = (request.remote_addr or "").strip()
                    host_header = (request.host or "")
                    if remote in ("127.0.0.1", "::1") or host_header.startswith(str(self.host)):
                        return None
                    if not self._is_authorized(request):
                        return jsonify({"error": "Unauthorized"}), 401
            except Exception:
                return jsonify({"error": "Unauthorized"}), 401

        self._setup_routes()
    
    def _setup_routes(self):
        """Setup Flask routes"""
        
        @self.app.route("/")
        def index():
            """Main dashboard page"""
            return render_template("dashboard.html", 
                                 bot_name=self.bot.user.name if self.bot.user else "Cinnamon")
        
        @self.app.route("/api/stats")
        def api_stats():
            """Get bot statistics"""
            try:
                stats = self._get_stats()
                return jsonify(stats)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/api/commands")
        def api_commands():
            """Get command usage data"""
            try:
                commands = self._get_command_stats()
                return jsonify(commands)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/api/users")
        def api_users():
            """Get user statistics"""
            try:
                users = self._get_user_stats()
                return jsonify(users)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/api/logs")
        def api_logs():
            """Get recent log entries"""
            try:
                lines = int(request.args.get("lines", 100))
                logs = self._get_recent_logs(lines)
                return jsonify(logs)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/api/active-tasks")
        def api_active_tasks():
            """Get currently active tasks"""
            try:
                tasks = self._get_active_tasks()
                return jsonify(tasks)
            except Exception as e:
                return jsonify({"error": str(e)}), 500
        
        @self.app.route("/api/health")
        def api_health():
            """Health check endpoint"""
            return jsonify({
                "status": "healthy",
                "uptime": self._get_uptime(),
                "bot_connected": self.bot.is_ready() if hasattr(self.bot, "is_ready") else False
            })

        @self.app.route("/api/control/actions")
        def api_control_actions():
            """Get available control actions"""
            return jsonify({
                "requires_token": True,
                "actions": [
                    "reload_cogs",
                    "sync_commands",
                    "set_presence",
                    "send_message",
                    "cancel_task",
                    "clear_logs",
                    "backup_keys",
                    "generate_keys",
                    "delete_key",
                    "post_keys",
                    "reset_stats",
                    "run_shell",
                    "run_python",
                    "read_file",
                    "write_file",
                    "shutdown_bot"
                ]
            })

        @self.app.route("/api/control/capabilities")
        def api_control_capabilities():
            """Get command and cog inventory"""
            try:
                commands_data = []
                for cmd in sorted(self.bot.commands, key=lambda c: c.name):
                    commands_data.append({
                        "name": cmd.name,
                        "aliases": list(cmd.aliases),
                        "signature": cmd.signature,
                        "help": cmd.help or ""
                    })

                return jsonify({
                    "commands": commands_data,
                    "cogs": sorted(list(self.bot.cogs.keys())),
                    "project_root": self.project_root,
                    "data_dir": self.data_dir
                })
            except Exception as e:
                return jsonify({"error": str(e)}), 500

        @self.app.route("/api/control/keys")
        def api_control_keys():
            """Get key database entries"""
            try:
                if not self._is_authorized(request):
                    return jsonify({"success": False, "error": "Unauthorized"}), 401
                return jsonify({"success": True, "keys": self._load_keys_data()})
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

        @self.app.route("/api/control", methods=["POST"])
        def api_control():
            """Perform admin control actions"""
            try:
                if not self._is_authorized(request):
                    return jsonify({"success": False, "error": "Unauthorized"}), 401

                payload = request.get_json(silent=True) or {}
                action = (payload.get("action") or "").strip()
                if not action:
                    return jsonify({"success": False, "error": "Missing action"}), 400

                success, result = self._execute_action(action, payload)
                status_code = 200 if success else 400
                return jsonify({"success": success, **result}), status_code
            except Exception as e:
                return jsonify({"success": False, "error": str(e)}), 500

    def _is_authorized(self, req) -> bool:
        """Check admin token authorization"""
        provided = req.headers.get("X-Admin-Token", "")
        if not provided:
            auth_header = req.headers.get("Authorization", "")
            if auth_header.lower().startswith("bearer "):
                provided = auth_header[7:].strip()
        return bool(provided) and secrets.compare_digest(provided, self.auth_token)

    def _run_coro(self, coro, timeout: int = 20):
        """Run coroutine safely from Flask thread on bot loop"""
        loop = getattr(self.bot, "loop", None)
        if loop is None or loop.is_closed():
            raise RuntimeError("Bot event loop is not available")
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout)

    def _execute_action(self, action: str, payload: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """Dispatch control actions"""
        if action == "reload_cogs":
            result = self._run_coro(self._reload_cogs_async())
            return True, {"message": "Cogs reloaded", "result": result}

        if action == "sync_commands":
            synced = self._run_coro(self.bot.tree.sync())
            return True, {"message": f"Synced {len(synced)} slash commands"}

        if action == "set_presence":
            status_name = (payload.get("status") or "online").lower()
            activity_text = (payload.get("text") or "").strip()[:128]
            status_map = {
                "online": discord.Status.online,
                "idle": discord.Status.idle,
                "dnd": discord.Status.dnd,
                "invisible": discord.Status.invisible
            }
            status_value = status_map.get(status_name, discord.Status.online)
            activity = discord.Game(name=activity_text) if activity_text else None
            self._run_coro(self.bot.change_presence(status=status_value, activity=activity))
            return True, {"message": "Presence updated"}

        if action == "send_message":
            channel_id = payload.get("channel_id")
            message = (payload.get("message") or "").strip()
            if not channel_id:
                return False, {"error": "channel_id is required"}
            if not message:
                return False, {"error": "message is required"}
            result = self._run_coro(self._send_message_async(str(channel_id), message[:2000]))
            return True, {"message": "Message sent", **result}

        if action == "cancel_task":
            user_id = payload.get("user_id")
            if user_id is None:
                return False, {"error": "user_id is required"}
            result = self._cancel_task(str(user_id))
            return result

        if action == "clear_logs":
            log_file = os.path.join(self.logs_dir, "cinnamon.log")
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("")
            return True, {"message": "Logs cleared"}

        if action == "backup_keys":
            keys_file = os.path.join(self.data_dir, "keys.json")
            if not os.path.exists(keys_file):
                return False, {"error": "keys.json not found"}
            backup_dir = os.path.join(self.data_dir, "backups")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(backup_dir, f"keys_manual_{timestamp}.json")
            shutil.copy(keys_file, backup_file)
            return True, {"message": "Backup created", "file": os.path.basename(backup_file)}

        if action == "generate_keys":
            count = int(payload.get("count", 1))
            if count < 1 or count > 1000:
                return False, {"error": "count must be between 1 and 1000"}
            keys = self._generate_keys(count)
            return True, {
                "message": f"Generated {len(keys)} key(s)",
                "generated_keys": keys
            }

        if action == "delete_key":
            key = (payload.get("key") or "").strip()
            if not key:
                return False, {"error": "key is required"}
            keys_data = self._load_keys_data()
            if key not in keys_data:
                return False, {"error": "key not found"}
            del keys_data[key]
            self._save_keys_data(keys_data)
            return True, {"message": "Key deleted"}

        if action == "post_keys":
            result = self._post_keys_message()
            return result

        if action == "reset_stats":
            stats_file = os.path.join(self.data_dir, "stats.json")
            empty = {"total_commands": 0, "commands": {}, "users": {}, "errors": {}}
            with open(stats_file, "w", encoding="utf-8") as f:
                json.dump(empty, f, indent=2)
            if hasattr(self.bot, "command_stats"):
                self.bot.command_stats = empty
            return True, {"message": "Stats reset"}

        if action == "run_shell":
            command = (payload.get("command") or "").strip()
            if not command:
                return False, {"error": "command is required"}
            result = self._run_shell(command)
            return True, {"message": "Shell command executed", **result}

        if action == "run_python":
            code = payload.get("code") or ""
            if not code.strip():
                return False, {"error": "code is required"}
            result = self._run_python(code)
            return True, {"message": "Python executed", **result}

        if action == "read_file":
            rel_path = payload.get("path") or ""
            target_path = self._safe_project_path(rel_path)
            if not os.path.exists(target_path):
                return False, {"error": "File not found"}
            if os.path.isdir(target_path):
                return True, {"entries": sorted(os.listdir(target_path))}
            with open(target_path, "r", encoding="utf-8", errors="replace") as f:
                content = f.read()
            return True, {"path": rel_path, "content": content[:200000]}

        if action == "write_file":
            rel_path = payload.get("path") or ""
            content = payload.get("content")
            if content is None:
                return False, {"error": "content is required"}
            target_path = self._safe_project_path(rel_path)
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(str(content))
            return True, {"message": "File written", "path": rel_path}

        if action == "shutdown_bot":
            self._run_coro(self.bot.close())
            return True, {"message": "Bot shutdown requested"}

        return False, {"error": f"Unknown action: {action}"}

    async def _reload_cogs_async(self) -> Dict[str, str]:
        """Reload main cogs"""
        results = {}
        for ext in ["cogs.audio", "cogs.tools"]:
            try:
                await self.bot.reload_extension(ext)
                results[ext] = "reloaded"
            except Exception:
                try:
                    await self.bot.load_extension(ext)
                    results[ext] = "loaded"
                except Exception as e:
                    results[ext] = f"failed: {str(e)}"
        return results

    def _safe_project_path(self, rel_path: str) -> str:
        """Resolve a workspace-relative path safely"""
        clean = (rel_path or "").replace("\\", "/").lstrip("/")
        abs_path = os.path.abspath(os.path.join(self.project_root, clean))
        root = os.path.abspath(self.project_root)
        if not abs_path.startswith(root):
            raise ValueError("Path escapes project root")
        return abs_path

    def _keys_file_path(self) -> str:
        return os.path.join(self.data_dir, "keys.json")

    def _load_keys_data(self) -> Dict[str, Any]:
        keys_file = self._keys_file_path()
        if not os.path.exists(keys_file):
            return {}
        try:
            with open(keys_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_keys_data(self, data: Dict[str, Any]) -> None:
        keys_file = self._keys_file_path()
        os.makedirs(os.path.dirname(keys_file), exist_ok=True)
        with open(keys_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _generate_keys(self, count: int) -> list:
        keys_data = self._load_keys_data()
        generated = []
        for _ in range(count):
            key = secrets.token_urlsafe(32)
            while key in keys_data:
                key = secrets.token_urlsafe(32)
            keys_data[key] = {
                "used": False,
                "user_id": None,
                "created_at": datetime.now().isoformat(),
                "redeemed_at": None
            }
            generated.append(key)

        self._save_keys_data(keys_data)
        copy_file = os.path.join(self.data_dir, "keys_copy.txt")
        with open(copy_file, "w", encoding="utf-8") as f:
            f.write("\n".join(generated))
        return generated

    def _post_keys_message(self) -> Tuple[bool, Dict[str, Any]]:
        """Post live keys message to the designated channel"""
        try:
            tool_cog = self.bot.get_cog("ToolCommands")
            if not tool_cog:
                return False, {"error": "ToolCommands cog not loaded"}
            
            # Reload keys from file to get latest generated keys
            tool_cog.generated_keys = tool_cog._load_keys()
            
            keys_channel_id = getattr(tool_cog, "keys_channel_id", 1478989104497561642)
            channel = self.bot.get_channel(keys_channel_id)
            if not channel:
                return False, {"error": f"Channel {keys_channel_id} not found"}
            
            unused = tool_cog._get_unused_keys()
            if not unused:
                return False, {"error": "No unused keys to post"}
            
            key_list = "\n".join(unused)
            content = f"**available keys** ({len(unused)} total)\n\n```\n{key_list}\n```\n\nreply with `!redeem <key>` in <#1465525274874609817> to redeem."
            message = self._run_coro(self._post_keys_async(channel, content, tool_cog))
            return True, {"message": "Keys message posted", "message_id": message}
        except Exception as e:
            return False, {"error": str(e)}

    async def _post_keys_async(self, channel, content: str, tool_cog):
        """Async helper to post message and track ID"""
        message = await channel.send(content)
        tool_cog.keys_message_id = message.id
        return str(message.id)
    def _run_shell(self, command: str) -> Dict[str, Any]:
        """Run shell command in project root"""
        try:
            completed = subprocess.run(
                command,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                shell=True,
                timeout=60
            )
            output = (completed.stdout or "") + ("\n" + completed.stderr if completed.stderr else "")
            return {
                "exit_code": completed.returncode,
                "output": output[-20000:]
            }
        except Exception as e:
            return {"exit_code": -1, "output": f"error: {str(e)}"}

    def _run_python(self, code: str) -> Dict[str, Any]:
        """Run Python snippet with dashboard globals"""
        stdout_buffer = io.StringIO()
        stderr_buffer = io.StringIO()
        local_vars = {
            "bot": self.bot,
            "dashboard": self,
            "os": os,
            "json": json,
            "datetime": datetime
        }
        try:
            with contextlib.redirect_stdout(stdout_buffer), contextlib.redirect_stderr(stderr_buffer):
                exec(code, {}, local_vars)
            output = stdout_buffer.getvalue()
            err = stderr_buffer.getvalue()
            return {"output": (output + ("\n" + err if err else ""))[-20000:]}
        except Exception:
            trace = traceback.format_exc()
            return {"output": (stdout_buffer.getvalue() + "\n" + trace)[-20000:], "error": True}

    async def _send_message_async(self, channel_id: str, message: str) -> Dict[str, Any]:
        """Send a message to a Discord channel"""
        try:
            channel_int = int(channel_id)
        except ValueError:
            raise ValueError("channel_id must be a valid integer")

        channel = self.bot.get_channel(channel_int)
        if channel is None:
            channel = await self.bot.fetch_channel(channel_int)
        sent = await channel.send(message)
        return {"channel_id": str(channel_int), "message_id": str(sent.id)}

    def _cancel_task(self, user_id: str) -> Tuple[bool, Dict[str, Any]]:
        """Cancel active task for a user id"""
        if not hasattr(self.bot, "active_tasks"):
            return False, {"error": "active_tasks not available"}

        normalized_id = user_id.strip()
        try:
            int_id = int(normalized_id)
        except ValueError:
            return False, {"error": "user_id must be an integer"}

        task_info = self.bot.active_tasks.get(int_id)
        if not task_info:
            return False, {"error": "No active task found for that user"}

        temp_files = task_info.get("files", [])
        for path in temp_files:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass

        message_obj = task_info.get("message")
        if message_obj:
            try:
                self._run_coro(message_obj.edit(content="❌ Task cancelled by admin dashboard."))
            except Exception:
                pass

        del self.bot.active_tasks[int_id]
        return True, {"message": f"Cancelled task for user {int_id}"}
    
    def _get_stats(self) -> Dict[str, Any]:
        """Get overall statistics"""
        stats = {}
        
        stats_file = os.path.join(self.data_dir, "stats.json")
        if os.path.exists(stats_file):
            try:
                with open(stats_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    stats["total_commands"] = data.get("total_commands", 0)
                    stats["total_users"] = len(data.get("users", {}))
                    stats["total_errors"] = sum(data.get("errors", {}).values())
            except Exception as e:
                print(f"Error reading stats: {e}")
        
        # Bot info
        if hasattr(self.bot, "guilds"):
            stats["guild_count"] = len(self.bot.guilds)
        
        return stats
    
    def _get_command_stats(self) -> Dict[str, Any]:
        """Get command usage statistics"""
        stats_file = os.path.join(self.data_dir, "stats.json")
        if not os.path.exists(stats_file):
            return {"commands": []}
        
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                commands = data.get("commands", {})
                errors = data.get("errors", {})
                
                # Calculate error rates
                command_data = []
                for cmd, count in commands.items():
                    error_count = errors.get(cmd, 0)
                    error_rate = (error_count / count * 100) if count > 0 else 0
                    command_data.append({
                        "name": cmd,
                        "count": count,
                        "errors": error_count,
                        "error_rate": round(error_rate, 2)
                    })
                
                # Sort by count
                command_data.sort(key=lambda x: x["count"], reverse=True)
                
                return {"commands": command_data}
        except Exception as e:
            print(f"Error reading command stats: {e}")
            return {"commands": []}
    
    def _get_user_stats(self) -> Dict[str, Any]:
        """Get user statistics"""
        stats_file = os.path.join(self.data_dir, "stats.json")
        if not os.path.exists(stats_file):
            return {"users": []}
        
        try:
            with open(stats_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                users = data.get("users", {})
                
                user_data = []
                for user_id, info in users.items():
                    user_data.append({
                        "id": user_id,
                        "username": info.get("username", "Unknown"),
                        "commands": info.get("commands", 0),
                        "last_command": info.get("last_command")
                    })
                
                # Sort by command count
                user_data.sort(key=lambda x: x["commands"], reverse=True)
                
                return {"users": user_data[:50]}  # Top 50 users
        except Exception as e:
            print(f"Error reading user stats: {e}")
            return {"users": []}
    
    def _get_recent_logs(self, lines: int = 100) -> Dict[str, Any]:
        """Get recent log entries"""
        log_file = os.path.join(self.logs_dir, "cinnamon.log")
        
        if not os.path.exists(log_file):
            return {"logs": [f"Log file not found: {log_file}"]}
        
        try:
            with open(log_file, "r", encoding="utf-8") as f:
                all_lines = f.readlines()
                recent = all_lines[-lines:]
                return {"logs": [line.strip() for line in recent]}
        except Exception as e:
            return {"logs": [f"Error reading logs: {str(e)}"]}
    
    def _get_active_tasks(self) -> Dict[str, Any]:
        """Get currently active tasks"""
        if not hasattr(self.bot, "active_tasks"):
            return {"tasks": []}
        
        tasks = []
        for user_id, task_info in self.bot.active_tasks.items():
            start_time = task_info.get("start_time")
            elapsed = None
            if start_time:
                elapsed = (datetime.now() - start_time).total_seconds()
            
            tasks.append({
                "user_id": user_id,
                "command": task_info.get("command"),
                "elapsed_seconds": round(elapsed, 1) if elapsed else None
            })
        
        return {"tasks": tasks}
    
    def _get_uptime(self) -> str:
        """Get bot uptime"""
        # This would need to track start time in the bot
        if hasattr(self.bot, "start_time"):
            uptime = datetime.now() - self.bot.start_time
            days = uptime.days
            hours = uptime.seconds // 3600
            minutes = (uptime.seconds % 3600) // 60
            return f"{days}d {hours}h {minutes}m"
        return "unknown"
    
    def run(self, debug: bool = False):
        """
        Run the dashboard server.
        
        Args:
            debug: Enable debug mode
        """
        print(f"Starting admin dashboard on http://{self.host}:{self.port}")
        self.app.run(host=self.host, port=self.port, debug=debug, use_reloader=False)
    
    def run_async(self):
        """Run dashboard in separate thread"""
        import threading
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread


def create_dashboard_html() -> str:
    """Create HTML template for dashboard"""
    return """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{{ bot_name }} - Admin Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #0d1117; 
            color: #c9d1d9;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { color: #58a6ff; margin-bottom: 30px; }
        h2 { color: #8b949e; margin: 20px 0 10px; font-size: 18px; }
        .stats-grid { 
            display: grid; 
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .stat-card {
            background: #161b22;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 20px;
        }
        .stat-value { font-size: 32px; font-weight: bold; color: #58a6ff; }
        .stat-label { color: #8b949e; margin-top: 5px; }
        table { 
            width: 100%; 
            border-collapse: collapse;
            background: #161b22;
            border-radius: 6px;
            overflow: hidden;
        }
        th, td { 
            padding: 12px; 
            text-align: left;
            border-bottom: 1px solid #30363d;
        }
        th { 
            background: #0d1117;
            color: #8b949e;
            font-weight: 600;
        }
        tr:hover { background: #1c2128; }
        .error-rate { color: #f85149; }
        .success-rate { color: #3fb950; }
        .log-container {
            background: #0d1117;
            border: 1px solid #30363d;
            border-radius: 6px;
            padding: 15px;
            max-height: 400px;
            overflow-y: auto;
            font-family: 'Courier New', monospace;
            font-size: 12px;
        }
        .log-line { 
            padding: 2px 0;
            border-bottom: 1px solid #21262d;
        }
        .refresh-btn {
            background: #238636;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            margin-bottom: 10px;
        }
        .refresh-btn:hover { background: #2ea043; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 {{ bot_name }} - Admin Dashboard</h1>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-value" id="total-commands">-</div>
                <div class="stat-label">Total Commands</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-users">-</div>
                <div class="stat-label">Total Users</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="total-errors">-</div>
                <div class="stat-label">Total Errors</div>
            </div>
            <div class="stat-card">
                <div class="stat-value" id="active-tasks">-</div>
                <div class="stat-label">Active Tasks</div>
            </div>
        </div>

        <h2>Top Commands</h2>
        <table id="commands-table">
            <thead>
                <tr>
                    <th>Command</th>
                    <th>Usage Count</th>
                    <th>Errors</th>
                    <th>Error Rate</th>
                </tr>
            </thead>
            <tbody id="commands-body"></tbody>
        </table>

        <h2>Top Users</h2>
        <table id="users-table">
            <thead>
                <tr>
                    <th>Username</th>
                    <th>Commands</th>
                    <th>Last Active</th>
                </tr>
            </thead>
            <tbody id="users-body"></tbody>
        </table>

        <h2>Recent Logs</h2>
        <button class="refresh-btn" onclick="loadLogs()">Refresh Logs</button>
        <div class="log-container" id="logs"></div>
    </div>

    <script>
        async function loadStats() {
            const res = await fetch('/api/stats');
            const data = await res.json();
            document.getElementById('total-commands').textContent = data.total_commands || 0;
            document.getElementById('total-users').textContent = data.total_users || 0;
            document.getElementById('total-errors').textContent = data.total_errors || 0;
        }

        async function loadCommands() {
            const res = await fetch('/api/commands');
            const data = await res.json();
            const tbody = document.getElementById('commands-body');
            tbody.innerHTML = '';
            (data.commands || []).slice(0, 15).forEach(cmd => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>!${cmd.name}</td>
                    <td>${cmd.count.toLocaleString()}</td>
                    <td>${cmd.errors}</td>
                    <td class="${cmd.error_rate > 5 ? 'error-rate' : 'success-rate'}">
                        ${cmd.error_rate.toFixed(1)}%
                    </td>
                `;
            });
        }

        async function loadUsers() {
            const res = await fetch('/api/users');
            const data = await res.json();
            const tbody = document.getElementById('users-body');
            tbody.innerHTML = '';
            (data.users || []).slice(0, 15).forEach(user => {
                const row = tbody.insertRow();
                row.innerHTML = `
                    <td>${user.username}</td>
                    <td>${user.commands.toLocaleString()}</td>
                    <td>${user.last_command ? new Date(user.last_command).toLocaleString() : 'N/A'}</td>
                `;
            });
        }

        async function loadActiveTasks() {
            const res = await fetch('/api/active-tasks');
            const data = await res.json();
            document.getElementById('active-tasks').textContent = (data.tasks || []).length;
        }

        async function loadLogs() {
            const res = await fetch('/api/logs?lines=50');
            const data = await res.json();
            const container = document.getElementById('logs');
            container.innerHTML = (data.logs || [])
                .reverse()
                .map(line => `<div class="log-line">${line}</div>`)
                .join('');
        }

        // Initial load
        loadStats();
        loadCommands();
        loadUsers();
        loadActiveTasks();
        loadLogs();

        // Auto-refresh every 30 seconds
        setInterval(() => {
            loadStats();
            loadActiveTasks();
        }, 30000);
    </script>
</body>
</html>"""
