"""python3 -m autoapply <command> ... — thin shim over cli.main()."""

from __future__ import annotations

import sys

from autoapply.cli import main

if __name__ == "__main__":
    sys.exit(main())
