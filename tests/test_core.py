from __future__ import annotations

from pathlib import Path

from exports import make_answer_pdf, make_docx_zip, make_question_pdf, validate_pdf_bytes
from generator import normalize_and_validate
from storage import Storage


SAMPLE = {
    "title": "교육평가 예상문제집",
    "source_scope": "첨부 자료 1~12쪽",
    "questions": [
        {
            "number": 9,
            "topic": "평가의 기초",
            "type": "객관식",
            "difficulty": "중",
            "question": "자료에서 설명한 평가의 목적에 가장 가까운 것은?",
            "options": [
                "학습 상태를 체계적으로 확인한다",
                "수업 시간을 일률적으로 줄인다",
                "학생 집단을 임의로 재편성한다",
                "교재 내용을 전면적으로 대체한다",
                "학습 목표를 사후적으로 삭제한다",
            ],
            "answer": "학습 상태를 체계적으로 확인한다",
            "answer_index": 1,
            "explanation": "자료는 평가가 학습 상태를 확인하는 과정이라고 설명한다. 나머지 선지는 평가의 목적이 아니다.",
            "key_concepts": ["교육평가", "학습 상태"],
            "reasoning": "평가의 정의와 각 선지를 대조한다.",
            "pages": [3],
            "misconceptions": "평가를 단순 서열화로만 이해하지 않는다.",
            "answer_lines": 1,
        },
        {
            "number": 10,
            "topic": "평가의 기초",
            "type": "서술형",
            "difficulty": "상",
            "question": "평가와 피드백의 관계를 설명하라.",
            "options": [],
            "answer": "평가는 학습 상태를 확인하고, 피드백은 그 결과를 바탕으로 학습 개선을 돕는다.",
            "answer_index": 0,
            "explanation": "두 개념은 진단과 개선의 연속 과정으로 연결된다.",
            "key_concepts": ["평가", "피드백"],
            "reasoning": "각 개념을 정의한 뒤 인과 관계를 서술한다.",
            "pages": [4, 5],
            "misconceptions": "피드백을 점수 통보와 동일시하지 않는다.",
            "answer_lines": 8,
        },
    ],
    "analysis": {
        "scope": "평가의 개념과 피드백",
        "topic_counts": [{"topic": "평가의 기초", "count": 2}],
        "difficulty_counts": {"하": 0, "중": 1, "상": 1},
        "core_concepts": ["교육평가", "피드백"],
        "important_topics": ["평가와 피드백의 관계"],
        "excluded_topics": ["자료에 없는 통계 사례"],
        "quality_check": {"coverage": "통과", "grounding": "통과"},
    },
}


def test_normalize_and_export(tmp_path: Path) -> None:
    data, warnings = normalize_and_validate(SAMPLE.copy(), 2)
    assert not warnings
    assert [item["number"] for item in data["questions"]] == [1, 2]
    question_pdf = make_question_pdf(data)
    answer_pdf = make_answer_pdf(data)
    assert validate_pdf_bytes(question_pdf, "교육평가")["ok"]
    assert validate_pdf_bytes(answer_pdf, "교육평가")["ok"]
    assert len(make_docx_zip(data)) > 1000


def test_storage_signup_login_and_admin(tmp_path: Path) -> None:
    admin_number = "00-00000000"
    admin_name = "테스트관리자"
    storage = Storage(tmp_path / "test.db", "test-pepper", admin_number, admin_name)
    admin = storage.login(admin_number, admin_name)
    assert admin and admin.is_admin
    user = storage.signup("25-12345678", "홍길동", True)
    assert storage.login("25-12345678", "홍길동") == user
    activity = storage.start_activity(user.id, ["lecture.pdf"], ["객관식"], 12, "과목", "3장 강조")
    storage.finish_activity(activity, "결과")
    assert storage.list_activities()[0]["status"] == "완료"
