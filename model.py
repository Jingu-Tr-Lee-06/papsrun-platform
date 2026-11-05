import json

# 원본 도로 JSON 경로
input_path = r"C:\Users\leeji\papsrun_platform\data\cache\CLASS_2026_A_roads.json"
output_path = r"C:\Users\leeji\papsrun_platform\data\CLASS_2026_A_roads copy.json"

with open(input_path, "r", encoding="utf-8") as f:
    roads_data = json.load(f)

# 균등 배분할 프로필 정의 (일사량 700 W/m² 기준)
profiles = [
    {"surface_type": "asphalt_dark", "albedo": 0.10, "is_shaded": False, "rad": 630.0},
    {"surface_type": "concrete_walkway", "albedo": 0.30, "is_shaded": False, "rad": 490.0},
    {"surface_type": "urethane_track", "albedo": 0.20, "is_shaded": False, "rad": 560.0},
    {"surface_type": "soil_trail", "albedo": 0.25, "is_shaded": True, "rad": 157.5},
]

# 간선별로 순환(modulo) 적용
for idx, edge in enumerate(roads_data):
    p = profiles[idx % len(profiles)]
    edge["surface_type"] = p["surface_type"]
    edge["albedo"] = p["albedo"]
    edge["is_shaded"] = p["is_shaded"]
    edge["absorbed_rad_w_m2"] = p["rad"]
    edge["effective_solar_w_m2"] = 700.0 * (0.30 if p["is_shaded"] else 1.0)

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(roads_data, f, ensure_ascii=False, indent=2)

print(f"✅ {len(roads_data)}개 도로의 노면 비율 균등화 완료 -> {output_path}")