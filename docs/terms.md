# The law, as read on 2026-11-02 (q13)

My call, 2026-11-02, on my reading of section 30(ה) (not legal advice): it allows publishing the headline basket's derived numbers (the page, the method page and the day's JSON), credited to the chains' published files. The raw files stay unpublished; on the same reading the clause would allow that too, but nothing needs it.

## Source

- Page: Nevo's consolidated text, https://www.nevo.co.il/law_html/law00/132302.htm, "חוק קידום התחרות בענפי המזון והפארם, תשע"ד-2014", shown as current as of 19-07-2026. Read by me in my browser on 2026-11-02 at about 21:48 Israel time; the clause below is as I copied it from that page. A web search the same evening also found the government's own consolidated PDF on gov.il ("נוסח מלא ומעודכן", updated 07/2025); not read.
- Earlier basis: the Hebrew Wikisource copy of 2026-07-21 (revision 3025772, read 2026-10-31), whose first sentence has the same wording.
- The law was renamed to cover pharma by a 2025 amendment (amendment 9, found by the web search; the amendment itself not read); the title above is the current one.

## The clause

Section 30(ה), Hebrew as on the page; the English translation is the project's own.

"כל אדם רשאי לגשת לפרסום, למידע ולנתונים הכלולים בו לפי סעיפים קטנים (א) ו־(ד), ולהשתמש בהם, באופן חופשי ובלא תמורה, לצרכים פרטיים או מסחריים; השר, באישור שר האוצר, רשאי לקבוע הוראות להבטחת ביצוען של הוראות סעיף קטן זה."

Anyone may access the publication and the information and data in it under sub-sections (a) and (d), and use them freely and without payment, for private or commercial purposes; the Minister, with the Finance Minister's approval, may set provisions to secure the carrying out of this sub-section.

(The connector between (א) and (ד) came through the copy-paste as "ו-?(ד)"; it is written here in the maqaf form "ו־(ד)", as the Wikisource copy prints it. Which glyph Nevo's page prints is UNVERIFIED and changes nothing.)

## What it asks (my reading)

- Credit: 30(ה) puts no duty on a reuser. Crediting the chains' files is this project's own rule: the credit line on every page (`credit` in `src/basket/words.py`) names the five chains, the law and the files' date, and `src/basket/check.py` refuses a site where any page lacks it, before every upload.
- No misleading presentation: 30(ה) says nothing of it. The risk the project's research named is a misleading-claims suit (the Consumer Protection Authority's spokesman as quoted by Globes via N12, 2025-12-16, a secondary source). The "Words" rules of `docs/headline-basket.md` are how the site meets it: "listed price", "before promotions", "lowest listed total for this basket", the chain's median across its stores; never "cheapest chain", "you'll pay", "at the till"; `src/basket/check.py` refuses a page carrying any of the never-phrases.
- Provisions under 30(ה): whether the Minister has set any is UNVERIFIED; none were looked for.
- Sub-sections 30(א) to (ד) were not read in the official copy. The Wikisource copy's (ב) says the files exist to allow an ongoing comparison of prices and baskets across large retailers, and regulation 4(2) of the 2014 price-transparency regulations says every web user may retrieve any file on an ongoing basis (both read 2026-10-31 from copies, not official texts).
- Changes: before each hand upload I check the "current as of" date on Nevo's page; if it has moved past 19-07-2026, the clause is read again before uploading.
