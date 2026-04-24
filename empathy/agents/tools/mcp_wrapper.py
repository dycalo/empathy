"""MCP tools wrapper - convert MCP tools to LangChain format."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from langchain_core.tools import StructuredTool
from pydantic import create_model

if TYPE_CHECKING:
    from empathy.extensions.mcp import McpProvider


def create_mcp_tools(mcp_provider: McpProvider) -> list[StructuredTool]:
    """Create LangChain tools from MCP provider.

    Args:
        mcp_provider: MCP provider with loaded tools

    Returns:
        List of LangChain StructuredTool instances
    """
    tools = []
    tool_defs = mcp_provider.tool_params()

    for tool_def in tool_defs:
        tool = create_mcp_langchain_tool(tool_def, mcp_provider)
        tools.append(tool)

    return tools


def create_mcp_langchain_tool(
    tool_def: dict[str, Any], mcp_provider: McpProvider
) -> StructuredTool:
    """Create a single LangChain tool from MCP tool definition.

    Args:
        tool_def: MCP tool definition
        mcp_provider: MCP provider for invoking the tool

    Returns:
        LangChain StructuredTool
    """

    def mcp_tool_func(**kwargs: Any) -> str:
        """Invoke MCP tool."""
        return asyncio.run(mcp_provider.invoke_tool(tool_def["name"], kwargs))

    # Create Pydantic model from input schema
    args_schema = create_model_from_schema(tool_def["input_schema"])

    return StructuredTool.from_function(
        func=mcp_tool_func,
        name=tool_def["name"],
        description=tool_def["description"],
        args_schema=args_schema,
    )


def create_model_from_schema(schema: dict[str, Any]) -> type:
    """Create a Pydantic model from JSON schema.

    Args:
        schema: JSON schema dict

    Returns:
        Pydantic model class
    """
    from pydantic import Field

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    fields = {}
    for prop_name, prop_def in properties.items():
        field_type = _json_type_to_python(prop_def.get("type", "string"))
        is_required = prop_name in required
        default = ... if is_required else None

        fields[prop_name] = (
            field_type,
            Field(default=default, description=prop_def.get("description", "")),
        )

    return create_model("DynamicMcpInput", **fields)


def _json_type_to_python(json_type: str) -> type:
    """Convert JSON schema type to Python type.

    Args:
        json_type: JSON schema type string

    Returns:
        Python type
    """
    type_map = {
        "string": str,
        "number": float,
        "integer": int,
        "boolean": bool,
        "array": list,
        "object": dict,
    }
    return type_map.get(json_type, str)
