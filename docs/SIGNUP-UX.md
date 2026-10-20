# Sign-up flow: audit, evidence and proposal

Written by an AI coding assistant for the repo owner. Evidence is labelled **confirmed** (I opened the page and read the passage), **citation only** (I confirmed the reference exists, not its content) or **unverified**.

## 1. Audit of the old flow

One page, 9 inputs, all on one screen before any value:

| Field | Required | Shown to anyone? |
| --- | --- | --- |
| First name | yes | **No.** Nothing in the app displays it (checked all templates). |
| Last name | no | No. |
| Username | yes | Yes, it is the public name and the login. |
| Email | yes | No (confirmation link, resets). |
| I already speak | yes | Yes, drives matching. |
| I want to practise | yes | Yes, drives matching. |
| Level | yes | Small matching bonus (30/20/10 points). Already pre-set to Beginner. |
| Password | yes | No. |
| Type it again | yes | No. |

- Mobile: the Create button sat at y = 1387 px on a 390x844 screen, so 1.6 screens of form.
- Email confirmation does not block anything except Quick match. Good, keep it.
- There is no Turnstile or other captcha in this repo. Spam control is a per-IP sign-up cap (`SIGNUPS_PER_HOUR_PER_IP`, off by default).
- Already good: password rules visible up front, Show button, inline validation, auto sign-in after sign-up.

Screenshots: `docs/img/signup-before-mobile.png`, `docs/img/signup-before-desktop.png`.

## 2. Evidence

**Confirmed**

- NN/g, "A Checklist for Registration and Login Forms on Mobile" (Budiu, 2017): ask for the minimum, "ideally, email and password should be enough"; do not repeat fields (two password boxes), offer Show instead; disclose password rules up front; offer social login while noting not everyone uses it; do not require email-link confirmation, because switching apps can disorient people; make registration optional where features allow. It cites a University of Munich study that mobile password entry takes about twice as long per character. https://www.nngroup.com/articles/checklist-registration-login/
- web.dev (Google), "Sign-up form best practices": "ask for as little as possible"; collect more only when the user sees a clear benefit; do not double up inputs; consider a code instead of a password; offer federated login. https://web.dev/articles/sign-up-form-best-practices
- NN/g, "Progressive Disclosure" (Nielsen, 2006): show the few important options first, offer the rest on request. https://www.nngroup.com/articles/progressive-disclosure/
- NN/g, "Password Creation: 3 Ways To Make It Easier": show the rules while typing, let people see the input. https://www.nngroup.com/articles/password-creation/
- NN/g, "The EAS Framework for Simplifying Forms": every question is a "withdrawal" from a bank account of trust; reciprocity means people share more once trust is built; eliminate first, then automate, then simplify. https://www.nngroup.com/articles/eas-framework-simplify-forms/
- NN/g, "Don't Force Users to Register Before They Can Buy" (Schade, 2015): offer registration after the task; state benefits from the user's side; mark password as optional where it is. E-commerce setting. https://www.nngroup.com/articles/optional-registration/
- Baymard, "Save Account Creation for the Confirmation Step" (2023): in their testing, asking to create an account early made some people hesitate or stop; 42% of benchmarked sites do it anyway. Qualitative, checkout setting. https://baymard.com/research-articles/delayed-account-creation
- Malheiros and Preibusch, "Sign-Up or Give-Up" (SOUPS 2013 workshop): observational study of drop-out in three services' registration forms. People drop out more or less depending on how much they value the service they came from. https://cups.cs.cmu.edu/soups/2013/trustbusters2013/Sign_up_or_Give_up_Malheiros.pdf
- Kahneman, Knetsch and Thaler (1990), endowment effect: people value what they already hold more than what they do not (abstract read). https://ideas.repec.org/a/ucp/jpolec/v98y1990i6p1325-48.html

**Counter-evidence worth knowing (confirmed)**

- Huang et al., "Not Registered? Please Sign-up First", Information Systems Research (randomized field experiment, US online retailer): asking new users to register at the start, before the later request, made them 58% relatively more likely to register, with no short-term effect on conversion and higher long-term purchases. So an early registration *request* is not automatically harmful. It was a request, not a wall, in e-commerce. Our case (account needed to match anyone) is different, and this does not argue for long forms. https://faculty.marshall.usc.edu/jinchi-lv/publications/ISR-HMSLG21.pdf

**Citation only**

- Freedman and Fraser (1966), foot-in-the-door: a small first request raises compliance with a bigger later one. J. Personality and Social Psychology 4(2), 195-202. https://doi.org/10.1037/h0023552
- Sweller (1988), cognitive load. Cognitive Science 12(2), 257-285. https://doi.org/10.1016/0364-0213(88)90023-7

**Unverified / not found**

- Apple HIG "Managing accounts" returned no readable text, so I make no claim from it. Stripe docs: not checked.
- I found no peer-reviewed A/B test on email-verification timing for a service like this. NN/g's advice against link confirmation is expert guidance, not an experiment.
- Search results include vendor blog A/B tests on form length (for example "14 fields to 4"). I did not read or use them. Do not quote their numbers.
- How these results transfer to Speakle (a video language exchange, not a shop) is my inference. Only an A/B test on real sign-ups would settle it.

## 3. What changed (this PR)

The form asks for the two languages first, then a username, email and one password. Level is a collapsed "Your level (Beginner unless you change it)" control.

| | Before | After |
| --- | --- | --- |
| Inputs | 9 | 5 visible, 1 collapsed |
| Create button, 390x844 | y = 1387 px | y = 1037 px |

Why each choice:

- **Dropped first and last name.** Nothing shows them. Collecting data nobody uses costs trust for no benefit (web.dev, EAS). Both stay editable on the profile page. Existing accounts are unaffected.
- **Dropped "Type it again".** NN/g and web.dev both advise against doubled inputs. The Show button and the visible rules cover typos. Forgotten passwords use the existing reset email.
- **Languages first.** They are the part that is about the product, cheap to answer, and the reason the person came. This is a foot-in-the-door ordering (citation only), and it keeps the commitment on what they want rather than on paperwork. My inference, not tested.
- **Level collapsed, defaulting to Beginner.** Progressive disclosure. It was already pre-set to Beginner, so most people never changed it. Anyone can change it later, and matching scores read the saved value.
- **Kept the languages required.** The data model and matching need them (sign-up is all-or-nothing by design).
- **Kept the username.** It is the login and the only public name.

No migration, no model change. Existing tests pass; new tests cover the field list, defaults, chosen level, and that password rules still apply.

Screenshots: `docs/img/signup-after-mobile.png`, `docs/img/signup-after-desktop.png`.

## 4. Options not built (need a decision)

1. **Social login (Google/Apple).** Fewer fields and no password, per web.dev and NN/g. Needs OAuth client credentials and a privacy review, and the username/login model would need a generated username. Not built.
2. **Email-code sign-in instead of a password.** Removes the password field entirely (web.dev mentions it). Needs email deliverability to be reliable first.
3. **Ask for the username after sign-up.** Would make the first step languages + email + password. Needs a generated temporary username, because login is by username today.
4. **Measure it.** The app has privacy-friendly page counters. A sign-up funnel count (page view, submit, success) by form version would show whether this helps. Not added here.
