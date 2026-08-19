"""Telegram bot front-end for Seshat.

Talks directly to the vault via `seshat.core.tools` (no HTTP hop through
`seshat.mcp` — this bot is a peer front-end, not an MCP client). Every
write command requires the sender's Telegram user id to be in the allowlist.
"""

from __future__ import annotations

import logging
from pathlib import Path

from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from seshat.core import VaultClient
from seshat.core.tools import (
    append_history,
    create_fragment,
    create_project,
    create_reference,
    get_project,
    list_projects,
    list_references,
    search_vault,
    update_project_status,
)

from .formatting import (
    escape_md,
    format_error,
    format_project_detail,
    format_projects_list,
    format_references_list,
    format_search_results,
)
from .parsing import ArgParseError, parse_kv_args, require, split_list

logger = logging.getLogger(__name__)

HELP_TEXT = """\
*Seshat — bot do Akasha*

Comandos de leitura:
/projects \\[field=\\.\\.\\.\\] \\[status=\\.\\.\\.\\] \\[stage=\\.\\.\\.\\]
/project slug
/references \\[area=\\.\\.\\.\\] \\[type=\\.\\.\\.\\] \\[field=\\.\\.\\.\\]
/search query=\\.\\.\\. \\[field=\\.\\.\\.\\] \\[category=\\.\\.\\.\\] \\[tag=\\.\\.\\.\\]

Comandos de escrita:
/newproject year\\_month=202608 slug=teste title="Teste" summary="\\.\\.\\." field=Programação type=comercial
/history slug=202608\\_teste date=2026\\-08\\-19 title="Início" summary="\\.\\.\\."
/status slug=202608\\_teste project\\_status=in\\_progress date=2026\\-08\\-19
/fragment filename\\_slug=nota title="Nota" summary="\\.\\.\\." field=Programação body="\\.\\.\\."
/newreference area=caligrafia slug=x title="X" summary="\\.\\.\\." field=Caligrafia type=technique

Argumentos são `chave=valor`, use aspas para valores com espaço\\.
Digite qualquer texto sem comando pra buscar no vault\\.
"""


