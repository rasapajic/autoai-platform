"""AutoAI listing source adapters.

Importing an adapter does not authorize ingestion. Runtime access is guarded by
``app.core.source_policy`` and the environment-backed internal admin endpoint.
Public/commercial and unattended ingestion remain disabled.
"""
