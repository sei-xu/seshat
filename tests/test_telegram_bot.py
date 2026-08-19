"""Tests exercise SeshatTelegramBot's command handlers directly against a
temp vault, with fake Update/Context objects — no real Telegram network calls
(Application.build() with a bogus token does no I/O until polling starts)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from seshat.telegram.bot import SeshatTelegramBot

ALLOWED_USER = 111
OTHER_USER = 222


@pytest.fixture
def bot(tmp_path):
    for folder in ("01-Fragments", "02-Projects", "03-References", "seixu"):
        (tmp_path / folder).mkdir()
    return SeshatTelegramBot(tmp_path, telegram_token="123:fake-token", allowed_user_ids={ALLOWED_USER})


def make_update(user_id, args_text="", user_data=None):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args_text.split() if args_text else []
    context.user_data = user_data if user_data is not None else {}
    return update, context


def last_reply_text(update) -> str:
    args, kwargs = update.message.reply_text.call_args
    return args[0] if args else kwargs.get("text", "")


async def run_flow(bot, start_command, *answers, user_data=None):
    """Starts a guided write command and answers each of its questions in
    order, returning the final reply text."""
    user_data = {} if user_data is None else user_data
    update, context = make_update(ALLOWED_USER, user_data=user_data)
    await start_command(update, context)
    last_update = update
    for answer in answers:
        update, context = make_update(ALLOWED_USER, user_data=user_data)
        update.message.text = answer
        await bot.on_text(update, context)
        last_update = update
    return last_reply_text(last_update)


@pytest.mark.asyncio
async def test_unauthorized_user_blocked(bot):
    update, context = make_update(OTHER_USER)
    await bot.cmd_projects(update, context)
    assert "não está autorizado" in last_reply_text(update)


@pytest.mark.asyncio
async def test_newproject_then_projects_list(bot):
    reply = await run_flow(
        bot, bot.cmd_newproject, "202608", "teste", "Teste Bot", "s", "Programação", "comercial"
    )
    assert "criado" in reply

    update2, context2 = make_update(ALLOWED_USER)
    await bot.cmd_projects(update2, context2)
    body = last_reply_text(update2)
    assert "202608" in body and "teste" in body


@pytest.mark.asyncio
async def test_newproject_invalid_field_reasked(bot):
    reply = await run_flow(bot, bot.cmd_newproject, "202608", "teste", "Teste", "s", "NaoExiste")
    assert "Valor inválido" in reply


@pytest.mark.asyncio
async def test_newproject_can_be_cancelled(bot):
    user_data = {}
    update, context = make_update(ALLOWED_USER, user_data=user_data)
    await bot.cmd_newproject(update, context)
    assert "flow" in user_data

    update2, context2 = make_update(ALLOWED_USER, user_data=user_data)
    await bot.cmd_cancel(update2, context2)
    assert "Cancelado" in last_reply_text(update2)
    assert "flow" not in user_data


@pytest.mark.asyncio
async def test_project_detail_and_history_append(bot):
    await run_flow(bot, bot.cmd_newproject, "202608", "teste", "Teste", "s", "Programação", "comercial")

    reply = await run_flow(bot, bot.cmd_history, "202608_teste", "2026-08-19", "Início", "Primeira entrada")
    assert "histórico adicionada" in reply

    update3, context3 = make_update(ALLOWED_USER, "202608_teste")
    await bot.cmd_project(update3, context3)
    detail = last_reply_text(update3)
    assert "Início" in detail


@pytest.mark.asyncio
async def test_status_update(bot):
    await run_flow(bot, bot.cmd_newproject, "202608", "teste", "Teste", "s", "Programação", "comercial")

    reply = await run_flow(bot, bot.cmd_status, "202608_teste", "2026-08-19", "in_progress", "-", "-")
    assert "atualizado" in reply


@pytest.mark.asyncio
async def test_newreference_flow(bot):
    reply = await run_flow(
        bot, bot.cmd_newreference, "caligrafia", "x", "X", "resumo", "Caligrafia", "technique"
    )
    assert "criada" in reply
    assert bot.vault.exists("03-References/caligrafia/x.md")


@pytest.mark.asyncio
async def test_fragment_creation_via_followup_text(bot):
    user_data = {}
    update, context = make_update(ALLOWED_USER, user_data=user_data)
    await bot.cmd_fragment(update, context)
    assert "Envie o texto" in last_reply_text(update)
    assert user_data["awaiting_fragment_field"] == "Pessoal"

    update2, context2 = make_update(ALLOWED_USER, user_data=user_data)
    update2.message.text = "Ideia de logo\nresto do corpo"
    await bot.on_text(update2, context2)
    assert "criado" in last_reply_text(update2)
    assert "awaiting_fragment_field" not in user_data

    fragments = list((bot.vault.root / "01-Fragments").glob("*.md"))
    assert len(fragments) == 1
    assert fragments[0].read_text().startswith("---")


@pytest.mark.asyncio
async def test_fragment_creation_with_field_argument(bot):
    user_data = {}
    update, context = make_update(ALLOWED_USER, "Programação", user_data=user_data)
    await bot.cmd_fragment(update, context)
    assert user_data["awaiting_fragment_field"] == "Programação"

    update2, context2 = make_update(ALLOWED_USER, user_data=user_data)
    update2.message.text = "nota técnica raríssima"
    await bot.on_text(update2, context2)
    assert "criado" in last_reply_text(update2)


@pytest.mark.asyncio
async def test_search_free_text(bot):
    user_data = {}
    update, context = make_update(ALLOWED_USER, user_data=user_data)
    await bot.cmd_fragment(update, context)

    update2, context2 = make_update(ALLOWED_USER, user_data=user_data)
    update2.message.text = "corpo raro do fragmento"
    await bot.on_text(update2, context2)

    update3, context3 = make_update(ALLOWED_USER, user_data=user_data)
    update3.message.text = "raro"
    await bot.on_text(update3, context3)
    assert "resultado" in last_reply_text(update3)
