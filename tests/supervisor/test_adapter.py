import sys
import tempfile
import unittest
from pathlib import Path


SUPERVISOR_DIR = Path(__file__).resolve().parents[2] / "scripts" / "supervisor"
sys.path.insert(0, str(SUPERVISOR_DIR))

from adapter import ACPAdapter, TmuxAdapter, classify_capture, command_verdict  # noqa: E402
from core import Ledger  # noqa: E402


class FakeTransport:
    def __init__(self):
        self.panes = {
            "%19": {
                "pane_id": "%19",
                "command": "codex",
                "path": "/repo/hill90",
                "server_id": "server-a",
                "session_id": "$4",
                "capture": "─ Worked for 1m ─\n\n› Continue\n",
                "options": {},
                "after_send": "• Working (1s • esc to interrupt)\n\n› Continue\n",
            },
            "%8": {
                "pane_id": "%8",
                "command": "claude.exe",
                "path": "/repo/hill90",
                "server_id": "server-a",
                "session_id": "$4",
                "capture": "✻ Crunched for 1s\n\n❯ \n────────────────\n",
                "options": {},
                "after_send": "✻ Thinking…\n\n❯ \n────────────────\n",
            },
        }
        self.sends = []

    def metadata(self, target):
        return dict(self.panes[target])

    def capture(self, target, lines=25):
        return self.panes[target]["capture"]

    def set_option(self, target, name, value):
        self.panes[target]["options"][name] = value

    def get_option(self, target, name):
        return self.panes[target]["options"].get(name, "")

    def send_literal(self, target, payload):
        self.sends.append((target, payload))
        self.panes[target]["capture"] = payload + "\n" + self.panes[target]["after_send"]


class AdapterTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ledger = Ledger(Path(self.tempdir.name), clock=lambda: 1_000)
        self.transport = FakeTransport()
        self.adapter = TmuxAdapter(self.ledger, self.transport, clock=lambda: 1_000)
        self.adapter.register_lane(
            lane="architecture", target="%19", harness="codex", repo="/repo/hill90", nonce="nonce-19"
        )
        self.adapter.register_lane(
            lane="infra-claude", target="%8", harness="claude", repo="/repo/hill90", nonce="nonce-8"
        )
        self._source_number = 899

    def seed_source(self, task_id, summary):
        self._source_number += 1
        self.ledger.reconstruct_task(
            task_id=task_id,
            source_kind="issue",
            source_url=f"https://github.com/jonhill90/Hill90/issues/{self._source_number}",
            source_ref="a" * 40,
            summary=summary,
            source_state="OPEN",
            status="created",
            evidence=[],
            status_marker=None,
        )

    def test_harness_classifiers_cover_idle_active_blocked_and_approval(self):
        self.assertEqual("idle", classify_capture("codex", "─ Worked for 1m ─\n\n› Continue\n"))
        self.assertEqual("active", classify_capture("codex", "• Working (2s • esc to interrupt)\n› Continue\n"))
        self.assertEqual("blocked", classify_capture("codex", "■ You've hit your usage limit.\n› Continue\n"))
        self.assertEqual("idle", classify_capture("claude", "✻ Crunched for 1s\n\n❯ \n────────\n"))
        self.assertEqual("active", classify_capture("claude", "✻ Thinking…\n\n❯ \n────────\n"))
        self.assertEqual("blocked", classify_capture("claude", "You've hit your weekly limit · resets tomorrow\n❯ \n"))
        self.assertEqual("approval", classify_capture("claude", "Allow this command? [Y/n]\n❯ \n"))

    def test_assignment_is_task_bound_and_accepts_real_codex_and_claude_activity(self):
        self.seed_source("codex-task", "Review one artifact")
        self.seed_source("claude-task", "Inspect one issue")
        codex = self.adapter.assign_task(
            lane="architecture", task_id="codex-task", summary="Review one artifact"
        )
        claude = self.adapter.assign_task(
            lane="infra-claude", task_id="claude-task", summary="Inspect one issue"
        )
        self.assertEqual("delivered", codex["status"])
        self.assertEqual("delivered", claude["status"])
        self.assertIn("codex-task", self.transport.sends[0][1])
        self.assertIn("claude-task", self.transport.sends[1][1])
        self.assertIn("complete", self.transport.sends[0][1])

    def test_blocked_lane_gets_no_assignment_input(self):
        self.transport.panes["%8"]["capture"] = "You've hit your weekly limit\n❯ \n"
        with self.assertRaisesRegex(RuntimeError, "blocked"):
            self.adapter.assign_task(lane="infra-claude", task_id="blocked-task", summary="Do not send")
        self.assertEqual([], self.transport.sends)
        self.assertIsNone(self.ledger.get_task("blocked-task"))

    def test_idle_outstanding_task_emits_attention_without_observed_transition(self):
        self.seed_source("short-task", "Short review")
        self.adapter.assign_task(lane="architecture", task_id="short-task", summary="Short review")
        self.transport.panes["%19"]["capture"] = "Review finished\n─ Worked for 2m ─\n\n› Continue\n"
        event = self.adapter.observe_lane("architecture")
        self.assertEqual("attention:short-task", event["key"])
        repeated = self.adapter.observe_lane("architecture")
        self.assertEqual(event["key"], repeated["key"])

    def test_blocked_after_echo_does_not_ack_architecture_notification(self):
        self.seed_source("review-task", "Review")
        self.adapter.assign_task(lane="infra-claude", task_id="review-task", summary="Review")
        self.ledger.complete("review-task", b"# Result\n\nNo findings.\n", pane_nonce="nonce-8")
        self.transport.panes["%19"]["after_send"] = "■ You have hit your usage limit.\n\n› Continue\n"
        notified = self.adapter.notify_architecture(lane="architecture", retry_after=900)
        self.assertFalse(notified)
        event = self.ledger.get_event("completion:review-task")
        self.assertEqual("pending", event["status"])

    def test_reused_pane_id_with_wrong_nonce_is_rejected_before_send(self):
        self.transport.panes["%19"]["options"]["@hill90_lane_nonce"] = "reused"
        with self.assertRaisesRegex(RuntimeError, "incarnation"):
            self.adapter.assign_task(lane="architecture", task_id="wrong-pane", summary="Must not send")
        self.assertEqual([], self.transport.sends)

    def test_ambiguous_send_persists_delivery_pending_and_blocks_automatic_resend(self):
        def failing_send(target, payload):
            self.transport.sends.append((target, payload))
            raise RuntimeError("tmux send-keys timed out")

        self.seed_source("flaky-task", "Ambiguous delivery")
        self.transport.send_literal = failing_send
        with self.assertRaisesRegex(RuntimeError, "timed out"):
            self.adapter.assign_task(lane="architecture", task_id="flaky-task", summary="Ambiguous delivery")

        task = self.ledger.get_task("flaky-task")
        self.assertEqual("delivery_pending", task["status"])
        self.assertEqual(1, len(self.transport.sends))

        # A never-attempted task simply has no ledger row at all.
        self.assertIsNone(self.ledger.get_task("never-attempted"))

        # The same task id cannot be silently resent while unconfirmed.
        with self.assertRaisesRegex(RuntimeError, "reconcile"):
            self.adapter.assign_task(lane="architecture", task_id="flaky-task", summary="Ambiguous delivery")
        self.assertEqual(1, len(self.transport.sends))

        # A human, not echoed pane text, resolves the ambiguity.
        reconciled = self.ledger.reconcile_delivery("flaky-task", pane_nonce="nonce-19", outcome="failed")
        self.assertEqual("failed", reconciled["status"])

    def test_successful_send_does_not_infer_delivery_from_echoed_prompt_text(self):
        # Even though the pane echoes the sent prompt back into its own capture,
        # assign_task must not use that capture to decide the task was delivered.
        self.seed_source("quiet-task", "No echo needed")
        self.transport.panes["%19"]["after_send"] = "flaky terminal chrome, no active/idle marker\n"
        task = self.adapter.assign_task(lane="architecture", task_id="quiet-task", summary="No echo needed")
        self.assertEqual("delivered", task["status"])

    def test_one_hundred_unchanged_observations_send_nothing(self):
        for _ in range(100):
            self.assertIsNone(self.adapter.observe_lane("architecture"))
            self.assertFalse(self.adapter.notify_architecture(lane="architecture", retry_after=900))
        self.assertEqual([], self.transport.sends)

    def test_blocked_approval_and_unknown_outstanding_tasks_emit_durable_attention(self):
        """Red: observe_lane only calls ledger.observe_idle when state == "idle";
        blocked/approval/unknown states hit `return None` and produce no
        durable event at all -- a restart between the pane going blocked and a
        human noticing loses that signal entirely."""
        self.seed_source("needs-help", "Review")
        self.adapter.assign_task(lane="architecture", task_id="needs-help", summary="Review")
        for capture_text, reason in (
            ("■ You've hit your usage limit.\n› Continue\n", "blocked"),
            ("Allow this command? [Y/n]\n› Continue\n", "approval"),
            ("unexpected terminal chrome with no recognizable marker\n", "unknown"),
        ):
            with self.subTest(reason=reason):
                self.transport.panes["%19"]["capture"] = capture_text
                event = self.adapter.observe_lane("architecture")
                self.assertIsNotNone(event, f"no durable event for {reason}")
                self.assertEqual(f"attention:needs-help:{reason}", event["key"])


