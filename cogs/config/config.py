from __future__ import annotations

import asyncio
import hashlib
import json
from typing import Annotated, Literal

from tabulate import tabulate

import discord
from cogs.config import method as config_method
from core import Cog, Context, Parrot
from discord.ext import commands
from utilities.converters import convert_bool
from utilities.time import ShortTime

with open(r"cogs/config/events.json", encoding="utf-8", errors="ignore") as f:
    events = json.load(f)


class Configuration(Cog):
    """To config the bot. In the server."""

    def __init__(self, bot: Parrot) -> None:
        self.bot = bot

        self.ON_TESTING = False

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="\N{GEAR}")

    @commands.group(name="config", aliases=["serverconfig"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def config(self, ctx: Context):
        """To config the bot, mod role, prefix, or you can disable the commands and cogs."""
        if not ctx.invoked_subcommand:
            if self.bot.guild_configurations_cache.get(ctx.guild.id):
                data = self.bot.guild_configurations_cache[ctx.guild.id]
            else:
                data = await self.bot.guild_configurations.find_one({"_id": ctx.guild.id})
            role = ctx.guild.get_role(data.get("mod_role", 0))
            mute_role = ctx.guild.get_role(data.get("mute_role", 0))
            suggestion_channel = ctx.guild.get_channel(data.get("suggestion_channel", 0))
            hub = ctx.guild.get_channel(data.get("hub", 0))

            await ctx.reply(
                f"Configuration of this server [server_config]\n\n"
                f"`Prefix  :` **{data['prefix']}**\n"
                f"`ModRole :` **{role.name if role else 'None'} ({data.get('mod_role')})**\n"
                f"`MuteRole:` **{mute_role.name if mute_role else 'None'} ({data.get('mute_role')})**\n"
                f"`Premium :` **{'Enabled' if data.get('premium') else 'Disabled'}**\n"
                f"`Hub     :` **{hub.mention if hub else 'None'} ({data.get('hub')})**\n"
                f"`SuggestionChannel:` **{suggestion_channel.mention if suggestion_channel else 'None'} ({data.get('suggestion_channel')})**\n",
            )

    @config.group(name="opt", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt(self, ctx: Context):
        """To opt in or opt out certain features."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @config_opt.group(name="in", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_in(self, ctx: Context):
        """To opt in certain features of Parrot bot in server."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @config_opt_in.command(name="github", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_in_github(self, ctx: Context):
        """To opt in git link to code block."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"gitlink_enabled": True}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} enabled gitlink to codeblock in this server")

    @config_opt_in.command(name="equation", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_in_equation(self, ctx: Context):
        """To opt in instant equation solver."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"equation_enabled": True}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} enabled instant equation solver in this server")

    @config_opt.group(name="out", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_out(self, ctx: Context):
        """To opt out certain features of Parrot bot in server."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @config_opt_out.command(name="github", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_out_github(self, ctx: Context):
        """To opt out git link to code block."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"gitlink_enabled": False}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} disabled gitlink to codeblock in this server")

    @config_opt_out.command(name="equation", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def config_opt_out_equation(self, ctx: Context):
        """To opt out instant equation solver."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"equation_enabled": False}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} disabled instant equation solver in this server")

    @config.group(name="hub", invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True)
    async def setup_hub(
        self,
        ctx: Context,
    ):
        """To setup Hub like channel."""
        overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
            ctx.guild.default_role: discord.PermissionOverwrite(connect=True, read_messages=True),
            ctx.guild.me: discord.PermissionOverwrite(
                connect=True,
                read_messages=True,
                manage_channels=True,
                manage_permissions=True,
            ),
        }
        cat: discord.CategoryChannel = await ctx.guild.create_category_channel(
            "The Hub",
            reason=f"Action requested by {ctx.author} ({ctx.author.id})",
            overwrites=overwrites,
        )

        channel: discord.VoiceChannel = await ctx.guild.create_voice_channel(
            "Hub - Join to create",
            reason=f"Action requested by {ctx.author} ({ctx.author.id})",
            category=cat,
            user_limit=1,
        )

        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": {"hub": channel.id}})
        await ctx.reply(f"{ctx.author.mention} successfully created {channel.mention}! Enjoy")

    @config.group(name="starboard", aliases=["star"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def starboard(
        self,
        ctx: Context,
    ):
        """To setup the starboard in your server."""
        if ctx.invoked_subcommand:
            return
        try:
            starboard_data = self.bot.guild_configurations_cache[ctx.guild.id]["starboard_config"]
        except KeyError:
            return await self.bot.invoke_help_command(ctx)

        channel: discord.TextChannel | None = ctx.guild.get_channel(starboard_data.get("channel", 0))
        limit: int | None = starboard_data.get("limit")
        is_locked: bool | None = starboard_data.get("is_locked")

        ignore_channel = ", ".join([f"{ctx.guild.get_channel(c)} ({c})" for c in starboard_data.get("ignore_channel", [])])
        max_duration: str | None = starboard_data.get("max_duration")
        can_self_star: bool | None = starboard_data.get("can_self_star")

        return await ctx.reply(
            f"Configuration of this server [starboard]\n\n"
            f"`Channel  :` **{channel.mention if channel else 'None'} ({starboard_data.get('channel')})**\n"
            f"`Limit    :` **{limit}**\n"
            f"`Locked   :` **{is_locked}**\n"
            f"`Ignore   :` **{ignore_channel or 'None'}**\n"
            f"`Duration :` **{max_duration}**\n"
            f"`Self Star:` **{can_self_star}**\n",
        )

    @starboard.command(name="channel")
    @commands.has_permissions(administrator=True)
    async def starboard_channel(self, ctx: Context, *, channel: discord.TextChannel | None = None):
        """To setup the channel."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"starboard_config.channel": channel.id if channel else None}},
        )
        if channel:
            return await ctx.reply(f"{ctx.author.mention} set the starboard channel to {channel.mention}")
        await ctx.send(f"{ctx.author.mention} removed the starboard channel")

    @starboard.command(name="maxage", aliases=["maxduration"])
    @commands.has_permissions(administrator=True)
    async def starboard_max_age(self, ctx: Context, *, duration: ShortTime):
        """To set the max duration."""
        difference = duration.dt.timestamp() - ctx.message.created_at.timestamp()
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"starboard_config.max_duration": difference}},
        )
        await ctx.reply(f"{ctx.author.mention} set the max duration to **{difference}** seconds")

    @starboard.command(name="ignore", aliases=["ignorechannel"])
    @commands.has_permissions(administrator=True)
    async def starboard_add_ignore(self, ctx: Context, *, channel: discord.TextChannel):
        """To add ignore list."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$addToSet": {"starboard_config.ignore_channel": channel.id}},
        )
        await ctx.reply(f"{ctx.author.mention} added {channel.mention} to the ignore list")

    @starboard.command(name="unignore", aliases=["unignorechannel"])
    @commands.has_permissions(administrator=True)
    async def starboard_remove_ignore(self, ctx: Context, *, channel: discord.TextChannel):
        """To remove the channel from ignore list."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$pull": {"starboard_config.ignore_channel": channel.id}},
        )
        await ctx.reply(f"{ctx.author.mention} removed {channel.mention} from the ignore list")

    @starboard.command(name="threshold", aliases=["limit"])
    @commands.has_permissions(administrator=True)
    async def starboard_limit(self, ctx: Context, limit: int = 3):
        """To set the starboard limit."""
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": {"starboard_config.limit": limit}})
        await ctx.reply(f"{ctx.author.mention} set starboard limit to **{limit}**")

    @starboard.command(name="lock", aliases=["locked"])
    @commands.has_permissions(administrator=True)
    async def starboard_lock(self, ctx: Context, toggle: Annotated[bool, convert_bool] = False):
        """To lock the starboard channel."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"starboard_config.is_locked": toggle}},
        )
        await ctx.reply(f"{ctx.author.mention} starboard channel is now {'locked' if toggle else 'unlocked'}")

    @starboard.command(name="selfstar", aliases=["self-star"])
    @commands.has_permissions(administrator=True)
    async def starboard_self_star(self, ctx: Context, *, toggle: Annotated[bool, convert_bool] = False):
        """To allow self star."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"starboard_config.can_self_star": toggle}},
        )
        await ctx.reply(f"{ctx.author.mention} self star is now {'enabled' if toggle else 'disabled'}")

    @config.command(aliases=["prefix"])
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def botprefix(self, ctx: Context, *, arg: str):
        """To set the prefix of the bot. Whatever prefix you passed, will be case sensitive.
        It is advised to keep a symbol as a prefix. Must not greater than 6 chars.
        """
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": {"prefix": arg}})

        await ctx.reply(f"{ctx.author.mention} success! Prefix for **{ctx.guild.name}** is **{arg}**.")

    @config.command()
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def suggestchannel(self, ctx: Context, *, channel: discord.TextChannel | None = None):
        """To configure the suggestion channel. If no channel is provided it will remove the channel."""
        if channel:
            await self.bot.guild_configurations.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"suggestion_channel": channel.id}},
            )
            await ctx.reply(f"{ctx.author.mention} set suggestion channel to {channel.mention}")
            return
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": {"suggestion_channel": None}})
        await ctx.reply(f"{ctx.author.mention} removed suggestion channel")

    @config.command(aliases=["mute-role"])
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def muterole(self, ctx: Context, *, role: discord.Role = None):
        """To set the mute role of the server. By default role with name `Muted` is consider as mute role."""
        post = {"mute_role": role.id if role else None}
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": post})
        if not role:
            return await ctx.reply(f"{ctx.author.mention} mute role reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! Mute role for **{ctx.guild.name}** is **{role.name} ({role.id})**")

    @config.command(aliases=["mod-role"])
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def modrole(self, ctx: Context, *, role: discord.Role = None):
        """To set mod role of the server. People with mod role can accesss the Moderation power of Parrot.
        By default the mod functionality works on the basis of permission.
        """
        post = {"mod_role": role.id if role else None}
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": post})
        if not role:
            return await ctx.reply(f"{ctx.author.mention} mod role reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! Mod role for **{ctx.guild.name}** is **{role.name} ({role.id})**")

    @config.command(aliases=["dj-role"])
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def djrole(self, ctx: Context, *, role: discord.Role = None):
        """To set dj role of the server. People with dj role can accesss the DJ power of Sparklin.
        By default the dj functionality works on the basis of permission that is (Manage Channel).
        """
        post = {"dj_role": role.id if role else None}
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": post})
        if not role:
            return await ctx.reply(f"{ctx.author.mention} dj role reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! DJ role for **{ctx.guild.name}** is **{role.name} ({role.id})**")

    @config.command(aliases=["g-setup", "g_setup"])
    @commands.has_permissions(administrator=True)
    @commands.bot_has_permissions(manage_channels=True, manage_webhooks=True, manage_roles=True)
    @Context.with_type
    async def gsetup(
        self,
        ctx: Context,
        setting: str = None,
        *,
        role: discord.Role | None = None,
    ):
        """This command will connect your server with other servers which then connected to #global-chat must try this once."""
        collection = self.bot.guild_configurations
        if not setting:
            overwrites: dict[discord.Role | discord.Member, discord.PermissionOverwrite] = {
                ctx.guild.default_role: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    read_message_history=True,
                ),
                ctx.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, read_message_history=True),
            }
            channel = await ctx.guild.create_text_channel(
                "global-chat",
                topic="Hmm. Please be calm, be very calm",
                overwrites=overwrites,
            )
            webhook = await channel.create_webhook(
                name="GlobalChat",
                reason=f"Action requested by {ctx.author.name} ({ctx.author.id})",
            )
            await collection.update_one(
                {"_id": ctx.guild.id},
                {
                    "$set": {
                        "global_chat.channel_id": channel.id,
                        "global_chat.webhook": webhook.url,
                        "global_chat.enable": True,
                    },
                },
                upsert=True,
            )
            return await ctx.reply(f"{ctx.author.mention} success! Global chat is now setup {channel.mention}")

        if setting.lower() in {
            "ignore-role",
            "ignore_role",
            "ignorerole",
        }:
            await collection.update_one(
                {"_id": ctx.guild.id},
                {
                    "$addToSet": {"global_chat.ignore_role": role.id if role else None},
                    "$set": {"global_chat.enable": True},
                },
                upsert=True,
            )
            if not role:
                return await ctx.reply(f"{ctx.author.mention} ignore role reseted! or removed")
            await ctx.reply(f"{ctx.author.mention} success! **{role.name} ({role.id})** will be ignored from global chat!")

    @config.group(aliases=["tel"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def telephone(self, ctx: Context):
        """To set the telephone phone line, in the server to call and receive the call from other server."""
        if not ctx.invoked_subcommand:
            data = await self.bot.guild_configurations.find_one({"_id": ctx.guild.id})
            if data:
                role = str(ctx.guild.get_role(data["pingrole"])) if data.get("pingrole") else None
                channel = str(ctx.guild.get_channel(data["channel"])) if data.get("channel") else None
                member = (
                    await self.bot.get_or_fetch_member(ctx.guild, data["memberping"]) if data.get("memberping") else None
                )
                await ctx.reply(
                    f"Configuration of this server [telsetup]\n\n"
                    f"`Channel   :` **{channel}**\n"
                    f"`Pingrole  :` **{role} ({data['pingrole'] or None})**\n"
                    f"`MemberPing:` **{member} ({data['memberping'] or None})**\n"
                    f"`Blocked   :` **{', '.join(data['blocked']) or None}**",
                )

    @telephone.command(name="channel")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def tel_config_channel(self, ctx: Context, *, channel: discord.TextChannel = None):
        """To setup the telephone line in the channel."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"telephone.channel_id": channel.id if channel else None}},
            upsert=True,
        )
        if not channel:
            return await ctx.reply(f"{ctx.author.mention} global telephone line is reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! **#{channel.name}** is now added to global telephone line.")

    @telephone.command(name="pingrole")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def tel_config_pingrole(self, ctx: Context, *, role: discord.Role = None):
        """To add the ping role. If other server call your server. Then the role will be pinged if set any."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"telephone.ping_role": role.id if role else None}},
            upsert=True,
        )
        if not role:
            return await ctx.reply(f"{ctx.author.mention} ping role reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! **@{role.name}** will be now pinged when someone calls your server.")

    @telephone.command(name="memberping")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def tel_config_memberping(self, ctx: Context, *, member: discord.Member = None):
        """To add the ping role. If other server call your server. Then the role will be pinged if set any."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"telephone.member_ping": member.id if member else None}},
            upsert=True,
        )
        if not member:
            return await ctx.reply(f"{ctx.author.mention} member ping reseted! or removed")
        await ctx.reply(f"{ctx.author.mention} success! **@{member}** will be now pinged when someone calls your server.")

    @telephone.command(name="block")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def tel_config_block(self, ctx: Context, *, server: discord.Guild | int):
        """There are people who are really anonying, you can block them."""
        if server is ctx.guild:
            return await ctx.reply(f"{ctx.author.mention} can't block your own server")

        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$addToSet": {"telephone.blocked": server.id if isinstance(server, discord.Guild) else server}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} success! blocked: **{server.name}**")

    @telephone.command(name="unblock")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def tel_config_unblock(self, ctx: Context, *, server: discord.Guild):
        """Now they understood their mistake. You can now unblock them."""
        if server is ctx.guild:
            return await ctx.reply(f"{ctx.author.mention} ok google, let the server admin get some rest")
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$pull": {"telephone.blocked": server.id}},
            upsert=True,
        )
        await ctx.reply(f"{ctx.author.mention} Success! unblocked: {server.id}")

    @config.group(name="command", aliases=["cmd"])
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def cmdconfig(self, ctx: Context):
        """Command Management of the server."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @cmdconfig.command()
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def enable(
        self,
        ctx: Context,
        command: Annotated[str, commands.clean_content],
        *,
        target: discord.TextChannel | discord.VoiceChannel | discord.Thread | discord.Role | None = None,
    ):
        """To enable the command."""
        cmd = self.bot.get_command(command)
        cog = self.bot.get_cog(command)
        if cmd is not None:
            await config_method._enable(ctx, cmd.qualified_name, target)
        elif cog is not None:
            await config_method._enable(ctx, cog.qualified_name, target)
        elif command == "all":
            await config_method._enable(ctx, "all", target)
        else:
            await ctx.send(f"{ctx.author.mention} {command} is nither command nor any category")

    @cmdconfig.command()
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def disable(
        self,
        ctx: Context,
        command: Annotated[str, commands.clean_content],
        *,
        target: discord.TextChannel | discord.VoiceChannel | discord.Thread | discord.Role | None = None,
    ):
        """To disable the command."""
        cmd = self.bot.get_command(command)
        cog = self.bot.get_cog(command)
        if cmd is not None:
            await config_method._disable(ctx, cmd.qualified_name, target)
        elif cog is not None:
            await config_method._disable(ctx, cog.qualified_name, target)
        elif command == "all":
            await config_method._disable(ctx, "all", target)
        else:
            await ctx.send(f"{ctx.author.mention} {command} is nither command nor any category")

    @cmdconfig.command(name="list")
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def cmd_config_list(self, ctx: Context, *, cmd: str):
        """To view what all configuation are being made with command."""
        data = self.bot.guild_configurations_cache[ctx.guild.id].get("cmd_config", {})
        CMD_GLOBAL_ENABLE_ = f"CMD_GLOBAL_ENABLE_{cmd}".upper()
        CMD_ROLE_ENABLE_ = f"CMD_ROLE_ENABLE_{cmd}".upper()
        CMD_ROLE_DISABLE_ = f"CMD_ROLE_DISABLE_{cmd}".upper()
        CMD_CHANNEL_ENABLE_ = f"CMD_CHANNEL_ENABLE_{cmd}".upper()
        CMD_CHANNEL_DISABLE_ = f"CMD_CHANNEL_DISABLE_{cmd}".upper()
        CMD_CATEGORY_ENABLE_ = f"CMD_CATEGORY_ENABLE_{cmd}".upper()
        CMD_CATEGORY_DISABLE_ = f"CMD_CATEGORY_DISABLE_{cmd}".upper()
        CMD_ENABLE_ = f"CMD_ENABLE_{cmd}".upper()

        embed = (
            discord.Embed(
                title=f"Command Configuration for {cmd}",
                description=f"**Global Enable**: {data.get(CMD_GLOBAL_ENABLE_, 'N/A')}\n",
            )
            .add_field(
                name="Role Enable",
                value="<@&" + ">, <@&".join(data.get(CMD_ROLE_ENABLE_, [0])) + ">" if data.get(CMD_ROLE_ENABLE_) else "N/A",
                inline=False,
            )
            .add_field(
                name="Role Disable",
                value="<@&" + ">, <@&".join(data.get(CMD_ROLE_DISABLE_, [0])) + ">"
                if data.get(CMD_ROLE_DISABLE_)
                else "N/A",
                inline=False,
            )
            .add_field(
                name="Channel Enable",
                value="<#" + ">, <#".join(data.get(CMD_CHANNEL_ENABLE_, [0])) + ">"
                if data.get(CMD_CHANNEL_ENABLE_)
                else "N/A",
                inline=False,
            )
            .add_field(
                name="Channel Disable",
                value="<#" + ">, <#".join(data.get(CMD_CHANNEL_DISABLE_, [0])) + ">"
                if data.get(CMD_CHANNEL_DISABLE_)
                else "N/A",
                inline=False,
            )
            .add_field(
                name="Category Enable",
                value="<#" + ">, <#".join(data.get(CMD_CATEGORY_ENABLE_, [0])) + ">"
                if data.get(CMD_CATEGORY_ENABLE_)
                else "N/A",
                inline=False,
            )
            .add_field(
                name="Category Disable",
                value="<#" + ">, <#".join(data.get(CMD_CATEGORY_DISABLE_, [0])) + ">"
                if data.get(CMD_CATEGORY_DISABLE_)
                else "N/A",
                inline=False,
            )
            .add_field(
                name="Command Enable",
                value=data.get(CMD_ENABLE_, "N/A"),
                inline=False,
            )
        )
        await ctx.reply(embed=embed)

    @cmdconfig.command()
    @commands.has_permissions(administrator=True)
    @Context.with_type
    async def clear(self, ctx: Context):
        """To clear all overrides."""
        await self.bot.guild_configurations.update_one({"_id": ctx.guild.id}, {"$set": {"cmd_config": {}}})
        await ctx.send(f"{ctx.author.mention} reseted everything!")

    @config.group(name="serverstats", aliases=["sstats"], invoke_without_command=True)
    @commands.has_permissions(administrator=True)
    async def serverstats(self, ctx: Context):
        """Creates Fancy counters that everyone can see."""
        if ctx.invoked_subcommand is not None:
            return
        try:
            server_stats = self.bot.guild_configurations_cache[ctx.guild.id]["stats_channels"]
        except KeyError:
            return await self.bot.invoke_help_command(ctx)
        table = []
        for key, value in server_stats.items():
            if key != "role":
                chn = self.bot.get_channel(value["channel_id"]) if value.get("channel_id") else 0
                table.append(
                    [
                        key.title(),
                        f"#{chn.name}" if chn else "None",
                        value.get("channel_type"),
                        value.get("template"),
                    ],
                )
        table_role = []
        for _role in server_stats.get("role", {}):
            role = ctx.guild.get_role(_role.get("role_id", 0))
            channel = ctx.guild.get_channel(_role.get("channel_id", 0))
            template = _role.get("template")
            channel_type = _role.get("channel_type")
            table_role.append(
                [
                    role.name if role else "None",
                    channel.name if channel else "None",
                    channel_type,
                    template,
                ],
            )
        await ctx.send(
            f"""```
{str(tabulate(table, headers=["Name", "Channel", "Type", "Template"], tablefmt="pretty"))}
``````
{str(tabulate(table_role, headers=["Role", "Channel", "Type", "Template"], tablefmt="pretty"))}
```""",
        )

    @serverstats.command(name="create")
    @commands.has_permissions(administrator=True)
    async def serverstats_create(
        self,
        ctx: Context,
    ):
        """Creates a server stats counter."""
        COUNTER_PAYLOAD = {
            "bots": len([m for m in ctx.guild.members if m.bot]),
            "members": len(ctx.guild.members),
            "channels": len(ctx.guild.channels),
            "roles": len(ctx.guild.roles),
            "emojis": len(ctx.guild.emojis),
            "text": ctx.guild.text_channels,
            "voice": ctx.guild.voice_channels,
            "categories": len(ctx.guild.categories),
        }
        AVAILABLE_COUNTER = [
            "bots",
            "members",
            "channels",
            "voice",
            "text",
            "categories",
            "emojis",
            "roles",
            "role",
        ]
        AVAILABLE_TYPE = [
            "voice",
            "text",
            "category",
        ]
        PAYLOAD = {}
        PAYLOAD_R = {}
        OP = "$set"

        QUES = [
            f"What type of counter you want to setup? (`{'`, `'.join(AVAILABLE_COUNTER)}`)",
            f"What type of channel you want? (`{'`, `'.join(AVAILABLE_TYPE)}`)",
            r"What should be the format of the channel? Example: `Total Channels {}`, `{} Roles in total`. Only the `{}` will be replaced with the counter value.",
        ]

        async def wait_for_response() -> str:
            def check(m: discord.Message) -> bool:
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg: discord.Message = await self.bot.wait_for("message", check=check, timeout=60)
                return msg.content.lower()
            except asyncio.TimeoutError as e:
                err = f"{ctx.author.mention} You took too long to respond!"
                raise commands.BadArgument(err) from e

        await ctx.send(f"{ctx.author.mention} {QUES[0]}")
        counter = await wait_for_response()

        if counter not in AVAILABLE_COUNTER:
            return await ctx.error(
                f"{ctx.author.mention} invalid counter! Available counter: `{'`, `'.join(AVAILABLE_COUNTER)}`",
            )
        if counter == "role":
            OP = "$addToSet"
            await ctx.send(f"{ctx.author.mention} Enter the role name/ID or you can even mention it")
            role = await wait_for_response()
            try:
                role = await commands.RoleConverter().convert(ctx, role)
            except commands.BadArgument:
                return await ctx.error(f"{ctx.author.mention} invalid role! Please enter a valid role name/ID")
            else:
                PAYLOAD_R["role_id"] = role.id
                COUNTER_PAYLOAD["role"] = len(role.members)

        await ctx.send(f"{ctx.author.mention} {QUES[1]}")
        channel_type = await wait_for_response()
        if channel_type not in AVAILABLE_TYPE:
            return await ctx.error(
                f"{ctx.author.mention} invalid channel type! Available channel type: `{'`, `'.join(AVAILABLE_TYPE)}`",
            )
        PAYLOAD[f"{counter}.channel_type"] = channel_type
        PAYLOAD_R["channel_type"] = channel_type

        await ctx.send(f"{ctx.author.mention} {QUES[2]}")
        _format = await wait_for_response()
        if r"{}" not in _format:
            return await ctx.error(f"{ctx.author.mention} invalid format! Please provide a valid format.")
        PAYLOAD[f"{counter}.template"] = _format
        PAYLOAD_R["template"] = _format

        channel = 0
        try:
            if channel_type == "text":
                channel = await ctx.guild.create_text_channel(
                    _format.format(COUNTER_PAYLOAD[counter.lower()]),
                    position=0,
                    reason=f"Action requested by {ctx.author} ({ctx.author.id})",
                )
            elif channel_type == "voice":
                channel = await ctx.guild.create_voice_channel(
                    _format.format(COUNTER_PAYLOAD[counter.lower()]),
                    position=0,
                    reason=f"Action requested by {ctx.author} ({ctx.author.id})",
                )
            elif channel_type == "category":
                channel = await ctx.guild.create_category(
                    _format.format(COUNTER_PAYLOAD[counter.lower()]),
                    position=0,
                    reason=f"Action requested by {ctx.author} ({ctx.author.id})",
                )
        except (ValueError, IndexError):
            return await ctx.error(f"{ctx.author.mention} invalid format! Please provide a valid format.")
        PAYLOAD[f"{counter}.channel_id"] = channel.id if isinstance(channel, discord.abc.Messageable) else channel
        PAYLOAD_R["channel_id"] = channel.id if isinstance(channel, discord.abc.Messageable) else channel

        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {
                OP: {f"stats_channels.{k}": v for k, v in PAYLOAD.items()}
                if counter != "role"
                else {"stats_channels.role": PAYLOAD_R},
            },
            upsert=True,
        )

        await ctx.send(f"{ctx.author.mention} counter created at #{channel.name} ({channel.mention})")

    @serverstats.command(name="delete")
    @commands.has_permissions(administrator=True)
    async def serverstats_delete(
        self,
        ctx: Context,
        counter: str,
    ):
        """Deletes a server stats counter."""
        AVAILABLE = [
            "bots",
            "members",
            "channels",
            "voice",
            "text",
            "categories",
            "emojis",
            "roles",
            "role",
        ]
        if counter.lower() not in AVAILABLE:
            return await ctx.error(f"{ctx.author.mention} invalid counter! Available counter: `{'`, `'.join(AVAILABLE)}`")

        async def wait_for_response() -> str | None:
            def check(m: discord.Message) -> bool:
                return m.author == ctx.author and m.channel == ctx.channel

            try:
                msg: discord.Message = await ctx.wait_for("message", check=check, timeout=60)
                return msg.content.lower()
            except asyncio.TimeoutError as e:
                err = f"{ctx.author.mention} You took too long to respond!"
                raise commands.BadArgument(err) from e

        if counter == "role":
            await ctx.send(f"{ctx.author.mention} Enter the role name/ID or you can even mention it")
            role = await wait_for_response()
            try:
                role = await commands.RoleConverter().convert(ctx, role)
            except commands.BadArgument:
                return await ctx.error(f"{ctx.author.mention} invalid role! Please enter a valid role name/ID")
            else:
                await self.bot.guild_configurations.update_one(
                    {"_id": ctx.guild.id},
                    {"$pull": {"stats_channels.role": {"role_id": role.id}}},
                    upsert=True,
                )
                return await ctx.error(f"{ctx.author.mention} counter deleted for role {role.name} ({role.mention})")

        if await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id, "stats_channels": {"$exists": True}},
            {
                "$set": {
                    f"stats_channels.{counter}.channel_id": None,
                    f"stats_channels.{counter}.channel_type": None,
                    f"stats_channels.{counter}.template": None,
                },
            },
        ):
            await ctx.send(f"{ctx.author.mention} counter deleted")

    @commands.group(invoke_without_command=True)
    async def optout(self, ctx: Context):
        """Opt-out to the certain configuration."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @optout.command(name="gitlink")
    async def optout_gitlink(self, ctx: Context, g: Literal["--global"]):
        """Opt-out for gitlink to codeblock."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"opts.gitlink": False}},
            upsert=True,
        )
        await ctx.send(f"{ctx.author.mention} You have opted-out to the use of gitlink in codeblocks.")

    @optout.command(name="equation")
    async def optout_equation(self, ctx: Context, g: Literal["--global"]):
        """Opt-out for equation usage."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"opts.equation": False}},
            upsert=True,
        )
        await ctx.send(f"{ctx.author.mention} You have opted-out to the use of equations.")

    @commands.group(invoke_without_command=True)
    async def optin(self, ctx: Context):
        """Opt-in to the certain configuration."""
        if ctx.invoked_subcommand is None:
            await self.bot.invoke_help_command(ctx)

    @optin.command(name="gitlink")
    async def optin_gitlink(self, ctx: Context, g: Literal["--global"]):
        """Opt-in for gitlink to codeblock."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"opts.equation": True}},
            upsert=True,
        )
        await ctx.send(f"{ctx.author.mention} You have opted-in to the use of gitlink in codeblocks.")

    @optin.command(name="equation")
    async def optin_equation(self, ctx: Context, g: Literal["--global"]):
        """Opt-in for equation usage."""
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"opts.equation": False}},
            upsert=True,
        )
        await ctx.send(f"{ctx.author.mention} You have opted-out to the use of equations.")

    @commands.command(hidden=True)
    @commands.has_permissions(administrator=True)
    async def activate(self, ctx: Context, code: str):
        """To upgrade the server to premium."""
        code_hash = hashlib.sha256(code.encode("utf-8")).hexdigest()
        if data := await self.bot.extra_collections.find_one({"hash": code_hash}):
            if data.get("uses", 0) > data.get("limit", 0):
                await ctx.send(f"{ctx.author.mention} This code has been used up. Please ask for new code in support server")
                return

            if data.get("guild", None) is not None and data["guild"] != ctx.guild.id:
                await ctx.send(
                    f"{ctx.author.mention} This code is not for this server. Please ask for new code in support server",
                )
                return

            if data.get("expiry", None) is not None and data["expiry"] < int(discord.utils.utcnow().timestamp()):
                await ctx.send(f"{ctx.author.mention} This code has expired. Please ask for new code in support server")
                return

            res = await ctx.prompt(f"{ctx.author.mention} are you sure you want to upgrade to premium?")
            if not res:
                return await ctx.error(f"{ctx.author.mention} cancelled.")
            await self.bot.extra_collections.update_one({"hash": code_hash}, {"$inc": {"uses": 1}}, upsert=True)
            await self.bot.guild_configurations.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"premium": True}},
                upsert=True,
            )
            await ctx.send(f"{ctx.author.mention} upgraded to premium :tada:")
        else:
            await ctx.send(f"{ctx.author.mention} This code is invalid. Please ask for new code in support server")

    @config.command(name="auditlog", aliases=["auditlogs"])
    @commands.bot_has_permissions(manage_channels=True)
    @commands.has_permissions(administrator=True)
    async def config_auditlog(self, ctx: Context, channel: discord.TextChannel = None):
        """Set the auditlog channel."""
        if channel is None:
            await self.bot.guild_configurations.update_one(
                {"_id": ctx.guild.id},
                {"$set": {"auditlog": None}},
                upsert=True,
            )
            return await ctx.send(f"{ctx.author.mention} auditlog channel deleted")

        webhook = await channel.create_webhook(name="Auditlog")
        await self.bot.guild_configurations.update_one(
            {"_id": ctx.guild.id},
            {"$set": {"auditlog": webhook.url}},
            upsert=True,
        )
        await ctx.send(f"{ctx.author.mention} auditlog channel set to {channel.mention}")

    @Cog.listener()
    async def on_command_completion(self, ctx: Context):
        if ctx.cog and ctx.cog.qualified_name == "Configuration":
            self.bot.update_server_config_cache.start(ctx.guild.id)
