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
# LIVE_CORPUS is Jon's own corpus database (agent-estate's internal/corpus,
# ~5,400 prompts and ~2,600 hard rows) -- a second, separate durable record
# this same guard has protected under the name ledger.sqlite3 since it moved
# out of ~/.local/state on 2026-08-30. agent-estate#P6 renamed the real file
# to corpus.sqlite3, with ledger.sqlite3 kept only as a compat symlink -- both
# names must stay guarded, since either can still open the live file. This
# regex was carried by an EARLIER, divergent, never-merged local revision of
# ledger-write-guard.sh (commit a3f6e09, "match the ledger path as an open,
# not as a mention") that this file's own #277 rewrite into command_guard.py
# did not incorporate -- so corpus protection had already silently lapsed
# here before this rename, independent of it. Restoring it, not just
# repointing it, is what this change actually does for LIVE_CORPUS.
LIVE_CORPUS = re.compile(
    r"(?:~|/Users/[^/\s]+)/corpus/(?:ledger|corpus)\.sqlite3"
)
DESTRUCTIVE = {"kill-server", "kill-session", "kill-window", "respawn-pane", "respawn-window"}
PROTECTED = re.compile(r"agent-supervisor:1|(?:^|[^\w])=?Hill90(?:$|[^\w])|hill90-app|hill90-docs")
KEYCHAIN_WRITE_COMMANDS = {
    "create-keychain",
    "delete-keychain",
    "lock-keychain",
    "unlock-keychain",
    "set-keychain-settings",
    "set-keychain-password",
    "create-keypair",
    "add-generic-password",
    "add-internet-password",
    "add-certificates",
    "delete-generic-password",
    "set-generic-password-partition-list",
    "delete-internet-password",
    "set-internet-password-partition-list",
    "set-key-partition-list",
    "delete-certificate",
    "delete-identity",
    "set-identity-preference",
    "create-db",
    "import",
    "install-mds",
    "add-trusted-cert",
    "remove-trusted-cert",
    "trust-settings-import",
    "create-filevaultmaster-keychain",
}


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
                index += 1
                candidate = body.rstrip("\n")
                if candidate.lstrip("\t") == delimiter:
                    kept.append(body)
                    found = True
                    break
                # A quoted delimiter disables expansions: the body is text,
                # drop it. An unquoted delimiter still expands $(...) and
                # backticks, so keep the body -- but as the ARGUMENT of a
                # no-op, inside double quotes, never as command lines
                # (agent-dotfiles#353, third defect: a heredoc quoting
                # `git commit` as evidence used to parse as a commit). The
                # tokenizer walks double-quoted text for expansions only, so
                # a substitution inside the body is still found and the
                # prose around it is not mistaken for a command.
                if is_quoted:
                    kept.append("\n" if body.endswith("\n") else "")
                else:
                    escaped = candidate.replace("\\", "\\\\").replace('"', '\\"')
                    kept.append(': "' + escaped + '"' + ("\n" if body.endswith("\n") else ""))
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


SECURITY_GLOBAL_FLAGS = {"-h", "-i", "-l", "-q", "-v"}
SECURITY_GLOBAL_FLAGS_WITH_ARG = {"-p"}


