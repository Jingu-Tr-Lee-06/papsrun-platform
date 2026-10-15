"""AST 기반 안전성 검증 및 동적 가중치 함수 샌드박스 실행기.

바이브 코딩을 통해 생성된 파이썬 코드가 파일 시스템 접근, 서브프로세스 호출,
네트워크 소켓 통신 등의 유해 동작을 수행하지 못하도록 AST 노드를 정적 전수 검사하고,
안전하게 격리된 런타임 네임스페이스에서 다익스트라 가중치 함수 객체를 컴파일 및 실행합니다.
"""

import ast
import math
from typing import Any, Callable, Dict, Optional, Tuple

# 시스템 보안을 위협하는 금지 식별자 및 내장 함수 블랙리스트
DANGEROUS_BUILTINS = {
    "__import__",
    "open",
    "eval",
    "exec",
    "compile",
    "input",
    "os",
    "sys",
    "subprocess",
    "shutil",
    "socket",
    "requests",
    "urllib",
    "pickle",
    "posix",
    "nt",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "exit",
    "quit",
}


class CodeSecurityVisitor(ast.NodeVisitor):
    """AST 구문 트리를 순회하며 안전하지 않은 구문과 모듈 접근을 감지합니다."""

    def __init__(self) -> None:
        self.is_secure: bool = True
        self.rejection_reason: Optional[str] = None

    def visit_Import(self, node: ast.Import) -> None:
        """외부 라이브러리 import 제한 (수학 계산용 math 모듈만 허용)."""
        for alias in node.names:
            if alias.name != "math":
                self.is_secure = False
                self.rejection_reason = (
                    f"보안 정책 위반: '{alias.name}' 모듈의 임포트는 금지되어 있습니다. "
                    "(오직 math 모듈만 허용됩니다)"
                )
                return
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        """from ... import 문 제한."""
        if node.module != "math":
            self.is_secure = False
            self.rejection_reason = (
                f"보안 정책 위반: '{node.module}' 모듈로부터의 임포트는 금지되어 있습니다."
            )
            return
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        """블랙리스트에 명시된 위험 식별자 차단."""
        if node.id in DANGEROUS_BUILTINS:
            self.is_secure = False
            self.rejection_reason = f"보안 정책 위반: 금지된 함수/식별자 '{node.id}' 사용이 감지되었습니다."
            return
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        """클래스 계층 탈출 기법 차단 (__class__, __subclasses__ 등 언더스코어 속성)."""
        if node.attr.startswith("__"):
            self.is_secure = False
            self.rejection_reason = f"보안 정책 위반: 특수 매직 속성 '{node.attr}' 접근이 차단되었습니다."
            return
        self.generic_visit(node)


def verify_code_security(source_code: str) -> Tuple[bool, Optional[str]]:
    """파이썬 소스코드의 문법 및 보안 무결성을 판정합니다.

    Args:
        source_code: 검증 대상 파이썬 소스코드 문자열

    Returns:
        (안전 여부, 오류 또는 거부 사유 문자열)
    """
    if not source_code or not source_code.strip():
        return False, "제공된 소스코드가 비어 있습니다."

    try:
        syntax_tree = ast.parse(source_code)
    except SyntaxError as e:
        return False, f"파이썬 문법 오류(SyntaxError): {str(e)}"

    visitor = CodeSecurityVisitor()
    visitor.visit(syntax_tree)

    if not visitor.is_secure:
        return False, visitor.rejection_reason

    # 대상 필수 함수 정의(custom_weight_function) 유무 검사
    target_found = any(
        isinstance(node, ast.FunctionDef) and node.name == "custom_weight_function"
        for node in syntax_tree.body
    )
    if not target_found:
        return False, "소스코드 내에 'def custom_weight_function(u, v, edge_dict):' 정의가 누락되었습니다."

    return True, None


def execute_weight_function_sandbox(
    source_code: str,
) -> Tuple[Optional[Callable[[str, str, Dict[str, Any]], float]], Optional[str]]:
    """검증된 소스코드를 격리된 환경에서 컴파일하고 유효한 함수 객체로 반환합니다.

    Args:
        source_code: 파이썬 소스코드 문자열

    Returns:
        (호출 가능한 가중치 함수, 오류 메시지)
    """
    is_safe, error_msg = verify_code_security(source_code)
    if not is_safe:
        return None, error_msg

    # 최소 필수 산술 연산 및 math 내장 객체만 포함하는 안전 네임스페이스
    restricted_builtins = {
        "abs": abs,
        "round": round,
        "min": min,
        "max": max,
        "float": float,
        "int": int,
        "bool": bool,
        "len": len,
        "sum": sum,
        "range": range,
    }

    execution_globals: Dict[str, Any] = {
        "__builtins__": restricted_builtins,
        "math": math,
    }
    execution_locals: Dict[str, Any] = {}

    try:
        exec(source_code, execution_globals, execution_locals)
    except Exception as e:
        return None, f"함수 스코프 컴파일 실패: {str(e)}"

    func = execution_locals.get("custom_weight_function")
    if not callable(func):
        return None, "custom_weight_function이 호출 가능한 함수로 정의되지 않았습니다."

    # 모의 간선 데이터 기반 단위 테스트 실행 (양수 가중치 보장 검증)
    mock_edge = {
        "length": 120.0,
        "slope": 2.5,
        "surface_type": "urethane_track",
        "is_shaded": True,
        "net_rn": 280.0,
    }

    try:
        test_cost = func("NODE_START", "NODE_END", mock_edge)
        cost_val = float(test_cost)
        if cost_val <= 0:
            return (
                None,
                f"가중치 함수의 반환값({cost_val})은 다익스트라 제약조건상 반드시 0보다 큰 양수여야 합니다.",
            )
    except Exception as e:
        return None, f"테스트 실행 중 런타임 예외 발생: {str(e)}"

    return func, None