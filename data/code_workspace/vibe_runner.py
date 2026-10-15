"""PAPSrun 학생 알고리즘 작업 영역 예제 스크립트."""

def calculate_path_cost(distance_m, slope_pct, surface_type):
    # 노면별 마찰계수 보정
    surface_weights = {
        'urethane_track': 0.8,
        'lawn_grass': 1.0,
        'concrete_walkway': 1.1,
        'soil_trail': 1.2,
        'asphalt_dark': 1.3,
    }
    weight = surface_weights.get(surface_type, 1.0)
    # 경사도 보정 (오르막 저항)
    slope_factor = 1.0 + (max(0.0, slope_pct) * 0.05)
    return distance_m * weight * slope_factor


if __name__ == '__main__':
    sample_cost = calculate_path_cost(100.0, 3.5, 'urethane_track')
    print(f'계산된 경로 가중치 비용: {sample_cost:.2f}')
