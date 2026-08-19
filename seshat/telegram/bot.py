"""Telegram bot front-end for Seshat.

Talks directly to the vault via `seshat.core.tools` (no HTTP hop through
`seshat.mcp` — this bot is a peer front-end, not an MCP client). Every
write command requires the sender's Telegram user id to be in the allowlist.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from telegram import BotCommand, Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from seshat.core import VaultClient, ensure_synced
from seshat.core.schema import FIELDS, PROJECT_STAGES, PROJECT_STATUSES
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
from seshat.core.vault import slugify

from .formatting import (
    escape_md,
    format_error,
    format_project_detail,
    format_projects_list,
    format_references_list,
    format_search_results,
)
from .parsing import parse_kv_args

logger = logging.getLogger(__name__)

HELP_TEXT = """\
*Seshat — bot do Akasha*

Comandos de leitura:
/projects \\[field=\\.\\.\\.\\] \\[status=\\.\\.\\.\\] \\[stage=\\.\\.\\.\\]
/project slug
/references \\[area=\\.\\.\\.\\] \\[type=\\.\\.\\.\\] \\[field=\\.\\.\\.\\]
/search query=\\.\\.\\. \\[field=\\.\\.\\.\\] \\[category=\\.\\.\\.\\] \\[tag=\\.\\.\\.\\]

Comandos de escrita — o bot pergunta cada campo, um de cada vez:
/newproject, /history, /status, /newreference
/fragment \\[campo\\] — depois envie o texto numa mensagem, o resto é preenchido automaticamente

