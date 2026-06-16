from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .models import DesignModel, NodeModel, TestModel


@dataclass
class RawBlock:
    name: str
    values: dict[str, str] = field(default_factory=dict)
    children: list["RawBlock"] = field(default_factory=list)
    # For blocks with repeated keys (e.g., Shape with multiple PointX/PointY)
    raw_lines: list[str] = field(default_factory=list)


def _strip_quote(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1]
    return value


def parse_blocks(text: str) -> RawBlock:
    root = RawBlock(name="ROOT")
    stack: list[RawBlock] = [root]

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        if line.startswith("$begin"):
            block_name = _strip_quote(line[len("$begin") :].strip())
            new_block = RawBlock(name=block_name)
            stack[-1].children.append(new_block)
            stack.append(new_block)
            continue

        if line.startswith("$end"):
            end_name = _strip_quote(line[len("$end") :].strip())
            if len(stack) == 1:
                raise ValueError(f"Unexpected $end {end_name}")
            if stack[-1].name != end_name:
                raise ValueError(f"Mismatched block end: expected {stack[-1].name}, got {end_name}")
            stack.pop()
            continue

        if "=" in line:
            key, value = line.split("=", 1)
            stack[-1].values[key.strip()] = value.strip()
            stack[-1].raw_lines.append(line)

    if len(stack) != 1:
        raise ValueError("Unclosed block detected in DoSA file")

    return root


def _to_node(block: RawBlock) -> NodeModel:
    node_name = block.values.get("NodeName", "")
    return NodeModel(
        kind=block.name,
        name=node_name,
        properties=dict(block.values),
        children=[_to_node(child) for child in block.children],
        raw_lines=list(block.raw_lines),
    )


def _collect_parts(nodes: list[NodeModel]) -> list[NodeModel]:
    part_kinds = {"Coil", "Magnet", "Steel", "Non-Kind"}
    output: list[NodeModel] = []
    for node in nodes:
        if node.kind in part_kinds:
            output.append(node)
        output.extend(_collect_parts(node.children))
    return output


def _collect_tests(nodes: list[NodeModel]) -> list[TestModel]:
    test_kinds = {"Force Test", "Stroke Test", "Current Test", "Force-Test", "Stroke-Test", "Current-Test"}
    output: list[TestModel] = []
    for node in nodes:
        if node.kind in test_kinds or node.properties.get("KindKey", "").endswith("_TEST"):
            output.append(TestModel(name=node.name or node.kind, kind=node.kind, properties=dict(node.properties)))
        output.extend(_collect_tests(node.children))
    return output


def parse_dosa_file(file_path: str | Path) -> DesignModel:
    path = Path(file_path)
    text = path.read_text(encoding="utf-8", errors="ignore")
    tree = parse_blocks(text)

    nodes = [_to_node(child) for child in tree.children]

    design_name = ""
    for node in nodes:
        if node.kind.lower() == "design":
            design_name = node.properties.get("NodeName", "")
            break

    source_type = "dsa3d" if path.suffix.lower() == ".dsa3d" else "dsa"

    return DesignModel(
        name=design_name,
        source_file=str(path),
        source_type=source_type,
        nodes=nodes,
        parts=_collect_parts(nodes),
        tests=_collect_tests(nodes),
    )
