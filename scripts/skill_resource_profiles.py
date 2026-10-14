"""Explicit distribution profiles; an unknown name never inherits setup powers."""

READONLY_RESOURCES = (
    ("templates/project/.github/agent-collaboration/run_pr_metadata_check.py", "scripts/run_pr_metadata_check.py"),
    ("shared/scripts/verify_installed_skill.py", "scripts/verify_installed_skill.py"),
)
EVENT_RESOURCES = (
    ("shared/scripts/collaboration_event.py", "scripts/collaboration_event.py"),
    ("shared/scripts/collaboration_scope.py", "scripts/collaboration_scope.py"),
    ("shared/requirements-helpers.txt", "scripts/requirements-helpers.txt"),
) + tuple(
    (f"skills/github-collaboration/templates/events/{name}.yml", f"templates/events/{name}.yml")
    for name in ("claim", "research-claim", "handoff", "reassign", "release", "resume")
)
# Build-time overlays keep one canonical source while producing a complete
# consumer deployment. No runtime lookup in another installed Skill is needed.
DEPLOYED_RESOURCES = tuple(
    (source, f"assets/templates/project/.github/agent-collaboration/{name}")
    for source, name in (
        ("shared/scripts/collaboration_event.py", "collaboration_event.py"),
        ("shared/scripts/collaboration_scope.py", "collaboration_scope.py"),
        ("schemas/collaboration-event.schema.json", "collaboration-event.schema.json"),
        ("shared/requirements-helpers.txt", "requirements-helpers.txt"),
    )
)

PROFILES = {
    "github-collaboration-setup": {
        "schema_root": "assets/schemas", "templates": True,
        "helpers": READONLY_RESOURCES + EVENT_RESOURCES + DEPLOYED_RESOURCES
        + (("shared/scripts/managed_block.py", "scripts/managed_block.py"),),
    },
    "github-collaboration": {
        "schema_root": "references/schemas", "templates": False,
        "helpers": READONLY_RESOURCES + EVENT_RESOURCES,
    },
    "github-collaboration-check": {
        "schema_root": "references/schemas", "templates": False,
        "helpers": READONLY_RESOURCES,
    },
}


def resolve_profile(destination_name: str, explicit: str | None = None) -> str:
    name = explicit or destination_name
    if name not in PROFILES:
        raise ValueError("unknown resource profile; select a supported --profile explicitly")
    if destination_name in PROFILES and destination_name != name:
        raise ValueError("resource profile conflicts with the named Skill package")
    return name
