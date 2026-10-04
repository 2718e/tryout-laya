"""Render one request/response exchange as the terminal block."""
import json

_ANSWER_KEYS = ("choice", "noul", "score")


def format_exchange(*, timestamp, method, path, status, elapsed_ms,
                    request_body, metadata, response_body, max_chars) -> str:
    lines = ["[%s] %s %s -> %s in %.1fms" % (timestamp, method, path, status, elapsed_ms)]

    routing = response_body.get("routing") if isinstance(response_body, dict) else None
    client_id = _client_id(metadata)
    model = routing.get("model") if isinstance(routing, dict) else None
    if client_id or model:
        labels = [label for label in ("clientId=%s" % client_id if client_id else None,
                                      "model=%s" % model if model else None) if label]
        lines.append("  " + "  ".join(labels))

    if metadata is not None:
        lines.append("  metadata: " + _truncate(_json(metadata), max_chars))
    if isinstance(request_body, dict):
        if "state" in request_body:
            lines.append("  state: " + _truncate(_json(request_body["state"]), max_chars))
        if "questions" in request_body:
            lines.append("  questions: " + _truncate(_json(request_body["questions"]), max_chars))

    if status == 200 and isinstance(response_body, dict):
        if isinstance(routing, dict) and routing:
            lines.append("  routing: %s (%s)" % (routing.get("model"), routing.get("reason")))
        usage = response_body.get("usage")
        if isinstance(usage, dict) and usage:
            lines.append("  usage: input_tokens=%s output_tokens=%s"
                         % (usage.get("input_tokens"), usage.get("output_tokens")))
        answers = response_body.get("answers")
        if isinstance(answers, dict) and answers:
            lines.append("  answers: " + _truncate(_answers_summary(answers), max_chars))
    elif status != 200:
        detail = response_body.get("detail") if isinstance(response_body, dict) else None
        lines.append('  status=%s detail="%s"' % (status, _detail_text(detail)))

    return "\n".join(lines)


def _client_id(metadata):
    if isinstance(metadata, dict):
        value = metadata.get("clientId")
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _detail_text(detail):
    if detail is None:
        return ""
    return detail if isinstance(detail, str) else _json(detail)


def _answers_summary(answers):
    return " ".join("%s=%s" % (name, _answer_value(answer)) for name, answer in answers.items())


def _answer_value(answer):
    if isinstance(answer, dict):
        for key in _ANSWER_KEYS:
            if key in answer:
                return _short(answer[key])
    return _json(answer)


def _short(value):
    if isinstance(value, float):
        return "%.2f" % value
    return value if isinstance(value, str) else _json(value)


def _json(value):
    try:
        return json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError):
        return repr(value)


def _truncate(text, max_chars):
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "…(+%d chars)" % (len(text) - max_chars)
