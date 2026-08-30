"""Characterization tests for execute_code tool.

These tests pin the current behavior of the execute_code function,
ensuring its contract remains stable. They are NOT security tests —
the vulnerability is the point. These tests characterize WHAT the
tool does, not whether it SHOULD do it.
"""
import pytest

from app.tools.execute_code import execute_code


class TestExecuteCodeContract:
    """Contract tests for execute_code behavior."""

    def test_simple_print_returns_output(self):
        """Valid Python code that prints returns the output."""
        result = execute_code('print("hello world")')
        assert result == "hello world\n"

    def test_empty_code_returns_no_output(self):
        """Empty code returns '(no output)'."""
        result = execute_code("")
        assert result == "(no output)"

    def test_non_python_language_returns_error(self):
        """Non-Python language returns error message."""
        result = execute_code("print('hi')", language="javascript")
        assert result == "Error: Only Python is supported, got javascript"

    def test_syntax_error_returns_exception_info(self):
        """Syntax error returns exception type and message."""
        result = execute_code("def broken(")
        assert "Error:" in result
        assert "SyntaxError" in result

    def test_runtime_error_returns_exception_info(self):
        """Runtime error returns exception type and message."""
        result = execute_code("1/0")
        assert "Error:" in result
        assert "ZeroDivisionError" in result

    def test_stderr_captured(self):
        """stderr output is captured and included."""
        result = execute_code("import sys; sys.stderr.write('error msg')")
        assert "STDERR:" in result
        assert "error msg" in result

    def test_both_stdout_and_stderr(self):
        """Both stdout and stderr are captured."""
        result = execute_code("""
import sys
print("stdout")
sys.stderr.write("stderr")
""")
        assert "stdout" in result
        assert "STDERR:" in result
        assert "stderr" in result

    def test_exception_with_prior_output(self):
        """Exception after output includes both output and error."""
        result = execute_code("""
print("before")
raise ValueError("oops")
""")
        assert "before" in result
        assert "Error:" in result
        assert "ValueError" in result
        assert "oops" in result

    def test_restricted_globals(self):
        """Globals are restricted — no access to built-ins by default."""
        # The exec uses empty globals, so built-ins like __import__ should work
        # via the __builtins__ injection Python does automatically
        # This test characterizes that built-ins ARE accessible
        result = execute_code("print(len([1,2,3]))")
        assert "3" in result

    def test_import_allowed(self):
        """Imports work because __builtins__ is provided."""
        result = execute_code("import os; print('ok')")
        assert "ok" in result

    def test_multiline_code(self):
        """Multiline code executes correctly."""
        result = execute_code("""
x = 1
y = 2
print(x + y)
""")
        assert "3" in result

    def test_return_value_not_captured(self):
        """Return values are not captured, only stdout/stderr."""
        result = execute_code("42")
        assert result == "(no output)"

    def test_name_error_returns_exception(self):
        """NameError returns exception info."""
        result = execute_code("undefined_var")
        assert "Error:" in result
        assert "NameError" in result

    def test_code_with_quotes(self):
        """Code with various quote styles works."""
        result = execute_code("print('single')")
        assert "single" in result
        result2 = execute_code('print("double")')
        assert "double" in result2

    def test_unicode_output(self):
        """Unicode characters in output work."""
        result = execute_code('print("Unicode: \u2603")')
        assert "Unicode:" in result
        assert "\u2603" in result

    def test_large_output(self):
        """Large output is captured completely."""
        result = execute_code("print('x' * 10000)")
        assert len(result) >= 10000

    def test_no_infinite_loop(self):
        """Test harness sanity: this test should complete."""
        # We do NOT test infinite loops in characterization tests
        # because they would hang. This is a placeholder documenting
        # that infinite loops are NOT characterized here.
        result = execute_code("for i in range(5): print(i)")
        assert "0" in result
        assert "4" in result
