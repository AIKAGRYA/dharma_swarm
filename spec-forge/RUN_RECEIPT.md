INITIALIZED 2026-06-11T21:21:33Z head=c131caf9d (smoke session 0, second attempt)
HARNESS-AMENDED 2026-06-11T21:23:42Z head=78da7c2ab (operator-sanctioned prompt-pack fixes pre-launch; evaluator window starts here)
2026-06-11T21:42:50Z F-001 GREEN 41a985357 bun test 527/527 exit 0, grep dharma_swarm tests src empty, 6/6 pre-theme goldens clean, ratchets 4064/40/97 flat
HARNESS-AMENDED 2026-06-11T21:43:49Z head=07d07d13a (operator-sanctioned CODER nits post-smoke; evaluator window starts here)
RUN_START 2026-06-12T00:03:06Z caps=40sessions/10h head=07d07d13a
SESSION 1 coder-start 2026-06-12T00:03:06Z p0_remaining=111
SESSION 2 coder-start 2026-06-12T00:03:16Z p0_remaining=111
SESSION 3 coder-start 2026-06-12T00:03:26Z p0_remaining=111
SESSION 4 coder-start 2026-06-12T00:03:37Z p0_remaining=111
SESSION 5 coder-start 2026-06-12T00:03:47Z p0_remaining=111
SESSION 6 coder-start 2026-06-12T00:03:59Z p0_remaining=111
SESSION 7 coder-start 2026-06-12T00:04:08Z p0_remaining=111
SESSION 8 coder-start 2026-06-12T00:04:19Z p0_remaining=111
SESSION 9 coder-start 2026-06-12T00:04:30Z p0_remaining=111
SESSION 10 coder-start 2026-06-12T00:04:43Z p0_remaining=111
SESSION 11 coder-start 2026-06-12T00:04:53Z p0_remaining=111
SESSION 12 coder-start 2026-06-12T00:05:04Z p0_remaining=111
SESSION 13 coder-start 2026-06-12T00:05:15Z p0_remaining=111
SESSION 14 coder-start 2026-06-12T00:05:25Z p0_remaining=111
SESSION 15 coder-start 2026-06-12T00:05:37Z p0_remaining=111
SESSION 16 coder-start 2026-06-12T00:05:48Z p0_remaining=111
SESSION 17 coder-start 2026-06-12T00:05:59Z p0_remaining=111
SESSION 18 coder-start 2026-06-12T00:06:11Z p0_remaining=111
SESSION 19 coder-start 2026-06-12T00:06:22Z p0_remaining=111
SESSION 20 coder-start 2026-06-12T00:06:34Z p0_remaining=111
SESSION 21 coder-start 2026-06-12T00:06:44Z p0_remaining=111
SESSION 22 coder-start 2026-06-12T00:06:56Z p0_remaining=111
SESSION 23 coder-start 2026-06-12T00:07:07Z p0_remaining=111
SESSION 24 coder-start 2026-06-12T00:07:19Z p0_remaining=111
SESSION 25 coder-start 2026-06-12T00:07:29Z p0_remaining=111
SESSION 26 coder-start 2026-06-12T00:07:41Z p0_remaining=111
SESSION 27 coder-start 2026-06-12T00:07:53Z p0_remaining=111
SESSION 28 coder-start 2026-06-12T00:08:04Z p0_remaining=111
SESSION 29 coder-start 2026-06-12T00:08:15Z p0_remaining=111
SESSION 30 coder-start 2026-06-12T00:08:25Z p0_remaining=111
SESSION 31 coder-start 2026-06-12T00:08:37Z p0_remaining=111
SESSION 32 coder-start 2026-06-12T00:08:49Z p0_remaining=111
SESSION 33 coder-start 2026-06-12T00:09:01Z p0_remaining=111
SESSION 34 coder-start 2026-06-12T00:09:14Z p0_remaining=111
SESSION 35 coder-start 2026-06-12T00:09:25Z p0_remaining=111
SESSION 36 coder-start 2026-06-12T00:09:38Z p0_remaining=111
SESSION 37 coder-start 2026-06-12T00:09:50Z p0_remaining=111
SESSION 38 coder-start 2026-06-12T00:10:02Z p0_remaining=111
SESSION 39 coder-start 2026-06-12T00:10:13Z p0_remaining=111
SESSION 40 coder-start 2026-06-12T00:10:26Z p0_remaining=111
RUN_END 2026-06-12T00:10:36Z head=07d07d13a
HARNESS-AMENDED 2026-06-12T00:16:09Z head=599024b66 (loop key-scrub fix after failed RUN-1; evaluator window starts here)
RUN_START 2026-06-12T00:22:09Z mode=in-session-conductor caps=8cycles/batch head=599024b66
2026-06-12T00:37:25Z F-002 GREEN 0d147e127 boot_smoke exit 0/0, negative exit 1, frame "backend offline, retrying" L21, 527/527 tests, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
2026-06-12T00:52:35Z F-003 GREEN 48382eee0 ls-files grep empty, boot_smoke exit 0 status-delta empty, default-boot delta empty, 527/527 tests 0 fail, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
2026-06-12T01:15:43Z F-004 GREEN 7856c9600 typecheck 0, 527/527 tests 0 fail, status-delta empty across bun test, probe preload mkdtemp both vars, supervisor tree untouched, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
2026-06-12T01:30:33Z F-005 GREEN cefb180d1 pty_smoke exit 0 "> helmprobe" 9 keystrokes bun 1.3.11, negative exit 1, 527/527 tests 0 fail, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
2026-06-12T01:38:34Z F-006 GREEN 947a130ac packageManager bun@1.3.11 grep exit 0, bun test exit 0 527/527 under bun 1.3.11, pty_smoke exit 0 9 keystrokes, ratchets 4064/flat/97, 6/6 pre-theme goldens identical
2026-06-12T01:48:41Z F-007 GREEN a302ca813 ls-files+frozen-install exit 0, blob 5be52a08b as-is, 527/527 tests 0 fail, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
2026-06-12T02:03:43Z F-008 GREEN 7eba0613d ratchet.sh baseline exit 0 max_file_lines=4064, +50-line probe exit 1 then revert clean, typecheck 0, 527/527 tests 0 fail, ratchets 4064/40/97 flat, 6/6 pre-theme goldens identical
HARNESS-AMENDED 2026-06-12T02:11:31Z head=c4dfa1ccf (operator-sanctioned batch-boundary spec amendment F-157..F-170 + CONSTITUTION design-truth pointer; evaluator window starts here)
