"""
Build the question pool JSON from MorphGNT SBLGNT data.

MVP scope: regular noun forms (1st declension -η/-α/-ης, 2nd declension -ος/-ον,
3rd declension -μα type) + regular thematic verbs in present and imperfect
indicative (active and middle/passive). Contract verbs, mi-verbs, εἰμί, and
irregular forms are excluded for MVP.

Output: data/questions.json — array of question objects matching the design
in design.md §4.3.
"""
import json
import re
import unicodedata
from collections import defaultdict
from pysblgnt import morphgnt_rows

BOOK_NAMES = [
    None, "Mt", "Mk", "Lk", "Jn", "Ac", "Ro", "1Co", "2Co", "Ga",
    "Eph", "Php", "Col", "1Th", "2Th", "1Ti", "2Ti", "Tit", "Phm",
    "Heb", "Jas", "1Pe", "2Pe", "1Jn", "2Jn", "3Jn", "Jud", "Re",
]
BOOK_DISPLAY = {
    1:"Matt",2:"Mark",3:"Luke",4:"John",5:"Acts",6:"Rom",7:"1Cor",8:"2Cor",
    9:"Gal",10:"Eph",11:"Phil",12:"Col",13:"1Thess",14:"2Thess",15:"1Tim",
    16:"2Tim",17:"Titus",18:"Phlm",19:"Heb",20:"Jas",21:"1Pet",22:"2Pet",
    23:"1John",24:"2John",25:"3John",26:"Jude",27:"Rev",
}

PARSE_KEYS = ["person", "tense", "voice", "mood", "case", "number", "gender", "degree"]
TENSE = {"P": "present", "I": "imperfect", "F": "future", "A": "aorist", "X": "perfect", "Y": "pluperfect"}
VOICE = {"A": "active", "M": "middle", "P": "passive"}
MOOD = {"I": "indicative", "D": "imperative", "S": "subjunctive", "O": "optative", "N": "infinitive", "P": "participle"}
CASE = {"N": "nominative", "G": "genitive", "D": "dative", "A": "accusative"}
NUMBER = {"S": "singular", "P": "plural"}
GENDER = {"M": "masculine", "F": "feminine", "N": "neuter"}


def strip_accents(s: str) -> str:
    """Remove accents and breathing marks; keep iota subscript folded into base."""
    nfd = unicodedata.normalize("NFD", s)
    out = []
    for ch in nfd:
        cat = unicodedata.category(ch)
        if cat == "Mn":  # combining mark
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out)).lower()


def parse_morph(parse_code: str, pos: str) -> dict:
    """Parse the 8-char CCAT parse code into named fields."""
    result = {}
    for i, key in enumerate(PARSE_KEYS):
        ch = parse_code[i] if i < len(parse_code) else "-"
        if ch == "-":
            continue
        result[key] = ch
    return result


# -------- Paradigm detectors --------

# Contract verb stems (must exclude)
CONTRACT_SUFFIX = ("άω", "έω", "όω", "άομαι", "έομαι", "όομαι")
# Known irregular / suppletive / mi-verbs (must exclude from MVP)
EXCLUDE_LEMMAS = {
    "εἰμί", "φημί", "οἶδα", "ἵστημι", "δίδωμι", "τίθημι", "ἵημι",
    "δείκνυμι", "ἀπόλλυμι", "γίνομαι",  # γίνομαι is irregular middle deponent
    "ἔρχομαι",  # aorist stem ἐλθ-, treat as irregular for prototype
    "λέγω",  # aorist εἶπον — but present is regular; allow for now
    "δέω",  # contract — exclude
    "ζάω",  # contract — exclude
}


def is_regular_thematic_verb(lemma: str) -> bool:
    """Return True if lemma is a regular ω-verb (non-contract, non-mi, non-irregular)."""
    if lemma in EXCLUDE_LEMMAS:
        return False
    if any(lemma.endswith(s) for s in CONTRACT_SUFFIX):
        return False
    # Strip accents to check ending
    bare = strip_accents(lemma)
    # Must end in -ω (active) or -ομαι (middle deponent)
    if not (bare.endswith("ω") or bare.endswith("ομαι")):
        return False
    # μι-verbs end in -μι
    if bare.endswith("μι"):
        return False
    return True


def classify_noun(lemma: str, morph: dict) -> str | None:
    """Return paradigm id, or None if not in MVP scope."""
    bare = strip_accents(lemma)
    gender = morph.get("gender")
    # 2nd declension masculine -ος
    if bare.endswith("ος") and gender == "M":
        return "noun_2nd_masc_os"
    # 2nd declension neuter -ον
    if bare.endswith("ον") and gender == "N":
        return "noun_2nd_neut_on"
    # 1st declension feminine -η
    if bare.endswith("η") and gender == "F":
        return "noun_1st_fem_eta"
    # 1st declension feminine -α (pure: preceded by ε,ι,ρ)
    if bare.endswith("α") and gender == "F":
        if len(bare) >= 2 and bare[-2] in ("ε", "ι", "ρ"):
            return "noun_1st_fem_alpha_pure"
        else:
            return "noun_1st_fem_alpha_mixed"
    # 1st declension masculine -ης
    if bare.endswith("ης") and gender == "M":
        return "noun_1st_masc_es"
    # 3rd declension -μα type neuter
    if bare.endswith("μα") and gender == "N":
        return "noun_3rd_neut_ma"
    return None


MI_VERBS = {"εἰμί", "δίδωμι", "τίθημι", "ἵστημι", "ἵημι"}


