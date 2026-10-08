## Why Tamis

Tamis started as a small extraction tool. The maintainer was running a real systematic review on long-term energy-system models in Africa and needed to pull structured data out of hundreds of PDFs without losing track of where each value came from. The script grew a form, then a way to quote the source passage next to every extracted value, then a screening step so the same team could first decide which papers to read at all.

At some point it was clear that the tool was no longer a script. A review needs one place where references, decisions, conflicts, extractions and PRISMA counts live together, where two people can screen blind and then compare, and where the final diagram is computed rather than typed by hand. Tamis is that place. It is built by someone who does reviews, for people who do reviews.

## The name

*Tamis* is the French word for a sieve. A systematic review is mostly sifting: thousands of records go in, a handful of included studies come out, and every record that falls through must be accounted for. The logo is a round sieve with a diagonal mesh.

## What Tamis is, and what it is not

Tamis is a workbench. You use it to:

- import references from RIS, BibTeX, PubMed, Web of Science, Scopus CSV or Excel files;
- remove duplicates;
- screen titles and abstracts, then full texts, alone or as a team, with single or double screening, blind mode and conflict resolution;
- extract data with an AI assistant that fills a form you designed and quotes the passages it relied on;
- report with the PRISMA 2020 counts and flow diagram;
- export your work as RIS, CSV or Excel at any time.

Tamis is not a methods authority. It does not tell you which criteria to use, how many screeners you need or when a study is good enough. Those choices are yours, and you are responsible for them.

The AI suggests; it never decides. Every suggestion is stored apart from human decisions and never counts as one. A record is included, excluded or extracted because a person said so.

For reporting, Tamis follows the PRISMA 2020 statement. The templates are reproduced under CC BY 4.0 from prisma-statement.org (Page MJ et al., BMJ 2021;372:n71).

## Open source

The application is released under the AGPL-3.0 licence. The core engine, the Python package `tamis_core` with the parsers, deduplication, screening rules and extraction schema, is released under the MIT licence so that it can be reused in other tools.

The source code is at [github.com/aymardino/systematic_review](https://github.com/aymardino/systematic_review). Anyone can self-host Tamis with Docker Compose or the Render blueprint. Issues, pull requests and discussions are welcome.

## The hosted edition

A hosted edition exists so that you can try Tamis without installing anything. It is a beta, currently served from a .onrender.com address; a proper domain will come. The web app, the API, the background worker and the database run on Render in Frankfurt, Germany, in the EU.

The hosted edition is operated by the maintainer as a private individual. It is non-commercial for now and provided as is, best effort, with no uptime guarantee. No paid plan is sold yet. Pro and Institution plans are announced on the [pricing page](/pricing) and will open only once billing and legal documents are ready. When they do, paid hosted plans will fund the hosting and the maintainer's time. Whatever happens to the hosted edition, the code stays free under AGPL-3.0.

See the [privacy policy](/privacy), the [terms of use](/terms) and the [legal notice](/legal) for details on data, responsibilities and publication.

## Who is behind it

Tamis is an independent project by an individual developer-researcher based in France, referred to on this site as the maintainer. There is no company or legal entity behind it yet. Tamis is not affiliated with, funded by or endorsed by any institution, company or other review tool. Contributors on GitHub are welcome and credited in the repository.

## How to cite

Cite the version number shown in the app and the repository URL. A DOI will come with the first tagged release.

> Tamis, version X.Y.Z. https://github.com/aymardino/systematic_review

## Contact

For bugs and public questions, use GitHub issues and discussions. For private matters, see the [contact page](/contact).
