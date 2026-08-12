#!/usr/bin/env bash
# One command that answers "what is the state of the estate right now".
#
# WHY: the Director reconstructs the same picture every tick from ~26 separate
# subprocess round-trips -- watchdog.status, pgrep, the poller status, lanes.sh,
# then five `gh` calls per open PR. That reasoning is identical every time and
# it is paid for in the most expensive tier in the estate.
#
# Every judgement moved out of a model and into a script is a permanent saving,
# and this is the largest remaining one: the Director's per-tick state read.
#
# The estate's own research (docs/hierarchy-naming-57.md) prices an LLM-backed
# coordination tier at 30-50% extra tokens; the answer here is not to remove the
# tier but to stop making it re-derive facts a script can hand it.
#
# Usage:
#   digest.sh              human-readable summary
#   digest.sh --json       one JSON object
#
# Exit 0 when the digest was produced. Exit 1 only when it could not be built at
# all -- a partial digest is still emitted, with the failures NAMED. This matters
# more here than usual: this file is what a reader trusts instead of looking, so
# a section that could not be read must say so rather than appear empty. An
# empty `prs` list and an unreachable GitHub must not look the same.

set -uo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
STATE="${SUPERVISOR_STATE:-$HOME/.local/state/agent-dotfiles-supervisor}"
SESSION="${LANES_SESSION:-agent-dotfiles}"
REPOS="${DIGEST_REPOS:-agent-dotfiles skills skills-private agent-evals}"
OWNER="${DIGEST_OWNER:-jonhill90}"
SINCE="${DIGEST_SINCE:-}"
MODE="${1:-}"

ERRORS=()
note_error() { ERRORS+=("$1"); }

# --- watchdog -------------------------------------------------------------
WD_FILE="$STATE/watchdog.status"
if [ -r "$WD_FILE" ]; then
  wd_state=$(awk -F': *' '/^state:/{print $2}' "$WD_FILE" | head -1)
  wd_checked=$(awk -F': *' '/^checked:/{print $2}' "$WD_FILE" | head -1)
  wd_restarts=$(awk -F': *' '/^restarts:/{print $2}' "$WD_FILE" | head -1)
  wd_heartbeat=$(awk -F': *' '/^heartbeat:/{print $2}' "$WD_FILE" | head -1)
else
  wd_state="UNREADABLE"; wd_checked=""; wd_restarts=""; wd_heartbeat=""
  note_error "watchdog.status unreadable at $WD_FILE"
fi

# --- poller ---------------------------------------------------------------
# Liveness by process, health by its own status file. They answer different
# questions: a wedged poller is alive and not listening, and only the second
# catches that.
if pgrep -f "inbox-poll.sh" >/dev/null 2>&1; then poller_alive=true; else poller_alive=false; fi
PL_FILE="$STATE/inbox-poll.status"
if [ -r "$PL_FILE" ]; then
  poller_state=$(awk -F': *' '/^state:/{print $2}' "$PL_FILE" | head -1)
  poller_checked=$(awk -F': *' '/^checked:/{print $2}' "$PL_FILE" | head -1)
else
  poller_state="UNREADABLE"; poller_checked=""
  [ "$poller_alive" = true ] && note_error "inbox-poll.status unreadable while the process is running"
fi

# --- lanes ----------------------------------------------------------------
LANES_OUT=$("$HERE/lanes.sh" "$SESSION" 2>/dev/null)
if [ -z "$LANES_OUT" ]; then
  note_error "lanes.sh returned nothing for session '$SESSION'"
fi
lane_line() { awk -v s="$1" 'NR>1 && $NF==s {print $2}' <<<"$LANES_OUT" | paste -sd, - ; }

