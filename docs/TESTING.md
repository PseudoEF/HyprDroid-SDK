# Testing and security limitations

Put the test vector in hyp-tests.json. It contains optional system data and steps.

    {
      "system": {"battery.level": 78, "battery.charging": false},
      "steps": [
        {"text": "Battery: 78%"},
        {"fresh_instance": true, "text": "Battery: 78%"}
      ]
    }

A step supports system overrides, an event containing kind/id/value, exact expect
assertions on frame fields, and a text assertion. Each step starts a fresh Lua
process with the preceding committed snapshot unless fresh_instance is set.
hyp test . --json produces a machine-readable status and frames.

Run python -m unittest discover -s tests -v. The official-vector test checks the
publisher key pin, catalogue and package signatures, Lua contract scenarios and
byte equality with all three published archives.

Run python tools/check-core.py --core-root /path/to/HyprDroid before updating the SDK
for a new Core revision. CI runs the same check against the pinned upstream sources.
A change in those files requires manual contract review and refreshed shared vectors.

## Containment

The harness starts Lua with an argument vector and a restricted environment. No standard Lua
libraries are exposed to module code, including string methods via the host metatable.
Input, output, instruction count and wall time are bounded. POSIX CPU limits apply;
address-space limits apply on POSIX hosts except Android, whose linker reserves a large
virtual range. Windows uses the instruction and wall-time limits. None of these controls
are equivalent to the Android isolated worker, JNI allocator, Binder checks or revocation
policy. Run only developer-controlled Lua in test/preview. Validate and build compile Lua
syntax without executing it. Inspect never runs Lua or extracts an archive.
