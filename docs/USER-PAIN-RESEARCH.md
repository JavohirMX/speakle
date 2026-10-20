# What language-exchange users complain about, and what Speakle does about it

Written by an AI coding assistant. These are user posts, so each one is an anecdote: self-selected, unverified, not a survey. I read the pages listed. I did not read app-store review pages, and I make no claim about how common any complaint is.

## Sources read

- r/languagelearning, "Language exchange app, more like dating app?" (Apr 2025): first partner asked for a face photo in the second message; top replies say state your purpose, block, or avoid the apps. https://www.reddit.com/r/languagelearning/comments/1jyojjn/language_exchange_app_more_like_dating_app/
- r/languagelearning, "Tandem used as a dating app" (Aug 2023): poster says most profile visitors were not who they expected. https://www.reddit.com/r/languagelearning/comments/15m85y1/tandem_used_as_a_dating_app/
- r/HelloTalk, "Am I the only one struggling?" (Jul 2025): 197 messages in 3 days from many people, requests for Instagram, bio says language exchange only; a reply points to the "Block unknown chat" setting. https://www.reddit.com/r/HelloTalk/comments/1ls3jw4/am_i_the_only_one_struggling/
- r/languagelearning, "AITA for always running out of topics to talk and eventually ghosting my study buddies" (Apr 2022): topics run out, people drift away; advice is to plan something to practise and ask open questions. https://www.reddit.com/r/languagelearning/comments/uczw6o/aita_for_always_running_out_of_topics_to_talk_and/
- italki community post, "Why did you stop talking to your exchange partner?" (2018): partners not interested in conversation, big level gaps, time-zone problems after a good text chat. https://www.italki.com/en/post/discussion-184252
- r/languagelearning, "Tandem keep getting worst and worst" (Oct 2024): ads, daily conversation limits even on premium, billing complaints. https://www.reddit.com/r/languagelearning/comments/1gfkex2/tandem_keep_getting_worst_and_worst/
- Trustpilot, Tandem reviews (read, not counted): several reviews allege bans with no explanation or support. https://www.trustpilot.com/review/tandem.net
- speaky.space blog, "The Language Exchange Commitment Problem" (Aug 2025). This is a competitor's marketing content, so I use it only as a description of the problem, not as evidence. https://www.speakyspace.com/blog/language-exchange-commitment

## Themes and where Speakle stands

| Pain | Seen in | Speakle today | Action |
| --- | --- | --- | --- |
| Dating-style approaches, photo and Instagram asks | 3 Reddit threads | Chat starts only after a request is accepted. Block and report exist. A profile photo is optional. | Cap on new requests (this PR). Ideas below. |
| Message and request floods | r/HelloTalk thread | Receiver must accept first. No cap on how many requests one account sends. | **Done here:** `MATCH_REQUESTS_PER_DAY` (default 20, rolling 24h, 0 = off). |
| Running out of things to say, then ghosting | Reddit 2022, italki | Conversation prompts and a 5-minute trial call exist. | None now. |
| Time zones make planning hard | italki | No time zone on profiles. | Follow-up: optional time zone on the profile, shown as the partner's local time on requests and matches. Needs a small additive migration. |
| Level mismatch | italki | Level adds a bonus to the match score. | None now. |
| Ads, daily limits, paywalls | Reddit 2024 | Speakle has none. | Do not add them. |
| Bans with no explanation | Trustpilot | Reports are reviewed in admin. The reporter is not told the outcome. | Follow-up: tell the reporter that a report was reviewed. |

## Ideas not built (need a decision)

- A "language practice only" line on every request the receiver sees, so the stated purpose is not left to each user's bio. Honest and cheap, but it is policy copy, so it needs John's wording.
- A soft label on a request message that asks to move to Instagram, WhatsApp or similar. Keyword lists have false positives, so label only, never block.
- Time zone field and local-time display (above).

## What this PR does

New requests per sender are capped per rolling 24 hours. Pending requests to the same person do not count again. A re-opened request counts as new. The web form and the JSON endpoint both answer with a plain message ("You've sent a lot of requests today. Wait for replies, then try again tomorrow."), HTTP 429 on the API. No migration.
