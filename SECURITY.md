# Security Policy

## Supported versions

Only the latest 1.0.x release receives security fixes. Older tags are not
patched; upgrade to the latest release before reporting.

| Version | Supported |
|---------|-----------|
| 1.0.x (latest) | yes |
| earlier | no |

## Reporting a vulnerability

Report vulnerabilities through GitHub's private vulnerability reporting:
open the **Security** tab of the repository and choose **Report a
vulnerability**. Do not open a public issue and do not send the report by
email.

Include the affected version or commit, how the project runs (pip, Docker CPU,
Docker GPU, web UI), steps to reproduce, and the impact you see.

## What to expect

- An acknowledgement within one week.
- A fix or a documented mitigation in the next release, with credit in
  `CHANGELOG.md` unless you ask otherwise.
- The report stays private until a fix is published.

## Deployment notes

The defaults are tuned for a machine on a private network. Before exposing
the server further, know that:

- Authentication is off unless `TTS_TOKENS` is set. Without it every client
  that can reach the port can synthesize, upload voice samples and read the
  history.
- `ttssrv` listens on all interfaces (`TTS_HOST=0.0.0.0`) on port 5000 by
  default. Bind it to `127.0.0.1` or keep it behind the bundled nginx when the
  host has a public address.
- The web UI's certificate is self-signed and generated on first start. It is
  there so browsers allow the microphone on the LAN; it is not a substitute for
  a real certificate.
- On the internet, run the stack behind your own reverse proxy with a real
  certificate, set `TTS_TOKENS`, and do not publish port 5000 directly.
