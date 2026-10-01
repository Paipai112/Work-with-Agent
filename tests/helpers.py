def frontmatter(text: str) -> dict[str, object]:
    if not text.startswith("---"):
        return {}

    lines = text.splitlines(keepends=True)
    if not lines or lines[0].rstrip("\r\n") != "---":
        return {}

    for index, line in enumerate(lines[1:], start=1):
        if line.rstrip("\r\n") == "---":
            import yaml

            parsed = yaml.safe_load("".join(lines[1:index]))
            return parsed if isinstance(parsed, dict) else {}
    return {}