def security_subcommand_index(values: list[str]) -> int:
    """Skip `security`'s own leading global options to find the subcommand.

    `security`'s man page is `security [-hilqv] [-p prompt] [command] ...` --
    global flags legitimately precede the subcommand, so position 0 cannot be
    assumed to hold it. `-p` takes an argument (the prompt text) and must be
    consumed along with it, the same way `executable()` above consumes `env`'s
    own flags.
    """
    index = 0
    while index < len(values):
        token = values[index]
        if token in SECURITY_GLOBAL_FLAGS:
            index += 1
        elif token in SECURITY_GLOBAL_FLAGS_WITH_ARG:
            index += 2
        else:
            break
    return index


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
            if program in {"sqlite3", "python", "python3"} and (any(LIVE_LEDGER.search(value) or LIVE_CORPUS.search(value) for value in values) or any("$" in value for value in values)):
                if "-readonly" not in values and not any("?mode=ro" in value for value in values) and not any(value.endswith(("cli.py", "core.py")) for value in values):
                    return True
        elif rule == "keychain" and program == "security" and values:
            sub_values = values[security_subcommand_index(values):]
            if not sub_values:
                continue
            subcommand = sub_values[0]
            if subcommand in KEYCHAIN_WRITE_COMMANDS:
                return True
            # These commands are getters without -s, but `security help`
            # confirms that -s changes the selected keychain/search list.
            if subcommand in {"list-keychains", "default-keychain", "login-keychain"} and "-s" in sub_values:
                return True
            # These subcommands report state by default and write only when
            # their documented mutating mode is explicitly requested.
            if subcommand == "user-trust-settings-enable" and any(value in {"-d", "-e"} for value in sub_values):
                return True
            if subcommand == "smartcards" and any(value in {"-d", "-e"} for value in sub_values):
                return True
            if subcommand == "filevault" and len(sub_values) >= 3 and sub_values[0:2] == ["filevault", "skip-sc-enforcement"] and sub_values[2] in {"set", "reset"}:
                return True
            if subcommand == "authorizationdb" and len(sub_values) >= 2 and sub_values[1] in {"remove", "write", "reset"}:
                return True
    return False


# --- commit target resolution (agent-dotfiles#353) ------------------------
#
# main-branch-guard used to read the branch from the hook payload's cwd --
# the session's directory -- never from where the write would land. A
# session in a worktree could commit to a checkout on main (false allow),
# and a session on main could not commit to its own feature worktree
# (false block). Every lane in the estate works in a worktree, so every
# lane was the shape that disarmed the guard.
#
# commit_targets() resolves, for every `git commit` in the payload, the
# directory the commit lands in, from the COMMAND: git's own -C options
# (applied in order, each relative to the last), a preceding `cd` in the
# same shell scope, and otherwise the session cwd (returned as "" for the
# hook to substitute). Scopes matter: a `cd` inside a subshell, a command
# substitution or a pipeline segment runs in a child process and never
# moves the enclosing shell, so it is tracked per scope and inherited
# downward, never leaked upward.
#
# Where the target cannot be resolved from the text, the entry is returned
# UNRESOLVED with a reason and the hook fails closed. Named limits, all
# refused rather than guessed: a cd or -C whose path carries an expansion
# ($VAR, $(...), backticks), `cd -`, `cd ~user`, globs, pushd/popd, more
# than one cd argument, git's --git-dir/--work-tree, and a `||` after a cd
# (if the cd fails the commit runs somewhere else). A `cd` followed by `;`
# is accepted only because the hook checks the directory exists; if it does
# not, cd would fail and the hook refuses.


@dataclass
class Entry:
    scope: int
    sep: str  # separator before this command within its scope
    in_pipe: bool
    words: list[Word]


class _Scopes:
    def __init__(self) -> None:
        self.next = 0
        self.parent: dict[int, int] = {}

    def new(self, parent: int) -> int:
        scope = self.next
        self.next += 1
        self.parent[scope] = parent
        return scope


def _expansion_entries(source: str, scope: int, scopes: _Scopes, out: list[Entry]) -> None:
    """Like expansion_commands, but records scoped entries for $(...) and backticks."""
    i = 0
    while i < len(source):
        if source[i] == "\\":
            i += 2
        elif source.startswith("$(", i):
            part, i = substitution(source, i)
            _entries(part, scopes.new(scope), scopes, out)
        elif source[i] == "`":
            part, i = quoted(source, i, "`")
            _entries(part, scopes.new(scope), scopes, out)
        else:
            i += 1


