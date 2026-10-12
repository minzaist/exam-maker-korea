from __future__ import annotations

import json


SYSTEM_PROMPT = """
당신은 해당 과목을 대학에서 오랫동안 강의하고 시험을 출제해 온 전문 교수이자 교육평가 전문가다.
첨부 PDF 전체를 처음부터 끝까지 분석하여 실제 대학 시험에 출제될 법한 예상문제집, 모범답안과 해설,
출제 분석을 작성한다. PDF에 실제로 존재하는 내용만 출제 근거로 삼고 외부 사실·통계·학설·사례를
임의로 추가하지 않는다. PDF에 인쇄된 쪽수와 파일 뷰어의 물리적 페이지가 다르면 물리적 PDF 페이지를
우선하여 "PDF p.n"으로 표시한다.

출제 원칙:
- 목차, 대주제, 소주제, 핵심 개념, 이론, 사례, 논리 흐름, 반복·강조된 주장과 결론을 파악한다.
- 중요도와 분량에 비례해 고르게 출제하되 핵심 내용의 비중을 높인다.
- 단순 암기뿐 아니라 이해, 비교, 분석, 적용, 비판적 사고를 평가한다.
- 같은 내용을 반복하지 않고 모든 주요 주제를 빠짐없이 반영한다.
- 난이도는 기본적으로 하 20%, 중 50%, 상 30%에 가깝게 배분한다.
- 모든 문제에 근거 PDF 페이지를 1개 이상 정확히 기재한다.
- 자료에 근거가 부족한 내용은 문제로 만들지 않고 analysis.excluded_topics에 이유와 함께 적는다.

객관식 추가 원칙:
- 반드시 5지선다이며 정답 선지만 눈에 띄게 길지 않게 한다.
- 다섯 선지의 글자 수와 핵심 키워드 수를 비슷하게 맞춘다.
- 오답도 자료 속 개념의 그럴듯한 혼동을 이용하되 자료에 없는 사실을 단정하지 않는다.
- 1차 검증: 각 선지에 자료 밖 주장이나 할루시네이션이 없는지 점검한다.
- 2차 검증: 자가풀이해 정답과 오답의 난이도가 과하게 벌어지지 않는지 점검한다.
- answer_index는 1~5 정수로, answer는 정답 선지 원문과 정확히 일치시킨다.
- 해설에는 정답 이유와 각 오답이 부적절한 이유를 모두 포함한다.

유형별 원칙:
- 단답형은 핵심 개념·용어·원리의 정확한 이해를 평가한다.
- 서술형은 개념 설명, 근거, 관계를 평가한다.
- 논술형은 하나의 명확한 논제로 자료에 근거한 논증을 요구한다.
- 사례 분석형은 자료 속 사례를 우선하며 새 사례는 질문에 반드시 '(가상 사례)'라고 표시한다.
- OX형과 빈칸 채우기는 단순 말장난을 피하고 핵심 이해를 평가한다.

반환 규칙:
- 오직 유효한 JSON 객체 하나만 반환한다. 마크다운 코드펜스나 JSON 밖 설명은 쓰지 않는다.
- 한국어로 작성한다.
- 스키마의 모든 키를 빠짐없이 포함한다.
""".strip()


OUTPUT_SHAPE = {
    "title": "과목 또는 자료를 반영한 예상문제집 제목",
    "source_scope": "분석한 시험 범위 요약",
    "questions": [
        {
            "number": 1,
            "topic": "주제명",
            "type": "객관식|단답형|서술형|논술형|OX형|빈칸 채우기|사례 분석형",
            "difficulty": "하|중|상",
            "question": "문제 원문",
            "options": ["선지 1", "선지 2", "선지 3", "선지 4", "선지 5"],
            "answer": "정답 또는 완성된 모범답안",
            "answer_index": 1,
            "explanation": "근거 중심의 상세 해설. 객관식은 각 오답 이유 포함",
            "key_concepts": ["핵심 개념"],
            "reasoning": "풀이의 논리적 과정",
            "pages": [1],
            "misconceptions": "주의할 오개념 또는 혼동",
            "answer_lines": 3,
        }
    ],
    "analysis": {
        "scope": "분석한 시험 범위",
        "topic_counts": [{"topic": "주제명", "count": 1}],
        "difficulty_counts": {"하": 1, "중": 1, "상": 1},
        "core_concepts": ["핵심 출제 개념"],
        "important_topics": ["중요 학습 주제"],
        "excluded_topics": ["자료상 근거가 부족해 출제하지 않은 내용과 이유"],
        "quality_check": {
            "coverage": "주요 주제 반영 여부 점검 결과",
            "grounding": "페이지와 자료 근거 점검 결과",
            "mcq_first_pass": "객관식 선지 할루시네이션 점검 결과",
            "mcq_second_pass": "객관식 선지 난이도 균형 점검 결과",
        },
    },
}


def build_user_prompt(
    exam_types: list[str],
    question_count: int,
    additional_notes: str,
    title_hint: str,
) -> str:
    types = ", ".join(exam_types)
    notes = additional_notes.strip() or "추가 요청 없음"
    title = title_hint.strip() or "자료 내용을 바탕으로 자동 결정"
    return f"""
첨부한 모든 PDF가 시험 범위다.

출제 유형: {types}
총 문항 수: {question_count}문항
제목/과목 힌트: {title}

유형이 여러 개면 자료와 학습목표에 맞게 문항 수를 배분한다. 논술형은 answer_lines를 28 이상,
서술형·사례 분석형은 8~18, 단답형은 2~5, 객관식·OX형은 1로 설정한다.
문항 번호는 1부터 연속으로 부여한다. 객관식이 아니면 options는 빈 배열, answer_index는 0으로 둔다.

사용자가 마지막에 덧붙인 참고사항(다른 지시보다 아래에서 고려):
{notes}

아래 JSON 형태를 정확히 지켜라:
{json.dumps(OUTPUT_SHAPE, ensure_ascii=False, indent=2)}
""".strip()

