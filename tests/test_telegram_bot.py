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


def make_update(user_id, args_text=""):
    update = MagicMock()
    update.effective_user.id = user_id
    update.message.reply_text = AsyncMock()
    context = MagicMock()
    context.args = args_text.split() if args_text else []
    return update, context


def last_reply_text(update) -> str:
    args, kwargs = update.message.reply_text.call_args
    return args[0] if args else kwargs.get("text", "")


@pytest.mark.asyncio
async def test_unauthorized_user_blocked(bot):
    update, context = make_update(OTHER_USER)
    await bot.cmd_projects(update, context)
    assert "não está autorizado" in last_reply_text(update)


@pytest.mark.asyncio
async def test_newproject_then_projects_list(bot):
    update, context = make_update(
        ALLOWED_USER,
        'year_month=202608 slug=teste title="Teste Bot" summary="s" field=Programação type=comercial',
    )
    await bot.cmd_newproject(update, context)
    assert "criado" in last_reply_text(update)

    update2, context2 = make_update(ALLOWED_USER)
    await bot.cmd_projects(update2, context2)
    body = last_reply_text(update2)
    assert "202608" in body and "teste" in body


@pytest.mark.asyncio
async def test_newproject_missing_args_reports_error(bot):
    update, context = make_update(ALLOWED_USER, "slug=teste")
    await bot.cmd_newproject(update, context)
    assert "Erro" in last_reply_text(update)


@pytest.mark.asyncio
async def test_project_detail_and_history_append(bot):
    update, context = make_update(
        ALLOWED_USER,
        'year_month=202608 slug=teste title="Teste" summary="s" field=Programação type=comercial',
    )
    await bot.cmd_newproject(update, context)

    update2, context2 = make_update(
        ALLOWED_USER,
        'slug=202608_teste date=2026-08-19 title="Início" summary="Primeira entrada"',
    )
    await bot.cmd_history(update2, context2)
    assert "histórico adicionada" in last_reply_text(update2)

    update3, context3 = make_update(ALLOWED_USER, "202608_teste")
    await bot.cmd_project(update3, context3)
    detail = last_reply_text(update3)
    assert "Início" in detail


@pytest.mark.asyncio
async def test_status_update(bot):
    update, context = make_update(
        ALLOWED_USER,
        'year_month=202608 slug=teste title="Teste" summary="s" field=Programação type=comercial',
    )
    await bot.cmd_newproject(update, context)

    update2, context2 = make_update(
        ALLOWED_USER, "slug=202608_teste date=2026-08-19 project_status=in_progress"
    )
    await bot.cmd_status(update2, context2)
    assert "atualizado" in last_reply_text(update2)


@pytest.mark.asyncio
async def test_fragment_creation(bot):
    update, context = make_update(
        ALLOWED_USER,
        'filename_slug=nota title="Nota" summary="s" field=Programação body="corpo"',
    )
    await bot.cmd_fragment(update, context)
    assert "criado" in last_reply_text(update)
    assert bot.vault.exists("01-Fragments/nota.md")


@pytest.mark.asyncio
async def test_search_free_text(bot):
    update, context = make_update(
        ALLOWED_USER,
        'filename_slug=nota title="Nota especial" summary="s" field=Programação body="corpo raro"',
    )
    await bot.cmd_fragment(update, context)

    update2, context2 = make_update(ALLOWED_USER)
    update2.message.text = "raro"
    await bot.on_text(update2, context2)
    assert "resultado" in last_reply_text(update2)
