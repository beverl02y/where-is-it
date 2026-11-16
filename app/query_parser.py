"""Natural-language question -> object key (SPEC 4.2 #3, AC-02).

Rule-based on purpose: it is instant (helps the < 2 s / < 6 s targets), works
offline, and never invents an object. Unclear questions produce a clarifying
question instead of a guess (SPEC 6.2 'Object name is ambiguous').
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from .appearance import describing_words
from .config import ObjectClass

STOPWORDS = {"is", "are", "the", "my", "a", "an", "where", "did", "i", "put", "leave",
             "left", "find", "can", "you", "me", "help", "now", "please", "it", "was",
             "were", "last", "seen", "see", "whats", "what", "have", "has", "go", "went",
             "to", "in", "of", "room", "do", "know", "tell", "today", "cant", "dont", "looking",
             "for", "lost", "lose", "missing", "search", "locate", "wheres", "whats", "im", "any",
             "some", "our", "this", "that", "again", "please", "show", "check", "could", "would"}


@dataclass
class ParsedQuery:
    status: str                      # ok | ambiguous | unsupported | empty
    object: str | None = None
    candidates: list[str] = field(default_factory=list)
    term: str | None = None          # unsupported word the user typed
    descriptors: list[str] = field(default_factory=list)   # "black", "big", "round" ...


def normalize(text: str) -> str:
    text = text.lower().replace("’", "'").replace("'", "")
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    return " " + re.sub(r"\s+", " ", text).strip() + " "


class QueryParser:
    def __init__(self, objects: dict[str, ObjectClass], ambiguous_terms: dict[str, list[str]]):
        self.objects = objects
        entries: list[tuple[str, tuple[str, ...]]] = []
        for key, obj in objects.items():
            for alias in {*obj.aliases, key, obj.display}:
                entries.append((normalize(alias).strip(), (key,)))
        for term, keys in ambiguous_terms.items():
            entries.append((normalize(term).strip(), tuple(k for k in keys if k in objects)))
        # Longest phrase first so "phone charger" wins over "phone".
        entries.sort(key=lambda e: len(e[0]), reverse=True)
        self._patterns = [(re.compile(rf"\b{re.escape(p)}(?:e?s)?\b"), keys) for p, keys in entries if p]

    def parse(self, question: str) -> ParsedQuery:
        text = normalize(question)
        exact: list[str] = []
        ambiguous: list[tuple[str, ...]] = []
        for pattern, keys in self._patterns:
            if pattern.search(text):
                text = pattern.sub(" ", text)          # consume the phrase
                if len(keys) == 1:
                    if keys[0] not in exact:
                        exact.append(keys[0])
                elif keys:
                    ambiguous.append(keys)

        rest = [w for w in text.split() if w not in STOPWORDS]
        desc = describing_words(rest)
        if len(exact) == 1 and not ambiguous:
            return ParsedQuery("ok", object=exact[0], descriptors=desc)
        if len(exact) > 1:
            return ParsedQuery("ambiguous", candidates=exact)
        if ambiguous:
            cands: list[str] = []
            for group in ambiguous:
                cands += [k for k in group if k not in cands]
            if exact and exact[0] in cands:   # "phone case": 'phone' settles it
                return ParsedQuery("ok", object=exact[0], descriptors=desc)
            return ParsedQuery("ambiguous", candidates=exact + [c for c in cands if c not in exact])

        leftover = [w for w in normalize(question).split() if w not in STOPWORDS]
        if leftover:
            return ParsedQuery("unsupported", term=" ".join(leftover[:6]))
        return ParsedQuery("empty")
