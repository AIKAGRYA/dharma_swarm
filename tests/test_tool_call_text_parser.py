"""Tests for _parse_tool_calls_from_text — including the XML function dialect.

The XML <function=name><parameter=key>value</parameter> dialect was the root
cause of the "fake tool_call results" pathology (NIKKI 2026-07-16): models
emitting this format had their raw, unexecuted XML stored verbatim as the
task result. Pattern 4 in _parse_tool_calls_from_text fixes this.
"""
import json

from dharma_swarm.agent_runner import _parse_tool_calls_from_text


KNOWN = {"read_file", "write_file", "edit_file", "glob_files", "grep_search"}


def test_pattern1_xml_tool_call_json():
    text = '<tool_call>{"name": "read_file", "arguments": {"path": "/a/b"}}</tool_call>'
    calls = _parse_tool_calls_from_text(text, KNOWN)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_file"
    assert json.loads(calls[0]["arguments"]) == {"path": "/a/b"}


def test_pattern4_function_param_xml_single():
    """The exact dialect that produced 113 fake results."""
    text = (
        "<tool_call>\n"
        "<function=read_file>\n"
        "<parameter=path>\n"
        "/home/dhyana/.dharma/knowledge_wiki/concepts/knowledge-compiler.md\n"
        "</parameter>\n"
        "</function>\n"
        "</tool_call>"
    )
    calls = _parse_tool_calls_from_text(text, KNOWN)
    assert len(calls) == 1, f"expected 1 call, got {calls}"
    assert calls[0]["name"] == "read_file"
    args = json.loads(calls[0]["arguments"])
    assert args["path"].endswith("knowledge-compiler.md")


def test_pattern4_function_param_xml_multiple_params():
    text = (
        "<function=edit_file>\n"
        "<parameter=path>/tmp/x.py</parameter>\n"
        "<parameter=old_string>foo</parameter>\n"
        "<parameter=new_string>bar</parameter>\n"
        "</function>"
    )
    calls = _parse_tool_calls_from_text(text, KNOWN)
    assert len(calls) == 1
    assert calls[0]["name"] == "edit_file"
    args = json.loads(calls[0]["arguments"])
    assert args == {"path": "/tmp/x.py", "old_string": "foo", "new_string": "bar"}


def test_pattern4_rejects_unknown_tool():
    text = "<function=delete_database><parameter=confirm>yes</parameter></function>"
    calls = _parse_tool_calls_from_text(text, KNOWN)
    assert calls == []


def test_pattern4_in_prose_still_parsed():
    """Models often wrap the XML in prose; the parser must still find it."""
    text = (
        "I'll investigate this latent branch by reading the relevant file.\n"
        "<function=read_file>\n"
        "<parameter=path>~/.dharma/knowledge_wiki/concepts/x.md</parameter>\n"
        "</function>\n"
        "Then I'll analyse the contents."
    )
    calls = _parse_tool_calls_from_text(text, KNOWN)
    assert len(calls) == 1
    assert calls[0]["name"] == "read_file"


def test_empty_and_garbage():
    assert _parse_tool_calls_from_text("", KNOWN) == []
    assert _parse_tool_calls_from_text("just some prose", KNOWN) == []