def classify_verb(lemma: str, morph: dict) -> str | None:
    """Return paradigm id for verb forms in MVP scope, else None."""
    tense = morph.get("tense")
    voice = morph.get("voice")
    mood = morph.get("mood")

    # εἰμί: special-cased irregular
    if lemma == "εἰμί":
        if mood == "I":
            if tense == "P":
                return "verb_eimi_pres_ind"
            if tense == "I":
                return "verb_eimi_impf_ind"
        return None

    # μι-verbs (主要): present indicative only for MVP
    if lemma in MI_VERBS:
        if mood == "I" and tense == "P":
            if voice == "A":
                return f"verb_mi_{lemma}_pres_act_ind"
            if voice in ("M", "P"):
                return f"verb_mi_{lemma}_pres_mp_ind"
        return None

    if not is_regular_thematic_verb(lemma):
        return None
    if mood != "I":
        return None
    if tense == "P" and voice == "A":
        return "verb_pres_act_ind"
    if tense == "P" and voice in ("M", "P"):
        return "verb_pres_mp_ind"
    if tense == "I" and voice == "A":
        return "verb_impf_act_ind"
    if tense == "I" and voice in ("M", "P"):
        return "verb_impf_mp_ind"
    # New paradigms: aorist & perfect indicative
    if tense == "A" and voice == "A":
        return "verb_aor_act_ind"
    if tense == "A" and voice == "M":
        return "verb_aor_mid_ind"
    if tense == "A" and voice == "P":
        return "verb_aor_pass_ind"
    if tense == "X" and voice == "A":
        return "verb_perf_act_ind"
    if tense == "X" and voice in ("M", "P"):
        return "verb_perf_mp_ind"
    return None


# -------- Decomposition / clues / minimalPairs generation --------

# Paradigm metadata: endings table, stem detection, clues, minimal pairs source
NOUN_PARADIGMS = {
    "noun_2nd_masc_os": {
        "name": "第2変化・男性 -ος",
        "stem_strip": lambda lemma: lemma_stem_2nd_os(lemma),
        "endings": {
            ("singular", "nominative"): "ος",
            ("singular", "genitive"):   "ου",
            ("singular", "dative"):     "ῳ",
            ("singular", "accusative"): "ον",
            ("singular", "vocative"):   "ε",
            ("plural", "nominative"):   "οι",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "οις",
            ("plural", "accusative"):   "ους",
        },
        "ending_role": "第2変化・男性 語尾",
    },
    "noun_2nd_neut_on": {
        "name": "第2変化・中性 -ον",
        "stem_strip": lambda lemma: lemma_stem_2nd_on(lemma),
        "endings": {
            ("singular", "nominative"): "ον",
            ("singular", "genitive"):   "ου",
            ("singular", "dative"):     "ῳ",
            ("singular", "accusative"): "ον",
            ("plural", "nominative"):   "α",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "οις",
            ("plural", "accusative"):   "α",
        },
        "ending_role": "第2変化・中性 語尾",
    },
    "noun_1st_fem_eta": {
        "name": "第1変化・女性 -η",
        "stem_strip": lambda lemma: lemma_stem_1st_eta(lemma),
        "endings": {
            ("singular", "nominative"): "η",
            ("singular", "genitive"):   "ης",
            ("singular", "dative"):     "ῃ",
            ("singular", "accusative"): "ην",
            ("plural", "nominative"):   "αι",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "αις",
            ("plural", "accusative"):   "ας",
        },
        "ending_role": "第1変化・女性 語尾",
    },
    "noun_1st_fem_alpha_pure": {
        "name": "第1変化・女性 -α（純）",
        "stem_strip": lambda lemma: lemma_stem_1st_alpha(lemma),
        "endings": {
            ("singular", "nominative"): "α",
            ("singular", "genitive"):   "ας",
            ("singular", "dative"):     "ᾳ",
            ("singular", "accusative"): "αν",
            ("plural", "nominative"):   "αι",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "αις",
            ("plural", "accusative"):   "ας",
        },
        "ending_role": "第1変化・女性 語尾",
    },
    "noun_1st_fem_alpha_mixed": {
        "name": "第1変化・女性 -α（混）",
        "stem_strip": lambda lemma: lemma_stem_1st_alpha(lemma),
        "endings": {
            ("singular", "nominative"): "α",
            ("singular", "genitive"):   "ης",
            ("singular", "dative"):     "ῃ",
            ("singular", "accusative"): "αν",
            ("plural", "nominative"):   "αι",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "αις",
            ("plural", "accusative"):   "ας",
        },
        "ending_role": "第1変化・女性 語尾",
    },
    "noun_1st_masc_es": {
        "name": "第1変化・男性 -ης",
        "stem_strip": lambda lemma: lemma_stem_1st_es(lemma),
        "endings": {
            ("singular", "nominative"): "ης",
            ("singular", "genitive"):   "ου",
            ("singular", "dative"):     "ῃ",
            ("singular", "accusative"): "ην",
            ("plural", "nominative"):   "αι",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "αις",
            ("plural", "accusative"):   "ας",
        },
        "ending_role": "第1変化・男性 語尾",
    },
    "noun_3rd_neut_ma": {
        "name": "第3変化・中性 -μα",
        "stem_strip": lambda lemma: lemma_stem_3rd_ma(lemma),
        "endings": {
            ("singular", "nominative"): "α",
            ("singular", "genitive"):   "ος",
            ("singular", "dative"):     "ι",
            ("singular", "accusative"): "α",
            ("plural", "nominative"):   "α",
            ("plural", "genitive"):     "ων",
            ("plural", "dative"):       "σι",
            ("plural", "accusative"):   "α",
        },
        "ending_role": "第3変化・中性 語尾（語幹 -ματ-）",
    },
}


def _strip_suffix(lemma, suffix_bare):
    """Strip a suffix from the lemma, accent-insensitively.
    e.g. _strip_suffix('Χριστός', 'ος') == 'Χριστ'"""
    bare = strip_accents(lemma)
    if bare.endswith(suffix_bare):
        return lemma[:-len(suffix_bare)]
    return lemma


def lemma_stem_2nd_os(lemma):
    return _strip_suffix(lemma, "ος")

def lemma_stem_2nd_on(lemma):
    return _strip_suffix(lemma, "ον")

def lemma_stem_1st_eta(lemma):
    return _strip_suffix(lemma, "η")

def lemma_stem_1st_alpha(lemma):
    return _strip_suffix(lemma, "α")