/cancelar interrompe um comando de escrita em andamento\\.
Digite qualquer texto sem comando pra buscar no vault \\(fora de um comando em andamento\\)\\.
"""

# Registrado no Telegram via set_my_commands (menu "/" do app) — mantém a lista
# sincronizada com HELP_TEXT em vez de exigir /setcommands manual no BotFather.
BOT_COMMANDS = [
    ("help", "Mostra os comandos disponíveis"),
    ("projects", "Lista projetos (field=... status=... stage=...)"),
    ("project", "Detalhes de um projeto (slug)"),
    ("references", "Lista referências (area=... type=... field=...)"),
    ("search", "Busca no vault (query=... field=... category=...)"),
    ("newproject", "Cria um novo projeto"),
    ("history", "Adiciona entrada ao histórico de um projeto"),
    ("status", "Atualiza status/etapa de um projeto"),
    ("fragment", "Captura um fragmento — envie o texto na mensagem seguinte"),
    ("newreference", "Cria uma referência"),
    ("cancelar", "Cancela o comando em andamento"),
]

FRAGMENT_DEFAULT_FIELD = "Pessoal"


@dataclass
class FlowStep:
    """One question in a guided multi-step write command."""

    key: str
    prompt: str
    choices: frozenset[str] | None = None
    optional: bool = False  # answer "-" to skip


FLOWS: dict[str, list[FlowStep]] = {
    "newproject": [
        FlowStep("year_month", "Ano-mês do projeto (formato AAAAMM, ex: 202608):"),
        FlowStep("slug", "Slug do projeto (nome curto, sem espaços):"),
        FlowStep("title", "Título do projeto:"),
        FlowStep("summary", "Resumo breve:"),
        FlowStep("field", f"Campo — opções: {', '.join(sorted(FIELDS))}", choices=frozenset(FIELDS)),
        FlowStep("project_type", "Tipo do projeto (ex: comercial, pessoal):"),
    ],
    "history": [
        FlowStep("slug", "Slug do projeto (pasta em 02-Projects/):"),
        FlowStep("date", "Data da entrada (AAAA-MM-DD):"),
        FlowStep("title", "Título da entrada:"),
        FlowStep("summary_line", "Resumo da entrada:"),
    ],
    "status": [
        FlowStep("slug", "Slug do projeto:"),
        FlowStep("date", "Data da mudança (AAAA-MM-DD):"),
        FlowStep(
            "project_status",
            f"Novo status — opções: {', '.join(sorted(PROJECT_STATUSES))}",
            choices=frozenset(PROJECT_STATUSES),
            optional=True,
        ),
        FlowStep(
            "project_stage",
            f"Nova etapa — opções: {', '.join(sorted(PROJECT_STAGES))}",
            choices=frozenset(PROJECT_STAGES),
            optional=True,
        ),
        FlowStep("summary_line", "Resumo da mudança:", optional=True),
    ],
    "newreference": [
        FlowStep("area", "Área da referência (subpasta, ex: caligrafia):"),
        FlowStep("slug", "Slug da referência:"),
        FlowStep("title", "Título:"),
        FlowStep("summary", "Resumo:"),
        FlowStep("field", f"Campo — opções: {', '.join(sorted(FIELDS))}", choices=frozenset(FIELDS)),
        FlowStep("reference_type", "Tipo da referência (ex: technique, document):"),
    ],
}


class SeshatTelegramBot:
    """Wraps a python-telegram-bot Application wired to a Seshat vault."""

    def __init__(
        self,
        vault_root: str | Path,
        telegram_token: str,
        allowed_user_ids: set[int],
        git_remote_url: str | None = None,
    ):
        self.git = ensure_synced(vault_root, git_remote_url)
        self.vault = VaultClient(vault_root)
        self.git_remote_url = git_remote_url
        self.allowed_user_ids = allowed_user_ids
        self.app = Application.builder().token(telegram_token).post_init(self._post_init).build()
        self._register_handlers()

    async def _post_init(self, application: Application) -> None:
        """Registers BOT_COMMANDS with Telegram so they show up in the "/" menu."""
        await application.bot.set_my_commands([BotCommand(name, desc) for name, desc in BOT_COMMANDS])

    def _autosync(self, message: str) -> None:
        """Commit and push any vault changes after a write command.

        No-ops when no git remote is configured. Failures are logged but never
        raised — a push failure shouldn't turn a successful write into an
        error reply, and on an ephemeral disk the next boot's clone will just
        be missing this one change rather than losing the whole vault.
        """
        if not self.git_remote_url:
            return
        try:
            self.git.commit_and_push(message)
        except Exception as e:
            logger.warning("git autosync failed: %s", e)

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
        self.app.add_handler(CommandHandler("cancelar", self.cmd_cancel))
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
        pending_field = context.user_data.pop("awaiting_fragment_field", None)
        if pending_field is not None:
            await self._create_fragment_from_text(update, update.message.text, pending_field)
            return
        if context.user_data.get("flow"):
            await self._advance_flow(update, context)
            return
        try:
            results = search_vault(self.vault, query=update.message.text)
            await self._reply_md(update, format_search_results(results))
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def cmd_cancel(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        had_something = (
            context.user_data.pop("flow", None) is not None
            or context.user_data.pop("awaiting_fragment_field", None) is not None
        )
        await update.message.reply_text("Cancelado." if had_something else "Nada em andamento pra cancelar.")

    # -- guided multi-step write commands -----------------------------------

    async def _start_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE, flow_name: str) -> None:
        context.user_data["flow"] = {"name": flow_name, "step": 0, "data": {}}
        await self._ask_current_step(update, context)

    async def _ask_current_step(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        flow = context.user_data["flow"]
        step = FLOWS[flow["name"]][flow["step"]]
        prompt = step.prompt
        if step.optional:
            prompt += '\n(envie "-" para pular)'
        await update.message.reply_text(prompt)

    async def _advance_flow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        flow = context.user_data["flow"]
        step = FLOWS[flow["name"]][flow["step"]]
        text = update.message.text.strip()

        if step.optional and text == "-":
            value = None
        elif step.choices and text not in step.choices:
            await self._reply_md(
                update, f"⚠️ Valor inválido\\. Opções: {escape_md(', '.join(sorted(step.choices)))}"
            )
            return  # re-ask the same step
        else:
            value = text

        if value is not None:
            flow["data"][step.key] = value

        flow["step"] += 1
        if flow["step"] >= len(FLOWS[flow["name"]]):
            data = flow["data"]
            flow_name = flow["name"]
            del context.user_data["flow"]
            await self._finish_flow(update, flow_name, data)
            return
        await self._ask_current_step(update, context)

    async def _finish_flow(self, update: Update, flow_name: str, data: dict[str, str]) -> None:
        try:
            if flow_name == "newproject":
                result = create_project(
                    self.vault,
                    year_month=data["year_month"],
                    slug=data["slug"],
                    title=data["title"],
                    summary=data["summary"],
                    field=data["field"],
                    project_type=data["project_type"],
                )
                self._autosync(f"telegram: cria projeto {result['slug']}")
                await self._reply_md(update, f"✅ Projeto criado: `{escape_md(result['slug'])}`")
            elif flow_name == "history":
                append_history(
                    self.vault,
                    history_relative_path=f"02-Projects/{data['slug']}/01_history.md",
                    date=data["date"],
                    title=data["title"],
                    summary_line=data["summary_line"],
                )
                self._autosync(f"telegram: histórico em {data['slug']}")
                await self._reply_md(update, f"✅ Entrada de histórico adicionada a `{escape_md(data['slug'])}`")
            elif flow_name == "status":
                result = update_project_status(
                    self.vault,
                    slug=data["slug"],
                    date=data["date"],
                    project_status=data.get("project_status"),
                    project_stage=data.get("project_stage"),
                    summary_line=data.get("summary_line"),
                )
                self._autosync(f"telegram: status de {result['slug']}")
                await self._reply_md(update, f"✅ Status atualizado: `{escape_md(result['slug'])}`")
            elif flow_name == "newreference":
                result = create_reference(
                    self.vault,
                    area_slug=data["area"],
                    slug=data["slug"],
                    title=data["title"],
                    summary=data["summary"],
                    field=data["field"],
                    type=data["reference_type"],
                )
                self._autosync(f"telegram: cria referência {result['area_slug']}/{result['slug']}")
                await self._reply_md(
                    update, f"✅ Referência criada: `{escape_md(result['area_slug'])}/{escape_md(result['slug'])}`"
                )
        except Exception as e:
            await self._reply_md(update, format_error(e))

    async def _create_fragment_from_text(self, update: Update, text: str, field: str) -> None:
        try:
            text = text.strip()
            if not text:
                raise ValueError("texto vazio — nada pra guardar")
            first_line = text.splitlines()[0].strip()
            title = first_line[:80]
            summary = first_line if len(first_line) <= 140 else first_line[:137] + "..."
            filename_slug = f"{slugify(title)}-{datetime.now():%Y%m%d%H%M%S}"
            result = create_fragment(
                self.vault,
                filename_slug=filename_slug,
                title=title,
                summary=summary,
                field=field,
                body=text,
            )
            self._autosync(f"telegram: cria fragmento {result['path']}")
            await self._reply_md(
                update, f"✅ Fragmento criado: `{escape_md(result['path'])}` \\(campo: {escape_md(field)}\\)"
            )
        except Exception as e:
            await self._reply_md(update, format_error(e))

    # -- write commands -----------------------------------------------------

    async def cmd_newproject(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await self._start_flow(update, context, "newproject")

    async def cmd_history(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await self._start_flow(update, context, "history")

    async def cmd_status(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await self._start_flow(update, context, "status")

    async def cmd_fragment(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Captura rápida: /fragment [campo opcional], depois o texto vem na mensagem seguinte.

        Título, resumo e nome do arquivo são derivados do próprio texto — o
        único dado que precisa ser dado é o corpo do fragmento (triagem de
        campo/tags fica pra depois, `triage_status: pending`).
        """
        if not await self._guard(update):
            return
        field = FRAGMENT_DEFAULT_FIELD
        if context.args:
            candidate = context.args[0]
            if candidate in FIELDS:
                field = candidate
            else:
                await self._reply_md(
                    update,
                    f"⚠️ Campo desconhecido: `{escape_md(candidate)}`\\. Usando `{escape_md(field)}`\\. "
                    f"Campos válidos: {escape_md(', '.join(sorted(FIELDS)))}",
                )
        context.user_data["awaiting_fragment_field"] = field
        await update.message.reply_text(f"Envie o texto do fragmento na próxima mensagem (campo: {field}).")

    async def cmd_newreference(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not await self._guard(update):
            return
        await self._start_flow(update, context, "newreference")
