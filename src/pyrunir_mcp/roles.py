from __future__ import annotations

import os
from dataclasses import dataclass


KR_PS_BASE_TOOLS = frozenset({"runir.ps.base.prove_sketch_policy", "runir.ps.base.execute_policy", "runir.ps.base.reformat_policy"})
KR_PS_EXT_TOOLS = frozenset({"runir.ps.ext.prove_module_program", "runir.ps.ext.prove_termination", "runir.ps.ext.execute_module_program", "runir.ps.ext.reformat_module_program"})
KR_UNS_TOOLS = frozenset({"runir.uns.prove_classifier", "runir.uns.reformat_classifier"})
ALL_TOOLS = KR_PS_BASE_TOOLS | KR_PS_EXT_TOOLS | KR_UNS_TOOLS

ROLE_TOOLS = {
    "kr/ps/base": KR_PS_BASE_TOOLS,
    "kr.ps.base": KR_PS_BASE_TOOLS,
    "kr/ps/ext": KR_PS_EXT_TOOLS,
    "kr.ps.ext": KR_PS_EXT_TOOLS,
    "kr/uns": KR_UNS_TOOLS,
    "kr.uns": KR_UNS_TOOLS,
    "all": ALL_TOOLS,
}


@dataclass(frozen=True)
class Role:
    name: str
    allowed_tools: frozenset[str]

    def allows(self, tool_name: str) -> bool:
        return tool_name in self.allowed_tools


def load_role() -> Role:
    name = os.environ.get("PYRUNIR_MCP_ROLE", "all")
    try:
        allowed_tools = ROLE_TOOLS[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(ROLE_TOOLS))
        raise ValueError(f"Unknown PYRUNIR_MCP_ROLE: {name}. Expected one of: {allowed}") from exc
    return Role(name=name, allowed_tools=allowed_tools)