def lemma_stem_1st_es(lemma):
    return _strip_suffix(lemma, "ης")

def lemma_stem_3rd_ma(lemma):
    # ὄνομα → ὀνοματ (stem includes the τ that appears in oblique cases)
    bare = strip_accents(lemma)
    if bare.endswith("α"):
        return lemma[:-1] + "ατ"
    return lemma


# Verb paradigm endings (no augment for present, augment for imperfect)
VERB_PARADIGMS = {
    "verb_pres_act_ind": {
        "name": "現在・能動・直説法",
        "augment": False,
        "endings": {
            ("1", "singular"): "ω",
            ("2", "singular"): "εις",
            ("3", "singular"): "ει",
            ("1", "plural"):   "ομεν",
            ("2", "plural"):   "ετε",
            ("3", "plural"):   "ουσι",  # also -ουσιν (movable nu)
        },
        "ending_role": "能動一次語尾（結合母音含む）",
    },
    "verb_pres_mp_ind": {
        "name": "現在・中受・直説法",
        "augment": False,
        "endings": {
            ("1", "singular"): "ομαι",
            ("2", "singular"): "ῃ",  # also -ει
            ("3", "singular"): "εται",
            ("1", "plural"):   "ομεθα",
            ("2", "plural"):   "εσθε",
            ("3", "plural"):   "ονται",
        },
        "ending_role": "中受一次語尾（結合母音含む）",
    },
    "verb_impf_act_ind": {
        "name": "未完了・能動・直説法",
        "augment": True,
        "endings": {
            ("1", "singular"): "ον",
            ("2", "singular"): "ες",
            ("3", "singular"): "ε",  # also -εν
            ("1", "plural"):   "ομεν",
            ("2", "plural"):   "ετε",
            ("3", "plural"):   "ον",
        },
        "ending_role": "能動二次語尾（結合母音含む）",
    },
    "verb_impf_mp_ind": {
        "name": "未完了・中受・直説法",
        "augment": True,
        "endings": {
            ("1", "singular"): "ομην",
            ("2", "singular"): "ου",
            ("3", "singular"): "ετο",
            ("1", "plural"):   "ομεθα",
            ("2", "plural"):   "εσθε",
            ("3", "plural"):   "οντο",
        },
        "ending_role": "中受二次語尾（結合母音含む）",
    },
    # ===== New: Aorist series =====
    "verb_aor_act_ind": {
        "name": "アオリスト・能動・直説法",
        "augment": True,
        "tense_marker_bare": "σ",
        "marker_label": "時制標識 σα",
        "endings": {
            ("1", "singular"): "α",
            ("2", "singular"): "ας",
            ("3", "singular"): "ε",     # also -εν (movable nu)
            ("1", "plural"):   "αμεν",
            ("2", "plural"):   "ατε",
            ("3", "plural"):   "αν",
        },
        "ending_role": "アオリスト能動語尾",
    },
    "verb_aor_mid_ind": {
        "name": "アオリスト・中動・直説法",
        "augment": True,
        "tense_marker_bare": "σ",
        "marker_label": "時制標識 σα",
        "endings": {
            ("1", "singular"): "αμην",
            ("2", "singular"): "ω",     # ασο → ω 縮約
            ("3", "singular"): "ατο",
            ("1", "plural"):   "αμεθα",
            ("2", "plural"):   "ασθε",
            ("3", "plural"):   "αντο",
        },
        "ending_role": "アオリスト中動語尾",
    },
    "verb_aor_pass_ind": {
        "name": "アオリスト・受動・直説法",
        "augment": True,
        "tense_marker_bare": "θη",
        "marker_label": "受動標識 θη",
        "endings": {
            ("1", "singular"): "ν",
            ("2", "singular"): "ς",
            ("3", "singular"): "",       # zero ending
            ("1", "plural"):   "μεν",
            ("2", "plural"):   "τε",
            ("3", "plural"):   "σαν",
        },
        "ending_role": "受動アオリスト語尾（二次能動）",
    },
    # ===== New: Perfect series =====
    "verb_perf_act_ind": {
        "name": "完了・能動・直説法",
        "reduplication": True,
        "tense_marker_bare": "κ",
        "marker_label": "完了標識 κ",
        "endings": {
            ("1", "singular"): "α",
            ("2", "singular"): "ας",
            ("3", "singular"): "ε",      # also -εν
            ("1", "plural"):   "αμεν",
            ("2", "plural"):   "ατε",
            ("3", "plural"):   "ασι",    # also -ασιν
        },
        "ending_role": "完了能動語尾",
    },
    "verb_perf_mp_ind": {
        "name": "完了・中受・直説法",
        "reduplication": True,
        "endings": {
            ("1", "singular"): "μαι",
            ("2", "singular"): "σαι",
            ("3", "singular"): "ται",
            ("1", "plural"):   "μεθα",
            ("2", "plural"):   "σθε",
            ("3", "plural"):   "νται",
        },
        "ending_role": "完了中受語尾（一次・結合母音なし）",
    },
    # ===== New: εἰμί (irregular) =====
    "verb_eimi_pres_ind": {
        "name": "εἰμί 現在・直説法",
        "is_eimi": True,
    },
    "verb_eimi_impf_ind": {
        "name": "εἰμί 未完了・直説法",
        "is_eimi": True,
    },
    # ===== New: μι verbs (present indicative only for MVP) =====
    "verb_mi_δίδωμι_pres_act_ind": {
        "name": "δίδωμι 現在・能動・直説法",
        "is_mi": True,
        "stem_display": "διδο-",
    },
    "verb_mi_δίδωμι_pres_mp_ind": {
        "name": "δίδωμι 現在・中受・直説法",
        "is_mi": True,
        "stem_display": "διδο-",
    },
    "verb_mi_τίθημι_pres_act_ind": {
        "name": "τίθημι 現在・能動・直説法",
        "is_mi": True,
        "stem_display": "τιθε-",
    },
    "verb_mi_τίθημι_pres_mp_ind": {
        "name": "τίθημι 現在・中受・直説法",
        "is_mi": True,
        "stem_display": "τιθε-",
    },
    "verb_mi_ἵστημι_pres_act_ind": {
        "name": "ἵστημι 現在・能動・直説法",
        "is_mi": True,
        "stem_display": "ἱστα-",
    },
    "verb_mi_ἵστημι_pres_mp_ind": {
        "name": "ἵστημι 現在・中受・直説法",
        "is_mi": True,
        "stem_display": "ἱστα-",
    },
    "verb_mi_ἵημι_pres_act_ind": {
        "name": "ἵημι 現在・能動・直説法",
        "is_mi": True,
        "stem_display": "ἱε-",
    },
    "verb_mi_ἵημι_pres_mp_ind": {
        "name": "ἵημι 現在・中受・直説法",
        "is_mi": True,
        "stem_display": "ἱε-",
    },
}


