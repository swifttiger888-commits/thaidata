#!/usr/bin/env python3
"""Single source of truth for ThaiData's design tokens.

Three page families grew three token sets. The *values* below are deliberately the
ones each family renders today — this module centralises them so a change is one
edit, without silently restyling 1,500 pages. Unifying the remaining drift
(ink-mute #7A6F6A vs #5B534C, radii 12/14/16/24) is a design decision that needs a
rendered before/after, tracked separately.

Usage:
    from design_tokens import root_css
    html = html.replace(existing_root, root_css('listing'))
"""
from __future__ import annotations

# Roles shared by every generated family. Values are the rendered ones in use.
SHARED = {
    'ivory': '#FBF7F0',
    'paper': '#FFFFFF',
    'ink': '#1A1614',
    'hairline': '#E7DFD5',
    'red': '#A3132B',
    'red-press': '#7E0E20',
    'red-wash': '#F6E7E7',
    'turmeric': '#F2B21A',
    'jade': '#047857',
    'amber': '#B45309',
    'amber-wash': '#FEF3C7',
    'danger': '#B91C1C',
    'danger-wash': '#FEE2E2',
}

# Per-family declarations. Aliases point at primitives so a primitive change
# propagates; literals are kept where the family needs its own value.
FAMILIES: dict[str, dict[str, str]] = {
    'listing': {
        'ivory': SHARED['ivory'],
        'paper': SHARED['paper'],
        'white': 'var(--paper)',
        'cream': 'var(--ivory)',
        'ink': SHARED['ink'],
        'ink-soft': '#4A403C',
        'ink-mute': '#5B534C',
        'hairline': SHARED['hairline'],
        'border': 'var(--hairline)',
        'border-light': '#F2EDE6',
        'brand': SHARED['red'],
        'brand-press': SHARED['red-press'],
        'brand-tint': '#F7E8EB',
        'turmeric': SHARED['turmeric'],
        'jade': SHARED['jade'],
        'success': '#047857',
        'success-dark': '#065F46',
        'success-light': '#D1FAE5',
        'amber': SHARED['amber'],
        'amber-light': SHARED['amber-wash'],
        'danger': SHARED['danger'],
        'danger-light': SHARED['danger-wash'],
        'green': 'var(--brand)',
        'green-dark': 'var(--brand-press)',
        'green-light': 'var(--brand-tint)',
        'red': 'var(--danger)',
        'red-light': 'var(--danger-light)',
        'ink-secondary': 'var(--ink-soft)',
        'ink-tertiary': 'var(--ink-mute)',
        'shadow-sm': '0 1px 2px 0 rgba(0,0,0,0.05)',
        'shadow': '0 1px 3px 0 rgba(0,0,0,0.1), 0 1px 2px -1px rgba(0,0,0,0.1)',
        'shadow-md': '0 4px 6px -1px rgba(0,0,0,0.1), 0 2px 4px -2px rgba(0,0,0,0.1)',
        'shadow-lg': '0 10px 15px -3px rgba(0,0,0,0.1), 0 4px 6px -4px rgba(0,0,0,0.1)',
        'radius-sm': '8px',
        'radius': '10px',
        'radius-lg': '10px',
        'radius-xl': '10px',
        'radius-full': '9999px',
    },
    'city': {
        # The city shells declare exactly these nine names; adding primitives here
        # would be dead weight and force a 278-file edit for no rendered change.
        'bg': '#FBF7F0',
        'c1': '#A3132B',
        'c2': '#A3132B',
        'dark': '#FFFFFF',
        'ink': '#1A1614',
        'ink2': '#4A403C',
        'ink3': '#5B534C',
        'ink4': '#5B534C',
        'line': '#E7DFD5',
    },
}


def root_css(family: str) -> str:
    """Return a :root block for a page family, one declaration per line."""
    decls = FAMILIES[family]
    body = '\n'.join(f'    --{name}: {value};' for name, value in decls.items())
    return f':root {{\n{body}\n}}'


if __name__ == '__main__':
    import sys
    print(root_css(sys.argv[1] if len(sys.argv) > 1 else 'listing'))
