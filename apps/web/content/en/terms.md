*Version 0.1, under legal review. Last updated: 8 October 2026.*

## In short

- Krinea is open-source software. These terms cover the hosted beta only. If you self-host, the AGPL-3.0 licence applies instead.
- The hosted edition is free today and run by the maintainer, a private individual. It is provided as is, best effort, with no uptime guarantee.
- You own everything you put in Krinea. We use it only to run the service for you. You can export or delete it at any time.
- AI output is a suggestion. You stay responsible for your review.
- You must be at least 16, keep your credentials safe and respect the copyright of the PDFs you upload.
- French law applies. If something goes wrong, we talk first.

## What the service is

Krinea is an open-source workbench for systematic reviews: import references, remove duplicates, screen with a team, extract data with an AI that quotes its sources, report with PRISMA 2020, export. See the [about page](/about).

The application is released under the AGPL-3.0 licence; its core engine, the Python package `krinea_core`, under the MIT licence. The source code is at [github.com/aymardino/systematic_review](https://github.com/aymardino/systematic_review).

These terms apply only to the **hosted edition**: the beta instance operated by the maintainer, currently at a .onrender.com address and hosted on Render in Frankfurt (Germany, EU). "We" means the maintainer, an independent developer-researcher based in France, who runs the service as a natural person. No legal entity exists yet. See the [legal notice](/legal).

If you self-host Krinea (Docker Compose, Render blueprint), these terms do not apply: the licences govern your use, and you are responsible for your instance and its users.

By creating an account or using the hosted edition, you accept these terms.

## Your account

- You must be at least 16 years old.
- Give an accurate e-mail address: it is how you sign in and how we reach you about the service. See the [privacy policy](/privacy).
- Keep your credentials safe. You are responsible for what is done under your account. If you think it has been compromised, tell us through the [contact page](/contact).
- One person per account. Do not share an account; invite collaborators to the review instead.
- You can sign in with Google. Google's own terms apply to that sign-in. We receive only your Google account identifier and verified e-mail address.

## Acceptable use

Use the service for research work, lawfully and fairly. You must not:

- upload or share content that is unlawful, defamatory or that infringes someone else's rights;
- upload a PDF you do not have the right to use: publisher licences and open-access terms decide this, and we cannot check it for you;
- scrape, probe or attack the service, or use it to attack others;
- circumvent limits, quotas or access controls, or access other people's reviews without an invitation;
- resell the hosted edition or present it as your own service.

The code is public. Auditing it and reporting a vulnerability on GitHub is welcome. Testing against the hosted instance without warning us is not.

## Your content

You own the references, PDFs, decisions, notes, forms, extractions and other content you put in Krinea. We claim no rights over it.

You grant us a licence limited to operating the service: storing and backing up your content, showing it to the people you invite, and processing it when you ask (deduplication, exports, AI features). It ends when you delete the content or your account, subject to the backup cycle described in the [privacy policy](/privacy).

You can export everything at any time (RIS, CSV, Excel, PRISMA). The owner of a review can delete it from its danger zone, which deletes its references, PDFs, decisions and extractions. Account deletion is requested through the [contact page](/contact) and done within 30 days.

AI suggestions are stored apart from human decisions and never count as a decision. You are responsible for your review: its criteria, the number of screeners, how conflicts are resolved, what is extracted and what is reported. Krinea is a tool, not a methods authority.

## AI features

Nothing is sent to an AI provider unless a user with reviewer rights triggers a suggestion or an extraction in a review. Then the title and abstract (screening) or the text of the PDF (extraction), plus the review's criteria or form, go to the provider configured for that review: Anthropic (Claude), Google (Gemini) or DeepSeek.

Today, AI features run with your own API key. It is encrypted at rest, never written to logs, and you can remove it at any time. You are responsible for that key, for the costs the provider bills you, and for complying with the provider's terms. We keep usage counters (token counts, never the texts). On paid plans, once they open, keys held by the service may be used instead.

AI output can be wrong. Check it; never include, exclude or extract on a suggestion alone.

## Plans and payment

The hosted edition is free today. Pro and Institution plans are announced on the [pricing page](/pricing) but are not for sale until billing and the related legal documents are published. When they open, prices will be shown on [/pricing](/pricing) before you subscribe. You will never be charged without an explicit sign-up to a paid plan.

## Availability and changes

The hosted edition is a beta, provided as is and best effort, with no uptime guarantee. We may carry out maintenance, change or remove features, set limits, and move the service to another address (a proper domain will come).

If we discontinue the hosted edition, or change it in a way that removes something essential, we will give at least 60 days' notice by e-mail or in the application and keep an export window open during that period. The software remains available under AGPL-3.0, so you can self-host it and import your exports.

## Liability

The hosted edition is provided "as is" and "as available", without warranty of any kind, to the extent permitted by law. It is a non-commercial beta run by an individual. We do not guarantee that it is error-free, that data will never be lost, or that it fits a particular purpose. Keep your own exports.

To the extent permitted by law, we are not liable for indirect damage, loss of data or research time, or the consequences of your methodological choices or of AI output. Nothing here excludes liability that cannot be excluded under French law, such as for gross negligence, wilful misconduct or personal injury.

No external security audit or certification has been carried out yet. The security measures are described in the [privacy policy](/privacy), and the code is public for anyone to audit.

## Termination

You can stop at any time: export your data, delete your reviews, and ask for your account to be deleted through the [contact page](/contact).

We can suspend or close an account that breaks these terms, in particular for abuse, unlawful content or attacks on the service. Where possible, we will warn you first and give you time to export. In urgent cases, such as an ongoing attack, we may act at once and explain afterwards. After termination, your data is deleted as described in the [privacy policy](/privacy).

## Governing law and disputes

These terms are governed by French law. The hosted service is published from France.

If you have a complaint, contact us first through the [contact page](/contact); most problems can be settled amicably. Failing that, the dispute goes to the competent French courts, without prejudice to the mandatory consumer-protection rules of your country of residence.

## Changes to the terms

We may update these terms, in particular when paid plans open or when a legal entity is created. We will announce material changes by e-mail or in the application before they take effect; if you do not agree, export your data and close your account. The current version is always at [/terms](/terms), alongside the [privacy policy](/privacy) and the [legal notice](/legal).
