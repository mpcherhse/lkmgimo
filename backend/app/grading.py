"""Система академического рейтинга МГИМО (по открытому «Положению об академическом рейтинге студентов»).

Рейтинг по дисциплине за семестр: Р = 0,4·Б1 + 0,5·Б2 + 0,1·Б3, всё в процентах.
- Б1 — текущий контроль: среднее трёх «срезов» (до 6-й, 12-й и 15/16-й недели) + премия преподавателя до 10 п.п. (итог ≤ 100).
- Б2 — экзамен или зачёт. «Правило 70%»: Б1 ≥ 70 → автоматический зачёт с оценкой Б1; иначе традиционный зачёт, оценка ≤ 69.
  Пересдача: в ведомость — фактическая оценка, в рейтинг — минус 10 п.п. (1-я) и минус 20 п.п. (2-я).
- Б3 — социальные характеристики (эрудиция, прилежание, активность, посещаемость…), ставит преподаватель в конце семестра.
Рейтинг за семестр — среднее по дисциплинам (кредиты не взвешиваются) + бонус за научную и общественную работу 0–5, итог ≤ 100.
Шкала: 90–100 A «отлично»; 82–89 B и 75–81 C «хорошо»; 67–74 D и 60–66 E «удовлетворительно»; < 60 F «неудовлетворительно»."""

W1, W2, W3 = 0.4, 0.5, 0.1
SCALE = [(90, "A", 5, "отлично"), (82, "B", 4, "хорошо"), (75, "C", 4, "хорошо"),
         (67, "D", 3, "удовлетворительно"), (60, "E", 3, "удовлетворительно"), (0, "F", 2, "неудовлетворительно")]
AUTO_ZACHET = 70
RETAKE_PENALTY = 10
TARGETS = (90, 82, 75, 60)


def grade(percent):
    if percent is None:
        return None
    p = float(percent)
    for edge, letter, five, word in SCALE:
        if p >= edge:
            return {"percent": round(p, 1), "letter": letter, "five": five, "word": word}
    return None


def _f(x):
    return None if x is None else float(x)


def block1(rec):
    """-> (значение Б1 или None, сколько срезов есть, итог ли)"""
    slices = [_f(rec[k]) for k in ("slice1", "slice2", "slice3") if rec.get(k) is not None]
    if not slices:
        return None, 0, False
    value = min(100.0, sum(slices) / len(slices) + _f(rec.get("bonus") or 0))
    return round(value, 2), len(slices), len(slices) == 3


def discipline(rec, control):
    """полная картина по дисциплине: блоки, правило 70%, рейтинг (итоговый или прогноз), что нужно для целей"""
    b1, n_slices, b1_final = block1(rec)
    exam = _f(rec.get("exam"))
    social = _f(rec.get("social"))
    retakes = int(rec.get("retakes") or 0)
    auto = control == "zachet" and b1_final and b1 is not None and b1 >= AUTO_ZACHET
    b2 = None
    if auto:
        b2 = b1
    elif exam is not None:
        b2 = exam
        if control == "zachet" and b1 is not None and b1 < AUTO_ZACHET:
            b2 = min(b2, 69.0)
        b2 = max(0.0, b2 - RETAKE_PENALTY * retakes)
    final = None
    if b1 is not None and b2 is not None and social is not None:
        final = round(W1 * b1 + W2 * b2 + W3 * social, 2)
    out = {
        "b1": b1, "b1_slices": n_slices, "b1_final": b1_final, "bonus": _f(rec.get("bonus") or 0),
        "slices": [_f(rec.get("slice1")), _f(rec.get("slice2")), _f(rec.get("slice3"))],
        "b2": b2, "exam_raw": exam, "b3": social, "retakes": retakes,
        "auto_zachet": bool(auto),
        "zachet_cap": control == "zachet" and b1_final and b1 is not None and b1 < AUTO_ZACHET,
        "final": final, "final_grade": grade(final),
        "b1_grade": grade(b1),
        "needs": None,
    }
    if final is None and b1 is not None:
        out["needs"] = needs(b1, control, assumed_social=social)
    return out


def needs(b1, control, assumed_social=None):
    """сколько нужно на экзамене (Б2), чтобы итог по дисциплине дошёл до 90/82/75/60.
    Б3 ещё неизвестен — считаем по выставленному, иначе по допущению 90 (так и показываем)"""
    s = assumed_social if assumed_social is not None else 90.0
    res = []
    for target in TARGETS:
        if control == "zachet" and b1 >= AUTO_ZACHET:
            got = W1 * b1 + W2 * b1 + W3 * s
            res.append({"target": target, "need": None, "auto": True, "reachable": got >= target})
            continue
        need = (target - W1 * b1 - W3 * s) / W2
        cap = 69.0 if control == "zachet" else 100.0
        res.append({"target": target, "need": max(0.0, round(need, 1)), "auto": False, "reachable": need <= cap})
    return {"assumed_social": s, "social_assumed": assumed_social is None, "items": res}


def semester(rows, bonus=0.0):
    """rows: [(rec, control)]. Итог семестра, если все дисциплины закрыты; иначе прогноз по Б1"""
    finals, progress = [], []
    for rec, control in rows:
        d = discipline(rec, control)
        if d["final"] is not None:
            finals.append(d["final"])
        if d["b1"] is not None:
            progress.append(d["final"] if d["final"] is not None else d["b1"])
    complete = bool(rows) and len(finals) == len(rows)
    value = None
    if complete:
        value = round(min(100.0, sum(finals) / len(finals) + float(bonus or 0)), 2)
    estimate = round(sum(progress) / len(progress), 2) if progress else None
    return {"complete": complete, "rating": value, "grade": grade(value), "estimate": estimate, "estimate_grade": grade(estimate),
            "bonus": float(bonus or 0), "disciplines": len(rows), "closed": len(finals)}


DISCOUNTS = [(95, 60), (90, 30)]


def tuition_discount(semester_ratings, had_retakes):
    """договорникам: средний рейтинг за 6 семестров ≥ 90 без пересдач — скидка 30%, ≥ 95 — 60% (памятка студенту, п. 4.22–4.23)"""
    if not semester_ratings:
        return None
    avg = round(sum(semester_ratings) / len(semester_ratings), 2)
    level = next((d for edge, d in DISCOUNTS if avg >= edge), 0)
    gap = None if avg >= 90 else round(90 - avg, 2)
    return {"average": avg, "semesters": len(semester_ratings), "of": 6, "discount": 0 if had_retakes else level,
            "blocked_by_retake": bool(had_retakes), "gap_to_30": gap}
