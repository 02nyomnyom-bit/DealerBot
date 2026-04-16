# fishing.py
import discord
from discord import app_commands
from discord import embeds
from discord.ext import commands, tasks
import asyncio
import random
from typing import Optional, Literal
from datetime import datetime, timedelta

from database_manager import DatabaseManager

# ==========================================
# ⚙️ [데이터 설정]
# ==========================================

TRAPS = ["앗, 진동이 전혀 안 느껴진다!!", "앗! 오늘 날씨 진짜 좋다!!", "구름이 참 예쁘네... 풍경 감상 중."]
REAL_BITES = ["!!! 찌가 강하게 가라앉았다 !!!", "어이쿠! 낚싯대가 부러질 듯 휜다!", "손끝에 묵직-한 느낌이 든다!"]

TRASH_LIST = [
    # 🥫 [Group 1] 1티어 쓰레기 (1~5% 현금 지출)
    {"name": "찌그러진 빈 캔", "min_rate": 0.01, "max_rate": 0.05, "group": 1},
    {"name": "찢어진 장화", "min_rate": 0.01, "max_rate": 0.05, "group": 1},
    {"name": "오염된 동전 주머니", "min_rate": 0.01, "max_rate": 0.05, "group": 1},
    {"name": "먹다만 핫바", "min_rate": 0.01, "max_rate": 0.05, "group": 1},
    {"name": "신발에 붙은 껌", "min_rate": 0.01, "max_rate": 0.05, "group": 1},

    # 🔞 [Group 2] 2티어 쓰레기 (5~8% 현금 지출)
    {"name": "누군가가 쓴 애널 플러그", "min_rate": 0.05, "max_rate": 0.08, "group": 2},
    {"name": "야외플용 무선 진동기", "min_rate": 0.05, "max_rate": 0.08, "group": 2},
    {"name": "왕왕! 어떤 펫의 목줄", "min_rate": 0.05, "max_rate": 0.08, "group": 2},
    {"name": "쓰다만 애널 비즈", "min_rate": 0.05, "max_rate": 0.08, "group": 2},

    # ⛓️ [Group 3] 3티어 쓰레기 (8~10% 현금 지출)
    {"name": "헉.. 멜섭의 니플 집게", "min_rate": 0.08, "max_rate": 0.10, "group": 3},
    {"name": "선물용이였던 애널테일", "min_rate": 0.08, "max_rate": 0.10, "group": 3},
    {"name": "깍다만 패들", "min_rate": 0.08, "max_rate": 0.10, "group": 3},
    {"name": "영화관에서 쓴 콘돔", "min_rate": 0.08, "max_rate": 0.10, "group": 3},

    # 🖤 [Group 4] 4티어 쓰레기 (10~13% 현금 지출)
    {"name": "하드하게 사용했던 패들", "min_rate": 0.10, "max_rate": 0.13, "group": 4},
    {"name": "누군가 쓰다 버린 딜도", "min_rate": 0.10, "max_rate": 0.13, "group": 4},
    {"name": "펨돔이 쓰다버린 페니반", "min_rate": 0.10, "max_rate": 0.13, "group": 4},
    {"name": "펨돔이 쓰다버린 대왕딜도", "min_rate": 0.10, "max_rate": 0.13, "group": 4},

    # 🏛️ [Group 5] 5티어 쓰레기 (14~20% 현금 지출)
    {"name": "폐업하기 일보직전인 SM Bar", "min_rate": 0.14, "max_rate": 0.20, "group": 5},
    {"name": "로프 본디지에서 쓴 로프", "min_rate": 0.14, "max_rate": 0.20, "group": 5},
    {"name": "니니님의 직설적인 욕", "min_rate": 0.14, "max_rate": 0.20, "group": 5},

    # ❓ [Group 6] 히든 쓰레기 (1~80% 현금 지출)
    {"name": "???", "min_rate": 0.01, "max_rate": 0.80, "group": 6},
]

FISHING_ECOLOGY = {
    "호수": [
        # --- 흔함 ---
        {"name": "피라미", "rarity": "흔함", "chance": 0.20, "min": 5, "max": 15, "price_per_cm": 150, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "가장 기초적인 민물 잡어입니다."},
        {"name": "붕어", "rarity": "흔함", "chance": 0.15, "min": 15, "max": 30, "price_per_cm": 120, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "표준적인 민물 낚시의 손맛을 줍니다."},
        {"name": "잉어", "rarity": "흔함", "chance": 0.12, "min": 30, "max": 80, "price_per_cm": 50, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "몸집이 커서 초반 돈벌이에 좋습니다."},
        {"name": "메기", "rarity": "흔함", "chance": 0.12, "min": 30, "max": 70, "price_per_cm": 60, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "야행성 어종이며 탁한 물을 좋아합니다."},
        
        # --- 🚨 특수 동물/유해 생물 (호수) ---
        {"name": "수달", "rarity": "희귀", "chance": 0.05, "min": 40, "max": 60, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "가방에서 가장 비싼 물고기를 훔쳐갑니다!"},
        {"name": "자라", "rarity": "희귀", "chance": 0.06, "min": 20, "max": 35, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "물리면 치료비 5,000원이 지출됩니다."},
        {"name": "붉은가위가재", "rarity": "흔함", "chance": 0.05, "min": 10, "max": 20, "price_per_cm": 0, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "낚싯대 내구도를 -10 감소시킵니다."},

        # --- 희귀 ---
        {"name": "쏘가리", "rarity": "희귀", "chance": 0.04, "min": 25, "max": 50, "price_per_cm": 180, "req_tier": 2, "water_quality": [1,2], "effect_desc": "깨끗한 돌 틈에 살며, 잡을 시 명성 +50"},
        {"name": "무지개송어", "rarity": "희귀", "chance": 0.04, "min": 30, "max": 60, "price_per_cm": 150, "req_tier": 2, "water_quality": [1,2], "effect_desc": "화려한 무늬를 띱니다. 경험치 획득 +10%"},
        {"name": "은어", "rarity": "희귀", "chance": 0.03, "min": 15, "max": 25, "price_per_cm": 350, "req_tier": 2, "water_quality": [1], "effect_desc": "맑은 물에만 살며 수박 향이 납니다."},
        {"name": "향어", "rarity": "희귀", "chance": 0.03, "min": 40, "max": 70, "price_per_cm": 130, "req_tier": 2, "water_quality": [3,4], "effect_desc": "양식 기원 어종으로 묵직한 손맛을 줍니다."},
        
        # --- 신종 ---
        {"name": "아로와나", "rarity": "신종", "chance": 0.02, "min": 50, "max": 100, "price_per_cm": 280, "req_tier": 3, "water_quality": [1], "effect_desc": "살아있는 화석. 잡을 시 낚시터 명성 +100"},
        {"name": "피라루쿠", "rarity": "신종", "chance": 0.015, "min": 100, "max": 250, "price_per_cm": 110, "req_tier": 3, "water_quality": [2,3], "effect_desc": "거대 민물 어종입니다. 낚싯대 내구도 -5"},
        
        # --- 전설 ---
        {"name": "산천어", "rarity": "전설", "chance": 0.005, "min": 20, "max": 40, "price_per_cm": 1100, "req_tier": 4, "water_quality": [1], "effect_desc": "1급수 청정 지표 어종입니다."},
        {"name": "철갑상어", "rarity": "전설", "chance": 0.003, "min": 100, "max": 200, "price_per_cm": 220, "req_tier": 4, "water_quality": [1,2], "effect_desc": "고급 알(캐비아)을 품어 매우 비쌉니다."},
        
        # --- 환상 ---
        {"name": "황금 잉어", "rarity": "환상", "chance": 0.001, "min": 80, "max": 150, "price_per_cm": 500, "req_tier": 5, "water_quality": [1,2], "effect_desc": "영험한 영물. 잡을 시 모든 보유 시설 유지비 1회 면제"},
        {"name": "천지 네시", "rarity": "환상", "chance": 0.0005, "min": 300, "max": 700, "price_per_cm": 110, "req_tier": 5, "water_quality": [1], "effect_desc": "호수의 지배자. 낚을 시 낚싯대 내구도 -30"},
    ],

    "바다": [
        # --- 흔함 ---
        {"name": "전갱이", "rarity": "흔함", "chance": 0.15, "min": 15, "max": 30, "price_per_cm": 150, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "미끼 도둑으로 불리는 흔한 바다 어종입니다."},
        {"name": "고등어", "rarity": "흔함", "chance": 0.15, "min": 20, "max": 40, "price_per_cm": 110, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "국민 생선. 가장 흔하게 잡힙니다."},
        {"name": "전어", "rarity": "흔함", "chance": 0.12, "min": 15, "max": 30, "price_per_cm": 150, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "집 나간 며느리도 돌아온다는 가을 별미입니다."},
        
        # --- 🚨 특수 동물/유해 생물 (바다) ---
        {"name": "바다거북", "rarity": "신종", "chance": 0.07, "min": 80, "max": 120, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2], "effect_desc": "보호종을 방생하여 개인 명성 +500을 얻습니다!"},
        {"name": "보라성게", "rarity": "희귀", "chance": 0.08, "min": 5, "max": 15, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2,3,4,5], "effect_desc": "가시에 찔려 낚싯대 내구도가 -10 감소합니다."},
        {"name": "아무르불가사리", "rarity": "흔함", "chance": 0.08, "min": 10, "max": 25, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2,3,4,5], "effect_desc": "줄이 엉켜 미끼가 2개 더 소모됩니다."},

        # --- 희귀 ---
        {"name": "벵에돔", "rarity": "희귀", "chance": 0.04, "min": 25, "max": 50, "price_per_cm": 180, "req_tier": 2, "water_quality": [1,2], "effect_desc": "낚시꾼들의 로망 중 하나입니다. 잡을 시 개인 명성 +50"},
        {"name": "감성돔", "rarity": "희귀", "chance": 0.04, "min": 25, "max": 60, "price_per_cm": 150, "req_tier": 2, "water_quality": [1,2], "effect_desc": "바다의 왕자. 경험치 획득 +15%"},
        {"name": "우럭", "rarity": "희귀", "chance": 0.04, "min": 20, "max": 50, "price_per_cm": 180, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "바위 틈에 서식하는 대중적인 횟감입니다."},
        
        # --- 신종 ---
        {"name": "고래상어", "rarity": "신종", "chance": 0.02, "min": 500, "max": 1200, "price_per_cm": 24, "req_tier": 3, "water_quality": [1,2], "effect_desc": "지구상에서 가장 큰 어류입니다. 낚을 시 낚시터 명성 +500"},
        {"name": "타이거 샤크(뱀상어)", "rarity": "신종", "chance": 0.015, "min": 300, "max": 600, "price_per_cm": 45, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "무엇이든 먹어치우는 바다의 포식자입니다. 낚싯대 내구도 -15"},
        {"name": "대왕 오징어", "rarity": "신종", "chance": 0.015, "min": 200, "max": 1000, "price_per_cm": 28, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "심해의 거대 괴수입니다. 낚싯대 내구도 -10"},
        
        # --- 전설 ---
        {"name": "백상아리", "rarity": "전설", "chance": 0.005, "min": 300, "max": 600, "price_per_cm": 80, "req_tier": 4, "water_quality": [1,2], "effect_desc": "죠스의 주인공! 낚을 시 낚싯대 내구도 -35"},
        {"name": "혹등고래", "rarity": "전설", "chance": 0.004, "min": 1200, "max": 1600, "price_per_cm": 30, "req_tier": 4, "water_quality": [1,2], "effect_desc": "화려한 점프를 선보이는 온순한 거인입니다. 낚을 시 명성 +1,000"},
        
        # --- 환상 ---
        {"name": "돌고래", "rarity": "환상", "chance": 0.001, "min": 150, "max": 300, "price_per_cm": 250, "req_tier": 5, "water_quality": [1,2], "effect_desc": "바다의 천사. 잡을 시 다음 낚시 성공 확률 +15%"},
        {"name": "메갈로돈", "rarity": "환상", "chance": 0.0005, "min": 1500, "max": 2000, "price_per_cm": 38, "req_tier": 5, "water_quality": [1,2], "effect_desc": "고대의 초대형 상어. 낚을 시 낚싯대 내구도 -80"},
    ],

    "늪": [
        # --- 흔함 ---
        {"name": "검정말", "rarity": "흔함", "chance": 0.15, "min": 10, "max": 50, "price_per_cm": 80, "req_tier": 1, "water_quality": [3,4,5,6], "effect_desc": "늪 바닥에 무성한 수초입니다."},
        {"name": "부레옥잠", "rarity": "흔함", "chance": 0.15, "min": 10, "max": 30, "price_per_cm": 150, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "수질 정화 능력이 있는 흔한 수생식물입니다."},
        {"name": "해캄", "rarity": "흔함", "chance": 0.12, "min": 5, "max": 20, "price_per_cm": 200, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "탁한 물에 끼는 녹조류 뭉덩이입니다."},
        
        # --- 🚨 특수 동물/유해 생물 (늪) ---
        {"name": "너구리", "rarity": "희귀", "chance": 0.06, "min": 30, "max": 45, "price_per_cm": 0, "req_tier": 1, "water_quality": [2,3,4,5], "effect_desc": "가방을 털어 미끼 5개를 훔쳐 달아납니다!"},
        {"name": "황소개구리", "rarity": "전설", "chance": 0.05, "min": 15, "max": 30, "price_per_cm": 0, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "퇴치 포상금 10,000원을 얻지만 오염도가 상승합니다."},
        {"name": "붉은가위가재", "rarity": "흔함", "chance": 0.05, "min": 10, "max": 25, "price_per_cm": 0, "req_tier": 1, "water_quality": [3,4,5,6], "effect_desc": "낚싯대 내구도를 -10 감소시킵니다."},

        # --- 희귀 ---
        {"name": "민물새우", "rarity": "희귀", "chance": 0.04, "min": 3, "max": 8, "price_per_cm": 1100, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "작고 투명한 늪지 새우입니다."},
        {"name": "말조개", "rarity": "희귀", "chance": 0.04, "min": 10, "max": 25, "price_per_cm": 350, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "진흙 바닥에 서식하는 거대 민물 조개입니다."},
        {"name": "물방개", "rarity": "희귀", "chance": 0.03, "min": 2, "max": 5, "price_per_cm": 1800, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "헤엄을 잘 치는 수서곤충입니다."},
        
        # --- 신종 ---
        {"name": "누룩뱀", "rarity": "신종", "chance": 0.02, "min": 50, "max": 120, "price_per_cm": 220, "req_tier": 3, "water_quality": [3,4,5], "effect_desc": "늪 습지에서 보이는 뱀입니다."},
        {"name": "메기", "rarity": "신종", "chance": 0.015, "min": 30, "max": 70, "price_per_cm": 400, "req_tier": 3, "water_quality": [3,4,5,6], "effect_desc": "탁한 수질에 도가 튼 야행성 포식자입니다."},
        
        # --- 전설 ---
        {"name": "가물치", "rarity": "전설", "chance": 0.005, "min": 40, "max": 100, "price_per_cm": 450, "req_tier": 4, "water_quality": [3,4,5,6], "effect_desc": "늪지의 무법자이자 난폭한 최상위 어종입니다."},
        
        # --- 환상 ---
        {"name": "왜가리", "rarity": "환상", "chance": 0.001, "min": 80, "max": 110, "price_per_cm": 650, "req_tier": 5, "water_quality": [2,3,4], "effect_desc": "부동의 자세로 물고기를 사냥하는 새입니다."},
        {"name": "악어", "rarity": "환상", "chance": 0.0005, "min": 150, "max": 400, "price_per_cm": 180, "req_tier": 5, "water_quality": [3,4,5,6], "effect_desc": "늪지의 최종 지배자. 엄청난 데스롤을 시전하여 낚싯대 내구도 -60"},
    ]
}

CATEGORY_MAPPING = {
        "ticketing": "🎫 매표소 관련",
        "warehouse": "📦 물고기 창고 관련",
        "cleaning": "🧹 쓰레기 청소 관련",
        "power": "⚡ 발전소 관련",
        "reputation": "✨ 명성 증가 배율 관련",
        "recycling": "♻️ 쓰레기장 및 환경 관련",
        "etc_business": "🛒 그 외 사업 관련",
        "store": "🏪 가게 및 상업 관련",
        "school": "🏫 학교 관련 (방해요소)"
    }

RARITY_CONFIG = {
    "흔함": {"color": discord.Color.light_grey(), "emoji": "🐟"},
    "희귀": {"color": discord.Color.blue(), "emoji": "✨"},
    "신종": {"color": discord.Color.purple(), "emoji": "🧬"},
    "전설": {"color": discord.Color.gold(), "emoji": "🏆"},
    "환상": {"color": discord.Color.from_rgb(255, 0, 127), "emoji": "🌈"}
}

CATEGORY_FACILITIES = {
    "ticketing": ["간이매표소", "매표소", "일반매표소", "중형매표소", "대형매표소", "거대한매표소"],
    "warehouse": ["창고", "소형창고", "중형창고", "대형창고", "초거대한창고"],
    "cleaning": ["환경미화원", "청소용역업체", "시설관리공단"],
    "power": ["전기배터리", "소형발전기", "중대형발전기", "화력발전소", "수력발전소"],
    "reputation": ["길거리상인", "기념품상점", "기념품백화점", "해외입점준비", "해외유명기업"],
    "recycling": ["재활용분리수거장", "쓰레기소각장", "환경부"],
    "etc_business": ["리안마켓", "묵이편의점", "할인마트", "정E-마트", "해외수출사업"],
    "store": ["노상", "물사랑고기사랑가게", "5일장시장", "회전문공장", "세계1위기업"],
    "school": ["어린이집", "유치원", "초등학교", "중학교", "고등학교"]
}