def verb_stem(lemma: str) -> str:
    """Strip -ω or -ομαι from lemma to get the present stem (accent-insensitive)."""
    bare = strip_accents(lemma)
    if bare.endswith("ομαι"):
        return lemma[:-4]
    if bare.endswith("ω"):
        return lemma[:-1]
    return lemma


# -------- Question builder --------

def build_noun_question(row, paradigm_id):
    """Build a noun question record."""
    pdef = NOUN_PARADIGMS[paradigm_id]
    morph = parse_morph(row["ccat-parse"], row["ccat-pos"])
    case = CASE.get(morph.get("case"))
    number = NUMBER.get(morph.get("number"))
    gender = GENDER.get(morph.get("gender"))
    if not case or not number:
        return None
    form = row["norm"]
    lemma = row["lemma"]
    bare_form = strip_accents(form)
    stem_unaccented = strip_accents(pdef["stem_strip"](lemma))
    # Find expected ending
    expected_ending = pdef["endings"].get((number, case))
    if not expected_ending:
        return None
    # Decompose: stem + ending (use the actual form, attempt to split)
    decomposition = decompose_noun(form, stem_unaccented, expected_ending, pdef)
    clues = build_noun_clues(form, paradigm_id, case, number, gender, expected_ending)
    minimal_pairs = build_noun_minimal_pairs(lemma, paradigm_id, case, number)
    return {
        "id": f"{paradigm_id}_{lemma}_{number[:2]}_{case[:3]}_{row['bcv']}",
        "type": "noun",
        "form": form,
        "lemma": lemma,
        "morph": {
            "gender": gender,
            "number": number,
            "case": case,
            "declension": paradigm_id,
        },
        "paradigm": paradigm_id,
        "paradigmName": pdef["name"],
        "decomposition": decomposition,
        "clues": clues,
        "minimalPairs": minimal_pairs,
        "bcv": row["bcv"],
        "ref": bcv_display(row["bcv"]),
    }


def decompose_noun(form, stem_bare, ending_bare, pdef):
    """Split surface form into stem + ending using ending length heuristic."""
    # Try to find the ending at the end of the form (accent-insensitive)
    form_bare = strip_accents(form)
    # Find the ending by suffix length
    end_len = len(ending_bare)
    if end_len == 0 or len(form) < end_len:
        return [{"segment": form, "role": "stem", "label": "語幹"}]
    surface_stem = form[:-end_len]
    surface_ending = form[-end_len:]
    return [
        {"segment": surface_stem, "role": "stem", "label": "語幹"},
        {"segment": surface_ending, "role": "ending", "label": pdef["ending_role"]},
    ]


