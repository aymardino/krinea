# Security policy

## Supported versions

| Version | Supported |
|---|---|
| 0.1.x | Yes |
| Earlier snapshots | No |

Security fixes go to the `main` branch and the latest 0.1.x release. The hosted service
at <https://krinea.org> always runs a supported version.

## Reporting a vulnerability

Report it privately, never in a public issue, discussion or pull request:

- by e-mail to **contact@krinea.org**, or
- through GitHub private vulnerability reporting: the **Security** tab of
  <https://github.com/aymardino/krinea>, then **Report a vulnerability**.

Please include what is affected (component, version or commit, the hosted service or a
self-hosted instance), the steps to reproduce, the impact you expect, and whether you
would like to be credited.

## What happens next

- We acknowledge your report within 5 working days.
- We confirm the problem, keep you informed of the fix, and agree with you on a
  disclosure date. Please give us a reasonable time to fix the issue before you
  disclose it.
- Once the fix is released, we publish an advisory and credit you if you wish.

## Testing rules

Test against your own instance (see `README.md` and `docs/deploy-render.md`). Do not
test against the hosted service without warning us first, do not access or change other
people's data, and do not degrade the service (no denial of service, no spam).

## Running your own instance safely

- Set `KRINEA_ENV=production`. The API then refuses to start with an empty, short or
  placeholder `SECRET_KEY`.
- Set `BASE_URL` on the API and `PUBLIC_ORIGIN` on the web app to the public https
  address, so that links sent by e-mail never depend on request headers.
- Serve the web app over HTTPS, keep `COOKIE_SECURE=true`, and keep the API on a private
  network behind the web app's `/api` proxy.
