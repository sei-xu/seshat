# Seshat

Agente arquivista do ecossistema Seîxu — lê e escreve markdown no vault Akasha, transformando decisões e itens encerrados em registros permanentes e pesquisáveis. Ver a documentação completa em `seixu/seshat/` e `seixu/akasha/` dentro do próprio vault Akasha (fora deste repositório).

## Estado atual: Fase 3 do roadmap (ferramentas completas, ainda sem servidor/deploy)

Todas as 9 ferramentas de leitura/escrita do `seshat/core/` estão implementadas e testadas localmente contra um vault de teste (fixture `tests/conftest.py`) — ainda sem servidor MCP, sem deploy na VPS, sem bot. A Fase 3 completa (protocolo de sincronização git, servidor HTTP/SSE, deploy na Render) fica pra uma próxima etapa, por decisão explícita de fazer um passo de cada vez.

Pacote instalável se chama `seshat` (bate com o nome do repositório); `core/` é o submódulo de lógica de negócio dentro dele — deixa espaço pra submódulos irmãos nas próximas fases (`seshat/mcp/`, `seshat/telegram/`, etc.), sem repetir "seshat" no nome do módulo.

Ferramentas implementadas:

| Ferramenta | Arquivo | Fase |
|---|---|---|
| `list_projects` | `seshat/core/tools/list_projects.py` | 2 |
| `get_project` | `seshat/core/tools/get_project.py` | 2 |
| `create_project` | `seshat/core/tools/create_project.py` | 2 |
| `append_history` | `seshat/core/tools/append_history.py` | 2 |
| `create_fragment` | `seshat/core/tools/create_fragment.py` | 2 |
| `list_references` | `seshat/core/tools/list_references.py` | 3 |
| `create_reference` | `seshat/core/tools/create_reference.py` | 3 |
| `update_project_status` | `seshat/core/tools/update_project_status.py` | 3 |
| `search_vault` | `seshat/core/tools/search_vault.py` | 3 |

Fora do escopo ainda: os comportamentos ativos (`suggest_technique_promotion`, `suggest_undefined_promotion`, `suggest_decade_numbering`, `suggest_fragment_triage`), servidor MCP exposto via HTTP/SSE, deploy na VPS, protocolo de sincronização git, bot do Telegram.

### Notas de implementação — Fase 3

- **`create_reference`**: cobre os dois formatos definidos em `22_estrutura_pastas.md` — arquivo único direto em `03-References/<área>/<slug>.md` (`as_folder=False`, default) ou pasta completa com `00_index.md`+`01_history.md` vazio (`as_folder=True`), mesmo padrão de "histórico não fabricado" do `create_project`.
- **`list_references`**: ao varrer uma referência em formato-pasta, lista só o `00_index.md` — os passos numerados (`10_x.md`, `11_x.md`) ficam de fora, igual `list_projects` já faz com o conteúdo de um projeto.
- **`update_project_status`**: nunca muda `project_status`/`project_stage` silenciosamente — toda chamada bem-sucedida grava uma entrada em `01_history.md` via `append_history` (regenera o gantt inteiro). Rejeita chamada sem mudança real de valor.
- **`search_vault`**: busca literal (substring case-insensitive em título/resumo/corpo) + filtro por tag/field/category — sem ranking, sem embeddings. Cobre a mesma superfície descrita em `10_arquitetura_seshat.md` ("Não há hoje um componente de busca semântica separado").

## Estrutura

```
seshat/
  __init__.py
  core/
    schema.py    validação do vocabulário fechado do frontmatter (category, field,
                 project_status, project_stage, triage_status, type, ai_access, status)
                 + geração de id/timestamps na escrita
    vault.py     VaultClient — leitura/escrita de notas markdown+frontmatter no disco,
                 nunca sobrescreve sem overwrite=True explícito
    history.py   parsing e geração de 01_history.md — timeline (mais nova primeiro no
                 texto) + bloco mermaid gantt (mais antiga primeiro, um milestone por
                 entrada), regenerado inteiro a cada append_history
    tools/       as 9 ferramentas (Fase 2 + Fase 3), uma função pura por arquivo
tests/           pytest contra um vault de teste temporário (fixture `vault` em conftest.py)
```

## Decisões de schema espelhadas deste repo

Fonte da verdade é o vault Akasha (`seixu/akasha/20_frontmatter_schema.md`, `21_vocabulario_type.md`, `22_estrutura_pastas.md`). Qualquer mudança de vocabulário nesses documentos precisa ser replicada em `seshat/core/schema.py` — não há sincronização automática ainda (isso seria material pra uma ferramenta futura, não existe hoje).

Duas lacunas que os documentos do vault deixam em aberto e que este código precisou decidir sozinho (marcadas com comentário no código, revisar quando a documentação formalizar):

- **`ai_access`**: o schema chama de "vocabulário fechado" mas não enumera os valores. Assumi `{read_write, read_only}`.
- **Convenção de `id` gerado automaticamente**: o schema só diz "gerar `id` automaticamente se ausente", sem algoritmo. Inferi o padrão `<field-slug>-<category>-<slug>` a partir de exemplos reais já existentes no vault (`ref-konnyaku-nori`, `pessoal-fragment-cuba-da-cozinha`).

## Rodando localmente

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Smoke test manual (cria um projeto de verdade num vault temporário, imprime o `01_history.md` gerado):

```bash
python3 -c "
from seshat.core import VaultClient
from seshat.core.tools import create_project, append_history

import tempfile, pathlib
root = pathlib.Path(tempfile.mkdtemp())
for f in ('01-Fragments', '02-Projects', '03-References', 'seixu'):
    (root / f).mkdir()

vault = VaultClient(root)
r = create_project(vault, year_month='202608', slug='teste', title='Teste',
                    summary='s', field='Programação', project_type='comercial')
append_history(vault, history_relative_path=f\"02-Projects/{r['slug']}/01_history.md\",
                date='2026-08-14', title='Início', summary_line='Primeira entrada.')
print((root / '02-Projects' / r['slug'] / '01_history.md').read_text())
"
```

## Próximos passos (restante da Fase 3 do roadmap)

MCP server rodando na VPS (Render), com clone git do vault, autenticação por API key, e o protocolo de sincronização (`seixu/seshat/11_git_conflitos.md`) implementado e testado — incluindo o caso de conflito forçado propositalmente, pra confirmar que a Seshat recusa e avisa em vez de tentar resolver.