# --- pull requests --------------------------------------------------------
# One `gh` call per repo for the PR list, then one per PR for the run. The
# per-PR fields that used to cost four calls each come from the list query.
PR_JSON="[]"
for repo in $REPOS; do
  list=$(gh pr list -R "$OWNER/$repo" --state open \
        --json number,title,headRefOid,headRefName,mergeStateStatus,comments 2>/dev/null) || {
    note_error "gh pr list failed for $OWNER/$repo -- its PRs are NOT in this digest"
    continue
  }
  [ -z "$list" ] && list="[]"
  runs=$(gh run list -R "$OWNER/$repo" --limit 40 \
        --json headSha,conclusion,headBranch 2>/dev/null) || {
    note_error "gh run list failed for $OWNER/$repo -- CI status omitted"
    runs="[]"
  }
  PR_JSON=$(jq -n --argjson acc "$PR_JSON" --argjson prs "$list" \
    --argjson runs "$runs" --arg repo "$repo" '
    $acc + [ $prs[] | . as $p |
      ($runs | map(select(.headBranch == $p.headRefName)) | first) as $r |
      {
        repo: $repo, number: $p.number, title: $p.title,
        head: $p.headRefOid[0:8],
        run_sha: ($r.headSha // "" | .[0:8]),
        run_conclusion: ($r.conclusion // "NO RUN"),
        # the check is stale unless the run was for THIS head -- the field the
        # UI does not distinguish, and a conflicted branch produces no run at all
        ci_is_current: (($r.headSha // "") == $p.headRefOid),
        merge_state: $p.mergeStateStatus,
        verdict: (
          [ $p.comments[]? | select(.body | test("quota limit") | not) ] | last | .body // ""
          | if test("REQUEST CHANGES";"i") then "REQUEST CHANGES"
            elif test("APPROVE";"i") then "APPROVE" else "none" end
        )
      } ]') || note_error "jq failed assembling PRs for $repo"
done

# --- merges since ---------------------------------------------------------
MERGED_JSON="[]"
if [ -n "$SINCE" ]; then
  for repo in $REPOS; do
    m=$(gh pr list -R "$OWNER/$repo" --state merged --limit 30 \
        --json number,title,mergedAt 2>/dev/null) || { note_error "merged-list failed for $repo"; continue; }
    MERGED_JSON=$(jq -n --argjson acc "$MERGED_JSON" --argjson m "${m:-[]}" \
      --arg repo "$repo" --arg since "$SINCE" '
      $acc + [ $m[] | select(.mergedAt > $since) | {repo:$repo, number:.number, title:.title} ]')
  done
fi

ERR_JSON=$(printf '%s\n' "${ERRORS[@]+"${ERRORS[@]}"}" | jq -R . | jq -s 'map(select(. != ""))')

DIGEST=$(jq -n \
  --arg checked "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  --arg wd_state "$wd_state" --arg wd_checked "$wd_checked" \
  --arg wd_restarts "$wd_restarts" --arg wd_heartbeat "$wd_heartbeat" \
  --argjson poller_alive "$poller_alive" --arg poller_state "$poller_state" \
  --arg poller_checked "$poller_checked" \
  --arg free "$(lane_line free)" --arg busy "$(lane_line busy)" \
  --arg blocked "$(lane_line blocked)" --arg menu "$(lane_line menu-blocked)" \
  --arg dead "$(lane_line dead)" --arg service "$(lane_line service)" \
  --arg unknown "$(lane_line unknown)" \
  --argjson prs "$PR_JSON" --argjson merged "$MERGED_JSON" --argjson errors "$ERR_JSON" '
  {checked: $checked,
   watchdog: {state:$wd_state, checked:$wd_checked, restarts:$wd_restarts, heartbeat:$wd_heartbeat},
   poller: {alive:$poller_alive, state:$poller_state, checked:$poller_checked},
   lanes: {free:$free, busy:$busy, blocked:$blocked, menu_blocked:$menu,
           dead:$dead, service:$service, unknown:$unknown},
   prs: $prs, merged_since: $merged, errors: $errors,
   ok: ($errors | length == 0)}')

if [ "$MODE" = "--json" ]; then
  printf '%s\n' "$DIGEST"
else
  jq -r '
    "watchdog: \(.watchdog.state)  restarts=\(.watchdog.restarts)  \(.watchdog.heartbeat)",
    "poller:   alive=\(.poller.alive) state=\(.poller.state)",
    "lanes:    free=[\(.lanes.free)] busy=[\(.lanes.busy)]",
    "          blocked=[\(.lanes.blocked)] menu=[\(.lanes.menu_blocked)] dead=[\(.lanes.dead)]",
    (if (.prs|length) == 0 then "prs:      none open" else "prs:" end),
    (.prs[] | "  \(.repo)#\(.number) ci=\(.run_conclusion)\(if .ci_is_current then "" else " [STALE - run is for \(.run_sha), head is \(.head)]" end) \(.merge_state) verdict=\(.verdict)"),
    (if (.merged_since|length) > 0 then "merged:" else empty end),
    (.merged_since[] | "  \(.repo)#\(.number) \(.title[0:52])"),
    (if (.errors|length) > 0 then "ERRORS (this digest is INCOMPLETE):" else empty end),
    (.errors[] | "  ! \(.)")
  ' <<<"$DIGEST"
fi

[ "${#ERRORS[@]}" -eq 0 ]
