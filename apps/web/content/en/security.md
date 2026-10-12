*Last updated: 12 October 2026*

## In short

- Your AI provider keys are encrypted before they reach the database, are never written to logs, are shown masked, and can be removed with one click.
- The encryption key lives only in the server's configuration, not in the database: a copy of the database alone cannot reveal your keys.
- Nothing is sent to an AI provider unless a reviewer triggers it, and then only the text needed for that task.
- Everything runs in Frankfurt (EU). Traffic between your browser and Krinea is encrypted with TLS; the web application reaches the API over the host's private network.
- The code is public. Anyone can read how this is done, line by line.

## How your API keys are handled

When you paste a key for Anthropic, Google or DeepSeek, the API encrypts it with authenticated symmetric encryption (Fernet: AES-128 in CBC mode with an HMAC-SHA256 signature) before storing it. The encryption key is derived from a secret that exists only in the hosting environment's configuration; the server refuses to start with a missing, short or placeholder secret. The key is decrypted in memory, for the duration of one request to the provider, and only when you or a reviewer in your team asks for a suggestion or an extraction.

What we never do with your key: write it in logs, display it again in full (you see the first and last characters only), share it between accounts, or use it for anything but the calls you trigger. You can replace or remove it at any time from the AI panel or your settings. Removing it deletes the encrypted value.

If you prefer not to store a key at all, you can use the credits included in paid plans when they open, or self-host Krinea on your own server.

## What reaches an AI provider

Only when a reviewer triggers it, and only for the review concerned:

- title and abstract screening: the record's bibliographic fields (title, authors, year, journal, keywords, abstract), with the review question and the inclusion and exclusion criteria;
- full-text screening: the same, plus the text of the record's PDF;
- extraction: the text of the PDF, with the review question and the extraction form.

The provider you chose for that review is the only one contacted. Krinea stores the provider's answer (the suggestion and its rationale, or the extracted values and their quotes) and, for extraction, the PDF text that was sent, so that each value can be checked against its source. These are stored apart from human decisions; a suggestion never counts as a decision. Usage is metered by counting tokens. The [privacy policy](/privacy) gives the details.

## Accounts and sessions

Passwords are hashed with Argon2id and never stored in clear. Sign-in sessions use a random token kept in an HttpOnly cookie; the server stores only its SHA-256 hash, and expired sessions are deleted. Sign-in links sent by e-mail are single-use, expire after 20 minutes and are deleted after a day. With Google sign-in, no password transits: we keep the Google account identifier and the verified e-mail address.

The first time an e-mail address is verified, by a sign-in link or by Google, any password set on that account before is removed and its other sessions are closed. Someone who registered your address before you therefore cannot keep access to your account.

## Where things run

The web application, the API, the background worker and the PostgreSQL database run at Render in the Frankfurt region (Germany, EU). Traffic between your browser and Krinea is encrypted with TLS (HTTPS). Browsers only ever talk to the web application, which relays requests to the API over the host's private network. Links in e-mails are built from the configured address of the site, never from the address a request claims. Sign-in links and invitations are sent through a mailbox at OVHcloud (France, EU). The database is backed up regularly by the hosting provider. Deleting a review also deletes its PDFs.

## What is not in place yet

Krinea has not been through an external security audit or certification. Two-factor authentication is not available yet. We say so plainly rather than imply otherwise; both are on the roadmap before paid plans open.

## Reporting a vulnerability

If you find a security issue, report it privately, never in a public issue:

- by e-mail to contact@krinea.org, or
- through GitHub private vulnerability reporting: the Security tab of [github.com/aymardino/krinea](https://github.com/aymardino/krinea), then "Report a vulnerability".

Please give us a reasonable time to fix it before disclosure. We acknowledge reports within five working days and will credit you if you wish. Do not test against the hosted service without warning us first. The supported versions and the full policy are in the repository's `SECURITY.md`.