class SeshatTelegramBot:
    """Wraps a python-telegram-bot Application wired to a Seshat vault."""

    def __init__(self, vault_root: str | Path, telegram_token: str, allowed_user_ids: set[int]):
        self.vault = VaultClient(vault_root)
        self.allowed_user_ids = allowed_user_ids
        self.app = Application.builder().token(telegram_token).build()
        self._register_handlers()

    def _register_handlers(self) -> None:
        self.app.add_handler(CommandHandler("start", self.cmd_help))
        self.app.add_handler(CommandHandler("help", self.cmd_help))
        self.app.add_handler(CommandHandler("projects", self.cmd_projects))
        self.app.add_handler(CommandHandler("project", self.cmd_project))
        self.app.add_handler(CommandHandler("references", self.cmd_references))
        self.app.add_handler(CommandHandler("search", self.cmd_search))
        self.app.add_handler(CommandHandler("newproject", self.cmd_newproject))
        self.app.add_handler(CommandHandler("history", self.cmd_history))
        self.app.add_handler(CommandHandler("status", self.cmd_status))
        self.app.add_handler(CommandHandler("fragment", self.cmd_fragment))
        self.app.add_handler(CommandHandler("newreference", self.cmd_newreference))
        self.app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.on_text))

    def run(self) -> None:
        logger.info("Seshat Telegram bot starting (polling)")
        self.app.run_polling(allowed_updates=Update.ALL_TYPES)

    # -- auth -----------------------------------------------------------

    def _is_authorized(self, update: Update) -> bool:
        user = update.effective_user
        return bool(user) and user.id in self.allowed_user_ids

    async def _guard(self, update: Update) -> bool:
        if not self._is_authorized(update):
            uid = update.effective_user.id if update.effective_user else "?"
            logger.warning("Unauthorized access attempt from user id %s", uid)
            await update.message.reply_text(
                "Você não está autorizado a usar este bot. "
                "Peça para adicionar seu id do Telegram em SESHAT_TELEGRAM_ALLOWED_USERS."
            )
            return False
        return True

    async def _reply_md(self, update: Update, text: str) -> None:
        await update.message.reply_text(text, parse_mode="MarkdownV2")

    # -- read commands ----------------------------------------------------

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await self._reply_md(update, HELP_TEXT)

    async def cmd_projects(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            results = list_projects(
                self.vault,
                field=args.get("field"),
                project_status=args.get("status") or args.get("project_status"),
                project_stage=args.get("stage") or args.get("project_stage"),
            )
            await self._reply_md(update, format_projects_list(results))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_project(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        if not context.args:
            await update.message.reply_text("Uso: /project <slug>")
            return
        try:
            result = get_project(self.vault, context.args[0])
            await self._reply_md(update, format_project_detail(result))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_references(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            results = list_references(
                self.vault,
                area_slug=args.get("area"),
                type=args.get("type"),
                field=args.get("field"),
            )
            await self._reply_md(update, format_references_list(results))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_search(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            raw = " ".join(context.args)
            args = parse_kv_args(raw) if "=" in raw else {"query": raw}
            results = search_vault(
                self.vault,
                query=args.get("query"),
                tag=args.get("tag"),
                field=args.get("field"),
                category=args.get("category"),
            )
            await self._reply_md(update, format_search_results(results))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def on_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            results = search_vault(self.vault, query=update.message.text)
            await self._reply_md(update, format_search_results(results))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    # -- write commands -----------------------------------------------------

    async def cmd_newproject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            require(args, "year_month", "slug", "title", "summary", "field", "type")
            result = create_project(
                self.vault,
                year_month=args["year_month"],
                slug=args["slug"],
                title=args["title"],
                summary=args["summary"],
                field=args["field"],
                project_type=args["type"],
                project_status=args.get("status", "planning"),
                project_stage=args.get("stage", "call"),
                khaos_project_id=args.get("khaos_id"),
            )
            await self._reply_md(update, f"✅ Projeto criado: `{escape_md(result['slug'])}`")
        except (ArgParseError, Exception) as e:
            await self._reply_md(update, format_error(e))

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            require(args, "slug", "date", "title", "summary")
            append_history(
                self.vault,
                history_relative_path=f"02-Projects/{args['slug']}/01_history.md",
                date=args["date"],
                title=args["title"],
                summary_line=args["summary"],
                detail=args.get("detail", ""),
            )
            await self._reply_md(update, f"✅ Entrada de histórico adicionada a `{escape_md(args['slug'])}`")
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            require(args, "slug", "date")
            result = update_project_status(
                self.vault,
                slug=args["slug"],
                date=args["date"],
                project_status=args.get("project_status") or args.get("status"),
                project_stage=args.get("project_stage") or args.get("stage"),
                summary_line=args.get("summary"),
                detail=args.get("detail", ""),
            )
            await self._reply_md(update, f"✅ Status atualizado: `{escape_md(result['slug'])}`")
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_fragment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            require(args, "filename_slug", "title", "summary", "field", "body")
            result = create_fragment(
                self.vault,
                filename_slug=args["filename_slug"],
                title=args["title"],
                summary=args["summary"],
                field=args["field"],
                body=args["body"],
                tags=split_list(args.get("tags")),
            )
            await self._reply_md(update, f"✅ Fragmento criado: `{escape_md(result['path'])}`")
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_newreference(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        try:
            args = parse_kv_args(" ".join(context.args))
            require(args, "area", "slug", "title", "summary", "field", "type")
            result = create_reference(
                self.vault,
                area_slug=args["area"],
                slug=args["slug"],
                title=args["title"],
                summary=args["summary"],
                field=args["field"],
                type=args["type"],
                body=args.get("body", ""),
                as_folder=args.get("folder", "false").lower() in ("1", "true", "yes"),
                tags=split_list(args.get("tags")),
            )
            await self._reply_md(update, f"✅ Referência criada: `{escape_md(result['area_slug'])}/{escape_md(result['slug'])}`")
        except Exception as e:
            await self._reply_md(update, format_error(e))
