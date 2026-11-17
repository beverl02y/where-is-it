"""SEARCH and EXPLAIN steps.

Decision flow for "Where is my X?" (SPEC 4.1, 6.1, 6.2):

  1. Parse the question -> object (or ask to clarify / say unsupported).
  2. CURRENT: if a recent camera frame exists and X is in it with conf >= 75%
     -> report location, time, confidence as a fact.                   (AC-03)
  3. HISTORY: otherwise find the most recent confirmed (>= 75%) record.  (AC-04)
     -> report last-seen location and time.                             (AC-05)
  4. CONTEXT: low-confidence (< 75%) sightings newer than the last confirmed one
     are offered ONLY as a labelled possibility.                         (AC-06)
  5. SAFE FAILURE: nothing reliable -> say it could not be found, explain that it
     may be outside the camera's view. Never guess.                     (4.2 #7)

Wording rules: confidence is never shown as 100%, and the system never says that
a person or pet moved anything.
"""
from __future__ import annotations

import math
import re
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from .appearance import CANON, COLOURS, best_matches, describing_words, item_name, record_terms, singular, words
from .config import Settings
from . import korean as K
from . import scope as S
from .rag import should_use_rag
from .db import Database, DetectionRecord, to_iso
from .query_parser import STOPWORDS, QueryParser


@dataclass
class Answer:
    status: str                       # current | last_seen | possible | not_found | clarify | unsupported
    message: str
    object: str | None = None
    location: str | None = None
    seen_at: str | None = None        # ISO-8601 in the user's timezone
    confidence: float | None = None
    confirmed: bool = False
    suggestion: str | None = None
    elapsed_ms: float = 0.0
    lang: str = "en"                  # "ko" when the question was asked in Korean
    source: str = "rules"             # rules = instant rule answer; rag = Gemini answer from the records

    def to_dict(self) -> dict:
        return asdict(self)


# real item words (from the Korean dictionary's English side): never "corrected" into another item
REAL_ITEM_WORDS = {w for en in K.ITEMS.values() for w in words(en)}


def one_slip(a: str, b: str) -> bool:
    """True if b is a with one letter added, missing or changed, or two neighbours swapped."""
    if a == b:
        return False
    if len(a) == len(b):
        diff = [i for i in range(len(a)) if a[i] != b[i]]
        return len(diff) == 1 or (len(diff) == 2 and diff[1] == diff[0] + 1
                                  and a[diff[0]] == b[diff[1]] and a[diff[1]] == b[diff[0]])
    if abs(len(a) - len(b)) != 1:
        return False
    s, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == s for i in range(len(l)))


def pct(conf: float) -> str:
    """Format confidence; never claim 100% certainty (SPEC 6.2).
    Rounds DOWN so a score below the 75% threshold never shows as 75% (golden GC-03)."""
    return f"{min(math.floor(conf * 100 + 1e-9), 99)}%"


