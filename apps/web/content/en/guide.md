This guide follows a review from the first import to the PRISMA diagram. Each section names the tab of the review where the work happens: Data, Screening, Full text, Extraction, PRISMA, Exports and Settings.

## Before you start

**One review, one project.** Create a review from your dashboard, then open **Settings**:

- **General**: the title and the **research question**. Write the question early: the AI reads it.
- **Screening criteria**: inclusion criteria, exclusion criteria and the list of exclusion reasons (one per line), plus the keywords highlighted in green and red.
- **Team**: invite people by e-mail and give each a role, set how many reviewers must screen each record, and turn blind mode on or off.
- **AI**: the provider and models used for suggestions and extraction (Google Gemini by default, with `gemini-3.8-flash`).

**Roles.**

- *Owner* and *Admin* change the settings, criteria, keywords and files, and settle conflicts.
- *Reviewer* screens and extracts.
- *Viewer* reads and exports.

**AI is optional.** Suggestions and extraction drafts use your own API key (Google Gemini, Anthropic Claude or DeepSeek). The key is stored encrypted, and you can add it in the AI panel of the Screening tab or in your account settings. The AI proposes and never decides: its answers are kept apart from human decisions.

## 1. Import your searches (Data tab)

Click **Add search results** and upload your exports: RIS, BibTeX, PubMed (`.nbib`), Web of Science (`.txt`), CSV, TSV or Excel. Naming the source database (Scopus, PubMed…) is optional; PRISMA counts the records of each source.

Each file stays a separate import. You can delete it, filter the lists by it, and give it its own keywords, criteria and extraction fields. If your review has several sub-questions, import **one file per search**: the rest of Krinea can then work search by search.

## 2. Remove duplicates (Data tab)

**Detect duplicates** compares every record:

- same DOI, or identical title: always merged;
- titles at least 95 % similar (adjustable), with the same first author or the same year: merged automatically;
- titles between 85 % and 95 % similar: listed under **Pairs to check**, where you choose **Keep this one** or **Different, keep both**;
- below 85 %: different studies.

Duplicates are never deleted: they are set aside, and **Restore** or **Restore all** brings them back.

**Which record is kept.** In **Settings**, **Record kept among duplicates** offers three rules:

- the most complete record (the default);
- the order of your imported files;
- the order of the databases.

The record kept gets its empty fields filled from the others, and every source that found the study counts for PRISMA.

**One search per sub-question: choose the order of your files.** With this rule, each study belongs to the file of its kept copy, and to it alone. Everything follows that file: the file filters, the AI runs, the keywords and criteria of each search, the extraction fields of each search and the exports. Rank the searches whose criteria should win first.

**Detect duplicates before screening.** A new detection starts again from scratch: the pairs you settled by hand come back to check, and if another copy of a study is kept, the decisions made on the previous copy no longer count. Avoid running it again once screening has started.

## 3. Title and abstract screening (Screening tab)

The page has three columns: the list on the left, the reference in the middle, panels on the right.

**The list.**

- **Views**: To screen, Included by me, Maybe, Excluded by me, Conflicts, Included, Excluded, All.
- **Filters**: imported file, label, and a search box.
- **List order**: import order, title, year, first author, journal, *AI: include first* or *AI: exclude first*.
- The list loads 200 references at a time. The links at both ends, and **Next** and **Previous**, go on to the following ones.

**Deciding.**

- **Include**, **Maybe** or **Exclude**.
- When you exclude, choose an **exclusion reason**. *No reason* empties the field; a reason only counts for an exclusion.
- **Labels** (comma-separated) are shared with the team and can be filtered. A **note** stays with your decision.
- **Clear my decision** takes it back.
- Keyboard: **I** include, **M** maybe, **E** exclude, **←** **→** (or **J** **K**) move, **P** opens the PDF.

**Keywords.** Green and red highlights help you read. The review has its own, and each search can add its own when a file is selected. Click a keyword to show only the references that mention it; with several keywords, choose *All of them* or *At least one*. Keywords are a visual aid only: the AI never reads them.

**Criteria of the search.** When a search has its own sub-question and inclusion or exclusion criteria, the right column shows them for the reference on screen (or for the file the list is filtered on). Admins enter them there. They add to the review's criteria, for you and for the AI.

**Working as a team.** With two reviewers or more per record (**Settings**, **Team**), a record is decided when the required decisions agree; otherwise it goes to **Conflicts**, where an admin settles it with **Resolve as consensus**. In blind mode, reviewers do not see each other's decisions; admins do.

## 4. AI suggestions (Screening and Full text tabs)

**What the AI receives for each reference:**

- the research question;
- the review's criteria;
- the criteria of the reference's search, if it has any;
- the list of exclusion reasons;
- the record: title, abstract, keywords and so on.

At full text it also gets the text of the PDF, up to 120,000 characters; for a longer document, the beginning and the end. It never receives the highlight keywords.

**Running it.** In the AI panel:

- set **References per run**: 50 by default at title and abstract, 1 at full text. **The whole list** fills in the most the list allows.
- Click **Ask the AI for suggestions**.

