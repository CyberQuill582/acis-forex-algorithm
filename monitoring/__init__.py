"""MCP monitoring & control plane (ACIS-08, master §12).

The ONLY external observability/control surface. No side channels. This package
imports no `core/*` layer internals — it holds narrow INJECTED interfaces
(control target + read-only providers) and config helpers only (C-MCP-4).
"""