def build_noun_clues(form, paradigm_id, case, number, gender, expected_ending):
    """Return a list of clue strings for a noun form."""
    clues = []
    bare = strip_accents(form)
    if paradigm_id == "noun_2nd_masc_os":
        if case == "dative" and number == "singular":
            clues.append("末尾 -ῳ（イオタ下書き）→ 第2変化単数与格の決定的サイン")
            clues.append("第1変化（-α/η 系）なら ᾳ になる")
        elif case == "genitive" and number == "singular":
            clues.append("末尾 -ου → 第2変化（または第1変化男性 -ης 型）単数属格")
            clues.append("複数与格 -οις と勘違いしないこと")
        elif case == "accusative" and number == "singular":
            clues.append("末尾 -ον → 第2変化単数対格（中性主格と同形になることに注意）")
        elif case == "nominative" and number == "singular":
            clues.append("末尾 -ος → 第2変化単数主格（属格 -ου を確認すれば 3変化と区別可）")
        elif case == "nominative" and number == "plural":
            clues.append("末尾 -οι → 第2変化複数主格（与格 -οις と取り違えやすい）")
        elif case == "accusative" and number == "plural":
            clues.append("末尾 -ους → 第2変化複数対格（与格 -οις との混同に注意）")
        elif case == "dative" and number == "plural":
            clues.append("末尾 -οις → 第2変化複数与格（主格 -οι、対格 -ους との対比を確認）")
        elif case == "genitive" and number == "plural":
            clues.append("末尾 -ων → 複数属格（変化型を問わず共通サイン）")
        elif case == "vocative" and number == "singular":
            clues.append("末尾 -ε → 第2変化単数呼格（主格 -ος とは違う）")
    elif paradigm_id == "noun_2nd_neut_on":
        if case in ("nominative", "accusative") and number == "singular":
            clues.append("中性は主格＝対格。-ον 終止で第2変化中性単数")
            clues.append("男性 -ος と混同しないこと（中性は -ον）")
        elif case in ("nominative", "accusative") and number == "plural":
            clues.append("末尾 -α → 中性複数主格＝対格（3変化中性とも形が似るので語幹で見分ける）")
        elif case == "dative" and number == "singular":
            clues.append("末尾 -ῳ → 第2変化単数与格")
        elif case == "genitive" and number == "singular":
            clues.append("末尾 -ου → 第2変化単数属格")
        elif case == "dative" and number == "plural":
            clues.append("末尾 -οις → 第2変化複数与格")
        elif case == "genitive" and number == "plural":
            clues.append("末尾 -ων → 複数属格（共通）")
    elif paradigm_id in ("noun_1st_fem_eta", "noun_1st_fem_alpha_pure", "noun_1st_fem_alpha_mixed"):
        if case == "dative" and number == "singular":
            clues.append(f"末尾 -{expected_ending}（イオタ下書き）→ 第1変化単数与格")
            clues.append("第2変化なら -ῳ になる")
        elif case == "genitive" and number == "singular":
            clues.append(f"末尾 -{expected_ending} → 第1変化単数属格")
        elif case == "accusative" and number == "singular":
            clues.append(f"末尾 -{expected_ending} → 第1変化単数対格")
        elif case == "nominative" and number == "singular":
            clues.append(f"末尾 -{expected_ending} → 第1変化女性単数主格")
        elif case == "nominative" and number == "plural":
            clues.append("末尾 -αι → 第1変化複数主格（第2変化 -οι と対比）")
        elif case == "accusative" and number == "plural":
            clues.append("末尾 -ας → 第1変化複数対格")
        elif case == "dative" and number == "plural":
            clues.append("末尾 -αις → 第1変化複数与格")
        elif case == "genitive" and number == "plural":
            clues.append("末尾 -ων → 複数属格（共通）")
    elif paradigm_id == "noun_1st_masc_es":
        if case == "nominative" and number == "singular":
            clues.append("末尾 -ης → 第1変化男性単数主格（属格 -ου で確認）")
        elif case == "genitive" and number == "singular":
            clues.append("末尾 -ου → 第1変化男性単数属格（第2変化単数属格と同形なので主格で見分ける）")
        elif case == "dative" and number == "singular":
            clues.append("末尾 -ῃ → 第1変化単数与格")
        elif case == "accusative" and number == "singular":
            clues.append("末尾 -ην → 第1変化単数対格")
        elif case == "vocative" and number == "singular":
            clues.append("末尾 -α → 第1変化男性単数呼格（主格 -ης と異なる）")
    elif paradigm_id == "noun_3rd_neut_ma":
        if case in ("nominative", "accusative") and number == "singular":
            clues.append("末尾 -μα → 第3変化中性単数（主格＝対格）。語幹は -ματ-")
        elif case == "genitive" and number == "singular":
            clues.append("末尾 -ματος → 第3変化中性単数属格（語幹 -ματ- ＋ -ος）")
        elif case == "dative" and number == "singular":
            clues.append("末尾 -ματι → 第3変化中性単数与格（語幹 -ματ- ＋ -ι）")
        elif case in ("nominative", "accusative") and number == "plural":
            clues.append("末尾 -ματα → 第3変化中性複数主格＝対格（語幹 -ματ- ＋ -α）")
        elif case == "dative" and number == "plural":
            clues.append("末尾 -μασι(ν) → 第3変化中性複数与格（語幹 τ が σ の前で脱落）")
        elif case == "genitive" and number == "plural":
            clues.append("末尾 -ματων → 第3変化中性複数属格（語幹 -ματ- ＋ -ων）")
    if not clues:
        clues.append(f"{case} {number}：{NOUN_PARADIGMS[paradigm_id]['name']} の語尾は -{expected_ending}")
    return clues


NOUN_NUM_ABBR = {"singular": "Sg", "plural": "Pl"}
NOUN_CASE_ABBR = {"nominative": "Nom", "genitive": "Gen", "dative": "Dat", "accusative": "Acc", "vocative": "Voc"}


def build_noun_minimal_pairs(lemma, paradigm_id, this_case, this_number):
    """Generate minimal-pair forms by appending each ending to lemma stem."""
    pdef = NOUN_PARADIGMS[paradigm_id]
    stem = pdef["stem_strip"](lemma)
    pairs = []
    # Choose 3 most-confusable cells (heuristic: same number, then other cases)
    candidates = []
    for (num, cas), end in pdef["endings"].items():
        if (num, cas) == (this_number, this_case):
            continue
        candidates.append((num, cas, end))
    # prioritize same-number first
    candidates.sort(key=lambda x: (x[0] != this_number, x[1]))
    for num, cas, end in candidates[:3]:
        approx_form = stem + end
        pairs.append({
            "form": approx_form,
            "gloss": f"{NOUN_NUM_ABBR[num]} {NOUN_CASE_ABBR[cas]}",
        })
    return pairs


def build_verb_question(row, paradigm_id):
    pdef = VERB_PARADIGMS[paradigm_id]
    morph = parse_morph(row["ccat-parse"], row["ccat-pos"])
    person = morph.get("person")
    number = NUMBER.get(morph.get("number"))
    if not person or not number:
        return None
    form = row["norm"]
    lemma = row["lemma"]

    if pdef.get("is_eimi") or pdef.get("is_mi"):
        expected_ending = ""
    else:
        expected_ending = pdef["endings"].get((person, number))
        if expected_ending is None:
            return None

    decomposition = decompose_verb(form, lemma, paradigm_id, expected_ending)
    clues = build_verb_clues(form, paradigm_id, person, number, expected_ending)
    minimal_pairs = build_verb_minimal_pairs(lemma, paradigm_id, person, number)
    return {
        "id": f"{paradigm_id}_{lemma}_{person}{number[:1]}_{row['bcv']}",
        "type": "verb",
        "form": form,
        "lemma": lemma,
        "morph": {
            "tense": TENSE[morph.get("tense", "P")],
            "voice": VOICE[morph.get("voice", "A")],
            "mood": MOOD[morph.get("mood", "I")],
            "person": person,
            "number": number,
        },
        "paradigm": paradigm_id,
        "paradigmName": pdef["name"],
        "decomposition": decomposition,
        "clues": clues,
        "minimalPairs": minimal_pairs,
        "bcv": row["bcv"],
        "ref": bcv_display(row["bcv"]),
    }


