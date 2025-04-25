# File: commitai/tests/test_template.py
# -*- coding: utf-8 -*-

from commitai.template import (
    adding_template,
    build_user_message,
    default_system_message,
)


def test_build_user_message_with_explanation():
    """Test building the user message with both explanation and diff."""
    explanation = "This is the explanation."
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    expected_message = (
        f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"
    )
    actual_message = build_user_message(explanation, diff)
    assert actual_message == expected_message


def test_build_user_message_without_explanation():
    """Test building the user message with only the diff (empty explanation)."""
    explanation = ""
    diff = "--- a/file.txt\n+++ b/file.txt\n@@ -1 +1 @@\n-old\n+new"
    # When explanation is empty, the function should still include the prefix text
    expected_message = (
        f"Here is a high-level explanation of the commit: {explanation}\n\n{diff}"
    )
    actual_message = build_user_message(explanation, diff)
    assert actual_message == expected_message


def test_default_system_message_content():
    """Test that the default system message exists and is a non-empty string."""
    assert isinstance(default_system_message, str)
    assert len(default_system_message) > 0
    assert "conventional commit format" in default_system_message


def test_adding_template_content():
    """Test that the adding template constant exists and is a non-empty string."""
    assert isinstance(adding_template, str)
    assert len(adding_template) > 0
    assert "follow this template" in adding_template
