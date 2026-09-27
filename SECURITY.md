# Security

System One Playground is a local tool. The gateway binds to `127.0.0.1` and has no authentication, so don't expose it on a
network you don't trust.

What the project does to contain model code:
- Local engines run under `sandbox-exec` with outbound network denied and file writes limited to the engine's project, the Hugging Face cache and `.run/`.
- They run with a minimal environment that carries no secrets. Only the Jev proxy receives `TYPESAFE_API_KEY`.

If you find a way around the sandbox, a leaked secret, or anything else security-relevant, please report it privately
with [GitHub's private vulnerability reporting](https://docs.github.com/code-security/security-advisories/guidance-on-reporting-and-writing-information-about-vulnerabilities/privately-reporting-a-security-vulnerability)
on this repository rather than in a public issue.
