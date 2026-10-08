*Version 0.1 — under legal review*

*Last updated: 8 October 2026*

## In short

- Tamis stores what you give it: your account details and the content of your reviews (references, PDFs, decisions, extractions).
- Your data is hosted in Frankfurt (Germany, EU).
- We use three cookies, none for analytics or advertising. No tracking, no banner.
- Nothing goes to an AI provider unless a reviewer in your team asks for a suggestion or an extraction.
- You can export everything at any time, delete a review yourself, and ask for your account to be deleted.
- The hosted edition is a non-commercial beta run by the maintainer, an individual based in France. This page has not yet been reviewed by a lawyer.

## Who is responsible

The hosted edition of Tamis (the beta at a .onrender.com address) is run by the maintainer of the project, an independent developer-researcher based in France, as a natural person. Under the GDPR, the maintainer is the data controller. No legal entity exists yet and no paid plan is sold.

If you self-host Tamis (open source, AGPL-3.0), you are the controller of your own instance; this policy does not cover it.

To contact the controller, use the [contact page](/contact).

## What we store

### Your account

- Your name and e-mail address. Both are needed to create an account.
- A hash of your password (Argon2id). We never store the password itself.
- If you sign in with Google: your Google account identifier and the e-mail address verified by Google. We do not receive your Google password.
- Sign-in sessions: a random token kept in an HttpOnly cookie for 30 days; the server stores only its SHA-256 hash.
- One-time sign-in links sent by e-mail: stored hashed, valid for 20 minutes.
- Your interface language and the name of your plan.

### Review content

Everything you and your team put in a review:

- imported references: titles, authors, abstracts, DOIs, keywords and other bibliographic fields;
- uploaded PDFs;
- screening decisions and their reasons, notes and labels, and the time spent on each record;
- extraction forms and the values entered or suggested;
- PRISMA counts;
- an activity log: who did what, and when;
- invitations sent by e-mail to team members;
- AI usage counters (token counts), never the texts exchanged.

If you add your own AI provider key, it is encrypted at rest (Fernet: AES-128-CBC with HMAC, key derived from the server secret), never written to logs, and you can remove it at any time.

### Technical data

Server logs, including IP addresses, are kept for 30 days for security purposes (detecting abuse, diagnosing incidents).

## Why and on what legal basis

| Purpose | Data | Legal basis |
|---|---|---|
| Providing the service (account, reviews, team, exports) | Account and review content | Performance of a contract: the [terms of use](/terms) |
| Sending sign-in links and invitations | E-mail address | Performance of a contract |
| Security, abuse prevention, incident diagnosis | Server logs, IP addresses, activity log | Legitimate interest |
| AI suggestions and extractions | Title and abstract, or PDF text, plus the review's criteria or form | Your consent, given each time a reviewer triggers the feature |

Consent for AI processing is given action by action; you withdraw it by not triggering the feature or by removing your key.

We do not use your data for advertising, profiling or resale, and we do not train AI models with it.

## Cookies

Tamis uses three cookies, all necessary for the service to work:

- `tamis_session`: keeps you signed in (HttpOnly, 30 days);
- a short-lived state cookie during Google sign-in, which protects that step (10 minutes);
- a cookie that remembers your chosen interface language.

No analytics, no advertising, no tracking cookies. Because every cookie is strictly necessary, no cookie banner is needed.

## Where data is hosted and who processes it

The web application, the API, the background worker and the PostgreSQL database run on Render, Inc. in the Frankfurt region (Germany, EU). Render takes regular backups of the database. Uploaded PDFs are stored with the application data, in the EU; an EU object-storage bucket may be used later.

A few third parties process data on our behalf:

| Provider | Purpose | Location |
|---|---|---|
| Render, Inc. | Hosting (app, API, worker, database, backups) | USA company; servers in Frankfurt, EU |
| Resend | Transactional e-mail (sign-in links, invitations) | USA |
| Google | Optional sign-in with a Google account | USA |
| Anthropic, Google or DeepSeek | AI suggestions and extractions, only when a reviewer triggers them | Depends on the provider, may be outside the EU |

Some of these companies are established in the United States. When data leaves the EU, the transfer relies on the European Commission's standard contractual clauses or, where applicable, on the EU-US Data Privacy Framework.

## AI providers

Data leaves Tamis for an AI provider only when a user with reviewer rights triggers a suggestion (screening) or an extraction in a review. Tamis then sends to the provider configured for that review:

- for screening: the title and abstract of the record, and the review's criteria;
- for extraction: the text of the PDF and the extraction form designed by the authors.

The provider is Anthropic (Claude), Google (Gemini) or DeepSeek, as set in the review. The request uses your own API key or, on paid plans once they open, keys held by the service. Each provider applies its own terms: check them before using AI on sensitive material.

AI output is stored apart from human decisions and never counts as a decision. We keep token counts, never the texts.

## How long we keep data

| Data | Retention |
|---|---|
| Account data | Life of the account |
| Reviews and their content | Until the review's owner deletes them |
| Sign-in links | 20 minutes |
| Sessions | 30 days |
| Activity log | With the review |
| Server logs with IP addresses | 30 days |
| Backups | A limited period after deletion, as part of the host's backup cycle |

## Your rights

Under the GDPR you can:

- access the data we hold about you;
- have it corrected;
- have it erased;
- receive it in a portable format;
- object to processing based on legitimate interest;
- lodge a complaint with the CNIL (France) or with the supervisory authority of your own country.

Much of this is self-service:

- export everything from the application at any time: RIS, CSV, Excel, PRISMA;
- a review's owner can delete the review from its danger zone, which deletes its references, PDFs, decisions and extractions;
- remove your AI provider key at any time;
- to delete your account, ask through the [contact page](/contact); it is done within 30 days.

For any other request, use the contact page. We may ask you to confirm your identity.

## Security

- TLS encrypts all traffic in transit.
- Single public origin: browsers never talk to the API directly.
- Passwords are hashed with Argon2id; session and sign-in tokens are stored as hashes.
- AI provider keys are encrypted at rest.
- No secret is ever written to logs.
- The code is public, so anyone can audit it.

Tamis has had no external security audit and holds no certification yet. We say so plainly so you can decide what to upload.

## Children

Tamis is for users aged 16 and over. We do not knowingly collect data from younger people. If you think a child has created an account, tell us through the contact page and we will delete it.

## Changes to this policy

This is version 0.1, still under legal review. It will change as the service grows (proper domain, paid plans, legal entity). We will tell you in the application before a material change applies. The date at the top of this page shows the current version; earlier versions stay in the public source history.
