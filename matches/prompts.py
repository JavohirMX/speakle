"""Conversation starters shown on the match page, so partners are never stuck
with "so... what do we talk about?" in the first minute of a call."""
import random

LEVEL_PROMPTS = {
    'warmup': [
        "What did you do today?",
        "What is your favourite food, and how do you make it?",
        "Describe your morning routine.",
        "What is the weather like where you are?",
        "Tell me about your family or close friends.",
    ],
    'everyday': [
        "What is a place in your city every visitor should see?",
        "What do you do to relax after a long week?",
        "Which song or show are you into right now, and why?",
        "Describe your dream holiday.",
        "What was the last thing that made you laugh?",
    ],
    'deeper': [
        "What is one thing you changed your mind about recently?",
        "What is hard about learning a language, in your experience?",
        "What would you do differently if you could start your career again?",
        "How has technology changed the way people in your country live?",
        "What does a good life look like to you?",
    ],
}

SWAP_TIPS = [
    "Split the call in half: 15 minutes in one language, then switch.",
    "Ask your partner to correct only the mistakes that block understanding.",
    "Write down 3 new words after the call and use them next time.",
]


def conversation_prompts(teach_name=None, learn_name=None, count=6, seed=None):
    """Return a list of prompt dicts: {'level': str, 'text': str}.

    Mixes levels so the list starts easy and gets deeper. `seed` makes the
    result deterministic (used in tests).
    """
    rng = random.Random(seed)
    per_level = max(1, count // len(LEVEL_PROMPTS))
    out = []
    for level in ('warmup', 'everyday', 'deeper'):
        pool = LEVEL_PROMPTS[level][:]
        rng.shuffle(pool)
        out.extend({'level': level, 'text': t} for t in pool[:per_level])
    return out[:count]


def swap_tip(seed=None):
    return random.Random(seed).choice(SWAP_TIPS)