class NodeCollisionTest(unittest.TestCase):
    """agent-dotfiles#234: `codex` and `copilot` both run as the process name
    `node`, so the plausibility check accepted EITHER for a `node` pane. A
    lane recorded `codex` that is really running copilot was silently
    admitted -- the first case in this estate where the failure was "told
    something false, cannot check it, so accept" rather than "cannot tell,
    so refuse" (#124/#126's one-way ratchet).

    The check is three-valued now: confirmed, contradicted, ambiguous --
    and ambiguous withholds. `argv` (the pane's foreground command line,
    which names the tool even when `comm` reads `node`) is what turns an
    ambiguous answer into a confirmed one; without it, both Node harnesses
    stay withheld.
    """

    COPILOT_ARGV = "node /opt/homebrew/bin/copilot --allow-all"
    CODEX_ARGV = "node /Users/jon/.npm-global/lib/node_modules/@openai/codex/bin/codex.js"

    def pane(self, command, argv=""):
        return {
            "pane_id": "%7",
            "command": command,
            "path": "/repo/hill90",
            "server_id": "server-a",
            "session_id": "$4",
            "argv": argv,
        }

    def adapter(self, pane):
        tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(tempdir.cleanup)
        transport = FakeTransport()
        transport.panes["%7"] = dict(pane, capture="", options={}, after_send="")
        return TmuxAdapter(Ledger(Path(tempdir.name), clock=lambda: 1_000), transport)

    def test_the_bug_a_lane_recorded_codex_whose_pane_really_runs_copilot_is_refused(self):
        """THE REPRODUCTION. `node` + argv naming copilot contradicts a
        recorded `codex`. Before #234 this registered without complaint."""
        adapter = self.adapter(self.pane("node", self.COPILOT_ARGV))
        with self.assertRaisesRegex(RuntimeError, "lane harness mismatch"):
            adapter.register_lane(
                lane="t:7", target="%7", harness="codex", repo="/repo/hill90", nonce="n"
            )

    def test_the_mirror_a_lane_recorded_copilot_whose_pane_really_runs_codex_is_refused(self):
        adapter = self.adapter(self.pane("node", self.CODEX_ARGV))
        with self.assertRaisesRegex(RuntimeError, "lane harness mismatch"):
            adapter.register_lane(
                lane="t:7", target="%7", harness="copilot", repo="/repo/hill90", nonce="n"
            )

    def test_a_node_pane_whose_argv_names_its_own_harness_still_registers(self):
        """THE OTHER DIRECTION, and it is what keeps the refusals honest:
        fail-closed must not become always-closed. A correctly recorded
        Node lane is still admitted, because argv confirms it."""
        for harness, argv in (("copilot", self.COPILOT_ARGV), ("codex", self.CODEX_ARGV)):
            with self.subTest(harness=harness):
                adapter = self.adapter(self.pane("node", argv))
                record = adapter.register_lane(
                    lane="t:7", target="%7", harness=harness, repo="/repo/hill90", nonce="n"
                )
                self.assertEqual(harness, record["harness"])

    def test_a_node_pane_with_no_readable_argv_is_withheld_from_both(self):
        """The residue, stated as behaviour: `ps` unavailable, the process
        already gone, an argv that names neither tool -- nothing confirms
        either harness, so neither is admitted. Withheld, never admitted."""
        for argv in ("", "node", "node /usr/local/bin/some-other-node-cli"):
            for harness in ("codex", "copilot"):
                with self.subTest(argv=argv, harness=harness):
                    adapter = self.adapter(self.pane("node", argv))
                    with self.assertRaisesRegex(RuntimeError, "lane harness mismatch"):
                        adapter.register_lane(
                            lane="t:7", target="%7", harness=harness, repo="/repo/hill90", nonce="n"
                        )

    def test_an_unambiguous_command_needs_no_argv_at_all(self):
        """`claude`/`claude.exe`/`codex` name exactly one harness between
        them, so nothing about those lanes changed -- they never needed
        argv and must not start needing it (every pre-#234 lane is one)."""
        for harness, command in (("claude", "claude"), ("claude", "claude.exe"), ("codex", "codex")):
            with self.subTest(command=command):
                adapter = self.adapter(self.pane(command))
                record = adapter.register_lane(
                    lane="t:7", target="%7", harness=harness, repo="/repo/hill90", nonce="n"
                )
                self.assertEqual(harness, record["harness"])

    def test_a_visibly_contradicted_command_is_still_refused(self):
        """Unchanged from #216: `claude` recorded against a `node` pane."""
        adapter = self.adapter(self.pane("node", self.COPILOT_ARGV))
        with self.assertRaisesRegex(RuntimeError, "lane harness mismatch"):
            adapter.register_lane(
                lane="t:7", target="%7", harness="claude", repo="/repo/hill90", nonce="n"
            )

    def test_every_later_operation_rechecks_argv_not_just_registration(self):
        """`_verified_lane` runs the same check on every assign/observe, so
        a pane that was copilot at registration and is codex now stops
        being the lane it was registered as."""
        pane = self.pane("node", self.COPILOT_ARGV)
        adapter = self.adapter(pane)
        adapter.register_lane(
            lane="t:7", target="%7", harness="copilot", repo="/repo/hill90", nonce="n"
        )
        adapter.transport.panes["%7"]["argv"] = self.CODEX_ARGV
        with self.assertRaisesRegex(RuntimeError, "pane incarnation does not match"):
            adapter.observe_lane("t:7")

    def test_the_verdict_names_which_of_the_two_failures_it_is(self):
        """Contradicted and ambiguous are different operator problems: one
        means the record is wrong, the other means the evidence is missing.
        The refusal has to say which."""
        self.assertEqual("confirmed", command_verdict("copilot", "node", self.COPILOT_ARGV))
        self.assertEqual("ambiguous", command_verdict("copilot", "node", ""))
        self.assertEqual("ambiguous", command_verdict("codex", "node", ""))
        self.assertEqual("contradicted", command_verdict("claude", "node", self.COPILOT_ARGV))
        self.assertEqual("contradicted", command_verdict("copilot", "claude", ""))
        self.assertEqual("confirmed", command_verdict("claude", "claude.exe", ""))


