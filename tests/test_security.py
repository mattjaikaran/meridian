#!/usr/bin/env python3
"""Adversarial tests for scripts/security.py."""

import pytest

from scripts.db import MeridianError
from scripts.security import (
    safe_json_loads,
    sanitize_shell_arg,
    validate_field_name,
    validate_path,
)


# -- validate_path tests ------------------------------------------------------


class TestValidatePath:
    def test_valid_subpath(self, tmp_path):
        sub = tmp_path / "src" / "main.py"
        sub.parent.mkdir(parents=True, exist_ok=True)
        sub.touch()
        result = validate_path(sub, tmp_path)
        assert result == sub.resolve()

    def test_valid_relative_within_root(self, tmp_path):
        sub = tmp_path / "a" / "b"
        sub.mkdir(parents=True)
        # a/b/../b is still inside tmp_path
        result = validate_path(tmp_path / "a" / "b" / ".." / "b", tmp_path)
        assert result == sub.resolve()

    def test_rejects_parent_traversal(self, tmp_path):
        with pytest.raises(MeridianError, match="escapes project root"):
            validate_path(tmp_path / ".." / "etc" / "passwd", tmp_path)

    def test_rejects_absolute_outside(self, tmp_path):
        with pytest.raises(MeridianError, match="escapes project root"):
            validate_path("/etc/passwd", tmp_path)

    def test_rejects_double_dot_traversal(self, tmp_path):
        with pytest.raises(MeridianError, match="escapes project root"):
            validate_path(tmp_path / "a" / ".." / ".." / "secrets", tmp_path)

    def test_root_itself_is_valid(self, tmp_path):
        result = validate_path(tmp_path, tmp_path)
        assert result == tmp_path.resolve()

    def test_symlink_escape(self, tmp_path):
        """Symlink that points outside project root should be rejected."""
        link = tmp_path / "sneaky_link"
        link.symlink_to("/tmp")
        with pytest.raises(MeridianError, match="escapes project root"):
            validate_path(link / "file.txt", tmp_path)

    def test_string_path_input(self, tmp_path):
        sub = tmp_path / "file.txt"
        sub.touch()
        result = validate_path(str(sub), str(tmp_path))
        assert result == sub.resolve()


# -- safe_json_loads tests ----------------------------------------------------


class TestSafeJsonLoads:
    def test_valid_dict(self):
        assert safe_json_loads('{"key": "value"}') == {"key": "value"}

    def test_valid_list(self):
        assert safe_json_loads('[1, 2, 3]') == [1, 2, 3]

    def test_malformed_json(self):
        assert safe_json_loads("{not json}") is None

    def test_empty_string(self):
        assert safe_json_loads("") is None

    def test_bare_string(self):
        assert safe_json_loads('"hello"') is None

    def test_bare_number(self):
        assert safe_json_loads("42") is None

    def test_bare_null(self):
        assert safe_json_loads("null") is None

    def test_oversized_input(self):
        huge = '{"x": "' + "a" * 2_000_000 + '"}'
        assert safe_json_loads(huge) is None

    def test_non_string_input(self):
        assert safe_json_loads(123) is None  # type: ignore[arg-type]

    def test_nested_json(self):
        result = safe_json_loads('{"a": {"b": [1, 2]}}')
        assert result == {"a": {"b": [1, 2]}}

    def test_unicode_content(self):
        assert safe_json_loads('{"emoji": "\\u2603"}') == {"emoji": "\u2603"}

    def test_trailing_garbage(self):
        assert safe_json_loads('{"a": 1} extra') is None


# -- validate_field_name tests ------------------------------------------------


class TestValidateFieldName:
    def test_valid_simple(self):
        assert validate_field_name("status") == "status"

    def test_valid_underscore_prefix(self):
        assert validate_field_name("_private") == "_private"

    def test_valid_mixed(self):
        assert validate_field_name("col_name_2") == "col_name_2"

    def test_rejects_starts_with_number(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("2col")

    def test_rejects_sql_injection(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("status; DROP TABLE")

    def test_rejects_dash(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("my-column")

    def test_rejects_space(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("my column")

    def test_rejects_empty(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("")

    def test_rejects_dot_notation(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("table.column")

    def test_rejects_semicolon(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("a;b")

    def test_rejects_parentheses(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name("func()")

    def test_rejects_non_string(self):
        with pytest.raises(MeridianError, match="Invalid field name"):
            validate_field_name(123)  # type: ignore[arg-type]


# -- sanitize_shell_arg tests -------------------------------------------------


class TestSanitizeShellArg:
    def test_valid_simple(self):
        assert sanitize_shell_arg("hello") == "hello"

    def test_valid_path_like(self):
        assert sanitize_shell_arg("/path/to/file.txt") == "/path/to/file.txt"

    def test_valid_flag(self):
        assert sanitize_shell_arg("--verbose") == "--verbose"

    def test_rejects_semicolon(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("file; rm -rf /")

    def test_rejects_pipe(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("file | cat /etc/passwd")

    def test_rejects_ampersand(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("cmd & evil")

    def test_rejects_dollar(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("$HOME")

    def test_rejects_backtick(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("`whoami`")

    def test_rejects_newline(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("file\nrm -rf /")

    def test_rejects_null_byte(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("file\x00evil")

    def test_rejects_double_quote(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg('file"injection')

    def test_rejects_single_quote(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("file'injection")

    def test_rejects_parentheses(self):
        with pytest.raises(MeridianError, match="dangerous characters"):
            sanitize_shell_arg("$(cmd)")

    def test_rejects_non_string(self):
        with pytest.raises(MeridianError, match="must be a string"):
            sanitize_shell_arg(123)  # type: ignore[arg-type]

    def test_allows_dots_and_dashes(self):
        assert sanitize_shell_arg("my-file.txt") == "my-file.txt"

    def test_allows_equals_sign(self):
        assert sanitize_shell_arg("--key=value") == "--key=value"
