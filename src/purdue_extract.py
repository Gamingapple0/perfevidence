# Vendored unchanged from PurdueDualityLab/EMSE-perf-pr-study@64432e0b6ed7791bbfa929c6c183fc76c75b5d58
# analysis/rq3_pattern_and_validation/ (MIT License, Copyright (c) 2026 The Authors).
# Extraction core only: lines 64-242 of extract_metrics.py (corpus/IO code dropped).
from bisect import bisect_left, bisect_right
import metric_patterns as mp

SNIPPET_CHARS = 70
# ---------------------------------------------------------------------------
# Extraction core
# ---------------------------------------------------------------------------

def _token_starts(text):
    """Character offsets of whitespace-delimited tokens."""
    return [m.start() for m in mp.re.finditer(r"\S+", text)]


def _tok(starts, pos):
    """Token index containing character position ``pos``."""
    return max(bisect_right(starts, pos) - 1, 0)


def _any_within(sorted_idx, center, window):
    """True if any index in ``sorted_idx`` lies within ±window of ``center``."""
    lo = bisect_left(sorted_idx, center - window)
    return lo < len(sorted_idx) and sorted_idx[lo] <= center + window


def _nearest_within(items, item_idx, center, window):
    """Return the item (tok, payload) closest to ``center`` within ±window, else None.

    ``items`` is sorted by token index and ``item_idx`` holds those indices.
    """
    if not items:
        return None
    i = bisect_left(item_idx, center)
    cands = [items[j] for j in (i - 1, i) if 0 <= j < len(items)]
    best = min(cands, key=lambda it: abs(it[0] - center))
    return best if abs(best[0] - center) <= window else None


def _mask_spans(text, spans):
    """Replace matched spans with a filler of equal length (keeps offsets)."""
    if not spans:
        return text
    out, last = [], 0
    for s, e in sorted(spans):
        if s < last:
            continue
        out.append(text[last:s])
        out.append("".join(c if c.isspace() else "█" for c in text[s:e]))
        last = e
    out.append(text[last:])
    return "".join(out)


def _snippet(text, pos):
    s, e = max(0, pos - SNIPPET_CHARS), min(len(text), pos + SNIPPET_CHARS)
    return " ".join(text[s:e].split())


