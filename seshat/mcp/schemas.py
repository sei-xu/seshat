"""Tool schemas for MCP/Claude integration.

Defines the 9 Seshat tools in JSON Schema format, compatible with Claude's tool_use.
"""

from __future__ import annotations

TOOL_SCHEMAS = {
    "list_projects": {
        "name": "list_projects",
        "description": "List projects in the vault, optionally filtered by field, status, or stage",
        "input_schema": {
            "type": "object",
            "properties": {
                "field": {
                    "type": "string",
                    "description": "Filter by field (e.g., Programação, Design, Pessoal)",
                    "enum": [
                        "Programação",
                        "Artes",
                        "Design",
                        "Caligrafia",
                        "Costura",
                        "Pesquisa",
                        "Pessoal",
                        "Imagem",
                        "Som",
                        "Textos",
                    ],
                },
                "project_status": {
                    "type": "string",
                    "description": "Filter by project status",
                    "enum": ["planning", "todo", "in_progress", "in_review", "done", "paused", "cancelled"],
                },
                "project_stage": {
                    "type": "string",
                    "description": "Filter by project stage",
                    "enum": ["call", "quote", "planning", "production", "delivered"],
                },
            },
        },
    },
    "get_project": {
        "name": "get_project",
        "description": "Get detailed information about a specific project including its history",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug (folder name in 02-Projects)",
                }
            },
            "required": ["slug"],
        },
    },
    "create_project": {
        "name": "create_project",
        "description": "Create a new project with index and empty history",
        "input_schema": {
            "type": "object",
            "properties": {
                "year_month": {
                    "type": "string",
                    "description": "Project year-month in YYYYMM format",
                    "pattern": "^\\d{6}$",
                },
                "slug": {
                    "type": "string",
                    "description": "Project slug (used in folder name)",
                },
                "title": {
                    "type": "string",
                    "description": "Project title",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief project summary",
                },
                "field": {
                    "type": "string",
                    "description": "Project field",
                    "enum": [
                        "Programação",
                        "Artes",
                        "Design",
                        "Caligrafia",
                        "Costura",
                        "Pesquisa",
                        "Pessoal",
                        "Imagem",
                        "Som",
                        "Textos",
                    ],
                },
                "project_type": {
                    "type": "string",
                    "description": "Type of project (e.g., comercial, pessoal)",
                },
                "project_status": {
                    "type": "string",
                    "description": "Initial project status (default: planning)",
                    "enum": ["planning", "todo", "in_progress", "in_review", "done", "paused", "cancelled"],
                },
                "project_stage": {
                    "type": "string",
                    "description": "Initial project stage (default: call)",
                    "enum": ["call", "quote", "planning", "production", "delivered"],
                },
                "khaos_project_id": {
                    "type": "string",
                    "description": "Optional external project ID from Khaos",
                },
            },
            "required": ["year_month", "slug", "title", "summary", "field", "project_type"],
        },
    },
    "append_history": {
        "name": "append_history",
        "description": "Add an entry to a project's history timeline",
        "input_schema": {
            "type": "object",
            "properties": {
                "history_relative_path": {
                    "type": "string",
                    "description": "Path to 01_history.md (e.g., 02-Projects/202608_slug/01_history.md)",
                },
                "date": {
                    "type": "string",
                    "description": "Date in YYYY-MM-DD format",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                },
                "title": {
                    "type": "string",
                    "description": "History entry title",
                },
                "summary_line": {
                    "type": "string",
                    "description": "Summary text for the entry",
                },
            },
            "required": ["history_relative_path", "date", "title", "summary_line"],
        },
    },
    "create_fragment": {
        "name": "create_fragment",
        "description": "Create a new fragment (short note) in the vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Fragment slug (folder or file name)",
                },
                "title": {
                    "type": "string",
                    "description": "Fragment title",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief fragment summary",
                },
                "field": {
                    "type": "string",
                    "description": "Fragment field",
                    "enum": [
                        "Programação",
                        "Artes",
                        "Design",
                        "Caligrafia",
                        "Costura",
                        "Pesquisa",
                        "Pessoal",
                        "Imagem",
                        "Som",
                        "Textos",
                    ],
                },
                "body": {
                    "type": "string",
                    "description": "Fragment body content",
                },
                "type": {
                    "type": "string",
                    "description": "Fragment type (e.g., technique, reading-notes, undefined)",
                },
                "triage_status": {
                    "type": "string",
                    "description": "Triage status (default: pending)",
                    "enum": ["pending", "deferred", "waiting"],
                },
            },
            "required": ["slug", "title", "summary", "field", "body"],
        },
    },
    "list_references": {
        "name": "list_references",
        "description": "List references in the vault, optionally filtered by type",
        "input_schema": {
            "type": "object",
            "properties": {
                "reference_type": {
                    "type": "string",
                    "description": "Filter by reference type (e.g., technique, document)",
                }
            },
        },
    },
    "create_reference": {
        "name": "create_reference",
        "description": "Create a new reference entry in the vault",
        "input_schema": {
            "type": "object",
            "properties": {
                "area": {
                    "type": "string",
                    "description": "Reference area/category (used in folder path)",
                },
                "slug": {
                    "type": "string",
                    "description": "Reference slug",
                },
                "title": {
                    "type": "string",
                    "description": "Reference title",
                },
                "summary": {
                    "type": "string",
                    "description": "Brief reference summary",
                },
                "field": {
                    "type": "string",
                    "description": "Reference field",
                    "enum": [
                        "Programação",
                        "Artes",
                        "Design",
                        "Caligrafia",
                        "Costura",
                        "Pesquisa",
                        "Pessoal",
                        "Imagem",
                        "Som",
                        "Textos",
                    ],
                },
                "reference_type": {
                    "type": "string",
                    "description": "Reference type",
                },
                "as_folder": {
                    "type": "boolean",
                    "description": "Create as folder (index + empty history) or flat file (default: false)",
                },
                "body": {
                    "type": "string",
                    "description": "Reference body content (for flat file format)",
                },
            },
            "required": ["area", "slug", "title", "summary", "field", "reference_type"],
        },
    },
    "update_project_status": {
        "name": "update_project_status",
        "description": "Update a project's status and/or stage, appending a history entry",
        "input_schema": {
            "type": "object",
            "properties": {
                "slug": {
                    "type": "string",
                    "description": "Project slug",
                },
                "project_status": {
                    "type": "string",
                    "description": "New project status",
                    "enum": ["planning", "todo", "in_progress", "in_review", "done", "paused", "cancelled"],
                },
                "project_stage": {
                    "type": "string",
                    "description": "New project stage",
                    "enum": ["call", "quote", "planning", "production", "delivered"],
                },
                "date": {
                    "type": "string",
                    "description": "Date for history entry (YYYY-MM-DD)",
                    "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                },
                "title": {
                    "type": "string",
                    "description": "History entry title",
                },
                "summary_line": {
                    "type": "string",
                    "description": "History entry summary",
                },
            },
            "required": ["slug", "date", "title", "summary_line"],
        },
    },
    "search_vault": {
        "name": "search_vault",
        "description": "Search vault notes by query, field, category, or tags",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Text to search in titles and bodies (case-insensitive substring match)",
                },
                "field": {
                    "type": "string",
                    "description": "Filter by field",
                    "enum": [
                        "Programação",
                        "Artes",
                        "Design",
                        "Caligrafia",
                        "Costura",
                        "Pesquisa",
                        "Pessoal",
                        "Imagem",
                        "Som",
                        "Textos",
                    ],
                },
                "category": {
                    "type": "string",
                    "description": "Filter by category",
                    "enum": ["project", "reference", "fragment"],
                },
                "tags": {
                    "type": "array",
                    "description": "Filter by tags (all must match)",
                    "items": {"type": "string"},
                },
                "max_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default: 50)",
                    "minimum": 1,
                    "maximum": 500,
                },
            },
        },
    },
}


def get_tool_schemas() -> list[dict]:
    """Return tool schemas as a list (format for Claude/MCP)."""
    return list(TOOL_SCHEMAS.values())


def get_tool_schema(tool_name: str) -> dict | None:
    """Get schema for a specific tool."""
    return TOOL_SCHEMAS.get(tool_name)