FACILITIES = {
    # 🎫 수수료 조정 매표소 (입장료 수익 최적화)
    "간이매표소": {"req_rep": 2000, "req_cash": 150000, "tier": 1, "effect": {"fee_adj": 0.05}, "desc": "수수료 조정 범위 +-5%"},
    "매표소": {"req_rep": 12000, "req_cash": 450000, "tier": 2, "effect": {"fee_adj": 0.10}, "desc": "수수료 조정 범위 +-10%"},
    "일반매표소": {"req_rep": 40000, "req_cash": 1200000, "tier": 3, "effect": {"fee_adj": 0.15}, "desc": "수수료 조정 범위 +-15%"},
    "중형매표소": {"req_rep": 150000, "req_cash": 3500000, "tier": 3, "effect": {"fee_adj": 0.20}, "desc": "수수료 조정 범위 +-20%"},
    "대형매표소": {"req_rep": 500000, "req_cash": 8000000, "tier": 4, "effect": {"fee_adj": 0.25}, "desc": "수수료 조정 범위 +-25%"},
    "거대한매표소": {"req_rep": 1500000, "req_cash": 25000000, "tier": 5, "effect": {"fee_adj": 0.35}, "desc": "수수료 조정 범위 +-35%"},

    # 📦 물고기 확률 조정 (희귀 어종 포획의 핵심)
    "창고": {"req_rep": 5000, "req_cash": 250000, "tier": 1, "effect": {"fish_rate": 0.05, "base_fee": 0.05}, "desc": "확률 +5%, 유지비 +5%"},
    "소형창고": {"req_rep": 25000, "req_cash": 800000, "tier": 2, "effect": {"fish_rate": 0.10, "base_fee": 0.08, "upkeep_mult": 0.15}, "desc": "확률 +10%, 유지비 +15%"},
    "중형창고": {"req_rep": 100000, "req_cash": 2500000, "tier": 3, "effect": {"fish_rate": 0.15, "base_fee": 0.12, "upkeep_mult": 0.25}, "desc": "확률 +15%, 유지비 +25%"},
    "대형창고": {"req_rep": 450000, "req_cash": 7000000, "tier": 4, "effect": {"fish_rate": 0.20, "base_fee": 0.18, "upkeep_mult": 0.40}, "desc": "확률 +20%, 유지비 +40%"},
    "초거대한창고": {"req_rep": 1500000, "req_cash": 20000000, "tier": 5, "effect": {"fish_rate": 0.30, "base_fee": 0.25, "upkeep_mult": 0.65}, "desc": "확률 +30%, 유지비 +65%"},
    
    # 🧹 [환경 정화] 쓰레기 낚일 확률 억제
    "환경미화원": {"req_rep": 3000, "req_cash": 50000, "tier": 2, "effect": {"trash_rate": -0.05, "upkeep_mult": 0.05}, "desc": "쓰레기 5% 감소, 유지비 5% 증가"},
    "청소용역업체": {"req_rep": 50000, "req_cash": 250000, "tier": 3, "effect": {"trash_rate": -0.15, "upkeep_mult": 0.12}, "desc": "쓰레기 15% 감소, 유지비 12% 증가"},
    "시설관리공단": {"req_rep": 250000, "req_cash": 920000, "tier": 5, "effect": {"trash_rate": -0.30, "upkeep_mult": 0.25}, "desc": "쓰레기 30% 감소, 유지비 25% 증가"},

    # ⚡ 유지비 관련 시설 (전략적 운영의 핵심)
    "전기배터리": {"req_rep": 3000, "req_cash": 50000, "tier": 1, "effect": {"upkeep_discount": 0.05}, "desc": "유지비 5% 감소"},
    "소형발전기": {"req_rep": 5000, "req_cash": 100000, "tier": 2, "effect": {"upkeep_discount": 0.10}, "desc": "유지비 10% 감소"},
    "중대형발전기": {"req_rep": 50000, "req_cash": 500000, "tier": 3, "effect": {"upkeep_discount": 0.15}, "desc": "유지비 15% 감소"},
    "화력발전소": {"req_rep": 120000, "req_cash": 300000, "tier": 4, "effect": {"upkeep_discount": 0.25, "upkeep_mult": 0.10}, "desc": "유지비 25% 감소, 관리비 10% 증가"},
    "수력발전소": {"req_rep": 330000, "req_cash": 950000, "tier": 5, "effect": {"upkeep_discount": 0.45, "upkeep_mult": 0.20}, "desc": "유지비 45% 감소, 관리비 20% 증가"},

    # ✨ 명성 특화 (서버 랭킹 정복자용)
    "길거리상인": {"req_rep": 1000, "req_cash": 30000, "tier": 1, "effect": {"rep_mult": 1.2, "upkeep_mult": 0.03}, "desc": "명성 1.2배, 유지비 3% 증가"},
    "기념품상점": {"req_rep": 15000, "req_cash": 50000, "tier": 2, "effect": {"rep_mult": 1.5, "upkeep_mult": 0.06}, "desc": "명성 1.5배, 유지비 6% 증가"},
    "기념품백화점": {"req_rep": 80000, "req_cash": 410000, "tier": 3, "effect": {"rep_mult": 1.8, "upkeep_mult": 0.10}, "desc": "명성 1.8배, 유지비 10% 증가"},
    "해외입점준비": {"req_rep": 270000, "req_cash": 710000, "tier": 4, "effect": {"rep_mult": 2.2, "upkeep_mult": 0.15}, "desc": "명성 2.2배, 유지비 15% 증가"},
    "해외유명기업": {"req_rep": 500000, "req_cash": 1200000, "tier": 5, "effect": {"rep_mult": 3.0, "upkeep_mult": 0.25}, "desc": "명성 3.0배, 유지비 25% 증가"},

    # ♻️ 복합 환경 시설 (쓰레기 차단 + 가격 보너스)
    "재활용분리수거장": {"req_rep": 5000, "req_cash": 80000, "tier": 1, "effect": {"trash_rate": -0.10, "upkeep_mult": 0.08}, "desc": "쓰레기 10% 감소, 유지비 8% 증가"},
    "쓰레기소각장": {"req_rep": 120000, "req_cash": 320000, "tier": 3, "effect": {"fish_price_mult": 1.1, "trash_rate": -0.25, "upkeep_mult": 0.20}, "desc": "가격 1.1배, 쓰레기 25% 감소, 유지비 20% 증가"},
    "환경부": {"req_rep": 440000, "req_cash": 940000, "tier": 5, "effect": {"fish_price_mult": 1.5, "trash_rate": -0.50, "upkeep_mult": 0.45}, "desc": "가격 1.5배, 쓰레기 50% 감소, 유지비 45% 증가"},

    # 🛒 유틸리티 사업 (유지비 절감 + 명성 시너지)
    "리안마켓": {"req_rep": 3000, "req_cash": 20000, "tier": 1, "effect": {"upkeep_discount": 0.05}, "desc": "유지비 5% 감소"},
    "묵이편의점": {"req_rep": 20000, "req_cash": 70000, "tier": 2, "effect": {"upkeep_discount": 0.10}, "desc": "유지비 10% 감소"},
    "할인마트": {"req_rep": 80000, "req_cash": 330000, "tier": 3, "effect": {"upkeep_discount": 0.15, "rep_mult": 1.2}, "desc": "유지비 15% 감소, 명성 1.2배"},
    "정E-마트": {"req_rep": 150000, "req_cash": 700000, "tier": 4, "effect": {"upkeep_discount": 0.25, "rep_mult": 1.5}, "desc": "유지비 25% 감소, 명성 1.5배"},
    "해외수출사업": {"req_rep": 800000, "req_cash": 1090000, "tier": 5, "effect": {"upkeep_discount": 0.40, "rep_mult": 2.0}, "desc": "유지비 40% 감소, 명성 2.0배"},

    # 🏪 상업 제국 (물고기 판매가 극대화)
    "노상": {"req_rep": 5000, "req_cash": 50000, "tier": 1, "effect": {"fish_price_mult": 1.1}, "desc": "판매가 1.1배"},
    "물고기사랑가게": {"req_rep": 45000, "req_cash": 320000, "tier": 2, "effect": {"fish_price_mult": 1.2, "upkeep_mult": 0.15}, "desc": "판매가 1.4배, 유지비 15% 증가"},
    "5일장시장": {"req_rep": 200000, "req_cash": 650000, "tier": 3, "effect": {"fish_price_mult": 1.4, "upkeep_mult": 0.30}, "desc": "판매가 1.5배, 유지비 30% 증가"},
    "회전문공장": {"req_rep": 800000, "req_cash": 980000, "tier": 4, "effect": {"fish_price_mult": 1.7, "upkeep_mult": 0.50}, "desc": "판매가 1.8배, 유지비 50% 증가"},
    "세계1위기업": {"req_rep": 1000000, "req_cash": 1050000, "tier": 5, "effect": {"fish_price_mult": 2.0, "upkeep_mult": 0.85}, "desc": "판매가 2.0배, 유지비 85% 증가"},

    # 🏫 공공 시설 (실패 리스크 감수형 파격 유지비 절감)
    "어린이집": {"req_rep": 1000, "req_cash": 30000, "tier": 1, "effect": {"fail_rate": 0.05, "upkeep_discount": 0.10}, "desc": "실패 5%, 유지비 10% 감소"},
    "유치원": {"req_rep": 30000, "req_cash": 170000, "tier": 2, "effect": {"fail_rate": 0.08, "upkeep_discount": 0.20}, "desc": "실패 8%, 유지비 20% 감소"},
    "초등학교": {"req_rep": 70000, "req_cash": 650000, "tier": 3, "effect": {"fail_rate": 0.12, "upkeep_discount": 0.35}, "desc": "실패 12%, 유지비 35% 감소"},
    "중학교": {"req_rep": 150000, "req_cash": 990000, "tier": 4, "effect": {"fail_rate": 0.18, "upkeep_discount": 0.55}, "desc": "실패 18%, 유지비 55% 감소"},
    "고등학교": {"req_rep": 870000, "req_cash": 2070000, "tier": 5, "effect": {"fail_rate": 0.25, "upkeep_discount": 0.80}, "desc": "실패 25%, 유지비 80% 감소"},
}

active_sessions = {}
user_locks = {}

async def get_usage_benefit(user_id, guild_id, db):
    """최근 24시간 내 이용 횟수를 조회하여 0.5씩 이득 수치를 계산합니다."""
    now = datetime.now()
    one_day_ago = (now - timedelta(hours=24)).strftime('%Y-%m-%d %H:%M:%S')
    
    # 해당 길드(서버) 전체 또는 특정 낚시터의 24시간 내 이용 횟수 카운트
    query = "SELECT COUNT(*) as cnt FROM fishing_logs WHERE guild_id = ? AND timestamp > ?"
    result = db.execute_query(query, (str(guild_id), one_day_ago), 'one')
    
    count = result['cnt'] if result else 0
    return count * 0.1  # 1회당 0.1씩 이득 수치 반환

# ==========================================
# 👀 [UI 뷰 클래스 정의]
# ==========================================

class TrashActionView(discord.ui.View):
    def __init__(self, db, user_id, guild_id, channel_id, value_name, value, rate):
        super().__init__(timeout=40) # 방치 투기까지 40초
        self.db = db
        self.user_id = user_id
        self.guild_id = guild_id
        self.channel_id = channel_id
        self.value_name = value_name
        self.value = value
        self.rate = rate
        self.message = None
        self.responded = False # ✅ 추가: 응답 여부 확인용

    def is_finished(self):
        """이미 버튼을 눌러 처리가 완료되었는지 확인"""
        return self.responded

    async def process_neglect(self):
        """다른 명령어로 인해 강제로 방치 처리해야 할 때 호출"""
        if not self.responded:
            await self.on_timeout()

    # ⌛ [1] 시간 초과 (방치 투기) 시 벌금 징수 로직
    async def on_timeout(self):
        if self.message and not self.responded:
            self.responded = True # ✅ 추가: 중복 처리 방지
            try:
                chid, gid = str(self.channel_id), str(self.guild_id)
                uid = str(self.user_id)

                current_data = self.db.execute_query(
                    "SELECT pollution, owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", 
                    (chid, gid), 'one'
                )
                current_pollution = current_data['pollution'] if current_data else 0
                owner_id = current_data['owner_id'] if current_data else None

                added_pollution = 1.0 + (current_pollution * 0.2)
                
                # ✅ 공영 낚시터(소유주 없음)는 최대 50, 사유지는 최대 100 제한
                pollution_cap = 50.0 if owner_id is None else 100.0
                new_pollution = min(pollution_cap, current_pollution + added_pollution)

                conn = self.db.get_connection()
                fine_msg = ""
                ban_msg = ""
                
                conn.execute("BEGIN")
                conn.execute("UPDATE fishing_ground SET pollution = ? WHERE channel_id = ? AND guild_id = ?", (new_pollution, chid, gid))
                conn.execute("UPDATE users SET neglect_dump_count = neglect_dump_count + 1 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                
                user_data = self.db.execute_query("SELECT neglect_dump_count, cash, max_dump_rate FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
                user_count = user_data['neglect_dump_count'] if user_data else 0
                current_cash = user_data['cash'] if user_data else 0
                max_dump_rate = user_data['max_dump_rate'] if user_data else 0.0

                # 📈 최대 투기 비율 경신 체크
                if self.rate > max_dump_rate:
                    max_dump_rate = self.rate
                    conn.execute("UPDATE users SET max_dump_rate = ? WHERE user_id = ? AND guild_id = ?", (max_dump_rate, uid, gid))

                # 🚨 [벌금 로직 변경] 10회 이상이며 10의 배수일 때 부과
                trigger_fine = (user_count >= 10 and user_count % 10 == 0)

                if trigger_fine:
                    # 💰 벌금율: 역대 최대 비율 * 2.0
                    fine_rate = max_dump_rate * 2.0
                    calculated_fine = max(5000, int(current_cash * fine_rate))

                    if current_cash < 50000:
                        debt_fine = 50000 
                        conn.execute("UPDATE users SET fine_debt = fine_debt + ? WHERE user_id = ? AND guild_id = ?", (debt_fine, uid, gid))
                        
                        fine_msg = (
                            f"\n\n🚨 **[환경 방치투기 과태료 빚 적립]**\n"
                            f"방치가 누적 **{user_count}회** 적발되었습니다.\n"
                            f"현재 보유 자산이 5만 원 미만이므로, 앞으로 물고기 정산 시 `{debt_fine:,}원`이 자동 차감됩니다!"
                        )
                    else:
                        conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (calculated_fine, uid, gid))
                        conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                                     (uid, "과태료", -calculated_fine, current_cash - calculated_fine, f"방치투기 누적 {user_count}회 적발 과태료"))

                        fine_msg = f"\n\n🚨 **[환경 방치투기 과태료 부과!]**\n방치가 누적 **{user_count}회** 적발되었습니다.\n과태료 **{calculated_fine:,}원**(배율 {fine_rate:.2f})이 즉시 징수되었습니다!"
                
                # 🚫 50회당 페널티 (돈 없으면 시간제한, 돈 있으면 추가 과태료)
                if user_count % 50 == 0:
                    if current_cash < 50000:
                        ban_until = (datetime.now() + timedelta(minutes=30)).strftime('%Y-%m-%d %H:%M:%S')
                        conn.execute("UPDATE users SET fishing_ban_until = ? WHERE user_id = ? AND guild_id = ?", (ban_until, uid, gid))
                        ban_msg = f"\n\n🚫 **[저소득자 이용 제한]**\n방치투기 50회 누적되었으나, 벌금을 낼 자산이 부족하여 향후 **30분간** 이용이 금지됩니다."
                    else:
                        surcharge = 50000
                        conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (surcharge, uid, gid))
                        conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                                     (uid, "과태료", -surcharge, current_cash - surcharge, f"투기 50회 누적 가중 과태료"))
                        ban_msg = f"\n\n💸 **[가중 과태료 부과]**\n방치투기 50회 누적 페널티로 가중 과태료 **{surcharge:,}원**이 추가 징수되었습니다. (소지금 보유로 이용 제한 면제)"

                conn.commit() # ✅ 추가: 트랜잭션 완료

                if self.message:
                    embed = discord.Embed(
                        title="💤 방치투기 발생",
                        description=(
                            f"쓰레기 **[{self.value_name}]**이(가) 방치되어 강물로 떠내려갔습니다.\n"
                            f"☣️ **오염도 상승:** `+{added_pollution:.2f} P` (현재: {new_pollution:.1f} P)"
                            f"{fine_msg}"
                            f"{ban_msg}"
                        ),
                        color=discord.Color.red()
                    )
                    await self.message.edit(embed=embed, view=None)
            except Exception as e:
                print(f"[방치투기 처리 오류] {e}")

        self._clear_session()

    def _clear_session(self):
        uid_int = int(self.user_id)
        active_sessions.pop(uid_int, None)
        user_locks.pop(uid_int, None)

    @discord.ui.button(label="🧹 쓰레기 치우기", style=discord.ButtonStyle.success)
    async def clean(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id: return await interaction.response.send_message("본인만 가능!", ephemeral=True)
        if self.responded: return
        self.responded = True

        uid, gid = self.user_id, str(interaction.guild_id)
        penalty = abs(self.value)
        current_cash = self.db.get_user_cash(uid) or 0
        if current_cash < penalty:
            self.responded = False
            return await interaction.response.send_message("❌ 현금 부족!", ephemeral=True)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (penalty, uid, gid))
            conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                         (uid, "낚시", -penalty, current_cash - penalty, "낚시 환경 정화 비용"))
            conn.commit()
            await interaction.response.edit_message(embed=discord.Embed(title="✅ 정화 완료", description=f"**{penalty:,}원**을 지출했습니다.", color=discord.Color.green()), view=None)
        except:
            conn.rollback()
            self.responded = False
            await interaction.response.send_message("❌ 처리 중 오류 발생!", ephemeral=True)
        finally: self._clear_session()

    @discord.ui.button(label="🗑️ 그냥 버리기", style=discord.ButtonStyle.grey)
    async def dump(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.user_id:
            return await interaction.response.send_message("자신의 쓰레기만 처리할 수 있습니다!", ephemeral=True)

        # 1. 실제 데이터베이스 오염도 수치 증가 (핵심 로직)
        self.db.execute_query(
            "UPDATE fishing_ground SET pollution = pollution + 1 WHERE channel_id = ? AND guild_id = ?",
            (str(interaction.channel_id), str(interaction.guild_id))
        )

        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        uid = self.user_id
        
        current_data = self.db.execute_query(
            "SELECT pollution, owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid), 'one'
        )
        current_pollution = current_data['pollution'] if current_data else 0
        owner_id = current_data['owner_id'] if current_data else None

        added_pollution = 0.5 + (current_pollution * 0.1)
        
        # ✅ 공영 낚시터(소유주 없음)는 최대 50, 사유지는 최대 100 제한
        pollution_cap = 50.0 if owner_id is None else 100.0
        new_pollution = min(pollution_cap, current_pollution + added_pollution)

        conn = self.db.get_connection()
        fine_msg = ""
        ban_msg = ""

        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET illegal_dump_count = illegal_dump_count + 1 WHERE user_id = ? AND guild_id = ?", (uid, gid))
            
            user_data = self.db.execute_query("SELECT illegal_dump_count, cash, max_dump_rate FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            user_count = user_data['illegal_dump_count'] if user_data else 0
            current_cash = user_data['cash'] if user_data else 0
            max_dump_rate = user_data['max_dump_rate'] if user_data else 0.0

            # 📈 최대 투기 비율 경신 체크
            if self.rate > max_dump_rate:
                max_dump_rate = self.rate
                conn.execute("UPDATE users SET max_dump_rate = ? WHERE user_id = ? AND guild_id = ?", (max_dump_rate, uid, gid))

            # 🚨 [벌금 로직 변경] 10회 이상이며 10의 배수일 때 부과
            trigger_fine = (user_count >= 10 and user_count % 10 == 0)

            if trigger_fine:
                # 💰 벌금율: 역대 최대 비율 * 2.0
                fine_rate = max_dump_rate * 2.0
                calculated_fine = max(5000, int(current_cash * fine_rate))

                if current_cash < 50000:
                    debt_fine = 50000 
                    conn.execute("UPDATE users SET fine_debt = fine_debt + ? WHERE user_id = ? AND guild_id = ?", (debt_fine, uid, gid))
                    
                    # ✅ [메시지 수정] 실제 수치에 맞게 안내 메시지 통일
                    fine_msg = f"\n\n🚨 **[무단투기 과태료 빚 적립]**\n무단투기가 누적 **{user_count}회** 적발되었습니다.\n소지금 부족으로 차후 정산 시 `{debt_fine:,}원`이 자동 차감됩니다!"
                else:
                    conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (calculated_fine, uid, gid))
                    conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                                (uid, "과태료", -calculated_fine, current_cash - calculated_fine, f"무단투기 누적 {user_count}회 적발 과태료"))
                    fine_msg = f"\n\n🚨 **[무단투기 과태료 부과!]**\n무단투기가 누적 **{user_count}회** 적발되었습니다.\n과태료 **{calculated_fine:,}원**(배율 {fine_rate:.2f})이 즉시 징수되었습니다!"
            
            # 🚫 10회당 10분 이용 제한 추가
            if user_count % 10 == 0:
                ban_until = (datetime.now() + timedelta(minutes=10)).strftime('%Y-%m-%d %H:%M:%S')
                conn.execute("UPDATE users SET fishing_ban_until = ? WHERE user_id = ? AND guild_id = ?", (ban_until, uid, gid))
                ban_msg = f"\n\n🚫 **[낚시터 이용 제한]**\n무단투기 누적 **{user_count}회** 기록으로 인해 향후 **10분간** 낚시터 이용이 금지됩니다."

            # ✅ [위치 수정] 조건문과 상관없이 트랜잭션을 끝내기 위해 바깥으로 이동
            conn.commit()

            
            # 2. 전송할 임베드 메시지 구성
            embed = discord.Embed(
                title="⚠️ 무단투기 완료", 
                description=f"우... 쓰레기...\n를 그냥 바닥에 버렸습니다.\n당신의 양심도 낚시터도 **오염도가 상승**합니다\n**오염도 상승:** `+{added_pollution:.2f} P` (현재: {new_pollution:.1f} P){fine_msg}{ban_msg}",
                color=discord.Color.red()
            )

            # 3. 화면 업데이트 (한 번만 호출)
            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            conn.rollback()
            print(f"[경고] 수동 무단투기 벌금 처리 오류: {e}")
            await interaction.response.send_message("❌ 데이터 처리 중 오류 발생!", ephemeral=True)
        finally:
            self._clear_session()