The run starts with the reference on screen and follows the list as filtered and ordered, going back to the top at the end. It skips the references you have decided and those that already have a suggestion, unless you tick **Also redo the references that already have a suggestion**. A run of more than 500 references asks first. Long runs go on in the background, and you can keep working.

**Using a suggestion.** The reference shows the AI's decision, its confidence and its reasons. **Accept suggestion** records it as your own decision. Otherwise a suggestion never counts as a decision.

**Cost.** Each reference is one call billed to the key used, unless the provider's free tier covers it. A daily quota may stop a run; the next run picks up where it stopped.

## 5. Full-text screening (Full text tab)

This tab holds the references included at title and abstract.

**Getting the PDFs:**

- **Upload PDF**;
- **Find open-access PDF** (needs a DOI);
- once a PDF is there, **Replace PDF** or **Remove PDF**.

The views **No PDF yet** and **Not retrievable** list what is missing.

**Reports you cannot obtain.** Click **Not retrievable**. The reference leaves *To screen* and the count of what is left, and PRISMA counts it among the *reports not retrieved*: it needs neither a decision nor a reason. Click again to undo.

**Deciding** works as at title and abstract, with a reason for each exclusion. PRISMA lists the full-text exclusion reasons.

**AI at full text** only takes references with a PDF. A scanned PDF without text is set aside without asking the AI, and the AI panel says how many.

## 6. Data extraction (Extraction tab)

### The form (Settings, Extraction form)

Each field has:

- a **Key**: its identifier, used to store the data, as the column name in exports and in what the AI reads;
- a **Label**: the name you read in the extraction view;
- a **Kind**;
- **Options**, for the enum and multi kinds;
- an **Instruction for the AI**;
- **Searches**: which searches the field belongs to;
- **Required**: whether it must be filled in.

The arrows set the order of the fields: the order of the form, of the AI's instructions and of the export columns. **Templates** start you with a PICO form or an energy-modelling form.

**From a spreadsheet.** **Import a form (CSV, Excel)** fills the form from a file with one row per field and the column names in the first row: Key, Label, Kind, Options, Instruction for the AI, Required, Searches (the French names work too). Searches are file names, separated by `;` or `|`. Nothing is saved until you click **Save**, and Krinea lists what it could not read. **Download the form (Excel)** gives a model to fill in.

**Kinds.**

| Kind | What the AI returns |
|---|---|
| text | a short text |
| sentences | one or two sentences |
| number | a number |
| year | a year |
| yesno | yes or no |
| enum | one of the options |
| multi | one or more of the options |
| list | a comma-separated list |
| search | nothing: Krinea fills it in |

A *search* field is filled in by Krinea with the study's search, the name of the file of its kept copy. It is never asked of the AI. Add it only if you want that column.

**Fields of some searches.** Leave **Searches** on *All* for a field asked of every study, or tick one or more searches. A study then shows, gets extracted and is checked with the general fields and those of its own search only.

**Do not rename a key once studies are extracted:** their values are stored under it. Change the label instead.

### Extracting and verifying

**How the AI extracts.** The AI reads each study's PDF once, with all of its fields together, and returns each value with a short verbatim quote. An instruction can therefore refer to another field by its key, for example "Strands touched other than main_strand"; place the field referred to first.

**Running the AI.** **Extract with AI** runs on the studies shown that have a PDF and no draft yet; filter the list to run it on fewer. In an open study, **Run AI again** redoes that one only.

**Verifying.** Open a study to see the values next to the PDF and its extracted text. Errors and warnings point to what needs a look: a required field left empty, a value outside the options, a missing quote. Correct what needs it, then click **Save as verified**. The AI's values are kept next to the verified ones.

## 7. Exports (Exports tab)

**Choose the stage:**

- title and abstract screening: every record left after duplicates;
- full-text screening: the records kept at title and abstract;
- data extraction: the studies included at full text.

**Filters.** Decision, exclusion reason, PDF (at full text), imported file and label. Each filter takes several values: a record passes when it matches any value ticked in a filter, and every filter used. The number of records is shown before you download.

**Formats.** RIS for a reference manager, CSV, or Excel.

- **Screening exports** give, for each record, its status and reason at both stages, its PDF, labels and notes, the file of its kept copy (`file`) and every file that found it (`files`).
- **Extraction exports** hold the verified extractions, or every included study with the status of its extraction. The Excel file has three sheets: values, quotes and the form.

**Other exports.** The decision log, the PRISMA counts, and all records with duplicates included.

In blind mode, reviewers only export their own decisions and reasons.

## 8. PRISMA 2020 (PRISMA tab)

The counts and the flow diagram are computed from your decisions: there is nothing to retype. Choose one of the four official templates (new or updated review, with databases only or with other methods too), then **Download SVG**. The page also shows the records found in each source and the full-text exclusion reasons.

## Good practice

- Import one file per search, and set the order of your files before detecting duplicates.
- Write the research question and the criteria before running the AI. Check a few suggestions before a large run.
- Export your work regularly and keep your own copies.