def _entries(source: str, scope: int, scopes: _Scopes, out: list[Entry]) -> None:
    """The same tokenizer as commands(), recording each command's scope,
    the separator before it, and whether it sits in a pipeline."""
    source = strip_heredoc_bodies(source)
    current: list[Word] = []
    text: list[str] = []
    was_quoted = False
    pending_sep = ""
    in_pipe = False
    last_index = -1

    def finish_word() -> None:
        nonlocal text, was_quoted
        if text or was_quoted:
            current.append(Word("".join(text), was_quoted))
        text = []
        was_quoted = False

    def finish_command() -> None:
        nonlocal pending_sep, in_pipe, last_index
        finish_word()
        if current:
            out.append(Entry(scope, pending_sep, in_pipe, current.copy()))
            last_index = len(out) - 1
            current.clear()
            pending_sep = ""
            in_pipe = False

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
                _expansion_entries(part, scope, scopes, out)
            text.append(part)
            was_quoted = True
        elif char == "`":
            part, i = quoted(source, i, "`")
            _entries(part, scopes.new(scope), scopes, out)
            text.append("$substitution")
        elif source.startswith("$(", i):
            part, i = substitution(source, i)
            _entries(part, scopes.new(scope), scopes, out)
            text.append("$substitution")
        elif char == "(":
            finish_command()
            part, i = subshell(source, i)
            _entries(part, scopes.new(scope), scopes, out)
        elif char == "\n" or char == ";":
            finish_command()
            pending_sep = char
            i += 1
        elif char in "|&":
            finish_command()
            if source.startswith("&&", i):
                pending_sep, i = "&&", i + 2
            elif source.startswith("||", i):
                pending_sep, i = "||", i + 2
            elif source.startswith("|&", i):
                pending_sep, i = "|", i + 2
            elif char == "|":
                pending_sep, i = "|", i + 1
            else:
                pending_sep, i = "&", i + 1
            if pending_sep == "|":
                # both sides of a pipe run in subshells
                in_pipe = True
                if last_index >= 0 and out[last_index].scope == scope:
                    out[last_index].in_pipe = True
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


@dataclass
class _CwdState:
    cwd: str = ""  # "" means the session cwd, substituted by the hook
    unresolved: str | None = None
    cd_seen: bool = False

    def copy(self) -> "_CwdState":
        return _CwdState(self.cwd, self.unresolved, self.cd_seen)


def _join(base: str, path: str) -> str:
    if path.startswith("/") or path == "~" or path.startswith("~/"):
        return path
    if base == "":
        return path
    return base.rstrip("/") + "/" + path


def _literal_path(value: str) -> str | None:
    """A reason the path is not a plain literal, or None if it is."""
    if value == "":
        return "cd/-C target is empty"
    if "$" in value or "`" in value:
        return f"cd/-C target {value!r} carries an expansion"
    if value.startswith("~") and value != "~" and not value.startswith("~/"):
        return f"cd/-C target {value!r} names another user's home"
    if any(c in value for c in "*?["):
        return f"cd/-C target {value!r} is a glob"
    return None


def _git_globals(values: list[str]) -> tuple[str, list[str], str | None]:
    """Return (subcommand, -C paths in order, reason unresolved)."""
    i = 0
    cpaths: list[str] = []
    while i < len(values):
        v = values[i]
        if v == "-C":
            if i + 1 >= len(values):
                return "", cpaths, "git -C without a path"
            cpaths.append(values[i + 1])
            i += 2
        elif v.startswith("-C") and len(v) > 2:
            cpaths.append(v[2:])
            i += 1
        elif v in {"-c", "--namespace", "--super-prefix", "--exec-path", "--config-env"}:
            i += 2
        elif v.startswith("--git-dir") or v.startswith("--work-tree"):
            return "", cpaths, f"git {v.split('=')[0]} is not resolved by this guard"
        elif v.startswith("-"):
            i += 1
        else:
            return v, cpaths, None
    return "", cpaths, None


