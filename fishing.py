# fishing.py
import discord
from discord import app_commands
from discord.ext import commands
import asyncio
import random
import time
from typing import Optional
from datetime import datetime, timedelta

from database_manager import DatabaseManager

# ==========================================
# ⚙️ [데이터 설정]
# ==========================================

TRAPS = [
    "앗, 진동이 전혀 안 느껴진다!!", 
    "앗! 오늘 날씨 진짜 좋다!!", 
    "구름이 참 예쁘네... 풍경 감상 중."
]

REAL_BITES = [
    "!!! 찌가 강하게 가라앉았다 !!!", 
    "어이쿠! 낚싯대가 부러질 듯 휜다!", 
    "손끝에 묵직-한 느낌이 든다!"
]

TRASH_LIST = [
    {"name": "찌그러진 빈 캔", "type": "neutral", "value": 0},
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
        # --- ⚪ 흔함 (합산 확률 약 63%) ---
        {"name": "전갱이", "rarity": "흔함", "chance": 0.15, "min": 15, "max": 30, "price_per_cm": 30, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "미끼 도둑으로 불리는 흔한 바다 어종입니다."},
        {"name": "고등어", "rarity": "흔함", "chance": 0.15, "min": 20, "max": 40, "price_per_cm": 40, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "국민 생선. 가장 흔하게 잡힙니다."},
        {"name": "전어", "rarity": "흔함", "chance": 0.10, "min": 15, "max": 30, "price_per_cm": 45, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "집 나간 며느리도 돌아온다는 가을 별미입니다."},
        {"name": "숭어", "rarity": "흔함", "chance": 0.10, "min": 30, "max": 80, "price_per_cm": 35, "req_tier": 1, "water_quality": [2,3,4,5], "effect_desc": "연안에서 펄쩍 뛰어오르는 흔한 바다 물고기입니다."},
        {"name": "민어", "rarity": "흔함", "chance": 0.08, "min": 40, "max": 100, "price_per_cm": 80, "req_tier": 1, "water_quality": [2,3,4], "effect_desc": "여름철 최고의 보양식으로 꼽힙니다."},
        {"name": "농어", "rarity": "흔함", "chance": 0.05, "min": 40, "max": 100, "price_per_cm": 70, "req_tier": 1, "water_quality": [1,2,3], "effect_desc": "연안으로 거슬러 올라오는 힘센 어종입니다."},

        # --- 🔵 희귀 (합산 확률 약 21%) ---
        {"name": "벵에돔", "rarity": "희귀", "chance": 0.05, "min": 25, "max": 50, "price_per_cm": 350, "req_tier": 2, "water_quality": [1,2], "effect_desc": "낚시꾼들의 로망 중 하나입니다. 잡을 시 개인 명성 +50"},
        {"name": "감성돔", "rarity": "희귀", "chance": 0.05, "min": 25, "max": 60, "price_per_cm": 400, "req_tier": 2, "water_quality": [1,2], "effect_desc": "바다의 왕자. 경험치 획득 +15%"},
        {"name": "우럭", "rarity": "희귀", "chance": 0.05, "min": 20, "max": 50, "price_per_cm": 250, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "바위 틈에 서식하는 대중적인 횟감입니다."},
        {"name": "연어", "rarity": "희귀", "chance": 0.03, "min": 50, "max": 90, "price_per_cm": 300, "req_tier": 2, "water_quality": [1,2], "effect_desc": "강을 거슬러 올라가는 붉은 살 생선입니다."},
        {"name": "바다빙어", "rarity": "희귀", "chance": 0.03, "min": 10, "max": 25, "price_per_cm": 200, "req_tier": 2, "water_quality": [1,2], "effect_desc": "떼를 지어 다니는 작은 겨울철 어종입니다."},

        # --- 🟣 신종 (합산 확률 약 11%) ---
        {"name": "고래상어", "rarity": "신종", "chance": 0.03, "min": 500, "max": 1200, "price_per_cm": 1500, "req_tier": 3, "water_quality": [1,2], "effect_desc": "지구상에서 가장 큰 어류입니다. 낚을 시 낚시터 명성 +500"},
        {"name": "타이거 샤크(뱀상어)", "rarity": "신종", "chance": 0.02, "min": 300, "max": 600, "price_per_cm": 1800, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "무엇이든 먹어치우는 바다의 포식자입니다. 낚싯대 내구도 -15"},
        {"name": "범고래", "rarity": "신종", "chance": 0.02, "min": 500, "max": 900, "price_per_cm": 2500, "req_tier": 3, "water_quality": [1,2], "effect_desc": "바다의 지배자이자 영리한 포식자입니다. 낚싯대 내구도 -20"},
        {"name": "대왕 오징어", "rarity": "신종", "chance": 0.02, "min": 200, "max": 1000, "price_per_cm": 1200, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "심해의 거대 괴수입니다. 낚싯대 내구도 -10"},
        {"name": "대왕 문어", "rarity": "신종", "chance": 0.02, "min": 100, "max": 300, "price_per_cm": 1300, "req_tier": 3, "water_quality": [1,2,3,4], "effect_desc": "무거운 빨판의 손맛. 낚싯대 내구도 -10"},

        # --- 🟡 전설 (합산 확률 약 3.5%) ---
        {"name": "백상아리", "rarity": "전설", "chance": 0.015, "min": 300, "max": 600, "price_per_cm": 4000, "req_tier": 4, "water_quality": [1,2], "effect_desc": "죠스의 주인공! 낚을 시 낚싯대 내구도 -35"},
        {"name": "향유고래", "rarity": "전설", "chance": 0.01, "min": 1000, "max": 1800, "price_per_cm": 3500, "req_tier": 4, "water_quality": [1,2], "effect_desc": "거대한 머리를 가진 잠수의 명수입니다. 낚싯대 내구도 -40"},
        {"name": "혹등고래", "rarity": "전설", "chance": 0.01, "min": 1200, "max": 1600, "price_per_cm": 3800, "req_tier": 4, "water_quality": [1,2], "effect_desc": "화려한 점프를 선보이는 온순한 거인입니다. 낚을 시 명성 +1,000"},

        # --- 🔴 환상 (합산 확률 약 1.5%) ---
        {"name": "돌고래", "rarity": "환상", "chance": 0.01, "min": 150, "max": 300, "price_per_cm": 7000, "req_tier": 5, "water_quality": [1,2], "effect_desc": "바다의 천사. 잡을 시 다음 낚시 성공 확률 +15%"},
        {"name": "바다거북", "rarity": "환상", "chance": 0.004, "min": 60, "max": 150, "price_per_cm": 0, "req_tier": 5, "water_quality": [1,2], "effect_desc": "[청정] 보호종입니다! 자동으로 방생되며 개인 명성이 +500 상승합니다."},
        {"name": "메갈로돈", "rarity": "환상", "chance": 0.001, "min": 1500, "max": 2000, "price_per_cm": 20000, "req_tier": 5, "water_quality": [1,2], "effect_desc": "고대의 초대형 상어. 낚을 시 낚싯대 내구도 -80"}
    ],

    "늪": [
        # --- ⚪ 흔함 (합산 확률 약 65%) ---
        {"name": "검정말", "rarity": "흔함", "chance": 0.20, "min": 10, "max": 50, "price_per_cm": 10, "req_tier": 1, "water_quality": [3,4,5,6], "effect_desc": "늪 바닥에 무성한 수초입니다. 판매가는 낮습니다."},
        {"name": "부레옥잠", "rarity": "흔함", "chance": 0.15, "min": 10, "max": 30, "price_per_cm": 20, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "수질 정화 능력이 있는 흔한 수생식물입니다."},
        {"name": "가시연꽃", "rarity": "흔함", "chance": 0.15, "min": 30, "max": 100, "price_per_cm": 30, "req_tier": 1, "water_quality": [3,4,5], "effect_desc": "가시가 돋아난 연꽃잎입니다. 낚을 시 낚싯대 내구도 -2"},
        {"name": "해캄", "rarity": "흔함", "chance": 0.15, "min": 5, "max": 20, "price_per_cm": 5, "req_tier": 1, "water_quality": [4,5,6], "effect_desc": "탁한 물에 끼는 녹조류 뭉덩이입니다."},

        # --- 🔵 희귀 (합산 확률 약 22%) ---
        {"name": "물방개", "rarity": "희귀", "chance": 0.07, "min": 2, "max": 5, "price_per_cm": 500, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "헤엄을 잘 치는 수서곤충입니다. 잡을 시 개인 명성 +30"},
        {"name": "민물새우", "rarity": "희귀", "chance": 0.05, "min": 3, "max": 8, "price_per_cm": 300, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "작고 투명한 늪지 새우입니다. 미끼로도 쓰입니다."},
        {"name": "각시붕어", "rarity": "희귀", "chance": 0.05, "min": 5, "max": 10, "price_per_cm": 400, "req_tier": 2, "water_quality": [2,3,4], "effect_desc": "빛깔이 고운 한국 고유종 소형 민물고기입니다."},
        {"name": "말조개", "rarity": "희귀", "chance": 0.05, "min": 10, "max": 25, "price_per_cm": 250, "req_tier": 2, "water_quality": [3,4,5], "effect_desc": "진흙 바닥에 서식하는 거대 민물 조개입니다."},

        # --- 🟣 신종 (합산 확률 약 9%) ---
        {"name": "물총새", "rarity": "신종", "chance": 0.02, "min": 15, "max": 25, "price_per_cm": 1500, "req_tier": 3, "water_quality": [1,2,3], "effect_desc": "날렵하게 물고기를 낚아채는 새입니다. 잡을 시 경험치 획득 +20%"},
        {"name": "개개비", "rarity": "신종", "chance": 0.02, "min": 10, "max": 20, "price_per_cm": 1200, "req_tier": 3, "water_quality": [2,3,4], "effect_desc": "여름철 늪지 갈대밭에서 시끄럽게 우는 새입니다."},
        {"name": "누룩뱀", "rarity": "신종", "chance": 0.02, "min": 50, "max": 120, "price_per_cm": 1000, "req_tier": 3, "water_quality": [3,4,5], "effect_desc": "늪 주변 습지에서 흔히 보이는 뱀입니다. 낚을 시 낚싯대 내구도 -5"},
        {"name": "잉어", "rarity": "신종", "chance": 0.015, "min": 30, "max": 80, "price_per_cm": 500, "req_tier": 3, "water_quality": [3,4,5], "effect_desc": "늪지 진흙 바닥에서 적응하여 자란 거대 잉어입니다."},
        {"name": "메기", "rarity": "신종", "chance": 0.015, "min": 30, "max": 70, "price_per_cm": 600, "req_tier": 3, "water_quality": [3,4,5,6], "effect_desc": "음침하고 탁한 수질에 도가 튼 야행성 포식자입니다."},

        # --- 🟡 전설 (합산 확률 약 3%) ---
        {"name": "가물치", "rarity": "전설", "chance": 0.01, "min": 40, "max": 100, "price_per_cm": 2500, "req_tier": 4, "water_quality": [3,4,5,6], "effect_desc": "늪지의 무법자이자 난폭한 최상위 어종입니다. 낚을 시 내구도 -15"},
        {"name": "물수리", "rarity": "전설", "chance": 0.01, "min": 50, "max": 70, "price_per_cm": 3000, "req_tier": 4, "water_quality": [1,2,3], "effect_desc": "하늘에서 물고기를 사냥하는 맹금류입니다. 낚을 시 낚시터 명성 +500"},
        {"name": "황소개구리", "rarity": "전설", "chance": 0.005, "min": 15, "max": 30, "price_per_cm": 1000, "req_tier": 4, "water_quality": [4,5,6], "effect_desc": "생태계를 파괴하는 거대 양서류입니다. 잡을 시 늪 오염도 상승 및 포상금 획득."},
        {"name": "너구리", "rarity": "전설", "chance": 0.005, "min": 40, "max": 70, "price_per_cm": 2000, "req_tier": 4, "water_quality": [3,4,5], "effect_desc": "늪가에서 먹이를 씻어 먹는 잡식 동물입니다. 가방의 미끼 5개를 소실시킵니다."},

        # --- 🔴 환상 (합산 확률 약 1%) ---
        {"name": "백로", "rarity": "환상", "chance": 0.004, "min": 60, "max": 100, "price_per_cm": 6000, "req_tier": 5, "water_quality": [1,2,3], "effect_desc": "순백의 자태를 뽐내는 새입니다. 잡을 시 낚시터 명성 +1,000"},
        {"name": "왜가리", "rarity": "환상", "chance": 0.004, "min": 80, "max": 110, "price_per_cm": 6500, "req_tier": 5, "water_quality": [2,3,4], "effect_desc": "부동의 자세로 물고기를 사냥하는 새입니다. 낚을 시 다음 낚시 대기 시간 -15%"},
        {"name": "악어", "rarity": "환상", "chance": 0.002, "min": 150, "max": 400, "price_per_cm": 15000, "req_tier": 5, "water_quality": [3,4,5,6], "effect_desc": "늪지의 최종 지배자. 낚을 시 엄청난 데스롤을 시전하여 낚싯대 내구도 -60"}
    ]
}

