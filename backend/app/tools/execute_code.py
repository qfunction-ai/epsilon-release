"""Vulnerable code execution tool for DVAA.

This tool executes Python code via exec() with no input validation.
It demonstrates what happens when an LLM agent can execute arbitrary
code without restrictions — the core of OWASP LLM01 (Prompt Injection)
and related vulnerabilities.

Registered with Letta via the tool API. Runs inside the Letta Docker
container, which provides process-level isolation.
"""
# aislop-ignore-file security/python-exec — DELIBERATE teaching vulnerability
# (DVAA). This raw exec() IS the point: students watch it fire in the
# vulnerable state and see the fixed state deny the tool via LettaLocal
# policy. Removing or sandboxing it here would delete the lesson.



def execute_code(code: str, language: str = "python") -> str:
    """Execute Python code locally. Vulnerable version: no input validation.

    Args:
        code: The Python code to execute.
        language: The programming language. Currently only Python is supported.
    """
    import io
    from contextlib import redirect_stderr, redirect_stdout

    if language != "python":
        return f"Error: Only Python is supported, got {language}"

    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()

    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            exec(code, {"__name__": "__main__"}, {})
    except Exception as e:
        err = stderr_buf.getvalue()
        out = stdout_buf.getvalue()
        result = out
        if err:
            result += f"\nSTDERR: {err}"
        result += f"\nError: {type(e).__name__}: {e}"
        return result or "(no output)"

    output = stdout_buf.getvalue()
    err = stderr_buf.getvalue()
    if err:
        output += f"\nSTDERR: {err}"
    return output or "(no output)"
