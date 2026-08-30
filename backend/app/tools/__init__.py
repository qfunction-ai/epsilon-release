"""Custom Letta tools for Epsilon DVAA.

These tools are registered with the Letta server via the tool API
and executed inside the Letta container. They provide local code
execution without requiring external services like E2B.

The execute_code tool is intentionally vulnerable — no input validation,
no import restrictions. The defense in the fixed state comes from
LettaLocal's framework-level controls (PolicyChecker denying the tool
via denied_tools), NOT from a "safe" version of the tool. Security
controls belong in the framework, not the application layer.
"""
