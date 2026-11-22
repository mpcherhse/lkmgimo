"""Правила системы академического рейтинга МГИМО."""
from app import grading


def rec(**kw):
    base = {"slice1": None, "slice2": None, "slice3": None, "bonus": 0, "exam": None, "social": None, "retakes": 0}
    base.update(kw)
    return base


def test_scale_edges():
    assert grading.grade(90)["letter"] == "A" and grading.grade(89.9)["letter"] == "B"
    assert grading.grade(82)["five"] == 4 and grading.grade(75)["letter"] == "C"
    assert grading.grade(67)["letter"] == "D" and grading.grade(60)["letter"] == "E" and grading.grade(59.9)["letter"] == "F"


def test_formula_exam():
    d = grading.discipline(rec(slice1=90, slice2=80, slice3=85, exam=90, social=100), "exam")
    assert d["b1"] == 85 and d["final"] == round(0.4 * 85 + 0.5 * 90 + 0.1 * 100, 2)


def test_bonus_capped_at_100():
    d = grading.discipline(rec(slice1=98, slice2=99, slice3=97, bonus=10), "exam")
    assert d["b1"] == 100


def test_auto_zachet_rule_70():
    d = grading.discipline(rec(slice1=70, slice2=72, slice3=74, social=90), "zachet")
    assert d["auto_zachet"] and d["b2"] == 72 and d["final"] is not None


def test_traditional_zachet_capped_69():
    d = grading.discipline(rec(slice1=60, slice2=65, slice3=62, exam=95, social=90), "zachet")
    assert not d["auto_zachet"] and d["b2"] == 69


def test_retake_penalty():
    first = grading.discipline(rec(slice1=70, slice2=70, slice3=70, exam=80, social=80, retakes=1), "exam")
    second = grading.discipline(rec(slice1=70, slice2=70, slice3=70, exam=80, social=80, retakes=2), "exam")
    assert first["b2"] == 70 and second["b2"] == 60


def test_needs_for_excellent():
    n = grading.needs(80, "exam")
    item = next(x for x in n["items"] if x["target"] == 90)
    # 90 = 0.4*80 + 0.5*x + 0.1*90 -> x = 98
    assert item["need"] == 98.0 and item["reachable"]


def test_semester_mean_and_bonus():
    rows = [(rec(slice1=90, slice2=90, slice3=90, exam=90, social=90), "exam"), (rec(slice1=80, slice2=80, slice3=80, exam=80, social=80), "exam")]
    s = grading.semester(rows, bonus=3)
    assert s["complete"] and s["rating"] == 88


def test_discount():
    assert grading.tuition_discount([91, 92, 90], False)["discount"] == 30
    assert grading.tuition_discount([96, 95, 97], False)["discount"] == 60
    assert grading.tuition_discount([96, 95, 97], True)["discount"] == 0
