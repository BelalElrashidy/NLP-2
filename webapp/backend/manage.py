#!/usr/bin/env python
import os
import sys
from pathlib import Path


if __name__ == '__main__':
    # Put repo root, webapp and src on PYTHONPATH so imports work when run from repo root
    repo_root = Path(__file__).resolve().parents[2]
    webapp_dir = repo_root.joinpath('webapp').resolve()
    src = repo_root.joinpath('src').resolve()

    # Insert in order: project root, webapp dir, src dir
    sys.path.insert(0, str(repo_root))
    sys.path.insert(0, str(webapp_dir))
    sys.path.insert(0, str(src))

    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'backend.settings')
    from django.core.management import execute_from_command_line
    execute_from_command_line(sys.argv)
