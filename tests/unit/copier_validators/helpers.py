"""Drives copier's own answer validation so copier.yml validators can be asserted.

``pretend=True`` skips file writes and tasks but still validates; ``vcs_ref="HEAD"``
auto-includes dirty working-tree changes, so uncommitted validator edits are picked up.
"""

import tempfile
from pathlib import Path

import copier

PROJECT_ROOT = Path(__file__).resolve().parents[3]

# Minimal answers that satisfy every no-default question (staging is off so its
# no-default account IDs aren't asked); tests override the single field under test.
_MINIMAL_ANSWERS: dict[str, object] = {
    "repo_name": "baz",
    "repo_org_name": "foo",
    "description": "Copier validator test fixture",
    "aws_identity_center_id": "d-0000000000",
    "aws_production_account_id": "000000000000",
    "use_staging_environment": False,
    "app_name": "baz_app",
    "app_domain_name": "www.baz.example.com",
}


def validate_answers(**overrides: object) -> None:
    _ = rendered_answers(**overrides)


def rendered_answers(**overrides: object) -> dict[str, object]:
    """Return every answer copier settles on for the fixture answers with `overrides` applied.

    A question the data leaves out comes back with the default copier derived for it from the other answers, which
    is how a test checks a computed default.
    """
    data = {**_MINIMAL_ANSWERS, **overrides}
    with tempfile.TemporaryDirectory() as tmp:
        worker = copier.run_copy(
            str(PROJECT_ROOT),
            tmp,
            data=data,
            defaults=True,
            unsafe=True,
            quiet=True,
            vcs_ref="HEAD",
            pretend=True,
        )
    return dict(worker.answers.combined)
