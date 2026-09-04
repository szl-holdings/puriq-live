"""Regression lock for the literal PURIQ HTML/JavaScript template."""
from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "app.py"


def test_application_source_parses_without_f_string_brace_interpolation() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    ast.parse(source)
    assert 'HTML_TEMPLATE = r"""' in source
    assert '@@REVISION@@' in source
    assert '@@VERSION@@' in source
    assert '@@FORMULAS@@' in source
    assert '.replace("@@REVISION@@", html.escape(revision_short))' in source
    assert '.replace("@@VERSION@@", html.escape(VERSION))' in source
    assert '.replace("@@FORMULAS@@", formula_rows)' in source


def test_template_preserves_product_and_accessibility_contracts() -> None:
    source = APP_PATH.read_text(encoding="utf-8")
    for fragment in (
        'data-puriq="market-chamber-v2"',
        "PURIQ Market Chamber",
        "Probability Orbit",
        "viewport-fit=cover",
        "@media(pointer:coarse)",
        "@media(prefers-reduced-motion:reduce)",
        "@media(forced-colors:active)",
        "X-SZL-Session",
        "Trading, wallet connections, custody",
    ):
        assert fragment in source
