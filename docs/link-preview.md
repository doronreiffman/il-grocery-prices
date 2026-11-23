# The link preview card

**Grade:** the public site's production grade, as for the shopper site: test-first, a planted bug for every rule, a fresh review before merge, and the owner's look at the card before merge.

## What it is for

A link to the site pasted into LinkedIn (or another app that draws link previews) shows a bare card today: the pages carry no preview tags, so the app has no picture and no description to show. The site's first post links its front page, and a bare card is the first thing a reader sees of it. This change gives the front page a card: a picture, a title and one line.

## What changes

The front page alone (the owner, 2026-11-23: the post links the front page; a shared product or store page keeps a bare card) gains these tags in its head, after the title:

| Tag | Content |
|---|---|
| `og:type` | `website` |
| `og:title` | Deal or No Deal: is it actually a deal? |
| `og:description` | Pick the store you're in, look up the product: each sale is checked against what it usually costs there. Shufersal, Rami Levy, Osher Ad, Carrefour and Yochananof. |
| `og:url` | the site's address |
| `og:image` | the site's address, then `assets/card.<hash>.png` |
| `og:image:alt` | the picture's words, as the picture shows them |
| `og:image:width`, `og:image:height` | `1200`, `630` |

The words above are a draft for the owner; the description takes the front page's own sentence. The Open Graph protocol names `og:title`, `og:type`, `og:image` and `og:url` as required on every page that uses it, and says a page with `og:image` should give `og:image:alt` (https://ogp.me/). LinkedIn's help page names `og:title`, `og:image`, `og:description` and `og:url`, and asks for a picture of at least 1200 × 627 pixels, a 1.91:1 ratio, at most 5 MB (https://www.linkedin.com/help/linkedin/answer/a521928). Both read 2026-11-23.

**The site's address** is one constant in the code, `https://d153udx05irk2f.cloudfront.net/`, the address the README already links. Both sources' examples give full addresses, so a path from the site's root is not enough here. A new distribution means a one-line change.

**The picture** (the owner, 2026-11-23: the name and the headline, no prices): the site's name on its green and yellow labels, as the header draws it; "Is it actually a deal?"; the five chains' names; on the light theme's paper. No price, product or date, so it never goes out of date and never needs the sample-data note of the README's screenshot. It is drawn once, as a throwaway page in the site's own fonts, photographed at 1200 × 630 by a headless Chrome on the Mac, and committed as a PNG under `src/shopper/static/`. The PNG is the source; the throwaway page is not kept, as with the look's previews. The site ships it under `assets/` with its hashed name, as it ships the fonts: a changed picture gets a new address, so an app's cached copy of the old one is never served under the new card.

**The upload** learns one file type, `.png` as `image/png`, in the Lambda's upload (`src/basket/site.py`) and the hand upload (`scripts/publish.sh`).

## What the site check adds

The check before upload (`shopper.check`) reads scripts, stylesheets and links today, but not a `<meta>` tag's content. On the front page it gains:

- Each tag in the table exactly once.
- `og:url` is the site's address; `og:image` is the site's address followed by a file under `assets/` that the build holds.
- That file is a PNG whose header gives 1200 × 630, and is at most 5 MB.
- The card's words (title, description, alt text) pass the page's own word rules: no NEVER phrase, no "we", "our" or "us".

Each rule gets a planted bug in `scripts/mutation_check.py`: about eight. The golden pages' pin changes for `index.html` alone.

## Cost

One picture, of the order of 100 KB, stored once and fetched by an app when someone shares the link: under one cent a month.

## Deploy

Its own deploy, after the front page's store labels (q40) are deployed and read live. The card appears at the next morning's site run. Then the owner pastes the front page's address into LinkedIn's Post Inspector (https://www.linkedin.com/post-inspector/) and reads the card. The post waits for that.

## Open points

- **The site asks search engines not to list it** (`noindex`), and stays so. LinkedIn's help page does not say what it does with such a page, and the site has no `robots.txt` (the address answers 403, read 2026-11-23). LinkedIn reads the page anyway: the owner pasted the live front page, still without the card, into Post Inspector before the build (2026-11-23), and its read was fine.
- **LinkedIn keeps a link's preview after it first reads it**; for how long, its help page does not say. So the order is: the card live, Post Inspector shows it, then the post.

## Deviations

What the build changed from the design above, and why.

- **The golden pages' pin moves more than `index.html`.** The pin lists every file the run leaves under `assets/`, so it gains the picture's line; and each built day's line is a digest over the files that day wrote, `index.html` and `assets/` among them, so every day's line moves too. No other file's line moves.
- **`assets/` admits the picture, and the hash rule covers it.** The check already held `assets/` to the stylesheet, the fonts it names and their licences, and refused anything else by name, so it would have refused the picture. It now admits the picture the build makes (`shopper.assets.CARD_IMAGE`), and holds its name to its bytes' hash, as it holds the stylesheet's and the fonts': an upload skips a name the bucket holds, so a name that did not match its bytes would never be corrected. A picture an earlier build left in `assets/` is refused by name, as an old stylesheet is.
- **A NEVER phrase in the card's words needed no rule of its own.** The page's own rule already reads the page as written, attributes included, so it names a NEVER phrase in the card's title, line or alt text, once. Only "we", "our" and "us", which the check seeks in the text a reader sees (no attribute is in it), needed a rule that reads the card's words on their own.
- **5 MB is read as 5,000,000 bytes**, the stricter of its two readings. The picture is 35,832 bytes.
