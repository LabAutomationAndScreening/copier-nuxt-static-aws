import tempfile
from pathlib import Path

import copier
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[3]
_BASE_ANSWERS_PATH = Path(__file__).parent / "base_answers.yaml"


def rendered_answers(*, app_domain_name: str, **overrides: object) -> dict[str, object]:
    """Return every answer copier settles on for the base answers, `app_domain_name` and `overrides`.

    Copier runs its own validators on these answers, so an invalid one raises copier's ValueError. A question the
    answers leave out comes back with the default copier derived for it from the other answers, which is how a test
    checks a computed default. `pretend=True` skips file writes and tasks but still validates, and `vcs_ref="HEAD"`
    includes uncommitted copier.yml edits.
    """
    base_answers = yaml.safe_load(_BASE_ANSWERS_PATH.read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as tmp:
        worker = copier.run_copy(
            str(PROJECT_ROOT),
            tmp,
            data={**base_answers, "app_domain_name": app_domain_name, **overrides},
            defaults=True,
            unsafe=True,
            quiet=True,
            vcs_ref="HEAD",
            pretend=True,
        )
    return dict(worker.answers.combined)