# 🏗️ [낚시터 공개/비공개 설정용 버튼 UI 뷰]
class PublicSettingView(discord.ui.View):
    def __init__(self, user: discord.Member, db_manager: DatabaseManager):
        super().__init__(timeout=60.0)
        self.user = user
        self.db = db_manager
        self.message = None

    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(view=None)
            except: pass

    @discord.ui.button(label="🔓 공개로 변경", style=discord.ButtonStyle.success)
    async def set_public(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 소유자만 변경할 수 있습니다.", ephemeral=True)
        
        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        self.db.execute_query("UPDATE fishing_ground SET is_public = 1 WHERE channel_id = ? AND guild_id = ?", (chid, gid))
        
        embed = discord.Embed(title="✅ 설정 완료", description="이 낚시터가 **[🔓 공개]** 상태로 변경되었습니다!\n누구나 무료로 낚시할 수 있습니다.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="🔒 비공개로 변경", style=discord.ButtonStyle.danger)
    async def set_private(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 소유자만 변경할 수 있습니다.", ephemeral=True)

        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        self.db.execute_query("UPDATE fishing_ground SET is_public = 0 WHERE channel_id = ? AND guild_id = ?", (chid, gid))
        
        embed = discord.Embed(title="✅ 설정 완료", description="이 낚시터가 **[🔒 비공개]** 상태로 변경되었습니다!\n다른 유저는 입장권을 구매해야 합니다.", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# 🔼 [낚시터 티어 업그레이드 최종 확인 UI 뷰]
class TierUpgradeConfirmView(discord.ui.View):
    def __init__(self, user: discord.Member, req_rep: int, current_tier: int, chid: str, gid: str, db_manager):
        super().__init__(timeout=60.0)
        self.user = user
        self.req_rep = req_rep
        self.current_tier = current_tier
        self.chid = chid
        self.gid = gid
        self.db = db_manager
        self.message = None
        self.responded = False

    async def on_timeout(self):
        if self.message and not self.responded:
            try:
                await self.message.edit(embed=discord.Embed(title="⌛ 시간 초과", description="티어 업그레이드 요청이 취소되었습니다.", color=discord.Color.light_gray()), view=None)
            except: pass

    @discord.ui.button(label="✅ 최종 승인", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 명령어를 입력한 땅 주인만 누를 수 있습니다.", ephemeral=True)
        
        if self.responded: return
        self.responded = True

        # 최신 명성 데이터 재검증
        ground = self.db.execute_query("SELECT ground_reputation FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid), 'one')
        current_rep = ground['ground_reputation'] if ground else 0

        if current_rep < self.req_rep:
            return await interaction.response.edit_message(embed=discord.Embed(title="❌ 업그레이드 실패", description="결제하려는 순간 낚시터 명성이 부족해졌습니다!", color=discord.Color.red()), view=None)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE fishing_ground SET tier = tier + 1, ground_reputation = ground_reputation - ? WHERE channel_id = ? AND guild_id = ?", (self.req_rep, self.chid, self.gid))
            conn.commit()

            embed = discord.Embed(
                title="🎉 낚시터 등급 상승 완료!", 
                description=f"<#{self.chid}> 채널이 **{self.current_tier + 1}티어**가 되었습니다!", 
                color=discord.Color.green()
            )
            embed.add_field(name="📉 소모 명성", value=f"`-{self.req_rep:,} P`", inline=True)
            embed.add_field(name="📈 남은 명성", value=f"`{current_rep - self.req_rep:,} P`", inline=True)
            embed.set_footer(text="티어가 오를수록 더 가치 있고 희귀한 물고기가 잡힙니다.")

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            conn.rollback()
            await interaction.response.edit_message(embed=discord.Embed(title="❌ 에러 발생", description=f"티어 상승 중 오류: {e}", color=discord.Color.red()), view=None)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 명령어를 입력한 땅 주인만 누를 수 있습니다.", ephemeral=True)
        
        self.responded = True
        await interaction.response.edit_message(embed=discord.Embed(title="⏹️ 요청 취소", description="티어 업그레이드를 취소했습니다. 명성이 소모되지 않았습니다.", color=discord.Color.light_gray()), view=None)
        self.stop()

# 🏗️ [관리자용 낚시터 유형 지정 버튼 UI 뷰]
class AdminGroundTypeView(discord.ui.View):
    def __init__(self, admin: discord.Member, db_manager: DatabaseManager):
        super().__init__(timeout=60.0)
        self.admin = admin
        self.db = db_manager
        self.message = None

    async def on_timeout(self):
        if self.message:
            try: await self.message.edit(view=None)
            except: pass

    @discord.ui.button(label="🔓 공용", style=discord.ButtonStyle.success)
    async def set_public(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)

        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        
        # 공용화 규칙: purchasable=0(구매불가), is_public=1(공개), 소유주 추방(NULL)
        self.db.execute_query(
            "UPDATE fishing_ground SET purchasable = 0, is_public = 1, owner_id = NULL WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid)
        )
        
        embed = discord.Embed(
            title="✅ [공용] 지정 완료", 
            description="이 채널이 **공용 낚시터**로 지정되었습니다!\n누구나 무료로 이용할 수 있으며, 개인이 구매할 수 없습니다.", 
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()
    
    @discord.ui.button(label="🛒 개인", style=discord.ButtonStyle.primary)
    async def set_purchasable(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("❌ 관리자 권한이 필요합니다.", ephemeral=True)

        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        
        # 개인용 규칙: purchasable=1(구매가능), 사기 전까진 비공개(is_public=0)
        self.db.execute_query(
            "UPDATE fishing_ground SET purchasable = 1, is_public = 0 WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid)
        )
        
        embed = discord.Embed(
            title="✅ [개인] 활성화 완료", 
            description="이 채널이 **개인 구매용 낚시터**로 활성화되었습니다!\n유저들이 돈을 모아 땅을 구매할 수 있습니다.", 
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

    @discord.ui.button(label="❌ 불가(취소)", style=discord.ButtonStyle.secondary)
    async def cancel_action(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.admin:
            return await interaction.response.send_message("❌ 명령어를 발동한 관리자만 취소할 수 있습니다.", ephemeral=True)

        embed = discord.Embed(
            title="⏹️ 설정 취소", 
            description="낚시터 유형 설정을 취소했습니다. 아무런 데이터도 변경되지 않았습니다.", 
            color=discord.Color.light_gray()
        )
        await interaction.response.edit_message(embed=embed, view=None)
        self.stop()

# 🧹 [쓰레기 청소 최종 확인 UI 뷰]
class CleanConfirmView(discord.ui.View):
    def __init__(self, user: discord.Member, cost: int, reduce_amount: float, chid: str, gid: str, db_manager):
        super().__init__(timeout=60.0)
        self.user = user
        self.cost = cost
        self.reduce_amount = reduce_amount
        self.chid = chid
        self.gid = gid
        self.db = db_manager
        self.message = None
        self.responded = False

    async def on_timeout(self):
        if self.message and not self.responded:
            try:
                await self.message.edit(embed=discord.Embed(title="⌛ 시간 초과", description="청소 요청이 취소되었습니다.", color=discord.Color.light_gray()), view=None)
            except: pass

    @discord.ui.button(label="✅ 최종 청소", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 명령어를 입력한 유저만 누를 수 있습니다.", ephemeral=True)
        
        if self.responded: return
        self.responded = True

        # 소지금 재검증
        user_cash = self.db.get_user_cash(str(self.user.id)) or 0
        if user_cash < self.cost:
            return await interaction.response.edit_message(embed=discord.Embed(title="❌ 청소 실패", description="결제하려는 순간 소지금이 부족해졌습니다!", color=discord.Color.red()), view=None)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            
            # 1. 돈 차감
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (self.cost, str(self.user.id), self.gid))
            
            # 2. 낚시터 오염도 차감 (음수가 되지 않도록 MAX 처리)
            conn.execute("UPDATE fishing_ground SET pollution = MAX(0, pollution - ?) WHERE channel_id = ? AND guild_id = ?", (self.reduce_amount, self.chid, self.gid))
            
            # 3. 로그 기록
            conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                         (str(self.user.id), "낚시", -self.cost, user_cash - self.cost, f"낚시터 채널 오염도 {self.reduce_amount} 정화 비용 지출"))
            
            conn.commit()

            # 오염도 정산 후 최종 조회
            ground = self.db.execute_query("SELECT pollution FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid), 'one')
            after_pollution = ground['pollution'] if ground else 0

            embed = discord.Embed(
                title="🌊 낚시터 환경 정화 완료", 
                description=f"<#{self.chid}> 낚시터 채널이 반짝반짝 깨끗해졌습니다!", 
                color=discord.Color.blue()
            )
            embed.add_field(name="📉 소모 비용", value=f"`{self.cost:,}원`", inline=True)
            embed.add_field(name="🚨 현재 오염도", value=f"**`{after_pollution:.1f} P`**", inline=True)
            embed.set_footer(text="깨끗한 낚시터는 물고기 획득률이 오르고 쓰레기 획득률이 내려갑니다.")

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            conn.rollback()
            await interaction.response.edit_message(embed=discord.Embed(title="❌ 에러 발생", description=f"정화 처리 중 오류: {e}", color=discord.Color.red()), view=None)


    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("❌ 명령어를 입력한 유저만 누를 수 있습니다.", ephemeral=True)
        
        self.responded = True
        await interaction.response.edit_message(embed=discord.Embed(title="⏹️ 청소 취소", description="청소 요청을 취소했습니다. 돈이 차감되지 않았습니다.", color=discord.Color.light_gray()), view=None)
        self.stop()

# ⚠️ [서버 데이터 초기화 확인 UI 뷰]
class ResetConfirmView(discord.ui.View):
    def __init__(self, admin: discord.Member, db_manager):
        super().__init__(timeout=30)
        self.admin = admin
        self.db = db_manager
        self.responded = False

    @discord.ui.button(label="⚠️ 서버 데이터 전체 초기화 (복구 불가)", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.admin:
            return await interaction.response.send_message("❌ 명령어를 실행한 관리자만 누를 수 있습니다.", ephemeral=True)
        
        if self.responded: return
        self.responded = True
        
        gid = str(interaction.guild_id)
        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            # 1. 낚시터 정보 초기화 (모든 채널 초기화)
            conn.execute(
                "UPDATE fishing_ground SET owner_id = NULL, tier = 1, ground_reputation = 0, pollution = 0, is_public = 1, entry_fee = 0, purchasable = 1 WHERE guild_id = ?", 
                (gid,)
            )
            # 2. 모든 유저 장비 삭제
            conn.execute("DELETE FROM fishing_gear WHERE guild_id = ?", (gid,))
            # 3. 모든 유저 인벤토리 삭제
            conn.execute("DELETE FROM fishing_inventory WHERE guild_id = ?", (gid,))
            # 4. 모든 입장권 삭제
            conn.execute("DELETE FROM fishing_passes WHERE guild_id = ?", (gid,))
            # 5. 모든 시설 삭제
            conn.execute("DELETE FROM fishing_facilities WHERE guild_id = ?", (gid,))
            # 6. 유저의 낚시 통계 및 명성 초기화
            conn.execute(
                "UPDATE users SET fishing_reputation = 0, max_fish_length = 0.0, illegal_dump_count = 0, neglect_dump_count = 0, fine_debt = 0, fishing_ban_until = NULL WHERE guild_id = ?", 
                (gid,)
            )
            # 7. 낚시 로그 삭제
            try: conn.execute("DELETE FROM fishing_logs WHERE guild_id = ?", (gid,))
            except: pass
            
            conn.commit()
            
            # 실시간 메모리 세션 클리어 (현재 서버의 모든 유저 대상)
            uids = list(active_sessions.keys())
            for u_id in uids:
                session = active_sessions.get(u_id)
                if hasattr(session, 'interaction') and str(session.interaction.guild_id) == gid:
                    active_sessions.pop(u_id, None)
                    user_locks.pop(u_id, None)

            await interaction.response.edit_message(content="✅ **서버의 모든 낚시 데이터가 성공적으로 초기화되었습니다.**", embed=None, view=None)
        except Exception as e:
            conn.rollback()
            await interaction.response.edit_message(content=f"❌ 초기화 중 오류 발생: {e}", embed=None, view=None)

    @discord.ui.button(label="취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.responded = True
        await interaction.response.edit_message(content="⏹️ 초기화 요청이 취소되었습니다.", embed=None, view=None)
        self.stop()

class BuyConfirmView(discord.ui.View):
    def __init__(self, db, price, chid, gid, buyer_id):
        super().__init__(timeout=30)
        self.db = db
        self.price = price
        self.chid = chid
        self.gid = gid
        self.buyer_id = buyer_id
        self.responded = False

    @discord.ui.button(label="✅ 최종 매입 승인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.buyer_id:
            return await interaction.response.send_message("구매 당사자만 결정할 수 있습니다.", ephemeral=True)
        
        if self.responded: return
        self.responded = True

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            
            # 1. 낚시터 상태 재검증
            ground = conn.execute("SELECT owner_id, purchasable FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid)).fetchone()
            if not ground:
                conn.rollback()
                return await interaction.response.edit_message(content="❌ 오류: 존재하지 않는 낚시터 정보입니다.", embed=None, view=None)
            
            # 본인 소유 체크
            if ground['owner_id'] == self.buyer_id:
                conn.rollback()
                return await interaction.response.edit_message(content="❌ 매입 실패: 이미 본인이 소유하고 있는 땅입니다!", embed=None, view=None)

            # 공용 낚시터 여부 체크
            if ground['owner_id'] is None and ground['purchasable'] != 1:
                conn.rollback()
                return await interaction.response.edit_message(content="❌ 매입 실패: 이 채널은 공용 낚시터로 지정되어 매입할 수 없습니다.", embed=None, view=None)

            is_takeover = ground['owner_id'] is not None
            old_owner_id = ground['owner_id']

            # 2. 사용자 잔액 재검증
            user = conn.execute("SELECT cash FROM users WHERE user_id = ? AND guild_id = ?", (self.buyer_id, self.gid)).fetchone()
            current_cash = user['cash'] if user else 0
            
            if current_cash < self.price:
                conn.rollback()
                return await interaction.response.edit_message(content=f"❌ 매입 실패: 잔액이 부족합니다! (필요: {self.price:,}원 / 보유: {current_cash:,}원)", embed=None, view=None)

            # 3. 실제 매입 처리
            # 구매자 돈 차감
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (self.price, self.buyer_id, self.gid))
            
            if is_takeover:
                # 📉 [약탈 로직] 전 주인에게 80% 환불 처리
                refund_amount = int(self.price * 0.8)
                conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (refund_amount, old_owner_id, self.gid))
                
                # 전 주인 시설물 철거
                conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid))
                
                # 명성 및 티어 초기화 (약탈당한 땅은 황폐화됨)
                conn.execute("UPDATE fishing_ground SET tier = 1, ground_reputation = 0 WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid))

                log_desc = f"낚시터 채널({self.chid}) 약탈(매입) 지출"
                old_owner_log = f"낚시터 채널({self.chid}) 약탈당함 (환불: {refund_amount:,}원)"
                
                # 전 주인 로그 기록
                conn.execute(
                    "INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) "
                    "SELECT ?, ?, ?, cash, ? FROM users WHERE user_id = ? AND guild_id = ?",
                    (old_owner_id, "낚시터강제매각", refund_amount, old_owner_log, old_owner_id, self.gid)
                )
            else:
                log_desc = f"낚시터 채널({self.chid}) 매입 지출"

            # 낚시터 정보 업데이트 (소유권 이전 및 비공개 처리)
            conn.execute(
                "UPDATE fishing_ground SET owner_id = ?, purchasable = 0, is_public = 0, last_activity = CURRENT_TIMESTAMP "
                "WHERE channel_id = ? AND guild_id = ?", 
                (self.buyer_id, self.chid, self.gid)
            )
            
            # 구매자 로그 기록
            conn.execute(
                "INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                (self.buyer_id, "낚시터매입", -self.price, current_cash - self.price, log_desc)
            )
            
            conn.commit()
            
            title = "⚔️ 낚시터 약탈 성공!" if is_takeover else "🎊 낚시터 매입 성공!"
            takeover_msg = f"\n⚠️ 기존 주인의 시설물은 철거되었으며, 땅의 등급과 명성이 초기화되었습니다." if is_takeover else ""

            embed = discord.Embed(
                title=title,
                description=(
                    f"성공적으로 <#{self.chid}> 채널을 소유하게 되었습니다!\n\n"
                    f"💰 **지출 금액:** `{self.price:,}원`\n"
                    f"🔒 **현재 상태:** `비공개 (입장권 필요)`"
                    f"{takeover_msg}\n\n"
                    f"💡 `/낚시터 액션: 설정 변경`을 통해 입장료와 공개 여부를 관리할 수 있습니다."
                ),
                color=discord.Color.green() if not is_takeover else discord.Color.red()
            )
            await interaction.response.edit_message(content=None, embed=embed, view=None)

        except Exception as e:
            try: conn.rollback()
            except: pass
            print(f"[매입 오류] {e}")
            await interaction.response.edit_message(content=f"❌ 시스템 오류로 인해 매입에 실패했습니다. (에러: {e})", embed=None, view=None)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.buyer_id:
            return await interaction.response.send_message("본인만 취소할 수 있습니다.", ephemeral=True)
        
        self.responded = True
        await interaction.response.edit_message(content="⏹️ 매입을 취소했습니다.", embed=None, view=None)

class SellConfirmView(discord.ui.View):
    def __init__(self, db, refund_price, chid, gid, owner_id):
        super().__init__(timeout=30)
        self.db = db
        self.refund_price = refund_price
        self.chid = chid
        self.gid = gid
        self.owner_id = owner_id
        self.responded = False

    @discord.ui.button(label="✅ 최종 매각 승인", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            return await interaction.response.send_message("소유자만 매각을 결정할 수 있습니다.", ephemeral=True)
        
        if self.responded: return
        self.responded = True

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            
            # 낚시터 정보 및 소유권 재검증
            ground = conn.execute("SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid)).fetchone()
            if not ground or ground['owner_id'] != self.owner_id:
                conn.rollback()
                return await interaction.response.edit_message(content="❌ 오류: 낚시터 소유주가 아니거나 정보가 유효하지 않습니다.", embed=None, view=None)

            # 1. 사용자에게 환불금 지급
            conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (self.refund_price, self.owner_id, self.gid))
            
            # 2. 낚시터 정보 초기화
            conn.execute(
                "UPDATE fishing_ground SET owner_id = NULL, purchasable = 1, is_public = 1, "
                "entry_fee = 0, ground_reputation = 0, tier = 1 "
                "WHERE channel_id = ? AND guild_id = ?", 
                (self.chid, self.gid)
            )
            
            # 3. 시설 철거
            conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (self.chid, self.gid))

            # 4. 로그 기록
            conn.execute(
                "INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) "
                "SELECT ?, ?, ?, cash, ? FROM users WHERE user_id = ? AND guild_id = ?",
                (self.owner_id, "낚시터매각", self.refund_price, f"낚시터 채널({self.chid}) 매각 환불", self.owner_id, self.gid)
            )
            
            conn.commit()
            
            embed = discord.Embed(
                title="🏢 낚시터 매각 완료",
                description=(
                    f"<#{self.chid}> 채널의 소유권을 포기하고 매각을 완료했습니다.\n\n"
                    f"💰 **환불 금액:** `{self.refund_price:,}원` (매입가 및 시설 가치 반영)\n"
                    f"🔓 **현재 상태:** `공개 (구매 가능)`\n\n"
                    f"시설물은 모두 철거되었으며, 기본 명성치와 티어가 초기화되었습니다."
                ),
                color=discord.Color.blue()
            )
            await interaction.response.edit_message(content=None, embed=embed, view=None)

        except Exception as e:
            try: conn.rollback()
            except: pass
            print(f"[매각 오류] {e}")
            await interaction.response.edit_message(content=f"❌ 시스템 오류로 인해 매각에 실패했습니다. (에러: {e})", embed=None, view=None)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != self.owner_id:
            return await interaction.response.send_message("본인만 취소할 수 있습니다.", ephemeral=True)
        
        self.responded = True
        await interaction.response.edit_message(content="⏹️ 매각을 취소했습니다.", embed=None, view=None)

class FishingGameView(discord.ui.View):
    def __init__(self, interaction, db, cog): # cog 인자 추가
        super().__init__(timeout=60)
        self.interaction = interaction
        self.db = db
        self.cog = cog  # 세션 관리를 위해 cog 저장
        self.user = interaction.user
        self.channel_id = interaction.channel_id # 추가
        self.is_pulled = False
        self.responded = False
        self.stage = "waiting"
        self.is_real = False

    async def on_timeout(self):
        self._clear_session()
        if self.message and not self.responded:
            try:
                for child in self.children: child.disabled = True
                await self.message.edit(embed=discord.Embed(title="⌛ 시간 초과", description="낚시가 자동으로 중단되었습니다.", color=discord.Color.default()), view=self)
            except: pass

    def _clear_session(self):
        active_sessions.pop(self.user.id, None)
        user_locks.pop(self.user.id, None)

    async def start_game(self, interaction: discord.Interaction):
        uid, gid = str(self.user.id), str(interaction.guild_id)
        gear = self.db.execute_query("SELECT bait_count, rod_durability FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
        
        if not gear or gear['bait_count'] <= 0:
            self._clear_session()
            return await interaction.response.send_message("❌ 미끼가 없습니다!", ephemeral=True)
        if gear['rod_durability'] <= 0:
            self._clear_session()
            return await interaction.response.send_message("❌ 낚싯대가 부러졌습니다!", ephemeral=True)

        self.db.execute_query("UPDATE fishing_gear SET bait_count = bait_count - 1 WHERE user_id = ? AND guild_id = ?", (uid, gid))
        
        await interaction.response.send_message(embed=discord.Embed(title="🎣 낚시 시작!", description="찌를 던졌습니다. 물고기를 기다리는 중...", color=discord.Color.green()), view=self)
        self.message = await interaction.original_response()

        await asyncio.sleep(random.uniform(1.5, 2.5))
        if self.responded: return
        try: await interaction.edit_original_response(embed=discord.Embed(title="🌬️ 찌가 살짝 살랑거립니다...", color=discord.Color.light_gray()))
        except: return

        await asyncio.sleep(random.uniform(1.5, 2.5))
        if self.responded: return
        
        if random.random() < 0.25: # 가짜 입질
            self.stage = "fake"
            try: await interaction.edit_original_response(embed=discord.Embed(title=f"❓ {random.choice(TRAPS)}", color=discord.Color.orange()))
            except: return
            await asyncio.sleep(1.5)
            if self.responded: return
            self.stage = "waiting"
            try: await interaction.edit_original_response(embed=discord.Embed(title="...낚시터가 다시 조용해졌습니다.", color=discord.Color.light_gray()))
            except: return
            await asyncio.sleep(random.uniform(1.5, 2.5))
            if self.responded: return

        self.stage, self.is_real = "bite", True

        # 🎰 아래의 리스트 중 하나가 무작위로 선택됩니다. 원하시는 멘트를 더 추가하셔도 됩니다!
        random_descriptions = [
            "**지금이야! 빨리 당겨!!**",
            "**어엇!! 팽팽하게 당겨진다!!**",
            "**엄청난 무게감이다! 놓치지 마!!**",
            "**왔다! 손맛이 느껴진다!!**",
            "**찌가 완전히 시야에서 사라졌다!!**"
        ]

        try: 
            await interaction.edit_original_response(
                embed=discord.Embed(
                    title=f"🚨 {random.choice(REAL_BITES)}", 
                    description=random.choice(random_descriptions), # 👈 랜덤 텍스트 적용!
                    color=discord.Color.red()
                )
            )
        except: 
            return
        
    async def resolve_fishing(self, interaction: discord.Interaction):
        if self.responded: return
        self.responded = True

        # [A] 24시간 이용 횟수에 따른 '이득' 계산 (0.5씩)
        benefit = await get_usage_benefit(self.user.id, interaction.guild_id, self.db)
        
        # 기본 수수료 500원에 활성화 보너스 합산
        owner_profit = 500 + benefit 
        
        # [B] 이번 이용 기록 저장 (이게 있어야 다음 사람이 낚시할 때 횟수에 포함됨)
        log_query = "INSERT INTO fishing_logs (user_id, guild_id, timestamp) VALUES (?, ?, ?)"
        self.db.execute_query(
            log_query, 
            (str(self.user.id), str(interaction.guild_id), datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
        )

        # [C] 낚시터 주인에게 수익금 실제로 지급 (DB 업데이트)
        # 낚시터 정보에서 주인 ID(owner_id)를 가져와 해당 유저의 돈을 늘려줍니다.
        update_profit_query = """
            UPDATE users 
            SET cash = cash + ? 
            WHERE user_id = (SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?)
        """
        self.db.execute_query(update_profit_query, (owner_profit, str(interaction.channel_id), str(interaction.guild_id)))

        # [D] 결과 메시지 출력
        embed = discord.Embed(
            title="🎣 낚시 완료!",
            description=(
                f"성공적으로 낚시를 마쳤습니다!\n\n"
                f"💰 **낚시터 수익 발생**: `{owner_profit:,.1f}`원\n"
                f"✨ **활성화 보너스**: `+{benefit:,.1f}`원 (최근 24시간 기준)"
            ),
            color=discord.Color.green()
        )
        
        await interaction.edit_original_response(embed=embed, view=None)

    @discord.ui.button(label="🎣 낚싯줄 당기기", style=discord.ButtonStyle.danger)
    async def pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        gid = str(interaction.guild.id)
        chid = str(interaction.channel.id)

        # 🛑 [하드코어 소급 적용] 필수 건축물 실시간 검증 시스템 --------------------------
        db = self.db
        ground = db.execute_query(
            "SELECT tier FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid), 'one'
        )
        
        if ground:
            current_tier = ground['tier']
            
            # 현재 땅에 지어진 시설 목록 조회
            facilities = db.execute_query(
                "SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", 
                (chid, gid), 'all'
            )
            built_names = [f['facility_name'] for f in facilities] if facilities else []

            # 🚨 각 티어별 필수 시설 누락 검증 (하향 검증 포함)
            missing_facility = None
            
            if current_tier >= 2 and ("매표소" not in built_names and "창고" not in built_names):
                missing_facility = "[매표소] 또는 [창고]"
            elif current_tier >= 3 and "중형창고" not in built_names:
                missing_facility = "[중형창고]"
            elif current_tier >= 4 and "화력발전소" not in built_names:
                missing_facility = "[화력발전소]"
            elif current_tier >= 5 and ("세계1위기업" not in built_names and "환경부" not in built_names):
                missing_facility = "[세계1위기업] 또는 [환경부]"

            # 필수 시설이 누락되었다면 낚시 차단
            if missing_facility:
                embed = discord.Embed(
                    title="⚠️ 불법 사유지 시설 규제 적발",
                    description=(
                        f"현재 이 낚시터는 **Lv.{current_tier}** 등급이지만, 등급 유지에 필요한 필수 기반 시설이 누락되었습니다.\n\n"
                        f"🚫 **낚시가 일시적으로 차단됩니다.**\n"
                        f"🔧 **필요한 건축물:** {missing_facility}\n\n"
                        f"*사유지 소유자는 시설을 먼저 건설해야 낚시터를 다시 가동할 수 있습니다.*"
                    ),
                    color=discord.Color.red()
                )
                self._clear_session() # 🚨 [추가] 낚시를 반려할 때 메모리 세션(중복 낚시 잠금)을 풀어줍니다.
                return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        if interaction.user != self.user: 
            return await interaction.response.send_message("본인만 조작할 수 있습니다.", ephemeral=True)
        
        if self.user.id not in user_locks: 
            user_locks[self.user.id] = asyncio.Lock()
        
        async with user_locks[self.user.id]:
            if self.responded: return
            self.responded = True
            await interaction.response.defer()
            self.stop()

            if self.stage != "bite":
                title = "❌ 실패!" if self.stage != "fake" else "💢 허탕!"
                desc = "가짜 입질이었습니다!" if self.stage == "fake" else "아직 입질이 오지 않았거나 타이밍을 놓쳤습니다."
                await interaction.edit_original_response(embed=discord.Embed(title=title, description=desc, color=discord.Color.default()), view=None)
                self._clear_session()
                return

            uid, gid = str(self.user.id), str(interaction.guild_id)
            conn = self.db.get_connection()
            
            try:
                # 🔓 트랜잭션 시작
                conn.execute("BEGIN")
                conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - 1) WHERE user_id = ? AND guild_id = ?", (uid, gid))

                ground = self.db.execute_query("SELECT ground_type, tier, pollution FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
                location = ground['ground_type'] if ground else "호수"
                current_ground_tier = ground['tier'] if ground else 1
                current_pollution = ground['pollution'] if ground else 0

                built_facilities = self.db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')

                trash_chance = 0.25 + (current_pollution / 100.0)
                if current_pollution >= 100.0:
                    trash_chance = 0.9999
                else:
                    # 오염도가 100 미만일 때는 기존 오염도 비례 공식을 사용합니다.
                    trash_chance = 0.25 + (current_pollution * 0.007499) 

                # 시설 효과가 있다면 마저 계산해 줍니다.
                if built_facilities:
                    for f in built_facilities:
                        f_name = f['facility_name']
                        if f_name in FACILITIES:
                            trash_mod = FACILITIES[f_name].get("effect", {}).get("trash_rate", 0)
                            trash_chance += trash_mod

                # 쓰레기 확률 상한선을 0.9999 (99.99%)로 설정합니다!
                trash_chance = max(0.0, min(0.9999, trash_chance))

                # 🗑️ 쓰레기 기믹 부분
                if random.random() < trash_chance:
                    # ⚖️ [티어별 그룹 가중치 계산]
                    all_groups = range(1, 7)
                    g_items = {i: [t for t in TRASH_LIST if t["group"] == i] for i in all_groups}
                    
                    # 5%는 무조건 ??? (Group 6)
                    target_weights = {6: 0.05}
                    
                    if current_ground_tier == 1:
                        target_weights[1] = 0.80
                        others_weight = 0.15
                    elif current_ground_tier == 2:
                        target_weights[2] = 0.70
                        others_weight = 0.25
                    elif current_ground_tier == 3:
                        target_weights[3] = 0.60
                        others_weight = 0.35
                    elif current_ground_tier == 4:
                        target_weights[4] = 0.50
                        others_weight = 0.45
                    elif current_ground_tier == 5:
                        target_weights[5] = 0.50
                        others_weight = 0.45
                    else: # 6티어 이상 예외 처리
                        target_weights[5] = 0.50
                        others_weight = 0.45
                    
                    # 나머지 그룹들에 others_weight를 균등 배분 (현재 티어 그룹 및 Group 6 제외)
                    other_groups = [i for i in range(1, 6) if i != current_ground_tier]
                    if other_groups:
                        per_group_weight = others_weight / len(other_groups)
                        for og in other_groups:
                            target_weights[og] = per_group_weight

                    trash_weights = []
                    for t in TRASH_LIST:
                        grp = t["group"]
                        grp_total_weight = target_weights.get(grp, 0)
                        items_in_grp = len(g_items[grp])
                        trash_weights.append(grp_total_weight / items_in_grp if items_in_grp > 0 else 0)

                    trash = random.choices(TRASH_LIST, weights=trash_weights, k=1)[0]

                    # 💰 소지금 기반 퍼센트 비용 계산
                    current_cash = self.db.get_user_cash(uid) or 0
                    rate = random.uniform(trash["min_rate"], trash["max_rate"])
                    
                    # 📈 [티어별 벌금 인상 로직 세분화]
                    if trash["group"] == 1 and current_ground_tier >= 2:
                        # Group 1: 2티어부터 3%씩 인상
                        rate += (current_ground_tier - 1) * 0.03
                    elif trash["group"] == 2 and current_ground_tier >= 3:
                        # Group 2: 3티어부터 3%씩 인상
                        rate += (current_ground_tier - 2) * 0.03
                    elif trash["group"] == 3 and current_ground_tier >= 4:
                        # Group 3: 4티어부터 4%씩 인상
                        rate += (current_ground_tier - 3) * 0.04
                    elif trash["group"] == 4 and current_ground_tier >= 5:
                        # Group 4: 5티어부터 5%씩 인상
                        rate += (current_ground_tier - 4) * 0.05
                    
                    # 계산된 금액이 1,000원보다 적으면 최소 1,000원 부과
                    calculated_fine = int(current_cash * rate)
                    actual_fine = -max(1000, calculated_fine) 
            
                    # 🚨 [인자 7개 채우기] 에러 해결 및 rate 전달
                    view = TrashActionView(
                        self.db, 
                        str(self.user.id), 
                        str(interaction.guild_id), 
                        str(interaction.channel_id), 
                        trash['name'], 
                        actual_fine,
                        rate
                    )
            
                    # 세션 등록 (self.cog를 통해 부모 Cog의 딕셔너리에 접근)
                    self.cog.active_trash_sessions[str(self.user.id)] = view

                    embed = discord.Embed(
                        title="🚮 쓰레기가 걸려왔습니다!", 
                        description=(
                            f"**[{trash['name']}]**\n\n"
                            f"⚠️ **주의:** 수거 시 처리비가 청구됩니다.\n"
                            f"💸 **방치 시 오염도가 대폭 상승합니다.**"
                        ), 
                        color=discord.Color.orange()
                    )
            
                    msg = await interaction.edit_original_response(embed=embed, view=view)
                    view.message = msg # 타임아웃/방치 처리를 위해 메시지 저장
                    return

                # 🎣 물고기 기믹
                # (이전 중복 조회 부분 제거됨)
                pool = FISHING_ECOLOGY.get(location, FISHING_ECOLOGY["호수"])
                valid_pool = [f for f in pool if f.get("req_tier", 1) <= current_ground_tier]
                if not valid_pool: valid_pool = pool

                fish_rate_bonus = 0.0
                if built_facilities:
                    for f in built_facilities:
                        f_name = f['facility_name']
                        if f_name in FACILITIES:
                            fish_rate_bonus += FACILITIES[f_name].get("effect", {}).get("fish_rate", 0.0)

                # ⚖️ [등급별 확률 캡 시스템]
                raw_weights = []
                for f in valid_pool:
                    base_chance = f["chance"]
                    if f["rarity"] in ["희귀", "신종", "전설", "환상"]:
                        # 티어 비례 상승 + 시설 버프 합산
                        adj_w = base_chance * current_ground_tier * (1 + fish_rate_bonus)
                    else:
                        adj_w = base_chance
                    raw_weights.append(adj_w)

                # 등급별 가중치 합 및 인덱스 분류
                rarity_map = {"환상": [], "전설": [], "신종": [], "기타": []}
                for i, f in enumerate(valid_pool):
                    r = f["rarity"]
                    if r in rarity_map: rarity_map[r].append(i)
                    else: rarity_map["기타"].append(i)

                def apply_cap(weights, indices, cap_percent):
                    total_w = sum(weights)
                    if total_w <= 0: return weights
                    
                    current_w_sum = sum(weights[i] for i in indices)
                    current_ratio = current_w_sum / total_w
                    
                    if current_ratio > cap_percent:
                        # 목표 확률을 맞추기 위한 새로운 가중치 합 계산
                        # target / (other + target) = cap  =>  target = other * cap / (1 - cap)
                        other_w_sum = total_w - current_w_sum
                        if other_w_sum <= 0: return weights # 전체가 해당 등급이면 조정 불가
                        
                        target_w_sum = other_w_sum * (cap_percent / (1.0 - cap_percent))
                        scale_factor = target_w_sum / current_w_sum
                        
                        for i in indices:
                            weights[i] *= scale_factor
                    return weights

                # 캡 적용 (가장 희귀한 순서대로 조정하여 하위 등급의 비중을 확보)
                adjusted_weights = list(raw_weights)
                adjusted_weights = apply_cap(adjusted_weights, rarity_map["환상"], 0.10) # 환상 10%
                adjusted_weights = apply_cap(adjusted_weights, rarity_map["전설"], 0.15) # 전설 15%
                adjusted_weights = apply_cap(adjusted_weights, rarity_map["신종"], 0.30) # 신종 30%

                # ✅ 최종 결정
                fish = random.choices(valid_pool, weights=adjusted_weights, k=1)[0]
                length = round(random.uniform(fish["min"], fish["max"]), 1)

                # 💥 [특수 동물 및 유해생물 이벤트 즉시 작동 구역]
                # ✅ [수정] 특수 이벤트 체크 및 DB 트랜잭션을 통합 관리합니다.
                special_event = False
                event_embed = None

                if fish["name"] == "수달":
                    most_expensive = self.db.execute_query(
                        "SELECT id, fish_name FROM fishing_inventory WHERE user_id = ? AND guild_id = ? ORDER BY (length * price_per_cm) DESC LIMIT 1",
                        (uid, gid), 'one'
                    )
                    if most_expensive:
                        conn.execute("DELETE FROM fishing_inventory WHERE id = ?", (most_expensive['id'],))
                        desc = f"😱 수달이 가방을 뒤져 가장 비싼 **[{most_expensive['fish_name']}]**을(를) 훔쳐 달아났습니다!"
                    else:
                        desc = "🦦 수달이 가방을 뒤졌지만 훔칠 물고기가 없어 그냥 도망갔습니다."
                    event_embed = discord.Embed(title="🦦 수달 출현!", description=desc, color=discord.Color.red())
                    special_event = True

                elif fish["name"] == "자라":
                    conn.execute("UPDATE users SET cash = MAX(0, cash - 5000) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🤕 자라에게 물렸습니다!", description="물고 늘어지는 자라 때문에 치료비 **5,000원**이 지출되었습니다.", color=discord.Color.red())
                    special_event = True

                elif fish["name"] == "붉은가위가재":
                    conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - 10) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🦞 붉은가위가재 출현!", description="가위가재가 날카로운 집게로 낚싯줄을 끊으려 합니다!\n낚싯대 내구도가 **-10** 감소했습니다.", color=discord.Color.orange())
                    special_event = True

                elif fish["name"] == "너구리":
                    conn.execute("UPDATE fishing_gear SET bait_count = MAX(0, bait_count - 5) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🦝 너구리 출현!", description="늪가에서 기웃거리던 너구리가 가방을 털어 **미끼 5개**를 훔쳐 달아났습니다!", color=discord.Color.red())
                    special_event = True

                elif fish["name"] == "바다거북":
                    conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + 50 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🐢 바다거북을 방생했습니다!", description="보호종 바다거북을 안전하게 돌려보냈습니다.\n\n⭐ **개인 명성 +50**", color=discord.Color.green())
                    special_event = True

                elif fish["name"] == "보라성게":
                    conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - 10) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🟣 보라성게를 건졌습니다!", description="바다 백화현상의 주범입니다! 성게 가시에 찔려 낚싯대 내구도가 **-10** 감소했습니다.", color=discord.Color.orange())
                    special_event = True

                elif fish["name"] == "아무르불가사리":
                    conn.execute("UPDATE fishing_gear SET bait_count = MAX(0, bait_count - 2) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    event_embed = discord.Embed(title="🌟 아무르불가사리 출현!", description="해양 생태계를 파괴하는 유해 불가사리입니다! 엉킨 줄을 푸느라 미끼가 **2개** 더 소실되었습니다.", color=discord.Color.orange())
                    special_event = True

                elif fish["name"] == "황소개구리":
                    conn.execute("UPDATE users SET cash = cash + 10000 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    new_pollution = min(100.0, current_pollution + 2.0)
                    conn.execute("UPDATE fishing_ground SET pollution = ? WHERE channel_id = ? AND guild_id = ?", (new_pollution, chid, gid))
                    event_embed = discord.Embed(title="🐸 황소개구리 포획!", description="외래종 퇴치 포상금 **10,000원**을 획득했습니다.\n(🚨 늪 오염도 **+2.0 P** 상승)", color=discord.Color.gold())
                    special_event = True

                # 🎣 [수정] 특수 이벤트가 아닐 때만 일반 물고기 인벤토리에 한 번만 저장
                if not special_event:
                    # ✅ [수정] rarity 컬럼 추가 저장
                    conn.execute("INSERT INTO fishing_inventory (user_id, guild_id, fish_name, length, price_per_cm, rarity) VALUES (?, ?, ?, ?, ?, ?)", 
                                 (uid, gid, fish["name"], length, fish["price_per_cm"], fish.get("rarity", "흔함")))
                    
                    # ✨ [명성 계산 시스템 개선]
                    rep_multiplier = 1.0
                    if built_facilities:
                        for f in built_facilities:
                            f_name = f['facility_name']
                            if f_name in FACILITIES:
                                f_mult = FACILITIES[f_name].get("effect", {}).get("rep_mult", 1.0)
                                if f_mult > rep_multiplier:
                                    rep_multiplier = f_mult

                    # 1. 개인 명성 지급 (등급별 기본 점수 + 특정 어종 보너스)
                    rarity_rep = {"흔함": 1, "희귀": 3, "신종": 10, "전설": 30, "환상": 100}
                    fish_base_personal_rep = rarity_rep.get(fish.get("rarity", "흔함"), 1)
                    
                    # 특정 어종 추가 보너스 (10% 하향 적용)
                    if fish["name"] == "쏘가리": fish_base_personal_rep += 2
                    elif fish["name"] == "벵에돔": fish_base_personal_rep += 2
                    elif fish["name"] == "혹등고래": fish_base_personal_rep = 150 

                    base_give_rep = int(fish_base_personal_rep * rep_multiplier)
                    conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + ? WHERE user_id = ? AND guild_id = ?", (base_give_rep, uid, gid))

                    # 2. 낚시터 명성 지급 (모든 물고기 1점 기본 + 특수 어종 보너스)
                    ground_rep_gain = 1 # 모든 물고기는 낚시터 명성 1점을 기본으로 기여
                    if fish["name"] == "아로와나": ground_rep_gain += 100
                    elif fish["name"] == "고래상어": ground_rep_gain += 500
                    elif fish.get("rarity") == "전설": ground_rep_gain += 50
                    elif fish.get("rarity") == "환상": ground_rep_gain += 200
                    
                    conn.execute("UPDATE fishing_ground SET ground_reputation = ground_reputation + ? WHERE channel_id = ? AND guild_id = ?", (ground_rep_gain, chid, gid))

                    # 3. 낚싯대 내구도 차감 (기존 로직 유지)
                    durability_damage = 0
                    damage_map = {
                        "피라루쿠": 5, "천지 네시": 30, "타이거 샤크(뱀상어)": 15, 
                        "대왕 오징어": 10, "백상아리": 35, "가시연꽃": 2, 
                        "악어": 60, "메갈로돈": 80
                    }
                    durability_damage = damage_map.get(fish["name"], 0)
                    
                    if durability_damage > 0:
                        conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - ?) WHERE user_id = ? AND guild_id = ?", (durability_damage, uid, gid))

                    # 등급 정보와 설정 가져오기
                    rarity = fish.get("rarity", "흔함")
                    r_set = RARITY_CONFIG.get(rarity, RARITY_CONFIG["흔함"])

                    # 설명 구성
                    desc_lines = [
                        f"📏 **길이:** `{length}cm`",
                        f"⭐ **개인 명성:** `+{base_give_rep} P` (배율 적용)",
                        f"🏞️ **낚시터 명성:** `+{ground_rep_gain} P` 기여"
                    ]
                    
                    if durability_damage > 0:
                        desc_lines.append(f"💢 **내구도 감소:** `-{durability_damage}` 포인트")
                        
                    desc_lines.append(f"\n_{fish['effect_desc']}_")

                    event_embed = discord.Embed(
                        title=f"{r_set['emoji']} {rarity} 등급! {fish['name']}을(를) 잡았습니다!", 
                        description="\n".join(desc_lines),
                        color=r_set["color"]
                    )

                    if rarity == "전설":
                        event_embed.set_author(name="🎊 축하합니다! 전설적인 손맛! 🎊")
                    elif rarity == "환상":
                        event_embed.set_author(name="🌌 기적 발생! 환상의 생명체 등장! 🌌")

                # 🏁 모든 처리가 끝난 후 커밋을 수행합니다.
                conn.commit()
                
                # 💬 최종 메시지 전송
                await interaction.edit_original_response(embed=event_embed, view=None)

            except Exception as e:
                conn.rollback()
                await interaction.edit_original_response(embed=discord.Embed(title="❌ 시스템 오류", description=f"데이터 처리 중 오류가 발생했습니다. (에러: {e})", color=discord.Color.red()), view=None)
            finally:
                self._clear_session()


    # === 2. [추가할 코드] 옆에 나란히 붙을 [🛑 낚시 중지] 버튼 ===
    @discord.ui.button(label="🛑 낚시 중지", style=discord.ButtonStyle.secondary)
    async def stop_fishing(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: 
            return await interaction.response.send_message("본인만 조작할 수 있습니다.", ephemeral=True)
        
        if self.responded: 
            return
        
        self.responded = True
        await interaction.response.defer()
        self.stop() # 뷰 타이머와 이벤트 루프를 정지합니다.

        # 낚시 중지 알림 임베드 출력
        embed = discord.Embed(
            title="🛑 낚시 중단", 
            description="낚싯대를 거두었습니다. 소모된 미끼는 반환되지 않습니다.", 
            color=discord.Color.from_rgb(128, 128, 128) # 직접 RGB (회색) 지정
        )
        
        await interaction.edit_original_response(embed=embed, view=None)
        self._clear_session() # 액티브 세션 및 유저 락을 해제합니다.

class GroundAccessView(discord.ui.View):
    def __init__(self, user: discord.Member, fee: int, hours: int, owner_id: str, db_manager: DatabaseManager):
        super().__init__(timeout=31.0)
        self.user, self.fee, self.hours, self.owner_id, self.db = user, fee, hours, owner_id, db_manager

    @discord.ui.button(label="🎫 이용권 구매", style=discord.ButtonStyle.primary)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = str(interaction.user.id)
        gid = str(interaction.guild_id)
        
        # 1. 사용자 잔액 확인
        user_data = self.db.execute_query("SELECT cash FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
        user_cash = user_data['cash'] if user_data else 0
        
        if user_cash < self.fee:
            return await interaction.response.send_message(f"❌ 잔액이 부족합니다! (필요: {self.fee:,}원)", ephemeral=True)

        try:
            conn = self.db.get_connection()
            conn.execute("BEGIN")

            # 🏪 [체크] 매표소 시설 등급 확인 (LIKE 문 사용으로 간이/고급 모두 체크)
            facility_row = conn.execute(
                "SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name LIKE '%매표소%'", 
                (str(interaction.channel_id), gid)
            ).fetchone()

            # 🏷️ [로직] 시설 등급에 따른 가변 수수료 결정
            if facility_row:
                f_name = facility_row['facility_name']
                if "고급" in f_name:
                    FEE_RATE = 0.05  # 고급매표소: 수수료 5%
                elif "간이" in f_name:
                    FEE_RATE = 0.15  # 간이매표소: 수수료 15%
                else:
                    FEE_RATE = 0.10  # 일반매표소: 수수료 10%
                has_booth = True
            else:
                FEE_RATE = 1.0   # 매표소 없으면 수수료 100% (주인 수익 0)
                has_booth = False

            # 💸 [계산] 수수료 및 주인 순수익
            tax = int(self.fee * FEE_RATE)
            owner_profit = self.fee - tax

            # 📉 [차감] 구매자 돈 차감
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (self.fee, uid, gid))
            
            # 💰 [정산] 주인에게 수익 지급 (주인이 존재하고, 매표소가 있으며, 본인이 아닐 때)
            if self.owner_id and has_booth and str(self.owner_id) != uid:
                conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (owner_profit, str(self.owner_id), gid))
            
            # 🎫 [발급] 이용권 데이터 저장
            expire = (datetime.now() + timedelta(hours=self.hours)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute(
                "INSERT INTO fishing_passes (user_id, channel_id, guild_id, expire_time) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, channel_id, guild_id) DO UPDATE SET expire_time = excluded.expire_time",
                (uid, str(interaction.channel_id), gid, expire)
            )
            
            conn.commit()

            # 📩 결과 안내 메시지 분기
            if self.owner_id and has_booth:
                if str(self.owner_id) == uid:
                    msg = "본인 소유 낚시터이므로 별도의 정산이 발생하지 않았습니다."
                else:
                    msg = f"낚시터 소유주에게 수수료 {int(FEE_RATE*100)}%를 제외한 **{owner_profit:,}원**이 정산되었습니다."
            else:
                msg = "⚠️ 매표소 시설이 없거나 소유주가 없어 입장료가 서버로 귀속(소각)되었습니다."

            await interaction.response.edit_message(
                embed=discord.Embed(title="🎫 구매 완료!", description=f"✅ 이용 가능 시간: {self.hours}시간\n{msg}", color=discord.Color.green()), 
                view=None
            )
        except Exception as e:
            if 'conn' in locals(): conn.rollback()
            print(f"[결제 오류] {e}")
            await interaction.followup.send("❌ 결제 처리 중 오류가 발생했습니다.", ephemeral=True)

class FishingSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_trash_sessions = {}  # 🚨 쓰레기 세션 저장소 (필수 추가)

    async def cog_load(self):
        self.db_cog = self.bot.get_cog("DatabaseManager")
        for guild in self.bot.guilds:
            db = self.db_cog.get_manager(guild.id)
            self._init_db_schema(db)
        
        if not self.auto_cleanup_inactive_grounds.is_running():
            self.auto_cleanup_inactive_grounds.start()

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if self.db_cog:
            db = self.db_cog.get_manager(guild.id)
            self._init_db_schema(db)

    def _init_db_schema(self, db):
        # 1. 기본 테이블 생성
        db.create_table("fishing_ground", "channel_id TEXT, guild_id TEXT, owner_id TEXT, channel_name TEXT, ground_type TEXT DEFAULT '호수', tier INTEGER DEFAULT 1, ground_reputation INTEGER DEFAULT 0, ground_price INTEGER DEFAULT 100000, purchasable INTEGER DEFAULT 1, is_public INTEGER DEFAULT 1, entry_fee INTEGER DEFAULT 0, usage_time_limit INTEGER DEFAULT 6, pollution INTEGER DEFAULT 0, last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY(channel_id, guild_id)")
        db.create_table("fishing_gear", "user_id TEXT, guild_id TEXT, rod_level INTEGER DEFAULT 0, rod_durability INTEGER DEFAULT 100, bait_level INTEGER DEFAULT 0, bait_count INTEGER DEFAULT 0, PRIMARY KEY(user_id, guild_id)")
        db.create_table("fishing_inventory", "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, guild_id TEXT, fish_name TEXT, length REAL, price_per_cm INTEGER, rarity TEXT DEFAULT '흔함'")
        db.create_table("fishing_passes", "user_id TEXT, channel_id TEXT, guild_id TEXT, expire_time TEXT, PRIMARY KEY(user_id, channel_id, guild_id)")
        db.create_table("fishing_facilities", "channel_id TEXT, guild_id TEXT, facility_name TEXT, PRIMARY KEY(channel_id, guild_id, facility_name)")
        db.create_table("point_history", "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, transaction_type TEXT, amount INTEGER, balance_after INTEGER, description TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")
        
        # 🔍 [수정 부분] users 테이블 컬럼 누락 체크 및 보정
        cols_u_res = db.execute_query("PRAGMA table_info(users)", (), 'all')
        cols_u = [c['name'] for c in cols_u_res] if cols_u_res else []

        if 'max_fish_length' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN max_fish_length REAL DEFAULT 0.0")
            except: pass

        if 'fishing_reputation' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN fishing_reputation INTEGER DEFAULT 0")
            except: pass

        if 'illegal_dump_count' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN illegal_dump_count INTEGER DEFAULT 0")
            except: pass

        if 'neglect_dump_count' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN neglect_dump_count INTEGER DEFAULT 0")
            except: pass

        if 'fine_debt' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN fine_debt INTEGER DEFAULT 0")
            except: pass

        if 'fishing_ban_until' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN fishing_ban_until TEXT")
            except: pass

        if 'max_dump_rate' not in cols_u:
            try: db.execute_query("ALTER TABLE users ADD COLUMN max_dump_rate REAL DEFAULT 0.0")
            except: pass

        # 📦 [추가] 인벤토리 rarity 컬럼 누락 체크
        cols_i_res = db.execute_query("PRAGMA table_info(fishing_inventory)", (), 'all')
        cols_i = [c['name'] for c in cols_i_res] if cols_i_res else []
        if 'rarity' not in cols_i:
            try: db.execute_query("ALTER TABLE fishing_inventory ADD COLUMN rarity TEXT DEFAULT '흔함'")
            except: pass

        # 3. 낚시터 테이블 컬럼 누락 보정 (PRAGMA 조회)
        cols_g_res = db.execute_query("PRAGMA table_info(fishing_ground)", (), 'all')
        cols_g = [c['name'] for c in cols_g_res] if cols_g_res else []

        if 'pollution' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN pollution INTEGER DEFAULT 0")
            except: pass

        # ✅ 여기에 purchasable 자동 생성 로직을 추가합니다!
        if 'purchasable' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN purchasable INTEGER DEFAULT 1")
            except: pass

        if 'is_public' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN is_public INTEGER DEFAULT 1")
            except: pass
        
        if 'usage_time_limit' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN usage_time_limit INTEGER DEFAULT 6")
            except: pass

        if 'entry_fee' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN entry_fee INTEGER DEFAULT 0")
            except: pass
        if 'ground_type' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN ground_type TEXT DEFAULT '호수'")
            except: pass

        if 'last_activity' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP")
            except: pass

    def _get_db(self, interaction: discord.Interaction):
        db = self.db_cog.get_manager(interaction.guild_id)
        # ✅ 명령어를 날릴 때마다 스키마를 체크하여 누락된 컬럼(is_public 등)이 있다면 채워 넣습니다.
        self._init_db_schema(db)
        return db
    
    def _ensure_ground_exists(self, db, chid: str, gid: str, channel_name: str):
        ground = db.execute_query("SELECT 1 FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            # 🚨 usage_time_limit을 6으로 명시하여 삽입
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name, usage_time_limit) VALUES (?, ?, ?, 6)", (chid, gid, channel_name))

    def _process_illegal_dump_fine(self, db, uid: str, gid: str) -> Optional[int]:
        """무단투기 횟수를 1 올리고, 10의 배수가 되면 벌금 50,000원을 부과합니다."""
        conn = db.get_connection()
        fine_imposed = None
        
        try:
            conn.execute("BEGIN")
            
            # 1. 무단투기 카운트 +1
            conn.execute("UPDATE users SET illegal_dump_count = illegal_dump_count + 1 WHERE user_id = ? AND guild_id = ?", (uid, gid))
            
            # 2. 현재 카운트 조회
            user_data = db.execute_query("SELECT illegal_dump_count, cash FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            count = user_data['illegal_dump_count'] if user_data else 0
            current_cash = user_data['cash'] if user_data else 0
            
            # 3. 10회 누적 시 벌금 부과
            if count > 0 and count % 10 == 0:
                fine_imposed = 50000
                # 돈이 마이너스가 되더라도 과태료는 징수합니다. (빚쟁이 시스템)
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (fine_imposed, uid, gid))
                conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                             (uid, "과태료", -fine_imposed, current_cash - fine_imposed, f"무단투기 누적 {count}회 적발 과태료"))
            
            conn.commit()
            return fine_imposed
        except:
            conn.rollback()
            return None
        
    def _get_facilities_value(self, db, chid: str, gid: str) -> int:
        """현재 낚시터에 건설된 모든 시설의 원가(req_cash) 총합을 계산합니다."""
        facilities = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')
        
        total_value = 0
        if facilities:
            for f in facilities:
                name = f['facility_name']
                if name in FACILITIES:
                    total_value += FACILITIES[name].get("req_cash", 0)
        return total_value
        
    async def _execute_fishing(self, interaction: discord.Interaction):
        uid = str(interaction.user.id)
        chid = str(interaction.channel_id)
        gid = str(interaction.guild_id)

        # 🚨 [추가] 국고 환수 및 연타 방지 로직
        if uid in self.active_trash_sessions:
            old_view = self.active_trash_sessions[uid]
            if not old_view.is_finished():
                await old_view.process_neglect() # 50% 페널티 등 처리
            del self.active_trash_sessions[uid]

        # 3️⃣ DB 연결 및 구역 체크
        db = self._get_db(interaction)

        # 🚫 [추가] 낚시 금지 제제 체크
        user_data = db.get_user(uid)
        if user_data and user_data.get('fishing_ban_until'):
            ban_until = datetime.strptime(user_data['fishing_ban_until'], '%Y-%m-%d %H:%M:%S')
            if datetime.now() < ban_until:
                remain = ban_until - datetime.now()
                minutes, seconds = divmod(int(remain.total_seconds()), 60)
                embed = discord.Embed(
                    title="🚫 낚시터 이용 제한 중",
                    description=(
                        f"누적 투기 기록으로 인해 현재 낚시터 이용이 금지된 상태입니다.\n\n"
                        f"⏳ **남은 시간:** `{minutes}분 {seconds}초` 뒤에 해제됩니다."
                    ),
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 🕒 [추가] 낚시 활동 시간 업데이트 (일주일 방치 체크용)
        db.execute_query(
            "UPDATE fishing_ground SET last_activity = CURRENT_TIMESTAMP WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid)
        )
        
        ground_check = db.execute_query(
            "SELECT 1 FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid), 'one'
        )

        if not ground_check:
            embed = discord.Embed(
                title="❌ 낚시 금지 구역",
                description=(
                    "이곳은 공식적으로 지정된 낚시터 채널이 아닙니다!\n"
                    "정해진 낚시터 채널로 이동하여 낚싯대를 던져주세요.\n\n"
                    "💡 사유지라면 낚시터를 먼저 구매해야 낚시가 가능합니다."
                ),
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        
        # 4️⃣ 장비 및 미끼 체크
        gear = db.execute_query("SELECT bait_count, rod_durability FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
        if not gear: 
            return await interaction.response.send_message("❌ 장비가 없습니다! `/낚시가게`에서 초보자 세트를 구매하세요.", ephemeral=True)
        if gear['bait_count'] <= 0: 
            return await interaction.response.send_message("❌ 미끼가 없습니다!", ephemeral=True)
        if gear['rod_durability'] <= 0: 
            return await interaction.response.send_message("❌ 낚싯대가 고장 났습니다! 수리 후 이용하세요.", ephemeral=True)

        # 5️⃣ 낚시터 정보 로드 및 입장권 체크
        ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name, usage_time_limit) VALUES (?, ?, ?, 6)", (chid, gid, interaction.channel.name))
            ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')

        # 사유지 입장 제한 로직
        if ground['owner_id'] and ground['owner_id'] != uid and ground['is_public'] != 1:
            p = db.execute_query("SELECT expire_time FROM fishing_passes WHERE user_id = ? AND channel_id = ? AND guild_id = ?", (uid, chid, gid), 'one')
            if not p or datetime.strptime(p['expire_time'], '%Y-%m-%d %H:%M:%S') <= datetime.now():
                view = GroundAccessView(interaction.user, ground['entry_fee'], ground['usage_time_limit'], ground['owner_id'], db)
                return await interaction.response.send_message(embed=discord.Embed(title="🛑 입장권이 필요합니다", description=f"비용: **{ground['entry_fee']:,}원**\n구매하시겠습니까?", color=discord.Color.orange()), view=view)

        # 6️⃣ 게임 뷰 생성 및 시작
        # FishingGameView(interaction, db, cog) 순서 준수
        view = FishingGameView(interaction, db, self)
        
        active_sessions[interaction.user.id] = view
            
        await view.start_game(interaction)

    @app_commands.command(name="낚시", description="낚시 게임을 시작합니다.")
    async def fish_start(self, interaction: discord.Interaction):
        await self._execute_fishing(interaction)

    @app_commands.command(name="ㄴㅅ", description="낚시를 즉시 시작합니다 (단축어)")
    async def fish_short(self, interaction: discord.Interaction):
        await self._execute_fishing(interaction)

    @app_commands.command(name="낚시터", description="낚시터 정보를 조회하거나 땅을 관리합니다.")
    @app_commands.choices(액션=[
        app_commands.Choice(name="정보 조회", value="info"),
        app_commands.Choice(name="낚시터 구매 (매입)", value="buy"),
        app_commands.Choice(name="낚시터 판매 (매각)", value="sell"),
        app_commands.Choice(name="설정 변경 (입장료/공개여부/지형)", value="edit")
    ])
    @app_commands.choices(지형=[
        app_commands.Choice(name="🏞️ 호수", value="호수"),
        app_commands.Choice(name="🌊 바다", value="바다"),
        app_commands.Choice(name="🐊 늪", value="늪")
    ])
    async def fish_ground(
        self, 
        interaction: discord.Interaction, 
        액션: str, 
        입장료: Optional[int] = None, 
        공개: Optional[int] = None, 
        지형: Optional[str] = None
    ):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name, usage_time_limit) VALUES (?, ?, ?, 6)", (chid, gid, interaction.channel.name))
            ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')

        # 🔍 [1] 정보 조회 기능 (수정본)
        if 액션 == "info":
            if ground['owner_id']:
                owner = f"<@{ground['owner_id']}>"
            elif ground['purchasable'] == 1:
                owner = "없음 (구매 가능)"
            else:
                owner = "없음 (공용 낚시터)"

            facilities = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')
            f_list = ", ".join([f['facility_name'] for f in facilities]) if facilities else "없음"

            adj_fee = 0.0          # 🎫 매표소 수수료 조정
            fish_rate = 0.0        # 📦 물고기 낚일 확률 증가
            base_fee = 0.0         # 📦 창고 기본 수수료
            trash_rate = 0.0       # 🧹 쓰레기 감소 확률
            upkeep_discount = 0.0  # ⚡ 유지비 감소율
            upkeep_mult = 0.0      # 💸 유지비 증가율
            rep_mult = 1.0         # ✨ 명성 획득 배율 (기본 1배)
            fish_price_mult = 1.0  # 🏪 물고기 판매가 배율 (기본 1배)
            fail_rate = 0.0        # 🏫 낚시 실패 확률 증가

            if facilities:
                for f in facilities:
                    f_name = f['facility_name']
                    if f_name in FACILITIES:
                        effects = FACILITIES[f_name].get("effect", {})
                        
                        adj_fee += effects.get("fee_adj", 0.0)
                        fish_rate += effects.get("fish_rate", 0.0)
                        base_fee += effects.get("base_fee", 0.0)
                        trash_rate += effects.get("trash_rate", 0.0)
                        upkeep_discount += effects.get("upkeep_discount", 0.0)
                        upkeep_mult += effects.get("upkeep_mult", 0.0)
                        
                        p_mult = effects.get("fish_price_mult", 1.0)
                        if p_mult > fish_price_mult:
                            fish_price_mult = p_mult
                            
                        r_mult = effects.get("rep_mult", 1.0)
                        if r_mult > rep_mult:
                            rep_mult = r_mult
                            
                        fail_rate += effects.get("fail_rate", 0.0)

            # ⚖️ [쓰레기 확률 최종 연동 계산]
            current_pollution = ground['pollution'] if ground['pollution'] is not None else 0
            base_trash_chance = 0.25 + (current_pollution / 100.0)
            final_trash_chance = max(0.0, min(1.0, base_trash_chance + trash_rate))

            final_upkeep_mod = (upkeep_mult - upkeep_discount) * 100

            base_land_price = ground['ground_price'] or 100000
            facilities_value = self._get_facilities_value(db, chid, gid)
            current_property_value = base_land_price + facilities_value

            embed = discord.Embed(title=f"📍 낚시터 정보: {interaction.channel.name}", color=discord.Color.blue())
            embed.add_field(name="👑 소유주", value=owner, inline=True)
            embed.add_field(name="💰 구매 가격", value=f"{ground['ground_price']:,}원", inline=True)
            embed.add_field(name="🎫 입장료", value=f"{ground['entry_fee']:,}원", inline=True)
            embed.add_field(name="⌛ 이용시간", value="6시간 (고정)", inline=True)
            embed.add_field(name="🔓 상태", value="공개" if ground['is_public'] == 1 else "비공개 (입장권 필요)", inline=True)
            embed.add_field(name="🌍 자연 환경", value=ground['ground_type'], inline=True)
            ground_rep = ground['ground_reputation'] if ground['ground_reputation'] is not None else 0
            embed.add_field(name="📈 낚시터 명성", value=f"`{ground_rep:,} P`", inline=True)
            embed.add_field(name="🚨 채널 오염도", value=f"`{current_pollution:.1f} P`", inline=True)
            embed.add_field(name="🏗️ 설치 시설", value=f_list, inline=False)

            effect_summary = (
                f"🎫 **수수료 조정 범위:** `±{adj_fee * 100:.1f}%` (매표소)\n"
                f"📦 **희귀 물고기 확률:** `+{fish_rate * 100:.1f}%` (창고)\n"
                f"💰 **창고 기본 수수료:** `+{base_fee * 100:.1f}%` (창고)\n"
                f"🗑️ **현재 쓰레기 낚일 확률:** `{final_trash_chance * 100:.1f}%` (기본+오염도+시설합산)\n"
                f"⚡ **최종 유지비 변동률:** `{final_upkeep_mod:+.1f}%` (발전소/사업체)\n"
                f"✨ **명성 획득 배율:** `{rep_mult:.1f}배` (명성 시설)\n"
                f"🏪 **물고기 판매가 보너스:** `{fish_price_mult:.1f}배` (상점/기업)\n"
                f"🏫 **낚시 실패 확률 증가:** `+{fail_rate * 100:.1f}%` (학교)\n"
            )
            embed.add_field(name="📊 현재 낚시터 적용 효과 종합", value=effect_summary, inline=False)

            await interaction.response.send_message(embed=embed)

        # 🛒 [2] 낚시터 구매 (매입 / 약탈) 기능
        elif 액션 == "buy":
            if ground['owner_id'] == uid:
                return await interaction.response.send_message("❌ 이미 본인이 소유하고 있는 낚시터입니다.", ephemeral=True)

            base_buy_price = ground['ground_price'] or 100000 
            
            facilities = db.execute_query(
                "SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", 
                (chid, gid), 'all'
            )

            total_facility_original = 0
            if facilities:
                for f in facilities:
                    f_name = f['facility_name']
                    if f_name in FACILITIES:
                        total_facility_original += FACILITIES[f_name].get('req_cash', 0)

            facility_value_80 = int(total_facility_original * 0.8)
            total_buy_price = base_buy_price + facility_value_80
            
            user_data = db.execute_query("SELECT cash FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            user_cash = user_data['cash'] if user_data else 0
            if user_cash < total_buy_price:
                return await interaction.response.send_message(
                    f"❌ 매입 자금이 부족합니다!\n"
                    f"💰 최종 매입가: {total_buy_price:,}원 (보유: {user_cash:,}원)", 
                    ephemeral=True
                )

            is_takeover = ground['owner_id'] is not None
            title = "⚔️ 낚시터 약탈(인수) 최종 확인" if is_takeover else "🏗️ 낚시터 매입 최종 확인"
            desc = (
                f"현재 채널(<#{chid}>)을 매입하시겠습니까?\n\n"
                f"💵 기본 토지 가치: `{base_buy_price:,}원` \n"
                f"🏗️ 시설 가치(80% 반영): `{facility_value_80:,}원` \n"
                f"└ *시설 정가 총액: {total_facility_original:,}원*\n"
                f"───\n"
                f"💰 **최종 매입가: {total_buy_price:,}원**"
            )
            if is_takeover:
                desc += f"\n\n⚠️ **주의:** 이미 다른 주인이 있는 땅입니다. 매입 시 기존 주인의 시설은 철거되며 땅이 초기화됩니다."

            confirm_embed = discord.Embed(title=title, description=desc, color=discord.Color.gold())
            view = BuyConfirmView(db, total_buy_price, chid, gid, uid)
            await interaction.response.send_message(embed=confirm_embed, view=view, ephemeral=True)
            return

        # ⚙️ [3] 설정 변경 기능
        elif 액션 == "edit":
            if ground['owner_id'] != uid: 
                return await interaction.response.send_message("❌ 소유자만 설정을 변경할 수 있습니다.", ephemeral=True)
            
            user_data = db.execute_query("SELECT cash FROM users WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            user_cash = user_data['cash'] if user_data else 0

            if 입장료 is not None:
                if 입장료 < 0:
                    return await interaction.response.send_message("❌ 입장료는 음수로 설정할 수 없습니다.", ephemeral=True)
                
                percent_limit = max(1000, int(user_cash * 0.8))
                ABSOLUTE_MAX_FEE = 100000 
                final_limit = min(percent_limit, ABSOLUTE_MAX_FEE)

                if 입장료 > final_limit:
                    embed = discord.Embed(
                        title="🛑 입장료 설정 제한",
                        description=(
                            f"서버 경제 밸런스와 사기 가격 방지를 위해 입장료 책정이 제한됩니다.\n\n"
                            f"🔒 **설정 가능한 최대 입장료:** `{final_limit:,}원`"
                        ),
                        color=discord.Color.red()
                    )
                    return await interaction.response.send_message(embed=embed, ephemeral=True)

            if 입장료 is not None or 지형 is not None:
                new_fee = 입장료 if 입장료 is not None else ground['entry_fee']
                new_type = 지형 if 지형 is not None else ground['ground_type']
                db.execute_query(
                    "UPDATE fishing_ground SET entry_fee = ?, ground_type = ? WHERE channel_id = ? AND guild_id = ?", 
                    (new_fee, new_type, chid, gid)
                )
                await interaction.response.send_message(f"✅ 기초 정보가 업데이트되었습니다! (입장료: {new_fee:,}원 / 환경: {new_type})")
                return 

            embed = discord.Embed(
                title="🔒 낚시터 공개 여부 설정", 
                description="아래 버튼을 눌러 낚시터 개방 여부를 선택하세요.\n\n- **공개:** 입장권 없이 누구나 무료 이용\n- **비공개:** 다른 유저는 이용권 구매 필요", 
                color=discord.Color.purple()
            )
            view = PublicSettingView(interaction.user, db)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()
            return

        elif 액션 == "sell":
            if not ground['owner_id'] or ground['owner_id'] != uid:
                return await interaction.response.send_message("❌ 본인 소유의 낚시터만 매각할 수 있습니다.", ephemeral=True)

            base_land_price = ground['ground_price'] or 100000
            facilities_value = self._get_facilities_value(db, chid, gid)
            
            # 매각 시 환불 비율: 땅값 50% + 시설값 50%
            refund_price = int((base_land_price + facilities_value) * 0.5)

            embed = discord.Embed(
                title="🏢 낚시터 매각 최종 확인",
                description=(
                    f"현재 채널(<#{chid}>)의 소유권을 포기하고 매각하시겠습니까?\n\n"
                    f"💰 **예상 환불 금액:** `{refund_price:,}원`\n"
                    f"└ 땅 가치(50%): `{int(base_land_price*0.5):,}원`\n"
                    f"└ 시설 가치(50%): `{int(facilities_value*0.5):,}원`\n\n"
                    f"⚠️ **주의:** 매각 시 모든 시설물이 철거되며, 낚시터 명성과 티어가 초기화됩니다."
                ),
                color=discord.Color.red()
            )
            view = SellConfirmView(db, refund_price, chid, gid, uid)
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            return

    @app_commands.command(name="낚시터티어", description="[주인 전용] 낚시터 명성을 소모하여 땅 등급을 올리거나 내립니다.")
    @app_commands.choices(액션=[
        app_commands.Choice(name="🔼 업그레이드 (명성 소모)", value="up"),
        app_commands.Choice(name="🔽 다운그레이드 (명성 일부 환급)", value="down")
    ])
    async def edit_tier(self, interaction: discord.Interaction, 액션: str):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)

        ground = db.execute_query("SELECT owner_id, tier, ground_reputation FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground or ground['owner_id'] != uid:
            return await interaction.response.send_message("❌ 본인 소유의 낚시터만 티어를 변경할 수 있습니다.", ephemeral=True)

        current_tier = ground['tier'] or 1
        current_rep = ground['ground_reputation'] or 0

        # 🔼 업그레이드 액션 시 1차 승인 버튼 팝업
        if 액션 == "up":
            if current_tier >= 5:
                return await interaction.response.send_message("❌ 이미 최고 등급(5티어)입니다.", ephemeral=True)
            
            # 🔍 [추가] 현재 땅에 지어진 시설 목록 조회
            built_facilities = db.execute_query(
                "SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", 
                (chid, gid), 'all'
            )
            built_names = [f['facility_name'] for f in built_facilities] if built_facilities else []

            # 🚨 [추가] 티어별 테크트리 필수 건축물 조건 체크 (하드코어 제한)
            if current_tier == 1 and "매표소" not in built_names and "창고" not in built_names:
                return await interaction.response.send_message("❌ 2티어로 업그레이드하려면 **[매표소]** 또는 **[창고]**가 건설되어 있어야 합니다!", ephemeral=True)
            
            elif current_tier == 2 and "중형창고" not in built_names:
                return await interaction.response.send_message("❌ 3티어로 업그레이드하려면 **[중형창고]**가 먼저 건설되어 있어야 합니다!", ephemeral=True)
            
            elif current_tier == 3 and "화력발전소" not in built_names:
                return await interaction.response.send_message("❌ 4티어로 업그레이드하려면 **[화력발전소]**가 먼저 건설되어 있어야 합니다!", ephemeral=True)
                
            elif current_tier == 4 and "세계1위기업" not in built_names and "환경부" not in built_names:
                return await interaction.response.send_message("❌ 5티어로 업그레이드하려면 **[세계1위기업]** 또는 **[환경부]**가 건설되어 있어야 합니다!", ephemeral=True)
            
            tier_costs = {
                1: 1000,  # 1 -> 2티어 갈 때 2000 P 소모
                2: 5000,  # 2 -> 3티어 갈 때 5000 P 소모
                3: 25000, # 3 -> 4티어 갈 때 10000 P 소모
                4: 50000  # 4 -> 5티어 갈 때 20000 P 소모
            }

            req_rep = tier_costs.get(current_tier, 1000) # 정의되지 않은 에러 방지용 기본값 1000
            
            if current_rep < req_rep:
                return await interaction.response.send_message(f"❌ 낚시터 명성이 부족합니다! (필요: {req_rep:,}점 / 보유: {current_rep:,}점)", ephemeral=True)

            embed = discord.Embed(
                title="🔔 티어 업그레이드 확인",
                description=(
                    f"<#{chid}> 채널의 등급을 올리시겠습니까?\n"
                    f"아래의 [✅ 최종 승인] 버튼을 누르면 즉시 명성이 차감되고 랭크가 오릅니다.\n\n"
                    f"🔼 **목표 등급:** `Lv.{current_tier + 1}`\n"
                    f"📉 **소모 예정 명성:** `{req_rep:,} P` (남은 명성 예상치: {current_rep - req_rep:,} P)"
                ),
                color=discord.Color.orange()
            )
            
            view = TierUpgradeConfirmView(interaction.user, req_rep, current_tier, chid, gid, db)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()

        # 🔽 다운그레이드는 기존처럼 즉시 반영 (혹은 필요하다면 동일하게 버튼 뷰 적용 가능)
        elif 액션 == "down":
            if current_tier <= 1:
                return await interaction.response.send_message("❌ 이미 최하 등급(1티어)입니다.", ephemeral=True)

            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE fishing_ground SET tier = tier - 1, ground_reputation = ground_reputation + 500 WHERE channel_id = ? AND guild_id = ?", (chid, gid))
                conn.commit()
                await interaction.response.send_message(f"🔽 낚시터 등급이 **{current_tier - 1}티어**로 내려갔습니다! (명성 500점 환급)")
            except Exception as e:
                conn.rollback()
                await interaction.response.send_message(f"❌ 티어 변경 중 오류가 발생했습니다. (에러: {e})", ephemeral=True)

    @app_commands.command(name="쓰레기청소", description="현재 낚시터 채널의 오염도를 돈을 내고 청소하여 정화합니다.")
    @app_commands.choices(청소량=[
        app_commands.Choice(name="🧹 가벼운 청소 (오염도 -5 감소 / 기본 5,000원)", value="light"),
        app_commands.Choice(name="🧼 대청소 (오염도 -20 감소 / 기본 20,000원)", value="deep"),
        app_commands.Choice(name="🚜 전문 방역 및 정화 (오염도 0으로 초기화 / 수치비례 고가)", value="full")
    ])
    async def clean_channel_pollution(self, interaction: discord.Interaction, 청소량: str):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)

        ground = db.execute_query("SELECT pollution, tier FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            return await interaction.response.send_message("❌ 이 채널은 등록된 낚시터가 아닙니다.", ephemeral=True)

        current_pollution = ground['pollution'] if ground['pollution'] is not None else 0
        ground_tier = ground['tier'] if ground['tier'] is not None else 1 # 👈 현재 티어 가져오기

        if current_pollution <= 0:
            return await interaction.response.send_message("✨ 이 낚시터는 이미 매우 깨끗합니다! 청소할 필요가 없습니다.", ephemeral=True)

        base_cost = 0
        reduce_amount = 0.0

        if 청소량 == "light":
            reduce_amount = 5.0
            base_cost = 5000
        elif 청소량 == "deep":
            reduce_amount = 20.0
            base_cost = 20000
        elif 청소량 == "full":
            reduce_amount = current_pollution
            base_cost = int(current_pollution * 2000)

        # 🚨 [중요 밸런스 조정] 티어 배율 적용
        # 1티어: base_cost * 1
        # 2티어: base_cost * 2
        # ... 5티어: base_cost * 5
        final_cost = base_cost * ground_tier

        # 💰 1차 소지금 검사
        user_cash = db.get_user_cash(uid) or 0
        if user_cash < final_cost:
            return await interaction.response.send_message(
                f"❌ 청소 비용이 부족합니다!\n(현재 {ground_tier}티어 요율 적용)\n"
                f"필요 비용: **{final_cost:,}원** (기본: {base_cost:,}원 × {ground_tier}배)\n보유 자금: {user_cash:,}원", 
                ephemeral=True
            )

        # 🔍 버튼을 통한 가격 가승인 출력
        embed = discord.Embed(
            title="🔔 청소 결제 확인",
            description=(
                f"<#{chid}> 채널을 청소하시겠습니까?\n"
                f"이 낚시터는 현재 **[{ground_tier}티어]** 등급이므로 정비 비용이 **{ground_tier}배** 증가합니다.\n\n"
                f"💳 **최종 결제 금액:** `{final_cost:,}원` (기본 비용 {base_cost:,}원 × {ground_tier}배)\n"
                f"📉 **오염도 정화 수치:** `- {min(current_pollution, reduce_amount):.1f} P`"
            ),
            color=discord.Color.orange()
        )
        embed.set_footer(text=f"차감 후 예상 잔액: {user_cash - final_cost:,}원")
        
        view = CleanConfirmView(interaction.user, final_cost, reduce_amount, chid, gid, db)
        await interaction.response.send_message(embed=embed, view=view)
        view.message = await interaction.original_response()

    # ==========================================
    # 🏢 [시설 건설 명령어] - 자동완성(Autocomplete) 추가 버전
    # ==========================================
    @app_commands.command(name="시설", description="낚시터에 수익을 높여줄 시설을 건설합니다.")
    @app_commands.choices(대분류=[
        app_commands.Choice(name="🎫 매표소", value="ticketing"),
        app_commands.Choice(name="📦 물고기 창고", value="warehouse"),
        app_commands.Choice(name="🧹 쓰레기 청소", value="cleaning"),
        app_commands.Choice(name="⚡ 발전소", value="power"),
        app_commands.Choice(name="✨ 명성 증가 배율", value="reputation"),
        app_commands.Choice(name="♻️ 쓰레기장 및 환경", value="recycling"),
        app_commands.Choice(name="🛒 그 외 사업", value="etc_business"),
        app_commands.Choice(name="🏪 가게 및 상업", value="store"),
        app_commands.Choice(name="🏫 학교 (방해요소)", value="school")
    ])
    # 📌 autocomplete=True 를 시설명 파라미터에 추가합니다.
    async def build_facility(self, interaction: discord.Interaction, 대분류: str, 시설명: str):
        if 시설명 not in FACILITIES:
            return await interaction.response.send_message("❌ 존재하지 않는 시설입니다.", ephemeral=True)
        
        if 시설명 not in CATEGORY_FACILITIES.get(대분류, []):
            return await interaction.response.send_message("❌ 선택하신 시설은 이 카테고리에 속해있지 않습니다.", ephemeral=True)
        
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        ground = db.execute_query("SELECT owner_id, is_public FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        
        # ✅ 공영 낚시터(소유주 없음)이면서 관리자라면 허용, 그 외에는 본인 땅 체크
        is_admin = interaction.user.guild_permissions.administrator
        is_public_ground = (ground and ground['owner_id'] is None)
        
        if not ground:
            return await interaction.response.send_message("❌ 등록된 낚시터 정보가 없습니다.", ephemeral=True)

        if not ( (is_public_ground and is_admin) or (ground['owner_id'] == uid) ):
            return await interaction.response.send_message("❌ 본인이 매입한 개인 사유지이거나, 공영 낚시터의 관리자여야 시설을 지을 수 있습니다.", ephemeral=True)
        
        f_data = FACILITIES[시설명]
        user = db.get_user(uid)
        
        if not user or user.get('fishing_reputation', 0) < f_data['req_rep']: 
            return await interaction.response.send_message(f"❌ 개인 낚시 명성이 부족합니다! (필요: {f_data['req_rep']:,}점)", ephemeral=True)
        if user.get('cash', 0) < f_data['req_cash']: 
            return await interaction.response.send_message(f"❌ 건설 자금이 부족합니다! (필요: {f_data['req_cash']:,}원)", ephemeral=True)
        
        existing = db.execute_query("SELECT 1 FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명), 'one')
        if existing: 
            return await interaction.response.send_message("⚠️ 이 채널에 이미 설치된 동일한 시설이 있습니다.", ephemeral=True)

        conn = db.get_connection()
        try:
            conn.execute("BEGIN")

            # 💰 1. 소지금 차감
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (f_data['req_cash'], uid, gid))
            
            # ⭐ 2. [추가] 개인 낚시 명성 차감
            conn.execute("UPDATE users SET fishing_reputation = fishing_reputation - ? WHERE user_id = ? AND guild_id = ?", (f_data['req_rep'], uid, gid))
            
            # 🏗️ 3. 시설 데이터 입력
            conn.execute("INSERT INTO fishing_facilities (channel_id, guild_id, facility_name) VALUES (?, ?, ?)", (chid, gid, 시설명))

            conn.commit()
            await interaction.response.send_message(
                f"🏗️ <#{chid}> 채널에 **{시설명}** 건설이 완료되었습니다!\n"
                f"💸 **차감 소지금:** `{f_data['req_cash']:,}원` / 📉 **소모 명성:** `{f_data['req_rep']:,}점`"
            )
        except Exception as e:
            conn.rollback()
            await interaction.response.send_message(f"❌ 시설 건설 중 DB 오류가 발생했습니다. (에러: {e})", ephemeral=True)
        
    @build_facility.autocomplete('시설명')
    async def build_facility_autocomplete(self, interaction: discord.Interaction, current: str):
        # 유저가 명령어를 칠 때 '대분류'에 무엇을 골랐는지 실시간으로 가져옵니다.
        selected_category = interaction.namespace.대분류 

        # 🚨 대분류가 아직 선택되지 않았거나 로딩 중일 때 빈 목록 반환 방지
        if not selected_category:
            return []

        # 딕셔너리(CATEGORY_FACILITIES)에서 해당 대분류 영문 키에 해당하는 리스트를 꺼내옵니다.
        available_facilities = CATEGORY_FACILITIES.get(selected_category, [])

        choices = []
        for f_name in available_facilities:
            # 시설 정보가 유효한지 2차 검증
            if f_name not in FACILITIES:
                continue

            # 유저가 검색창에 글자를 치면 필터링하고, 아무것도 안 치면 해당 대분류의 전체 목록을 보여줍니다.
            if current.lower() in f_name.lower():
                # 🏷️ 표시 이름에 가격과 명성 조건을 적어주면 유저가 고르기 훨씬 편해집니다!
                f_data = FACILITIES[f_name]
                display_name = f"{f_name} (명성 {f_data['req_rep']:,}점 / {f_data['req_cash']:,}원)"
                choices.append(app_commands.Choice(name=display_name, value=f_name))

        # 디스코드 API 한계상 자동완성 목록은 최대 25개까지만 표출 가능합니다.
        return choices[:25]


    # ==========================================
    # 🪓 [시설 철거 명령어]
    # ==========================================
    @app_commands.command(name="시설철거", description="낚시터에 지어진 시설을 파괴하고 명성을 일부 돌려받습니다.")
    async def destroy_facility(self, interaction: discord.Interaction, 시설명: str):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)

        ground = db.execute_query("SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground or not ground['owner_id'] or ground['owner_id'] != uid:
            return await interaction.response.send_message("❌ 본인 소유의 낚시터 시설만 철거할 수 있습니다.", ephemeral=True)

        if 시설명 not in FACILITIES:
            return await interaction.response.send_message("❌ 존재하지 않는 시설입니다.", ephemeral=True)

        existing = db.execute_query("SELECT 1 FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명), 'one')
        if not existing:
            return await interaction.response.send_message("⚠️ 이 채널에 건설되지 않은 시설입니다.", ephemeral=True)

        refund_rep = int(FACILITIES[시설명]["req_rep"] * 0.5)

        conn = db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명))
            conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + ? WHERE user_id = ? AND guild_id = ?", (refund_rep, uid, gid))
            conn.commit()
            await interaction.response.send_message(f"🪓 <#{chid}> 채널의 **{시설명}** 시설이 철거되었습니다! 개인 명성 **{refund_rep:,}점**을 환급받았습니다.")
        except Exception as e:
            conn.rollback()
            await interaction.response.send_message(f"❌ 철거 중 오류가 발생했습니다. (에러: {e})", ephemeral=True)

    # 🔍 철거할 시설을 오타 없이 고를 수 있도록 현재 지어진 건물만 보여주는 자동완성
    @destroy_facility.autocomplete('시설명')
    async def destroy_facility_autocomplete(self, interaction: discord.Interaction, current: str):
        db = self._get_db(interaction)
        chid, gid = str(interaction.channel_id), str(interaction.guild_id)
        
        facilities = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')
        if not facilities:
            return []

        choices = []
        for f in facilities:
            name = f['facility_name']
            if current.lower() in name.lower():
                choices.append(app_commands.Choice(name=name, value=name))
        return choices[:25]
    
    @app_commands.command(name="낚시정보", description="내 낚시 기록과 장비 정보를 확인합니다.")
    @app_commands.choices(분류=[app_commands.Choice(name="내 정보", value="me"), app_commands.Choice(name="서버 랭킹", value="rank")])
    async def fish_info(self, interaction: discord.Interaction, 분류: str = "me"):
        db = self._get_db(interaction)
        uid, gid = str(interaction.user.id), str(interaction.guild_id)
        
        if 분류 == "me":
            u = db.get_user(uid)
            if not u: return await interaction.response.send_message("❌ 기록을 찾을 수 없습니다. 경제 시스템에 먼저 가입하세요.", ephemeral=True)
            
            cnt_res = db.execute_query("SELECT COUNT(*) as c FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            cnt = cnt_res['c'] if cnt_res else 0
            
            embed = discord.Embed(title=f"🎣 {interaction.user.display_name}님의 낚시 수첩", color=discord.Color.blue())
            embed.add_field(name="🌟 낚시 명성", value=f"{u.get('fishing_reputation', 0):,}점", inline=True)
            embed.add_field(name="📏 최대 월척", value=f"{u.get('max_fish_length', 0.0)}cm", inline=True)
            embed.add_field(name="🎒 가방 물고기", value=f"{cnt}마리", inline=True)
            
            # 투기 기록 추가
            illegal = u.get('illegal_dump_count', 0)
            neglect = u.get('neglect_dump_count', 0)
            embed.add_field(name="🚮 투기 기록", value=f"🚫 무단: {illegal}회 / 💤 방치: {neglect}회", inline=False)

            gear = db.execute_query("SELECT rod_level, rod_durability, bait_count FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            if gear:
                max_d = 100 + (gear['rod_level'] * 100)
                embed.add_field(name="🎣 현재 장비", value=f"Lv.{gear['rod_level']} 낚싯대 (내구도: {gear['rod_durability']}/{max_d})", inline=False)
                embed.add_field(name="🐛 보유 미끼", value=f"{gear['bait_count']}개", inline=True)
            else:
                embed.add_field(name="⚠️ 장비 없음", value="낚시가게에서 초보자 세트를 구매해 보세요!", inline=False)
            await interaction.response.send_message(embed=embed)
        else:
            res = db.execute_query("SELECT display_name, IFNULL(fishing_reputation, 0) as r FROM users WHERE guild_id = ? ORDER BY r DESC LIMIT 10", (gid,), 'all')
            desc = "\n".join([f"**{i+1}위.** {r['display_name']}: {r['r']:,}점" for i, r in enumerate(res)]) if res else "기록이 없습니다."
            await interaction.response.send_message(embed=discord.Embed(title="🏆 서버 낚시 명성 TOP 10", description=desc, color=discord.Color.gold()))

    @app_commands.command(name="낚시가게", description="잡은 고기를 판매하거나 장비를 관리합니다.")
    @app_commands.choices(액션=[
        app_commands.Choice(name="물고기 전량 판매", value="sell"), 
        app_commands.Choice(name="낚싯대 수리(1당 10원)", value="repair"),
        app_commands.Choice(name="초보자 세트 구매 (10,000원)", value="starter"),
        app_commands.Choice(name="미끼 개당 (300원)", value="buy_bait")
    ])
    async def fish_shop(self, interaction: discord.Interaction, 액션: str, 수량: Optional[int] = None):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        if 액션 == "sell":
            # ✅ [수정] rarity 컬럼을 명시적으로 가져와야 등급별 캡이 적용됩니다.
            items = db.execute_query("SELECT length, price_per_cm, fish_name, rarity FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (uid, gid), 'all')
            if not items: 
                return await interaction.response.send_message("🎒 가방에 팔 물고기가 없습니다.", ephemeral=True)
            
            # 👤 유저의 개인 명성 조회
            user_data = db.get_user(uid)
            user_rep = user_data.get('fishing_reputation', 0) if user_data else 0

            # ⭐ [명성별 1회 최대 판매 한도 설정]
            if user_rep < 1000:
                max_limit = 30000        # 명성 1,000 미만: 최대 3만 원
                tier_name = "초보 낚시꾼"
            elif user_rep < 5000:
                max_limit = 100000       # 명성 5,000 미만: 최대 10만 원
                tier_name = "숙련된 낚시꾼"
            elif user_rep < 20000:
                max_limit = 200000       # 명성 20,000 미만: 최대 20만 원
                tier_name = "전문 낚시꾼"
            else:
                max_limit = 300000       # 명성 20,000 이상: 최대 30만 원
                tier_name = "전설의 낚시꾼"

            # 🏪 설치된 시설 중 가장 높은 물고기 가격 배율 찾기
            built_facilities = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')
            
            best_multiplier = 1.0
            if built_facilities:
                for f in built_facilities:
                    f_name = f['facility_name']
                    if f_name in FACILITIES:
                        f_mult = FACILITIES[f_name].get("effect", {}).get("fish_price_mult", 1.0)
                        if f_mult > best_multiplier:
                            best_multiplier = f_mult

            # 💰 총액 정산 (등급별 최대 상한선 적용)
            calculated_total = 0
            # 등급별 상한선 정의
            RARITY_CAPS = {
                "흔함": 5000,
                "희귀": 10000,
                "신종": 30000,
                "전설": 50000,
                "환상": 80000
            }

            for i in items:
                fish_price = int(i['length'] * i['price_per_cm'] * best_multiplier)
                # 아이템 데이터에 저장된 rarity를 기준으로 캡 적용 (없으면 기본 5,000원)
                fish_rarity = i.get('rarity', '흔함')
                cap_limit = RARITY_CAPS.get(fish_rarity, 5000)
                
                # 개별 물고기 가격에 등급별 캡 적용
                calculated_total += min(fish_price, cap_limit)
            
            # 🚨 [전체 한도 검사] 유저 명성 등급에 따른 1회 판매 총액 제한
            actual_earn = min(calculated_total, max_limit)
            is_capped = calculated_total > max_limit

            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (actual_earn, uid, gid))
                conn.execute("DELETE FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (uid, gid))
                conn.commit()
                
                # 📜 결과 임베드 메시지 구성
                embed = discord.Embed(title="💰 물고기 일괄 정산", color=discord.Color.green())
                embed.add_field(name="🎒 판매 수량", value=f"{len(items)}마리", inline=True)
                embed.add_field(name="🏅 현재 등급", value=f"{tier_name} (명성: {user_rep:,}점)", inline=True)
                
                if is_capped:
                    embed.add_field(name="⚠️ 정산 경고", value=f"정산 금액({calculated_total:,}원)이 현재 등급의 한도를 초과하여 **{max_limit:,}원**만 입금되었습니다!", inline=False)
                else:
                    embed.add_field(name="💸 획득 금액", value=f"**{actual_earn:,}원** 입금 완료", inline=True)

                if best_multiplier > 1.0:
                    embed.set_footer(text=f"상업 시설 효과로 판매 가격이 {best_multiplier}배 보너스 정산되었습니다.")

                await interaction.response.send_message(embed=embed)

            except Exception as e:
                conn.rollback()
                await interaction.response.send_message(f"❌ 판매 처리 중 오류가 발생했습니다. (에러: {e})", ephemeral=True)
        
        elif 액션 == "repair":
            g = db.execute_query("SELECT rod_durability, rod_level FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
            if not g: return await interaction.response.send_message("❌ 수리할 낚싯대가 없습니다!", ephemeral=True)
            
            max_d = 100 + (g['rod_level'] * 100)
            cost = (max_d - g['rod_durability']) * 20
            if cost <= 0: return await interaction.response.send_message("🛠️ 이미 완벽한 상태입니다.", ephemeral=True)
            if (db.get_user_cash(uid) or 0) < cost: return await interaction.response.send_message(f"❌ 수리비가 부족합니다! (필요: {cost:,}원)", ephemeral=True)
            
            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("UPDATE fishing_gear SET rod_durability = ? WHERE user_id = ? AND guild_id = ?", (max_d, uid, gid))
                conn.commit()
                await interaction.response.send_message(f"🔧 낚싯대 수리 완료! **{cost:,}원**을 지출했습니다.")
            except:
                conn.rollback()
                await interaction.response.send_message("❌ 수리 처리 중 오류가 발생했습니다.", ephemeral=True)

        elif 액션 == "starter":
            cost = 10000
            if (db.get_user_cash(uid) or 0) < cost: return await interaction.response.send_message("❌ 자금이 부족합니다!", ephemeral=True)
            if db.execute_query("SELECT 1 FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one'):
                return await interaction.response.send_message("⚠️ 이미 장비를 보유하고 있습니다.", ephemeral=True)

            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("INSERT INTO fishing_gear (user_id, guild_id, rod_level, rod_durability, bait_count) VALUES (?, ?, 0, 100, 20)", (uid, gid))
                conn.commit()
                await interaction.response.send_message("🎣 **초보자 세트** 구매 완료! (낚싯대 Lv.0, 미끼 20개)")
            except:
                conn.rollback()
                await interaction.response.send_message("❌ 구매 처리 실패!", ephemeral=True)

        elif 액션 == "buy_bait":
            # 낱개 가격 300원 설정
            PRICE_PER_BAIT = 300

            # 수량이 주어지지 않았거나 0 이하면 기본 1개로 설정
            buy_count = 수량 if (수량 and 수량 > 0) else 1 
            cost = PRICE_PER_BAIT * buy_count # 총비용 계산 (300원 * n개)

            if not db.execute_query("SELECT 1 FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one'):
                return await interaction.response.send_message("❌ 낚싯대가 없습니다! 초보자 세트를 먼저 구매하세요.", ephemeral=True)
                
            if (db.get_user_cash(uid) or 0) < cost: 
                return await interaction.response.send_message(f"❌ 자금이 부족합니다! (필요 자금: {cost:,}원)", ephemeral=True)
            
            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                
                # ✅ 계산된 buy_count만큼 미끼 개수를 증가시킵니다.
                conn.execute("UPDATE fishing_gear SET bait_count = bait_count + ? WHERE user_id = ? AND guild_id = ?", (buy_count, uid, gid))
                conn.commit()
                
                await interaction.response.send_message(f"🐛 **미끼 {buy_count}개**를 추가로 구매했습니다! (지출: {cost:,}원)")
            except:
                conn.rollback()
                await interaction.response.send_message("❌ 구매 처리 중 오류가 발생했습니다.", ephemeral=True)
                
    @app_commands.command(name="낚시장비강화", description="현금을 지불하여 낚싯대 및 미끼의 한계 레벨을 강화합니다.")
    @app_commands.choices(강화대상=[
        app_commands.Choice(name="🎣 낚싯대 강화 (내구도 한계치 및 등급 상승)", value="rod"),
        app_commands.Choice(name="🧪 미끼 등급 강화 (물고기 포획률 상승)", value="bait")
    ])
    async def upgrade_gear(self, interaction: discord.Interaction, 강화대상: str):
        db = self._get_db(interaction)
        uid, gid = str(interaction.user.id), str(interaction.guild_id)

        gear = db.execute_query("SELECT * FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
        if not gear:
            return await interaction.response.send_message("❌ 장비가 없습니다! 초보자 세트를 먼저 구매하세요.", ephemeral=True)

        current_cash = db.get_user_cash(uid) or 0
        conn = db.get_connection()

        try:
            conn.execute("BEGIN")
            if 강화대상 == "rod":
                current_level = gear['rod_level'] or 0
                if current_level >= 5:
                    return await interaction.response.send_message("❌ 낚싯대가 이미 마스터(5레벨) 단계입니다.", ephemeral=True)
                
                cost = (current_level + 1) * 10000 # 10000원 단위 증가
                if current_cash < cost:
                    return await interaction.response.send_message(f"❌ 강화 자금이 부족합니다. (비용: {cost:,}원)", ephemeral=True)

                # 레벨을 올리고 최대 내구도를 올려줌
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("UPDATE fishing_gear SET rod_level = rod_level + 1, rod_durability = rod_durability + 100 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                conn.commit()
                await interaction.response.send_message(f"🔥 낚싯대 강화 완료! **Lv.{current_level + 1}**이 되었습니다. (지출: {cost:,}원)")

            elif 강화대상 == "bait":
                current_level = gear['bait_level'] or 0
                if current_level >= 5:
                    return await interaction.response.send_message("❌ 미끼 배합술이 이미 마스터(5레벨) 단계입니다.", ephemeral=True)

                cost = (current_level + 1) * 5000
                if current_cash < cost:
                    return await interaction.response.send_message(f"❌ 강화 자금이 부족합니다. (비용: {cost:,}원)", ephemeral=True)

                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("UPDATE fishing_gear SET bait_level = bait_level + 1 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                conn.commit()
                await interaction.response.send_message(f"🧪 미끼 등급 상승 완료! **Lv.{current_level + 1}**이 되었습니다. (지출: {cost:,}원)")

        except Exception as e:
            conn.rollback()
            await interaction.response.send_message(f"❌ 강화 중 오류가 발생했습니다. (에러: {e})", ephemeral=True)

            # === 👑 [여기에 붙여넣으세요!] 관리자 전용 낚시 시스템 조작 명령어 ===
    
    @app_commands.command(name="낚시관리", description="[관리자 전용] 명성 수정 및 현재 채널의 공용/개인 낚시터 상태를 관리합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True) # 디스코드 메뉴 노출 설정
    @app_commands.choices(대상=[
        app_commands.Choice(name="👤 특정 유저 개인 명성 수정", value="user"),
        app_commands.Choice(name="🏞️ 현재 채널의 낚시터 명성 수정", value="channel"),
        app_commands.Choice(name="💰 현재 채널의 기본 매입가 수정", value="price"),
        app_commands.Choice(name="⚙️ 현재 채널의 낚시터 유형 설정 (버튼)", value="set_type"),
        app_commands.Choice(name="🧹 현재 채널 낚시 데이터 초기화 (공용화)", value="reset_channel") # 👈 추가된 부분
    ])
    async def admin_control(
        self, 
        interaction: discord.Interaction, 
        대상: str, 
        수치: Optional[int] = None, 
        유저: Optional[discord.Member] = None
    ):
        db = self._get_db(interaction)
        gid = str(interaction.guild_id)
        chid = str(interaction.channel_id)

        if 대상 == "user":
            if not 유저 or 수치 is None:
                return await interaction.response.send_message("❌ 유저 명성을 수정할 때는 '유저'와 '수치' 파라미터를 모두 입력해 주세요.", ephemeral=True)
            uid = str(유저.id)
            db.execute_query("UPDATE users SET fishing_reputation = ? WHERE user_id = ? AND guild_id = ?", (수치, uid, gid))
            await interaction.response.send_message(f"✅ <@{uid}> 유저의 개인 명성을 **{수치:,}점**으로 수정했습니다.", ephemeral=True)

        elif 대상 == "channel":
            if 수치 is None:
                return await interaction.response.send_message("❌ 낚시터 명성을 수정할 때는 '수치' 파라미터를 입력해 주세요.", ephemeral=True)
            self._ensure_ground_exists(db, chid, gid, interaction.channel.name)
            db.execute_query("UPDATE fishing_ground SET ground_reputation = ? WHERE channel_id = ? AND guild_id = ?", (수치, chid, gid))
            await interaction.response.send_message(f"✅ 이 채널(<#{chid}>)의 낚시터 명성을 **{수치:,}점**으로 수정했습니다.", ephemeral=True)

        elif 대상 == "set_type":
            self._ensure_ground_exists(db, chid, gid, interaction.channel.name)
            embed = discord.Embed(
                title="⚙️ 낚시터 유형 설정", 
                description="현재 채널을 어떤 낚시터로 지정할지 아래 버튼을 선택하세요.\n\n"
                            "- **공용:** 구매 불가능, 누구나 무료 이용\n"
                            "- **개인:** 유저들이 구매 가능, 주인이 사면 비공개 사유지화", 
                color=discord.Color.purple()
            )
            view = AdminGroundTypeView(interaction.user, db)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()

        elif 대상 == "price": 
            if 수치 is None or 수치 < 0:
                return await interaction.response.send_message("❌ 올바른 매입가 수치를 입력해 주세요.", ephemeral=True)
            self._ensure_ground_exists(db, chid, gid, interaction.channel.name)
            db.execute_query("UPDATE fishing_ground SET ground_price = ? WHERE channel_id = ? AND guild_id = ?", (수치, chid, gid))
            await interaction.response.send_message(f"✅ 이 채널(<#{chid}>)의 초기 매입가가 **{수치:,}원**으로 변경되었습니다.", ephemeral=True)

        elif 대상 == "reset_channel":
            self._ensure_ground_exists(db, chid, gid, interaction.channel.name)
            
            # 🔥 [추가] 현재 채널에서 낚시 중인 세션이나 락(Lock)이 있다면 메모리에서 강제 퇴출
            # 이 채널의 ID를 사용하는 게임 인스턴스를 찾아 세션을 파괴합니다.
            active_uids = list(active_sessions.keys())
            for u_id in active_uids:
                session = active_sessions.get(u_id)
                # 세션 객체 내부의 channel_id가 현재 채널과 일치하면 메모리에서 지웁니다.
                if hasattr(session, 'channel_id') and str(session.channel_id) == chid:
                    active_sessions.pop(u_id, None)
                    user_locks.pop(u_id, None)

            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                # 1. 낚시터 정보 초기화
                conn.execute(
                    "UPDATE fishing_ground SET owner_id = NULL, purchasable = 1, is_public = 1, "
                    "ground_type = '호수', entry_fee = 0, ground_reputation = 0, tier = 1 "
                    "WHERE channel_id = ? AND guild_id = ?", 
                    (chid, gid)
                )
                
                # 2. 시설 완전 철거 (DB 삭제)
                conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid))
                conn.commit()

                # 3. 비동기 채널명 원복 (429 Rate Limit 방지)
                async def safe_rename_reset():
                    try:
                        await interaction.channel.edit(name="🌊｜공용_낚시터")
                    except discord.HTTPException as e:
                        print(f"[경고] 초기화 채널명 변경 속도 제한 무시됨: {e}")

                asyncio.create_task(safe_rename_reset())

                await interaction.response.send_message(
                    f"🧹 <#{chid}> 채널의 DB 데이터, 시설 버프 및 **실시간 메모리 세션**이 완전히 초기화되었습니다!\n"
                    f"이제 깔끔한 기본 공용 낚시터 상태입니다."
                )
            except Exception as e:
                conn.rollback()
                await interaction.response.send_message(f"❌ 채널 초기화 중 DB 오류가 발생했습니다. (에러: {e})", ephemeral=True)

    @app_commands.command(name="낚시초기화", description="[관리자 전용] 이 서버의 모든 낚시 관련 데이터(장비, 인벤토리, 명성, 낚시터 등)를 초기화합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset_all_fishing_data(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚠️ 서버 낚시 데이터 전체 초기화 경고",
            description=(
                "이 명령어를 실행하면 서버 내 모든 유저의 **장비, 인벤토리, 낚시 명성, 소유한 낚시터 및 시설**이 완전히 삭제됩니다.\n"
                "삭제된 데이터는 **절대 복구할 수 없습니다.**\n\n"
                "정말로 초기화를 진행하시겠습니까?"
            ),
            color=discord.Color.red()
        )
        view = ResetConfirmView(interaction.user, self._get_db(interaction))
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
    def _ensure_ground_exists(self, db, chid: str, gid: str, channel_name: str):
        """낚시터가 DB에 없을 경우 기본값으로 생성해주는 헬퍼 메서드"""
        ground = db.execute_query(
            "SELECT 1 FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", 
            (chid, gid), 
            'one'
        )
        if not ground:
            db.execute_query(
                "INSERT INTO fishing_ground (channel_id, guild_id, channel_name) VALUES (?, ?, ?)", 
                (chid, gid, channel_name)
            )

    @tasks.loop(hours=24)
    async def auto_cleanup_inactive_grounds(self):
        """7일 방치 낚시터 회수: 50% 환불 & 다음 구매가 10만원 설정"""
        threshold_date = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d %H:%M:%S')
        
        for guild in self.bot.guilds:
            try:
                db = self.db_cog.get_manager(guild.id)
                targets = db.execute_query(
                    "SELECT * FROM fishing_ground WHERE owner_id IS NOT NULL AND last_activity < ?", 
                    (threshold_date,), 'all'
                )

                if not targets:
                    continue

                for ground in targets:
                    uid, chid = ground['owner_id'], ground['channel_id']
                    # ground_price를 기준으로 환불액 계산
                    refund_amount = int(ground['ground_price'] * 0.5)

                    try:
                        with db.get_connection() as conn:
                            # 3. 국고 환수 처리
                            conn.execute(
                                """UPDATE fishing_ground 
                                   SET owner_id = NULL, 
                                       pollution = 0, 
                                       is_public = 1, 
                                       ground_price = 100000, 
                                       last_activity = CURRENT_TIMESTAMP 
                                   WHERE channel_id = ?""", 
                                (chid,)
                            )
                            
                            # 4. 시설물 철거
                            conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, str(guild.id)))
                            
                            # 5. 기존 주인에게 50% 입금
                            conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (refund_amount, uid, str(guild.id)))
                        
                        print(f"🏛️ [국고환수] {guild.name} - {chid} 채널 회수 완료. (전주인 {uid} {refund_amount:,}원 환불)")
                        
                    except Exception as e:
                        print(f"❌ [{guild.name}] 국고 환수 중 오류 발생 (채널 {chid}): {e}")
            except Exception as e:
                print(f"❌ [{guild.name}] 국고 환수 루프 중 오류 발생: {e}")

async def setup(bot):
    await bot.add_cog(FishingSystemCog(bot))