def extract_dimensions(raw_text, *, include_positions=False):
    """
    Return {dim: [match dicts]} for one text. Each match records the cue, the
    quantitative claim it co-occurs with, and a snippet for auditing.
    """
    text = mp.normalize(raw_text)
    if not text.strip():
        return {}
    starts = _token_starts(text)

    # quantitative claims, per kind: sorted [(token index, (kind, matched text))]
    quant_by_kind = {}
    for kind, pat in mp.QUANT_PATTERNS:
        items = sorted((_tok(starts, m.start()), (kind, m.group(0), m.start(), m.end()))
                       for m in pat.finditer(text))
        if items:
            quant_by_kind[kind] = (items, [t for t, _ in items])

    def nearest_quant(center, kinds):
        best = None
        # Resolve equal-distance claims consistently across Python hash seeds.
        for k in sorted(kinds):
            if k not in quant_by_kind:
                continue
            items, idx = quant_by_kind[k]
            q = _nearest_within(items, idx, center, mp.WINDOW_TOKENS)
            if q is not None and (best is None or abs(q[0] - center) < abs(best[0] - center)):
                best = q
        return best

    excl_idx = [_tok(starts, m.start()) for m in mp.EXCLUSION_RE.finditer(text)]
    # a heading such as "## Expected performance improvements" makes the whole
    # following block prospective; exclude its tokens too
    for m in mp.PROSPECTIVE_HEADING_RE.finditer(text):
        end = mp.block_end(text, m.end())
        excl_idx.extend(range(_tok(starts, m.start()), _tok(starts, end - 1) + 1))
    excl_idx = sorted(set(excl_idx))

    # raw cue spans per dimension (unmasked) — used for masking and suppression
    cue_spans = {d: [(m.start(), m.end()) for m in pat.finditer(text)]
                 for d, pat in mp.CUE_PATTERNS.items()}
    cue_tok = {d: sorted(_tok(starts, s) for s, _ in spans) for d, spans in cue_spans.items()}

    # effective cues per dimension: matched on the text with higher-priority
    # phrases masked out ("build time" is not a D1 "time" cue)
    eff_cues = {}
    for dim, pat in mp.CUE_PATTERNS.items():
        t_dim = text
        masked = [sp for other in mp.MASK_BEFORE.get(dim, []) for sp in cue_spans[other]]
        if masked:
            t_dim = _mask_spans(text, masked)
        eff_cues[dim] = [(_tok(starts, m.start()), _tok(starts, m.end() - 1), m.group(0), m.start())
                         for m in pat.finditer(t_dim)]
    eff_cue_tok = {d: sorted(st for st, _, _, _ in cues) for d, cues in eff_cues.items()}

    def span_dist(qt, st, et):
        return 0 if st <= qt <= et else min(abs(qt - st), abs(qt - et))

    def nearer_cue_elsewhere(dim, qt, kind, dist):
        """True if another dimension has a cue strictly closer to the claim at ``qt``."""
        for d2, cues in eff_cues.items():
            if d2 == dim or kind not in mp.QUANT_KINDS[d2]:
                continue
            idx = eff_cue_tok[d2]
            i = bisect_left(idx, qt)
            for j in (i - 1, i):
                if 0 <= j < len(cues):
                    st, et, _, _ = cues[j]
                    if span_dist(qt, st, et) < dist:
                        return True
        return False

    found = {}

    def record(dim, cue, cue_pos, quant_item, rule, rule_id):
        cue_end = cue_pos + len(cue)
        cue = " ".join(cue.split())
        match = {
            "cue": cue if len(cue) <= 60 else cue[:28] + " … " + cue[-28:],
            "quant_kind": quant_item[0], "quant": " ".join(str(quant_item[1]).split())[:60],
            "rule": rule, "snippet": _snippet(text, cue_pos),
        }
        if include_positions:
            match.update(cue_start=cue_pos, cue_end=cue_end,
                         quant_start=quant_item[2], quant_end=quant_item[3], rule_id=rule_id)
        found.setdefault(dim, []).append(match)

    # (a) cue + quantitative claim (of a kind appropriate to the dimension) within window;
    #     the claim is credited to the nearest cue only
    for dim, cues in eff_cues.items():
        suppress = mp.SUPPRESS_IF_NEAR.get(dim, [])
        for st, et, cue, pos in cues:
            if _any_within(excl_idx, st, mp.EXCLUSION_TOKENS):
                continue
            if any(_any_within(cue_tok[s], st, mp.WINDOW_TOKENS) for s in suppress):
                continue
            q = nearest_quant(st, mp.QUANT_KINDS[dim])
            if q is None:
                continue
            qt, (kind, _, _, _) = q
            if mp.NEAREST_CUE_WINS and nearer_cue_elsewhere(dim, qt, kind, span_dist(qt, st, et)):
                continue
            if dim in mp.FALLBACK_DIMS:
                # fallback only when no named dimension is cued in the window and the
                # numerals carry no unit (a unit would itself name the dimension)
                if any(d2 != dim and _any_within(eff_cue_tok[d2], qt, mp.WINDOW_TOKENS) for d2 in eff_cues):
                    continue
                if any(_any_within(quant_by_kind[k][1], qt, 2) for k in mp.UNIT_KINDS if k in quant_by_kind):
                    continue
            record(dim, cue, pos, q[1], "cue+quant", f"CUE_{dim}+QUANT_{kind}")

    # (b) self-sufficient cues
    for dim, rules in mp.SELF_SUFFICIENT.items():
        for rule_index, (pat, required_ctx, suppress_dims) in enumerate(rules):
            for m in pat.finditer(text):
                ct = _tok(starts, m.start())
                if _any_within(excl_idx, ct, mp.EXCLUSION_TOKENS):
                    continue
                if any(_any_within(cue_tok[s], ct, mp.WINDOW_TOKENS) for s in suppress_dims):
                    continue
                if required_ctx is not None and nearest_quant(ct, required_ctx) is None:
                    continue
                record(dim, m.group(0), m.start(), ("self", m.group(0), m.start(), m.end()),
                       "self-sufficient", f"SELF_{dim}[{rule_index}]")

    return found
