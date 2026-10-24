def calculate_effective_solar(solar_w_m2: float, is_shaded: bool = False) -> float:
    """노면에 도달하는 유효 일사량(W/m²)을 계산합니다."""
    safe_solar = max(0.0, float(solar_w_m2))
    shade_factor = 0.30 if is_shaded else 1.0
    return round(safe_solar * shade_factor, 2)