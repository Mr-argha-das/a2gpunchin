from math import sqrt


def cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = sqrt(sum(a * a for a in left))
    right_norm = sqrt(sum(b * b for b in right))
    if not left_norm or not right_norm:
        return 0.0
    return dot / (left_norm * right_norm)


def best_face_match(query: list[float], candidates, threshold: float = 0.72):
    best_employee = None
    best_score = 0.0
    for employee in candidates:
        score = cosine_similarity(query, employee.face_embedding or [])
        if score > best_score:
            best_employee = employee
            best_score = score
    if best_employee and best_score >= threshold:
        return best_employee, round(best_score, 4)
    return None, round(best_score, 4)
