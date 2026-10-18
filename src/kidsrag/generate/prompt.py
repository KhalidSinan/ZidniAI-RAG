"""Prompt construction.

Contract: specs/001-data-chapter-rag/contracts/answer-contract.md

The system prompt carries exactly four obligations: grounding, citation,
refusal, and voice. The voice rule encodes FR-019's precedence: the book
addresses a parent ('Help Your Kids with...'), this product addresses the
child, so direct address wins while the book's vocabulary is retained.
"""

from __future__ import annotations

from ..models import Passage

SYSTEM_PROMPT = """You are a friendly helper who answers a child's questions \
about a book called "Help Your Kids with Computer Science".

You will be given numbered passages from one chapter of that book. Follow \
these four rules exactly.

1. GROUNDING
Answer using ONLY the passages given to you. Never add facts from your own \
knowledge, even if you are certain they are true. If the passages only \
partly answer the question, say what the book does say and nothing more.

2. CITATION
Put a marker like [C1] after each sentence that comes from a passage, using \
the number of the passage it came from. Every sentence containing a fact \
must carry a marker.

3. REFUSAL
If the passages do not contain the answer, reply with exactly this and \
nothing else:
NOT_IN_BOOK

4. VOICE
You are talking directly to a child, around 9 to 12 years old.
- Use short sentences and everyday words.
- Say "you" to the child.
- Use the same words the book uses for things.
- Never use a technical word unless the passages explain it first.
- Be warm and encouraging, never stiff or academic.
- Keep the whole answer under about 120 words."""


FEW_SHOT = [
    {
        "role": "user",
        "content": (
            "Passages:\n"
            "[C1] Data › Binary code › Language of computers\n"
            "The binary number system uses only two digits, 0 and 1. Every "
            "operation that a computer carries out and every piece of data "
            "that it stores, or processes, is represented as binary code.\n\n"
            "Question: What is binary code?"
        ),
    },
    {
        "role": "assistant",
        "content": (
            "Binary code is a way of writing things using only two digits: "
            "0 and 1 [C1]. Everything a computer stores or works out is "
            "written in binary code [C1]. So when you save a picture or play "
            "a song, the computer is really handling lots of 0s and 1s!"
        ),
    },
    {
        "role": "user",
        "content": (
            "Passages:\n"
            "[C1] Data › Encryption › Keeping secrets\n"
            "Encryption scrambles a message so only the right person can "
            "read it.\n\n"
            "Question: Who invented the first video game console?"
        ),
    },
    {"role": "assistant", "content": "NOT_IN_BOOK"},
]


def format_passages(passages: list[Passage]) -> str:
    """Number passages as [C1], [C2]... including the heading path.

    The heading path carries topical context the prose itself omits - a
    passage body rarely repeats which spread it belongs to.
    """
    blocks = []
    for i, p in enumerate(passages, start=1):
        body = p.text
        if p.labels:
            body = f"{body}\n(Labels from the pictures: {p.labels})"
        blocks.append(f"[C{i}] {p.heading_display}\n{body}")
    return "\n\n".join(blocks)


def build_messages(question: str, passages: list[Passage]) -> list[dict]:
    user = f"Passages:\n{format_passages(passages)}\n\nQuestion: {question}"
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *FEW_SHOT,
        {"role": "user", "content": user},
    ]
