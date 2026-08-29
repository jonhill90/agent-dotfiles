#!/usr/bin/env python3
"""Conservatively identify executable simple commands in a Bash payload.

This deliberately is not a general-purpose shell interpreter.  It recognises
the separators and expansions relevant to the PreToolUse guards, keeps quoted
text as an argument of its containing command, recurses into command
substitutions, and omits heredoc bodies.  On malformed syntax it fails closed
instead of guessing that an apparent command is prose.
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass


class ParseError(ValueError):
    pass


@dataclass
class Word:
    text: str
    quoted: bool = False


ASSIGNMENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*=.*\Z")
LIVE_LEDGER = re.compile(
    r"(?:agent-dotfiles-supervisor|\.local/state/[^/\s]*supervisor[^/\s]*)/ledger\.sqlite3"
)
DESTRUCTIVE = {"kill-server", "kill-session", "kill-window", "respawn-pane", "respawn-window"}
PROTECTED = re.compile(r"agent-supervisor:1|(?:^|[^\w])=?Hill90(?:$|[^\w])|hill90-app|hill90-docs")


def dequote_delimiter(value: str) -> str:
    return value.replace("'", "").replace('"', "")


def strip_heredoc_bodies(source: str) -> str:
    """Replace heredoc bodies with blank lines while retaining their headers."""
    lines = source.splitlines(keepends=True)
    kept: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        kept.append(line)
        delimiters = [
            (dequote_delimiter(match.group(1)), match.group(1)[0] in "'\"")
            for match in re.finditer(
                r"<<-?\s*('(?:[^']*)'|\"(?:[^\"]*)\"|[A-Za-z_][A-Za-z0-9_]*)", line
            )
        ]
        index += 1
        for delimiter, is_quoted in delimiters:
            found = False
            while index < len(lines):
                body = lines[index]
                # A quoted delimiter disables expansions; an unquoted one does
                # not. Keep the latter conservatively so its $(...) and
                # backticks cannot hide an executable command.
                kept.append(("\n" if body.endswith("\n") else "") if is_quoted else body)
                index += 1
                candidate = body.rstrip("\n")
                if candidate.lstrip("\t") == delimiter:
                    found = True
                    break
            if not found:
                raise ParseError("unterminated heredoc")
    return "".join(kept)


def quoted(source: str, start: int, quote: str) -> tuple[str, int]:
    value: list[str] = []
    i = start + 1
    while i < len(source):
        char = source[i]
        if char == quote:
            return "".join(value), i + 1
        if char == "\\" and quote != "'" and i + 1 < len(source):
            value.append(source[i + 1])
            i += 2
            continue
        value.append(char)
        i += 1
    raise ParseError(f"unterminated {quote} quote")


def substitution(source: str, start: int) -> tuple[str, int]:
    depth = 1
    i = start + 2
    value: list[str] = []
    while i < len(source):
        char = source[i]
        if char in "'\"":
            part, i = quoted(source, i, char)
            value.extend((char, part, char))
            continue
        if char == "\\" and i + 1 < len(source):
            value.extend((char, source[i + 1]))
            i += 2
            continue
        if source.startswith("$(", i):
            depth += 1
            value.append("$(")
            i += 2
            continue
        if char == ")":
            depth -= 1
            if depth == 0:
                return "".join(value), i + 1
        value.append(char)
        i += 1
    raise ParseError("unterminated command substitution")


def subshell(source: str, start: int) -> tuple[str, int]:
    depth = 1
    i = start + 1
    value: list[str] = []
    while i < len(source):
        char = source[i]
        if char in "'\"":
            part, i = quoted(source, i, char)
            value.extend((char, part, char))
            continue
        if char == "\\" and i + 1 < len(source):
            value.extend((char, source[i + 1]))
            i += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                return "".join(value), i + 1
        value.append(char)
        i += 1
    raise ParseError("unterminated subshell")


def expansion_commands(source: str) -> list[list[Word]]:
    """Return only commands executed by expansions embedded in a word."""
    result: list[list[Word]] = []
    i = 0
    while i < len(source):
        if source[i] == "\\":
            i += 2
        elif source.startswith("$(", i):
            part, i = substitution(source, i)
            result.extend(commands(part))
        elif source[i] == "`":
            part, i = quoted(source, i, "`")
            result.extend(commands(part))
        else:
            i += 1
    return result


def commands(source: str) -> list[list[Word]]:
    source = strip_heredoc_bodies(source)
    result: list[list[Word]] = []
    current: list[Word] = []
    text: list[str] = []
    was_quoted = False

    def finish_word() -> None:
        nonlocal text, was_quoted
        if text or was_quoted:
            current.append(Word("".join(text), was_quoted))
        text = []
        was_quoted = False

    def finish_command() -> None:
        finish_word()
        if current:
            result.append(current.copy())
            current.clear()

    i = 0
    while i < len(source):
        char = source[i]
        if char in " \t\r":
            finish_word()
            i += 1
        elif char == "\\":
            if i + 1 >= len(source):
                raise ParseError("trailing escape")
            text.append(source[i + 1])
            i += 2
        elif char in "'\"":
            part, i = quoted(source, i, char)
            if char == '"':
                result.extend(expansion_commands(part))
            text.append(part)
            was_quoted = True
        elif char == "`":
            part, i = quoted(source, i, "`")
            result.extend(commands(part))
            text.append("$substitution")
        elif source.startswith("$(", i):
            part, i = substitution(source, i)
            result.extend(commands(part))
            text.append("$substitution")
        elif char == "(":
            finish_command()
            part, i = subshell(source, i)
            result.extend(commands(part))
        elif char == "\n" or char == ";" or char in "|&":
            finish_command()
            i += 2 if source.startswith(char * 2, i) else 1
        elif char in "<>":
            finish_word()
            end = i + 1
            if end < len(source) and source[end] == char:
                end += 1
            current.append(Word(source[i:end]))
            i = end
        else:
            text.append(char)
            i += 1
    finish_command()
    return result


def executable(words: list[Word]) -> tuple[str, list[Word]]:
    index = 0
    while index < len(words) and ASSIGNMENT.fullmatch(words[index].text):
        index += 1
    if index < len(words) and words[index].text == "env":
        index += 1
        while index < len(words):
            token = words[index].text
            if ASSIGNMENT.fullmatch(token):
                index += 1
            elif token.startswith("-"):
                index += 2 if token in {"-u", "--unset"} else 1
            else:
                break
    while index < len(words) and words[index].text in {
        "command", "exec", "nohup", "if", "then", "do", "else", "elif", "fi", "done", "{", "}",
    }:
        index += 1
    if index >= len(words):
        return "", []
    return words[index].text, words[index + 1 :]


def violates(rule: str, parsed: list[list[Word]]) -> bool:
    for words in parsed:
        program, args = executable(words)
        values = [word.text for word in args]
        if program in {"bash", "sh", "zsh"} and "-c" in values:
            script_index = values.index("-c") + 1
            if script_index < len(values) and violates(rule, commands(values[script_index])):
                return True
        if program == "eval" and violates(rule, commands(" ".join(values))):
            return True
        if rule == "main" and program == "git":
            if "commit" in values and "--dry-run" not in values:
                return True
        elif rule == "destructive" and program == "tmux":
            if any(value in DESTRUCTIVE for value in values):
                all_values = [word.text for word in words]
                tmux_index = all_values.index("tmux")
                prefix = all_values[:tmux_index]
                scoped = any(
                    value.startswith("TMUX_TMPDIR=") and value not in {"TMUX_TMPDIR=", "TMUX_TMPDIR=$substitution"}
                    for value in prefix
                ) or "TMUX_TMPDIR=$substitution" in prefix
                unset = any(prefix[index:index + 3] == ["env", "-u", "TMUX"] for index in range(len(prefix)))
                if not (scoped and unset):
                    return True
        elif rule == "protected":
            if program == "tmux" and (any(PROTECTED.search(value) for value in values) or any("$" in value for value in values)):
                return True
            if any(value == ".tmux.conf" or value.endswith("/.tmux.conf") or "$" in value for value in values):
                if program == "tmux" and "source-file" in values:
                    return True
                if any(value in {">", ">>"} for value in values) or program in {"tee", "mv", "cp"} or (program == "sed" and "-i" in values):
                    return True
        elif rule == "gh-body" and program == "gh" and args and args[0].text == "api":
            if "--body-file" in values or any(value.startswith("body=@") for value in values):
                return True
        elif rule.startswith("self-close:"):
            own_issue = rule.removeprefix("self-close:")
            if program == "gh" and len(values) >= 3 and values[:2] == ["issue", "close"]:
                if values[2] == own_issue:
                    return True
            if program == "gh" and values and values[0] == "api":
                if any(f"/issues/{own_issue}" in value for value in values) and "state=closed" in values:
                    return True
        elif rule == "ledger":
            if program in {"sqlite3", "python", "python3"} and (any(LIVE_LEDGER.search(value) for value in values) or any("$" in value for value in values)):
                if "-readonly" not in values and not any("?mode=ro" in value for value in values) and not any(value.endswith(("cli.py", "core.py")) for value in values):
                    return True
    return False


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        parsed = commands(sys.stdin.read())
        return 10 if violates(sys.argv[1], parsed) else 0
    except ParseError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
