from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from typing import Any

from openai import OpenAI

from prompts import SYSTEM_PROMPT, build_user_prompt


ALLOWED_TYPES = {
    "객관식",
    "단답형",
    "서술형",
    "논술형",
    "OX형",
    "빈칸 채우기",
    "사례 분석형",
}


@dataclass
class GenerationResult:
    data: dict[str, Any]
    warnings: list[str]
    model: str


class GenerationError(RuntimeError):
    pass


def _extract_json(text: str) -> dict[str, Any]:
    value = text.strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        start, end = value.find("{"), value.rfind("}")
        if start < 0 or end <= start:
            raise GenerationError("모델 응답에서 JSON을 찾지 못했습니다.")
        try:
            parsed = json.loads(value[start : end + 1])
        except json.JSONDecodeError as exc:
            raise GenerationError("모델 응답의 JSON 형식이 올바르지 않습니다.") from exc
    if not isinstance(parsed, dict):
        raise GenerationError("모델 응답이 JSON 객체가 아닙니다.")
    return parsed


def _coerce_pages(pages: Any) -> list[int]:
    if not isinstance(pages, list):
        pages = [pages]
    result: list[int] = []
    for page in pages:
        match = re.search(r"\d+", str(page))
        if match:
            number = int(match.group())
            if number > 0 and number not in result:
                result.append(number)
    return result


def normalize_and_validate(data: dict[str, Any], expected_count: int) -> tuple[dict[str, Any], list[str]]:
    warnings: list[str] = []
    questions = data.get("questions")
    if not isinstance(questions, list) or not questions:
        raise GenerationError("생성된 문항이 없습니다.")

    normalized: list[dict[str, Any]] = []
    for index, raw in enumerate(questions, start=1):
        if not isinstance(raw, dict):
            warnings.append(f"{index}번 문항의 형식이 잘못되어 제외했습니다.")
            continue
        question = dict(raw)
        question["number"] = index
        question["topic"] = str(question.get("topic") or "기타")
        qtype = str(question.get("type") or "서술형")
        question["type"] = qtype if qtype in ALLOWED_TYPES else "서술형"
        difficulty = str(question.get("difficulty") or "중")
        question["difficulty"] = difficulty if difficulty in {"상", "중", "하"} else "중"
        question["question"] = str(question.get("question") or "").strip()
        question["answer"] = str(question.get("answer") or "").strip()
        question["explanation"] = str(question.get("explanation") or "").strip()
        question["reasoning"] = str(question.get("reasoning") or "").strip()
        question["misconceptions"] = str(question.get("misconceptions") or "").strip()
        concepts = question.get("key_concepts")
        question["key_concepts"] = [str(v) for v in concepts] if isinstance(concepts, list) else []
        question["pages"] = _coerce_pages(question.get("pages", []))
        if not question["pages"]:
            warnings.append(f"{index}번 문항에 PDF 페이지 근거가 없습니다.")

        options = question.get("options")
        question["options"] = [str(v).strip() for v in options] if isinstance(options, list) else []
        try:
            answer_index = int(question.get("answer_index") or 0)
        except (TypeError, ValueError):
            answer_index = 0
        question["answer_index"] = answer_index

        if question["type"] == "객관식":
            if len(question["options"]) != 5:
                warnings.append(f"{index}번 객관식이 5지선다 형식을 충족하지 못했습니다.")
            if not 1 <= answer_index <= len(question["options"]):
                warnings.append(f"{index}번 객관식의 정답 번호가 올바르지 않습니다.")
            lengths = [len(re.sub(r"\s+", "", option)) for option in question["options"] if option]
            if lengths and (max(lengths) - min(lengths) > 28 or max(lengths) > max(1, min(lengths)) * 1.65):
                warnings.append(f"{index}번 객관식 선지 길이 균형을 다시 확인하세요.")
            if len(set(question["options"])) != len(question["options"]):
                warnings.append(f"{index}번 객관식에 중복 선지가 있습니다.")
        else:
            question["answer_index"] = 0
            question["options"] = []

        default_lines = {
            "객관식": 1,
            "OX형": 1,
            "빈칸 채우기": 2,
            "단답형": 4,
            "서술형": 10,
            "사례 분석형": 14,
            "논술형": 30,
        }[question["type"]]
        try:
            question["answer_lines"] = max(1, min(34, int(question.get("answer_lines") or default_lines)))
        except (TypeError, ValueError):
            question["answer_lines"] = default_lines
        normalized.append(question)

    if len(normalized) != expected_count:
        warnings.append(f"요청한 {expected_count}문항 중 {len(normalized)}문항이 생성되었습니다.")
    data["questions"] = normalized
    data["title"] = str(data.get("title") or "예상문제집")
    data["source_scope"] = str(data.get("source_scope") or "첨부 PDF 전체")
    if not isinstance(data.get("analysis"), dict):
        data["analysis"] = {}
    return data, warnings


def _pdf_content(file_name: str, file_bytes: bytes) -> dict[str, str]:
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return {
        "type": "input_file",
        "filename": file_name,
        "file_data": f"data:application/pdf;base64,{encoded}",
        "detail": "high",
    }


def generate_exam(
    api_key: str,
    model: str,
    files: list[tuple[str, bytes]],
    exam_types: list[str],
    question_count: int,
    additional_notes: str,
    title_hint: str,
    safety_identifier: str,
) -> GenerationResult:
    if not api_key:
        raise GenerationError("OpenAI API 키가 설정되지 않았습니다.")
    if not files:
        raise GenerationError("PDF 파일을 한 개 이상 올려주세요.")
    if sum(len(content) for _, content in files) > 49 * 1024 * 1024:
        raise GenerationError("PDF 전체 용량은 49MB 이하여야 합니다.")

    client = OpenAI(api_key=api_key, timeout=300.0)
    content: list[dict[str, str]] = [_pdf_content(name, body) for name, body in files]
    content.append(
        {
            "type": "input_text",
            "text": build_user_prompt(exam_types, question_count, additional_notes, title_hint),
        }
    )
    try:
        response = client.responses.create(
            model=model,
            instructions=SYSTEM_PROMPT,
            input=[{"role": "user", "content": content}],
            max_output_tokens=24000,
            store=False,
            safety_identifier=safety_identifier[:128],
        )
    except Exception as exc:
        raise GenerationError(f"문제 생성 요청에 실패했습니다: {exc}") from exc

    data = _extract_json(response.output_text)
    data, warnings = normalize_and_validate(data, question_count)
    return GenerationResult(data=data, warnings=warnings, model=model)