class FakeACPTransport:
    """Stands in for a freshly `ACPTransport.spawn()`-ed process per call --
    the CLI is one process per command, so there is no live subprocess to
    reuse between `assign_task` invocations (see `ACPTransport.load_session`
    docstring)."""

    instances = []

    def __init__(self, sessions=None, stop_reason="end_turn", message="Done."):
        self.sessions = sessions if sessions is not None else {}
        self.stop_reason = stop_reason
        self.message = message
        self.initialized = False
        self.loaded_sessions = []
        self.prompts = []
        self.closed = False
        self.terminated = False
        self.__class__.instances.append(self)

    def initialize(self, **kwargs):
        self.initialized = True
        return {}

    def new_session(self, cwd, **kwargs):
        session_id = f"sess-{len(self.sessions) + 1}"
        self.sessions[session_id] = cwd
        return session_id

    def load_session(self, session_id, *, cwd):
        self.loaded_sessions.append((session_id, cwd))
        return session_id

    def send_literal(self, target, payload):
        self.prompts.append((target, payload))
        return {
            "stop_reason": self.stop_reason,
            "message": self.message,
            "token_usage": {"input_tokens": 10, "output_tokens": 5},
            "context_window": None,
        }

    def close(self):
        self.closed = True

    def terminate(self):
        self.terminated = True
        self.close()


class ACPAdapterTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tempdir.cleanup)
        self.ledger = Ledger(Path(self.tempdir.name), clock=lambda: 1_000)
        FakeACPTransport.instances = []
        self.shared_sessions = {}
        self.adapter = ACPAdapter(
            self.ledger,
            lambda: FakeACPTransport(sessions=self.shared_sessions),
            clock=lambda: 1_000,
        )
        self._source_number = 899

    def seed_source(self, task_id, summary):
        self._source_number += 1
        self.ledger.reconstruct_task(
            task_id=task_id,
            source_kind="issue",
            source_url=f"https://github.com/jonhill90/Hill90/issues/{self._source_number}",
            source_ref="a" * 40,
            summary=summary,
            source_state="OPEN",
            status="created",
            evidence=[],
            status_marker=None,
        )

    def test_register_lane_opens_an_acp_session_and_stores_it_as_the_lane_identity(self):
        record = self.adapter.register_lane(
            lane="copilot-worker", target=None, harness="copilot-acp", repo="/repo/hill90", nonce="nonce-acp"
        )
        self.assertEqual("copilot-acp", record["harness"])
        self.assertEqual(record["pane_id"], record["session_id"])
        self.assertTrue(FakeACPTransport.instances[0].initialized)
        self.assertTrue(FakeACPTransport.instances[0].closed)

    def test_assign_task_resumes_the_session_and_completes_synchronously_from_the_stop_reason(self):
        self.adapter.register_lane(
            lane="copilot-worker", target=None, harness="copilot-acp", repo="/repo/hill90", nonce="nonce-acp"
        )
        self.seed_source("acp-task", "Review one artifact")
        task = self.adapter.assign_task(lane="copilot-worker", task_id="acp-task", summary="Review one artifact")
        self.assertEqual("complete", task["status"])

        # A fresh transport was spawned for this call and closed afterward --
        # no subprocess lingers between CLI invocations.
        assign_transport = FakeACPTransport.instances[-1]
        self.assertTrue(assign_transport.closed)
        self.assertEqual(1, len(assign_transport.loaded_sessions))
        self.assertIn("acp-task", assign_transport.prompts[0][1])

    def test_assign_task_to_unregistered_lane_raises(self):
        with self.assertRaisesRegex(RuntimeError, "unknown lane"):
            self.adapter.assign_task(lane="missing", task_id="t1", summary="x")

    def test_observe_lane_is_a_no_op_because_prompts_are_synchronous(self):
        self.adapter.register_lane(
            lane="copilot-worker", target=None, harness="copilot-acp", repo="/repo/hill90", nonce="nonce-acp"
        )
        self.assertIsNone(self.adapter.observe_lane("copilot-worker"))


if __name__ == "__main__":
    unittest.main()