def commit_targets(source: str, initial: _CwdState | None = None) -> list[tuple[str | None, str | None]]:
    """Every `git commit` in source as (target_dir, None) or (None, reason)."""
    scopes = _Scopes()
    root = scopes.new(-1)
    entries: list[Entry] = []
    _entries(source, root, scopes, entries)
    states: dict[int, _CwdState] = {root: (initial or _CwdState()).copy()}
    results: list[tuple[str | None, str | None]] = []

    def state_for(scope: int) -> _CwdState:
        if scope not in states:
            parent = scopes.parent[scope]
            states[scope] = state_for(parent).copy() if parent >= 0 else _CwdState()
        return states[scope]

    for entry in entries:
        st = state_for(entry.scope)
        if entry.sep == "||" and st.cd_seen and st.unresolved is None:
            st.unresolved = "a `||` after a cd leaves the working directory ambiguous"
        program, args = executable(entry.words)
        values = [word.text for word in args]
        if program in {"bash", "sh", "zsh"} and "-c" in values:
            script_index = values.index("-c") + 1
            if script_index < len(values):
                results.extend(commit_targets(values[script_index], st))
            continue
        if program == "eval":
            results.extend(commit_targets(" ".join(values), st))
            continue
        if program == "cd":
            if entry.in_pipe:
                continue
            st.cd_seen = True
            # cd's own grammar: options (-L, -P, -e, -@) precede the target;
            # `--` ends options; a bare `-` is NOT an option, it is the
            # target $OLDPWD (agent-dotfiles#354: stripping it as a flag made
            # `cd -` resolve like bare `cd`, to $HOME). After `--` every token
            # is a literal path, so `cd -- -` names a directory called "-".
            targets: list[str] = []
            literal = False
            for v in values:
                if literal:
                    targets.append(v)
                elif v == "--":
                    literal = True
                elif v == "-" or not v.startswith("-"):
                    targets.append(v)
            if len(targets) > 1:
                st.unresolved = "cd with more than one argument"
            elif not targets:
                st.cwd = "~"
            elif targets[0] == "-" and not literal:
                st.unresolved = "cd - targets $OLDPWD, which the command text cannot show"
            else:
                reason = _literal_path(targets[0])
                if reason:
                    st.unresolved = reason
                else:
                    st.cwd = _join(st.cwd, targets[0])
            continue
        if program in {"pushd", "popd"} and not entry.in_pipe:
            st.cd_seen = True
            st.unresolved = f"{program} is not tracked by this guard"
            continue
        if program == "git":
            sub, cpaths, bad = _git_globals(values)
            # agent-dotfiles#354: a --git-dir/--work-tree invocation ends
            # option parsing before the subcommand is seen, so `bad` must be
            # reported BEFORE the subcommand test -- otherwise the commit is
            # dropped from the target list and, beside a resolvable commit in
            # the same command, the hook's fallback never fires.
            if bad and "commit" in values and "--dry-run" not in values:
                results.append((None, bad))
                continue
            if sub != "commit" or "--dry-run" in values:
                continue
            if st.unresolved:
                results.append((None, st.unresolved))
                continue
            target = st.cwd
            problem = None
            for c in cpaths:
                problem = _literal_path(c)
                if problem:
                    break
                target = _join(target, c)
            results.append((None, problem) if problem else (target, None))
    return results


def main() -> int:
    if len(sys.argv) != 2:
        return 2
    try:
        source = sys.stdin.read()
        if sys.argv[1] == "main-targets":
            targets = commit_targets(source)
            for target, reason in targets:
                if reason is not None:
                    print("UNRESOLVED\t" + reason)
                else:
                    print("TARGET\t" + (target or "."))
            return 10 if targets else 0
        parsed = commands(source)
        return 10 if violates(sys.argv[1], parsed) else 0
    except ParseError:
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
