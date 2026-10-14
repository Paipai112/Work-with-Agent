"""Explicit distribution profiles; an unknown name never inherits setup powers."""

PROFILES = {
    "github-collaboration-setup": {
        "schema_root": "assets/schemas", "templates": True,
        "helpers": (("shared/scripts/managed_block.py", "scripts/managed_block.py"),),
    },
    "github-collaboration": {
        "schema_root": "references/schemas", "templates": False, "helpers": (),
    },
    "github-collaboration-check": {
        "schema_root": "references/schemas", "templates": False, "helpers": (),
    },
}


def resolve_profile(destination_name: str, explicit: str | None = None) -> str:
    name = explicit or destination_name
    if name not in PROFILES:
        raise ValueError("unknown resource profile; select a supported --profile explicitly")
    if destination_name in PROFILES and destination_name != name:
        raise ValueError("resource profile conflicts with the named Skill package")
    return name
