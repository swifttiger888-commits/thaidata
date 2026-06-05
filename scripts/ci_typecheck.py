#!/usr/bin/env python3
"""CI type check — validates Python AST and JS syntax for all project files."""
import ast, os, sys, subprocess

errors = []

# Python AST check
for root, dirs, files in os.walk('scripts'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try:
                ast.parse(open(p).read())
            except SyntaxError as e:
                errors.append(f'PY {p}: {e}')

for root, dirs, files in os.walk('tests'):
    for f in files:
        if f.endswith('.py'):
            p = os.path.join(root, f)
            try:
                ast.parse(open(p).read())
            except SyntaxError as e:
                errors.append(f'PY {p}: {e}')

# JavaScript syntax check
import glob
for f in glob.glob('functions/**/*.js', recursive=True) + glob.glob('tools/**/*.js', recursive=True) + ['privacy-banner.js']:
    result = subprocess.run(['node', '--check', f], capture_output=True, text=True)
    if result.returncode != 0:
        errors.append(f'JS {f}: {result.stderr.strip()}')

if errors:
    for e in errors:
        print(f'ERROR: {e}')
    sys.exit(1)
print('All Python + JS files pass syntax check')
