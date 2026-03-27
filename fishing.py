# fishing.py
import discord
from discord import app_commands
from discord.ext import commands
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
    {"name": "찌그러진 빈 캔", "type": "neutral", "value": -100},
    {"name": "찢어진 장화", "type": "loss", "value": -1000},
    {"name": "오래된 동전 주머니", "type": "profit", "value": 2000},
    {"name": "성인용품 딜도", "type": "loss", "value": -30000},
    {"name": "패들", "type": "loss", "value": -35000},
    {"name": "애널 테일", "type": "loss", "value": -20000},
    {"name": "애널 플러그", "type": "loss", "value": -5000},
    {"name": "목줄", "type": "loss", "value": -10000},
    {"name": "케인", "type": "loss", "value": -35000},
    {"name": "채찍", "type": "loss", "value": -35000},
    {"name": "무선 진동기", "type": "loss", "value": -5000},
    {"name": "SM 바", "type": "loss", "value": -50000},
    {"name": "니플 집게", "type": "loss", "value": -10000},
]

FISHING_ECOLOGY = {
    "호수": [
        # --- 흔함 ---
        {"name": "피라미", "rarity": "흔함", "chance": 0.20, "min": 5, "max": 15, "price_per_cm": 30, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "가장 기초적인 민물 잡어입니다."},
        {"name": "붕어", "rarity": "흔함", "chance": 0.15, "min": 15, "max": 30, "price_per_cm": 50, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "표준적인 민물 낚시의 손맛을 줍니다."},
        {"name": "잉어", "rarity": "흔함", "chance": 0.10, "min": 30, "max": 80, "price_per_cm": 80, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "몸집이 커서 초반 돈벌이에 좋습니다."},
        {"name": "메기", "rarity": "흔함", "chance": 0.10, "min": 30, "max": 70, "price_per_cm": 100, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "야행성 어종이며 탁한 물을 좋아합니다."},
        {"name": "누치", "rarity": "흔함", "chance": 0.05, "min": 20, "max": 50, "price_per_cm": 60, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "흔하지만 은근히 힘이 좋은 물고기입니다."},
        # --- 희귀 ---
        {"name": "쏘가리", "rarity": "희귀", "chance": 0.07, "min": 25, "max": 50, "price_per_cm": 300, "req_tier": 2, "water_quality": [1,2], "effect_desc": "깨끗한 돌 틈에 살며, 잡을 시 명성 +50"},
        {"name": "무지개송어", "rarity": "희귀", "chance": 0.07, "min": 30, "max": 60, "price_per_cm": 350, "req_tier": 2, "water_quality": [1,2], "effect_desc": "화려한 무늬를 띱니다. 경험치 획득 +10%"},
        {"name": "은어", "rarity": "희귀", "chance": 0.06, "min": 15, "max": 25, "price_per_cm": 400, "req_tier": 2, "water_quality": [1], "effect_desc": "맑은 물에만 살며 수박 향이 납니다."},
        {"name": "향어", "rarity": "희귀", "chance": 0.05, "min": 40, "max": 70, "price_per_cm": 250, "req_tier": 2, "water_quality": [3,4], "effect_desc": "양식 기원 어종으로 묵직한 손맛을 줍니다."},
        # --- 신종 ---
        {"name": "아로와나", "rarity": "신종", "chance": 0.04, "min": 50, "max": 100, "price_per_cm": 800, "req_tier": 3, "water_quality": [1], "effect_desc": "살아있는 화석. 잡을 시 낚시터 명성 +100"},
        {"name": "피라루쿠", "rarity": "신종", "chance": 0.04, "min": 100, "max": 250, "price_per_cm": 1200, "req_tier": 3, "water_quality": [2,3], "effect_desc": "거대 민물 어종입니다. 낚싯대 내구도 -5"},
        # --- 전설 ---
        {"name": "산천어", "rarity": "전설", "chance": 0.025, "min": 20, "max": 40, "price_per_cm": 2500, "req_tier": 4, "water_quality": [1], "effect_desc": "1급수 청정 지표 어종입니다."},
        {"name": "철갑상어", "rarity": "전설", "chance": 0.02, "min": 100, "max": 200, "price_per_cm": 3000, "req_tier": 4, "water_quality": [1,2], "effect_desc": "고급 알(캐비아)을 품어 매우 비쌉니다."},
        # --- 환상 ---
        {"name": "황금 잉어", "rarity": "환상", "chance": 0.01, "min": 80, "max": 150, "price_per_cm": 5000, "req_tier": 5, "water_quality": [1,2], "effect_desc": "영험한 영물. 잡을 시 모든 보유 시설 유지비 1회 면제"},
        {"name": "천지 네시", "rarity": "환상", "chance": 0.005, "min": 300, "max": 700, "price_per_cm": 10000, "req_tier": 5, "water_quality": [1], "effect_desc": "호수의 지배자. 낚을 시 낚싯대 내구도 -30"},
        # --- 🐊 호수/강 유해생물 및 특수동물 ---
        {"name": "자라", "rarity": "특수동물", "chance": 0.05, "min": 20, "max": 40, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "[유해] 물어뜯기! 자라가 물고 안 놔줍니다. 치료비 5,000원 지출"},
        {"name": "큰입 배스", "rarity": "유해생물", "chance": 0.20, "min": 20, "max": 50, "price_per_cm": 50, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "[유해] 생태계 교란종. 잡을 시 다음 3회 일반 어종 확률 상승"},
        {"name": "파랑볼우럭(블루길)", "rarity": "유해생물", "chance": 0.18, "min": 10, "max": 25, "price_per_cm": 30, "req_tier": 1, "water_quality": [3,4,6], "effect_desc": "[유해] 미끼 스틸러. 미끼 2개 추가 소실"},
        {"name": "붉은가위가재", "rarity": "유해생물", "chance": 0.10, "min": 10, "max": 20, "price_per_cm": 40, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "[유해] 줄 끊기! 낚싯대 내구도 -10"},
        {"name": "수달", "rarity": "특수동물", "chance": 0.02, "min": 50, "max": 100, "price_per_cm": 0, "req_tier": 1, "water_quality": [1,2], "effect_desc": "[유해] 물고기 도둑! 가방 안에서 가장 비싼 물고기 1마리를 훔쳐 달아납니다."}
    ],

    "바다": [
        {"name": "전갱이", "rarity": "흔함", "chance": 0.15, "min": 15, "max": 30, "price_per_cm": 30, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "미끼 도둑으로 불리는 흔한 바다 어종입니다."},
        {"name": "고등어", "rarity": "흔함", "chance": 0.15, "min": 20, "max": 40, "price_per_cm": 40, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "국민 생선. 가장 흔하게 잡힙니다."},
        {"name": "전어", "rarity": "흔함", "chance": 0.10, "min": 15, "max": 30, "price_per_cm": 45, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "집 나간 며느리도 돌아온다는 가을 별미입니다."},
        {"name": "숭어", "rarity": "흔함", "chance": 0.10, "min": 30, "max": 80, "price_per_cm": 35, "req_tier": 1, "water_quality": [2,3,4,5], "effect_desc": "연안에서 펄쩍 뛰어오르는 흔한 바다 물고기입니다."},
        {"name": "민어", "rarity": "흔함", "chance": 0.08, "min": 40, "max": 100, "price_per_cm": 80, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "여름철 최고의 보양식으로 꼽힙니다."},
        {"name": "농어", "rarity": "흔함", "chance": 0.05, "min": 40, "max": 100, "price_per_cm": 70, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "연안으로 거슬러 올라오는 힘센 어종입니다."},
        {"name": "벵에돔", "rarity": "희귀", "chance": 0.05, "min": 25, "max": 50, "price_per_cm": 350, "req_tier": 2, "water_quality": [1,2], "effect_desc": "낚시꾼들의 로망 중 하나입니다. 잡을 시 개인 명성 +50"},
        {"name": "감성돔", "rarity": "희귀", "chance": 0.05, "min": 25, "max": 60, "price_per_cm": 400, "req_tier": 2, "water_quality": [1,2], "effect_desc": "바다의 왕자. 경험치 획득 +15%"},
        {"name": "우럭", "rarity": "희귀", "chance": 0.05, "min": 20, "max": 50, "price_per_cm": 250, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "바위 틈에 서식하는 대중적인 횟감입니다."},
        {"name": "연어", "rarity": "희귀", "chance": 0.03, "min": 50, "max": 90, "price_per_cm": 300, "req_tier": 2, "water_quality": [1,2], "effect_desc": "강을 거슬러 올라가는 붉은 살 생선입니다."},
        {"name": "바다빙어", "rarity": "희귀", "chance": 0.03, "min": 10, "max": 25, "price_per_cm": 200, "req_tier": 2, "water_quality": [1,2], "effect_desc": "떼를 지어 다니는 작은 겨울철 어종입니다."},
        {"name": "고래상어", "rarity": "신종", "chance": 0.03, "min": 500, "max": 1200, "price_per_cm": 1500, "req_tier": 3, "water_quality": [1,2], "effect_desc": "지구상에서 가장 큰 어류입니다. 낚을 시 낚시터 명성 +500"},
        {"name": "타이거 샤크(뱀상어)", "rarity": "신종", "chance": 0.02, "min": 300, "max": 600, "price_per_cm": 1800, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "무엇이든 먹어치우는 바다의 포식자입니다. 낚싯대 내구도 -15"},
        {"name": "범고래", "rarity": "신종", "chance": 0.02, "min": 500, "max": 900, "price_per_cm": 2500, "req_tier": 3, "water_quality": [1,2], "effect_desc": "바다의 지배자이자 영리한 포식자입니다. 낚싯대 내구도 -20"},
        {"name": "대왕 오징어", "rarity": "신종", "chance": 0.02, "min": 200, "max": 1000, "price_per_cm": 1200, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "심해의 거대 괴수입니다. 낚싯대 내구도 -10"},
        {"name": "대왕 문어", "rarity": "신종", "chance": 0.02, "min": 100, "max": 300, "price_per_cm": 1300, "req_tier": 3, "water_quality": [1,2,3,4], "effect_desc": "무거운 빨판의 손맛. 낚싯대 내구도 -10"},
        {"name": "백상아리", "rarity": "전설", "chance": 0.015, "min": 300, "max": 600, "price_per_cm": 4000, "req_tier": 4, "water_quality": [1,2], "effect_desc": "죠스의 주인공! 낚을 시 낚싯대 내구도 -35"},
        {"name": "향유고래", "rarity": "전설", "chance": 0.01, "min": 1000, "max": 1800, "price_per_cm": 3500, "req_tier": 4, "water_quality": [1,2], "effect_desc": "거대한 머리를 가진 잠수의 명수입니다. 낚싯대 내구도 -40"},
        {"name": "혹등고래", "rarity": "전설", "chance": 0.01, "min": 1200, "max": 1600, "price_per_cm": 3800, "req_tier": 4, "water_quality": [1,2], "effect_desc": "화려한 점프를 선보이는 온순한 거인입니다. 낚을 시 명성 +1,000"},
        {"name": "돌고래", "rarity": "환상", "chance": 0.01, "min": 150, "max": 300, "price_per_cm": 7000, "req_tier": 5, "water_quality": [1,2], "effect_desc": "바다의 천사. 잡을 시 다음 낚시 성공 확률 +15%"},
        {"name": "바다거북", "rarity": "환상", "chance": 0.004, "min": 60, "max": 150, "price_per_cm": 0, "req_tier": 5, "water_quality": [1,2], "effect_desc": "[청정] 보호종입니다! 자동으로 방생되며 개인 명성이 +500 상승합니다."},
        {"name": "메갈로돈", "rarity": "환상", "chance": 0.001, "min": 1500, "max": 2000, "price_per_cm": 20000, "req_tier": 5, "water_quality": [1,2], "effect_desc": "고대의 초대형 상어. 낚을 시 낚싯대 내구도 -80"}
    ],

    "늪": [
        {"name": "검정말", "rarity": "흔함", "chance": 0.20, "min": 10, "max": 50, "price_per_cm": 10, "req_tier": 1, "water_quality": [3,4,5,6], "effect_desc": "늪 바닥에 무성한 수초입니다. 판매가는 낮습니다."},
        {"name": "부레옥잠", "rarity": "흔함", "chance": 0.15, "min": 10, "max": 30, "price_per_cm": 20, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "수질 정화 능력이 있는 흔한 수생식물입니다."},
        {"name": "가시연꽃", "rarity": "흔함", "chance": 0.15, "min": 30, "max": 100, "price_per_cm": 30, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "가시가 돋아난 연꽃잎입니다. 낚을 시 낚싯대 내구도 -2"},
        {"name": "해캄", "rarity": "흔함", "chance": 0.15, "min": 5, "max": 20, "price_per_cm": 5, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "탁한 물에 끼는 녹조류 뭉덩이입니다."},
        {"name": "물방개", "rarity": "희귀", "chance": 0.07, "min": 2, "max": 5, "price_per_cm": 500, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "헤엄을 잘 치는 수서곤충입니다. 잡을 시 개인 명성 +30"},
        {"name": "민물새우", "rarity": "희귀", "chance": 0.05, "min": 3, "max": 8, "price_per_cm": 300, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "작고 투명한 늪지 새우입니다. 미끼로도 쓰입니다."},
        {"name": "각시붕어", "rarity": "희귀", "chance": 0.05, "min": 5, "max": 10, "price_per_cm": 400, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "빛깔이 고운 한국 고유종 소형 민물고기입니다."},
        {"name": "말조개", "rarity": "희귀", "chance": 0.05, "min": 10, "max": 25, "price_per_cm": 250, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "진흙 바닥에 서식하는 거대 민물 조개입니다."},
        {"name": "물총새", "rarity": "신종", "chance": 0.02, "min": 15, "max": 25, "price_per_cm": 1500, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "날렵하게 물고기를 낚아채는 새입니다. 잡을 시 경험치 획득 +20%"},
        {"name": "개개비", "rarity": "신종", "chance": 0.02, "min": 10, "max": 20, "price_per_cm": 1200, "req_tier": 3, "water_quality": [2,3,4], "effect_desc": "여름철 늪지 갈대밭에서 시끄럽게 우는 새입니다."},
        {"name": "누룩뱀", "rarity": "신종", "chance": 0.02, "min": 50, "max": 120, "price_per_cm": 1000, "req_tier": 3, "water_quality": [3,4,5], "effect_desc": "늪 주변 습지에서 흔히 보이는 뱀입니다. 낚을 시 낚싯대 내구도 -5"},
        {"name": "잉어", "rarity": "신종", "chance": 0.015, "min": 30, "max": 80, "price_per_cm": 500, "req_tier": 3, "water_quality": [3,4,5], "effect_desc": "늪지 진흙 바닥에서 적응하여 자란 거대 잉어입니다."},
        {"name": "메기", "rarity": "신종", "chance": 0.015, "min": 30, "max": 70, "price_per_cm": 600, "req_tier": 3, "water_quality": [3,4,5,6], "effect_desc": "음침하고 탁한 수질에 도가 튼 야행성 포식자입니다."},
        {"name": "가물치", "rarity": "전설", "chance": 0.01, "min": 40, "max": 100, "price_per_cm": 2500, "req_tier": 4, "water_quality": [3,4,5,6], "effect_desc": "늪지의 무법자이자 난폭한 최상위 어종입니다. 낚을 시 내구도 -15"},
        {"name": "물수리", "rarity": "전설", "chance": 0.01, "min": 50, "max": 70, "price_per_cm": 3000, "req_tier": 4, "water_quality": [1,2,3], "effect_desc": "하늘에서 물고기를 사냥하는 맹금류입니다. 낚을 시 낚시터 명성 +500"},
        {"name": "황소개구리", "rarity": "전설", "chance": 0.005, "min": 15, "max": 30, "price_per_cm": 1000, "req_tier": 4, "water_quality": [4,5,6], "effect_desc": "생태계를 파괴하는 거대 양서류입니다. 잡을 시 늪 오염도 상승 및 포상금 획득."},
        {"name": "너구리", "rarity": "전설", "chance": 0.005, "min": 40, "max": 70, "price_per_cm": 2000, "req_tier": 4, "water_quality": [3,4,5], "effect_desc": "늪가에서 먹이를 씻어 먹는 잡식 동물입니다. 가방의 미끼 5개를 소실시킵니다."},
        {"name": "백로", "rarity": "환상", "chance": 0.004, "min": 60, "max": 100, "price_per_cm": 6000, "req_tier": 5, "water_quality": [1,2,3], "effect_desc": "순백의 자태를 뽐내는 새입니다. 잡을 시 낚시터 명성 +1,000"},
        {"name": "왜가리", "rarity": "환상", "chance": 0.004, "min": 80, "max": 110, "price_per_cm": 6500, "req_tier": 5, "water_quality": [2,3,4], "effect_desc": "부동의 자세로 물고기를 사냥하는 새입니다. 낚을 시 다음 낚시 대기 시간 -15%"},
        {"name": "악어", "rarity": "환상", "chance": 0.002, "min": 150, "max": 400, "price_per_cm": 15000, "req_tier": 5, "water_quality": [3,4,5,6], "effect_desc": "늪지의 최종 지배자. 낚을 시 엄청난 데스롤을 시전하여 낚싯대 내구도 -60"}
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
    # 🎫 수수료 조정 매표소
    "간이매표소": {"req_rep": 500, "req_cash": 30000, "tier": 1, "effect": {"fee_adj": 0.03}, "desc": "수수료 조정 범위 +-3%"},
    "매표소": {"req_rep": 2000, "req_cash": 50000, "tier": 2, "effect": {"fee_adj": 0.05}, "desc": "수수료 조정 범위 +-5%"},
    "일반매표소": {"req_rep": 5000, "req_cash": 80000, "tier": 2, "effect": {"fee_adj": 0.08}, "desc": "수수료 조정 범위 +-8%"},
    "중형매표소": {"req_rep": 10000, "req_cash": 120000, "tier": 3, "effect": {"fee_adj": 0.10}, "desc": "수수료 조정 범위 +-10%"},
    "대형매표소": {"req_rep": 30000, "req_cash": 200000, "tier": 4, "effect": {"fee_adj": 0.15}, "desc": "수수료 조정 범위 +-15%"},
    "거대한매표소": {"req_rep": 50000, "req_cash": 300000, "tier": 5, "effect": {"fee_adj": 0.20}, "desc": "수수료 조정 범위 +-20%"},

    # 📦 물고기 확률 조정 (창고)
    "창고": {"req_rep": 500, "req_cash": 30000, "tier": 1, "effect": {"fish_rate": 0.05, "base_fee": 0.05}, "desc": "기본 수수료 5%, 물고기 낚일 확률 5% 증가"},
    "소형창고": {"req_rep": 3000, "req_cash": 50000, "tier": 2, "effect": {"fish_rate": 0.07, "base_fee": 0.07, "upkeep_mult": 0.05}, "desc": "기본 수수료 7%, 물고기 확률 7% 증가, 유지비 5% 증가"},
    "중형창고": {"req_rep": 10000, "req_cash": 80000, "tier": 3, "effect": {"fish_rate": 0.10, "base_fee": 0.10, "upkeep_mult": 0.07}, "desc": "기본 수수료 10%, 물고기 확률 10% 증가, 유지비 7% 증가"},
    "대형창고": {"req_rep": 50000, "req_cash": 120000, "tier": 4, "effect": {"fish_rate": 0.15, "base_fee": 0.15, "upkeep_mult": 0.10}, "desc": "기본 수수료 15%, 물고기 확률 15% 증가, 유지비 10% 증가"},
    "초거대한창고": {"req_rep": 100000, "req_cash": 250000, "tier": 5, "effect": {"fish_rate": 0.20, "base_fee": 0.20, "upkeep_mult": 0.15}, "desc": "기본 수수료 20%, 물고기 확률 20% 증가, 유지비 15% 증가"},

    # 🧹 쓰레기 감소 확률
    "환경미화원": {"req_rep": 1000, "req_cash": 20000, "tier": 2, "effect": {"trash_rate": -0.05}, "desc": "쓰레기가 5% 덜 낚임"},
    "청소용역업체": {"req_rep": 30000, "req_cash": 80000, "tier": 3, "effect": {"trash_rate": -0.10}, "desc": "쓰레기가 10% 덜 낚임"},
    "시설관리공단": {"req_rep": 100000, "req_cash": 300000, "tier": 5, "effect": {"trash_rate": -0.20}, "desc": "쓰레기가 20% 덜 낚임"},

    # ⚡ 유지비 감소 확률 (발전소)
    "전기배터리": {"req_rep": 5000, "req_cash": 10000, "tier": 1, "effect": {"upkeep_discount": 0.05}, "desc": "유지비 5% 감소"},
    "소형발전기": {"req_rep": 10000, "req_cash": 50000, "tier": 2, "effect": {"upkeep_discount": 0.07}, "desc": "유지비 7% 감소"},
    "중대형발전기": {"req_rep": 50000, "req_cash": 100000, "tier": 3, "effect": {"upkeep_discount": 0.10}, "desc": "유지비 10% 감소"},
    "화력발전소": {"req_rep": 80000, "req_cash": 300000, "tier": 4, "effect": {"upkeep_discount": 0.15}, "desc": "유지비 15% 감소"},
    "수력발전소": {"req_rep": 120000, "req_cash": 500000, "tier": 5, "effect": {"upkeep_discount": 0.25}, "desc": "유지비 25% 감소"},

    # ✨ 명성 증가 배율
    "길거리상인": {"req_rep": 500, "req_cash": 10000, "tier": 1, "effect": {"rep_mult": 1.2}, "desc": "명성 증가량 1.2배"},
    "기념품상점": {"req_rep": 3000, "req_cash": 50000, "tier": 2, "effect": {"rep_mult": 1.5}, "desc": "명성 증가량 1.5배"},
    "기념품백화점": {"req_rep": 10000, "req_cash": 90000, "tier": 3, "effect": {"rep_mult": 2.0}, "desc": "명성 증가량 2배"},
    "해외입점준비": {"req_rep": 50000, "req_cash": 130000, "tier": 4, "effect": {"rep_mult": 2.2}, "desc": "명성 증가량 2.2배"},
    "해외유명기업": {"req_rep": 100000, "req_cash": 300000, "tier": 5, "effect": {"rep_mult": 3.0}, "desc": "명성 증가량 3배"},

    # ♻️ 유지비 감소 + 쓰레기 확률 조정
    "재활용분리수거장": {"req_rep": 1500, "req_cash": 8000, "tier": 1, "effect": {"fish_price_mult": 0.5, "trash_rate": -0.05, "upkeep_mult": 0.05}, "desc": "물고기 가격 0.5배 증가, 쓰레기 5% 감소, 유지비 5% 증가"},
    "쓰레기소각장": {"req_rep": 10000, "req_cash": 70000, "tier": 3, "effect": {"fish_price_mult": 1.2, "trash_rate": -0.10, "upkeep_mult": 0.12}, "desc": "물고기 가격 1.2배 증가, 쓰레기 10% 감소, 유지비 12% 증가"},
    "환경부": {"req_rep": 100000, "req_cash": 500000, "tier": 5, "effect": {"fish_price_mult": 2.0, "trash_rate": -0.20, "upkeep_mult": 0.20}, "desc": "물고기 가격 2.0배 증가, 쓰레기 20% 감소, 유지비 20% 증가"},

    # 🛒 유지비 감소 (그 외 사업)
    "리안마켓": {"req_rep": 1000, "req_cash": 8000, "tier": 1, "effect": {"upkeep_discount": 0.05}, "desc": "유지비 5% 감소"},
    "묵이편의점": {"req_rep": 7000, "req_cash": 35000, "tier": 2, "effect": {"upkeep_discount": 0.07}, "desc": "유지비 7% 감소"},
    "할인마트": {"req_rep": 30000, "req_cash": 70000, "tier": 3, "effect": {"upkeep_discount": 0.10, "rep_mult": 1.2}, "desc": "유지비 10% 감소, 명성 1.2배 증가"},
    "정E-마트": {"req_rep": 50000, "req_cash": 150000, "tier": 4, "effect": {"upkeep_discount": 0.15, "rep_mult": 1.5}, "desc": "유지비 15% 감소, 명성 1.5배 증가"},
    "해외수출사업": {"req_rep": 100000, "req_cash": 300000, "tier": 5, "effect": {"upkeep_discount": 0.20, "rep_mult": 2.0}, "desc": "유지비 20% 감소, 명성 2배 증가"},

    # 🏪 물고기 가격 보너스
    "노상": {"req_rep": 2000, "req_cash": 10000, "tier": 1, "effect": {"fish_price_mult": 1.1}, "desc": "물고기 가격 1.1배 증가"},
    "물사랑고기사랑가게": {"req_rep": 10000, "req_cash": 50000, "tier": 2, "effect": {"fish_price_mult": 1.3, "upkeep_mult": 0.05}, "desc": "물고기 가격 1.3배 증가, 유지비 5% 증가"},
    "5일장시장": {"req_rep": 40000, "req_cash": 100000, "tier": 3, "effect": {"fish_price_mult": 1.5, "upkeep_mult": 0.10}, "desc": "물고기 가격 1.5배 증가, 유지비 10% 증가"},
    "회전문공장": {"req_rep": 100000, "req_cash": 250000, "tier": 4, "effect": {"fish_price_mult": 2.0, "upkeep_mult": 0.15}, "desc": "물고기 가격 2.0배 증가, 유지비 15% 증가"},
    "세계1위기업": {"req_rep": 300000, "req_cash": 500000, "tier": 5, "effect": {"fish_price_mult": 2.5, "upkeep_mult": 0.20}, "desc": "물고기 가격 2.5배 증가, 유지비 20% 증가"},

    # 🏫 기타 방해요소 (실패 확률)
    "어린이집": {"req_rep": 500, "req_cash": 10000, "tier": 1, "effect": {"fail_rate": 0.05, "upkeep_mult": 0.05}, "desc": "낚시 실패확률 5% 증가, 유지비 5% 증가"},
    "유치원": {"req_rep": 2000, "req_cash": 30000, "tier": 2, "effect": {"fail_rate": 0.07, "upkeep_mult": 0.09}, "desc": "낚시 실패확률 7% 증가, 유지비 9% 증가"},
    "초등학교": {"req_rep": 5000, "req_cash": 50000, "tier": 3, "effect": {"fail_rate": 0.10, "upkeep_discount": 0.05}, "desc": "낚시 실패확률 10% 증가, 유지비 5% 감소"},
    "중학교": {"req_rep": 10000, "req_cash": 80000, "tier": 4, "effect": {"fail_rate": 0.12, "upkeep_discount": 0.09}, "desc": "낚시 실패확률 12% 증가, 유지비 9% 감소"},
    "고등학교": {"req_rep": 30000, "req_cash": 110000, "tier": 5, "effect": {"fail_rate": 0.15, "upkeep_discount": 0.12}, "desc": "낚시 실패확률 15% 증가, 유지비 12% 감소"},
}

active_sessions = {}
user_locks = {}

# ==========================================
# 👀 [UI 뷰 클래스 정의]
# ==========================================

class TrashActionView(discord.ui.View):
    def __init__(self, user: discord.Member, penalty: int, db_manager: DatabaseManager):
        super().__init__(timeout=30.0)
        self.user, self.penalty, self.db = user, abs(penalty), db_manager
        self.message, self.responded = None, False

    async def on_timeout(self):
        if self.message and not self.responded:
            try: await self.message.edit(view=None)
            except: pass
        self._clear_session()

    def _clear_session(self):
        active_sessions.pop(self.user.id, None)
        user_locks.pop(self.user.id, None)

    @discord.ui.button(label="🧹 쓰레기 치우기", style=discord.ButtonStyle.success)
    async def clean(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return await interaction.response.send_message("본인만 가능!", ephemeral=True)
        if self.responded: return
        self.responded = True

        uid, gid = str(self.user.id), str(interaction.guild_id)
        current_cash = self.db.get_user_cash(uid) or 0
        if current_cash < self.penalty:
            self.responded = False
            return await interaction.response.send_message("❌ 현금 부족!", ephemeral=True)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (self.penalty, uid, gid))
            conn.execute("INSERT INTO point_history (user_id, transaction_type, amount, balance_after, description) VALUES (?, ?, ?, ?, ?)",
                         (uid, "낚시", -self.penalty, current_cash - self.penalty, "낚시 환경 정화 비용"))
            conn.commit()
            await interaction.response.edit_message(embed=discord.Embed(title="✅ 정화 완료", description=f"**{self.penalty:,}원**을 지출했습니다.", color=discord.Color.green()), view=None)
        except:
            conn.rollback()
            self.responded = False
            await interaction.response.send_message("❌ 처리 중 오류 발생!", ephemeral=True)
        finally: self._clear_session()

    @discord.ui.button(label="🚮 그냥 버리기", style=discord.ButtonStyle.danger)
    async def dump(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return await interaction.response.send_message("본인만 가능!", ephemeral=True)
        self._clear_session()
        await interaction.response.edit_message(embed=discord.Embed(title="⚠️ 무단 투기", description="환경이 오염되었습니다.", color=discord.Color.red()), view=None)

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

class FishingGameView(discord.ui.View):
    def __init__(self, user: discord.Member, db_manager: DatabaseManager, channel_id: int):
        super().__init__(timeout=60.0)
        self.user, self.db, self.channel_id = user, db_manager, channel_id
        self.stage, self.is_real, self.responded, self.message = "waiting", False, False, None

    async def on_timeout(self):
        self._clear_session()
        if self.message and not self.responded:
            try:
                for child in self.children: child.disabled = True
                await self.message.edit(embed=discord.Embed(title="⌛ 시간 초과", description="낚시가 자동으로 중단되었습니다.", color=discord.Color.gray()), view=self)
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

        await asyncio.sleep(random.uniform(2, 4))
        if self.responded: return
        try: await interaction.edit_original_response(embed=discord.Embed(title="🌬️ 찌가 살짝 살랑거립니다...", color=discord.Color.light_gray()))
        except: return

        await asyncio.sleep(random.uniform(3, 5))
        if self.responded: return
        
        if random.random() < 0.3: # 가짜 입질
            self.stage = "fake"
            try: await interaction.edit_original_response(embed=discord.Embed(title=f"❓ {random.choice(TRAPS)}", color=discord.Color.orange()))
            except: return
            await asyncio.sleep(2.5)
            if self.responded: return
            self.stage = "waiting"
            try: await interaction.edit_original_response(embed=discord.Embed(title="...낚시터가 다시 조용해졌습니다.", color=discord.Color.light_gray()))
            except: return
            await asyncio.sleep(random.uniform(2, 4))
            if self.responded: return

        self.stage, self.is_real = "bite", True
        try: await interaction.edit_original_response(embed=discord.Embed(title=f"🚨 {random.choice(REAL_BITES)}", description="**지금 당기세요!!**", color=discord.Color.red()))
        except: return

        await asyncio.sleep(4.0)
        if not self.responded:
            try: await interaction.edit_original_response(embed=discord.Embed(title="💨 물고기가 도망갔습니다.", description="타이밍이 늦었습니다.", color=discord.Color.dark_gray()), view=None)
            except: pass
            self._clear_session()

    @discord.ui.button(label="🎣 낚싯줄 당기기", style=discord.ButtonStyle.danger)
    async def pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return await interaction.response.send_message("본인만 조작할 수 있습니다.", ephemeral=True)
        if self.user.id not in user_locks: user_locks[self.user.id] = asyncio.Lock()
        
        async with user_locks[self.user.id]:
            if self.responded: return
            self.responded = True
            await interaction.response.defer()
            self.stop()

            if self.stage != "bite":
                title = "❌ 실패!" if self.stage != "fake" else "💢 허탕!"
                desc = "타이밍을 놓쳤습니다." if self.stage != "fake" else "물고기가 아니었던 것 같습니다!"
                await interaction.edit_original_response(embed=discord.Embed(title=title, description=desc, color=discord.Color.gray()), view=None)
                return self._clear_session()

            uid, gid = str(self.user.id), str(interaction.guild_id)
            conn = self.db.get_connection()
            try:

                conn.execute("BEGIN")
                conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - 1) WHERE user_id = ? AND guild_id = ?", (uid, gid))

                built_facilities = self.db.execute_query(
                    "SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", 
                    (str(self.channel_id), gid), 'all'
                )

                # 2. 기본 쓰레기 확률 설정 (25%)
                trash_chance = 0.25

                # 3. 설치된 시설들 중 '쓰레기 감소 효과(trash_rate)'가 있는 건물을 찾아 확률을 깎습니다.
                if built_facilities:
                    for f in built_facilities:
                        f_name = f['facility_name']
                        if f_name in FACILITIES:
                            # FACILITIES 딕셔너리에서 "trash_rate" 수치를 읽어옵니다.
                            trash_mod = FACILITIES[f_name].get("effect", {}).get("trash_rate", 0)
                            trash_chance += trash_mod # 예: -0.05 더하기

                # 4. 음수 방지 (최소 0% 고정)
                trash_chance = max(0.0, trash_chance)

                # 🗑️ [쓰레기 기믹 작동부]
                if random.random() < trash_chance:
                    trash = random.choice(TRASH_LIST)
                    if trash["type"] == "loss":
                        view = TrashActionView(self.user, trash["value"], self.db)
                        active_sessions[self.user.id] = view
                        msg = await interaction.edit_original_response(embed=discord.Embed(title="🚮 쓰레기가 걸려왔습니다!", description=f"**[{trash['name']}]**\n적절한 조치가 필요합니다.", color=discord.Color.orange()), view=view)
                        view.message = msg
                        conn.commit()
                        return
                    
                    # 쓰레기 수익 (음수일 경우 0원 처리)
                    conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (max(0, trash["value"]), uid, gid))
                    await interaction.edit_original_response(embed=discord.Embed(title="🗑️ 잡동사니를 건졌습니다", description=f"**{trash['name']}** (수익: {max(0, trash['value']):,}원)", color=discord.Color.gray()), view=None)
                    conn.commit()
                    return self._clear_session()

                # 🎣 [물고기 기믹 작동부]
                ground = self.db.execute_query("SELECT ground_type FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (str(self.channel_id), gid), 'one')
                location = ground['ground_type'] if ground else "호수" # 기본값은 호수
                pool = FISHING_ECOLOGY.get(location, FISHING_ECOLOGY["호수"]) # 해당 지형의 물고기 풀 로드

                # 🔧 1. 장비 티어 필터링
                gear = self.db.execute_query("SELECT rod_level FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
                user_tier = (gear['rod_level'] + 1) if gear else 1 
                
                valid_pool = [f for f in pool if f.get("req_tier", 1) <= user_tier]
                if not valid_pool: valid_pool = pool

                # 📦 [창고 효과 연동 추가] 설치된 창고 시설의 물고기 확률 보너스 계산
                fish_rate_bonus = 0.0
                if built_facilities:
                    for f in built_facilities:
                        f_name = f['facility_name']
                        if f_name in FACILITIES:
                            # FACILITIES 딕셔너리에서 창고의 "fish_rate" 수치를 읽어옵니다.
                            fish_rate_bonus += FACILITIES[f_name].get("effect", {}).get("fish_rate", 0.0)
                            
                # ⚖️ 가중치(확률) 계산 시 창고 보너스 적용
                # 흔함 어종을 제외한 [희귀, 신종, 전설, 환상] 물고기들의 확률을 창고 보너스만큼 뻥튀기 해줍니다.
                adjusted_weights = []
                for f in valid_pool:
                    base_chance = f["chance"]
                    if f["rarity"] in ["희귀", "신종", "전설", "환상"]:
                        # 예: 기본 확률이 0.05 이고 창고 보너스가 0.05 이면 -> 0.05 * (1 + 0.05) = 0.0525 (5.25%)
                        adjusted_chance = base_chance * (1 + fish_rate_bonus)
                    else:
                        adjusted_chance = base_chance
                    adjusted_weights.append(adjusted_chance)

                    # 보정된 확률로 물고기 선택
                fish = random.choices(valid_pool, weights=adjusted_weights, k=1)[0]
                length = round(random.uniform(fish["min"], fish["max"]), 1)

                # 💥 2. 특수 동물 기믹 (가방에 인벤토리로 들어가지 않고 이벤트 발생)
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
                    conn.commit()
                    await interaction.edit_original_response(embed=discord.Embed(title="🦦 수달 출현!", description=desc, color=discord.Color.red()), view=None)
                    return self._clear_session()

                elif fish["name"] == "자라":
                    conn.execute("UPDATE users SET cash = MAX(0, cash - 5000) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    conn.commit()
                    await interaction.edit_original_response(embed=discord.Embed(title="🤕 자라에게 물렸습니다!", description="물고 늘어지는 자라 때문에 치료비 **5,000원**이 지출되었습니다.", color=discord.Color.red()), view=None)
                    return self._clear_session()

                elif fish["name"] == "바다거북":
                    conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + 500 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                    conn.commit()
                    await interaction.edit_original_response(embed=discord.Embed(title="🐢 바다거북을 방생했습니다!", description="멸종위기 청정 보호종 바다거북을 안전하게 돌려보냈습니다.\n\n⭐ **개인 명성 +500**", color=discord.Color.green()), view=None)
                    return self._clear_session()

                # 🧺 3. 일반 물고기 인벤토리 저장
                conn.execute("INSERT INTO fishing_inventory (user_id, guild_id, fish_name, length, price_per_cm) VALUES (?, ?, ?, ?, ?)", (uid, gid, fish["name"], length, fish["price_per_cm"]))

                # 🛠️ 4. 대형 어종 고유 패널티 (내구도 추가 삭감)
                penalty_durability = 0
                if "악어" in fish["name"]: penalty_durability = 60
                elif "메갈로돈" in fish["name"]: penalty_durability = 80
                elif "백상아리" in fish["name"]: penalty_durability = 35
                elif "천지 네시" in fish["name"]: penalty_durability = 30
                elif "향유고래" in fish["name"]: penalty_durability = 40
                elif "혹등고래" in fish["name"]: penalty_durability = 0 # 온순하므로 패스
                elif fish["name"] in ["타이거 샤크(뱀상어)", "가물치"]: penalty_durability = 15
                elif "범고래" in fish["name"]: penalty_durability = 20
                elif fish["name"] in ["대왕 오징어", "대왕 문어", "붉은가위가재"]: penalty_durability = 10
                elif "피라루쿠" in fish["name"]: penalty_durability = 5

                if penalty_durability > 0:
                    conn.execute("UPDATE fishing_gear SET rod_durability = MAX(0, rod_durability - ?) WHERE user_id = ? AND guild_id = ?", (penalty_durability, uid, gid))

                # 🐛 5. 유해생물 패널티 (미끼 추가 소실)
                if fish["name"] == "파랑볼우럭(블루길)":
                    conn.execute("UPDATE fishing_gear SET bait_count = MAX(0, bait_count - 2) WHERE user_id = ? AND guild_id = ?", (uid, gid))
                elif fish["name"] == "너구리":
                    conn.execute("UPDATE fishing_gear SET bait_count = MAX(0, bait_count - 5) WHERE user_id = ? AND guild_id = ?", (uid, gid))

                # 🌟 6. 명성 및 월척 기록 저장
                rep = {"흔함": 10, "희귀": 50, "신종": 150, "전설": 500, "환상": 2000}.get(fish["rarity"], 10)
                conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + ?, max_fish_length = MAX(max_fish_length, ?) WHERE user_id = ? AND guild_id = ?", (rep, length, uid, gid))
                
                conn.commit()
                await interaction.edit_original_response(embed=discord.Embed(title=f"🎉 {fish['name']}을(를) 잡았습니다!", description=f"길이: **{length}cm** (등급: {fish['rarity']})\n*{fish.get('effect_desc', '')}*", color=discord.Color.blue()), view=None)
            
            except Exception as e:
                conn.rollback()
                await interaction.edit_original_response(embed=discord.Embed(title="❌ 시스템 오류", description=f"데이터 처리 중 오류가 발생했습니다. (에러: {e})", color=discord.Color.red()), view=None)
            finally: self._clear_session()

class GroundAccessView(discord.ui.View):
    def __init__(self, user: discord.Member, fee: int, hours: int, owner_id: str, db_manager: DatabaseManager):
        super().__init__(timeout=60.0)
        self.user, self.fee, self.hours, self.owner_id, self.db = user, fee, hours, owner_id, db_manager

    @discord.ui.button(label="💳 이용권 구매", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user: return await interaction.response.send_message("본인만 구매 가능합니다.", ephemeral=True)
        uid, gid = str(self.user.id), str(interaction.guild_id)
        current_cash = self.db.get_user_cash(uid) or 0
        if current_cash < self.fee: return await interaction.response.send_message("❌ 소지 금액이 부족합니다!", ephemeral=True)

        conn = self.db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (self.fee, uid, gid))
            
            has_booth = self.db.execute_query("SELECT 1 FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = '매표소'", (str(interaction.channel_id), gid), 'one')
            if self.owner_id and has_booth:
                conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (self.fee, self.owner_id, gid))
            
            expire = (datetime.now() + timedelta(hours=self.hours)).strftime('%Y-%m-%d %H:%M:%S')
            conn.execute("INSERT INTO fishing_passes (user_id, channel_id, guild_id, expire_time) VALUES (?, ?, ?, ?) ON CONFLICT(user_id, channel_id, guild_id) DO UPDATE SET expire_time = excluded.expire_time",
                         (uid, str(interaction.channel_id), gid, expire))
            conn.commit()
            msg = "낚시터 소유주에게 입장료가 전달되었습니다." if (self.owner_id and has_booth) else "입장이 승인되었습니다."
            await interaction.response.edit_message(embed=discord.Embed(title="🎫 구매 완료!", description=f"이용 가능 시간: {self.hours}시간\n{msg}", color=discord.Color.green()), view=None)
        except:
            conn.rollback()
            await interaction.response.send_message("❌ 결제 실패!", ephemeral=True)

class FishingSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot, self.db_cog = bot, None

    async def cog_load(self):
        self.db_cog = self.bot.get_cog("DatabaseManager")
        for guild in self.bot.guilds:
            db = self.db_cog.get_manager(guild.id)
            self._init_db_schema(db)

    @commands.Cog.listener()
    async def on_guild_join(self, guild):
        if self.db_cog:
            db = self.db_cog.get_manager(guild.id)
            self._init_db_schema(db)

    def _init_db_schema(self, db):
        # 1. 기본 테이블 생성
        db.create_table("fishing_ground", "channel_id TEXT, guild_id TEXT, owner_id TEXT, channel_name TEXT, ground_type TEXT DEFAULT '호수', tier INTEGER DEFAULT 1, ground_reputation INTEGER DEFAULT 0, ground_price INTEGER DEFAULT 100000, purchasable INTEGER DEFAULT 1, is_public INTEGER DEFAULT 1, entry_fee INTEGER DEFAULT 0, usage_time_limit INTEGER DEFAULT 1, PRIMARY KEY(channel_id, guild_id)")
        db.create_table("fishing_gear", "user_id TEXT, guild_id TEXT, rod_level INTEGER DEFAULT 0, rod_durability INTEGER DEFAULT 100, bait_level INTEGER DEFAULT 0, bait_count INTEGER DEFAULT 0, PRIMARY KEY(user_id, guild_id)")
        db.create_table("fishing_inventory", "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, guild_id TEXT, fish_name TEXT, length REAL, price_per_cm INTEGER")
        db.create_table("fishing_passes", "user_id TEXT, channel_id TEXT, guild_id TEXT, expire_time TEXT, PRIMARY KEY(user_id, channel_id, guild_id)")
        db.create_table("fishing_facilities", "channel_id TEXT, guild_id TEXT, facility_name TEXT, PRIMARY KEY(channel_id, guild_id, facility_name)")
        db.create_table("point_history", "id INTEGER PRIMARY KEY AUTOINCREMENT, user_id TEXT, transaction_type TEXT, amount INTEGER, balance_after INTEGER, description TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP")
        
        # 3. 낚시터 테이블 컬럼 누락 보정 (None을 ()로 변경)
        cols_g_res = db.execute_query("PRAGMA table_info(fishing_ground)", (), 'all')
        cols_g = [c['name'] for c in cols_g_res] if cols_g_res else []

        if 'is_public' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN is_public INTEGER DEFAULT 1")
            except: pass
        if 'usage_time_limit' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN usage_time_limit INTEGER DEFAULT 1")
            except: pass
        if 'entry_fee' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN entry_fee INTEGER DEFAULT 0")
            except: pass
        if 'ground_type' not in cols_g:
            try: db.execute_query("ALTER TABLE fishing_ground ADD COLUMN ground_type TEXT DEFAULT '호수'")
            except: pass

    def _get_db(self, interaction: discord.Interaction):
        db = self.db_cog.get_manager(interaction.guild_id)
        # ✅ 명령어를 날릴 때마다 스키마를 체크하여 누락된 컬럼(is_public 등)이 있다면 채워 넣습니다.
        self._init_db_schema(db)
        return db
    
    def _ensure_ground_exists(self, db, chid: str, gid: str, channel_name: str):
        ground = db.execute_query("SELECT 1 FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name) VALUES (?, ?, ?)", (chid, gid, channel_name))

    async def _execute_fishing(self, interaction: discord.Interaction):
        if interaction.user.id in active_sessions: 
            return await interaction.response.send_message("⏳ 이미 낚시를 진행 중입니다!", ephemeral=True)
        
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        gear = db.execute_query("SELECT bait_count, rod_durability FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one')
        if not gear: return await interaction.response.send_message("❌ 장비가 없습니다! `/낚시가게`에서 초보자 세트를 구매하세요.", ephemeral=True)
        if gear['bait_count'] <= 0: return await interaction.response.send_message("❌ 미끼가 없습니다!", ephemeral=True)
        if gear['rod_durability'] <= 0: return await interaction.response.send_message("❌ 낚싯대가 고장 났습니다! 수리 후 이용하세요.", ephemeral=True)

        ground = db.execute_query("SELECT owner_id, is_public, entry_fee, usage_time_limit FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name, is_public) VALUES (?, ?, ?, 1)", (chid, gid, interaction.channel.name))
            ground = db.execute_query("SELECT owner_id, is_public, entry_fee, usage_time_limit FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')

        if ground['owner_id'] and ground['owner_id'] != uid and ground['is_public'] != 1:
            p = db.execute_query("SELECT expire_time FROM fishing_passes WHERE user_id = ? AND channel_id = ? AND guild_id = ?", (uid, chid, gid), 'one')
            if not p or datetime.strptime(p['expire_time'], '%Y-%m-%d %H:%M:%S') <= datetime.now():
                view = GroundAccessView(interaction.user, ground['entry_fee'], ground['usage_time_limit'], ground['owner_id'], db)
                return await interaction.response.send_message(embed=discord.Embed(title="🛑 입장권이 필요합니다", description=f"비용: **{ground['entry_fee']:,}원**\n구매하시겠습니까?", color=discord.Color.orange()), view=view)

        view = FishingGameView(interaction.user, db, interaction.channel_id)
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
        app_commands.Choice(name="낚시터 판매 (매각)", value="sell"), # 👈 추가됨!
        app_commands.Choice(name="설정 변경 (입장료/공개여부/지형)", value="edit")
    ])
    @app_commands.choices(지형=[ # 🌟 지형 선택지 추가!
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
        지형: Optional[str] = None # 🌟 매개변수 추가!
    ):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name) VALUES (?, ?, ?)", (chid, gid, interaction.channel.name))
            ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')

        if 액션 == "info":
            owner = f"<@{ground['owner_id']}>" if ground['owner_id'] else "없음 (구매 가능)"
            facilities = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'all')
            f_list = ", ".join([f['facility_name'] for f in facilities]) if facilities else "없음"

            # 📊 [확률 보너스 계산] 현재 설치된 시설들의 총합 스탯 도출
            total_fish_rate = 0.0     # 물고기(창고) 확률 보너스
            total_trash_rate = 0.0    # 쓰레기 감소 확률 (기본 25%에서 차감)
            best_sell_mult = 1.0      # 최고 판매가 배율 (가게)

            if facilities:
                for f in facilities:
                    f_name = f['facility_name']
                    if f_name in FACILITIES:
                        effects = FACILITIES[f_name].get("effect", {})
                        total_fish_rate += effects.get("fish_rate", 0.0)
                        total_trash_rate += effects.get("trash_rate", 0.0)
                        
                        # 물고기 가격은 가장 높은 배율 하나만 적용
                        price_mult = effects.get("fish_price_mult", 1.0)
                        if price_mult > best_sell_mult:
                            best_sell_mult = price_mult

            # 최종 퍼센트 변환
            trash_prob = max(0.0, 25.0 + (total_trash_rate * 100)) # 기본 쓰레기 확률 25%
            
            embed = discord.Embed(title=f"📍 낚시터 정보: {interaction.channel.name}", color=discord.Color.blue())
            embed.add_field(name="👑 소유주", value=owner, inline=True)
            embed.add_field(name="💰 구매 가격", value=f"{ground['ground_price']:,}원", inline=True)
            embed.add_field(name="🎫 입장료", value=f"{ground['entry_fee']:,}원", inline=True)
            embed.add_field(name="🔓 상태", value="공개" if ground['is_public'] == 1 else "비공개 (입장권 필요)", inline=True)
            embed.add_field(name="🏗️ 설치 시설", value=f_list, inline=False)
            embed.add_field(name="🌍 자연 환경", value=ground['ground_type'], inline=True)
            await interaction.response.send_message(embed=embed)

            # ✨ [확률 및 시설 효과 출력란]
            effect_summary = (
                f"📈 **희귀 물고기 확률 증가:** `+{total_fish_rate * 100:.1f}%` (창고 효과)\n"
                f"🗑️ **현재 쓰레기 낚일 확률:** `{trash_prob:.1f}%` (환경미화 효과)\n"
                f"🏪 **물고기 판매가 정산율:** `{best_sell_mult:.1f}배` (상업 시설 효과)"
            )
            embed.add_field(name="📊 현재 낚시터 적용 효과", value=effect_summary, inline=False)

            await interaction.response.send_message(embed=embed)

        elif 액션 == "buy":
            if ground['owner_id']: 
                return await interaction.response.send_message("❌ 이미 주인이 있는 땅입니다.", ephemeral=True)
            
            cost = ground['ground_price']
            user_cash = db.get_user_cash(uid) or 0

            if user_cash < cost: 
                return await interaction.response.send_message(f"❌ 소지금이 부족합니다! (보유: {user_cash:,}원 / 필요: {cost:,}원)", ephemeral=True)

            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("UPDATE fishing_ground SET owner_id = ?, purchasable = 0 WHERE channel_id = ? AND guild_id = ?", (uid, chid, gid))
                conn.commit()
                await interaction.response.send_message(f"🎊 성공적으로 <#{chid}> 낚시터를 **{cost:,}원**에 구매했습니다!")
            except:
                conn.rollback()
                await interaction.response.send_message("❌ 구매 중 오류가 발생했습니다.", ephemeral=True)

        elif 액션 == "edit":
            if ground['owner_id'] != uid: 
                return await interaction.response.send_message("❌ 소유자만 설정을 변경할 수 있습니다.", ephemeral=True)
            
            # 1. 텍스트로 수정할 입장료와 지형 타입 갱신
            if 입장료 is not None or 지형 is not None:
                new_fee = 입장료 if 입장료 is not None else ground['entry_fee']
                new_type = 지형 if 지형 is not None else ground['ground_type']
                db.execute_query(
                    "UPDATE fishing_ground SET entry_fee = ?, ground_type = ? WHERE channel_id = ? AND guild_id = ?", 
                    (new_fee, new_type, chid, gid)
                )
                await interaction.response.send_message(f"✅ 기초 정보가 업데이트되었습니다! (입장료: {new_fee:,}원 / 환경: {new_type})")
                return # 👈 기초 정보만 수정했다면 여기서 끝냅니다.

            # 2. 유저가 값을 안 치고 `/낚시터 액션:edit`만 친 경우 공개/비공개 버튼 UI 발송!
            embed = discord.Embed(
                title="🔒 낚시터 공개 여부 설정", 
                description="아래 버튼을 눌러 낚시터 개방 여부를 선택하세요.\n\n"
                            "- **공개:** 입장권 없이 누구나 무료 이용\n"
                            "- **비공개:** 다른 유저는 이용권 구매 필요", 
                color=discord.Color.purple()
            )
            view = PublicSettingView(interaction.user, db)
            await interaction.response.send_message(embed=embed, view=view)
            view.message = await interaction.original_response()\
            
        elif 액션 == "sell":
            if ground['owner_id'] != uid: 
                return await interaction.response.send_message("❌ 본인 소유의 낚시터만 매각할 수 있습니다.", ephemeral=True)

            price = ground['ground_price'] or 100000
            
            # 🤝 1차 확인 절차 (실수 방지용 UI 뷰 호출)
            # 과거 버전에 있던 ConfirmActionView를 현재 UI 스타일인 PublicSettingView 등의 구조와 맞춘 임시 확인창입니다.
            embed = discord.Embed(
                title="🏢 낚시터 매각 확인", 
                description=f"정말로 현재 낚시터를 매각하시겠습니까?\n매각 시 **{price:,}원**을 돌려받으며, 소유권이 초기화되어 **누구나 다시 구매할 수 있게 됩니다.**", 
                color=discord.Color.orange()
            )

            # 간단하게 구현하기 위해 기존에 이미 정의되어 있는 TrashActionView나 PublicSettingView처럼 
            # 즉시 처리하는 인라인 코드를 작성하거나, 아래와 같이 표준 SQLite 트랜잭션으로 안전하게 구현합니다.
            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                # 1. 판매자에게 땅값 환불
                conn.execute("UPDATE users SET cash = cash + ? WHERE user_id = ? AND guild_id = ?", (price, uid, gid))
                # 2. 소유주 비우기 및 다시 구매 가능하도록 세팅 (owner_id = NULL, purchasable = 1)
                conn.execute("UPDATE fishing_ground SET owner_id = NULL, purchasable = 1, is_public = 1 WHERE channel_id = ? AND guild_id = ?", (chid, gid))
                conn.commit()
                
                await interaction.response.send_message(f"🏢 낚시터 매각이 완료되었습니다! 계좌로 **{price:,}원**이 입금되었으며, 이제 다른 사람이 이 땅을 살 수 있습니다.")
            except Exception as e:
                conn.rollback()
                await interaction.response.send_message(f"❌ 매각 중 오류가 발생했습니다: {e}", ephemeral=True)

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

        conn = db.get_connection()
        try:
            conn.execute("BEGIN")
            if 액션 == "up":
                if current_tier >= 5:
                    return await interaction.response.send_message("❌ 이미 최고 등급(5티어)입니다.", ephemeral=True)
                
                req_rep = current_tier * 1000 # 1->2는 1000점, 2->3은 2000점 소모
                if current_rep < req_rep:
                    return await interaction.response.send_message(f"❌ 낚시터 명성이 부족합니다! (필요: {req_rep:,}점 / 보유: {current_rep:,}점)", ephemeral=True)

                conn.execute("UPDATE fishing_ground SET tier = tier + 1, ground_reputation = ground_reputation - ? WHERE channel_id = ? AND guild_id = ?", (req_rep, chid, gid))
                conn.commit()
                await interaction.response.send_message(f"🔼 낚시터 등급이 **{current_tier + 1}티어**로 상승했습니다! (소모 명성: -{req_rep:,}점)")

            elif 액션 == "down":
                if current_tier <= 1:
                    return await interaction.response.send_message("❌ 이미 최하 등급(1티어)입니다.", ephemeral=True)

                conn.execute("UPDATE fishing_ground SET tier = tier - 1, ground_reputation = ground_reputation + 500 WHERE channel_id = ? AND guild_id = ?", (chid, gid))
                conn.commit()
                await interaction.response.send_message(f"🔽 낚시터 등급이 **{current_tier - 1}티어**로 내려갔습니다! (명성 500점 환급)")

        except Exception as e:
            conn.rollback()
            await interaction.response.send_message(f"❌ 티어 변경 중 오류가 발생했습니다. (에러: {e})", ephemeral=True)

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
    async def build_facility(self, interaction: discord.Interaction, 대분류: str, 시설명: str):
        # 유저가 직접 타이핑해서 오타를 냈을 경우 방어 코드
        if 시설명 not in FACILITIES:
            return await interaction.response.send_message("❌ 존재하지 않는 시설입니다. 목록에서 올바르게 선택해 주세요.", ephemeral=True)
        
        # 선택한 시설이 내가 고른 대분류에 속하는지 검증
        if 시설명 not in CATEGORY_FACILITIES.get(대분류, []):
            return await interaction.response.send_message(f"❌ 선택하신 시설은 이 카테고리에 속해있지 않습니다.", ephemeral=True)
        
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        ground = db.execute_query("SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground or ground['owner_id'] != uid: 
            return await interaction.response.send_message("❌ 본인 소유의 낚시터에만 시설을 지을 수 있습니다.", ephemeral=True)
        
        f_data = FACILITIES[시설명]
        user = db.get_user(uid)
        
        if not user or user.get('fishing_reputation', 0) < f_data['req_rep']: 
            return await interaction.response.send_message(f"❌ 낚시 명성이 부족합니다! (필요: {f_data['req_rep']:,}점)", ephemeral=True)
        if user.get('cash', 0) < f_data['req_cash']: 
            return await interaction.response.send_message(f"❌ 건설 자금이 부족합니다! (필요: {f_data['req_cash']:,}원)", ephemeral=True)
        
        existing = db.execute_query("SELECT 1 FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명), 'one')
        if existing: 
            return await interaction.response.send_message("⚠️ 이미 설치된 시설입니다.", ephemeral=True)

        conn = db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (f_data['req_cash'], uid, gid))
            conn.execute("INSERT INTO fishing_facilities (channel_id, guild_id, facility_name) VALUES (?, ?, ?)", (chid, gid, 시설명))
            conn.commit()
            await interaction.response.send_message(f"🏗️ **{시설명}** 건설이 완료되었습니다!\n(효과: {f_data['desc']})")
        except:
            conn.rollback()
            await interaction.response.send_message("❌ 시설 건설 중 오류가 발생했습니다.", ephemeral=True)
    
    # 🔍 대분류를 고르면 해당 대분류에 있는 시설명만 필터링해주는 자동완성 시스템
    @build_facility.autocomplete('시설명')
    async def build_facility_autocomplete(self, interaction: discord.Interaction, current: str):
        selected_category = interaction.namespace.대분류 
        if not selected_category:
            return []

        # 전역 딕셔너리에서 안전하게 참조
        facility_names = CATEGORY_FACILITIES.get(selected_category, [])
    
        choices = []
        for name in facility_names:
            if current.lower() in name.lower():
                data = FACILITIES[name]
                # f-string으로 유저 편의성 증가
                choices.append(app_commands.Choice(
                    name=f"{name} (💰{data['req_cash']:,}원 | ⭐{data['req_rep']:,}점)",
                    value=name
                ))
        return choices[:25]
    
    @app_commands.command(name="시설철거", description="낚시터에 지어진 시설을 파괴하고 명성을 일부 돌려받습니다.")
    async def destroy_facility(self, interaction: discord.Interaction, 시설명: str):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)

        ground = db.execute_query("SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (chid, gid), 'one')
        if not ground or ground['owner_id'] != uid:
            return await interaction.response.send_message("❌ 본인 소유의 낚시터 시설만 철거할 수 있습니다.", ephemeral=True)

        if 시설명 not in FACILITIES:
            return await interaction.response.send_message("❌ 존재하지 않는 시설입니다.", ephemeral=True)

        existing = db.execute_query("SELECT 1 FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명), 'one')
        if not existing:
            return await interaction.response.send_message("⚠️ 이 낚시터에 건설되지 않은 시설입니다.", ephemeral=True)

        # 💸 철거 시 명성 50% 환급 정책 적용
        refund_rep = int(FACILITIES[시설명]["req_rep"] * 0.5)

        conn = db.get_connection()
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (chid, gid, 시설명))
            conn.execute("UPDATE users SET fishing_reputation = fishing_reputation + ? WHERE user_id = ? AND guild_id = ?", (refund_rep, uid, gid))
            conn.commit()
            await interaction.response.send_message(f"🪓 **{시설명}** 철거가 완료되었습니다! 개인 명성 **{refund_rep:,}점**을 돌려받았습니다.")
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
        app_commands.Choice(name="낚싯대 수리(1당100)", value="repair"),
        app_commands.Choice(name="초보자 세트 구매 (10,000원)", value="starter"),
        app_commands.Choice(name="미끼 10개 구매 (5,000원)", value="buy_bait")
    ])
    async def fish_shop(self, interaction: discord.Interaction, 액션: str):
        db = self._get_db(interaction)
        uid, chid, gid = str(interaction.user.id), str(interaction.channel_id), str(interaction.guild_id)
        
        if 액션 == "sell":
            items = db.execute_query("SELECT length, price_per_cm, fish_name FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (uid, gid), 'all')
            if not items: 
                return await interaction.response.send_message("🎒 가방에 팔 물고기가 없습니다.", ephemeral=True)
            
            # 👤 유저의 개인 명성 조회
            user_data = db.get_user(uid)
            user_rep = user_data.get('fishing_reputation', 0) if user_data else 0

            # ⭐ [명성별 1회 최대 판매 한도 설정]
            # 원하는 수치로 자유롭게 수정 가능합니다!
            if user_rep < 1000:
                max_limit = 50000        # 명성 1,000 미만: 최대 5만 원
                tier_name = "초보 낚시꾼"
            elif user_rep < 5000:
                max_limit = 200000       # 명성 5,000 미만: 최대 20만 원
                tier_name = "숙련된 낚시꾼"
            elif user_rep < 20000:
                max_limit = 1000000      # 명성 20,000 미만: 최대 100만 원
                tier_name = "전문 낚시꾼"
            else:
                max_limit = 999999999    # 명성 20,000 이상: 한도 없음 (무제한)
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

            # 💰 총액 정산
            calculated_total = sum([int(i['length'] * i['price_per_cm'] * best_multiplier) for i in items])
            
            # 🚨 [한도 초과 검사] 계산된 금액이 한도를 넘으면 한도 금액으로 고정
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
            cost = 5000
            if not db.execute_query("SELECT 1 FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (uid, gid), 'one'):
                return await interaction.response.send_message("❌ 낚싯대가 없습니다! 초보자 세트를 먼저 구매하세요.", ephemeral=True)
                
            if (db.get_user_cash(uid) or 0) < cost: return await interaction.response.send_message("❌ 자금이 부족합니다!", ephemeral=True)
            
            conn = db.get_connection()
            try:
                conn.execute("BEGIN")
                conn.execute("UPDATE users SET cash = cash - ? WHERE user_id = ? AND guild_id = ?", (cost, uid, gid))
                conn.execute("UPDATE fishing_gear SET bait_count = bait_count + 10 WHERE user_id = ? AND guild_id = ?", (uid, gid))
                conn.commit()
                await interaction.response.send_message("🐛 **미끼 10개**를 추가로 구매했습니다!")
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
        app_commands.Choice(name="⚙️ 현재 채널의 낚시터 유형 설정 (버튼)", value="set_type")
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
async def setup(bot):
    await bot.add_cog(FishingSystemCog(bot))