class SearchEngine:
    def __init__(self, settings: Settings, db: Database, parser: QueryParser | None = None, rag=None):
        self.s = settings
        self.db = db
        self.rag = rag                     # RagAnswerer, or None = rules only
        self.parser = parser or QueryParser(settings.objects, settings.ambiguous_terms)
        self.tz = ZoneInfo(settings.timezone)

    # ---------- wording helpers ----------
    def _display(self, key: str) -> str:
        return self.s.objects[key].display if key in self.s.objects else key

    def _words(self, key: str) -> dict[str, str]:
        if key in self.s.objects:
            name, plural = self.s.objects[key].display, self.s.objects[key].plural
        else:   # any other item Gemini found, e.g. "water bottle", "keys"
            name = key
            plural = key.endswith("s") and not key.endswith("ss")
        if plural:
            return dict(name=name, be="are", was="were", pron="they", Pron="They", isnt="aren't")
        return dict(name=name, be="is", was="was", pron="it", Pron="It", isnt="isn't")

    @staticmethod
    def _singular(phrase: str) -> str:
        out = []
        for w in phrase.split():
            if len(w) > 3 and w.endswith("ies"):
                w = w[:-3] + "y"
            elif len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
                w = w[:-1]
            out.append(w)
        return " ".join(out)

    def _resolve_other(self, term: str, dev: str | None = None) -> tuple[str, list[str], list[str], str]:
        """Match what the user typed ("my bottle", "white mask", "facemask") to items Gemini has seen.
        Describing words (colour, size, shape) are taken out first and returned separately.
        "bottle" matches every kind of bottle seen ("water bottle", "glass bottle"), so all of
        them are answered together. Returns (ok | none, keys, describing words, item name)."""
        typed = words(term)
        desc = describing_words(typed)
        item = [w for w in typed if w not in desc] or typed       # "clear" alone is still a name
        t = item_name(singular(" ".join(item)), self.s.same_items)
        tw = t.split()
        known = [k for k in self.db.known_objects(dev) if k not in self.s.objects]
        same = lambda k: item_name(singular(k), self.s.same_items)
        whole = item_name(singular(" ".join(typed)), self.s.same_items)   # "glass bottle" as one name
        exact_whole = [k for k in known if same(k).replace(" ", "") == whole.replace(" ", "")]
        if exact_whole and whole != t:
            return "ok", exact_whole[:1], [], same(exact_whole[0])
        joined = t.replace(" ", "")
        # the same name, or a kind of it: "bottle" -> "water bottle" (not "bottle opener")
        found = [k for k in known
                 if same(k).replace(" ", "") == joined
                 or (set(tw) <= set(same(k).split()) and same(k).split()[-1] == tw[-1])]
        if not found:   # a more general name was saved: "blue glass bottle" -> "bottle"
            found = [k for k in known if set(same(k).split()) <= set(tw)]
        if not found:
            return "none", [], desc, t
        found.sort(key=lambda k: same(k) != t)                    # exact name first
        return "ok", found[:6], desc, (same(found[0]) if len(found) == 1 else t)

    def _name_words(self, question: str, key: str, desc: list[str], dev: str | None) -> list[str]:
        """Other words in the question that match how some saved items look, e.g. "airpods"
        when one of the earphones was described as "white airpods case". Words that match
        every saved item of that kind (like "earphones" itself) are left out."""
        keys = [key] if isinstance(key, str) else list(key)
        skip = STOPWORDS | set(desc) | {x for k in keys for x in words(k) + words(self._display(k))}
        typed = [CANON.get(x, x) for x in words(question) if x not in skip and singular(x) not in skip]
        if not typed:
            return []
        recs = self.db.history(key, dev)
        terms = [record_terms(r) | {singular(x) for x in record_terms(r)} for r in recs]
        out = []
        for x in typed:
            hits = sum(1 for tset in terms if x in tset or singular(x) in tset)
            if 0 < hits < len(terms):
                out.append(x)
        return out

    def _when(self, dt: datetime, now: datetime) -> str:
        local = dt.astimezone(self.tz)
        today = now.astimezone(self.tz).date()
        clock = local.strftime("%I:%M %p").lstrip("0")
        if local.date() == today:
            return f"at {clock} today"
        if local.date() == today - timedelta(days=1):
            return f"yesterday at {clock}"
        return f"on {local.strftime('%b')} {local.day} at {clock}"

    def _supported(self) -> str:
        return ", ".join(o.display for o in self.s.objects.values())

    # ---------- Korean wording ----------
    def _when_ko(self, dt: datetime, now: datetime) -> str:
        return K.when_ko(dt.astimezone(self.tz), now.astimezone(self.tz).date())

    def _supported_ko(self) -> str:
        return ", ".join(K.KEY_KO.get(k, o.display) for k, o in self.s.objects.items())

    @staticmethod
    def _place_ko(r: DetectionRecord) -> str:
        return K.place_ko(r.location, r.location_label, r.location_ko)

    def _label_ko(self, r: DetectionRecord) -> str:
        return r.appearance_ko or K.item_ko(r.object, r.name_ko)

    def _listing_ko(self, recs: list[DetectionRecord], now: datetime, when: bool = False) -> str:
        return ", ".join((f"{self._when_ko(r.detected_at, now)} " if when else "")
                         + f"{self._place_ko(r)}에 {'있던' if when else '있는'} {self._label_ko(r)} "
                         f"({pct(r.confidence)})" for r in recs)

    def _possibility_ko(self, rec: DetectionRecord, name: str, now: datetime) -> str:
        return (f"가능성 (확인되지 않음): {self._when_ko(rec.detected_at, now)}의 낮은 신뢰도 감지"
                f"({pct(rec.confidence)})로 보면 {K.josa(name, '이가')} {self._place_ko(rec)}에 있을 수도 있어요. "
                f"먼저 그곳을 확인해 보세요.")

    def _possibility(self, rec: DetectionRecord, w: dict, now: datetime) -> str:
        return (f"Possibility (not confirmed): a low-confidence detection ({pct(rec.confidence)}) "
                f"{self._when(rec.detected_at, now)} suggests {w['pron']} might be {rec.location_label}. "
                f"You could check there first.")

    # ---------- main entry ----------
    def ask(self, question: str, now: datetime | None = None, device_id: str | None = None) -> Answer:
        """Answer for ONE camera device: only that device's records are searched.

        0. not about a belonging (brain, boyfriend, "quit", distances, write code) -> instant answer
        1. several items ("phone and signboard") -> each one answered by the rules
        2. rules: instant, free, exact
        3. Gemini (RAG) only for questions the rules can't handle, never for a question
           that contains instructions for the AI ("ignore your rules ...")
        """
        t0 = time.perf_counter()
        now = now or datetime.now(timezone.utc)
        ko = K.is_korean(question)
        kind = S.out_of_scope(question, lambda q: self._names_item(q, device_id))
        if kind:
            ans = Answer("not_found", S.message(kind, ko))
        else:
            parts = self._item_parts(question, device_id)
            if parts:
                ans = self._combine([self._ask(p, now, device_id) for p in parts])
            else:
                ans = self._ask(question, now, device_id)
                if self.rag and not getattr(ans, "final", False) and not S.is_injection(question) and should_use_rag(
                        question, ans, self.s, lambda name: bool(name and self.db.history(name, device_id, limit=1))):
                    ans = self.rag.answer(question, now, device_id, self.tz, fallback=ans)
        ans.lang = "ko" if ko else "en"
        ans.elapsed_ms = round((time.perf_counter() - t0) * 1000, 1)
        return ans

    # ---------- helpers for ask() ----------
    def _item_names(self, dev: str | None) -> set[str]:
        """Every item name the system knows, whole ("house key", not "house"): aliases of the key
        items, other names in config.yaml and the names Gemini has used for this camera."""
        names = set(self.s.same_items) | set(self.s.same_items.values())
        for key, o in self.s.objects.items():
            names |= {key, o.display, *o.aliases}
        names |= set(self.db.known_objects(dev))
        return {n.lower() for n in names if n}

    def _vocabulary(self, dev: str | None) -> set[str]:
        """Every word that appears in a known item name."""
        names = self._item_names(dev)
        return {w for v in names for w in words(v)} | {v.replace(" ", "") for v in names}

    def _names_item(self, question: str, dev: str | None) -> bool:
        """Does the question name an item the system knows? ("heart keychain" is an item)"""
        if K.is_korean(question):
            eng, _, typed = K.to_english(question, self.db.korean_names(dev))
            if eng and typed:                         # a known item was found (not just an unknown word)
                return True
            question = re.sub(r"[가-힣]+", " ", question)
        p = self.parser.parse(question)
        if p.status in ("ok", "ambiguous"):
            return True
        vocab = self._vocabulary(dev)
        return any(w in vocab or singular(w) in vocab for w in words(question) if w not in STOPWORDS)

    def _item_parts(self, question: str, dev: str | None) -> list[str] | None:
        """"phone and signboard" -> ["phone", "signboard"], when every part names something.
        "black and white wallet" is NOT split: "black" alone names nothing."""
        parts = S.split_items(question)
        if len(parts) < 2 or S.is_injection(question):
            return None
        for p in parts:
            if K.is_korean(p):
                _, unknown, typed = K.to_english(p, self.db.korean_names(dev))
                if not (typed or unknown):
                    return None
            else:
                content = [w for w in words(p) if w not in STOPWORDS and w not in S.FILLER_EN]
                if not content or not [w for w in content if w not in describing_words(content)]:
                    return None
                # a part that names no known item must look like a short item name ("signboard"),
                # not a sentence ("ignore all rules")
                if len(content) > 2 and not self._names_item(p, dev):
                    return None
        return parts

    @staticmethod
    def _combine(answers: list[Answer]) -> Answer:
        """One answer for several items: every item's sentence, in the order asked.
        status / location / confidence come from the best-supported item."""
        order = {"current": 0, "last_seen": 1, "possible": 2, "clarify": 3, "not_found": 4, "unsupported": 5}
        best = min(answers, key=lambda a: order.get(a.status, 9))
        sugg = " ".join(a.suggestion for a in answers if a.suggestion) or None
        return Answer(best.status, " ".join(a.message for a in answers),
                      object=", ".join(a.object or "?" for a in answers), location=best.location,
                      seen_at=best.seen_at, confidence=best.confidence, confirmed=best.confirmed,
                      suggestion=sugg)

    def _spell(self, question: str, dev: str | None) -> tuple[str, list[tuple[str, str]]]:
        """Fix one typing slip in an item name: "scurnchie" -> "scrunchie", "earphnoes" -> "earphones".
        Only words of 5+ letters that are not known words, and only when exactly one known word is
        one slip away (a letter added, missing or wrong, or two letters swapped). Ordinary words that
        merely look similar ("chair" vs "charm") are two slips apart and are left alone."""
        names = self._item_names(dev)
        known = {w for v in names for w in words(v)} | REAL_ITEM_WORDS
        # targets: whole one-word item names only. "house" is only part of "house key",
        # so "mouse" must never be read as "house".
        vocab = {v for v in names if " " not in v and len(v) >= 5}
        fixes = []
        for w in set(words(question)):
            if (len(w) < 5 or w in known or singular(w) in known or w in STOPWORDS
                    or describing_words([w])):
                continue
            close = {singular(v) for v in vocab if abs(len(v) - len(w)) <= 1 and one_slip(w, v)}
            if len(close) == 1:
                fix = next(v for v in vocab if singular(v) in close and one_slip(w, v))
                fixes.append((w, fix))
                question = re.sub(rf"\b{re.escape(w)}\b", fix, question, flags=re.I)
        return question, fixes

    def _ask(self, question: str, now: datetime, dev: str | None = None) -> Answer:
        ko = K.is_korean(question)
        ko_typed = None                               # the item as typed in Korean, e.g. "흰색 물병"
        fixes: list[tuple[str, str]] = []
        if ko:
            saved_ko = self.db.korean_names(dev)
            question_ko = question
            question, unknown_ko, ko_typed = K.to_english(question, saved_ko)
            if unknown_ko:                            # a typo of a known item? "드폰" -> "핸드폰"
                options = K.close_items(unknown_ko, saved_ko)
                if len(options) > 1:                  # "드폰": 핸드폰 or 헤드폰? ask, don't guess
                    ans = Answer("clarify", f"“{unknown_ko}”{'은' if K.has_batchim(unknown_ko) else '는'} "
                                 f"{' / '.join(options)} 중 어떤 물건인가요?", object=unknown_ko)
                    ans.final = True                  # the question is clear enough: no Gemini call
                    return ans
                close = options[0] if options else None
                if close:
                    fixes.append((unknown_ko, close))
                    question, unknown_ko, ko_typed = K.to_english(question_ko.replace(unknown_ko, close), saved_ko)
        else:
            question, fixes = self._spell(question, dev)
        ans = self._answer_rules(question, now, dev, ko, ko_typed, unknown_ko if ko else None)
        if fixes:                                     # say how the question was read
            note = ", ".join(f"“{a}” → “{b}”" for a, b in fixes)
            ans.message = (f"({note}) " if ko else f"(I read {note}.) ") + ans.message
        return ans

    def _answer_rules(self, question: str, now: datetime, dev: str | None, ko: bool,
                      ko_typed: str | None, unknown_ko: str | None) -> Answer:
        if ko:
            if unknown_ko and not self.s.detect_all_objects:
                return Answer("unsupported", f"“{unknown_ko}”{'은' if K.has_batchim(unknown_ko) else '는'} 아직 "
                              f"찾을 수 없어요. 찾을 수 있는 물건: {self._supported_ko()}.")
            if unknown_ko:
                return Answer("not_found",
                              f"카메라 기록에서 {K.josa(ko_typed, '을를')} 본 적이 없어요. 가방이나 서랍, 수납장 안에 "
                              f"있거나, 다른 물건 아래에 있거나, 카메라 화면 밖에 있을 수 있어서 위치를 말할 수 "
                              f"있는 카메라 근거가 부족해요.", object=unknown_ko)
        q = self.parser.parse(question or "")
        if q.status == "empty":
            if ko:
                return Answer("clarify", f"어떤 물건을 찾으세요? 찾을 수 있는 물건: {self._supported_ko()}.")
            return Answer("clarify", f"Which item are you looking for? I can search for: {self._supported()}.")
        if q.status == "unsupported" and not self.s.detect_all_objects:
            if ko:
                return Answer("unsupported", f"“{q.term}”은(는) 아직 찾을 수 없어요. "
                              f"찾을 수 있는 물건: {self._supported_ko()}.")
            return Answer("unsupported",
                          f"I can't search for “{q.term}” yet. Version 1 supports: {self._supported()}.")
        if q.status == "unsupported":
            found, keys, desc, item = self._resolve_other(q.term, dev)
            if found == "none":
                w = self._words(q.term)
                if ko:
                    name = ko_typed or q.term
                    return Answer("not_found",
                                  f"카메라 기록에서 {K.josa(name, '을를')} 본 적이 없어요. 가방이나 서랍, 수납장 안에 "
                                  f"있거나, 다른 물건 아래에 있거나, 카메라 화면 밖에 있을 수 있어서 위치를 말할 수 "
                                  f"있는 카메라 근거가 부족해요.", object=q.term)
                return Answer("not_found",
                              f"I haven't seen {'any ' if w['be'] == 'are' else 'a '}{q.term} in the available camera "
                              f"records. {w['Pron']} may be inside a bag, drawer or cupboard, under something, or "
                              f"outside the camera's view, so there isn't enough camera evidence to say where "
                              f"{w['pron']} {w['be']}.", object=q.term)
            else:
                q.status, q.object = "ok", (keys[0] if len(keys) == 1 else keys)
                q.term = item
                key_words = {singular(x) for k in keys for x in k.split()}
                q.descriptors = [w for w in desc if singular(w) not in key_words]
        if q.status == "ambiguous":
            if ko:
                names = [K.item_ko(c) for c in q.candidates]
                return Answer("clarify", f"어떤 물건을 말씀하시는 건가요? {', '.join(names)} 중에서 골라 주세요.")
            names = [f"your {self._display(c)}" for c in q.candidates]
            options = ", ".join(names[:-1]) + f" or {names[-1]}" if len(names) > 1 else names[0]
            return Answer("clarify", f"Which item do you mean: {options}?")

        key = q.object                       # one name, or several kinds ("water bottle", "glass bottle")
        obj_name = key if isinstance(key, str) else q.term
        w = self._words(obj_name)
        thr = self.s.confirm_threshold
        desc = q.descriptors + self._name_words(question, key, q.descriptors, dev)
        if desc:   # "my black laptop": talk about that one
            w = dict(w, name=" ".join(desc + [w["name"]]))
        many = w["name"] if w["be"] == "are" else w["name"] + "s"
        # Korean name for this question: what the user typed, else the saved Korean name
        kn = ko_typed or " ".join(K.desc_ko(desc) + [K.item_ko(obj_name)])

        def label(r: DetectionRecord) -> str:
            return r.appearance or self._display(r.object)

        def listing(recs: list[DetectionRecord], when: bool = False) -> str:
            parts = [f"the {label(r)} {r.location_label} "
                     + (f"{self._when(r.detected_at, now)} " if when else "") + f"({pct(r.confidence)})" for r in recs]
            return "; ".join(parts[:-1]) + f"; and {parts[-1]}" if len(parts) > 2 else " and ".join(parts)

        def which_hint(recs: list[DetectionRecord]) -> str:
            example = next((r.appearance for r in recs if r.appearance), None)
            if not example:
                return ""
            be = "are" if example.endswith("s") and not example.endswith(("ss", "case")) else "is"
            if ko:
                ex = next((r.appearance_ko for r in recs if r.appearance_ko), None)
                return f" 어느 것이 내 것인가요? 색이나 크기로 물어보세요. 예: “{ex or example} 어디 있어?”"
            return f" Which one is yours? Ask with its colour or size, e.g. “Where {be} my {example}?”"

        # ---- 1. CURRENT view (AC-03) ----
        frame = self.db.latest_frame(dev)
        fresh = frame is not None and (now - frame.captured_at) <= timedelta(seconds=self.current_window(frame))
        if fresh:
            inst = self.db.instances_in_frame(frame.id, key, dev)
            if desc:
                inst = best_matches(inst, desc)
            sure = [r for r in inst if r.confidence >= thr]
            if len(sure) == 1:
                cur = sure[0]
                if ko:
                    name = self._label_ko(cur) if desc else kn
                    return Answer(
                        "current",
                        f"{K.josa(name, '은는')} {self._place_ko(cur)}에 있어요 — 지금 카메라 화면에 보여요 "
                        f"({self._when_ko(cur.detected_at, now)}, 신뢰도 {pct(cur.confidence)}).",
                        object=obj_name, location=cur.location_ko or cur.location_label,
                        seen_at=self._local_iso(cur.detected_at), confidence=round(cur.confidence, 3), confirmed=True,
                    )
                name = label(cur) if desc else w["name"]
                be = ("are" if name.endswith("s") and not name.endswith("ss") else "is") if desc else w["be"]
                return Answer(
                    "current",
                    f"Your {name} {be} {cur.location_label} — visible in the current camera view "
                    f"({self._when(cur.detected_at, now)}, {pct(cur.confidence)} confidence).",
                    object=obj_name, location=cur.location_label, seen_at=self._local_iso(cur.detected_at),
                    confidence=round(cur.confidence, 3), confirmed=True,
                )
            if len(sure) > 1 and ko:
                return Answer(
                    "current",
                    f"지금 카메라 화면에 {kn} {len(sure)}개가 보여요 ({self._when_ko(sure[0].detected_at, now)}): "
                    f"{self._listing_ko(sure, now)}." + which_hint(sure),
                    object=obj_name, location=sure[0].location_ko or sure[0].location_label,
                    seen_at=self._local_iso(sure[0].detected_at), confidence=round(sure[0].confidence, 3), confirmed=True,
                )
            if len(sure) > 1:
                return Answer(
                    "current",
                    f"I can see {len(sure)} {many} in the current camera view "
                    f"({self._when(sure[0].detected_at, now)}): {listing(sure)}." + which_hint(sure),
                    object=obj_name, location=sure[0].location_label, seen_at=self._local_iso(sure[0].detected_at),
                    confidence=round(sure[0].confidence, 3), confirmed=True,
                )

        if fresh:
            prefix = f"Your {w['name']} {w['be']} not visible in the current camera view. "
        elif frame is None:
            prefix = "No camera images have been received yet. "
        else:
            prefix = (f"The camera hasn't sent a recent image (latest {self._when(frame.captured_at, now)}), "
                      f"so I can't check the current view. ")
        if ko:
            if fresh:
                prefix = f"{K.josa(kn, '은는')} 지금 카메라 화면에 보이지 않아요. "
            elif frame is None:
                prefix = "아직 카메라 사진이 들어오지 않았어요. "
            else:
                prefix = (f"카메라가 최근 사진을 보내지 않아서 (마지막 사진: {self._when_ko(frame.captured_at, now)}) "
                          f"지금 화면은 확인할 수 없어요. ")

        # ---- 2. HISTORY (AC-04 / AC-05) ----
        siblings: list[DetectionRecord] = []
        if desc:
            matching = best_matches(self.db.history(key, dev), desc)
            last = next((r for r in matching if r.confidence >= thr), None)
            hint = next((r for r in matching if r.confidence < thr
                         and (last is None or r.detected_at > last.detected_at)), None)
        else:
            last = self.db.last_confirmed(key, thr, dev)
            hint = self.db.latest_unconfirmed(key, thr, after=last.detected_at if last else None, device_id=dev)
            if last:
                siblings = [r for r in self.db.instances_in_frame(last.frame_id, key, dev) if r.confidence >= thr]
        suggestion = (self._possibility_ko(hint, kn, now) if ko else self._possibility(hint, w, now)) if hint else None

        # Different items of this kind seen at different times (white bottle at 4:02,
        # blue bottle at 4:22): give the last place of each one.
        items = [] if desc else self._each_item(key, thr, dev)
        if len(items) > 1 and ko:
            if fresh:
                prefix = f"지금 카메라 화면에 {K.josa(kn, '이가')} 보이지 않아요. "
            msg = (prefix + f"서로 다른 {kn} {len(items)}개를 봤어요. 마지막으로 본 곳: "
                   f"{self._listing_ko(items, now, when=True)}." + which_hint(items))
            return Answer("last_seen", msg, object=obj_name, location=items[0].location_ko or items[0].location_label,
                          seen_at=self._local_iso(items[0].detected_at), confidence=round(items[0].confidence, 3),
                          confirmed=True, suggestion=suggestion)
        if len(items) > 1:
            if fresh:
                prefix = f"No {many} are visible in the current camera view. "
            msg = (prefix + f"I have seen {len(items)} different {many}. Last seen: "
                   f"{listing(items, when=True)}." + which_hint(items))
            return Answer("last_seen", msg, object=obj_name, location=items[0].location_label,
                          seen_at=self._local_iso(items[0].detected_at), confidence=round(items[0].confidence, 3),
                          confirmed=True, suggestion=suggestion)
        if last and len(siblings) > 1 and ko:
            msg = (prefix + f"{self._when_ko(last.detected_at, now)}에 {kn} {len(siblings)}개가 마지막으로 "
                   f"보였어요: {self._listing_ko(siblings, now)}." + which_hint(siblings))
            return Answer("last_seen", msg, object=obj_name, location=last.location_ko or last.location_label,
                          seen_at=self._local_iso(last.detected_at), confidence=round(last.confidence, 3),
                          confirmed=True, suggestion=suggestion)
        if last and len(siblings) > 1:
            msg = (prefix + f"{len(siblings)} {many} were last seen {self._when(last.detected_at, now)}: "
                   f"{listing(siblings)}." + which_hint(siblings))
            return Answer("last_seen", msg, object=obj_name, location=last.location_label,
                          seen_at=self._local_iso(last.detected_at), confidence=round(last.confidence, 3),
                          confirmed=True, suggestion=suggestion)
        if last and ko:
            name = self._label_ko(last) if desc and last.appearance_ko else kn
            subject = "" if fresh and name == kn else K.josa(name, "은는") + " "   # already named in the prefix
            msg = (prefix + f"{subject}{self._when_ko(last.detected_at, now)} "
                   f"{self._place_ko(last)}에서 마지막으로 보였어요 (신뢰도 {pct(last.confidence)}).")
            msg += " " + (suggestion or "지금 그곳에 없다면 옮겨졌거나, 다른 물건에 가려졌거나, 가방이나 서랍처럼 "
                                        "카메라가 볼 수 없는 곳에 있을 수 있어요.")
            return Answer("last_seen", msg, object=obj_name, location=last.location_ko or last.location_label,
                          seen_at=self._local_iso(last.detected_at), confidence=round(last.confidence, 3),
                          confirmed=True, suggestion=suggestion)
        if last:
            seen = f"Your {label(last)} was" if desc and last.appearance and w["be"] == "is" else f"{w['Pron']} {w['was']}"
            msg = (prefix + f"{seen} last seen {last.location_label} "
                   f"{self._when(last.detected_at, now)} ({pct(last.confidence)} confidence).")
            if suggestion:
                msg += " " + suggestion
            else:
                msg += (f" If {w['pron']} {w['isnt']} there now, {w['pron']} may have been moved, covered, "
                        f"or put somewhere the camera can't see, such as a bag or drawer.")
            return Answer("last_seen", msg, object=obj_name, location=last.location_label,
                          seen_at=self._local_iso(last.detected_at), confidence=round(last.confidence, 3),
                          confirmed=True, suggestion=suggestion)

        # ---- 3. CONTEXT only (AC-06) ----
        if hint and ko:
            msg = prefix + ("카메라 기록으로도 위치를 확인하지 못했어요. " if fresh
                            else f"카메라 기록으로는 {kn}의 위치를 확인하지 못했어요. ") + suggestion
            return Answer("possible", msg, object=obj_name, location=hint.location_ko or hint.location_label,
                          seen_at=self._local_iso(hint.detected_at), confidence=round(hint.confidence, 3),
                          confirmed=False, suggestion=suggestion)
        if hint:
            msg = (prefix + f"I couldn't confirm where your {w['name']} {w['be']} from the camera records. "
                   + suggestion)
            return Answer("possible", msg, object=obj_name, location=hint.location_label,
                          seen_at=self._local_iso(hint.detected_at), confidence=round(hint.confidence, 3),
                          confirmed=False, suggestion=suggestion)

        # ---- 4. SAFE FAILURE ----
        if ko:
            found_part = "카메라 기록에서도 찾지 못했어요" if fresh else f"카메라 기록에서 {K.josa(kn, '을를')} 찾지 못했어요"
            msg = (prefix + f"{found_part}. 가방이나 서랍, 수납장 안에 있거나, "
                   f"다른 물건 아래에 있거나, 카메라 화면 밖에 있을 수 있어서 위치를 말할 수 있는 카메라 근거가 "
                   f"부족해요.")
            if desc:
                seen_recs, seen_names = [], set()
                for r in self.db.history(key, dev):
                    if r.confidence >= thr and self._label_ko(r) not in seen_names:
                        seen_names.add(self._label_ko(r))
                        seen_recs.append(r)
                    if len(seen_recs) == 3:
                        break
                if seen_recs:
                    msg += " 제가 본 것: " + self._listing_ko(seen_recs, now, when=True) + "."
            return Answer("not_found", msg, object=obj_name)
        msg = (prefix + f"I couldn't find your {w['name']} in the available camera records. "
               f"{w['Pron']} may be inside a bag, drawer or cupboard, under something, or outside the "
               f"camera's view, so there isn't enough camera evidence to say where {w['pron']} {w['be']}.")
        if desc:   # say which ones of that kind were seen, so the user can pick
            others, seen_names = [], set()
            for r in self.db.history(key, dev):
                if r.confidence >= thr and label(r) not in seen_names:
                    seen_names.add(label(r))
                    others.append(f"the {label(r)} ({r.location_label}, {self._when(r.detected_at, now)})")
                if len(others) == 3:
                    break
            if others:
                msg += " I have seen: " + "; ".join(others) + "."
        return Answer("not_found", msg, object=obj_name)

    @staticmethod
    def _ident(r: DetectionRecord) -> tuple:
        """(name, main colour) — how one item is told apart from another of its kind."""
        colour = next((CANON.get(x, x) for x in reversed(words(r.color or r.appearance))
                       if CANON.get(x, x) in COLOURS - {"dark", "light"}), None)
        return r.object, colour or r.appearance

    def _each_item(self, key, thr: float, dev: str | None, most: int = 4) -> list[DetectionRecord]:
        """The latest confirmed sighting of each different item of this kind, newest first.
        Items are told apart by name and main colour ("white water bottle", "blue glass
        bottle"); sightings with no colour or description are not counted separately."""
        out: dict[tuple, DetectionRecord] = {}
        for r in self.db.history(key, dev):
            if r.confidence < thr:
                continue
            ident = self._ident(r)
            if ident[1] is None or ident in out:
                continue
            out[ident] = r
            if len(out) == most:
                break
        return list(out.values())

    def current_window(self, frame) -> int:
        """How old the latest photo may be and still count as the "current view".
        With a slow camera (e.g. one photo every 15 min) the window grows to match,
        so answers don't wrongly say the camera stopped."""
        base = self.s.current_window_seconds
        if frame is not None and frame.interval_s:
            return max(base, int(frame.interval_s * 1.5) + 30)
        return base

    def _local_iso(self, dt: datetime) -> str:
        return dt.astimezone(self.tz).isoformat(timespec="seconds")

    # ---------- overview for the UI ----------
    def overview(self, now: datetime | None = None, device_id: str | None = None) -> list[dict]:
        now = now or datetime.now(timezone.utc)
        rows = []
        keys = list(self.s.objects)
        if self.s.detect_all_objects:   # plus other items confirmed in the last 7 days
            others = [k for k in self.db.recent_confirmed_objects(self.s.confirm_threshold, now - timedelta(days=7), device_id)
                      if k not in self.s.objects]
            keys += others[:15]
        for key in keys:
            last = self.db.last_confirmed(key, self.s.confirm_threshold, device_id)
            where = last.location_label if last else None
            if last:   # several of the same kind in that photo: list each one
                same = [r for r in self.db.instances_in_frame(last.frame_id, key, device_id)
                        if r.confidence >= self.s.confirm_threshold]
                if len(same) > 1:
                    where = "; ".join(f"{r.appearance or self._display(key)} {r.location_label}" for r in same)
            rows.append({
                "object": key,
                "display": self._display(key),
                "key_item": key in self.s.objects,
                "location": where,
                "seen": self._when(last.detected_at, now) if last else None,
                "seen_at": self._local_iso(last.detected_at) if last else None,
                "confidence": round(last.confidence, 3) if last else None,
            })
        return rows


__all__ = ["Answer", "SearchEngine", "pct", "to_iso"]
