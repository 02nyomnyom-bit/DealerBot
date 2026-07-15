# pet_manager.py
from __future__ import annotations
import random
import time
import json
import sqlite3
import discord
import os  # 로컬 파일 조회를 위한 모듈
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import Button, View
from typing import Optional, Dict, List
import asyncio
from collections import deque
from database_manager import DatabaseManager
from pet_skill import DiscordUIFormatter
from pet_climate import ClimateManager
from pet_skill import PvPBattle, DiscordUIFormatter

class Pet:
    def __init__(self, name: str, main_type: str = "노말"):
        self.name = name
        self.stage = "알"  # 알 -> 새끼 -> 유년기 -> 성체 -> 최종 진화
        self.level = 1
        self.main_type = main_type
        self.sub_type = None
        
        # 알 단계 컨디션 및 성장 요소
        self._max_mp = 50
        self.warmth = 50
        self.cleanliness_egg = 50
        self.stability = 50
        self.hatch_progress = 0.0
        self.created_time = time.time()  # 이 시점 기준으로 3일 뒤 방생 가능
        
        # 숨겨진 스탯
        self.rarity = "일반"
        self.iv = random.randint(0, 31)
        self.personality = None
        self.hidden_trait = None  # 숨겨진 특성
        self.name_changed = False
        
        # 기획서 기준 실시간 변동 상태 요소 (0~100)
        self.fullness = 100
        self.mood_score = 100
        self.cleanliness = 100
        self.energy = 100
        self.stress = 0
        self.affinity = 0  # 친밀도 (0~300)
        self.exp = 0
        self.potential = 0  # 잠재력 (0~100)
        
        # 세부 능력치 스탯 (유년기부터 본격 증가)
        self.hp = 10
        self.attack = 5
        self.defense = 5
        self.speed = 5
        self.luck = 5
        
        # 최종 진화 스탯 확장용
        self.crit = 0
        self.res = 0
        
        # 패널티 스탯
        self.is_sick = False
        self.fine_charged = False
        self.zero_fullness_time = None  # 포만감 0이 된 시간 기록
        self.zero_cleanliness_time = None  # 청결 0이 된 시간 기록
        
        # 카운터 및 일일 제한 (자정 초기화용)
        self.train_count = 0
        self.explore_count = 0
        self.train_count_today = 0
        self.explore_count_today = 0
        self.snack_count_today = 0  
        self.pvp_count = 0
        self.last_update_time = time.time()
        
        self.skills = []
        self.equipment = {"머리": None, "견갑": None, "허리": None, "다리": None}
        self.inventory = {"열매": {"상": 0, "중": 0, "하": 0}, "장비": []}

    @property
    def max_mp(self):
        return self._max_mp

    @max_mp.setter
    def max_mp(self, value):
        self._max_mp = value

    @property
    def mood_state(self):
        """기획서 기준 기분 5단계 정의"""
        if self.mood_score >= 80: return "행복"
        elif self.mood_score >= 60: return "평범"
        elif self.mood_score >= 40: return "심심"
        elif self.mood_score >= 20: return "우울"
        else: return "화남"

    @property
    def affinity_rank(self):
        """기획서 기준 친밀도 6구간 정의"""
        if self.affinity <= 50: return "노말"
        elif self.affinity <= 100: return "야성"
        elif self.affinity <= 150: return "균형"
        elif self.affinity <= 200: return "신뢰"
        elif self.affinity <= 250: return "수호"
        else: return "희귀"

    @property
    def max_mp(self):
        """기획서 예시 기반 MP 연산 로직"""
        return int(50 + self.energy * (0.5 + (self.mood_score / 125.0)))

    def check_ultimate_skill(self):
        """친밀도 [수호/희귀] 및 [성체] 이상 도달 시 궁극기 자동 해금"""
        if self.stage not in ["성체", "최종 진화"]:
            return None
        if self.affinity_rank not in ["수호", "희귀"]:
            return None
            
        import pet_skill
        ult_list = pet_skill.SKILL_DATABASE.get(self.main_type, {}).get("궁극기", [])
        if not ult_list:
            return None
            
        ult_skill = ult_list[0]["name"]
        if ult_skill not in self.skills:
            self.skills.append(ult_skill)
            return ult_skill
        return None

    def update_passive_decay(self):
        """시간 경과에 따른 3일 기준 차감 엔진 및 자정 단위 횟수 초기화"""
        current_time = time.time()
        
        # 1. 날짜 비교 변수 정의 (이 부분이 정의되지 않아서 에러가 발생합니다)
        last_date = time.strftime('%Y-%m-%d', time.localtime(self.last_update_time + 32400))
        current_date = time.strftime('%Y-%m-%d', time.localtime(current_time + 32400))

        # 2. 자정 리셋 로직
        if last_date != current_date:
            self.train_count_today = 0
            self.explore_count_today = 0
            self.snack_count_today = 0

        hours_passed = (current_time - self.last_update_time) / 3600.0
        if hours_passed <= 0: return
        
        # 스트레스 60% 이상부터 기분 감소 가속화
        decay_modifier = 2.0 if self.stress >= 60 else 1.0
        
        # 3. 상태 감소 연산 (기존 로직 유지)
        decay_modifier = 2.0 if self.stress >= 60 else 1.0
        self.fullness = max(0, self.fullness - (hours_passed * 1.5))
        self.mood_score = max(0, self.mood_score - (hours_passed * 1.0 * decay_modifier))
        self.cleanliness = max(0, self.cleanliness - (hours_passed * 0.8))

        # 4. 상태 0 처리 (기존 로직 유지)
        if self.fullness <= 0 and self.zero_fullness_time is None:
            self.zero_fullness_time = current_time
        elif self.fullness > 0:
            self.zero_fullness_time = None

        if self.cleanliness <= 0 and self.zero_cleanliness_time is None:
            self.zero_cleanliness_time = current_time
            self.is_sick = True
        elif self.cleanliness > 0:
            self.zero_cleanliness_time = None
            self.is_sick = False
            self.fine_charged = False

        self.last_update_time = current_time

    def get_available_actions(self):
        """기획서 행동 해금 시스템 테이블 매핑"""
        actions = {
            "알": ["햇빛받기", "보듬어주기", "씻겨주기", "품어주기"],
            "새끼": ["먹이 주기", "간식 주기", "쓰다듬기", "청소하기", "놀아주기", "벌레잡기", "산책"],
            "유년기": ["먹이", "간식 주기", "훈련", "탐험", "채집", "장난감", "휴식", "산책"],
            "성체": ["먹이", "간식 주기", "훈련", "탐험", "채집", "PvP", "휴식", "산책"],
            "최종 진화": ["먹이", "간식 주기", "훈련", "랭크전", "탐험", "교배", "휴식", "산책"]
        }
        available = actions.get(self.stage, []).copy()
        if self.stage != "알" and not getattr(self, "name_changed", False):
            available.insert(0, "이름 변경")
        return available

    def interact_egg(self, action_name):
        """알 단계 전용 행동 핸들러"""
        climate = ClimateManager().get_current_climate()
        
        if action_name == "햇빛받기":
            self.warmth = min(100, self.warmth + 15)
        elif action_name == "보듬어주기":
            self.stability = min(100, self.stability + 15)
        elif action_name == "씻겨주기":
            self.cleanliness_egg = min(100, self.cleanliness_egg + 15)
        elif action_name == "품어주기":
            self.warmth = min(100, self.warmth + 10)
            self.stability = min(100, self.stability + 10)
            
        base_progress = random.uniform(8.0, 15.0)
        # 맑음: 부화 진행도 +10%, 봄: 부화 진행도 +10%
        if climate.weather == "맑음":
            base_progress *= 1.10
        if climate.season == "봄":
            base_progress *= 1.10
            
        self.hatch_progress = min(100.0, self.hatch_progress + base_progress)
        
        # 최소 3일 제약 검증 및 진행도 100% 충족 시 자동 부화
        if self.hatch_progress >= 100.0:
            elapsed_time = time.time() - self.created_time
            if elapsed_time >= 3 * 86400:
                return self.hatch_trigger()
            else:
                remaining_seconds = (3 * 86400) - elapsed_time
                hours = int(remaining_seconds // 3600)
                minutes = int((remaining_seconds % 3600) // 60)
                return f"🥚 진행도가 100%에 도달했으나, 아직 알이 단단합니다. 부화까지 약 **{hours}시간 {minutes}분** 더 품어주어야 합니다!"
                
        return f"🥚 [{action_name}] 완료! 부화 진행도: {self.hatch_progress:.1f}%"

    @property
    def rarity_multiplier(self):
        """등급별 스탯(ATK, DEF, SPD, HP, MP) 뻥튀기 배율"""
        mapping = {"일반": 1.0, "희귀": 1.1, "영웅": 1.25, "전설": 1.5}
        return mapping.get(self.rarity, 1.0)

    def hatch_trigger(self):
        """알 부화 및 관리 점수 기반 희귀도 가챠 트리거"""
        self.stage = "새끼"
        
        # 알 관리 점수 평균 계산
        avg_score = (self.warmth + self.cleanliness_egg + self.stability) / 3.0
        
        roll = random.random()
        if avg_score >= 80:
            # 훌륭한 관리: 전설 5%, 영웅 15%, 희귀 40%, 일반 40%
            if roll < 0.05:
                self.rarity = "전설"
            elif roll < 0.20:
                self.rarity = "영웅"
            elif roll < 0.60:
                self.rarity = "희귀"
            else:
                self.rarity = "일반"
            
            # 덤으로 개체값 상승 보너스
            self.iv = min(31, self.iv + 5)
        else:
            # 관리 미흡: 일반 90%, 희귀 10%
            if roll < 0.10:
                self.rarity = "희귀"
            else:
                self.rarity = "일반"
                
        return f"🎉 알이 새끼 단계로 부화했습니다! (부여된 희귀도: **[{self.rarity}]**)"

    def gain_exp(self, amount: int) -> str:
        """기분 상태 가중치를 계산하여 경험치를 획득하고 레벨업/진화 조건을 판정합니다"""
        if self.energy <= 0:
            return "❌ 에너지가 전부 소진되어 더 이상 경험치를 지급받지 못합니다! [재우기]나 [휴식]을 통해 회복시키세요."
            
        # 기분 버프/너프 반영
        if self.mood_state == "행복":
            amount = int(amount * 1.1)
        elif self.mood_state == "우울":
            amount = int(amount * 0.9)
        elif self.mood_state == "화남":
            amount = int(amount * 0.8)

        # 친밀도 균형(101~150) 경험치 5% 버프 반영
        if 101 <= self.affinity <= 150:
            amount = int(amount * 1.05)

        self.exp += amount
        energy_cost = int(amount * 0.5)
        if getattr(self, 'personality', None) == "나태":
            energy_cost = int(energy_cost * 0.5)  # 에너지 소모 50% 감소
        self.energy = max(0, self.energy - energy_cost)  # 소모한 만큼 에너지 감소
        
        # 기획서 기준 레벨 경험치 공식 (EXP = 5N³ / 4) 적용
        def get_req_exp(lvl):
            return int((5 * ((lvl + 1) ** 3)) / 4) - int((5 * (lvl ** 3)) / 4)
            
        next_exp = get_req_exp(self.level)
        level_up_msg = ""
        
        while self.exp >= next_exp and self.level < 100:
            self.exp -= next_exp
            self.level += 1
            # 스탯 상승 가중치 부여
            self.hp += random.randint(3, 7)
            self.attack += random.randint(1, 3)
            self.defense += random.randint(1, 3)
            self.speed += random.randint(1, 3)
            self.luck += random.randint(1, 2)
            
            level_up_msg += f"\n🆙 **레벨 업!** Lv.{self.level}이(가) 되었습니다! 스탯이 본격 상승합니다."
            next_exp = get_req_exp(self.level)

        # 레벨업 후 성장 단계 진화 요건 자동 검증
        evo_msg = self.check_evolution_conditions()
        return f"✨ 경험치 **+{amount}** 획득! (남은 에너지: {int(self.energy)}){level_up_msg}{evo_msg}"

    def check_evolution_conditions(self) -> str:
        """기획서 조건에 만족할 시 단계를 즉시 진화시키고 성격 및 고유 패시브를 각성시킵니다"""
        climate = ClimateManager().get_current_climate()
        
        # "변하지 않는 반지" 장착 여부 검사 (진화 락)
        if "변하지 않는 반지" in getattr(self, "inventory", {}).get("장비", [{"부위": "", "등급": ""}]) or \
           any(e.get("부위") == "변하지 않는 반지" for e in getattr(self, "inventory", {}).get("장비", [])):
            return ""
        # 1. 새끼 -> 유년기 (Lv.15 달성 및 친밀도 30 이상)
        if self.stage == "새끼" and self.level >= 15 and self.affinity >= 30:
            self.stage = "유년기"
            self.personality = random.choice(["다혈질", "장난꾸러기", "나태", "신중함", "용맹함"])
            
            # 기획서 규칙: 특정 성격 스킬 강제 셋팅 (삭제 및 교체 불가능)
            if self.personality == "장난꾸러기":
                self.skills = ["놀리기"]
            elif self.personality == "나태":
                self.skills = ["잠자기"]
            else:
                self.skills = ["몸통박치기"]
            return f"\n\n🌅 **[진화 완료]** {self.name}이(가) **유년기** 단계로 진화했습니다! 성격 **[{self.personality}]**이(가) 형성되었으며 고유 패시브가 장착되었습니다."

        # 2. 유년기 -> 성체 (Lv.40 달성, 훈련 50회, 탐험 50회)
        elif self.stage == "유년기" and self.level >= 40 and self.train_count >= 50 and self.explore_count >= 50:
            self.stage = "성체"
            # 기본 원소 외 부가 원소 획득 (매우 낮은 확률로 상극 원소가 들어올 수 있음)
            available_types = ["노말", "불", "물", "풀", "전기", "비행", "땅", "어둠", "독", "에스퍼"]
            available_types.remove(self.main_type)
            self.sub_type = random.choice(available_types)
            
            # 스킬 셋 확장
            self.skills.extend(["웅크리기", "피하기"])
            return f"\n\n⚡ **[원소 각성 진화]** {self.name}이(가) **성체** 단계로 진화했습니다! 부속성 **[{self.sub_type}]**을(를) 깨우쳤으며 이제 일반 PvP전에 참여할 수 있습니다!"

        # 3. 성체 -> 최종 진화 (Lv.75 달성, PvP 30회, 친밀도 70, 잠재력 50%)
        elif self.stage == "성체" and self.level >= 75 and self.pvp_count >= 30 and self.affinity >= 70 and self.potential >= 50:
            
            # 히든 진화 조건 체크 (일반 최종 진화보다 우선 적용)
            hidden_evo = None
            if climate.weather == "비" and climate.is_night and self.affinity >= 250 and self.main_type == "물":
                hidden_evo = "심해의 수호자"
            elif climate.weather == "폭염" and self.main_type == "불":
                hidden_evo = "화염 군주"
            elif climate.weather == "안개" and self.main_type == "어둠" and self.affinity_rank == "신뢰":
                hidden_evo = "안개의 망령"
            elif climate.special_weather == "유성우" and self.main_type == "에스퍼" and self.potential >= 90:
                hidden_evo = "별의 현자"
                
            if hidden_evo:
                self.stage = "최종 진화"
                self.crit = 30 # 히든 보너스
                self.res = 20
                self.name = f"{hidden_evo} {self.name}"
                return f"\n\n✨ **[히든 진화 발동!!]** 특수한 기후와 조건이 맞아떨어져 {self.name}이(가) 숨겨진 진화형인 **『{hidden_evo}』**(으)로 각성했습니다!"
            
            self.stage = "최종 진화"
            self.crit = 15  # 최종 진화 스탯 보너스 부여
            self.res = 10
            
            return f"\n\n🔥 **[최종 진화 완료]** {self.name}이(가) 마침내 궁극의 **최종 진화**를 이루었습니다! 전용 패시브가 개방되었으며 랭크전에 참전할 자격을 얻었습니다!"

        return ""

    def feed(self):
        """포만감 및 스트레스 감소 행동"""
        self.fullness = min(100, self.fullness + 30)
        self.stress = max(0, self.stress - 10)
        return f"🍖 먹이를 주었습니다. 포만감: {int(self.fullness)}/100, 스트레스: {self.stress}/100"

    def to_dict(self) -> dict:
        return self.__dict__

    @classmethod
    def from_dict(cls, data: dict) -> Pet:
        pet = cls(data.get('name', '이름없음'), data.get('main_type', '노말'))
        pet.__dict__.update(data)
        if not hasattr(pet, 'equipment'):
            pet.equipment = {"머리": None, "견갑": None, "허리": None, "다리": None}
        if not hasattr(pet, 'inventory'):
            pet.inventory = {"열매": {"상": 0, "중": 0, "하": 0}, "장비": []}
        return pet


class PetManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_managers: Dict[str, DatabaseManager] = {}
        
        try:
            dummy_db = DatabaseManager(guild_id="pet_init_setup")
            dummy_db.create_table(
                "user_pets",
                """
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                pet_data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (user_id, guild_id)
                """
            )
            dummy_db.create_table(
                "user_pet_storage",
                """
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                pet_data TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                """
            )
        except Exception as e:
            print(f"⚠️ 테이블 설정 에러: {e}")

    def _get_db(self, guild_id: int) -> DatabaseManager:
        gid_str = str(guild_id)
        if gid_str not in self.db_managers:
            db = DatabaseManager(guild_id=gid_str)
            
            # 🛡️ 새로운 길드 DB가 로드될 때, 테이블이 없다면 즉시 생성해 줍니다.
            try:
                db.create_table(
                    "user_pets",
                    """
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    pet_data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (user_id, guild_id)
                    """
                )
                db.create_table(
                    "user_pet_storage",
                    """
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    guild_id TEXT NOT NULL,
                    pet_data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    """
                )
            except Exception as e:
                print(f"⚠️ [{gid_str}] 테이블 동적 초기화 에러: {e}")
                
            self.db_managers[gid_str] = db
            
        return self.db_managers[gid_str]

    def get_user_pet(self, guild_id: str, user_id: str) -> Optional[Pet]:
        db = self._get_db(int(guild_id))
        res = db.execute_query("SELECT pet_data FROM user_pets WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'one')
        if res and res['pet_data']:
            return Pet.from_dict(json.loads(res['pet_data']))
        return None

    def save_user_pet(self, guild_id: str, user_id: str, pet: Pet):
        db = self._get_db(int(guild_id))
        pet_json = json.dumps(pet.to_dict(), ensure_ascii=False)
        db.execute_query(
            """
            INSERT INTO user_pets (user_id, guild_id, pet_data, updated_at) 
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(user_id, guild_id) DO UPDATE SET pet_data = ?, updated_at = CURRENT_TIMESTAMP
            """,
            (user_id, guild_id, pet_json, pet_json), 'none'
        )

    def delete_user_pet(self, guild_id: str, user_id: str):
        """방치형 페널티로 야생으로 날아갈 시 DB 레코드 완전히 말소"""
        db = self._get_db(int(guild_id))
        db.execute_query("DELETE FROM user_pets WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'none')

    # --- 보관함 (Storage) DB 관리 로직 ---
    def get_stored_pets(self, guild_id: str, user_id: str) -> List[tuple]:
        """(id, Pet객체) 형태의 리스트 반환"""
        db = self._get_db(int(guild_id))
        rows = db.execute_query("SELECT id, pet_data FROM user_pet_storage WHERE user_id = ? AND guild_id = ? ORDER BY id ASC", (user_id, guild_id), 'all')
        if not rows:
            return []
        pets = []
        for row in rows:
            try:
                pet_obj = Pet.from_dict(json.loads(row['pet_data']))
                pets.append((row['id'], pet_obj))
            except Exception:
                pass
        return pets

    def add_stored_pet(self, guild_id: str, user_id: str, pet: Pet):
        db = self._get_db(int(guild_id))
        pet_json = json.dumps(pet.to_dict(), ensure_ascii=False)
        db.execute_query(
            "INSERT INTO user_pet_storage (user_id, guild_id, pet_data) VALUES (?, ?, ?)",
            (user_id, guild_id, pet_json), 'none'
        )

    def delete_stored_pet(self, guild_id: str, id_to_delete: int):
        db = self._get_db(int(guild_id))
        db.execute_query("DELETE FROM user_pet_storage WHERE id = ? AND guild_id = ?", (id_to_delete, guild_id), 'none')
        
    def get_stored_pet_by_id(self, guild_id: str, id_to_get: int) -> Optional[Pet]:
        db = self._get_db(int(guild_id))
        res = db.execute_query("SELECT pet_data FROM user_pet_storage WHERE id = ? AND guild_id = ?", (id_to_get, guild_id), 'one')
        if res and res['pet_data']:
            return Pet.from_dict(json.loads(res['pet_data']))
        return None

    def get_total_pet_count(self, guild_id: str, user_id: str) -> int:
        """현재 메인 펫과 보관함 펫 수를 총합하여 현재 기르는 펫의 총 개수를 반환합니다 (Max 3)"""
        count = 0
        if self.get_user_pet(guild_id, user_id) is not None:
            count += 1
        stored = self.get_stored_pets(guild_id, user_id)
        count += len(stored)
        return count

    def check_penalties_and_update(self, guild_id: str, user_id: str, pet: Pet) -> Optional[str]:
        """행동 명령 전 펫 상태가 24시간 이상 방치 상태인지 실시간 검증합니다"""
        pet.update_passive_decay()
        current_time = time.time()
        
        # 1. 포만감 0 상태로 24시간(86400초) 이상 방치 시 야생으로 도망
        if pet.zero_fullness_time and (current_time - pet.zero_fullness_time) >= 86400:
            self.delete_user_pet(guild_id, user_id)
            return "RUNAWAY"
            
        # 2. 청결도 0 상태로 24시간 이상 방치 시 동물 학대 벌금 부과
        if pet.zero_cleanliness_time and (current_time - pet.zero_cleanliness_time) >= 86400:
            if getattr(pet, 'fine_charged', False) is False:
                pet.fine_charged = True
                # 학대 벌금 3,000골드 강제 차감
                db = self._get_db(int(guild_id))
                db.add_user_cash(user_id, -3000)
                return "SICK_TRIGGERED"

        return None

    @app_commands.command(name="키우기", description="첫 펫을 입양하고 알을 지급받습니다. (최대 3마리 제한)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def start_game(self, interaction: discord.Interaction, 펫이름: str, 타입: str = "노말"):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        db = self._get_db(interaction.guild.id)
        db.get_or_create_user(user_id, interaction.user.name)
        
        # 총 보유 마릿수 제약 검사 (Max 3)
        total_pets = self.get_total_pet_count(guild_id, user_id)
        if total_pets >= 3:
            await interaction.response.send_message("❌ 이 세계에서 최대로 보호할 수 있는 생명은 **최대 3마리**까지입니다. 더 입양하려면 펫을 방생해 주세요.", ephemeral=True)
            return
            
        active_pet = self.get_user_pet(guild_id, user_id)
        
        # 🌟 [개선] 메인 동행 자리가 비어있다면, 보관함을 거치지 않고 즉시 활성화 슬롯에 안착시킵니다.
        if active_pet is None:
            new_pet = Pet(펫이름, 타입)
            self.save_user_pet(guild_id, user_id, new_pet)
            await interaction.response.send_message(f"🎉 첫 번째 동행 파트너 지정 완료! ??? 알 **[{펫이름}]**이 메인 파트너로 즉시 활성화되었습니다! (현재 보유: {total_pets + 1}/3)")
        else:
            # 메인 자리가 이미 차 있을 때만 보관함(Storage)으로 자동 안전 수령
            new_pet = Pet(펫이름, 타입)
            self.add_stored_pet(guild_id, user_id, new_pet)
            await interaction.response.send_message(f"📦 현재 메인 파트너 자리가 차 있습니다! 새로운 알 **[{펫이름}]**은(는) **🗃️ 펫 보관함**으로 안전하게 수령되었습니다! (현재 보유: {total_pets + 1}/3)")

    @app_commands.command(name="펫보관함", description="보관 중인 펫을 확인하고 메인 펫과 교체(스왑)합니다. (최대 3마리 보존)")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def open_storage(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        stored = self.get_stored_pets(guild_id, user_id)
        active_pet = self.get_user_pet(guild_id, user_id)
        
        embed = discord.Embed(title="🗃️ 펫 보관함 (PC)", description="동행하지 않고 보관 중인 펫 목록입니다.", color=0x3498db)
        if active_pet:
            embed.add_field(name="🟢 현재 동행 중인 펫", value=f"[{active_pet.rarity}] {active_pet.name} (Lv.{active_pet.level} {active_pet.main_type})", inline=False)
        else:
            embed.add_field(name="🟢 현재 동행 중인 펫", value="없음", inline=False)
            
        if not stored:
            embed.add_field(name="📦 보관함", value="보관 중인 펫이나 알이 없습니다.", inline=False)
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
            
        for idx, (db_id, p) in enumerate(stored):
            stage_icon = "🥚" if p.stage == "알" else "🐾"
            embed.add_field(name=f"{idx+1}. {stage_icon} {p.name}", value=f"[{p.rarity}] Lv.{p.level} {p.main_type} (고유번호: {db_id})", inline=False)
            
        view = StorageSwapView(self, user_id, guild_id, stored, active_pet)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        
    @app_commands.command(name="교배", description="NPC와 교배하여 강력한 알을 얻습니다. (10만 골드 소모, 최종 진화체 필요)")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
    @app_commands.default_permissions(administrator=True)
    async def breed_pet(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        db = self._get_db(interaction.guild.id)
        
        # 총보유 3마리 락 체크
        total_pets = self.get_total_pet_count(guild_id, user_id)
        if total_pets >= 3:
            await interaction.response.send_message("❌ 더 이상 알을 품을 수 있는 둥지가 없습니다. 보유 공간(최대 3마리 제한)을 먼저 정리해 주세요.", ephemeral=True)
            return
            
        pet = self.get_user_pet(guild_id, user_id)
        if not pet:
            await interaction.response.send_message("❌ 동행 중인 펫이 없습니다.", ephemeral=True)
            return
            
        if pet.stage != "최종 진화":
            await interaction.response.send_message("❌ 교배는 **최종 진화** 단계의 펫만 가능합니다.", ephemeral=True)
            return
            
        user_data = db.get_user(user_id)
        cash = user_data.get('cash', 0) if user_data else 0
        if cash < 100000:
            await interaction.response.send_message("❌ 교배 비용(100,000원)이 부족합니다.", ephemeral=True)
            return
            
        db.add_user_cash(user_id, -100000)
        
        types = ["불", "물", "풀", "전기", "비행", "땅", "어둠", "독", "에스퍼", "노말"]
        npc_type = random.choice(types)
        npc_iv = random.randint(15, 31)
        
        base_iv = (pet.iv + npc_iv) // 2
        new_iv = min(31, max(0, base_iv + random.randint(-3, 5)))
        new_type = random.choice([pet.main_type, npc_type])
        
        new_personality = pet.personality if (pet.personality and random.random() < 0.3) else random.choice(["용맹함", "신중함", "다혈질", "나태", "변덕", None])
        
        child = Pet(f"{pet.name}의 알", new_type)
        child.iv = new_iv
        child.personality = new_personality
        
        self.add_stored_pet(guild_id, user_id, child)
        
        embed = discord.Embed(title="💞 교배 성공!", description="교배소에서 10만 골드를 지불하고 훌륭한 종마와 교배를 마쳤습니다.", color=0xff9ff3)
        embed.add_field(name="🥚 새로운 생명", value=f"새로운 **[{new_type}]** 속성의 알이 태어났습니다!\n(개체값 보정: {base_iv} ➡️ {new_iv})\n알은 즉시 **🗃️ 펫 보관함**으로 이동되었습니다. (보유 공간: {total_pets + 1}/3)", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="방생", description="현재 키우는 펫 중 하나를 자연으로 방생합니다. (이름 일치 필수, 3일 경과 제약)")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(펫이름="방생하여 영구 작별할 펫의 이름")
    async def release_pet_cmd(self, interaction: discord.Interaction, 펫이름: str):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        
        # 1. 메인 펫 및 보관함 펫 목록 중 이름 매칭 수색
        active_pet = self.get_user_pet(guild_id, user_id)
        stored_pets = self.get_stored_pets(guild_id, user_id) # list of (db_id, Pet)
        
        target_pet: Optional[Pet] = None
        is_active = False
        db_id_to_delete = None
        
        if active_pet and active_pet.name == 펫이름:
            target_pet = active_pet
            is_active = True
        else:
            for db_id, p in stored_pets:
                if p.name == 펫이름:
                    target_pet = p
                    db_id_to_delete = db_id
                    break
                    
        if not target_pet:
            await interaction.response.send_message(f"❌ 보호 중인 펫 중 이름이 **[{펫이름}]**인 아이를 찾을 수 없습니다. 다시 확인해 주세요.", ephemeral=True)
            return

        # 2. 입양 3일(72시간 / 259,200초) 제약 검사
        elapsed_time = time.time() - target_pet.created_time
        required_time = 3 * 86400
        
        if elapsed_time < required_time:
            remaining = required_time - elapsed_time
            days = int(remaining // 86400)
            hours = int((remaining % 86400) // 3600)
            minutes = int((remaining % 3600) // 60)
            
            time_msg = f"**{days}일 {hours}시간 {minutes}분**" if days > 0 else f"**{hours}시간 {minutes}분**"
            await interaction.response.send_message(
                f"❌ 아직 보호자와 함께한 시간이 짧습니다! 펫은 충분한 신뢰를 형성한 뒤에야 방생할 수 있습니다.\n"
                f"⏱️ **방생 조건 충족까지 남은 시간:** {time_msg} (최소 3일 동행 필수)", 
                ephemeral=True
            )
            return

        # 3. 방생용 무작위 편지 선택 (5종)
        letters = [
            f"💌 **{target_pet.name}이(가) 보낸 편지**\n\"주인과 함께 생활한 것은 정말 즐거웠어! 잊지 못할 추억을 만들어 줘서 고마워. 새주인을 만나면 거기서도 잘지낼게!\"",
            f"💌 **{target_pet.name}이(가) 보낸 편지**\n\"그동안 정말 고마웠어. 주인 곁에서 떠나더라도 친구인 건 변함없지? 가끔은 생각해 줘!\"",
            f"💌 **{target_pet.name}이(가) 보낸 편지**\n\"그래, 주인이 그렇게 생각했다면 마음 편히 떠나야겠지. 그동안 정말 고마웠어!\"",
            f"💌 **{target_pet.name}이(가) 보낸 편지**\n\"주인과 보낸 시간들은 온통 맑은 날 같았어. 나 없는 곳에서도 밥 제때 챙겨 먹고 아프지 마! 정말 고마웠어!\"",
            f"💌 **{target_pet.name}이(가) 보낸 편지**\n\"서운했던 마음도 다 잊혀질 만큼 행복했어. 주인과의 따뜻했던 온기를 가슴속에 품고 씩씩하게 살아갈게. 안녕!\""
        ]
        chosen_letter = random.choice(letters)

        # 4. 소멸 처리
        if is_active:
            self.delete_user_pet(guild_id, user_id)
        else:
            self.delete_stored_pet(guild_id, db_id_to_delete)

        embed = discord.Embed(
            title="🍃 숲속으로 떠나는 안녕",
            description=f"**[{target_pet.name}]**이(가) 주인과의 추억을 정리하며 편지를 남기고 스스로 떠납니다.",
            color=0x2ecc71
        )
        embed.add_field(name="✉️ 남겨진 편지 한 통", value=chosen_letter, inline=False)
        embed.set_footer(text="펫은 자연의 품에서 무사히 뛰어놀며, 새로운 시작을 응원합니다.")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="날씨", description="신비섬의 현재 실시간 기후 및 날씨를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
    @app_commands.default_permissions(administrator=True)
    async def view_weather(self, interaction: discord.Interaction):
        climate = ClimateManager().get_current_climate()
        
        weather_icons = {
            "맑음": "☀️", "흐림": "☁️", "비": "🌧️", "강풍": "💨",
            "폭염": "🔥", "한파": "❄️", "눈": "🌨️", "안개": "🌫️"
        }
        icon = weather_icons.get(climate.weather, "🌈")
        
        embed = discord.Embed(title=f"신비섬 기후 현황 ({climate.season})", description="실시간 날씨에 기반한 게임 내 기상 정보입니다.", color=0x3498db)
        
        time_str = "🌌 밤 (특수 야간 진화 및 이벤트 활성화)" if climate.is_night else "☀️ 낮"
        embed.add_field(name="기본 날씨", value=f"{icon} **{climate.weather}** ({climate.temperature}℃, 풍속 {climate.wind_speed}km/h)", inline=False)
        embed.add_field(name="시간대", value=time_str, inline=False)
        
        if climate.special_weather:
            embed.add_field(name="✨ 특수 기상 발생 중!", value=f"현재 **[{climate.special_weather}]** 현상이 관측되고 있습니다! 숨겨진 이벤트를 찾아보세요.", inline=False)
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="보호자", description="보호자 정보창 및 대시보드 허브 뷰를 출력합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
    @app_commands.default_permissions(administrator=True)
    async def open_guardian_hub(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild.id)
        db = self._get_db(interaction.guild.id)
        user_data = db.get_user(user_id)
        
        if not user_data:
            db.get_or_create_user(user_id, interaction.user.name)
            user_data = db.get_user(user_id)
            
        pet = self.get_user_pet(guild_id, user_id)
        
        # 패널티 검증 수행
        if pet:
            penalty = self.check_penalties_and_update(guild_id, user_id, pet)
            if penalty == "RUNAWAY":
                await interaction.response.send_message("🚨 **경고:** 펫을 너무 오랫동안 굶주린 상태로 방치하여 펫이 야생으로 도망갔습니다... (데이터가 완전히 말소되었습니다)", ephemeral=True)
                return
            elif penalty == "SICK_TRIGGERED":
                await interaction.followup.send("🚨 **경고:** 청결도를 너무 오랜 시간 방치하여 펫이 병에 걸렸습니다! 동물 보호 위반 벌금으로 **3,000원**이 자산에서 강제 차감됩니다.", ephemeral=True)
            self.save_user_pet(guild_id, user_id, pet)

        data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
        embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
        for f in data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            
        # 보유 수량 표시 덧붙임
        total_p = self.get_total_pet_count(guild_id, user_id)
        embed.set_footer(text=f"🔑 총 보유 펫 공간: {total_p} / 3마리")
            
        await interaction.response.send_message(embed=embed, view=MainPetHubView(self, user_id, guild_id))

    @app_commands.command(name="펫관리", description="[관리자 전용] 특정 유저의 펫 능력치 및 성장 단계를 강제 조정합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        대상자="펫 정보를 수정할 유저",
        변경항목="수정할 수치 또는 상태를 선택하세요",
        설정값="변경 대입할 수치를 입력하세요 (단계는 알, 새끼, 유년기, 성체, 최종 진화 중 입력)"
    )
    @app_commands.choices(변경항목=[
        app_commands.Choice(name="📈 레벨 설정 (1 ~ 100)", value="level"),
        app_commands.Choice(name="🧬 성장단계 강제 설정", value="stage"),
        app_commands.Choice(name="❤️ 친밀도 수치 조정 (0 ~ 300)", value="affinity"),
        app_commands.Choice(name="🧼 질병 상태 강제 완치", value="heal_sick"),
        app_commands.Choice(name="⚡ 에너지 완충 (100)", value="heal_energy")
    ])
    async def admin_set_pet_status(self, interaction: discord.Interaction, 대상자: discord.Member, 변경항목: str, 설정값: str):
        user_id = str(대상자.id)
        guild_id = str(interaction.guild.id)
        
        pet = self.get_user_pet(guild_id, user_id)
        if not pet:
            return await interaction.response.send_message(f"❌ {대상자.display_name}님은 현재 동행 중인 펫이 없습니다.", ephemeral=True)

        msg = ""
        if 변경항목 == "level":
            try:
                val = max(1, min(100, int(설정값)))
                pet.level = val
                msg = f"📈 {대상자.display_name}님의 펫 **[{pet.name}]**의 레벨을 강제로 **Lv.{val}**(으)로 조정했습니다."
            except ValueError:
                return await interaction.response.send_message("❌ 설정값에 올바른 정수 숫자(1~100)를 입력해 주세요.", ephemeral=True)

        elif 변경항목 == "stage":
            if 설정값 in ["알", "새끼", "유년기", "성체", "최종 진화"]:
                pet.stage = 설정값
                msg = f"🧬 {대상자.display_name}님의 펫 **[{pet.name}]**의 성장 단계를 **[{설정값}]**(으)로 강제 조정했습니다."
            else:
                return await interaction.response.send_message("❌ 올바른 성장 단계를 입력하세요: `알`, `새끼`, `유년기`, `성체`, `최종 진화`", ephemeral=True)

        elif 변경항목 == "affinity":
            try:
                val = max(0, min(300, int(설정값)))
                pet.affinity = val
                msg = f"❤️ {대상자.display_name}님의 펫 **[{pet.name}]**의 친밀도를 강제로 **{val} / 300**(으)로 조정했습니다."
            except ValueError:
                return await interaction.response.send_message("❌ 설정값에 올바른 정수 숫자(0~300)를 입력해 주세요.", ephemeral=True)

        elif 변경항목 == "heal_sick":
            pet.is_sick = False
            pet.cleanliness = 100
            pet.zero_cleanliness_time = None
            pet.fine_charged = False
            msg = f"🧼 {대상자.display_name}님의 펫 **[{pet.name}]**의 질병을 완치하고 주변 청결도를 최상(100)으로 조치했습니다."

        elif 변경항목 == "heal_energy":
            pet.energy = 100
            pet.stress = 0
            msg = f"⚡ {대상자.display_name}님의 펫 **[{pet.name}]**의 에너지를 100으로 완충하고 누적 스트레스를 0으로 관리했습니다."

        self.save_user_pet(guild_id, user_id, pet)
        
        embed = discord.Embed(title="⚙️ [어드민] 펫 상태 수동 개입", description=msg, color=discord.Color.purple())
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="제한초기화", description="[관리자 전용] 특정 유저 혹은 서버 전체 유저의 일일 상호작용 제한 횟수를 리셋합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        대상구분="특정 유저만 초기화할지, 서버 내 모든 유저를 초기화할지 선택하세요",
        대상자="특정 유저를 선택한 경우에만 지정해주세요"
    )
    @app_commands.choices(대상구분=[
        app_commands.Choice(name="👤 특정 유저만 초기화", value="target"),
        app_commands.Choice(name="🌐 서버 전체 유저 일괄 초기화", value="all")
    ])
    async def admin_reset_limits(self, interaction: discord.Interaction, 대상구분: str, 대상자: Optional[discord.Member] = None):
        guild_id = str(interaction.guild.id)
        db = self._get_db(interaction.guild.id)

        if 대상구분 == "target":
            if not 대상자:
                return await interaction.response.send_message("❌ 특정 유저 초기화를 선택하셨다면 `대상자`를 지정하셔야 합니다.", ephemeral=True)
                
            user_id = str(대상자.id)
            pet = self.get_user_pet(guild_id, user_id)
            if not pet:
                return await interaction.response.send_message(f"❌ {대상자.display_name}님은 현재 동행 중인 펫이 없습니다.", ephemeral=True)

            # 카운터 수동 영점 조절
            pet.train_count_today = 0
            pet.explore_count_today = 0
            pet.snack_count_today = 0
            self.save_user_pet(guild_id, user_id, pet)

            embed = discord.Embed(
                title="⚙️ [어드민] 일일 제한 개별 초기화 완료",
                description=f"👤 {대상자.mention}님의 펫 **[{pet.name}]**의 오늘자 훈련/탐험/간식 한도가 모두 해제되었습니다! (오늘자 이용률: 0/3)",
                color=discord.Color.blue()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

        elif 대상구분 == "all":
            await interaction.response.defer(ephemeral=True)
            
            # 서버 DB 내에 활성화되어 보존 중인 모든 유저 목록 가져오기
            rows = db.execute_query("SELECT user_id, pet_data FROM user_pets WHERE guild_id = ?", (guild_id,), 'all')
            if not rows:
                return await interaction.followup.send("❌ 이 서버에 펫을 키우는 보호자 데이터가 없습니다.")

            success_count = 0
            for row in rows:
                try:
                    p_data = json.loads(row['pet_data'])
                    p_obj = Pet.from_dict(p_data)
                    
                    p_obj.train_count_today = 0
                    p_obj.explore_count_today = 0
                    p_obj.snack_count_today = 0
                    
                    self.save_user_pet(guild_id, row['user_id'], p_obj)
                    success_count += 1
                except Exception:
                    continue

            embed = discord.Embed(
                title="⚙️ [어드민] 일일 제한 전체 초기화 완료",
                description=f"🌐 현재 서버에서 활동 중인 **{success_count}명**의 펫 일일 이용 제한을 자정 리셋 전 강제로 초기화 조치했습니다!",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)
        
    @app_commands.command(name="펫설정", description="[관리자 전용] 펫 상점 판매가 및 탐험 시 아이템 획득 확률을 밸런싱합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        최상급열매가="최상급 열매의 상점 가격을 설정합니다.",
        반지드롭확률="탐험 중 보물상자 조우 시, 전설 반지가 뜰 확률(%)을 지정합니다. (0.1 ~ 100 사이 입력)"
    )
    async def admin_set_balancing(self, interaction: discord.Interaction, 최상급열매가: Optional[int] = None, 반지드롭확률: Optional[float] = None):
        config_path = "data/pet_config.json"
        
        # 디렉토리 체크 후 파일 로드 및 디폴트 세팅
        os.makedirs("data", exist_ok=True)
        default_config = {
            "fruit_high_price": 50000,   # 최상급 기본값
            "ring_drop_rate": 0.05       # 상자 속 전설 드롭 기본값 5%
        }

        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    loaded = json.load(f)
                    default_config.update(loaded)
            except Exception:
                pass

        # 매개변수 적용
        changes = []
        if 최상급열매가 is not None:
            if 최상급열매가 >= 0:
                default_config["fruit_high_price"] = 최상급열매가
                changes.append(f"🍎 최상급 열매 판매 가격: **{최상급열매가:,}원**")
            else:
                return await interaction.response.send_message("❌ 금액은 음수가 될 수 없습니다.", ephemeral=True)

        if 반지드롭확률 is not None:
            if 0.01 <= 반지드롭확률 <= 100.0:
                rate_val = 반지드롭확률 / 100.0
                default_config["ring_drop_rate"] = rate_val
                changes.append(f"💍 변하지 않는 반지 상자 파밍 확률: **{반지드롭확률:.2f}%**")
            else:
                return await interaction.response.send_message("❌ 확률은 0.01%에서 100.0% 사이로 지정해주셔야 합니다.", ephemeral=True)

        # 수치 최종 보존
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(default_config, f, indent=4, ensure_ascii=False)
        except Exception as e:
            return await interaction.response.send_message(f"❌ 설정 저장 실패: {e}", ephemeral=True)

        if changes:
            embed = discord.Embed(
                title="⚙️ [어드민] 펫 밸런스 설정 패치 완료",
                description="수정된 규칙이 펫 인프라에 즉시 동기화 적용되었습니다.\n\n" + "\n".join(changes),
                color=discord.Color.gold()
            )
        else:
            # 현재 적용 중인 세팅값 가이드 출력
            embed = discord.Embed(title="⚙️ 현재 펫 상점 및 파밍 밸런스 설정 상황", color=discord.Color.blue())
            embed.add_field(name="🍎 최상급 열매 소비가", value=f"{default_config['fruit_high_price']:,}원", inline=True)
            embed.add_field(name="💍 반전의 보물 반지 획득율 (상자 개봉 시)", value=f"{default_config['ring_drop_rate'] * 100.0:.2f}%", inline=True)

        await interaction.response.send_message(embed=embed)


# --- 보관함 스왑 뷰 ---
class StorageSwapView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, stored_pets, active_pet):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.stored_pets = stored_pets
        self.active_pet = active_pet
        
        for idx, (db_id, p) in enumerate(stored_pets):
            btn = discord.ui.Button(label=f"{idx+1}번 펫 스왑", style=discord.ButtonStyle.primary, custom_id=f"swap_{db_id}")
            btn.callback = self.handle_swap
            self.add_item(btn)
            
    async def handle_swap(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        db_id = int(custom_id.split("_")[1])
        
        target_pet = self.cog.get_stored_pet_by_id(self.guild_id, db_id)
        if not target_pet:
            await interaction.response.send_message("❌ 대상을 찾을 수 없습니다.", ephemeral=True)
            return
            
        if self.active_pet:
            self.cog.add_stored_pet(self.guild_id, self.user_id, self.active_pet)
            
        self.cog.save_user_pet(self.guild_id, self.user_id, target_pet)
        self.cog.delete_stored_pet(self.guild_id, db_id)
        
        await interaction.response.send_message(f"🔄 성공적으로 **{target_pet.name}**(으)로 스왑(교체) 되었습니다! `/보호자` 명령어를 확인하세요.", ephemeral=True)


class MainPetHubView(View):
    def __init__(self, cog: PetManager, user_id: str, guild_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        for label in ["펫", "가방", "퀘스트", "상점", "설정"]:
            btn = Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"hub_{label}")
            btn.callback = self.handle_click
            self.add_item(btn)

    async def handle_click(self, interaction: discord.Interaction):
        msg = ""
        custom_id = interaction.data["custom_id"]
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        if pet:
            penalty = self.cog.check_penalties_and_update(self.guild_id, self.user_id, pet)
            if penalty == "RUNAWAY":
                await interaction.response.send_message("🚨 펫이 오랫동안 방치되어 야생으로 도망갔습니다.", ephemeral=True)
                return
        
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)
        # (여기에 있던 중복 응답 및 빈 메시지 전송 로직 삭제)

        if custom_id == "hub_펫":
            if not pet:
                await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)
                return
            
            pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
            embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
            for f in pet_data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            
            # 💡 웹 URL 방식 적용
            pet_image_url = pet_data.get("image_url")
            if pet_image_url:
                embed.set_thumbnail(url=pet_image_url)
            
            try:
                # 기존 로컬 파일 로직 제거
                await interaction.response.edit_message(
                    embed=embed, 
                    attachments=[], # 기존 파일 제거
                    view=PetInfoSubView(self.cog, self.user_id, self.guild_id)
                )
            except Exception as e:
                print(f"이미지 출력 에러: {e}")

        elif custom_id == "hub_상점":
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            
            # 상점 메뉴 구성 시 JSON 파일 기반으로 판매가 출력
            fruit_top_price = 50000
            if os.path.exists("data/pet_config.json"):
                try:
                    with open("data/pet_config.json", "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        fruit_top_price = cfg.get("fruit_high_price", 50000)
                except Exception: 
                    pass
                
            embed = discord.Embed(title="🛒 펫 상점", description=f"아이템을 구매하세요!\n보유 자산: **{user_data.get('cash', 0):,}원**", color=0xf1c40f)
            embed.add_field(name="🍎 열매 (포만감 회복)", value=f"- 최상급 열매 (포만감 +30): {fruit_top_price:,}원\n- 중급 열매 (포만감 +15): 30,000원\n- 하급 열매 (포만감 +5): 10,000원", inline=False)
            embed.add_field(name="🛡️ 일반 장비", value="- 머리/견갑/허리/다리 각 부위: 150,000원\n- 기본 스탯: HP +5, ATK +5, SPD +5", inline=False)
            try:
                await interaction.response.edit_message(embed=embed, view=ShopView(self.cog, self.user_id, self.guild_id))
            except Exception:
                pass
        elif custom_id == "hub_가방":
            if not pet:
                await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)
                return
            
            fruits = pet.inventory.get("열매", {})
            equips = pet.inventory.get("장비", [])
            embed = discord.Embed(title="🎒 내 가방", description="보유 중인 아이템 목록입니다.", color=0x9b59b6)
            embed.add_field(name="🍎 열매", value=f"- 최상급 열매: {fruits.get('상', 0)}개\n- 중급 열매: {fruits.get('중', 0)}개\n- 하급 열매: {fruits.get('하', 0)}개", inline=False)
            
            eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
            embed.add_field(name="🛡️ 장비", value=eq_list, inline=False)
            
            try:
                await interaction.response.edit_message(embed=embed, view=InventoryView(self.cog, self.user_id, self.guild_id))
            except Exception:
                pass
        elif custom_id == "hub_퀘스트":
            from pet_views import QuestView
            await interaction.response.edit_message(view=QuestView(self.cog, self.user_id, self.guild_id))
        elif custom_id == "hub_설정":
            from pet_views import SettingView
            await interaction.response.edit_message(view=SettingView(self.cog, self.user_id, self.guild_id))

class PetInfoSubView(View):
    def __init__(self, cog: PetManager, user_id: str, guild_id: str):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        for label in ["행동", "장비", "스킬", "진화", "처음으로"]:
            style = discord.ButtonStyle.secondary if label != "처음으로" else discord.ButtonStyle.danger
            btn = Button(label=label, style=style, custom_id=f"pet_{label}")
            btn.callback = self.handle_click
            self.add_item(btn)

    async def handle_click(self, interaction: discord.Interaction):
        msg = ""
        custom_id = interaction.data["custom_id"]
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        if pet:
            penalty = self.cog.check_penalties_and_update(self.guild_id, self.user_id, pet)
            if penalty == "RUNAWAY":
                await interaction.response.send_message("🚨 펫이 야생으로 도망갔습니다.", ephemeral=True)
                return
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
            # (여기에 있던 중복 응답 및 빈 메시지 전송 로직 삭제)

        if custom_id == "pet_처음으로":
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            try:
                await interaction.response.edit_message(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception:
                pass
        elif custom_id == "pet_장비":
            fruits = pet.inventory.get("열매", {})
            equips = pet.inventory.get("장비", [])
            embed = discord.Embed(title="🎒 장비 및 가방", description="장비를 장착하거나 아이템을 사용하세요.", color=0x9b59b6)
            embed.add_field(name="🍎 열매", value=f"- 최상급: {fruits.get('상', 0)}개 | 중급: {fruits.get('중', 0)}개 | 하급: {fruits.get('하', 0)}개", inline=False)
            eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
            embed.add_field(name="🛡️ 보유 장비", value=eq_list, inline=False)
            try:
                await interaction.response.edit_message(embed=embed, view=InventoryView(self.cog, self.user_id, self.guild_id))
            except Exception:
                pass
        elif custom_id == "pet_행동":
            actions = pet.get_available_actions()
            embed = discord.Embed(title=f"🎭 {pet.name} 행동 목록", description="행동할 상호작용 버튼을 선택하세요.")
            try:
                await interaction.response.edit_message(embed=embed, view=PetActionExecutionView(self.cog, self.user_id, self.guild_id, actions))
            except Exception:
                pass
        elif custom_id == "pet_스킬":
            from pet_views import SkillManageView
            await interaction.response.edit_message(view=SkillManageView(self.cog, self.user_id, self.guild_id))
        elif custom_id == "pet_진화":
            from pet_views import EvolutionView
            await interaction.response.edit_message(view=EvolutionView(self.cog, self.user_id, self.guild_id))

class ShopView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        self.add_item(discord.ui.Button(label="최상급 열매", custom_id="buy_fruit_상", row=0))
        self.add_item(discord.ui.Button(label="중급 열매 (3만)", custom_id="buy_fruit_중", row=0))
        self.add_item(discord.ui.Button(label="하급 열매 (1만)", custom_id="buy_fruit_하", row=0))
        
        self.add_item(discord.ui.Button(label="머리 장비 (15만)", custom_id="buy_equip_머리", row=1))
        self.add_item(discord.ui.Button(label="견갑 장비 (15만)", custom_id="buy_equip_견갑", row=1))
        self.add_item(discord.ui.Button(label="허리 장비 (15만)", custom_id="buy_equip_허리", row=1))
        self.add_item(discord.ui.Button(label="다리 장비 (15만)", custom_id="buy_equip_다리", row=1))
        
        btn = discord.ui.Button(label="처음으로", style=discord.ButtonStyle.danger, custom_id="buy_back_none", row=2)
        self.add_item(btn)
        
        for item in self.children:
            item.callback = self.handle_click

    async def handle_click(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        _, item_type, item_name = custom_id.split("_")

        act_name = "상점 거래"
        
        if item_type == "back":
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            pet = self.cog.get_user_pet(self.guild_id, self.user_id)
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            try:
                await interaction.response.edit_message(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception: 
                pass
            return

        db = self.cog._get_db(int(self.guild_id))
        user_data = db.get_user(self.user_id)
        cash = user_data.get('cash', 0) if user_data else 0
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)
            return

        price = 0
        if item_type == "fruit":
            if item_name == "상":
                price = 50000
                if os.path.exists("data/pet_config.json"):
                    try:
                        with open("data/pet_config.json", "r", encoding="utf-8") as f:
                            cfg = json.load(f)
                            price = cfg.get("fruit_high_price", 50000)
                    except Exception: 
                        pass
            elif item_name == "중": 
                price = 30000
            elif item_name == "하": 
                price = 10000
        elif item_type == "equip":
            price = 150000
            
        if cash < price:
            await interaction.response.send_message("❌ 보유 자산이 부족합니다.", ephemeral=True)
            return
            
        db.add_user_cash(self.user_id, -price)
        
        msg = ""
        if item_type == "fruit":
            pet.inventory["열매"][item_name] = pet.inventory["열매"].get(item_name, 0) + 1
            msg = f"🛒 {item_name}급 열매를 구매하여 가방에 넣었습니다!"
        elif item_type == "equip":
            pet.inventory["장비"].append({"부위": item_name, "등급": "일반"})
            msg = f"🛒 일반 등급 {item_name} 장비를 구매하여 가방에 넣었습니다!"
            
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        # 1. 펫 상태창 임베드 데이터 생성
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)

        # 2. 결과 임베드 생성 (msg를 여기에 담습니다)
        embed = discord.Embed(title=f"명령: {act_name}", description=msg, color=0x2ecc71)
        
        # 3. 펫 상태창 필드 추가
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        
        # 4. 이미지 처리
        pet_image_url = pet_data.get("image_url")
        if pet_image_url:
            embed.set_thumbnail(url=pet_image_url)

        # 5. [중요] 단 한 번만 응답을 수정합니다.
        try:
            await interaction.response.edit_message(
                embed=embed, 
                view=PetActionExecutionView(self.cog, self.user_id, self.guild_id, pet.get_available_actions())
            )
        except Exception as e:
            print(f"UI 갱신 오류: {e}")
        
        user_data = db.get_user(self.user_id)
        
        # 최상급 열매 가격 재호출
        fruit_top_price = 50000
        if os.path.exists("data/pet_config.json"):
            try:
                with open("data/pet_config.json", "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                    fruit_top_price = cfg.get("fruit_high_price", 50000)
            except Exception: 
                pass

        embed = discord.Embed(title="🛒 펫 상점", description=f"아이템을 구매하세요!\n보유 자산: **{user_data.get('cash', 0):,}원**\n\n{msg}", color=0xf1c40f)
        embed.add_field(name="🍎 열매 (포만감 회복)", value=f"- 최상급 열매 (포만감 +30): {fruit_top_price:,}원\n- 중급 열매 (포만감 +15): 30,000원\n- 하급 열매 (포만감 +5): 10,000원", inline=False)
        embed.add_field(name="🛡️ 일반 장비", value="- 머리/견갑/허리/다리 각 부위: 150,000원\n- 기본 스탯: HP +5, ATK +5, SPD +5", inline=False)
        
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception: 
            pass


class InventoryView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        self.add_item(discord.ui.Button(label="최상급 열매 사용", custom_id="inv_use_상", row=0))
        self.add_item(discord.ui.Button(label="중급 열매 사용", custom_id="inv_use_중", row=0))
        self.add_item(discord.ui.Button(label="하급 열매 사용", custom_id="inv_use_하", row=0))
        
        self.add_item(discord.ui.Button(label="머리 장착", custom_id="inv_equip_머리", row=1))
        self.add_item(discord.ui.Button(label="견갑 장착", custom_id="inv_equip_견갑", row=1))
        self.add_item(discord.ui.Button(label="허리 장착", custom_id="inv_equip_허리", row=1))
        self.add_item(discord.ui.Button(label="다리 장착", custom_id="inv_equip_다리", row=1))
        
        btn = discord.ui.Button(label="처음으로", style=discord.ButtonStyle.danger, custom_id="inv_back_none", row=2)
        self.add_item(btn)
        
        for item in self.children:
            item.callback = self.handle_click

    async def handle_click(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        _, action, item_name = custom_id.split("_")
        
        if action == "back":
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            pet = self.cog.get_user_pet(self.guild_id, self.user_id)
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            try:
                await interaction.response.edit_message(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception: 
                pass
            return
            
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet: return
        
        msg = ""
        if action == "use":
            count = pet.inventory["열매"].get(item_name, 0)
            if count <= 0:
                await interaction.response.send_message(f"❌ {item_name}급 열매가 부족합니다.", ephemeral=True)
                return
            pet.inventory["열매"][item_name] -= 1
            heal = 30 if item_name == "상" else (15 if item_name == "중" else 5)
            pet.fullness = min(100, pet.fullness + heal)
            msg = f"😋 {item_name}급 열매를 먹어 포만감이 {heal} 올랐습니다! (현재: {int(pet.fullness)}/100)"
            
        elif action == "equip":
            equips = pet.inventory.get("장비", [])
            part_equips = [e for e in equips if e["부위"] == item_name]
            if not part_equips:
                await interaction.response.send_message(f"❌ 장착할 {item_name} 부위 장비가 가방에 없습니다.", ephemeral=True)
                return
            
            grade_val = {"일반": 1, "희귀": 2, "영웅": 3, "전설": 4}
            part_equips.sort(key=lambda x: grade_val.get(x["등급"], 0), reverse=True)
            best_equip = part_equips[0]
            
            current_equip = pet.equipment.get(item_name)
            if current_equip == best_equip["등급"]:
                await interaction.response.send_message(f"❌ 이미 {best_equip['등급']} 등급 장비를 장착 중입니다.", ephemeral=True)
                return
                
            pet.equipment[item_name] = best_equip["등급"]
            msg = f"🛡️ {best_equip['등급']} 등급 {item_name} 장비를 장착했습니다!"
            
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        try:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)
        except Exception as e:
            print(f"UI 갱신 오류: {e}")
        
        fruits = pet.inventory.get("열매", {})
        equips = pet.inventory.get("장비", [])
        embed = discord.Embed(title="🎒 내 가방", description=f"**{msg}**\n\n보유 중인 아이템 목록입니다.", color=0x9b59b6)
        embed.add_field(name="🍎 열매", value=f"- 최상급 열매: {fruits.get('상', 0)}개\n- 중급 열매: {fruits.get('중', 0)}개\n- 하급 열매: {fruits.get('하', 0)}개", inline=False)
        eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
        embed.add_field(name="🛡️ 장비", value=eq_list, inline=False)
        
        try:
            await interaction.response.edit_message(embed=embed, view=self)
        except Exception: 
            pass


class NameChangeModal(discord.ui.Modal, title='펫 이름 변경'):
    new_name = discord.ui.TextInput(
        label='새로운 이름',
        style=discord.TextStyle.short,
        placeholder='새로운 이름을 입력하세요 (최대 20자)',
        required=True,
        max_length=20
    )

    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    async def on_submit(self, interaction: discord.Interaction):
        msg = "이름을 변경했습니다."
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            await interaction.response.send_message("❌ 펫 정보를 불러올 수 없습니다.", ephemeral=True)
            return
            
        old_name = pet.name
        pet.name = self.new_name.value
        pet.name_changed = True
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        try:
            await interaction.response.edit_message(embed=embed, attachments=[], view=self)
        except Exception as e:
            print(f"UI 갱신 오류: {e}")
        
        await interaction.response.send_message(f"✨ 성공적으로 이름이 변경되었습니다! `{old_name}` -> `{pet.name}`\n대시보드에서 `펫` 버튼을 다시 누르면 반영된 이름이 보입니다.", ephemeral=True)


class PvPInteractiveView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, battle_engine):
        super().__init__(timeout=3.0)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.battle = battle_engine
        self.message = None
        
        skills = battle_engine.pet_a.skills if battle_engine.pet_a.skills else ["몸통박치기"]
        for sk in skills[:4]:
            btn = discord.ui.Button(label=sk, style=discord.ButtonStyle.danger, custom_id=f"skill_{sk}")
            btn.callback = self.handle_skill
            self.add_item(btn)

    async def handle_skill(self, interaction: discord.Interaction):
        skill_name = interaction.data["custom_id"].split("_")[1]
        await self.process_turn(interaction, skill_name)

    async def process_turn(self, interaction: discord.Interaction, player_action=None):
        result = self.battle.execute_turn(player_action)
        
        log_text = "\n".join(self.battle.log[-12:])
        embed = discord.Embed(title="⚔️ PvP 배틀 진행 중!", description=log_text, color=0xe74c3c)
        embed.add_field(name=f"🟢 {self.battle.pet_a.name} (나)", value=f"HP: {max(0, self.battle.hp_a)}/{self.battle.max_hp_a}\nMP: {max(0, self.battle.mp_a)}/{self.battle.pet_a.max_mp}")
        embed.add_field(name=f"🔴 {self.battle.pet_b.name} (적)", value=f"HP: {max(0, self.battle.hp_b)}/{self.battle.max_hp_b}\nMP: {max(0, self.battle.mp_b)}/{self.battle.pet_b.max_mp}")
        
        if result:
            self.stop()
            pet = self.cog.get_user_pet(self.guild_id, self.user_id)
            if pet:
                pet.pvp_count = getattr(pet, 'pvp_count', 0) + 1
                
                # 랭크전 점수 처리
                is_ranked = getattr(self.battle, 'is_ranked', False)
                db = self.cog._get_db(self.guild_id)
                user_data = db.get_user(self.user_id)
                rank_score = user_data.get('pet_rank_score', 1000) if user_data else 1000
                
                if result == "A":
                    pet.win_count = getattr(pet, 'win_count', 0) + 1
                    pet.gain_exp(200 if not is_ranked else 300)
                    if is_ranked:
                        rank_score += 25
                        embed.add_field(name="결과", value=f"🎉 [랭크전 승리!] 경험치 300과 랭크 점수 25점을 획득했습니다! (현재 점수: {rank_score}점)", inline=False)
                    else:
                        embed.add_field(name="결과", value="🎉 승리하여 경험치 200과 전적을 획득했습니다!", inline=False)
                elif result == "DRAW":
                    pet.gain_exp(50)
                    embed.add_field(name="결과", value="🤝 무승부! 약간의 경험치를 획득했습니다.", inline=False)
                else:
                    if is_ranked:
                        rank_score = max(0, rank_score - 15)
                        embed.add_field(name="결과", value=f"💀 [랭크전 패배...] 랭크 점수가 15점 하락했습니다. (현재 점수: {rank_score}점)", inline=False)
                    else:
                        embed.add_field(name="결과", value="💀 패배했습니다. 다음 기회를 노리세요!", inline=False)
                
                self.cog.save_user_pet(self.guild_id, self.user_id, pet)

                pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
                embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
                for f in pet_data["fields"]:
                    embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

                try:
                    await interaction.message.edit(embed=embed, attachments=[])
                except Exception as e:
                    print(f"메시지 수정 에러: {e}")
                if is_ranked:
                    try:
                        with db.get_connection() as conn:
                            conn.execute("UPDATE users SET pet_rank_score = ? WHERE user_id = ? AND guild_id = ?", (rank_score, self.user_id, self.guild_id))
                            conn.commit()
                    except Exception as e:
                        print(f"랭크 점수 업데이트 실패: {e}")
            
            try:
                await interaction.response.edit_message(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception:
                pass
        else:
            try:
                await interaction.response.edit_message(embed=embed, view=self)
            except Exception:
                pass

    async def on_timeout(self):
        result = None
        while not result:
            result = self.battle.execute_turn(None)
            
        log_text = "\n".join(self.battle.log[-15:])
        embed = discord.Embed(title="⚔️ PvP 배틀 자동 완료!", description="[자동 진행] 제한 시간이 초과되어 남은 전투가 자동으로 진행되었습니다.\n" + log_text, color=0xe74c3c)
        embed.add_field(name=f"🟢 {self.battle.pet_a.name} (나)", value=f"HP: {max(0, self.battle.hp_a)}/{self.battle.max_hp_a}")
        embed.add_field(name=f"🔴 {self.battle.pet_b.name} (적)", value=f"HP: {max(0, self.battle.hp_b)}/{self.battle.max_hp_b}")
        
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if pet:
            pet.pvp_count = getattr(pet, 'pvp_count', 0) + 1
            if result == "A":
                pet.win_count = getattr(pet, 'win_count', 0) + 1
                pet.gain_exp(200)
                embed.add_field(name="결과", value="🎉 승리하여 경험치 200과 전적을 획득했습니다!", inline=False)
            elif result == "DRAW":
                pet.gain_exp(50)
                embed.add_field(name="결과", value="🤝 무승부! 약간의 경험치를 획득했습니다.", inline=False)
            else:
                embed.add_field(name="결과", value="💀 패배했습니다. 다음 기회를 노리세요!", inline=False)
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)

            pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
            embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
            for f in pet_data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        if self.message:
            try:
                await self.message.edit(embed=embed, attachments=[], view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception as e:
                print(f"타임아웃 UI 갱신 실패: {e}")

class RankQueueManager:
    def __init__(self):
        self.queue = deque()
        self.lock = asyncio.Lock() # 동시성 제어를 위한 Lock 추가

    async def add_user(self, user_id, interaction):
        async with self.lock: # 락을 걸어 안전하게 큐 조작
            # 이미 대기 중인지 확인
            if user_id not in [u[0] for u in self.queue]:
                self.queue.append((user_id, interaction))
                return True
        return False # 이미 대기 중인 경우

class PetActionExecutionView(View):
    def __init__(self, cog: PetManager, user_id: str, guild_id: str, actions: list):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        
        for act in actions:
            # 스타일을 인스턴스가 아닌 정수형(ButtonStyle.success)으로 명시
            btn = discord.ui.Button(
                label=act, 
                style=discord.ButtonStyle.success,
                custom_id=f"act_{act}"
            )
            # 클래스 내부의 메서드를 정확히 연결
            btn.callback = self.handle_action
            self.add_item(btn)

    async def handle_action(self, interaction: discord.Interaction):
        # 1. 공통 데이터 로드
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 펫 정보를 불러올 수 없습니다.", ephemeral=True)
        
        custom_id = interaction.data.get("custom_id", "")
        act_name = custom_id.split("_")[1] if "_" in custom_id else "알 수 없음"

        # --- A. [특수 행동: 랭크전/PvP] 분기 ---
        if act_name == "랭크전":
            if pet.mood_state == "화남":
                return await interaction.response.send_message("❌ 기분이 나빠 배틀 거부 중입니다!", ephemeral=True)
            self.cog.rank_queue.add_user(self.user_id, interaction)
            embed = discord.Embed(title="⌛ 랭크전 매칭 대기 중", description="60초 동안 서버 내 다른 도전자와 매칭을 시도합니다...", color=0x3498db)
            await interaction.response.edit_message(embed=embed, view=None)
            asyncio.create_task(self.process_match_logic(interaction, pet))
            return 

        if act_name == "PvP":
            if pet.mood_state == "화남":
                return await interaction.response.send_message("❌ 기분이 나빠 배틀 거부 중입니다!", ephemeral=True)
            # PvP 로직 실행
            types = ["불", "물", "풀", "전기", "비행", "땅", "어둠", "독", "에스퍼", "노말"]
            wild_pet = Pet("야생의 펫", random.choice(types))
            wild_pet.level = max(1, pet.level + random.randint(-2, 2))
            wild_pet.stage = "성체"
            battle = PvPBattle(pet, wild_pet)
            battle.is_ranked = False
            embed = discord.Embed(title="⚔️ 일반 친선전 시작!", description=f"{pet.name} 님이 야생의 {wild_pet.name}을(를) 만났습니다!", color=0xe74c3c)
            await interaction.response.edit_message(embed=embed, view=PvPInteractiveView(self.cog, self.user_id, self.guild_id, battle))
            return

        # --- B. [일반 행동] 수행 로직 ---
        msg = f"⚙️ {pet.name}이(가) {act_name} 행동을 마쳤습니다."
        
        # 제한 검사
        if (act_name in ["먹이 주기", "먹이"] and pet.fullness >= 99) or \
           (act_name == "청소하기" and pet.cleanliness >= 99) or \
           (act_name in ["쓰다듬기", "벌레잡기"] and pet.affinity >= 297):
            return await interaction.response.send_message("❌ 이미 상태가 충분합니다!", ephemeral=True)

        # 상태 변화 로직
        if pet.stage == "알": msg = pet.interact_egg(act_name)
        elif act_name in ["먹이 주기", "먹이"]:
            pet.fullness = min(100, pet.fullness + 30); msg = "🍖 먹이를 주었습니다."
        elif act_name == "쓰다듬기":
            pet.affinity = min(300, pet.affinity + 15); msg = "👋 정성스레 쓰다듬었습니다."
        elif act_name == "청소하기":
            pet.cleanliness = min(100, pet.cleanliness + 50); msg = "🧼 깨끗이 청소했습니다!"
        elif act_name in ["놀아주기", "장난감"]:
            msg = pet.gain_exp(40) if pet.energy >= 15 else "❌ 에너지가 부족합니다."
        elif act_name in ["재우기", "휴식"]:
            pet.energy = min(100, pet.energy + 50); pet.stress = max(0, pet.stress - 10); msg = "💤 푹 쉬었습니다."
        elif act_name == "훈련":
            if pet.train_count_today >= 3: msg = "❌ 훈련 횟수 초과."
            else: pet.train_count_today += 1; msg = pet.gain_exp(60)
        elif act_name == "탐험":
            if pet.explore_count_today >= 3: msg = "❌ 탐험 횟수 초과."
            else: pet.explore_count_today += 1; msg = pet.gain_exp(100)

        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        # --- C. [출력] 메시지 분리 (결과창 먼저 -> 상태창 followup) ---
        # 1. 결과 텍스트창 수정
        embed_result = discord.Embed(title=f"명령: {act_name}", description=msg, color=0x2ecc71)
        await interaction.response.edit_message(embed=embed_result, view=None) 
        
        # 2. 상태창 followup 전송
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        embed_status = discord.Embed(title=pet_data["title"], color=0x2ecc71)
        for f in pet_data["fields"]:
            embed_status.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        if pet_data.get("image_url"):
            embed_status.set_thumbnail(url=pet_data["image_url"])
            
        await interaction.followup.send(
            embed=embed_status, 
            view=PetActionExecutionView(self.cog, self.user_id, self.guild_id, pet.get_available_actions())
        )

async def setup(bot):
    await bot.add_cog(PetManager(bot))