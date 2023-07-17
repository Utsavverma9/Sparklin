from __future__ import annotations

import io
from itertools import zip_longest
from typing import Annotated, Any, Dict, Optional, Union

import discord
from core import Cog, Context, Parrot
from discord.ext import commands
from utilities.checks import is_mod
from utilities.formats import TabularData

REACTION_EMOJI = ["\N{UPWARDS BLACK ARROW}", "\N{DOWNWARDS BLACK ARROW}"]


OTHER_REACTION = {
    "INVALID": {"emoji": "\N{WARNING SIGN}", "color": 0xFFFFE0},
    "ABUSE": {"emoji": "\N{DOUBLE EXCLAMATION MARK}", "color": 0xFFA500},
    "INCOMPLETE": {"emoji": "\N{WHITE QUESTION MARK ORNAMENT}", "color": 0xFFFFFF},
    "DECLINE": {"emoji": "\N{CROSS MARK}", "color": 0xFF0000},
    "APPROVED": {"emoji": "\N{WHITE HEAVY CHECK MARK}", "color": 0x90EE90},
    "DUPLICATE": {"emoji": "\N{HEAVY EXCLAMATION MARK SYMBOL}", "color": 0xDDD6D5},
}


class Suggestions(Cog):
    """For making the suggestion, which then then voted on by the community."""

    def __init__(self, bot: Parrot) -> None:
        self.bot = bot
        self.message: Dict[int, Dict[str, Any]] = {}

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="\N{SPEECH BALLOON}")

    async def __fetch_suggestion_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        try:
            ch_id: Optional[int] = self.bot.guild_configurations_cache[guild.id]["suggestion_channel"]
        except KeyError as e:
            raise commands.BadArgument("No suggestion channel is setup") from e
        else:
            if not ch_id:
                raise commands.BadArgument("No suggestion channel is setup")
            ch: Optional[discord.TextChannel] = self.bot.get_channel(ch_id)  # type: ignore
            if ch is None:
                await self.bot.wait_until_ready()
                ch: discord.TextChannel = await self.bot.fetch_channel(ch_id)  # type: ignore

            return ch

    async def get_or_fetch_message(
        self, msg_id: int, *, guild: discord.Guild, channel: discord.TextChannel = None
    ) -> Optional[discord.Message]:
        try:
            self.message[msg_id]
        except KeyError:
            if channel is None:
                try:
                    channel_id = self.bot.guild_configurations_cache[guild.id]["suggestion_channel"]
                except KeyError as e:
                    raise commands.BadArgument("No suggestion channel is setup") from e
            msg = await self.__fetch_message_from_channel(message=msg_id, channel=self.bot.get_channel(channel_id))  # type: ignore
        else:
            msg = self.message[msg_id]["message"]

        return msg if msg and msg.author.id == self.bot.user.id else None

    async def __fetch_message_from_channel(self, *, message: int, channel: discord.TextChannel):
        async for msg in channel.history(
            limit=1,
            before=discord.Object(message + 1),
            after=discord.Object(message - 1),
        ):
            payload = {
                "message_author": msg.author,
                "message": msg,
                "message_downvote": self.__get_emoji_count_from__msg(msg, emoji="\N{DOWNWARDS BLACK ARROW}"),
                "message_upvote": self.__get_emoji_count_from__msg(msg, emoji="\N{UPWARDS BLACK ARROW}"),
            }
            self.message[message] = payload
            return msg

    def __get_emoji_count_from__msg(
        self,
        msg: discord.Message,
        *,
        emoji: Union[discord.Emoji, discord.PartialEmoji, str],
    ):
        for reaction in msg.reactions:
            if str(reaction.emoji) == str(emoji):
                return reaction.count

    async def __suggest(
        self,
        content: Optional[str] = None,
        *,
        embed: discord.Embed,
        ctx: Context,
        file: Optional[discord.File] = None,
    ) -> Optional[discord.Message]:
        channel: Optional[discord.TextChannel] = await self.__fetch_suggestion_channel(ctx.guild)
        if channel is None:
            raise commands.BadArgument(f"{ctx.author.mention} error fetching suggestion channel")
        file = file or discord.utils.MISSING
        msg: discord.Message = await channel.send(content, embed=embed, file=file)

        await ctx.bulk_add_reactions(msg, *REACTION_EMOJI)
        thread = await msg.create_thread(name=f"Suggestion {ctx.author}")

        payload = {
            "message_author": msg.author,
            "message_downvote": 0,
            "message_upvote": 0,
            "message": msg,
            "thread": thread.id,
        }
        self.message[msg.id] = payload
        return msg

    async def __notify_on_suggestion(self, ctx: Context, *, message: Optional[discord.Message]) -> None:
        if not message:
            return

        jump_url: str = message.jump_url
        _id: int = message.id
        content = (
            f"{ctx.author.mention} your suggestion being posted.\n"
            f"To delete the suggestion type: `{ctx.clean_prefix or await ctx.bot.get_guild_prefixes(ctx.guild.id)}suggest delete {_id}`\n"
            f"> {jump_url}"
        )
        try:
            await ctx.author.send(
                content,
                view=ctx.send_view(),
            )
        except discord.Forbidden:
            pass

    async def __notify_user(
        self,
        ctx: Context,
        user: Optional[discord.Member] = None,
        *,
        message: discord.Message,
        remark: str,
    ) -> None:
        if user is None:
            return

        remark = remark or "No remark was given"

        content = (
            f"{user.mention} your suggestion of ID: {message.id} had being updated.\n"
            f"By: {ctx.author} (`{ctx.author.id}`)\n"
            f"Remark: {remark}\n"
            f"> {message.jump_url}"
        )
        try:
            await user.send(
                content,
                view=ctx.send_view(),
            )
        except discord.Forbidden:
            pass

    @commands.group(aliases=["suggestion"], invoke_without_command=True)
    @commands.cooldown(1, 60, commands.BucketType.member)
    @commands.bot_has_permissions(embed_links=True, create_public_threads=True)
    async def suggest(self, ctx: Context, *, suggestion: Annotated[str, commands.clean_content]):
        """Suggest something. Abuse of the command may result in required mod actions"""

        if not ctx.invoked_subcommand:
            embed = discord.Embed(description=suggestion, timestamp=ctx.message.created_at, color=0xADD8E6)
            embed.set_author(name=str(ctx.author), icon_url=ctx.author.display_avatar.url)
            embed.set_footer(
                text=f"Author ID: {ctx.author.id}",
                icon_url=getattr(ctx.guild.icon, "url", ctx.author.display_avatar.url),
            )

            file: Optional[discord.File] = None

            if ctx.message.attachments and (
                ctx.message.attachments[0].url.lower().endswith(("png", "jpeg", "jpg", "gif", "webp"))
            ):
                _bytes = await ctx.message.attachments[0].read(use_cached=True)
                file = discord.File(io.BytesIO(_bytes), "image.jpg")
                embed.set_image(url="attachment://image.jpg")

            msg = await self.__suggest(ctx=ctx, embed=embed, file=file)
            await self.__notify_on_suggestion(ctx, message=msg)
            await ctx.message.delete(delay=0)

    @suggest.command(name="delete")
    @commands.cooldown(1, 60, commands.BucketType.member)
    @commands.bot_has_permissions(read_message_history=True)
    async def suggest_delete(self, ctx: Context, *, message_id: int):
        """To delete the suggestion you suggested"""

        msg: Optional[discord.Message] = await self.get_or_fetch_message(message_id, guild=ctx.guild)
        if not msg:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{message_id}`. Probably already deleted, or `{message_id}` is invalid"
            )

        if ctx.channel.permissions_for(ctx.author).manage_messages:
            await msg.delete(delay=0)
            await ctx.send(f"{ctx.author.mention} Done", delete_after=5)
            return

        if int(msg.embeds[0].footer.text.split(":")[1]) != ctx.author.id:  # type: ignore
            return await ctx.send(f"{ctx.author.mention} You don't own that 'suggestion'")

        await msg.delete(delay=0)
        await ctx.send(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="stats", hidden=True)
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def suggest_status(self, ctx: Context, *, message_id: int):
        """To get the statistics os the suggestion"""

        msg: Optional[discord.Message] = await self.get_or_fetch_message(message_id, guild=ctx.guild)
        if not msg:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{message_id}`. Probably already deleted, or `{message_id}` is invalid"
            )
        PAYLOAD: Dict[str, Any] = self.message[msg.id]

        table = TabularData()

        upvoter = [PAYLOAD["message_upvote"]]
        downvoter = [PAYLOAD["message_downvote"]]

        table.set_columns(["Upvote", "Downvote"])
        ls = list(zip_longest(upvoter, downvoter, fillvalue=""))
        table.add_rows(ls)

        embed = discord.Embed(title=f"Suggestion Statistics of message ID: {message_id}")
        embed.description = f"```\n{table.render()}```"

        if msg.content:
            embed.add_field(name="Flagged", value=msg.content)
        await ctx.send(content=msg.jump_url, embed=embed)

    @suggest.command(name="resolved")
    @commands.bot_has_guild_permissions(manage_threads=True)
    @commands.cooldown(1, 60, commands.BucketType.member)
    async def suggest_resolved(self, ctx: Context, *, thread_id: int):
        """To mark the suggestion as resolved"""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(thread_id, guild=ctx.guild)

        if int(msg.embeds[0].footer.text.split(":")[1]) != ctx.author.id:  # type: ignore
            return await ctx.send(f"{ctx.author.mention} You don't own that 'suggestion'")

        thread: discord.Thread = await self.bot.getch(ctx.guild.get_channel, ctx.guild.fetch_channel, thread_id)
        if not msg or not thread:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{thread_id}`. Probably already deleted, or `{thread_id}` is invalid"
            )
        await thread.edit(
            archived=True,
            locked=True,
            reason=f"Suggestion resolved by {ctx.author} ({ctx.author.id})",
        )
        await ctx.send(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="note", aliases=["remark"])
    @commands.check_any(commands.has_permissions(manage_messages=True), is_mod())
    async def add_note(self, ctx: Context, message_id: int, *, remark: str):
        """To add a note in suggestion embed"""
        msg: Optional[discord.Message] = await self.get_or_fetch_message(message_id, guild=ctx.guild)
        if not msg:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{message_id}`. Probably already deleted, or `{message_id}` is invalid"
            )

        embed: discord.Embed = msg.embeds[0]
        embed.clear_fields()
        embed.add_field(name="Remark", value=remark[:250])
        new_msg = await msg.edit(content=msg.content, embed=embed)
        self.message[new_msg.id]["message"] = new_msg

        user_id = int(embed.footer.text.split(":")[1])  # type: ignore
        user = ctx.guild.get_member(user_id)
        await self.__notify_user(ctx, user, message=msg, remark=remark)

        await ctx.send(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="clear", aliases=["cls"])
    @commands.check_any(commands.has_permissions(manage_messages=True), is_mod())
    async def clear_suggestion_embed(
        self,
        ctx: Context,
        message_id: int,
    ):
        """To remove all kind of notes and extra reaction from suggestion embed"""

        msg: Optional[discord.Message] = await self.get_or_fetch_message(message_id, guild=ctx.guild)
        if not msg:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{message_id}`. Probably already deleted, or `{message_id}` is invalid"
            )

        embed: discord.Embed = msg.embeds[0]
        embed.clear_fields()
        embed.color = 0xADD8E6
        new_msg = await msg.edit(embed=embed, content=None)
        self.message[new_msg.id]["message"] = new_msg

        for reaction in msg.reactions:
            if str(reaction.emoji) not in REACTION_EMOJI:
                await msg.clear_reaction(reaction.emoji)
        await ctx.send(f"{ctx.author.mention} Done", delete_after=5)

    @suggest.command(name="flag")
    @commands.check_any(commands.has_permissions(manage_messages=True), is_mod())
    async def suggest_flag(self, ctx: Context, message_id: int, flag: str):
        """To flag the suggestion.

        Avalibale Flags :-
        - INVALID
        - ABUSE
        - INCOMPLETE
        - DECLINE
        - APPROVED
        - DUPLICATE
        """

        msg: Optional[discord.Message] = await self.get_or_fetch_message(message_id, guild=ctx.guild)
        if not msg:
            return await ctx.send(
                f"{ctx.author.mention} Can not find message of ID `{message_id}`. Probably already deleted, or `{message_id}` is invalid"
            )

        if msg.author.id != self.bot.user.id:
            return await ctx.send(f"{ctx.author.mention} Invalid `{message_id}`")

        flag = flag.upper()
        try:
            payload: Dict[str, Union[int, str]] = OTHER_REACTION[flag]
        except KeyError:
            return await ctx.send(f"{ctx.author.mention} Invalid Flag")

        embed: discord.Embed = msg.embeds[0]
        embed.color = payload["color"]  # type: ignore

        user_id = int(embed.footer.text.split(":")[1])  # type: ignore
        user: Optional[discord.Member] = await self.bot.get_or_fetch_member(ctx.guild, user_id)
        await self.__notify_user(ctx, user, message=msg, remark="")

        content = f"Flagged: {flag} | {payload['emoji']}"
        new_msg = await msg.edit(content=content, embed=embed)
        self.message[new_msg.id]["message"] = new_msg

        await ctx.send(f"{ctx.author.mention} Done", delete_after=5)

    @Cog.listener(name="on_raw_message_delete")
    async def suggest_msg_delete(self, payload: discord.RawMessageDeleteEvent) -> None:
        if payload.message_id in self.message:
            del self.message[payload.message_id]

    @Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        await self.bot.wait_until_ready()
        if message.author.bot or message.guild is None:
            return

        ls = await self.bot.guild_configurations.find_one(
            {"_id": message.guild.id, "suggestion_channel": message.channel.id}
        )
        if not ls:
            return

        if message.channel.id != ls["suggestion_channel"]:
            return

        if _ := await self.__parse_mod_action(message):
            return

        context: Context = await self.bot.get_context(message, cls=Context)
        await self.suggest(context, suggestion=message.content)

    @Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message) -> None:
        if after.id in self.message:
            self.message[after.id]["message"] = after

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.message:
            return

        if str(payload.emoji) not in REACTION_EMOJI:
            return

        if str(payload.emoji) == "\N{UPWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_upvote"] += 1
        if str(payload.emoji) == "\N{DOWNWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_downvote"] += 1

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id not in self.message:
            return

        if str(payload.emoji) not in REACTION_EMOJI:
            return

        if str(payload.emoji) == "\N{UPWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_upvote"] -= 1
        if str(payload.emoji) == "\N{DOWNWARDS BLACK ARROW}":
            self.message[payload.message_id]["message_downvote"] -= 1

    async def __parse_mod_action(self, message: discord.Message) -> Optional[bool]:
        assert isinstance(message.author, discord.Member)

        if not self.__is_mod(message.author):
            return

        if message.content.upper() in OTHER_REACTION:
            context: Context = await self.bot.get_context(message, cls=Context)
            # cmd: commands.Command = self.bot.get_command("suggest flag")

            msg = None

            if message.reference is not None:
                msg: Optional[Union[discord.Message, discord.DeletedReferencedMessage]] = message.reference.resolved

            if not isinstance(msg, discord.Message):
                return

            if msg.author.id != self.bot.user.id:
                return

            # await context.invoke(cmd, msg.id, message.content.upper())
            await self.suggest_flag(context, msg.id, message.content.upper())
            return True

    def __is_mod(self, member: discord.Member) -> bool:
        try:
            role_id = self.bot.guild_configurations_cache[member.guild.id]["mod_role"]
            if role_id is None:
                perms: discord.Permissions = member.guild_permissions
                if any([perms.manage_guild, perms.manage_messages]):
                    return True
            return member._roles.has(role_id)
        except KeyError:
            return False


async def setup(bot: Parrot):
    await bot.add_cog(Suggestions(bot))
