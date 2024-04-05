from __future__ import annotations

import asyncio
import hashlib
import io
import json
import os
import random
import re
import string
import traceback
import typing
import urllib.parse
from collections import Counter
from typing import Annotated, Literal

import arrow
import jishaku  # noqa: F401
import jishaku.paginators  # noqa: F401
from aiofile import async_open
from aiosqlite.cursor import Cursor
from jishaku.paginators import PaginatorEmbedInterface
from tabulate import tabulate

import discord
from core import Cog, Context, Parrot
from discord.ext import commands
from utilities.converters import convert_bool
from utilities.paginator import PaginationView
from utilities.time import ShortTime
from utilities.wikihow import Parser as WikihowParser

from . import fuzzy
from .flags import BanFlag, SubscriptionFlag
from .utils import SphinxObjectFileReader
from .views import MongoCollectionView, MongoView, MongoViewSelect, NitroView


class Owner(Cog, command_attrs={"hidden": True}):
    """You can not use these commands."""

    def __init__(self, bot: Parrot) -> None:
        self.bot = bot
        self.count = 0
        self.wikihow_parser = WikihowParser()

        self.bot.get_user_data = self.get_user_data

    async def cog_load(self):
        await self.wikihow_parser.init()

    async def cog_unload(self):
        await self.wikihow_parser.close()

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="early_verified_bot_developer", id=892433993537032262)

    async def cog_check(self, ctx: Context) -> bool:
        return await self.bot.is_owner(ctx.author)

    @commands.command()
    @Context.with_type
    async def gitload(self, ctx: Context, *, link: str) -> None:
        """To load the cog extension from github."""
        r = await self.bot.http_session.get(link)
        data = await r.read()
        name = f"temp/temp{self.count}"
        name_cog = f"temp.temp{self.count}"
        try:
            async with async_open(f"{name}.py", "wb") as f:
                await f.write(data)
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            tbe = "".join(tb) + ""
            await ctx.send(f"[ERROR] Could not create file `{name}.py`: ```py\n{tbe}\n```")
        else:
            await ctx.send(f"[SUCCESS] file `{name}.py` created")

        try:
            await self.bot.load_extension(f"{name_cog}")
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            tbe = "".join(tb) + ""
            await ctx.send(f"[ERROR] Could not load extension {name_cog}.py: ```py\n{tbe}\n```")
        else:
            await ctx.send(f"[SUCCESS] Extension loaded `{name_cog}.py`")

        self.count += 1

    @commands.command()
    @Context.with_type
    async def makefile(self, ctx: Context, name: str, *, text: str) -> None:
        """To make a file in ./temp/ directly."""
        try:
            async with async_open(f"temp/{name}", "w+") as f:
                await f.write(text)
        except Exception as e:
            tb = traceback.format_exception(type(e), e, e.__traceback__)
            tbe = "".join(tb) + ""
            await ctx.send(f"[ERROR] Could not create file `{name}`: ```py\n{tbe}\n```")
        else:
            await ctx.send(f"[SUCCESS] File `{name}` created")

    @commands.command(aliases=["nitroscam", "nitro-scam"])
    async def nitro_scam(
        self,
        ctx: Context,
        *,
        target: discord.User | discord.TextChannel | discord.Thread | None = None,
    ):
        """Fun command."""
        await ctx.message.delete(delay=0)
        target = target or ctx.channel
        await target.send(
            embed=discord.Embed(
                title="You've been gifted a subscription!",
                description="You've been gifted Nitro for **1 month!**\nExpires in **24 hours**",
                timestamp=discord.utils.utcnow(),
            ).set_thumbnail(url="https://i.imgur.com/w9aiD6F.png"),
            view=NitroView(ctx),
        )

    @commands.command()
    @Context.with_type
    async def leave_guild(self, ctx: Context, *, guild: discord.Guild):
        """To leave the guild."""
        await ctx.send("Leaving Guild in a second!")
        await guild.leave()

    @commands.command()
    @Context.with_type
    async def ban_user(
        self,
        ctx: Context,
        user: discord.User,
        *,
        args: BanFlag,
    ):
        """To ban the user."""
        reason = args.reason or "No reason provided"
        payload = {"reason": reason, "command": args.command, "global": args._global}
        await self.bot.ban_user(user_id=user.id, **payload)
        try:
            await user.send(
                f"{user.mention} you are banned from using Sparklin bot. Reason: {reason}\n\nContact `{self.bot.author_name}` for unban.",
                view=ctx.send_view(),
            )
            await ctx.tick()
        except discord.Forbidden:
            await ctx.send("User banned, unable to DM as their DMs are locked")

    @commands.command()
    @Context.with_type
    async def unban_user(
        self,
        ctx: Context[Parrot],
        user: discord.User,
        *,
        remark: str = "No reason provided",
    ):
        """To ban the user."""
        await self.bot.unban_user(user_id=user.id)
        try:
            await user.send(
                f"{user.mention} you are unbanned. You can now use Sparklin bot.\n\nContact `{self.bot.author_name}` for any queries.",
                view=ctx.send_view(),
            )
            await ctx.tick()
        except discord.Forbidden:
            await ctx.send("User unbanned, unable to DM as their DMs are locked")

    @commands.group(
        name="image-search",
        aliases=["imagesearch", "imgs"],
        hidden=True,
        invoke_without_command=True,
    )
    @Context.with_type
    async def imgsearch(self, ctx: Context, *, text: str):
        """Image Search. Anything."""
        if ctx.invoked_subcommand is None:
            text = urllib.parse.quote(text)
            params = {
                "key": os.environ["GOOGLE_KEY"],
                "cx": os.environ["GOOGLE_CX"],
                "q": text,
                "searchType": "image",
            }
            url = "https://www.googleapis.com/customsearch/v1"
            res = await self.bot.http_session.get(url, params=params)
            data = await res.json()
            ls = []
            for i in data["items"]:
                embed = discord.Embed(
                    title=i["title"],
                    description=f"```\n{i['snippet']}```",
                    timestamp=discord.utils.utcnow(),
                )
                embed.set_footer(text=f"Requester: {ctx.author}")
                embed.set_image(url=i["link"])
                ls.append(embed)
            page = PaginationView(embed_list=ls)
            await page.start(ctx)

    @commands.command(name="delete-reference", aliases=["dr"])
    async def dr(self, ctx: Context):
        """To delete the message reference."""
        await ctx.message.delete(delay=0)
        await ctx.message.reference.resolved.delete(delay=0)

    @commands.command()
    async def spy_server(
        self,
        ctx: Context,
        guild: discord.Guild | int | None = None,
        channel_member: str | None = None,
    ):
        """This is not really a spy command."""
        guild = guild or ctx.guild
        channel_member = channel_member or "members"
        URL = f"https://discord.com/api/guilds/{guild.id if isinstance(guild, discord.Guild) else guild}/widget.json"
        data = await self.bot.http_session.get(URL)
        json: dict[str, typing.Any] = await data.json()
        if "message" in json:
            return await ctx.reply(f"{ctx.author.mention} can not spy that server")
        name = json["name"]
        _id = json["id"]
        instant_invite = json["instant_invite"]
        presence_count = json["presence_count"]

        embed_first = discord.Embed(
            title=name,
            color=ctx.author.color,
            timestamp=discord.utils.utcnow(),
        )
        if instant_invite:
            embed_first.url = instant_invite
        embed_first.set_footer(text=f"{_id}")
        embed_first.description = f"**Presence Count:** {presence_count}"
        em_list = [embed_first]

        for channel in json["channels"]:
            em_chan = discord.Embed(
                title=channel["name"],
                description=f"**Position:** {channel['position']}",
                color=ctx.author.color,
                timestamp=discord.utils.utcnow(),
            ).set_footer(text=channel["id"])

            em_list.append(em_chan)

        em_list_member = [embed_first]

        for member in json["members"]:
            _id = member["id"]
            username = member["username"]
            avatar_url = member["avatar_url"]
            status = member["status"]
            vc = member["channel_id"] if "channel_id" in member else None
            suppress = member["suppress"] if "suppress" in member else None
            self_mute = member["self_mute"] if "self_mute" in member else None
            self_deaf = member["self_deaf"] if "self_deaf" in member else None
            deaf = member["deaf"] if "deaf" in member else None
            mute = member["mute"] if "mute" in member else None

            em = (
                discord.Embed(
                    title=f"Username: {username}",
                    color=ctx.author.color,
                    timestamp=discord.utils.utcnow(),
                )
                .set_footer(text=f"{_id}")
                .set_thumbnail(url=avatar_url)
            )
            em.description = f"**Status:** {status.upper()}\n**In VC?** {bool(vc)} ({f'<#{str(vc)}>' if vc else None})"

            if vc:
                em.add_field(name="VC Channel ID", value=str(vc), inline=True).add_field(
                    name="Suppress?",
                    value=suppress,
                    inline=True,
                ).add_field(name="Self Mute?", value=self_mute, inline=True).add_field(
                    name="Self Deaf?",
                    value=self_deaf,
                    inline=True,
                ).add_field(
                    name="Deaf?",
                    value=deaf,
                    inline=True,
                ).add_field(
                    name="Mute?",
                    value=mute,
                    inline=True,
                )
            em_list_member.append(em)

        if channel_member.lower() in ("channels",):
            await PaginationView(em_list).start(ctx=ctx)
        elif channel_member.lower() in ("members",):
            await PaginationView(em_list_member).start(ctx=ctx)

    @commands.command()
    async def announce_global(self, ctx: Context, *, announcement: str):
        async for data in self.bot.guild_configurations.find():
            webhook = data["global_chat"]
            if (hook := webhook["webhook"]) and webhook["enable"]:
                if webhook := discord.Webhook.from_url(f"{hook}", session=self.bot.http_session):
                    await webhook.send(
                        content=announcement,
                        username="SERVER - SECTOR 17-29",
                        avatar_url=self.bot.user.display_avatar.url,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
        await ctx.tick()

    @commands.command(aliases=["command-lookup", "cl"])
    async def command_lookup(self, ctx: Context, _id: int, tp: str = "user"):
        """Command lookup."""
        data = await self.bot.command_collections.find_one({"type": tp, "_id": _id})
        if not data:
            return await ctx.send("No data")

        table = [["Command", "Count"]]
        data.pop("_id")

        for command, count in data.items():
            if command.endswith("_used"):
                cmd_name = command.replace("_used", "").replace("command_", "").replace("_", " ").title()
                table.append([cmd_name, count])

        table = tabulate(table, headers="firstrow", tablefmt="psql")
        await ctx.paginate(table, module="JishakuPaginatorInterface", max_size=1000, prefix="```sql", suffix="```")

    @commands.command(alises=["direct-message"])
    async def dm(self, ctx: Context, user: discord.User, *, reply: str):
        """Reply to the DM."""
        now = discord.utils.utcnow()
        msg = """## This is automated message from developer of Sparklin bot.\n"""
        msg += f"> **{ctx.author}**: _{reply.strip(' ')}_.\n"
        msg += "\n"
        msg += f"### Today at {discord.utils.format_dt(now)} ({discord.utils.format_dt(now, 'R')})"

        try:
            await user.send(msg)
            await ctx.tick()
        except discord.Forbidden:
            await ctx.wrong()

    @commands.command(alises=["direct-message-reply", "dm-reply", "dmreply"])
    async def dmreplay(self, ctx: Context, user: discord.User, limit: int | None = 100):
        """To get the DM reply."""
        ls = []
        dm = user.dm_channel or await user.create_dm()
        async for msg in dm.history(limit=limit):
            if msg.content:
                discord_timestamp = discord.utils.format_dt(msg.created_at, "R")
                ls.append(f"**{discord_timestamp} {msg.author}**: {msg.content.strip(' ')}")

        if not ls:
            await ctx.wrong()
            return

        await ctx.paginate(ls, max_size=1980, module="JishakuPaginatorEmbedInterface")

    @commands.command()
    async def create_code(self, ctx: Context, *, args: SubscriptionFlag):
        """To create a code for the bot premium."""
        PAYLOAD = {}
        BASIC = list(string.ascii_letters + string.digits)
        random.shuffle(BASIC)

        if args.code:
            PAYLOAD["hash"] = hashlib.sha256(args.code.encode()).hexdigest()
        else:
            PAYLOAD["hash"] = hashlib.sha256("".join(BASIC).encode()).hexdigest()

        PAYLOAD["guild"] = args.guild.id if args.guild else ctx.guild.id
        PAYLOAD["expiry"] = args.expiry.dt.timestamp() if args.expiry else ShortTime("2d").dt.timestamp()
        PAYLOAD["uses"] = args.uses
        PAYLOAD["limit"] = args.limit
        await self.bot.mongo.extra.subscriptions.insert_one(PAYLOAD)
        await ctx.send(
            f"""**{ctx.author.mention} Code created successfully.**
`Hash  `: `{PAYLOAD["hash"]}`
`Code  `: `{args.code or "".join(BASIC)}`
`Guild `: `{args.guild.name if args.guild else ctx.guild.name}`
`Expiry`: {discord.utils.format_dt(args.expiry.dt if args.expiry else ShortTime("2d").dt, 'R')}
`Uses  `: `{args.uses}`
`Limit `: `{args.limit}`
""",
        )

    @commands.command(hidden=True)
    async def gateway(self, ctx: Context):
        """Gateway related stats."""
        yesterday = arrow.utcnow().shift(days=-1).datetime

        # fmt: off
        identifies = {
            shard_id: sum(dt > yesterday for dt in dates)
            for shard_id, dates in self.bot.identifies.items()
        }

        resumes = {
            shard_id: sum(dt > yesterday for dt in dates)
            for shard_id, dates in self.bot.resumes.items()
        }

        # fmt: on

        total_identifies = sum(identifies.values())

        builder = [
            f"Total RESUMEs: {sum(resumes.values())}",
            f"Total IDENTIFYs: {total_identifies}",
        ]

        shard_count = len(self.bot.shards)
        if total_identifies > (shard_count * 10):
            issues = 2 + (total_identifies // 10) - shard_count
        else:
            issues = 0

        for shard_id, shard in self.bot.shards.items():
            badge = None
            # Shard WS closed
            # Shard Task failure
            # Shard Task complete (no failure)
            if shard.is_closed():
                badge = "\N{MEDIUM BLACK CIRCLE}"
                issues += 1
            elif shard._parent._task and shard._parent._task.done():
                exc = shard._parent._task.exception()
                if exc is not None:
                    badge = "\N{FIRE}"
                    issues += 1
                else:
                    badge = "\U0001f504"

            if badge is None:
                badge = "\N{LARGE GREEN CIRCLE}"

            stats = []
            identify = identifies.get(shard_id, 0)
            resume = resumes.get(shard_id, 0)
            if resume != 0:
                stats.append(f"R: {resume}")
            if identify != 0:
                stats.append(f"ID: {identify}")

            if stats:
                builder.append(f'Shard ID {shard_id}: {badge} ({", ".join(stats)})')
            else:
                builder.append(f"Shard ID {shard_id}: {badge}")

        if issues == 0:
            colour = 0x43B581
        elif issues < len(self.bot.shards) // 4:
            colour = 0xF09E47
        else:
            colour = 0xF04947

        embed = discord.Embed(colour=colour, title="Gateway (last 24 hours)")
        embed.description = "\n".join(builder)
        embed.set_footer(text=f"{issues} warnings")
        await ctx.send(embed=embed)

    @commands.command()
    async def maintenance(
        self,
        ctx: Context,
        till: ShortTime | None = None,
        *,
        reason: str | None = None,
    ):
        """To toggle the bot maintenance."""
        ctx.bot.UNDER_MAINTENANCE = not ctx.bot.UNDER_MAINTENANCE
        ctx.bot.UNDER_MAINTENANCE_OVER = till.dt if till is not None else till
        ctx.bot.UNDER_MAINTENANCE_REASON = reason
        await ctx.tick()

    @commands.command(aliases=["streaming", "listening", "watching"], hidden=True)
    async def playing(
        self,
        ctx: Context[Parrot],
        shard: int | None,
        status: Literal["online", "dnd", "offline", "idle"] | None = "dnd",
        *,
        media: str,
    ):
        """Update bot presence accordingly to invoke command.

        This is equivalent to:
        ```py
        p_types = {'playing': 0, 'streaming': 1, 'listening': 2, 'watching': 3}
        await ctx.bot.change_presence(discord.Activity(name=media, type=p_types[ctx.invoked_with]))
        ```
        """
        p_types = {"playing": 0, "streaming": 1, "listening": 2, "watching": 3, None: 0}
        await ctx.bot.change_presence(
            activity=discord.Activity(name=media, type=p_types[ctx.invoked_with]),
            shard_id=shard,
            status=discord.Status(status),
        )
        await ctx.tick()

    @commands.command()
    async def toggle_testing(self, ctx: Context, cog: str, toggle: Annotated[bool | None, convert_bool] = None) -> None:
        """Update the cog setting to toggle testing mode.

        ```py
        if hasattr(cog, "ON_TESTING"):
            cog.ON_TESTING = not cog.ON_TESTING
        ```
        """
        cog: Cog | None = self.bot.get_cog(cog)
        assert cog is not None
        if hasattr(cog, "ON_TESTING"):
            true_false = toggle if toggle is not None else not cog.ON_TESTING
            cog.ON_TESTING = true_false
            await ctx.send(f"{ctx.author.mention} successfully toggled cog ({cog.qualified_name}) to {toggle}")
            return
        if cog is not None:
            await ctx.send(f"{ctx.author.mention} cog ({cog.qualified_name}) does not have testing mode")
        else:
            await ctx.send(f"{ctx.author.mention} cog ({cog}) does not exist")

    async def get_user_data(self, *, user: discord.Object | int) -> typing.Any:
        """Illegal way to get presence of a user."""
        from utilities.object import objectify

        _id: int = user.id if isinstance(user, discord.Object) else user

        url = f"https://japi.rest/discord/v1/user/{_id}"
        async with self.bot.http_session.get(url) as resp:
            data = await resp.json()

        return objectify(data)

    @commands.command()
    async def mongo(
        self,
        ctx: Context,
        db: str | None = None,
        collection: str | None = None,
    ):
        """MongoDB query."""
        if db and collection:
            view = MongoCollectionView(db=db, collection=collection, ctx=ctx)
            embed = await MongoViewSelect.build_embed(ctx, db, collection)
            view.message = await ctx.send(embed=embed, view=view)
            return

        view = MongoView(ctx)
        await view.init()

    @commands.command(alises=["sql3", "sqlite3", "sqlite"])
    async def sql(self, ctx: Context, *, queries: str):
        """SQL query.

        This is equivalent to:
        ```py
        sql = ctx.bot.sql
        for query in queries.split(";"):
            cursor = await sql.execute(query)
        ...
        ```
        """
        queries = queries.replace("```sql", "").replace("```", "").strip("`").strip()

        queries: list[str] = queries.split(";")
        sql = self.bot.sql  # sqlite3

        super_ini = arrow.utcnow().timestamp()
        results: list[tuple[str, Cursor, int, float]] = []
        # list of tuples of str, Cursor, affected rows, time taken

        for query in queries:
            if not query:
                continue

            ini = arrow.utcnow().timestamp()
            try:
                cursor = await sql.execute(query)
            except Exception as e:
                await ctx.send(f"```py\n{e}```")
                return
            total_rows_affected = cursor.rowcount
            fin = arrow.utcnow().timestamp() - ini

            results.append((query.upper(), cursor, total_rows_affected, fin))

        super_fin = arrow.utcnow().timestamp() - super_ini

        to_send = ""
        if not results:
            await ctx.send(f"Rows affected: **-1** | Time taken: **{super_fin:.3f}s**")
            return

        for q, cursor, total_rows_affected, fin in results:
            colums = [i[0] for i in cursor.description]
            rslt = await cursor.fetchall()
            table = tabulate(rslt, headers=colums, tablefmt="psql")

            to_send += f"""```sql
SQLite > {q.strip(' ')}
{table}
Rows affected: `{total_rows_affected}` | Time taken: `{fin:.3f}s`
```"""
        if not to_send:
            await ctx.send(f"Rows affected: **-1** | Time taken: **{super_fin:.3f}s**")
            return

        if len(to_send) < 2000:
            await ctx.send(to_send)
            return

        file = discord.File(io.BytesIO(to_send.encode()), filename="table.sql")
        await ctx.send(file=file)
        return

    @commands.command()
    async def wikihow(self, ctx: Context, *, query: int | str) -> None:
        """WikiHow search."""
        if isinstance(query, str) and query.isdigit():
            query = int(query)

        if isinstance(query, int):
            data = await self.wikihow_parser.get_wikihow_article(query)
            if not data["real"]["intro"]:
                await ctx.send("No results found.")
                return

            page = commands.Paginator(prefix="", suffix="")
            interface = PaginatorEmbedInterface(ctx.bot, page, owner=ctx.author, timeout=60)
            real = data["real"]
            if real.get("intro"):
                await interface.add_line(f"# Intro\n> {real['intro']}")

            await interface.send_to(ctx)

            def _join_values(values: list[str] | list[list[str]]) -> str:
                val: list[str] = []
                for value in values:
                    if isinstance(value, list):
                        val.append(" ".join(value))
                    else:
                        val.append(value)
                return "\n".join(val)

            async def add_page(interface: PaginatorEmbedInterface, *, title: str, data: list[str] | list[list[str]]) -> None:
                if not data:
                    return
                await interface.add_line(f"# {title}")
                _data = _join_values(data)
                _data = _data.split("\n")
                for d in _data:
                    await interface.add_line(f"- {d}")

            if real.get("Things You Should Know"):
                await add_page(interface, title="Things You Should Know", data=real["Things You Should Know"].values())

            wiki_steps: dict[
                str,
                list[list[str | list[str]] | str],
            ] = real.pop("Steps", {})

            for hd, steps in wiki_steps.items():
                if not steps:
                    continue
                await interface.add_line(f"## {hd}")
                if isinstance(steps, str):
                    _steps = steps.split("\n")
                    for step in _steps:
                        await interface.add_line(f"- {step}")
                    continue

                for points in steps:
                    if isinstance(points, str):
                        await interface.add_line(f"**{points}**")
                        continue
                    for point in points:
                        await interface.add_line(f"- {point}")

            if real.get("Tips"):
                await add_page(interface, title="Tips", data=real["Tips"].values())

            if real.get("Warnings"):
                await add_page(interface, title="Warnings", data=real["Warnings"].values())

            if real.get("Test Your Knowledge"):
                await add_page(interface, title="Test Your Knowledge", data=real["Test Your Knowledge"].values())

            if real.get("Video"):
                await add_page(interface, title="Video", data=real["Video"].values())

            if real.get("Related wikiHows"):
                await add_page(interface, title="Related wikiHows", data=real["Related wikiHows"].values())

            if real.get("References"):
                await add_page(interface, title="References", data=real["References"].values())

            if real.get("Summary"):
                await add_page(interface, title="Summary", data=real["Summary"].values())

        else:
            initial_data = await self.wikihow_parser.get_wikihow(query)
            if not initial_data:
                await ctx.reply("No results found. Try again with a different query.")
                return

            page = commands.Paginator(prefix="", suffix="", max_size=1500)
            interface = PaginatorEmbedInterface(ctx.bot, page, owner=ctx.author, timeout=60)
            for title, snippet, _id in initial_data:
                await interface.add_line(f"[{title}] {_id}\n> {snippet}\n")
            await interface.send_to(ctx)


class DiscordPy(Cog, command_attrs={"hidden": True}):
    def __init__(self, bot: Parrot) -> None:
        self.bot = bot
        with open("extra/docs_links.json", encoding="utf-8", errors="ignore") as f:
            self.page_types = json.load(f)

    @property
    def display_emoji(self) -> discord.PartialEmoji:
        return discord.PartialEmoji(name="dpy", id=596577034537402378)

    async def cog_load(self) -> None:
        self.bot.loop.create_task(self.build_rtfm_lookup_table(self.page_types))

    def parse_object_inv(self, stream, url):
        # key: URL
        # n.b.: key doesn't have `discord` or `discord.ext.commands` namespaces
        result = {}

        # first line is version info
        inv_version = stream.readline().rstrip()
        _ = stream.readline().rstrip()[11:]

        if inv_version != "# Sphinx inventory version 2":
            msg = "Invalid objects.inv file version."
            raise RuntimeError(msg)

        # next line is "# Project: <name>"
        # then after that is "# Version: <version>"
        projname = stream.readline().rstrip()[11:]

        # next line says if it's a zlib header
        line = stream.readline()
        if "zlib" not in line:
            msg = "Invalid objects.inv file, not z-lib compatible."
            raise RuntimeError(msg)

        # This code mostly comes from the Sphinx repository.
        entry_regex = re.compile(r"(?x)(.+?)\s+(\S*:\S*)\s+(-?\d+)\s+(\S+)\s+(.*)")
        for line in stream.read_compressed_lines():
            match = entry_regex.match(line.rstrip())
            if not match:
                continue

            name, directive, _, location, dispname = match.groups()
            domain, _, subdirective = directive.partition(":")
            if directive == "py:module" and name in result:
                # From the Sphinx Repository:
                # due to a bug in 1.1 and below,
                # two inventory entries are created
                # for Python modules, and the first
                # one is correct
                continue

            # Most documentation pages have a label
            if directive == "std:doc":
                subdirective = "label"

            if location.endswith("$"):
                location = location[:-1] + name

            key = name if dispname == "-" else dispname
            prefix = f"{subdirective}:" if domain == "std" else ""

            if projname == "discord.py":
                key = key.replace("discord.ext.commands.", "").replace("discord.", "")

            result[f"{prefix}{key}"] = os.path.join(url, location)

        return result

    async def build_rtfm_lookup_table(self, page_types):
        cache = {}
        for key, page in page_types.items():
            cache[key] = {}
            resp = await self.bot.http_session.get(f"{page}/objects.inv")
            if resp.status != 200:
                msg = "Cannot build rtfm lookup table, try again later."
                raise RuntimeError(msg)

            stream = SphinxObjectFileReader(await resp.read())
            cache[key] = self.parse_object_inv(stream, page)

        self._rtfm_cache = cache

    async def do_rtfm(self, ctx: Context, key: str, obj):
        if obj is None:
            await ctx.send(self.page_types[key])
            return

        if not hasattr(self, "_rtfm_cache"):
            await ctx.typing()
            await self.build_rtfm_lookup_table(self.page_types)

        obj = re.sub(r"^(?:discord\.(?:ext\.)?)?(?:commands\.)?(.+)", r"\1", obj)

        if key.startswith("latest"):
            # point the abc.Messageable types properly:
            q = obj.lower()
            for name in dir(discord.abc.Messageable):
                if name[0] == "_":
                    continue
                if q == name:
                    obj = f"abc.Messageable.{name}"
                    break

        cache = list(self._rtfm_cache[key].items())

        _matches = await asyncio.to_thread(fuzzy.finder, obj, cache, key=lambda t: t[0], lazy=False)
        matches = list(_matches)[:8]
        if len(matches) == 0:
            return await ctx.send("Could not find anything. Sorry.")

        e = (
            discord.Embed(
                title="RTFD - Read the Fine Documentation",
                timestamp=discord.utils.utcnow(),
                description="\n".join(f"[`{key}`]({url})" for key, url in matches),
            )
            .set_footer(
                text=f"Request by {ctx.author}",
                icon_url=ctx.author.display_avatar.url,
            )
            .set_author(
                name="Search Results",
                icon_url=self.display_emoji.url,
            )
        )
        await ctx.send(embed=e)

    @commands.group(invoke_without_command=True)
    async def rtfd(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a specified entity.
        Events, objects, and functions are all supported through
        a cruddy fuzzy algorithm.
        """
        if not ctx.invoked_subcommand:
            return await self.do_rtfm(ctx, "discord", obj)

    @rtfd.command(name="python", aliases=["py"])
    async def rtfm_python(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a Python entity."""
        await self.do_rtfm(ctx, "python", obj)

    @rtfd.command(name="aiohttp")
    async def rtfd_aiohttp(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a aiohttp entity."""
        await self.do_rtfm(ctx, "aiohttp", obj)

    @rtfd.command(name="requests", aliases=["request", "req"])
    async def rtfd_request(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a request entity."""
        await self.do_rtfm(ctx, "requests", obj)

    @rtfd.command(name="flask")
    async def rtfd_flask(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a flask entity."""
        await self.do_rtfm(ctx, "flask", obj)

    @rtfd.command(name="numpy", aliases=["np"])
    async def rtfd_numpy(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a numpy entity."""
        await self.do_rtfm(ctx, "numpy", obj)

    @rtfd.command(name="pil")
    async def rtfd_pil(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a PIL entity."""
        await self.do_rtfm(ctx, "pil", obj)

    @rtfd.command(name="matplotlib", aliases=["matlab", "plt", "mat"])
    async def rtfd_matplotlib(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a matplotlib entity."""
        await self.do_rtfm(ctx, "matplotlib", obj)

    @rtfd.command(name="pandas", aliases=["pd"])
    async def rtfd_pandas(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a pandas entity."""
        await self.do_rtfm(ctx, "pandas", obj)

    @rtfd.command(name="pymongo", aliases=["mongo", "pym"])
    async def rtfd_pymongo(self, ctx: Context, *, obj: str | None = None):
        """Gives you a documentation link for a pymongo entity."""
        await self.do_rtfm(ctx, "pymongo", obj)

    @rtfd.command(name="showall", aliases=["show", "list", "all", "ls"])
    async def rtfd_showall(
        self,
        ctx: Context,
    ):
        """Show all the docs links."""
        async with async_open(r"extra/docs_links.json") as f:
            data = json.loads(await f.read())

        await ctx.send(f"```json\n{json.dumps(data, indent=4)}```")

    @rtfd.command(name="add")
    async def rtfd_add(self, ctx: Context, name: str, *, link: str):
        """To add the links in docs."""
        async with async_open(r"extra/docs_links.json") as f:
            data = json.loads(await f.read())

        data[name] = link

        async with async_open(r"extra/docs_links.json") as f:
            await f.write(data)

        await ctx.send(f"{ctx.author.mention} done!")

    @rtfd.command(name="del")
    async def rtfd_del(
        self,
        ctx: Context,
        name: str,
    ):
        """To add the links in docs."""
        async with async_open(r"extra/docs_links.json") as f:
            data: dict = json.loads(await f.read())

        data.pop(name)

        async with async_open(r"extra/docs_links.json") as f:
            await f.write(data)

        await ctx.send(f"{ctx.author.mention} done!")

    @commands.command()
    async def cleanup(self, ctx: Context, search: int = 100):
        """Cleans up the bot's messages from the channel.
        If a search number is specified, it searches that many messages to delete.

        If the bot has Manage Messages permissions then it will try to delete
        messages that look like they invoked the bot as well.

        After the cleanup is completed, the bot will send you a message with
        which people got their messages deleted and their count. This is useful
        to see which users are spammers.

        Members with Manage Messages can search up to 1000 messages.
        Members without can search up to 25 messages.
        """
        strategy = self._basic_cleanup_strategy
        assert isinstance(ctx.author, discord.Member) and isinstance(ctx.me, discord.Member)
        is_mod = ctx.channel.permissions_for(ctx.author).manage_messages
        if ctx.channel.permissions_for(ctx.me).manage_messages:
            if is_mod:
                strategy = self._complex_cleanup_strategy
            else:
                strategy = self._regular_user_cleanup_strategy

        search = min(max(2, search), 1000) if is_mod else min(max(2, search), 25)
        spammers = await strategy(ctx, search)
        deleted = sum(spammers.values())
        messages = [f'{deleted} message{" was" if deleted == 1 else "s were"} removed.']
        if deleted:
            messages.append("")
            spammers = sorted(spammers.items(), key=lambda t: t[1], reverse=True)
            messages.extend(f"- **{author}**: {count}" for author, count in spammers)

        await ctx.send("\n".join(messages), delete_after=10)

    async def _basic_cleanup_strategy(self, ctx: Context, search: int):
        count = 0
        async for msg in ctx.history(limit=search, before=ctx.message):
            if msg.author == ctx.me and not msg.mentions and not msg.role_mentions:
                await msg.delete()
                count += 1
        return {"Bot": count}

    async def _complex_cleanup_strategy(self, ctx: Context, search: int):
        prefixes = tuple(await self.bot.get_guild_prefixes(ctx.guild))  # thanks startswith

        def check(m: discord.Message):
            return m.author == ctx.me or m.content.startswith(prefixes)

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)

    async def _regular_user_cleanup_strategy(self, ctx: Context, search: int):
        prefixes = tuple(await self.bot.get_guild_prefixes(ctx.guild))

        def check(m: discord.Message):
            return (m.author == ctx.me or m.content.startswith(prefixes)) and not m.mentions and not m.role_mentions

        deleted = await ctx.channel.purge(limit=search, check=check, before=ctx.message)
        return Counter(m.author.display_name for m in deleted)
