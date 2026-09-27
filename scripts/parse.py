"""
Парсер экспорта DeepSeek.
Читает JSON, обходит дерево mapping, отдаёт плоские структуры.
Сухой прогон — без записи в БД.
"""
import json
from collections import Counter


def extract_fragments(message: dict) -> list[dict]:
    if not message:
        return []
    frags = message.get("fragments") or []
    result = []
    for i, f in enumerate(frags):
        result.append({
            "type": f.get("type"),
            "content": f.get("content") or "",
            "position": i,
        })
    return result


def define_role(fragments: list[dict]) -> str:
    types = {f["type"] for f in fragments}
    if "REQUEST" in types:
        return "user"
    if "RESPONSE" in types:
        return "assistant"
    if "THINK" in types:
        return "assistant"
    if types & {"TOOL_SEARCH", "TOOL_OPEN", "SEARCH", "FILE"}:
        return "tool"
    return "unknown"


def walk_tree(mapping: dict) -> list[tuple[str, dict, bool]]:
    if "root" not in mapping:
        return []

    result = []
    queue = [("root", False)]
    visited = set()

    while queue:
        node_id, is_branch = queue.pop(0)
        if node_id in visited:
            continue
        visited.add(node_id)

        node = mapping.get(node_id)
        if not node:
            continue

        result.append((node_id, node, is_branch))

        children = node.get("children") or []
        for i, child_id in enumerate(children):
            queue.append((child_id, is_branch or i > 0))

    return result


def parse_conversation(conv: dict, source_file: str) -> dict:
    mapping = conv.get("mapping") or {}
    walked = walk_tree(mapping)

    messages = []
    position = 0

    for node_id, node, is_branch in walked:
        msg = node.get("message")
        if not msg:
            continue

        fragments = extract_fragments(msg)
        if not fragments:
            continue

        messages.append({
            "node_id": node_id,
            "parent_node_id": node.get("parent"),
            "role": define_role(fragments),
            "model": msg.get("model"),
            "inserted_at": msg.get("inserted_at"),
            "position": position,
            "is_branch": is_branch,
            "fragments": fragments,
        })
        position += 1

    return {
        "id": conv.get("id"),
        "title": conv.get("title"),
        "inserted_at": conv.get("inserted_at"),
        "updated_at": conv.get("updated_at"),
        "source_file": source_file,
        "raw_mapping": mapping,
        "messages": messages,
    }


def main():
    source_file = "21092026.json"
    with open(source_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"Загружено диалогов: {len(data)}")

    total_messages = 0
    total_fragments = 0
    roles = Counter()
    frag_types = Counter()
    empty_conv = 0
    branch_msgs = 0

    for conv in data:
        parsed = parse_conversation(conv, source_file)
        if not parsed["messages"]:
            empty_conv += 1
        total_messages += len(parsed["messages"])
        for m in parsed["messages"]:
            roles[m["role"]] += 1
            if m["is_branch"]:
                branch_msgs += 1
            for fr in m["fragments"]:
                frag_types[fr["type"]] += 1
                total_fragments += 1

    print(f"Всего сообщений: {total_messages}")
    print(f"Всего fragments: {total_fragments}")
    print(f"Пустых диалогов: {empty_conv}")
    print(f"Сообщений в ветках: {branch_msgs}")
    print(f"Роли: {dict(roles)}")
    print(f"Типы fragments: {dict(frag_types)}")


if __name__ == "__main__":
    main()
