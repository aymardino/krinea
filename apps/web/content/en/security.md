*Last updated: 9 October 2026*

## In short

- Your AI provider keys are encrypted before they reach the database, are never written to logs, are shown masked, and can be removed with one click.
- The encryption key lives only in the server's configuration, not in the database: a copy of the database alone cannot reveal your keys.
- Nothing is sent to an AI provider unless a reviewer triggers it, and then only the text needed for that task.
- Everything runs in Frankfurt (EU), over HTTPS, behind a single public origin.
- The code is public. Anyone can read how this is done, line by line.

## How your API keys are handled

When you paste a key for Anthropic, Google or DeepSeek, the API encrypts it with authenticated symmetric encryption (Fernet: AES-128 in CBC mode with an HMAC-SHA256 signature) before storing it. The encryption key is derived from a secret that exists only in the hosting environment's configuration. The key is decrypted in memory, for the duration of one request to the provider, and only when you or a reviewer in your team asks for a suggestion or an extraction.

What we never do with your key: write it in logs, display it again in full (you see the first and last characters only), share it between accounts, or use it for anything but the calls you trigger. You can replace or remove it at any time from the AI panel or your settings. Removing it deletes the encrypted value.

If you prefer not to store a key at all, you can use the credits included in paid plans when they open, or self-host Krinea on your own server.

## What reaches an AI provider

Only when a reviewer triggers it, and only for the review concerned: the title and abstract of a record (screening) or the text of a PDF (extraction), together with the review's criteria or extraction form. The provider you chose for that review is the only one contacted. Krinea stores the provider's answer apart from human decisions; a suggestion never counts as a decision. Usage is metered in tokens, never by storing the texts sent.

## Accounts and sessions

Passwords are hashed with Argon2id and never stored in clear. Sign-in sessions use a random token kept in an HttpOnly cookie; the server stores only its SHA-256 hash. Sign-in links sent by e-mail are single-use and expire after 20 minutes. With Google sign-in, no password transits: we keep the Google account identifier and the verified e-mail address.

## Where things run

The web application, the API, the background worker and the PostgreSQL database run at Render in the Frankfurt region (Germany, EU). All traffic is encrypted in transit (TLS). Browsers only ever talk to the web application, which relays requests to the API on a private network. The database is backed up regularly by the hosting provider.

## What is not in place yet

Krinea has not been through an external security audit or certification. Two-factor authentication is not available yet. We say so plainly rather than imply otherwise; both are on the roadmap before paid plans open.

## Reporting a vulnerability

If you find a security issue, please tell us privately through the [contact page](/contact) rather than in a public issue, and give us a reasonable time to fix it before disclosure. We will acknowledge your report and credit you if you wish.