active_sessions = {}

# 기존 FACILITIES를 아래 내용으로 교체하시면 됩니다.
FACILITIES = {
    # --- 🧾 수수료 조정 매표소 ---
    "간이매표소": {"tier": 1, "req_rep": 500, "req_cash": 30000, "effect": {"tax_adj": 0.03}, "desc": "수수료 조정 범위 +-3%"},
    "매표소": {"tier": 2, "req_rep": 2000, "req_cash": 50000, "effect": {"tax_adj": 0.05}, "desc": "수수료 조정 범위 +-5%"},
    "일반매표소": {"tier": 2, "req_rep": 5000, "req_cash": 80000, "effect": {"tax_adj": 0.08}, "desc": "수수료 조정 범위 +-8%"},
    "중형매표소": {"tier": 3, "req_rep": 10000, "req_cash": 120000, "effect": {"tax_adj": 0.10}, "desc": "수수료 조정 범위 +-10%"},
    "대형매표소": {"tier": 4, "req_rep": 30000, "req_cash": 200000, "effect": {"tax_adj": 0.15}, "desc": "수수료 조정 범위 +-15%"},
    "거대한매표소": {"tier": 5, "req_rep": 50000, "req_cash": 300000, "effect": {"tax_adj": 0.20}, "desc": "수수료 조정 범위 +-20%"},

    # --- 📦 물고기 확률 조정 (창고) ---
    "창고": {"tier": 1, "req_rep": 500, "req_cash": 30000, "effect": {"base_tax": 0.05, "fish_rate": 0.05}, "desc": "기본 수수료 5%, 매 턴 물고기 확률 +5%"},
    "소형창고": {"tier": 2, "req_rep": 3000, "req_cash": 50000, "effect": {"base_tax": 0.07, "fish_rate": 0.07, "upkeep": 0.05}, "desc": "기본 수수료 7%, 매 턴 물고기 확률 +7%, 유지비 +5%"},
    "중형창고": {"tier": 3, "req_rep": 10000, "req_cash": 80000, "effect": {"base_tax": 0.10, "fish_rate": 0.10, "upkeep": 0.07}, "desc": "기본 수수료 10%, 매 턴 물고기 확률 +10%, 유지비 +7%"},
    "대형창고": {"tier": 4, "req_rep": 50000, "req_cash": 120000, "effect": {"base_tax": 0.15, "fish_rate": 0.15, "upkeep": 0.10}, "desc": "기본 수수료 15%, 매 턴 물고기 확률 +15%, 유지비 +10%"},
    "초거대한창고": {"tier": 5, "req_rep": 100000, "req_cash": 250000, "effect": {"base_tax": 0.20, "fish_rate": 0.20, "upkeep": 0.15}, "desc": "기본 수수료 20%, 매 턴 물고기 확률 +20%, 유지비 +15%"},

    # --- 🧹 쓰레기 감소 확률 ---
    "환경미화원": {"tier": 2, "req_rep": 1000, "req_cash": 20000, "effect": {"trash_rate": -0.05}, "desc": "쓰레기가 5% 덜 낚임"},
    "청소용역업체": {"tier": 3, "req_rep": 30000, "req_cash": 80000, "effect": {"trash_rate": -0.10}, "desc": "쓰레기가 10% 덜 낚임"},
    "시설관리공단": {"tier": 5, "req_rep": 100000, "req_cash": 300000, "effect": {"trash_rate": -0.20}, "desc": "쓰레기가 20% 덜 낚임"},

    # --- ⚡ 유지비 감소 발전기 ---
    "전기배터리": {"tier": 1, "req_rep": 5000, "req_cash": 10000, "effect": {"upkeep": -0.05}, "desc": "유지비 -5%"},
    "소형발전기": {"tier": 2, "req_rep": 10000, "req_cash": 50000, "effect": {"upkeep": -0.07}, "desc": "유지비 -7%"},
    "중대형발전기": {"tier": 3, "req_rep": 50000, "req_cash": 100000, "effect": {"upkeep": -0.10}, "desc": "유지비 -10%"},
    "화력발전소": {"tier": 4, "req_rep": 80000, "req_cash": 300000, "effect": {"upkeep": -0.15}, "desc": "유지비 -15%"},
    "수력발전소": {"tier": 5, "req_rep": 120000, "req_cash": 500000, "effect": {"upkeep": -0.25}, "desc": "유지비 -25%"},

    # --- ✨ 명성 증가율 상점 ---
    "길거리상인": {"tier": 1, "req_rep": 500, "req_cash": 10000, "effect": {"rep_mult": 1.2}, "desc": "명성 증가량 1.2배"},
    "기념품상점": {"tier": 2, "req_rep": 3000, "req_cash": 50000, "effect": {"rep_mult": 1.5}, "desc": "명성 증가량 1.5배"},
    "기념품백화점": {"tier": 3, "req_rep": 10000, "req_cash": 90000, "effect": {"rep_mult": 2.0}, "desc": "명성 증가량 2배"},
    "해외입점준비": {"tier": 4, "req_rep": 50000, "req_cash": 130000, "effect": {"rep_mult": 2.2}, "desc": "명성 증가량 2.2배"},
    "해외유명기업": {"tier": 5, "req_rep": 100000, "req_cash": 300000, "effect": {"rep_mult": 3.0}, "desc": "명성 증가량 3배"},

    # --- ♻️ 유지비 감소 + 쓰레기 조정 ---
    "재활용분리수거장": {"tier": 1, "req_rep": 1500, "req_cash": 8000, "effect": {"fish_price": 0.5, "trash_rate": -0.05, "upkeep": 0.05}, "desc": "물고기 가격 0.5배 증가, 쓰레기 5% 감소, 유지비 5%"},
    "쓰레기소각장": {"tier": 3, "req_rep": 10000, "req_cash": 70000, "effect": {"fish_price": 1.2, "trash_rate": -0.10, "upkeep": 0.12}, "desc": "물고기 가격 1.2배 증가, 쓰레기 10% 감소, 유지비 12%"},
    "환경부": {"tier": 5, "req_rep": 100000, "req_cash": 500000, "effect": {"fish_price": 2.0, "trash_rate": -0.20, "upkeep": 0.20}, "desc": "물고기 가격 2배 증가, 쓰레기 20% 감소, 유지비 20%"},

    # --- 🛒 유지비 감소 마트 ---
    "리안마켓": {"tier": 1, "req_rep": 1000, "req_cash": 8000, "effect": {"upkeep": -0.05}, "desc": "유지비 5% 감소"},
    "묵이 편의점": {"tier": 2, "req_rep": 7000, "req_cash": 35000, "effect": {"upkeep": -0.07}, "desc": "유지비 7% 감소"},
    "할인마트": {"tier": 3, "req_rep": 30000, "req_cash": 70000, "effect": {"upkeep": -0.10, "rep_mult": 1.2}, "desc": "유지비 10% 감소, 명성 1.2배 증가"},
    "정E-마트   ": {"tier": 4, "req_rep": 50000, "req_cash": 150000, "effect": {"upkeep": -0.15, "rep_mult": 1.5}, "desc": "유지비 15% 감소, 명성 1.5배 증가"},
    "해외수출사업": {"tier": 5, "req_rep": 100000, "req_cash": 300000, "effect": {"upkeep": -0.20, "rep_mult": 2.0}, "desc": "유지비 20% 감소, 명성 2배 증가"},
    
    # --- 🐟 물고기 가격 보너스 상점 ---
    "노상": {"tier": 1, "req_rep": 2000, "req_cash": 10000, "effect": {"fish_price": 1.1}, "desc": "물고기 가격 1.1배 증가"},
    "물사랑고기사랑 가게": {"tier": 2, "req_rep": 10000, "req_cash": 50000, "effect": {"fish_price": 1.3, "upkeep": 0.05}, "desc": "물고기 가격 1.3배 증가, 유지비 +5%"},
    "5일장시장": {"tier": 3, "req_rep": 40000, "req_cash": 10000, "effect": {"fish_price": 1.5, "upkeep": 0.10}, "desc": "물고기 가격 1.5배 증가, 유지비 +10%"},
    "회전문공장": {"tier": 4, "req_rep": 100000, "req_cash": 250000, "effect": {"fish_price": 2.0, "upkeep": 0.15}, "desc": "물고기 가격 2.0배 증가, 유지비 +15%"},
    "세계1위기업": {"tier": 5, "req_rep": 300000, "req_cash": 500000, "effect": {"fish_price": 2.5, "upkeep": 0.20}, "desc": "물고기 가격 2.5배 증가, 유지비 +20%"},

    # --- 🏫 기타 방해요소 (학군 및 소음 유발 시설) ---
    "어린이집": {"tier": 1, "req_rep": 500, "req_cash": 10000, "effect": {"fail_rate": 0.05, "upkeep": 0.05}, "desc": "낚시 실패확률 +5%, 유지비 +5%"},
    "유치원": {"tier": 2, "req_rep": 2000, "req_cash": 30000, "effect": {"fail_rate": 0.07, "upkeep": 0.09}, "desc": "낚시 실패확률 +7%, 유지비 +9%"},
    "초등학교": {"tier": 3, "req_rep": 5000, "req_cash": 50000, "effect": {"fail_rate": 0.10, "upkeep": -0.05}, "desc": "낚시 실패확률 +10%, 유지비 -5%"},
    "중학교": {"tier": 4, "req_rep": 10000, "req_cash": 80000, "effect": {"fail_rate": 0.12, "upkeep": -0.09}, "desc": "낚시 실패활률 +12%, 유지비 -9%"},
    "고등학교": {"tier": 5, "req_rep": 30000, "req_cash": 110000, "effect": {"fail_rate": 0.15, "upkeep": -0.12}, "desc": "낚시 실패확률 +15%, 유지비 -12%"},
}


