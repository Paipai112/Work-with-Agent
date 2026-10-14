# Verify a package and its fixed source

Load for install/update, first use without trusted record or recorded-input drift. Otherwise reuse [session core](session-core.md)'s unchanged verification, no package redownload for local edits.

## Source and bytes

1. Verify accessible maintainer-selected release and published `source_repository_url`, `release_tag`, full 40-character `resolved_commit_sha`, `installation_page_permalink`; independently bind tag/permalink to that commit. Access ≠ license. Unpublished/missing/conflicting fields, search/unverified Fork/floating `main` prove no installable source or completed configuration.
2. Compare **complete** `skills/<skill-name>/` files/bytes/`RESOURCE_MANIFEST.json` with actual discovered/candidate directory. For an already verified Git source use the bundled read-only [helper](../scripts/verify_installed_skill.py):

   `python3 scripts/verify_installed_skill.py --source-repo <verified-source-git> --source-sha <40-char-sha> --skill <skill-name> --installed <directory>`

   Fixed Git objects only, no replace/lazy fetch; unsupported Git/missing objects → unknown. It compares complete pinned files/bytes and declared copied-resource hashes, rejecting extra/missing/symlink/drift. Exits: 0 match, 1 drift, 2 unknown. It does not prove canonical-source→resource-list completeness; verified-source `verify_skill_packages.py` separately checks that contract. `release_binding_verified=false`: it does **not** authenticate release URL/tag-to-commit, download/install/repair. If unavailable independently compare same inventory/bytes; manifest proves nothing about unlisted instructions. Runtime resources stay in this package, never another Skill/source checkout.
3. Record repository/tag/commit/permalink, package/version/full inventory/digest/manifest, target/discovered path, client/OS/version, evidence/time/project minimum. Subsequent sessions compare recorded inputs/local digest; drift invalidates affected verification, no stale provenance/elevation reuse.

## Installation target

Directory-owner approval needs no project/Leader. Proposal: source/whole digest/client/OS/exact target/existing content/collisions/discovery scope/affected projects. Inspect target/parents without following symlinks. Copy complete verified directory **after** approval; existing/modified/unknown target uses caller's upgrade/conflict procedure, no overwrite/auto-merge. Named backups stay outside discovery; recompute copied bytes.

User discovery affects all projects; setup remains explicitly invoked. Inspect supported/added roots, disable/overrides/trust/same-name precedence; report settings before proposing changes. Native Windows and WSL prove nothing about each other.

New session at intended directory: actual `SKILL.md` path/version/invocation/all relative resources. Installed projects also test root/nested/spaces/platform entry; package-only needs no invented entry. Copy/menu success ≠ loading, record fail/unknown. Package approval grants no Leader/project/Git action. Rollback needs recorded old whole digest, inspected current target and exact restoration approval; no automatic user-change discard.