def decompose_verb(form, lemma, paradigm_id, expected_ending):
    """Decompose verb form into [aug/redup] + stem + [tense_marker] + ending."""
    pdef = VERB_PARADIGMS[paradigm_id]

    # εἰμί / μι 動詞: 不規則。語形をそのまま見せる（impf εἰμί だけ augment を分離）
    if pdef.get("is_eimi") or pdef.get("is_mi"):
        first_bare = strip_accents(form[:1])
        if pdef.get("is_eimi") and "impf" in paradigm_id and first_bare in ("η", "ω"):
            return [
                {"segment": form[:1], "role": "augment", "label": "augment（母音延長）"},
                {"segment": form[1:], "role": "stem", "label": pdef["name"]},
            ]
        return [{"segment": form, "role": "stem", "label": pdef["name"]}]

    # Strip movable nu notation "(ν)" before processing; we'll reattach to ending
    movable_nu = ""
    work_form = form
    if work_form.endswith("(ν)"):
        movable_nu = "(ν)"
        work_form = work_form[:-3]

    surface = work_form
    end_len = len(expected_ending)
    if end_len > 0 and len(surface) >= end_len:
        ending_part = surface[-end_len:]
        stem_zone = surface[:-end_len]
    else:
        ending_part = ""
        stem_zone = surface

    segments = []
    has_aug = pdef.get("augment", False)
    has_redup = pdef.get("reduplication", False)

    # 1. Augment / reduplication
    if has_aug and stem_zone:
        first_bare = strip_accents(stem_zone[:1])
        if first_bare in ("ε", "η", "ω"):
            segments.append({"segment": stem_zone[0], "role": "augment", "label": "augment"})
            stem_zone = stem_zone[1:]
    elif has_redup and stem_zone:
        if len(stem_zone) >= 2:
            first_two_bare = strip_accents(stem_zone[:2])
            # consonant + ε reduplication (λε-, γε-, τε- など)
            if len(first_two_bare) >= 2 and first_two_bare[1] == "ε" and first_two_bare[0] not in "αεηιοωυ":
                segments.append({"segment": stem_zone[:2], "role": "reduplication", "label": "reduplication"})
                stem_zone = stem_zone[2:]
            elif first_two_bare[0] in ("ε", "η"):
                # vowel-initial: lengthening-style reduplication
                segments.append({"segment": stem_zone[:1], "role": "reduplication", "label": "reduplication"})
                stem_zone = stem_zone[1:]

    # 2. Tense marker (σ, θη, κ)
    tense_marker_bare = pdef.get("tense_marker_bare", "")
    if tense_marker_bare and stem_zone:
        bare_stem_zone = strip_accents(stem_zone)
        if bare_stem_zone.endswith(tense_marker_bare):
            marker_len = len(tense_marker_bare)
            stem_segment = stem_zone[:-marker_len]
            marker_segment = stem_zone[-marker_len:]
            if stem_segment:
                segments.append({"segment": stem_segment, "role": "stem", "label": "語幹"})
            segments.append({"segment": marker_segment, "role": "tense_marker", "label": pdef.get("marker_label", "時制標識")})
        else:
            # Marker absorbed (liquid stem, 2nd aorist, 2nd aor passive, etc.)
            if stem_zone:
                segments.append({"segment": stem_zone, "role": "stem", "label": "語幹"})
    else:
        if stem_zone:
            segments.append({"segment": stem_zone, "role": "stem", "label": "語幹"})

    # 3. Ending (with movable nu reattached)
    if ending_part or movable_nu:
        segments.append({"segment": (ending_part + movable_nu), "role": "ending", "label": pdef.get("ending_role", "語尾")})

    return segments