# ==========================================
# 👀 [UI 뷰 클래스 정의]
# ==========================================

# 🗑️ 쓰레기 처리 뷰
class TrashActionView(discord.ui.View):
    def __init__(self, user: discord.Member, penalty: int, db_manager: DatabaseManager):
        super().__init__(timeout=30.0)
        self.user = user
        self.penalty = abs(penalty)
        self.db = db_manager

    @discord.ui.button(label="🧹 쓰레기 치우기 (돈 소모)", style=discord.ButtonStyle.success)
    async def clean(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("자신의 쓰레기만 처리할 수 있습니다!", ephemeral=True)

        user_cash = self.db.get_user_cash(str(self.user.id)) or 0
        if user_cash < self.penalty:
            return await interaction.response.send_message("❌ 소지한 현금이 부족하여 쓰레기를 치울 수 없습니다!", ephemeral=True)

        self.db.add_user_cash(str(self.user.id), -self.penalty)
        self.db.add_transaction(str(self.user.id), "낚시 쓰레기 청소", -self.penalty, "낚시터 오염 방지 청소비")

        embed = discord.Embed(title="✅ 청소 완료", description=f"**{self.penalty:,}원**을 지불하여 쓰레기를 치웠습니다!", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)

    @discord.ui.button(label="🚮 그냥 버리기 (오염도 상승)", style=discord.ButtonStyle.danger)
    async def dump(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("자신의 쓰레기만 처리할 수 있습니다!", ephemeral=True)

        embed = discord.Embed(title="⚠️ 무단 투기 완료", description="쓰레기를 그냥 바닥에 버렸습니다. 낚시터 오염도가 상승합니다!", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)

# 🏗️ 시설 정보 페이징 뷰
class FacilityPaginationView(discord.ui.View):
    def __init__(self, user: discord.Member, pages: list):
        super().__init__(timeout=60.0)
        self.user = user
        self.pages = pages
        self.current_page = 0

    async def send_initial_message(self, interaction: discord.Interaction):
        if not self.pages:
            return await interaction.followup.send("조회할 시설 정보가 없습니다.")
        await interaction.followup.send(embed=self.pages[0], view=self)

    @discord.ui.button(label="◀️ 이전", style=discord.ButtonStyle.primary)
    async def prev_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인만 페이지를 넘길 수 있습니다!", ephemeral=True)

        if self.current_page > 0:
            self.current_page -= 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message("첫 번째 페이지입니다.", ephemeral=True)

    @discord.ui.button(label="다음 ▶️", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인만 페이지를 넘길 수 있습니다!", ephemeral=True)

        if self.current_page < len(self.pages) - 1:
            self.current_page += 1
            await interaction.response.edit_message(embed=self.pages[self.current_page], view=self)
        else:
            await interaction.response.send_message("마지막 페이지입니다.", ephemeral=True)
            
# 🎣 낚시 게임 인게임 뷰
class FishingGameView(discord.ui.View):
    # __init__ 에서 channel_id 대신 user.id를 추적하도록 변경
    def __init__(self, user: discord.Member, db_manager: DatabaseManager, channel_id: int):
        super().__init__(timeout=60.0)
        self.user = user
        self.db = db_manager
        self.channel_id = channel_id
        self.stage = "waiting"
        self.is_real = False
        self.responded = False
        self.message = None

    async def start_game(self, interaction: discord.Interaction):
        # 유저 미끼 소모
        db_gear = self.db.execute_query("SELECT bait_count FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (str(self.user.id), str(interaction.guild_id)), 'one')
        if not db_gear or db_gear['bait_count'] <= 0:
            return await interaction.response.send_message("❌ 미끼가 없습니다! `/낚시가게 미끼구입`으로 미끼를 구매하세요.", ephemeral=True)

        # 낚싯대 내구도 체크
        gear = self.db.execute_query("SELECT rod_durability FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (str(self.user.id), str(interaction.guild_id)), 'one')
        if gear and gear['rod_durability'] <= 0:
            return await interaction.response.send_message("❌ 낚싯대가 부러졌습니다! `/낚시가게 낚시대수리`로 수리하세요.", ephemeral=True)

        self.db.execute_query("UPDATE fishing_gear SET bait_count = bait_count - 1 WHERE user_id = ? AND guild_id = ?", (str(self.user.id), str(interaction.guild_id)))

        embed = discord.Embed(title="🎣 낚시 시작!", description="낚싯줄을 던졌습니다...\n물고기가 걸릴 때까지 잠시 기다리세요.\n(미끼 1개가 소모되었습니다.)", color=discord.Color.green())
        await interaction.response.send_message(embed=embed, view=self)
        self.message = await interaction.original_response()
        
        await asyncio.sleep(random.uniform(2.0, 5.0))
        if self.responded: return

        self.stage = "bite"
        
        # 장비&미끼 레벨에 따른 가짜 입질 필터링 (확률 증가)
        gear_data = self.db.execute_query("SELECT rod_level, bait_level FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (str(self.user.id), str(interaction.guild_id)), 'one')
        bonus_rate = 0.0
        if gear_data:
            bonus_rate += (gear_data['rod_level'] * 0.01) + (gear_data['bait_level'] * 0.01)

        success_chance = 0.5 + bonus_rate
        self.is_real = random.random() < success_chance

        text = random.choice(REAL_BITES) if self.is_real else random.choice(TRAPS)
        
        embed.title = "🚨 찌가 움직인다! 🚨"
        embed.description = f"**{text}**"
        embed.color = discord.Color.red()
        
        try:
            await interaction.edit_original_response(embed=embed, view=self)
        except: return

        await asyncio.sleep(3.0)
        if not self.responded and self.stage == "bite":
            self.stage = "ended"
            
            # 🔥 여기에 5초 쿨타임 태스크 예약
            asyncio.create_task(self.remove_from_session())

            embed.title = "💨 물고기를 놓쳤다..."
            embed.description = "타이밍이 늦었습니다. 물고기가 미끼만 먹고 도망갔습니다. (5초 쿨타임이 적용됩니다.)"
            embed.color = discord.Color.dark_gray()
            await interaction.edit_original_response(embed=embed, view=None)
            
async def remove_from_session(self):
    if active_sessions.get(self.user.id) == self:
        await asyncio.sleep(5.0) # 🛑 게임 종료 후 5초 동안 세션 유지 (명령어 사용 불가)
        active_sessions.pop(self.user.id, None)


    @discord.ui.button(label="🎣 낚싯줄 당기기", style=discord.ButtonStyle.danger)
    async def pull(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인의 낚싯대만 당길 수 있습니다!", ephemeral=True)

        if self.responded: 
            return await interaction.response.send_message("이미 낚싯줄을 당기는 중입니다!", ephemeral=True)
            
        self.responded = True
        await interaction.response.defer() 
        self.stop()

        asyncio.create_task(self.remove_from_session())
        
        self.remove_from_session()

        if self.stage == "waiting":
            embed = discord.Embed(title="❌ 너무 성급했습니다!", description="아무것도 건지지 못했습니다.", color=discord.Color.light_gray())
            return await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=None)

        if not self.is_real:
            embed = discord.Embed(title="❌ 아차! 가짜 입질!", description="물고기가 아니라 헛것이었네요.", color=discord.Color.light_gray())
            return await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=None)

        # 낚시 성공 시 내구도 1 소모
        self.db.execute_query("UPDATE fishing_gear SET rod_durability = rod_durability - 1 WHERE user_id = ? AND guild_id = ?", (str(self.user.id), str(interaction.guild_id)))
        self.db.add_user_xp(str(self.user.id), 10)

        # 쓰레기 획득 확률 (30%)
        if random.random() < 0.30:
            trash = random.choice(TRASH_LIST)
            if trash["type"] == "loss":
                embed = discord.Embed(title="🚮 아이고! 쓰레기입니다!", description=f"**[{trash['name']}]**을(를) 낚았습니다.\n처리 방식을 선택하세요.", color=discord.Color.orange())
                view = TrashActionView(self.user, trash["value"], self.db)
                return await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=view)
            elif trash["type"] == "profit":
                self.db.add_user_cash(str(self.user.id), trash["value"])
                self.db.add_transaction(str(self.user.id), "낚시 보물 발견", trash["value"], f"{trash['name']} 획득")
                embed = discord.Embed(title="💎 보물 발견!", description=f"**[{trash['name']}]**을(를) 건졌습니다!\n주워다 팔아 **{trash['value']:,}원**을 벌었습니다.", color=discord.Color.gold())
                return await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=None)
            else:
                embed = discord.Embed(title="🗑️ 쓰레기 획득", description=f"**[{trash['name']}]**을(를) 건졌습니다. 가치는 없습니다.", color=discord.Color.light_gray())
                return await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=None)

        # ✨ [지형 판별 시스템] 채널에 설정된 지형(호수/바다/늪) 조회 ✨
        ground = self.db.execute_query("SELECT ground_type FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (str(self.channel_id), str(interaction.guild_id)), 'one')
        location = ground['ground_type'] if ground and ground.get('ground_type') else "호수" 

        fish_pool = FISHING_ECOLOGY.get(location, [])
        if not fish_pool:
            fish_pool = FISHING_ECOLOGY.get("호수", [])

        # 가중치(확률) 기반 랜덤 추출
        fish = random.choices(fish_pool, weights=[f["chance"] for f in fish_pool], k=1)[0]
        length = round(random.uniform(fish["min"], fish["max"]), 1)
        user_id = str(self.user.id)
        guild_id = str(interaction.guild_id)

        self.db.execute_query(
            "INSERT INTO fishing_inventory (user_id, guild_id, fish_name, length, price_per_cm) VALUES (?, ?, ?, ?, ?)", 
            (user_id, guild_id, fish["name"], length, fish.get("price_per_cm", 100))
        )

        current_user = self.db.get_user(user_id)
        current_max = current_user.get('max_fish_length', 0.0) if current_user else 0.0
        if length > current_max:
            self.db.execute_query("UPDATE users SET max_fish_length = ? WHERE user_id = ? AND guild_id = ?", (length, user_id, guild_id))
            max_record_text = f"\n\n🏆 **개인 최고 기록 경신!** ({length}cm)"
        else:
            max_record_text = ""

        rarity_colors = {"흔함": discord.Color.light_gray(), "희귀": discord.Color.blue(), "신종": discord.Color.purple(), "전설": discord.Color.gold(), "환상": discord.Color.red()}
        embed_color = rarity_colors.get(fish.get("rarity", "흔함"), discord.Color.blue())

        embed = discord.Embed(
            title=f"🎉 월척입니다! [{fish.get('rarity', '흔함')}] 어종!", 
            description=f"**[{fish['name']} ({length}cm)]**을(를) 낚아 가방에 넣었습니다!\n*{fish.get('effect_desc', '')}*{max_record_text}\n\n✨ XP +10\n🛒 물고기는 `/낚시가게 관리 액션:sell`로 일괄 정산 가능합니다.", 
            color=embed_color
        )
        await interaction.followup.edit_message(message_id=self.message.id, embed=embed, view=None)


# 💳 낚시터 이용 구매 뷰
class GroundAccessView(discord.ui.View):
    def __init__(self, user: discord.Member, fee: int, open_t: int, close_t: int, db_manager: DatabaseManager):
        super().__init__(timeout=60.0)
        self.user = user
        self.fee = fee
        self.open_t = open_t
        self.close_t = close_t
        self.db = db_manager

    @discord.ui.button(label="💳 이용권 구매", style=discord.ButtonStyle.success)
    async def buy(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("자신의 이용권만 구매할 수 있습니다!", ephemeral=True)

        user_cash = self.db.get_user_cash(str(self.user.id)) or 0
        if user_cash < self.fee:
            return await interaction.response.send_message("❌ 소지 금액이 부족합니다.", ephemeral=True)

        self.db.add_user_cash(str(self.user.id), -self.fee)
        self.db.add_transaction(str(self.user.id), "낚시터 입장권 구매", -self.fee, "낚시터 사용")

        ground = self.db.execute_query("SELECT owner_id FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (str(interaction.channel_id), str(interaction.guild_id)), 'one')
        if ground and ground['owner_id']:
            self.db.add_user_cash(ground['owner_id'], self.fee)
            self.db.add_transaction(ground['owner_id'], "낚시터 입장권 수익", self.fee, f"{self.user.display_name}의 입장료")

        embed = discord.Embed(title="🎫 구매 완료!", description="낚시터 이용권 구매가 완료되었습니다! 바로 낚시를 즐기세요.", color=discord.Color.green())
        await interaction.response.edit_message(embed=embed, view=None)

        # 5분 전 알람 스케줄링 (24시간제로만 동작하므로 별도 낚시 스케줄링에 비동기 루프 연동)
        await asyncio.sleep(5) # 예제 딜레이: 실 구현시 이용 시간 끝에 맞춤.
        try:
            await interaction.followup.send("⚠️ 낚시터 이용 시간이 5분 남았습니다!", ephemeral=True)
        except: pass

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인만 취소할 수 있습니다!", ephemeral=True)
        embed = discord.Embed(title="❌ 취소됨", description="구매를 취소했습니다.", color=discord.Color.red())
        await interaction.response.edit_message(embed=embed, view=None)


# ⚖️ 낚시터 업다운, 시설건설/철거 1차 확인 뷰
class ConfirmActionView(discord.ui.View):
    def __init__(self, user: discord.Member):
        super().__init__(timeout=30.0)
        self.user = user
        self.value = None

    @discord.ui.button(label="✅ 확인", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인만 버튼을 클릭할 수 있습니다!", ephemeral=True)
        self.value = True
        self.stop()
        await interaction.response.defer()

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.danger)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user != self.user:
            return await interaction.response.send_message("본인만 버튼을 클릭할 수 있습니다!", ephemeral=True)
        self.value = False
        self.stop()
        await interaction.response.defer()


# ==========================================
# ⌨️ [Cog: 명령어 통합 그룹]
# ==========================================

class FishingSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_cog = None

    async def cog_load(self):
        self.db_cog = self.bot.get_cog("DatabaseManager")

    def _get_db(self, interaction: discord.Interaction):
        return self.db_cog.get_manager(interaction.guild_id)

    # 📂 그룹 명령어 정의
    fish_info_group = app_commands.Group(name="낚시정보", description="자신의 낚시 정보 및 랭킹을 확인합니다.")
    fishing_ground_group = app_commands.Group(name="낚시터", description="낚시터 이용 및 소유 관리 명령어 그룹")
    fishing_shop_group = app_commands.Group(name="낚시가게", description="낚시 장비 구입, 강화 및 판매 명령어 그룹")
    fishing_admin_group = app_commands.Group(name="낚시관리", description="[관리자 전용] 시스템 관리 명령어 그룹")


    # ==========================================
    # 🎣 1. 독립 명령어 (/낚시, /ㄴㅅ)
    # ==========================================

    async def _do_fish_start(self, interaction: discord.Interaction):
        if not self.db_cog:
            return await interaction.response.send_message("❌ DB 시스템을 로드할 수 없습니다.", ephemeral=True)

        db = self._get_db(interaction)
        user_data = db.get_user(str(interaction.user.id))
        if not user_data:
            return await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 명단에 등록해주세요.", ephemeral=True)

        # ✅ 유저가 active_sessions에 남아있다면 실행 거부
        if interaction.user.id in active_sessions:
            return await interaction.response.send_message("⚠️ 이미 낚시 진행 중이거나 종료된 지 얼마 되지 않았습니다! 잠시 후(5초 쿨타임)에 다시 시도해 주세요.", ephemeral=True)

        view = FishingGameView(interaction.user, db, interaction.channel_id)
        active_sessions[interaction.user.id] = view
        await view.start_game(interaction)

    @app_commands.command(name="낚시", description="채널에서 낚시 게임을 시작합니다 (ㄴㅅ)")
    async def fish_start(self, interaction: discord.Interaction):
        await self._do_fish_start(interaction)

    @app_commands.command(name="ㄴㅅ", description="채널에서 낚시 게임을 시작합니다 (ㄴㅅ 단축어)")
    async def fish_start_short(self, interaction: discord.Interaction):
        await self._do_fish_start(interaction)

    @app_commands.command(name="낚시중지", description="[관리자 전용] 특정 유저의 멈춘 낚시 세션을 강제 중단합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(대상유저="멈추게 할 유저를 멘션하거나 ID를 입력하세요.")
    async def fish_stop(self, interaction: discord.Interaction, 대상유저: discord.Member):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message("🚫 관리자만 사용할 수 있습니다.", ephemeral=True)

        if 대상유저.id not in active_sessions:
            return await interaction.response.send_message(f"ℹ️ {대상유저.display_name} 유저는 진행 중인 낚시가 없습니다.", ephemeral=True)

        view = active_sessions[대상유저.id]
        view.responded = True
        view.stop()
        if view.message: 
            try:
                await view.message.edit(view=None)
            except: pass
        active_sessions.pop(대상유저.id, None)
        await interaction.response.send_message(f"✅ {대상유저.display_name} 유저의 낚시 세션 강제 초기화 완료.", ephemeral=True)


    # ==========================================
    # 📊 2. [/낚시정보] 그룹
    # ==========================================

    @fish_info_group.command(name="조회", description="내 낚시 수첩을 보거나 랭킹을 조회합니다.")
    @app_commands.describe(분류="서버 혹은 채널 랭킹 조건 조회")
    @app_commands.choices(분류=[
        app_commands.Choice(name="내 정보 보기", value="me"),
        app_commands.Choice(name="서버 개인 명성 TOP 10", value="server_rep"),
        app_commands.Choice(name="서버 물고기 크기 TOP 10", value="server_fish"),
        app_commands.Choice(name="서버 낚시터 명성 TOP 10", value="server_ground"),
        app_commands.Choice(name="채널 개인 명성 TOP 10", value="channel_rep"),
        app_commands.Choice(name="채널 물고기 크기 TOP 10", value="channel_fish"),
        app_commands.Choice(name="채널 낚시터 명성 TOP 10", value="channel_ground")
    ])
    async def fish_info_main(self, interaction: discord.Interaction, 분류: Optional[str] = "me"):
        await interaction.response.defer()
        db = self._get_db(interaction)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)

        # 1. 내 정보
        if 분류 == "me":
            # 📌 안전하게 컬럼 생성 시도
            try:
                db.execute_query("ALTER TABLE users ADD COLUMN fishing_reputation INTEGER DEFAULT 0")
            except Exception:
                pass

            user_data = db.get_user(user_id)
            if not user_data: return await interaction.followup.send("❗ 아직 등록되지 않은 사용자입니다.")
            xp_data = db.get_user_xp(user_id)

            embed = discord.Embed(title=f"🎣 {interaction.user.display_name}의 낚시 수첩", color=discord.Color.blue())
            embed.add_field(name="📈 레벨", value=f"Lv. {xp_data.get('level', 1)}", inline=True)
            embed.add_field(name="💰 보유 현금", value=f"{user_data.get('cash', 0):,}원", inline=True)
            embed.add_field(name="🌟 개인 명성", value=f"{user_data.get('fishing_reputation', 0):,} 명성", inline=True)
            embed.add_field(name="📏 최대 크기", value=f"{user_data.get('max_fish_length', 0.0)} cm", inline=True)
            return await interaction.followup.send(embed=embed)

        # 2. 랭킹 처리 (서버 vs 채널)
        embed = discord.Embed(color=discord.Color.gold())
        ranking_list = []

        is_channel_query = "channel" in 분류

        if "rep" in 분류:
            embed.title = "🏆 개인 명성 TOP 10 (" + ("현재 채널" if is_channel_query else "전체 서버") + ")"
            
            # 📌 [1] 안전하게 컬럼 생성 시도
            try:
                db.execute_query("ALTER TABLE users ADD COLUMN fishing_reputation INTEGER DEFAULT 0")
            except Exception:
                pass

            results = db.execute_query("SELECT display_name, username, IFNULL(fishing_reputation, 0) as score FROM users WHERE guild_id = ? ORDER BY score DESC LIMIT 10", (guild_id,), 'all')
            
            # 📌 [2] results가 None이 아닐 때만 반복하도록 방어 코드 추가
            if results:
                for i, row in enumerate(results, 1): 
                    ranking_list.append(f"**{i}위.** {row['display_name'] or row['username']} : `{row['score']:,} 명성`")

        elif "fish" in 분류:
            embed.title = "🐋 최대 물고기 크기 TOP 10 (" + ("현재 채널" if is_channel_query else "전체 서버") + ")"
            # 인벤토리 테이블을 통해 채널별 조회 스케일링
            query_str = "SELECT u.display_name, u.username, MAX(i.length) as score FROM fishing_inventory i JOIN users u ON i.user_id = u.user_id WHERE i.guild_id = ?"
            args = [guild_id]
            if is_channel_query:
                # 가설: 채널을 fishing_inventory 에 기록하지 않기 때문에 원안과 users 매핑은 동일하게 가되 메시지 디자인만 수정
                pass 
            query_str += " GROUP BY u.user_id ORDER BY score DESC LIMIT 10"
            results = db.execute_query(query_str, args, 'all')
            for i, row in enumerate(results, 1): ranking_list.append(f"**{i}위.** {row['display_name'] or row['username']} : `{row['score']} cm`")

        elif "ground" in 분류:
            embed.title = "🏭 낚시터 명성 TOP 10 (" + ("현재 채널" if is_channel_query else "전체 서버") + ")"
            query_str = "SELECT channel_name, ground_reputation as score FROM fishing_ground WHERE guild_id = ?"
            args = [guild_id]
            if is_channel_query:
                query_str += " AND channel_id = ?"
                args.append(str(interaction.channel_id))
            query_str += " ORDER BY score DESC LIMIT 10"
            results = db.execute_query(query_str, args, 'all')
            for i, row in enumerate(results, 1): ranking_list.append(f"**{i}위.** {row['channel_name']} : `{row['score']:,} 명성`")

        embed.description = "\n".join(ranking_list) if ranking_list else "📊 데이터가 존재하지 않습니다."
        await interaction.followup.send(embed=embed)


    # ==========================================
    # 🏠 3. [/낚시터] 그룹
    # ==========================================

    def _get_ground(self, db, guild_id, channel_id, channel_name):
        check_col = db.execute_query("PRAGMA table_info(fishing_ground)", None, 'all')
        columns = [col['name'] for col in check_col] if check_col else []

        if 'ground_type' not in columns:
            db.execute_query("ALTER TABLE fishing_ground ADD COLUMN ground_type TEXT DEFAULT '호수'")

        ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (channel_id, guild_id), 'one')
        if not ground:
            db.execute_query("INSERT INTO fishing_ground (channel_id, guild_id, channel_name, ground_type) VALUES (?, ?, ?, '호수')", (channel_id, guild_id, channel_name))
            ground = db.execute_query("SELECT * FROM fishing_ground WHERE channel_id = ? AND guild_id = ?", (channel_id, guild_id), 'one')
        return dict(ground)

    @fishing_ground_group.command(name="공용", description="낚시터 정보 조회, 매입, 매각, 이용권을 구매합니다.")
    @app_commands.describe(액션="원하는 명령 행동 선택")
    @app_commands.choices(액션=[
        app_commands.Choice(name="정보 - 낚시터 정보 조회", value="info"),
        app_commands.Choice(name="매입 - 낚시터 땅 구매", value="buy"),
        app_commands.Choice(name="매각 - 소유 낚시터 판매", value="sell"),
        app_commands.Choice(name="이용 - 낚시터 이용권 구매", value="use")
    ])
    async def ground_general(self, interaction: discord.Interaction, 액션: str):
        await interaction.response.defer()
        db = self._get_db(interaction)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        ground = self._get_ground(db, guild_id, channel_id, interaction.channel.name)

        # 1. 정보
        if 액션 == "info":
            owner_mention = f"<@{ground['owner_id']}>" if ground['owner_id'] else "서버 소유"
            facilities_built = db.execute_query("SELECT facility_name FROM fishing_facilities WHERE channel_id = ? AND guild_id = ?", (channel_id, guild_id), 'all')
            facility_list = ", ".join([row["facility_name"] for row in facilities_built]) if facilities_built else "없음"

            embed = discord.Embed(title=f"🌊 {interaction.channel.name} 낚시터 정보", color=discord.Color.blue())
            embed.add_field(name="👑 땅주인", value=owner_mention, inline=True)
            embed.add_field(name="🗺️ 지형 종류", value=f"**{ground.get('ground_type', '호수')}**", inline=True) # 👈 지형 텍스트 추가
            embed.add_field(name="⭐ 등급", value=f"{ground.get('tier', 1)}티어", inline=True)
            embed.add_field(name="📊 낚시터 명성", value=f"{ground.get('ground_reputation', 0):,} 명성", inline=True)
            embed.add_field(name="💸 매입가", value=f"{ground.get('ground_price', 0):,}원", inline=True)
            embed.add_field(name="🏗️ 건설된 시설", value=facility_list, inline=False)
            return await interaction.followup.send(embed=embed)

        # 2. 매입 (주인 유무 상관 없이 돈을 주면 구매 가능하도록 연동)
        elif 액션 == "buy":
            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN purchasable INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN is_public INTEGER DEFAULT 0")
            except Exception:
                pass
            
            updated_ground = self._get_ground(db, guild_id, channel_id, interaction.channel.name)

            if updated_ground.get('is_public') == 1:
                return await interaction.followup.send("❌ 이 채널은 관리자가 지정한 **공용 낚시터**이므로 구매할 수 없습니다.")

            if updated_ground.get('purchasable') != 1:
                return await interaction.followup.send("❌ 이 채널은 관리자가 **구매 가능 낚시터**로 지정하지 않은 일반 채널입니다.")

            user_cash = db.get_user_cash(user_id) or 0
            price = updated_ground.get('ground_price', 100000)

            if updated_ground.get('owner_id') == user_id:
                return await interaction.followup.send("❌ 이미 당신의 땅입니다!")

            if user_cash < price:
                return await interaction.followup.send(f"❌ 소지 금액이 부족합니다. (매입가: {price:,}원)")

            # 이전 주인이 있으면 정산
            if updated_ground.get('owner_id'):
                db.add_user_cash(updated_ground['owner_id'], price)
                db.add_transaction(updated_ground['owner_id'], "낚시터 판매 매각금", price, f"{interaction.channel.name} 땅 판매")

            db.add_user_cash(user_id, -price)
            db.add_transaction(user_id, "낚시터 매입", -price, f"{interaction.channel.name} 땅 구매")
            db.execute_query("UPDATE fishing_ground SET owner_id = ? WHERE channel_id = ? AND guild_id = ?", (user_id, channel_id, guild_id))

            # 🏷️ 디스코드 채널명 '유저닉네임-낚시터'로 자동 변경 봇 기능
            try:
                new_channel_name = f"🎣ㅣ{interaction.user.display_name}-낚시터"
                await interaction.channel.edit(name=new_channel_name)
                db.execute_query("UPDATE fishing_ground SET channel_name = ? WHERE channel_id = ? AND guild_id = ?", (new_channel_name, channel_id, guild_id))
                rename_msg = f"\n🏷️ 채널명이 **'{new_channel_name}'**(으)로 변경되었습니다!"
            except discord.Forbidden:
                rename_msg = "\n⚠️ 봇의 권한 부족으로 디스코드 채널명을 직접 변경하지 못했습니다. (서버 권한 확인 필요)"

            return await interaction.followup.send(f"🎉 **{interaction.channel.name}** 낚시터를 매입했습니다!{rename_msg}")

        # 3. 매각
        elif 액션 == "sell":
            if ground.get('owner_id') != user_id:
                return await interaction.followup.send("❌ 해당 낚시터의 주인이 아닙니다.")

            price = ground.get('ground_price', 0)
            db.add_user_cash(user_id, price)
            db.add_transaction(user_id, "낚시터 매각", price, f"{interaction.channel.name} 매각 환불")
            db.execute_query("UPDATE fishing_ground SET owner_id = NULL WHERE channel_id = ? AND guild_id = ?", (channel_id, guild_id))
            return await interaction.followup.send(f"🏢 낚시터를 매각하여 **{price:,}원**을 돌려받았습니다.")
        
        # 4. 이용권 구매 (시간, 이용 요금 띄워주는 초기화면)
        elif 액션 == "use":
            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN entry_fee INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN open_time INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN close_time INTEGER DEFAULT 24")
            except Exception:
                pass

            ground_updated = self._get_ground(db, guild_id, channel_id, interaction.channel.name)

            ground_updated = self._get_ground(db, guild_id, channel_id, interaction.channel.name)
            open_t = ground_updated.get('open_time', 0)
            close_t = ground_updated.get('close_time', 24)
            fee = ground_updated.get('entry_fee', 0)

            embed = discord.Embed(title="🎣 낚시터 이용권 구매 안내", description=f"**낚시터 채널**: {interaction.channel.name}\n**운영 시간**: {open_t}시 ~ {close_t}시\n**이용 요금**: {fee:,}원\n\n이용권 구매 버튼을 누르면 시간이 소모됩니다.", color=discord.Color.teal())
            view = GroundAccessView(interaction.user, fee, open_t, close_t, db)
            return await interaction.followup.send(embed=embed, view=view)


    # 👑 낚시터 주인 전용
    @fishing_ground_group.command(name="주인설정", description="[낚시터 주인 전용] 땅값, 이용금액, 이용시간, 시설 등을 관리합니다.")
    @app_commands.describe(액션="원하는 설정 행동 선택", 값="설정할 수치 (예: 땅값 변경 시 금액 등 입력, 시설명 입력)")
    @app_commands.choices(액션=[
        app_commands.Choice(name="지형변경 - 호수/바다/늪 지형 타입 변경", value="change_type"), # 👈 지형변경 추가!
        app_commands.Choice(name="땅값변경 - 낚시터 매입 기준가 수정", value="price"),
        app_commands.Choice(name="이용금액 - 입장료 설정", value="fee"),
        app_commands.Choice(name="이용시간 - 오픈/마감 설정 (24시형식, 예: 9-18)", value="time_limit"),
        app_commands.Choice(name="업다운 - 티어 변경 (티어 당 명성 소모/일부 반환)", value="tier_ctrl"),
        app_commands.Choice(name="시설정보 - 지을 수 있는 구조물 설명", value="fac_info"),
        app_commands.Choice(name="건설목록 - 현재 상태로 건설 가능한 시설", value="fac_list"),
        app_commands.Choice(name="시설건설 - 명성을 소모하여 시설 건축", value="fac_build"),
        app_commands.Choice(name="시설철거 - 건축물을 파괴하고 명성 회수", value="fac_destroy")
    ])
    async def ground_owner(self, interaction: discord.Interaction, 액션: str, 값: Optional[str] = None):
        await interaction.response.defer()
        db = self._get_db(interaction)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        ground = self._get_ground(db, guild_id, channel_id, interaction.channel.name)

        if ground.get('owner_id') != user_id and 액션 not in ["fac_info"]:
            return await interaction.followup.send("❌ 당신은 이 낚시터의 주인이 아닙니다!")

        # 1. 땅값 변경
        if 액션 == "price":
            if not 값 or not 값.isdigit() or int(값) <= 0:
                return await interaction.followup.send("❌ 올바른 금액을 숫자로 입력하세요. (파라미터: 값)")
            db.execute_query("UPDATE fishing_ground SET ground_price = ? WHERE channel_id = ? AND guild_id = ?", (int(값), channel_id, guild_id))
            return await interaction.followup.send(f"✅ 땅값이 **{int(값):,}원**으로 변경되었습니다.")
        
        # ✅ 액션: 지형 변경
        if 액션 == "change_type":
            if not 값 or 값 not in ["호수", "바다", "늪"]:
                return await interaction.followup.send("❌ '값' 파라미터에 정확한 지형(`호수`, `바다`, `늪`) 중 하나를 입력하세요.")

            if ground.get('ground_type', '호수') == 값:
                return await interaction.followup.send(f"❌ 이미 현재 지형이 **[{값}]**입니다.")

            # 지형 개간 비용 설정 (예: 명성 5,000점 소모)
            req_rep = 5000 
            current_rep = ground.get("ground_reputation", 0)

            if current_rep < req_rep:
                return await interaction.followup.send(f"❌ 낚시터 지형을 개간할 명성이 부족합니다! (필요 명성: {req_rep:,} / 현재 명성: {current_rep:,})")

            # 1차 확인 절차 뷰 출력
            confirm_view = ConfirmActionView(interaction.user)
            await interaction.followup.send(f"🚜 정말로 낚시터 지형을 **[{값}]**(으)로 공사하시겠습니까?\n(낚시터 명성 **{req_rep:,}점**이 소모됩니다.)", view=confirm_view)
            await confirm_view.wait()

            if confirm_view.value:
                # 명성 차감 및 지형 데이터 업데이트
                db.execute_query("UPDATE fishing_ground SET ground_type = ?, ground_reputation = ground_reputation - ? WHERE channel_id = ? AND guild_id = ?", (값, req_rep, channel_id, guild_id))
                await interaction.followup.send(f"✅ 공사가 완료되었습니다! 이 채널의 낚시터 지형이 **[{값}]** 환경으로 바인딩되었습니다! 명성 {req_rep:,}점이 차감되었습니다.")
            else:
                await interaction.followup.send("❌ 지형 공사가 취소되었습니다.")

        # 2. 이용금액
        elif 액션 == "fee":
            if not 값 or not 값.isdigit() or int(값) < 0:
                return await interaction.followup.send("❌ 올바른 이용료를 0 이상 숫자로 입력하세요.")
            
            # 📌 try-except 로 감싸서 안전하게 컬럼을 추가합니다.
            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN entry_fee INTEGER DEFAULT 0")
            except Exception:
                pass

            db.execute_query("UPDATE fishing_ground SET entry_fee = ? WHERE channel_id = ? AND guild_id = ?", (int(값), channel_id, guild_id))
            return await interaction.followup.send(f"✅ 낚시터 입장 요금이 **{int(값):,}원**으로 변경되었습니다.")

        # 3. 이용 시간 (포맷 예: 9-18)
        elif 액션 == "time_limit":
            if not 값 or '-' not in 값:
                return await interaction.followup.send("❌ 포맷 형식을 맞춰주세요. (예: 9-18)")
            try:
                start_t, end_t = map(int, 값.split('-'))
                if not (0 <= start_t <= 23) or not (0 <= end_t <= 23): raise ValueError
            except:
                return await interaction.followup.send("❌ 시간은 0시~23시 사이여야 합니다.")

            # 📌 안전하게 컬럼 생성 시도
            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN open_time INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN close_time INTEGER DEFAULT 24")
            except Exception:
                pass

            db.execute_query("UPDATE fishing_ground SET open_time = ?, close_time = ? WHERE channel_id = ? AND guild_id = ?", (start_t, end_t, channel_id, guild_id))
            return await interaction.followup.send(f"✅ 운영 시간이 **{start_t}시 ~ {end_t}시**로 설정되었습니다.")

        # 4. 티어 업다운 (확인 절차 1차)
        elif 액션 == "tier_ctrl":
            if not 값 or 값 not in ["업", "다운"]:
                return await interaction.followup.send("❌ '값' 파라미터에 '업' 또는 '다운'을 입력하세요.")

            # 📌 명성과 티어 데이터를 확실하게 숫자형(int)으로 변환하여 계산 오류 방지
            current_tier = int(ground.get("tier") if ground.get("tier") is not None else 1)
            current_rep = int(ground.get("ground_reputation") if ground.get("ground_reputation") is not None else 0)

            confirm_view = ConfirmActionView(interaction.user)
            await interaction.followup.send(f"⚠️ 정말로 낚시터 티어를 **{값}** 하시겠습니까?\n(현재 티어: {current_tier}티어 / 보유 낚시터 명성: {current_rep:,})", view=confirm_view)
            await confirm_view.wait()

            if confirm_view.value:
                if 값 == "업":
                    req_rep = current_tier * 1000 # 1티어->2티어는 1000점 필요
                    if current_rep < req_rep: 
                        return await interaction.followup.send(f"❌ 낚시터 명성이 부족합니다. (필요 명성: {req_rep:,} / 보유 명성: {current_rep:,})")
                    
                    db.execute_query("UPDATE fishing_ground SET tier = tier + 1, ground_reputation = ground_reputation - ? WHERE channel_id = ? AND guild_id = ?", (req_rep, channel_id, guild_id))
                    await interaction.followup.send(f"🆙 낚시터 등급이 **{current_tier + 1}티어**가 되었습니다!")
                else:
                    if current_tier <= 1: 
                        return await interaction.followup.send("❌ 이미 최저 1티어입니다.")
                    # 다운 시 명성 일부(500) 환급
                    db.execute_query("UPDATE fishing_ground SET tier = tier - 1, ground_reputation = ground_reputation + 500 WHERE channel_id = ? AND guild_id = ?", (channel_id, guild_id))
                    await interaction.followup.send(f"⬇️ 낚시터 등급이 **{current_tier - 1}티어**로 내려갔고 명성 500점을 환산받았습니다.")
            else:
                await interaction.followup.send("❌ 작업이 취소되었습니다.")

        # 5. 시설 정보
        elif 액션 == "fac_info":
            # 카테고리 정의
            categories = {
                "🎫 매표소 (수수료 조정)": ["간이매표소", "매표소", "일반매표소", "중형매표소", "대형매표소", "거대한매표소"],
                "📦 창고 (물고기 확률 증가)": ["창고", "소형창고", "중형창고", "대형창고", "초거대한창고"],
                "🧹 환경 시설 (쓰레기 감소/처리)": ["환경미화원", "청소용역업체", "시설관리공단", "재활용분리수거장", "쓰레기소각장", "환경부"],
                "⚡ 발전기 및 상점 (유지비 감소)": ["전기배터리", "소형발전기", "중대형발전기", "화력발전소", "수력발전소", "리안마켓", "묵이 편의점", "할인마트", "정E-마트   ", "해외수출사업"],
                "✨ 기념품 및 어시장 (명성/물고기 가격 증가)": ["길거리상인", "기념품상점", "기념품백화점", "해외입점준비", "해외유명기업", "노상", "물사랑고기사랑 가게", "5일장시장", "회전문공장", "세계1위기업"],
                "🏫 교육 시설 (방해요소: 낚시 실패확률 증가)": ["어린이집", "유치원", "초등학교", "중학교", "고등학교"]
            }

            # 첫 번째 안내 메시지
            await interaction.followup.send("🏗️ **낚시터 시설 목록 조회를 시작합니다.** (내용이 길어 카테고리별로 나누어 전송됩니다.)")

            for cat_name, fac_list in categories.items():
                embed = discord.Embed(title=cat_name, color=discord.Color.green())
                
                for name in fac_list:
                    if name in FACILITIES:
                        data = FACILITIES[name]
                        embed.add_field(
                            name=f"{name} ({data['tier']}티어 필요)", 
                            value=f"- 필요 명성: {data['req_rep']:,}\n- 건설 비용: {data.get('req_cash', 0):,}원\n- 효과: {data['desc']}", 
                            inline=False
                        )
                
                # 카테고리별로 Embed 전송
                await interaction.followup.send(embed=embed)
            
            return

        # 6. 건설 가능 목록
        elif 액션 == "fac_list":
            tier = ground.get('tier', 1)
            reputation = ground.get('ground_reputation', 0)
            user_cash = db.get_user_cash(user_id) or 0

            valid_facilities = []
            
            for name, data in FACILITIES.items():
                # 📌 조건 완화: 티어와 명성만 맞으면 돈이 부족해도 일단 목록에 표시합니다.
                if tier >= data["tier"] and reputation >= data["req_rep"]:
                    valid_facilities.append((name, data))

            if not valid_facilities:
                return await interaction.followup.send("📋 **현재 낚시터 티어와 명성 조건에 맞는 건설 가능한 시설이 없습니다.** (티어를 올리거나 명성을 더 쌓아보세요!)")

            await interaction.followup.send(f"🛠️ **현재 티어/명성으로 건설 가능한 시설 목록입니다.** (총 {len(valid_facilities)}개)")

            embed = discord.Embed(title="🏗️ 건설 가능한 시설 목록", color=discord.Color.orange())
            field_count = 0

            for name, data in valid_facilities:
                if field_count >= 20:
                    await interaction.followup.send(embed=embed)
                    embed = discord.Embed(title="🏗️ 건설 가능한 시설 목록 (이어서)", color=discord.Color.orange())
                    field_count = 0

                # 돈이 부족한 시설은 ❌ 표시를 해줍니다.
                cash_req = data.get('req_cash', 0)
                cash_status = "✅ 건설 가능" if user_cash >= cash_req else "❌ 돈 부족"

                embed.add_field(
                    name=f"{name} ({data['tier']}티어)",
                    value=f"- 소모 명성: {data['req_rep']:,}\n- 필요 비용: {cash_req:,}원\n- 보유 현금: {user_cash:,}원 ({cash_status})\n- 효과: {data['desc']}",
                    inline=False
                )
                field_count += 1

            if field_count > 0:
                await interaction.followup.send(embed=embed)

            return

        # 7. 시설 건설 (확인 절차 1차)
        elif 액션 == "fac_build":
            if not 값 or 값 not in FACILITIES:
                return await interaction.followup.send("❌ 올바른 시설명을 입력하세요. (값 파라미터)")
            
            db.create_table("fishing_facilities", "channel_id TEXT NOT NULL, guild_id TEXT NOT NULL, facility_name TEXT NOT NULL, PRIMARY KEY(channel_id, guild_id, facility_name)")
            existing = db.execute_query("SELECT * FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (channel_id, guild_id, 값), 'one')
            if existing: return await interaction.followup.send("❌ 이미 지어진 시설입니다.")

            fac = FACILITIES[값]
            user_cash = db.get_user_cash(user_id) or 0

            # 📌 명성과 티어 데이터를 확실하게 숫자형(int)으로 변환
            current_tier = int(ground.get("tier") if ground.get("tier") is not None else 1)
            current_rep = int(ground.get("ground_reputation") if ground.get("ground_reputation") is not None else 0)

            # 명성 및 건설 비용(돈) 검증
            if current_tier < fac["tier"]:
                return await interaction.followup.send(f"❌ 낚시터 티어가 부족합니다. (건설 필요: {fac['tier']}티어 / 현재: {current_tier}티어)")
            
            if current_rep < fac["req_rep"]:
                return await interaction.followup.send(f"❌ 낚시터 명성이 부족합니다. (건설 필요: {fac['req_rep']:,} / 보유: {current_rep:,})")

            if user_cash < fac.get("req_cash", 0):
                return await interaction.followup.send(f"❌ 건설 비용(돈)이 부족합니다! (필요 금액: {fac.get('req_cash', 0):,}원 / 보유 현금: {user_cash:,}원)")

            confirm_view = ConfirmActionView(interaction.user)
            await interaction.followup.send(f"🏗️ 정말로 **[{값}]** 시설을 건설하시겠습니까?\n(낚시터 명성 {fac['req_rep']:,} 소모 및 건설 비용 {fac.get('req_cash', 0):,}원 차감)", view=confirm_view)
            await confirm_view.wait()

            if confirm_view.value:
                # 명성과 돈 함께 차감
                db.execute_query("UPDATE fishing_ground SET ground_reputation = ground_reputation - ? WHERE channel_id = ? AND guild_id = ?", (fac["req_rep"], channel_id, guild_id))
                db.add_user_cash(user_id, -fac.get("req_cash", 0))
                db.add_transaction(user_id, f"시설 건설 [{값}]", -fac.get("req_cash", 0), f"{interaction.channel.name} 시설 건설비")
                
                db.execute_query("INSERT INTO fishing_facilities (channel_id, guild_id, facility_name) VALUES (?, ?, ?)", (channel_id, guild_id, 값))
                await interaction.followup.send(f"🔨 **[{값}]** 건설이 완료되었습니다! 명성과 돈이 차감되었습니다.")
            else:
                await interaction.followup.send("❌ 건축이 취소되었습니다.")

        # 8. 시설 철거 (확인 절차 1차, 명성 일부 환급)
        elif 액션 == "fac_destroy":
            if not 값 or 값 not in FACILITIES:
                return await interaction.followup.send("❌ 올바른 시설명을 입력하세요.")

            existing = db.execute_query("SELECT * FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (channel_id, guild_id, 값), 'one')
            if not existing: return await interaction.followup.send("❌ 건설되지 않은 시설입니다.")

            confirm_view = ConfirmActionView(interaction.user)
            await interaction.followup.send(f"🪓 정말로 지어진 **[{값}]** 시설을 철거하시겠습니까? (파괴 시 명성 일부가 환산됩니다)", view=confirm_view)
            await confirm_view.wait()

            if confirm_view.value:
                refund_rep = int(FACILITIES[값]["req_rep"] * 0.5) # 철거 시 반절 환불
                db.execute_query("DELETE FROM fishing_facilities WHERE channel_id = ? AND guild_id = ? AND facility_name = ?", (channel_id, guild_id, 값))
                db.execute_query("UPDATE fishing_ground SET ground_reputation = ground_reputation + ? WHERE channel_id = ? AND guild_id = ?", (refund_rep, channel_id, guild_id))
                await interaction.followup.send(f"🪓 **[{값}]** 철거가 완료되었습니다. 명성 {refund_rep}점을 반환받았습니다.")
            else:
                await interaction.followup.send("❌ 철거가 취소되었습니다.")


    # ==========================================
    # 🛒 4. [/낚시가게] 그룹
    # ==========================================

    def _get_gear(self, db, user_id, guild_id):
        db.create_table("fishing_gear", "user_id TEXT NOT NULL, guild_id TEXT NOT NULL, rod_level INTEGER DEFAULT 0, rod_durability INTEGER DEFAULT 100, bait_level INTEGER DEFAULT 0, bait_count INTEGER DEFAULT 0, PRIMARY KEY (user_id, guild_id)")
        gear = db.execute_query("SELECT * FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'one')
        if not gear:
            db.execute_query("INSERT INTO fishing_gear (user_id, guild_id) VALUES (?, ?)", (user_id, guild_id))
            gear = db.execute_query("SELECT * FROM fishing_gear WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'one')
        return dict(gear)

    @fishing_shop_group.command(name="관리", description="물고기 판매, 미끼 및 낚싯대 구매/수리/강화를 관리합니다.")
    @app_commands.describe(액션="원하는 상점 행동", 값="개수(미끼구입 시) 등 추가 데이터")
    @app_commands.choices(액션=[
        app_commands.Choice(name="판매 - 가방 속 물고기 전량 판매", value="sell"),
        app_commands.Choice(name="미끼구입 - 개당 50원", value="bait_buy"),
        app_commands.Choice(name="미끼업그레이드 - 미끼 레벨 업 (최대 5레벨)", value="bait_upgrade"),
        app_commands.Choice(name="낚시대정보 - 장비 스펙 확인", value="rod_info"),
        app_commands.Choice(name="낚시대구입 - 초보자 낚싯대 (10000원)", value="rod_buy"),
        app_commands.Choice(name="낚시대업그레이드 - 낚싯대 레벨업 (최대 5레벨)", value="rod_upgrade"),
        app_commands.Choice(name="낚시대수리 - 내구도 수리 (내구 5당 100원)", value="rod_repair")
    ])
    async def shop_main(self, interaction: discord.Interaction, 액션: str, 값: Optional[str] = None):
        await interaction.response.defer()
        db = self._get_db(interaction)
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)

        user_cash = db.get_user_cash(user_id) or 0

        # 1. 판매
        if 액션 == "sell":
            fish_list = db.execute_query("SELECT id, fish_name, length, price_per_cm FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'all')
            if not fish_list: return await interaction.followup.send("🪹 가방에 물고기가 없습니다.")

            # ✅ 'price_per_cm'의 로우 데이터를 직접 매핑하여 곱합니다.
            total_price = sum([int(fish['length'] * fish['price_per_cm']) for fish in fish_list])
            
            db.add_user_cash(user_id, total_price)
            db.add_transaction(user_id, "물고기 일괄 판매", total_price, f"물고기 {len(fish_list)}마리 판매")
            db.execute_query("DELETE FROM fishing_inventory WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))

            return await interaction.followup.send(f"💰 물고기 **{len(fish_list)}마리**를 모두 팔아 **{total_price:,}원**을 획득했습니다!")

        # 2. 미끼 구입 (개당 50원)
        elif 액션 == "bait_buy":
            if not 값 or not 값.isdigit() or int(값) <= 0:
                return await interaction.followup.send("❌ 1개 이상의 숫자를 '값' 파라미터에 적어주세요.")
            cost = int(값) * 50
            if user_cash < cost: return await interaction.followup.send("❌ 보유 현금이 부족합니다.")

            db.add_user_cash(user_id, -cost)
            self._get_gear(db, user_id, guild_id)
            db.execute_query("UPDATE fishing_gear SET bait_count = bait_count + ? WHERE user_id = ? AND guild_id = ?", (int(값), user_id, guild_id))
            return await interaction.followup.send(f"✅ 미끼 **{값}개**를 획득했습니다! (-{cost:,}원)")

        # 3. 미끼 업그레이드 (최대 5레벨)
        elif 액션 == "bait_upgrade":
            gear = self._get_gear(db, user_id, guild_id)
            if gear['bait_level'] >= 5: return await interaction.followup.send("❌ 이미 미끼가 최대 단계(5레벨)입니다!")

            cost = (gear['bait_level'] + 1) * 5000
            if user_cash < cost: return await interaction.followup.send("❌ 돈이 부족합니다.")

            db.add_user_cash(user_id, -cost)
            db.execute_query("UPDATE fishing_gear SET bait_level = bait_level + 1 WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            return await interaction.followup.send(f"🧪 미끼 레벨이 **Lv.{gear['bait_level'] + 1}**이 되었습니다! (+ 잘잡힐 확률 {gear['bait_level']+1}%) (-{cost:,}원)")

        # 4. 낚싯대 정보
        elif 액션 == "rod_info":
            gear = self._get_gear(db, user_id, guild_id)
            max_durability = 100 + (gear['rod_level'] * 100) # 레벨당 내구 최대치 증가 500까지

            embed = discord.Embed(title=f"🎣 {interaction.user.display_name}의 낚시 장비", color=discord.Color.purple())
            embed.add_field(name="🔱 낚싯대 레벨", value=f"Lv. {gear['rod_level']} / 5", inline=True)
            embed.add_field(name="❤️ 내구도", value=f"{gear['rod_durability']} / {max_durability}", inline=True)
            embed.add_field(name="🧪 미끼 등급", value=f"Lv. {gear['bait_level']} / 5", inline=True)
            embed.add_field(name="🪱 보유 미끼 수", value=f"{gear['bait_count']}개", inline=True)
            return await interaction.followup.send(embed=embed)

        # 5. 낚싯대 구입 (10000원)
        elif 액션 == "rod_buy":
            if user_cash < 10000: return await interaction.followup.send("❌ 돈이 부족합니다 (10,000원 필요).")
            db.add_user_cash(user_id, -10000)
            self._get_gear(db, user_id, guild_id)
            db.execute_query("UPDATE fishing_gear SET rod_level = 1, rod_durability = 100 WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            return await interaction.followup.send("🆕 초보자 낚싯대 세팅 완료! 기본 내구도가 100이 되었습니다.")

        # 6. 낚싯대 업그레이드 (레벨 최대 5단계, 단계당 내구도 100 증가)
        elif 액션 == "rod_upgrade":
            gear = self._get_gear(db, user_id, guild_id)
            if gear['rod_level'] >= 5: return await interaction.followup.send("❌ 이미 낚싯대가 최대 단계(5단계)입니다!")

            cost = (gear['rod_level'] + 1) * 10000
            if user_cash < cost: return await interaction.followup.send("❌ 돈이 부족합니다.")

            db.add_user_cash(user_id, -cost)
            # 내구도 자동 100 추가
            db.execute_query("UPDATE fishing_gear SET rod_level = rod_level + 1, rod_durability = rod_durability + 100 WHERE user_id = ? AND guild_id = ?", (user_id, guild_id))
            return await interaction.followup.send(f"🔥 낚싯대 강화 완료! 현재 **Lv.{gear['rod_level'] + 1}** (최대 내구도 {100 + ((gear['rod_level']+1)*100)}) (-{cost:,}원)")

        # 7. 낚싯대 수리 (내구도 5당 100원)
        elif 액션 == "rod_repair":
            gear = self._get_gear(db, user_id, guild_id)
            max_durability = 100 + (gear['rod_level'] * 100)
            
            if gear['rod_durability'] >= max_durability: return await interaction.followup.send("🛠️ 이미 내구도가 가득 차 있습니다.")
            missing_durability = max_durability - gear['rod_durability']
            
            # 5 당 100원 (즉 1당 20원)
            cost = missing_durability * 20

            if user_cash < cost: return await interaction.followup.send(f"❌ 수리비가 부족합니다. (필요: {cost:,}원)")
            db.add_user_cash(user_id, -cost)
            db.execute_query("UPDATE fishing_gear SET rod_durability = ? WHERE user_id = ? AND guild_id = ?", (max_durability, user_id, guild_id))
            return await interaction.followup.send(f"🔧 수리 완료! 내구도 {max_durability}로 가득 찼습니다. (-{cost:,}원)")


    # ==========================================
    # 👑 5. [/낚시관리] 그룹 (관리자용)
    # ==========================================

    @fishing_admin_group.command(name="설정", description="[관리자 전용] 낚시 시스템의 핵심 정책들을 관리합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(작업="실행할 관리자 작업", 값="설정할 수치 또는 상태 (예: 세금% / True 또는 False)")
    @app_commands.choices(작업=[
        app_commands.Choice(name="세금 - 물고기 판매/부동산 매입 수수료 비율 설정", value="tax"),
        app_commands.Choice(name="명성기능 - 유저 명성 및 유지비 수동 수정", value="reputation_ctrl"),
        app_commands.Choice(name="공용지정 - 현재 채널을 구매 불가능한 공용 낚시터로 지정", value="set_public"),
        app_commands.Choice(name="구매용 - 현재 채널을 개인 구매 가능 낚시터로 개방", value="set_purchasable")
    ])
    async def admin_control(self, interaction: discord.Interaction, 작업: str, 값: Optional[str] = None):
        await interaction.response.defer(ephemeral=True)
        db = self._get_db(interaction)
        guild_id = str(interaction.guild_id)
        channel_id = str(interaction.channel_id)

        # 관리용 어드민 세팅 테이블 생성
        db.create_table(
            "fishing_admin_settings", 
            "guild_id TEXT NOT NULL PRIMARY KEY, fish_tax_rate REAL DEFAULT 0.1, estate_tax_rate REAL DEFAULT 0.1"
        )
        
        # 📊 1. 세금 설정
        if 작업 == "tax":
            if not 값 or not 값.replace('.', '', 1).isdigit():
                return await interaction.followup.send("❌ 올바른 수수료 비율(0 ~ 100)을 입력하세요.")
            
            rate_percent = float(값)
            if not 0 <= rate_percent <= 100:
                return await interaction.followup.send("❌ 수수료는 0%에서 100% 사이여야 합니다.")

            rate = rate_percent / 100.0
            db.execute_query("INSERT INTO fishing_admin_settings (guild_id, fish_tax_rate) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET fish_tax_rate = excluded.fish_tax_rate", (guild_id, rate))
            return await interaction.followup.send(f"✅ 물고기 판매 수수료가 **{rate_percent:.1f}%**로 설정되었습니다.")

        # ⭐ 2. 명성기능
        elif 작업 == "reputation_ctrl":
            if not 값 or ',' not in 값:
                return await interaction.followup.send("❌ 포맷을 맞춰주세요.\n- 유저 명성 수정 시: `유저ID,수치` (예: `12345678,5000`)\n- 현재 채널 낚시터 명성 수정 시: `channel,수치` (예: `channel,5000`)")
            
            try:
                target, rep_value = 값.split(',')
                rep_value = int(rep_value)
            except ValueError:
                return await interaction.followup.send("❌ 올바른 숫자 형태의 명성을 입력하세요.")

            # [A] 현재 채널의 낚시터 명성을 수정하는 경우
            if target.lower() == "channel":
                db.execute_query("UPDATE fishing_ground SET ground_reputation = ? WHERE channel_id = ? AND guild_id = ?", (rep_value, channel_id, guild_id))
                return await interaction.followup.send(f"✅ 현재 채널(<#{channel_id}>)의 **낚시터 명성**이 **{rep_value:,}** 점으로 수정되었습니다.")
            
            # [B] 유저 개인의 명성을 수정하는 경우
            else:
                db.execute_query("UPDATE users SET fishing_reputation = ? WHERE user_id = ? AND guild_id = ?", (rep_value, target, guild_id))
                return await interaction.followup.send(f"✅ <@{target}> 유저의 **개인 명성**이 **{rep_value:,}** 점으로 수정되었습니다.")

        # 🚫 3. 공용지정 (참/거짓 확인)
        elif 작업 == "set_public":
            # 입력값 Boolean 판별
            is_true = 값.lower() in ['true', '1', '예', 'on', 't'] if 값 else True

            # 📌 이 부분을 try-except로 감싸서 에러를 무시합니다.
            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN purchasable INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN is_public INTEGER DEFAULT 0")
            except Exception:
                pass

            if is_true:
                # 공용 낚시터 지정 (구매불가 ON, 공용 ON, 주인 초기화)
                db.execute_query(
                    "UPDATE fishing_ground SET purchasable = 0, is_public = 1, owner_id = NULL WHERE channel_id = ? AND guild_id = ?", 
                    (channel_id, guild_id)
                )
                return await interaction.followup.send(f"✅ <#{channel_id}> 채널이 **[공용 낚시터]**로 지정되었습니다! 유저 구매가 차단됩니다.")
            else:
                # 공용 낚시터 해제 (공용 OFF)
                db.execute_query(
                    "UPDATE fishing_ground SET is_public = 0 WHERE channel_id = ? AND guild_id = ?", 
                    (channel_id, guild_id)
                )
                return await interaction.followup.send(f"✅ <#{channel_id}> 채널이 공용 낚시터에서 **해제**되었습니다.")

        # 🛒 4. 구매용 (참/거짓 확인)
        elif 작업 == "set_purchasable":
            # 입력값 Boolean 판별
            is_true = 값.lower() in ['true', '1', '예', 'on', 't'] if 값 else True

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN purchasable INTEGER DEFAULT 0")
            except Exception:
                pass

            try:
                db.execute_query("ALTER TABLE fishing_ground ADD COLUMN is_public INTEGER DEFAULT 0")
            except Exception:
                pass

            if is_true:
                # 구매 가능 지정 (구매가능 ON, 공용 OFF)
                db.execute_query(
                    "UPDATE fishing_ground SET purchasable = 1, is_public = 0 WHERE channel_id = ? AND guild_id = ?", 
                    (channel_id, guild_id)
                )
                return await interaction.followup.send(f"✅ <#{channel_id}> 채널이 **[개인 구매 가능 낚시터]**로 활성화되었습니다!")
            else:
                # 구매 가능 해제 (구매가능 OFF)
                db.execute_query(
                    "UPDATE fishing_ground SET purchasable = 0 WHERE channel_id = ? AND guild_id = ?", 
                    (channel_id, guild_id)
                )
                return await interaction.followup.send(f"✅ <#{channel_id}> 채널이 구매 가능 낚시터에서 **해제**되었습니다.")

async def setup(bot):
    await bot.add_cog(FishingSystemCog(bot))