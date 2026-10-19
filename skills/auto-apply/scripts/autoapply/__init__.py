"""auto-apply deterministic script layer (Python 3.9+, standard library only).

Layering (CODE_STANDARDS §2):
- entry:    cli / __main__            (argparse, printing, exit codes, os.environ)
- business: ledger evidence runstate gates queue_build dedup profile_check facts_render
            export_md migrate_legacy report selfcheck
- tools:    enums errors paths ids redact normalize schema_validate i18n

The package never touches the network, a browser, an LLM or secrets.env.
"""

from __future__ import annotations

__version__ = "0.1.0"
