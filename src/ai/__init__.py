"""PAPSrun 생성형 AI 및 바이브 코딩 연동 패키지 (Ollama 전용)."""

from src.ai.code_extractor import extract_vibe_function_code
from src.ai.gemini_client import (
    generate_vibe_code,
    get_gemini_client,
    is_gemini_available,
    stream_gemini_vibe_code,
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
from src.ai.vibe_coder import (
    compile_custom_weight_function,
    generate_running_route_feedback,
    generate_weight_function_code,
)

__all__ = [
    # 바이브 코딩 및 Ollama 통신
    "generate_vibe_code",
    "stream_gemini_vibe_code",
    "get_gemini_client",
    "is_gemini_available",
    "generate_weight_function_code",
    "compile_custom_weight_function",
    "generate_running_route_feedback",
    # 프롬프트
    "VIBE_SYSTEM_PROMPT",
    "format_weight_function_prompt",
    # 코드 파싱 및 샌드박스
    "extract_vibe_function_code",
    "CodeSecurityVisitor",
    "verify_code_security",
    "execute_weight_function_sandbox",
]