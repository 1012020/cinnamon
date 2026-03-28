import discord
from discord.ext import commands
import os
import json
from datetime import datetime
import config
from cogs.utils.helpers import send_status, send_error

APPLICATIONS_FILE = "data/applications.json"
ROLE_ID_ON_ACCEPT = 1458951498615750888

class ApplicationCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        try:
            os.makedirs(os.path.dirname(APPLICATIONS_FILE), exist_ok=True)
        except Exception:
            pass

    def _load_apps(self):
        if os.path.exists(APPLICATIONS_FILE):
            try:
                with open(APPLICATIONS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return []
        return []

    def _save_apps(self, apps):
        try:
            with open(APPLICATIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(apps, f, indent=2)
        except Exception:
            pass

    @commands.command(name='apply')
    async def apply(self, ctx):
        """Start an application: asks why you want to join cinnamon."""
        try:
            # Ensure we can DM the user
            dm = ctx.author.dm_channel
            if dm is None:
                try:
                    dm = await ctx.author.create_dm()
                except discord.Forbidden:
                    await send_status(ctx, "error: couldn't DM you. please enable DMs and try again.")
                    return
            # Prevent repeat applications
            apps = self._load_apps()
            if any(a.get('user_id') == ctx.author.id for a in apps):
                try:
                    await send_status(ctx, "error: you have already applied and cannot apply again.")
                except Exception:
                    pass
                try:
                    await dm.send("you have already applied and cannot apply again.")
                except Exception:
                    pass
                return

            # Confirmation step: require explicit 'yes' before starting questions
            confirm = (
                "do you understand that you get only get to apply once? after that you cannot apply, "
                "please be concise with your answers.\n\ntype \"yes\" if you understand"
            )
            try:
                await dm.send(confirm)
            except Exception:
                await send_status(ctx, "error: couldn't DM you. please enable DMs and try again.")
                return

            def check(m):
                return m.author.id == ctx.author.id and isinstance(m.channel, discord.DMChannel)

            try:
                resp_confirm = await self.bot.wait_for('message', check=check, timeout=120)
                if resp_confirm.content.strip().lower() != 'yes':
                    await dm.send("application cancelled: you did not confirm with 'yes'.")
                    return
            except Exception:
                await dm.send("timed out. please run `!apply` again when ready.")
                return

            # Notify channel that DM form has been started
            if ctx.guild is not None:
                try:
                    await send_status(ctx, "i've sent you a DM with the application form.")
                except Exception:
                    pass

            # Ask the requested questions
            q1 = "why do you want to join cinnamon?"
            q2 = "where did you hear about cinnamon?"
            q3 = "who invited you to cinnamon, and why?"
            q4 = "what is cinnamon?"

            await dm.send(q1)

            try:
                resp = await self.bot.wait_for('message', check=check, timeout=300)
                reason = resp.content.strip()
                if not reason:
                    await dm.send("application cancelled: empty response.")
                    return
            except Exception:
                await dm.send("timed out. please run `!apply` again when ready.")
                return

            await dm.send(q2)
            try:
                resp2 = await self.bot.wait_for('message', check=check, timeout=120)
                heard_from = resp2.content.strip()
            except Exception:
                heard_from = "<no response>"

            await dm.send(q3)
            try:
                resp3 = await self.bot.wait_for('message', check=check, timeout=180)
                invited_by = resp3.content.strip()
            except Exception:
                invited_by = "<no response>"

            await dm.send(q4)
            try:
                resp4 = await self.bot.wait_for('message', check=check, timeout=180)
                what_is = resp4.content.strip()
            except Exception:
                what_is = "<no response>"


            apps = self._load_apps()
            next_id = 1
            if apps:
                try:
                    max_id = max((a.get("id", 0) for a in apps), default=0)
                    next_id = max_id + 1
                except Exception:
                    next_id = len(apps) + 1

            app = {
                "id": next_id,
                "user_id": ctx.author.id,
                "username": str(ctx.author),
                "created_at": datetime.utcnow().isoformat(),
                "reason": reason,
                "heard_from": heard_from,
                "invited_by": invited_by,
                "what_is": what_is,
                "status": "pending"
            }
            apps.append(app)
            self._save_apps(apps)

            await dm.send("your application has been submitted for review.")
        except Exception as e:
            await send_error(ctx, e)

    @commands.command(name='listapps')
    async def list_apps(self, ctx):
        """Owner-only: list pending applications."""
        if ctx.author.id != config.OWNER_ID:
            await send_status(ctx, "error: owner only.")
            return
        apps = self._load_apps()
        pending = [a for a in apps if a.get('status') == 'pending']
        if not pending:
            await send_status(ctx, "no pending applications.")
            return
        lines = [f"#{a['id']} - {a['username']} - {a['created_at']}" for a in pending]
        await send_status(ctx, "pending applications:\n" + "\n".join(lines))

    @commands.command(name='showapp')
    async def show_app(self, ctx, app_id: int = None):
        """Owner-only: show full application."""
        if ctx.author.id != config.OWNER_ID:
            await send_status(ctx, "error: owner only.")
            return
        if app_id is None:
            await send_status(ctx, "provide application id. use !listapps to see ids.")
            return
        apps = self._load_apps()
        app = next((a for a in apps if a.get('id') == app_id), None)
        if not app:
            await send_status(ctx, "application not found.")
            return
        embed = discord.Embed(title=f"Application #{app['id']}", color=0xE1F6FF)
        embed.add_field(name="applicant", value=f"{app['username']} ({app['user_id']})", inline=False)
        embed.add_field(name="submitted", value=app['created_at'], inline=False)
        embed.add_field(name="why", value=app.get('reason',''), inline=False)
        embed.add_field(name="where heard", value=app.get('heard_from',''), inline=False)
        embed.add_field(name="invited (who + why)", value=app.get('invited_by',''), inline=False)
        embed.add_field(name="what is cinnamon", value=app.get('what_is',''), inline=False)
        embed.add_field(name="status", value=app.get('status','pending'), inline=False)
        await send_status(ctx, embed=embed)

    async def review_application(self, app_id: int, decision: str, reviewer_name: str = None):
        """Programmatic helper: review an application (accept/reject).

        Returns a dict with success/status info.
        """
        try:
            apps = self._load_apps()
            app = next((a for a in apps if a.get('id') == app_id), None)
            if not app:
                return {"success": False, "error": "application not found"}
            if app.get('status') != 'pending':
                return {"success": False, "error": f"already {app.get('status')}"}

            app['status'] = 'accepted' if decision == 'accept' else 'rejected'
            app['reviewed_by'] = reviewer_name or 'web'
            app['reviewed_at'] = datetime.utcnow().isoformat()
            self._save_apps(apps)

            # notify applicant and attempt to grant role if accepted
            try:
                user = await self.bot.fetch_user(app['user_id'])
                if decision == 'accept':
                    added = False
                    for guild in self.bot.guilds:
                        member = guild.get_member(app['user_id'])
                        if member:
                            role = guild.get_role(ROLE_ID_ON_ACCEPT)
                            if role:
                                try:
                                    await member.add_roles(role)
                                    added = True
                                except Exception:
                                    pass
                    try:
                        if added:
                            await user.send(f"your application was accepted you've been given access.")
                        else:
                            await user.send(f"your application was accepted. please contact staff to receive the role.")
                    except Exception:
                        pass
                else:
                    try:
                        await user.send(f"your application was not accepted. thanks for applying.")
                    except Exception:
                        pass
            except Exception:
                pass

            return {"success": True, "status": app['status']}
        except Exception as e:
            return {"success": False, "error": str(e)}

    @commands.command(name='decideapp')
    async def decide_app(self, ctx, app_id: int = None, decision: str = None):
        """Owner-only: decide an application: accept or reject"""
        if ctx.author.id != config.OWNER_ID:
            await send_status(ctx, "error: owner only.")
            return
        if app_id is None or decision is None:
            await send_status(ctx, "usage: !decideapp <id> <accept|reject>")
            return
        decision = decision.lower()
        if decision not in ('accept', 'reject'):
            await send_status(ctx, "decision must be 'accept' or 'reject'.")
            return
        # delegate to reusable review method
        result = await self.review_application(app_id, decision, reviewer_name=str(ctx.author))
        if result.get('success'):
            await send_status(ctx, f"application #{app_id} {result.get('status')}.")
        else:
            await send_status(ctx, f"error: {result.get('error')}")

async def setup(bot):
    await bot.add_cog(ApplicationCog(bot))
