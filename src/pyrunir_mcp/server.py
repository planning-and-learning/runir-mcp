from __future__ import annotations

from typing import Protocol, TypeAlias

from fastmcp import FastMCP

from pyrunir_mcp.config import ServerConfig, load_config
from pyrunir_mcp.kr.ps.base.tools import TOOL_NAME as PROVE_SKETCH_TOOL
from pyrunir_mcp.kr.ps.base.tools import register_tools as register_ps_base_tools
from pyrunir_mcp.kr.ps.base.execute.tools import TOOL_NAME as EXECUTE_BASE_TOOL
from pyrunir_mcp.kr.ps.base.execute.tools import register_tools as register_base_execute_tools
from pyrunir_mcp.kr.ps.base.reformat.tools import TOOL_NAME as REFORMAT_BASE_TOOL
from pyrunir_mcp.kr.ps.base.reformat.tools import register_tools as register_base_reformat_tools
from pyrunir_mcp.kr.ps.ext.tools import TOOL_NAME as PROVE_MODULE_TOOL
from pyrunir_mcp.kr.ps.ext.tools import register_tools as register_ps_ext_tools
from pyrunir_mcp.kr.ps.ext.execute.tools import TOOL_NAME as EXECUTE_MODULE_TOOL
from pyrunir_mcp.kr.ps.ext.execute.tools import register_tools as register_ext_execute_tools
from pyrunir_mcp.kr.ps.ext.reformat.tools import TOOL_NAME as REFORMAT_MODULE_TOOL
from pyrunir_mcp.kr.ps.ext.reformat.tools import register_tools as register_ext_reformat_tools
from pyrunir_mcp.kr.ps.ext.termination.tools import TOOL_NAME as PROVE_TERMINATION_TOOL
from pyrunir_mcp.kr.ps.ext.termination.tools import register_tools as register_termination_tools
from pyrunir_mcp.kr.uns.tools import TOOL_NAME as PROVE_CLASSIFIER_TOOL
from pyrunir_mcp.kr.uns.tools import register_tools as register_uns_tools
from pyrunir_mcp.kr.uns.reformat.tools import TOOL_NAME as REFORMAT_CLASSIFIER_TOOL
from pyrunir_mcp.kr.uns.reformat.tools import register_tools as register_uns_reformat_tools
from pyrunir_mcp.roles import Role, load_role

ServerInfo: TypeAlias = dict[str, str | list[str]]


class Registrar(Protocol):
    def __call__(self, mcp: FastMCP, config: ServerConfig) -> None: ...


REGISTRARS: dict[str, Registrar] = {
    PROVE_SKETCH_TOOL: register_ps_base_tools,
    EXECUTE_BASE_TOOL: register_base_execute_tools,
    REFORMAT_BASE_TOOL: register_base_reformat_tools,
    PROVE_MODULE_TOOL: register_ps_ext_tools,
    EXECUTE_MODULE_TOOL: register_ext_execute_tools,
    REFORMAT_MODULE_TOOL: register_ext_reformat_tools,
    PROVE_TERMINATION_TOOL: register_termination_tools,
    PROVE_CLASSIFIER_TOOL: register_uns_tools,
    REFORMAT_CLASSIFIER_TOOL: register_uns_reformat_tools,
}


def create_server(config: ServerConfig | None = None, role: Role | None = None) -> FastMCP:
    config = config or load_config()
    role = role or load_role()
    mcp = FastMCP("pyrunir-mcp")

    for tool_name, register in REGISTRARS.items():
        if role.allows(tool_name):
            register(mcp, config)

    @mcp.tool(name="pyrunir_mcp.server_info")
    def server_info() -> ServerInfo:
        return {
            "name": "pyrunir-mcp",
            "role": role.name,
            "allowed_tools": sorted(role.allowed_tools),
            "workspace_root": config.workspace_root.as_posix(),
            "output_root": config.output_root.as_posix(),
        }

    return mcp


def main() -> None:
    create_server().run()


if __name__ == "__main__":
    main()
