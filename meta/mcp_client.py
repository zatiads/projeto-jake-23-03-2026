"""Cliente HTTP para o Meta MCP Server (localhost:5051)."""
import requests


def chamar_mcp_tool(tool_name: str, args: dict) -> dict:
    """Chama o Meta MCP Server em localhost:5051. Retorna {"ok": bool, ...}."""
    try:
        r = requests.post(
            "http://localhost:5051/call",
            json={"tool": tool_name, "args": args},
            timeout=5,
        )
        return r.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}
