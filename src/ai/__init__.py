"""PAPSrun 생성형 AI 및 바이브 코딩 연동 패키지.

Gemini 모델 통신 클라이언트, 프롬프트 템플릿, 코드 블록 추출기,
그리고 AST 기반 샌드박스 실행기를 노출합니다.
"""

from src.ai.code_extractor import extract_vibe_function_code
from src.ai.gemini_client import (
    generate_vibe_code,
    get_gemini_client,
    is_gemini_available,
)
from src.ai.prompt_templates import (
    VIBE_SYSTEM_PROMPT,
    format_weight_function_prompt,
)
from src.ai.sandbox_runner import (
    CodeSecurityVisitor,
    execute_weight_function_sandbox,
    verify_code_security,
)

__all__ = [
    # Gemini 통신
    "generate_vibe_code",
    "get_gemini_client",
    "is_gemini_available",
    # 프롬프트
    "VIBE_SYSTEM_PROMPT",
    "format_weight_function_prompt",
    # 코드 파싱
    "extract_vibe_function_code",
    # AST 샌드박스 러너
    "CodeSecurityVisitor",
    "verify_code_security",
    "execute_weight_function_sandbox",
]