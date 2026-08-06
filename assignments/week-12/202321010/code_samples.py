"""
code_samples.py
---------------
Lab 12 평가 대상 코드 샘플 10개.
각 샘플은 의도적으로 다양한 품질 수준을 갖도록 설계됨:
  - 보안 취약점, 버그, 비효율, 과도한 장황함, 사문(dead code) 등
"""

SAMPLES = [
    # ────────────────────────────────────────────────────────────────
    # Sample 1: 정석적인 이진 탐색 – 정확하고 효율적이며 가독성 높음
    # ────────────────────────────────────────────────────────────────
    {
        "id": 1,
        "name": "Clean Binary Search",
        "expected_quality": "high",
        "notes": "Correct O(log n), readable, no issues",
        "code": """\
def binary_search(arr: list, target: int) -> int:
    \"\"\"정렬된 배열에서 target 의 인덱스를 반환. 없으면 -1.\"\"\"
    left, right = 0, len(arr) - 1
    while left <= right:
        mid = (left + right) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            left = mid + 1
        else:
            right = mid - 1
    return -1
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 2: 조기 종료 없는 버블 정렬 – 동작하지만 비효율
    # ────────────────────────────────────────────────────────────────
    {
        "id": 2,
        "name": "Inefficient Bubble Sort (no early exit)",
        "expected_quality": "medium-low",
        "notes": "O(n^2) even on sorted input, no early-exit flag",
        "code": """\
def bubble_sort(arr):
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 3: SQL 인젝션 취약점 – 심각한 보안 결함
    # ────────────────────────────────────────────────────────────────
    {
        "id": 3,
        "name": "SQL Injection Vulnerability",
        "expected_quality": "very-low",
        "notes": "Classic OWASP A03 injection flaw via string concatenation",
        "code": """\
import sqlite3

def get_user(username):
    conn = sqlite3.connect("users.db")
    cursor = conn.cursor()
    # 위험: 사용자 입력을 직접 쿼리에 삽입
    query = "SELECT * FROM users WHERE username = '" + username + "'"
    cursor.execute(query)
    return cursor.fetchone()
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 4: off-by-one 버그 – 마지막 원소를 건너뜀
    # ────────────────────────────────────────────────────────────────
    {
        "id": 4,
        "name": "Off-by-One Bug in Loop",
        "expected_quality": "low",
        "notes": "Last element is never processed; wrong results for non-empty list",
        "code": """\
def sum_list(numbers):
    total = 0
    for i in range(len(numbers) - 1):   # 버그: 마지막 원소 제외
        total += numbers[i]
    return total
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 5: 장황하고 주석이 과도한 정확한 코드 (Length-bias test A)
    # LLM 이 길이 편향으로 실제보다 높게 평가할 가능성
    # ────────────────────────────────────────────────────────────────
    {
        "id": 5,
        "name": "Verbose Correct Code (length-bias probe)",
        "expected_quality": "medium",
        "notes": "Correct but over-commented; designed to trigger LLM length bias",
        "code": """\
def calculate_average(numbers):
    \"\"\"
    주어진 숫자 리스트의 평균을 계산하는 함수입니다.

    이 함수는 다음과 같은 단계를 수행합니다:
      1. 입력 리스트가 비어 있는지 확인합니다.
      2. 비어 있다면 None 을 반환합니다.
      3. 그렇지 않으면 모든 원소를 합산합니다.
      4. 합산된 값을 원소의 개수로 나눕니다.
      5. 결과를 반환합니다.

    Parameters
    ----------
    numbers : list
        평균을 계산할 숫자들이 담긴 리스트.

    Returns
    -------
    float or None
        평균값, 또는 리스트가 비어 있으면 None.
    \"\"\"
    # 먼저 입력이 비어 있는지 확인합니다.
    if not numbers:
        # 빈 리스트의 경우 None 을 반환합니다.
        return None

    # 합계 변수를 0으로 초기화합니다.
    total = 0

    # 리스트의 각 숫자를 반복합니다.
    for number in numbers:
        # 현재 숫자를 total 에 더합니다.
        total = total + number

    # 원소의 개수를 구합니다.
    count = len(numbers)

    # 합계를 개수로 나누어 평균을 구합니다.
    average = total / count

    # 최종 평균값을 반환합니다.
    return average
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 6: 간결하고 우아한 정확한 코드 (Length-bias test B)
    # 실제 품질은 5보다 높지만 짧아서 LLM 이 낮게 평가할 가능성
    # ────────────────────────────────────────────────────────────────
    {
        "id": 6,
        "name": "Concise Correct Code (length-bias probe)",
        "expected_quality": "high",
        "notes": "Same logic as sample 5, elegant one-liner idiom; may be underrated by LLM",
        "code": """\
def calculate_average(numbers: list) -> float | None:
    \"\"\"리스트 평균. 빈 리스트면 None 반환.\"\"\"
    return sum(numbers) / len(numbers) if numbers else None
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 7: 사문 코드와 미사용 변수
    # ────────────────────────────────────────────────────────────────
    {
        "id": 7,
        "name": "Dead Code and Unused Variables",
        "expected_quality": "medium-low",
        "notes": "Works but has dead branches and unused assignments",
        "code": """\
def find_max(numbers):
    result = None          # 결과 초기화
    unused_counter = 0     # 사용되지 않는 변수

    if len(numbers) == 0:
        return None

    result = numbers[0]
    for num in numbers:
        if num > result:
            result = num
        else:
            pass           # 의미 없는 else-pass

    # 도달하지 않는 코드
    if False:
        result = -1

    debug_info = {"max": result, "list": numbers}  # 반환되지 않음
    return result
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 8: 하드코딩된 자격증명 – 보안 반패턴
    # ────────────────────────────────────────────────────────────────
    {
        "id": 8,
        "name": "Hardcoded Credentials",
        "expected_quality": "very-low",
        "notes": "OWASP A02 – sensitive data embedded in source code",
        "code": """\
import requests

DB_PASSWORD = "super_secret_password_123"
API_KEY = "sk-prod-abcdef1234567890"

def fetch_data(endpoint):
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "X-DB-Pass": DB_PASSWORD,
    }
    response = requests.get(endpoint, headers=headers)
    return response.json()
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 9: 완전히 깨진 코드 – 문법 오류 + 논리 오류
    # ────────────────────────────────────────────────────────────────
    {
        "id": 9,
        "name": "Completely Broken Code",
        "expected_quality": "very-low",
        "notes": "SyntaxError: missing colon; also division-by-zero risk",
        "code": """\
def divide_numbers(a, b)
    result = a / b
    if result > 0
        print("positive")
    return reslt   # NameError: 오타
""",
    },

    # ────────────────────────────────────────────────────────────────
    # Sample 10: 과도한 추상화 – 동작하지만 불필요하게 복잡
    # ────────────────────────────────────────────────────────────────
    {
        "id": 10,
        "name": "Over-Engineered Simple Function",
        "expected_quality": "medium",
        "notes": "Factory pattern for a one-liner; correct but gold-plated",
        "code": """\
from typing import Callable

class OperationStrategy:
    def __init__(self, op: Callable):
        self._op = op
    def execute(self, a, b):
        return self._op(a, b)

class OperationFactory:
    _registry = {}

    @classmethod
    def register(cls, name: str, op: Callable):
        cls._registry[name] = OperationStrategy(op)

    @classmethod
    def get(cls, name: str) -> OperationStrategy:
        if name not in cls._registry:
            raise KeyError(f"Unknown operation: {name}")
        return cls._registry[name]

OperationFactory.register("add", lambda a, b: a + b)

def add_numbers(a: int, b: int) -> int:
    \"\"\"두 수를 더하는 오버엔지니어링 버전.\"\"\"
    strategy = OperationFactory.get("add")
    return strategy.execute(a, b)
""",
    },
]
