"""更新 config.yaml 的數值，同時保留原本的中文註解與排版。

config.yaml 只有兩層（區塊 → 欄位），所以逐行找到「區塊下的欄位」，只換掉冒號後面的值，
後面的 # 註解原封不動。檔案裡沒有的欄位會加在該區塊最後；沒有的區塊會加在檔案最後。
"""

from __future__ import annotations

import re
from typing import Any, Dict

import yaml

_TOP = re.compile(r"^([A-Za-z_][\w]*)\s*:(.*)$")
_SUB = re.compile(r"^(\s+)([A-Za-z_][\w]*)(\s*:\s*)(.*)$")


def format_value(value: Any) -> str:
    """把 Python 值寫成一行 YAML。"""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        text = f"{value:.4f}".rstrip("0")
        return text + "0" if text.endswith(".") else text
    if isinstance(value, int):
        return str(value)
    return yaml.safe_dump(str(value), allow_unicode=True, default_flow_style=True).strip().removesuffix("...").strip()


def _split_comment(rest: str):
    """把「值  # 註解」拆成值和註解（含前面的空白）。字串值裡的 # 不算註解。"""
    in_quote = None
    for i, ch in enumerate(rest):
        if in_quote:
            if ch == in_quote:
                in_quote = None
        elif ch in ("'", '"'):
            in_quote = ch
        elif ch == "#" and (i == 0 or rest[i - 1].isspace()):
            j = i
            while j > 0 and rest[j - 1].isspace():
                j -= 1
            return rest[:j], rest[j:]
    return rest.rstrip(), ""


def update_yaml_text(text: str, data: Dict[str, Any]) -> str:
    """data：{區塊: {欄位: 值}}，或 {頂層欄位: 值}（例如 show_preview）。"""
    lines = text.splitlines()
    pending = {k: (dict(v) if isinstance(v, dict) else v) for k, v in data.items()}
    section = None
    section_end: Dict[str, int] = {}   # 區塊最後一個欄位所在行
    indent: Dict[str, str] = {}

    for i, line in enumerate(lines):
        m = _TOP.match(line)
        if m:
            section = m.group(1)
            if section in pending and not isinstance(pending[section], dict):
                value, comment = _split_comment(m.group(2))
                lines[i] = f"{section}: {format_value(pending.pop(section))}{comment}"
                section = None
            else:
                section_end[section] = i
            continue
        m = _SUB.match(line)
        if m and section is not None:
            section_end[section] = i
            indent.setdefault(section, m.group(1))
            sec = pending.get(section)
            key = m.group(2)
            if isinstance(sec, dict) and key in sec:
                _, comment = _split_comment(m.group(4))
                lines[i] = f"{m.group(1)}{key}{m.group(3)}{format_value(sec.pop(key))}{comment}"

    # 檔案裡還沒有的欄位：插在區塊最後（從後面往前插，行號才不會亂）
    inserts = []
    for sec, values in pending.items():
        if isinstance(values, dict) and values and sec in section_end:
            ind = indent.get(sec, "  ")
            inserts.append((section_end[sec], [f"{ind}{k}: {format_value(v)}" for k, v in values.items()]))
    for pos, new_lines in sorted(inserts, reverse=True):
        lines[pos + 1:pos + 1] = new_lines

    for sec, values in pending.items():
        if isinstance(values, dict):
            if values and sec not in section_end:
                lines.append(f"{sec}:")
                lines.extend(f"  {k}: {format_value(v)}" for k, v in values.items())
        else:
            lines.append(f"{sec}: {format_value(values)}")

    return "\n".join(lines) + ("\n" if text.endswith("\n") or not text else "")
