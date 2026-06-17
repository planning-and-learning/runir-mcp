from __future__ import annotations

import json

from pyrunir_mcp.kr.ps.ext.termination.service import TOOL_NAME
from pyrunir_mcp.artifacts import write_native_counterexample_run


def test_prove_termination_summary_links_counterexample_files(tmp_path):
    result = write_native_counterexample_run(
        tool=TOOL_NAME,
        status="failure",
        output_dir=tmp_path,
        metadata={
            "domain": "domain.pddl",
            "module_program_file": "module_program.txt",
            "program_status": "NON_TERMINATING",
            "terminating": False,
            "recursive_call_rules": ["rule"],
            "modules": [{"module": "main", "status": "NON_TERMINATING", "terminating": False}],
        },
        counterexamples=[
            {
                "category": "structural_termination",
                "module": "main",
                "task": "main",
                "counterexample": {
                    "num_vertices": 1,
                    "num_edges": 1,
                    "vertices": [{"index": 0, "memory_state": "0"}],
                    "edges": [{"index": 0, "source": 0, "target": 0, "rule": "rule"}],
                },
            }
        ],
    )

    assert result["counts"] == {
        "counterexamples": 1,
        "categories": 1,
        "tasks_with_counterexamples": 1,
    }
    summary = json.loads((tmp_path / "summary.json").read_text())
    item = summary["by_category"]["structural_termination"]["items"][0]
    counterexample = json.loads((tmp_path / item["path"]).read_text())
    assert counterexample["module"] == "main"
    assert counterexample["counterexample"]["num_edges"] == 1