def build_verb_clues(form, paradigm_id, person, number, expected_ending):
    clues = []
    pdef = VERB_PARADIGMS[paradigm_id]

    # εἰμί
    if pdef.get("is_eimi"):
        if "pres" in paradigm_id:
            clues.append("εἰμί「ある／いる」は完全に不規則。古い印欧語の活用を保持する基本動詞")
            person_clue = {
                ("1", "singular"): "εἰμί → 辞書形そのもの（1人称単数）",
                ("2", "singular"): "εἶ → 2人称単数（短形）",
                ("3", "singular"): "ἐστί(ν) → 3人称単数（無アクセントの enclitic 形 ἐστιν も多用）",
                ("1", "plural"):   "ἐσμέν → 1人称複数",
                ("2", "plural"):   "ἐστέ → 2人称複数",
                ("3", "plural"):   "εἰσί(ν) → 3人称複数",
            }.get((person, number))
            if person_clue: clues.append(person_clue)
        else:
            clues.append("εἰμί の未完了：augment 母音延長（ἤ-, ἦ-）が決定的サイン")
            person_clue = {
                ("1", "singular"): "ἤμην → 1人称単数",
                ("2", "singular"): "ἦς（または ἦσθα）→ 2人称単数",
                ("3", "singular"): "ἦν → 3人称単数（不規則）",
                ("1", "plural"):   "ἦμεν（または ἤμεθα）→ 1人称複数",
                ("2", "plural"):   "ἦτε → 2人称複数",
                ("3", "plural"):   "ἦσαν → 3人称複数",
            }.get((person, number))
            if person_clue: clues.append(person_clue)
        clues.append("εἰμί はいかなる時制でも λύω 型とは無関係。例外として丸ごと覚える")
        return clues

    # μι 動詞
    if pdef.get("is_mi"):
        stem_display = pdef.get("stem_display", "")
        clues.append(f"μι 動詞は結合母音を持たず、直接語尾を付ける athematic 型")
        clues.append(f"現在語幹に reduplication（δι-/τι-/ἱ-）が固着")
        if stem_display:
            clues.append(f"語幹（弱・強の交替）：{stem_display}（長母音は単数能動、短母音は複数・中受）")
        return clues

    has_aug = pdef.get("augment", False)
    has_redup = pdef.get("reduplication", False)

    if has_aug:
        clues.append("語頭の ἐ-（または η-/ω-）が augment → 過去系列")
        if paradigm_id == "verb_impf_act_ind":
            clues.append("能動二次語尾の組合せ → 未完了能動")
        elif paradigm_id == "verb_impf_mp_ind":
            clues.append("中受二次語尾の組合せ → 未完了中受")
        elif paradigm_id == "verb_aor_act_ind":
            clues.append("σα（または音便結果 ξα / ψα）が見える → 第1アオリスト能動")
            clues.append("第2アオリストは σ を取らず語幹自体が変わる（λαμβάνω → ἔλαβον など）")
        elif paradigm_id == "verb_aor_mid_ind":
            clues.append("σα + 中動二次語尾 → 第1アオリスト中動")
        elif paradigm_id == "verb_aor_pass_ind":
            clues.append("θη（または -η- のみの第2アオリスト受動）→ アオリスト受動")
            clues.append("3Sg は無語尾、3Pl は -σαν（μι 動詞型の二次語尾）")
    elif has_redup:
        clues.append("語頭の reduplication（子音 + ε または ε-）→ 完了系列")
        if paradigm_id == "verb_perf_act_ind":
            clues.append("κ が見える → 完了能動（一部の動詞は κ なしの第2完了：γέγραφα など）")
        elif paradigm_id == "verb_perf_mp_ind":
            clues.append("κ が無く、結合母音もなく直接中受語尾 → 完了中受")
            clues.append("子音語幹では音便変化が頻発（γέγραμμαι, πέπεισμαι 等）")
    else:
        clues.append("augment が無い → 現在系（未完了 or アオリストではない）")
        if paradigm_id == "verb_pres_act_ind":
            clues.append("能動一次語尾の組合せ → 現在能動")
        elif paradigm_id == "verb_pres_mp_ind":
            clues.append("中受一次語尾の組合せ → 現在中受")
    # Person/number-specific clue
    person_label = {"1": "1人称", "2": "2人称", "3": "3人称"}[person]
    num_label = {"singular": "単数", "plural": "複数"}[number]
    if paradigm_id == "verb_pres_act_ind":
        person_clue = {
            ("1", "singular"): "-ω → 1人称単数（thematic 動詞の辞書形と同形）",
            ("2", "singular"): "-εις → 2人称単数（結合母音 ε ＋ -ις）",
            ("3", "singular"): "-ει → 3人称単数",
            ("1", "plural"):   "-ομεν → 1人称複数（つねに -μεν は 1pl）",
            ("2", "plural"):   "-ετε → 2人称複数",
            ("3", "plural"):   "-ουσι(ν) → 3人称複数（ν 移動）",
        }.get((person, number))
        if person_clue:
            clues.append(person_clue)
    elif paradigm_id == "verb_pres_mp_ind":
        person_clue = {
            ("1", "singular"): "-ομαι → 1人称単数（中受一次）",
            ("2", "singular"): "-ῃ または -ει → 2人称単数（-εσαι から σ脱落・縮約）",
            ("3", "singular"): "-εται → 3人称単数",
            ("1", "plural"):   "-ομεθα → 1人称複数",
            ("2", "plural"):   "-εσθε → 2人称複数",
            ("3", "plural"):   "-ονται → 3人称複数",
        }.get((person, number))
        if person_clue:
            clues.append(person_clue)
    elif paradigm_id == "verb_impf_act_ind":
        person_clue = {
            ("1", "singular"): "-ον → 1人称単数（3pl と同形なので主語で区別）",
            ("2", "singular"): "-ες → 2人称単数",
            ("3", "singular"): "-ε(ν) → 3人称単数",
            ("1", "plural"):   "-ομεν → 1人称複数（現在と同形、augment で時制を判別）",
            ("2", "plural"):   "-ετε → 2人称複数（現在と同形、augment で時制を判別）",
            ("3", "plural"):   "-ον → 3人称複数（1sg と同形）",
        }.get((person, number))
        if person_clue:
            clues.append(person_clue)
    elif paradigm_id == "verb_impf_mp_ind":
        person_clue = {
            ("1", "singular"): "-ομην → 1人称単数（中受二次）",
            ("2", "singular"): "-ου → 2人称単数（-εσο の σ脱落・縮約）",
            ("3", "singular"): "-ετο → 3人称単数",
            ("1", "plural"):   "-ομεθα → 1人称複数（現在と同形、augment で時制判別）",
            ("2", "plural"):   "-εσθε → 2人称複数（現在と同形、augment で時制判別）",
            ("3", "plural"):   "-οντο → 3人称複数",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    elif paradigm_id == "verb_aor_act_ind":
        person_clue = {
            ("1", "singular"): "-α → 1人称単数（-ν ではない点が現在・未完了との大きな違い）",
            ("2", "singular"): "-ας → 2人称単数",
            ("3", "singular"): "-ε(ν) → 3人称単数（α が ε に交替）",
            ("1", "plural"):   "-αμεν → 1人称複数",
            ("2", "plural"):   "-ατε → 2人称複数",
            ("3", "plural"):   "-αν → 3人称複数（σαν 型もあり）",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    elif paradigm_id == "verb_aor_mid_ind":
        person_clue = {
            ("1", "singular"): "-σαμην → 1人称単数（σα + μην）",
            ("2", "singular"): "-σω → 2人称単数（-σασο の σ脱落・縮約）",
            ("3", "singular"): "-σατο → 3人称単数",
            ("1", "plural"):   "-σαμεθα → 1人称複数",
            ("2", "plural"):   "-σασθε → 2人称複数",
            ("3", "plural"):   "-σαντο → 3人称複数",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    elif paradigm_id == "verb_aor_pass_ind":
        person_clue = {
            ("1", "singular"): "θη + ν → 1人称単数（-θην）",
            ("2", "singular"): "θη + ς → 2人称単数（-θης）",
            ("3", "singular"): "θη のみ（無語尾）→ 3人称単数",
            ("1", "plural"):   "θη + μεν → 1人称複数（-θημεν）",
            ("2", "plural"):   "θη + τε → 2人称複数（-θητε）",
            ("3", "plural"):   "θη + σαν → 3人称複数（-θησαν）",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    elif paradigm_id == "verb_perf_act_ind":
        person_clue = {
            ("1", "singular"): "-κα → 1人称単数（reduplication + κα が完了能動の核）",
            ("2", "singular"): "-κας → 2人称単数",
            ("3", "singular"): "-κε(ν) → 3人称単数（α → ε 交替）",
            ("1", "plural"):   "-καμεν → 1人称複数",
            ("2", "plural"):   "-κατε → 2人称複数",
            ("3", "plural"):   "-κασι(ν) → 3人称複数",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    elif paradigm_id == "verb_perf_mp_ind":
        person_clue = {
            ("1", "singular"): "-μαι → 1人称単数（結合母音なし、語幹に直結）",
            ("2", "singular"): "-σαι → 2人称単数（縮約なしの古形）",
            ("3", "singular"): "-ται → 3人称単数",
            ("1", "plural"):   "-μεθα → 1人称複数",
            ("2", "plural"):   "-σθε → 2人称複数",
            ("3", "plural"):   "-νται → 3人称複数",
        }.get((person, number))
        if person_clue: clues.append(person_clue)
    return clues


PERSON_ABBR = {"1": "1st", "2": "2nd", "3": "3rd"}
VERB_NUM_ABBR = {"singular": "Sg", "plural": "Pl"}


def build_verb_minimal_pairs(lemma, paradigm_id, this_person, this_number):
    pdef = VERB_PARADIGMS[paradigm_id]
    # εἰμί / μι 動詞は不規則。minimal pair は省略（同じパラダイム内で語幹生成しても誤った形になる）
    if pdef.get("is_eimi") or pdef.get("is_mi") or not pdef.get("endings"):
        return []
    stem = verb_stem(lemma)
    pairs = []
    # Same-paradigm other cells, prefer same number first
    candidates = []
    for (person, number), end in pdef["endings"].items():
        if (person, number) == (this_person, this_number):
            continue
        candidates.append((person, number, end))
    candidates.sort(key=lambda x: (x[1] != this_number, x[0]))
    augment = "ἐ" if pdef.get("augment") else ""
    for person, number, end in candidates[:3]:
        approx = augment + stem + end
        pairs.append({
            "form": approx,
            "gloss": f"{PERSON_ABBR[person]} {VERB_NUM_ABBR[number]}",
        })
    return pairs


def bcv_display(bcv):
    """020101 → 'Mark 1:1' (book is already 1-indexed in BCV)"""
    book = int(bcv[:2])
    ch = int(bcv[2:4])
    vs = int(bcv[4:6])
    return f"{BOOK_DISPLAY.get(book, '?')} {ch}:{vs}"


# -------- Main extraction --------

PER_CELL_CAP = 30  # max attestations per (paradigm, cell) — keeps dataset compact


def cell_key_noun(q):
    return (q["paradigm"], q["morph"]["number"], q["morph"]["case"])


def cell_key_verb(q):
    return (q["paradigm"], q["morph"]["person"], q["morph"]["number"])


def main():
    raw = []
    skipped = defaultdict(int)
    # First pass: group all rows by bcv to assemble verse contexts
    verse_tokens = defaultdict(list)  # bcv → list of {word, idx}
    for book in range(1, 28):
        for row in morphgnt_rows(book):
            verse_tokens[row["bcv"]].append(row["text"])  # text includes punctuation

    # Second pass: build questions with verseText and tokenIndex
    for book in range(1, 28):
        for row in morphgnt_rows(book):
            pos = row["ccat-pos"]
            morph = parse_morph(row["ccat-parse"], pos)
            q = None
            if pos == "N-":
                paradigm = classify_noun(row["lemma"], morph)
                if paradigm:
                    q = build_noun_question(row, paradigm)
                else:
                    skipped["noun_other"] += 1
            elif pos == "V-":
                paradigm = classify_verb(row["lemma"], morph)
                if paradigm:
                    q = build_verb_question(row, paradigm)
                else:
                    skipped["verb_other"] += 1
            if q:
                # Attach verse text and target index
                tokens = verse_tokens[row["bcv"]]
                q["verseText"] = " ".join(tokens)
                # Find index of THIS token within the verse (first match by exact text + position fallback)
                # Use the row's text field for exact match including punctuation
                try:
                    q["tokenIndex"] = tokens.index(row["text"])
                except ValueError:
                    q["tokenIndex"] = -1
                raw.append(q)

    # Cap per cell to keep dataset compact; prefer lemma diversity
    by_cell = defaultdict(list)
    for q in raw:
        if q["type"] == "noun":
            key = cell_key_noun(q)
        else:
            key = cell_key_verb(q)
        by_cell[key].append(q)

    final = []
    paradigm_counts = defaultdict(int)
    for key, qs in by_cell.items():
        # Sort by lemma to get diversity, then take first N unique lemmas; fill remainder if cap not reached
        seen_lemmas = {}
        for q in qs:
            seen_lemmas.setdefault(q["lemma"], q)
        unique_lemma_questions = list(seen_lemmas.values())[:PER_CELL_CAP]
        for q in unique_lemma_questions:
            final.append(q)
            paradigm_counts[q["paradigm"]] += 1

    print(f"\nFinal questions (capped at {PER_CELL_CAP}/cell): {len(final)}")
    print(f"\nParadigm counts:")
    for p, n in sorted(paradigm_counts.items(), key=lambda x: -x[1]):
        print(f"  {p}: {n}")
    print(f"\nSkipped (out of MVP scope): {dict(skipped)}")
    out_path = "/sessions/friendly-adoring-bell/mnt/Greek Lessons/data/questions.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final, f, ensure_ascii=False, separators=(",", ":"))
    print(f"\nWritten to {out_path}")
    import os
    print(f"Size: {os.path.getsize(out_path)/1024:.1f} KB")


if __name__ == "__main__":
    main()
