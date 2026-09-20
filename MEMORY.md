# MEMORY.md

## Stable Lessons

- TRE should move bulk files with null-safe or `find ... -exec` patterns, not brittle `xargs` pipelines.
- When Giacomo asks for an internal system task, TRE should execute it directly, verify it, and only then report back.
- OpenClaw runs locally on Giacomo's Mac through the local gateway; Ollama is remote on the VPS.
- OpenClaw's browser profile is `chromium`; Google Chrome and the `chrome` profile are excluded.
- Chromium has its own profile. GCloud, Tailscale, and GitHub may need one-time interactive login in Chromium.
- Money-related actions are never performed. A successful report requires post-action evidence, not an intention or drafted command.
- For internet work, TRE uses web_search for discovery, web_fetch for readable sources, and the OpenClaw Chromium profile for dynamic or authenticated pages; it records sources and verifies every browser action.
- The workspace skill web-research is the standard procedure for current research, source comparison, prompt-injection resistance, and post-action verification.
