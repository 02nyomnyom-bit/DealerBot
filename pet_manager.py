# pet_manager.py
from __future__ import annotations
import random
import time
import json
import discord
import os
import asyncio
from collections import defaultdict
from discord import app_commands, Interaction
from discord.ext import commands
from discord.ui import Button, View
from typing import Optional, List
from database_manager import DatabaseManager
from pet_skill import DiscordUIFormatter
from pet_climate import ClimateManager

# 알 -> 새끼 -> 유년기 -> 성체 -> 최종 진화
class Pet:
    def __init__(self, name: str, owner_name: str = None, main_type: str = "노말"):
        self.name = name
        self.stage = "알"
        self.owner_name = owner_name
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
        self.cleanliness = 100
        self.closeness = 30
        self.stress = 0
        self.health = 100
        self.mood_score = 100
        self.energy = 100
        self.affinity = 0
        
        # 전투 스탯 (기본값)
        self.hp = 20
        self.max_hp = 100
        self.attack = 15
        self.defense = 10
        self.speed = 10
        self.exp = 0
        self.potential = 0
        self.rank_score = 1000
        self.is_dead = False
        self.luck = 10

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
        self.pet_count_today = 0      # 쓰다듬기 카운트
        self.clean_count_today = 0    # 청소 카운트
        self.bug_count_today = 0      # 벌레잡기 카운트
        self.sleep_count_today = 0    # 휴식 및 재우기 일일 카운트
        self.last_decay_time = time.time()

        # 알 돌보기 일일 행동 기록용 딕셔너리
        self.egg_actions_today = {"햇빛받기": 0, "보듬어주기": 0, "씻겨주기": 0, "품어주기": 0}

        self.skills = []
        self.equipment = {"머리": None, "견갑": None, "허리": None, "다리": None, "아이템": None}
        self.inventory = {"열매": {"상": 0, "중": 0, "하": 0}, "장비": []}
        self.learned_ultimate = None

        self.last_update_time = getattr(self, 'last_update_time', time.time())

        # 📜 [추가] 일일 퀘스트 카운터 및 보상 플래그
        self.stroke_count_today = 0
        self.last_reward_date = None

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

    def update_passive_decay(self):
        """시간 경과에 따른 스탯 자연 감소 및 일일 제한 리셋 (원본 복원)"""
        current_time = time.time()

        # 1. 초기화되지 않은 경우 대비
        if not hasattr(self, 'last_update_time'):
            self.last_update_time = current_time
        if not hasattr(self, 'last_decay_time'):
            self.last_decay_time = current_time
    
        # 2. 날짜 비교 변수 정의 (안전한 속성 접근)
        last_date = time.strftime('%Y-%m-%d', time.localtime(self.last_update_time + 32400))
        current_date = time.strftime('%Y-%m-%d', time.localtime(current_time + 32400))

        # 3. 자정 리셋 로직
        if last_date != current_date:
            self.train_count_today = 0
            self.explore_count_today = 0
            self.snack_count_today = 0
            self.pet_count_today = 0
            self.clean_count_today = 0
            self.bug_count_today = 0
            self.sleep_count_today = 0 

            # ✅ 알 돌보기 일일 횟수도 자정에 함께 초기화!
            self.egg_actions_today = {"햇빛받기": 0, "보듬어주기": 0, "씻겨주기": 0, "품어주기": 0}
            
            # 업데이트 시간 갱신
            self.last_update_time = current_time

        hours_passed = (current_time - self.last_update_time) / 3600.0
        if hours_passed <= 0: return
        
        # 알 상태일 경우 포만감/청결도 등 스탯 자연 감소를 진행하지 않고 여기서 중단합니다. (새끼부터 적용됨)
        if self.stage == "알":
            self.last_decay_time = current_time
            return
        
        # 48시간(이틀) 기준 = 2.1
        # 72시간(3일) 기준 = 1.4
        # 96시간(4일) 기준 = 1.0
        
        # 3. 상태 감소 연산 (기존 로직 유지)
        decay_modifier = 2.0 if self.stress >= 60 else 1.0
        self.fullness = max(0, self.fullness - (hours_passed * 2.1))
        self.cleanliness = max(0, self.cleanliness - (hours_passed * 2.1))
        self.mood_score = max(0, self.mood_score - (hours_passed * 1.5 * decay_modifier))

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

        self.last_decay_time = current_time

    def add_exp(self, amount: int) -> bool:
        """경험치를 획득하고 레벨업 여부를 반환"""
        self.exp += amount
        needed = self.level * 100
        leveled_up = False
        while self.exp >= needed:
            self.exp -= needed
            self.level += 1
            self.max_hp += 15
            self.hp = self.max_hp
            self.attack += 3
            self.defense += 2
            self.speed += 2
            leveled_up = True
            needed = self.level * 100
        return leveled_up

    def check_ultimate_skill(self) -> Optional[str]:
        """성체 이상의 단계에서 친밀도가 100에 도달할 경우 전용 궁극기 각성"""
        if self.stage in ["성체", "최종 진화"] and self.closeness >= 100 and not self.learned_ultimate:
            ult_skills = {
                "불": "지옥불", "물": "대해일", "풀": "대자연의 분노", "전기": "천벌", "비행": "폭풍우",
                "땅": "대지진", "얼음": "절대영도", "어둠": "빅뱅", "독": "맹독지대", "에스퍼": "차원절단", "노말": "최후의 일격"
            }
            skill = ult_skills.get(self.main_type, "최후의 일격")
            self.learned_ultimate = skill
            if len(self.skills) < 4:
                self.skills.append(skill)
            else:
                self.skills[3] = skill  # 마지막 슬롯 대체
            return skill
        return None

    def get_available_actions(self):
        """기획서 행동 해금 시스템 테이블 매핑"""
        actions = {
            "알": ["햇빛받기", "보듬어주기", "씻겨주기", "품어주기"],
            "새끼": ["먹이 주기", "간식 주기", "쓰다듬기", "청소하기", "놀아주기", "벌레잡기", "산책"],
            "유년기": ["먹이 주기", "간식 주기", "청소하기", "훈련", "탐험", "채집", "장난감", "휴식", "산책"],
            "성체": ["먹이 주기", "간식 주기", "청소하기", "훈련", "탐험", "채집", "PvP", "휴식", "산책"],
            "최종 진화": ["먹이 주기", "간식 주기", "청소하기", "훈련", "랭크전", "탐험", "교배", "휴식", "산책"]
        }
        available = actions.get(self.stage, []).copy()
        if self.stage != "알" and not getattr(self, "name_changed", False):
            available.insert(0, "이름 변경")
        return available

    def interact_egg(self, action_name):
        """알 단계 전용 행동 핸들러"""
        # ✅ 1. 기존에 생성된 알(DB에 정보가 없는 경우)을 위한 방어 코드
        if not hasattr(self, 'egg_actions_today'):
            self.egg_actions_today = {"햇빛받기": 0, "보듬어주기": 0, "씻겨주기": 0, "품어주기": 0}

        # ✅ 2. 하루 1회 제한 검사
        if self.egg_actions_today.get(action_name, 0) >= 1:
            return f"❌ [{action_name}] 행동은 하루에 한 번만 가능합니다! 내일 다시 돌봐주세요."

        # ✅ 3. 통과 시 해당 행동 카운터 증가
        self.egg_actions_today[action_name] = 1

        # (이하 기존 로직 동일하게 유지)
        climate = ClimateManager().get_current_climate()
        
        if action_name == "햇빛받기":
            self.warmth = min(100, self.warmth + 15)
            
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
        # 🧬 성격에 따른 보너스 가중치 (예: '용맹함'은 공격력 상승 가중치 증가)
        stat_multiplier = 1.2 if self.personality == "용맹함" else 1.0
        
        # 레벨업 시 스탯 부여
        self.attack += int(random.randint(1, 3) * stat_multiplier)

        if self.level % 10 == 0:
            if self.main_type == "불" and self.personality == "다혈질":
                self.skills.append("화염 방사")

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

    def try_learn_skill(self) -> tuple:
        from pet_skill import get_random_skill_by_type
        
        is_full = len(self.skills) >= 4
        success_chance = 0.25 if is_full else 0.70
        
        if random.random() > success_chance:
            return ("FAIL", "...아쉽게도 새로운 스킬을 떠올리지 못했습니다.")

        new_skill = get_random_skill_by_type(self.main_type)
        
        if not is_full:
            self.skills.append(new_skill)
            return ("SUCCESS", f"✨ {new_skill}을(를) 배웠습니다!")
        else:
            return ("CHOICE_NEEDED", new_skill)
        
    @classmethod
    def from_dict(cls, data: dict) -> Pet:
        pet = cls(data.get('name', '이름없음'), data.get('main_type', '노말'))
        pet.__dict__.update(data)
        if not hasattr(pet, 'equipment'):
            pet.equipment = {"머리": None, "견갑": None, "허리": None, "다리": None, "아이템": None}
        if not hasattr(pet, 'inventory'):
            pet.inventory = {"열매": {"상": 0, "중": 0, "하": 0}, "장비": []}
        return pet

class SkillConfirmView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, skill_to_remove):
        super().__init__()
        self.cog, self.user_id, self.guild_id = cog, user_id, guild_id
        self.skill_to_remove = skill_to_remove

    @discord.ui.button(label="예 (교체하기)", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        pet.skills.remove(self.skill_to_remove)
        self.cog.save_user_pet(self.guild_id, self.user_id, pet) # 💾 DB 저장
        await interaction.response.send_message("스킬이 교체되었습니다.", ephemeral=True)

class PetActionSelectionView(discord.ui.View):
    def __init__(self, cog, user_id: int, guild_id: int, pet: Pet):
        super().__init__(timeout=120)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.pet = pet
        
        # 상호작용 및 모험 옵션 세팅
        actions = ["쓰다듬기", "청소하기", "벌레잡기", "간식 주기", "산책", "훈련", "탐험", "채집", "전투", "랭크전"]
        for act in actions:
            self.add_item(ActionButton(act))

class ActionButton(discord.ui.Button):
    def __init__(self, action_name: str):
        style = discord.ButtonStyle.secondary
        if action_name in ["탐험", "채집", "전투", "랭크전"]:
            style = discord.ButtonStyle.danger
        elif action_name in ["산책", "훈련"]:
            style = discord.ButtonStyle.success
            
        super().__init__(label=action_name, style=style)
        self.action_name = action_name

    async def callback(self, interaction: Interaction):
        view: PetActionSelectionView = self.view
        view.pet.update_passive_decay()
        
        # 인자를 5개로 맞춰서 전달하세요
        exec_view = PetActionExecutionView(
            view.cog, 
            view.user_id, 
            view.guild_id, 
            view.pet,        # Pet 객체 전달
            self.action_name # action_name 전달
        )
        await exec_view.handle_action(interaction)

class PetManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.matching_queues = defaultdict(list)
        self.match_tasks = {}
        self.db_managers = {}
        self.quest_pool = [
            {"id": "train", "name": "🏋️ 펫 훈련하기", "target": 3, "desc": "훈련을 3회 수행하세요."},
            {"id": "stroke", "name": "❤️ 펫 쓰다듬기", "target": 5, "desc": "펫을 5회 쓰다듬어주세요."},
            {"id": "clean", "name": "🧼 펫 청소하기", "target": 2, "desc": "펫 청소를 2회 완료하세요."},
            {"id": "feed", "name": "🍖 펫 먹이주기", "target": 2, "desc": "펫에게 먹이를 2회 주세요."}
        ]

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

    def assign_daily_quests(self, pet):
        """매일 새로운 퀘스트를 선정하되, 현재 단계에서 가능한 미션만 부여합니다."""
        today = time.strftime('%Y-%m-%d', time.localtime(time.time() + 32400))
        
        if getattr(pet, 'quest_date', None) == today:
            return

        # 펫의 현재 단계에서 할 수 있는 행동 목록 가져오기
        available_actions = pet.get_available_actions()
        valid_quests = []
        
        # 퀘스트별 필요 행동 매핑
        req_actions = {
            "train": "훈련",
            "stroke": "쓰다듬기",
            "clean": "청소하기",
            "feed": ["먹이 주기", "먹이"] # 단계에 따라 이름이 약간 다름
        }

        # 할 수 있는 행동에 해당하는 퀘스트만 필터링
        for q in self.quest_pool:
            req = req_actions.get(q["id"])
            if isinstance(req, list):
                if any(a in available_actions for a in req):
                    valid_quests.append(q)
            else:
                if req in available_actions:
                    valid_quests.append(q)

        # 가능한 퀘스트 중 최대 3개 무작위 추출
        num_to_select = min(3, len(valid_quests))
        selected_quests = random.sample(valid_quests, num_to_select) if num_to_select > 0 else []
        
        pet.daily_quests = {q["id"]: {"count": 0, "target": q["target"]} for q in selected_quests}
        pet.quest_date = today

    # 훈련 버튼 핸들러 예시
    async def handle_train(self, pet):
        pet.train_count_today += 1 # 기존 카운트
    
        # [확장] 무작위 퀘스트 카운트 체크
        if hasattr(pet, 'daily_quests') and "train" in pet.daily_quests:
            if pet.daily_quests["train"]["count"] < pet.daily_quests["train"]["target"]:
                pet.daily_quests["train"]["count"] += 1

    def delete_user_pet(self, guild_id: str, user_id: str):
        """방치형 페널티로 야생으로 날아갈 시 DB 레코드 완전히 말소"""
        db = self._get_db(int(guild_id))
        db.execute_query("DELETE FROM user_pets WHERE user_id = ? AND guild_id = ?", (user_id, guild_id), 'none')

    async def force_release_pet(self, guild_id: int, user_id: int) -> bool:
        """관리자 권한으로 대상 유저의 현재 펫을 강제 방생(삭제)합니다."""
        # await 제거 및 string 형변환
        current_pet = self.get_user_pet(str(guild_id), str(user_id)) 
        if not current_pet:
            return False # 펫이 없으면 False 반환
            
        # 기존 설정하신 DatabaseManager 구조에 맞게 쿼리 실행
        db = self._get_db(guild_id)
        db.execute_query(
            "DELETE FROM user_pets WHERE guild_id = ? AND user_id = ?", 
            (str(guild_id), str(user_id)), 
            'none'
        )
        return True
    
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

    # pet_manager.py -> PetManager 클래스 내부에 추가
    async def start_breeding(self, guild_id: str, user_id: str) -> tuple[str, str, Optional[discord.Embed]]:
        """교배 시스템 데이터 연산 및 유전 로직을 처리합니다."""
        db = self._get_db(int(guild_id))
        
        # 1. 보유 공간 체크 (최대 3마리 제한)
        total_pets = self.get_total_pet_count(guild_id, user_id)
        if total_pets >= 3:
            return "SPACE_FULL", "❌ 더 이상 알을 품을 수 있는 둥지가 없습니다. 보유 공간(최대 3마리 제한)을 먼저 정리해 주세요.", None
            
        # 2. 펫 상태 및 진화 단계 체크
        pet = self.get_user_pet(guild_id, user_id)
        if not pet:
            return "NO_PET", "❌ 동행 중인 펫이 없습니다.", None
            
        if pet.stage != "최종 진화":
            return "NOT_FINAL_STAGE", "❌ 교배는 **최종 진화** 단계의 펫만 가능합니다.", None
            
        # 3. 비용 체크 및 차감 (300,000 골드)
        user_data = db.get_user(user_id)
        cash = user_data.get('cash', 0) if user_data else 0
        
        if cash < 300000:
            return "NOT_ENOUGH_GOLD", "❌ 교배 비용(300,000원)이 부족합니다.", None
            
        db.add_user_cash(user_id, -300000)
        
        # 4. 유전 및 능력치 결정 로직 (NPC 파트너 생성)
        types = ["불", "물", "풀", "전기", "비행", "땅", "얼음", "어둠", "독", "에스퍼", "노말"]
        npc_type = random.choice(types)
        npc_iv = random.randint(15, 31)
        
        # 🧬 개체값(IV) 계산: 부모 평균 + 랜덤 보정치(-3 ~ +5), 최대 31 상한
        base_iv = (pet.iv + npc_iv) // 2
        new_iv = min(31, max(0, base_iv + random.randint(-3, 5)))
        
        # 🧬 속성(Type) 계산: 50% 확률로 내 펫 or NPC 속성
        new_type = random.choice([pet.main_type, npc_type])
        
        # 🧬 성격 계산: 30% 확률로 부모 유전, 70% 확률로 랜덤
        if pet.personality and random.random() < 0.3:
            new_personality = pet.personality
        else:
            new_personality = random.choice(["용맹함", "신중함", "다혈질", "나태", "변덕", None])
        
        # 5. 새로운 알 객체 생성 및 보관함(Storage) 이동
        user = self.bot.get_user(int(user_id))
        user_name = user.name if user else "보호자"
        
        child = Pet(name=f"@{user_name}의 알", owner_name=user_name, main_type=new_type)
        child.iv = new_iv
        child.personality = new_personality
        
        # 메인 자리를 교체하지 않고 보관함으로 즉시 전송
        self.add_stored_pet(guild_id, user_id, child)
        
        # 6. 성공 임베드 제작
        embed = discord.Embed(
            title="💞 교배 성공!", 
            description="교배소에서 30만 골드를 지불하고 훌륭한 파트너와 교배를 마쳤습니다.", 
            color=0xff9ff3
        )
        embed.add_field(
            name="🥚 새로운 생명", 
            value=f"새로운 알이 태어났습니다!\n(개체값 보정: {base_iv} ➡️ {new_iv})\n알은 즉시 **🗃️ 펫 보관함**으로 이동되었습니다. (보유 공간: {total_pets + 1}/3)", 
            inline=False
        )
        
        return "SUCCESS", "", embed
        
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
                
                db = self._get_db(int(guild_id))
                
                # 유저 재산(cash) 조회 후 30% 계산
                user_data = db.get_user(user_id)
                current_cash = user_data.get('cash', 0) if user_data else 0
                fine_amount = int(current_cash * 0.3)  # 재산의 30%
                
                # 계산된 벌금 차감
                db.add_user_cash(user_id, -fine_amount)
                return "SICK_TRIGGERED"

        return None
    
    async def find_matching_user(self, guild_id: str, user_id: str) -> Optional[str]:
        """60초 동안 대기열에서 다른 유저를 찾습니다."""
        queue = self.matching_queues[guild_id]
        queue.append(user_id)
        
        try:
            for _ in range(60):  # 60초 동안 1초마다 확인
                await asyncio.sleep(1)
                # 큐에 나 말고 다른 유저가 있다면 매칭 성공!
                opponents = [uid for uid in queue if uid != user_id]
                if opponents:
                    opponent_id = opponents[0]
                    # 매칭되었으니 큐에서 두 명 모두 제거
                    if user_id in queue: queue.remove(user_id)
                    if opponent_id in queue: queue.remove(opponent_id)
                    return opponent_id
            return None  # 60초 초과 시 None 반환
        finally:
            # 에러가 나거나 취소되었을 때 큐에서 확실히 제거
            if user_id in queue:
                queue.remove(user_id)

    def check_and_reset_daily_quest(self, pet) -> None:
        """한국 시간 기준으로 날짜가 바뀌었다면 일일 퀘스트 카운터를 초기화합니다."""
        if not pet:
            return
            
        # 한국 시간(KST) 기준 오늘 날짜 생성
        today = time.strftime('%Y-%m-%d', time.localtime(time.time() + 32400))
        
        # 펫 객체에 마지막 퀘스트 체크 날짜 저장용 변수가 없거나 날짜가 다르다면 초기화
        last_check = getattr(pet, 'last_quest_check_date', None)
        if last_check != today:
            pet.train_count_today = 0
            pet.stroke_count_today = 0
            pet.last_quest_check_date = today

    @app_commands.command(name="키우기", description="첫 펫을 입양하고 알을 지급받습니다. (최대 3마리 제한)")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
    @app_commands.default_permissions(administrator=True)
    async def start_game(self, interaction: discord.Interaction, 펫이름: str): 
        # 명령어 핸들러 내부
        types = ["불", "물", "풀", "전기", "비행", "땅", "얼음", "어둠", "독", "에스퍼", "노말"]
        weights = [5, 5, 5, 5, 5, 5, 5, 5, 5, 5, 50]
        selected_type = random.choices(types, weights=weights, k=1)[0]
        new_pet = Pet(name=펫이름, main_type=selected_type) # 랜덤 속성 펫 완성!
        
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
            # 💡 중복 생성 코드 삭제 완료
            self.save_user_pet(guild_id, user_id, new_pet)
            await interaction.response.send_message(f"🎉 첫 번째 동행 파트너 지정 완료! ???의 알 **[{펫이름}]**이 메인 파트너로 즉시 활성화되었습니다! (현재 보유: {total_pets + 1}/3)")
        else:
            # 💡 중복 생성 코드 삭제 완료
            self.add_stored_pet(guild_id, user_id, new_pet)
            await interaction.response.send_message(f"📦 현재 메인 파트너 자리가 차 있습니다! 새로운 ???의 알 **[{펫이름}]**은(는) **🗃️ 펫 보관함**으로 안전하게 수령되었습니다! (현재 보유: {total_pets + 1}/3)")
            
    @app_commands.command(name="펫보관함", description="보관 중인 펫을 확인하고 메인 펫과 교체(스왑)합니다. (최대 3마리 보존)")
    @app_commands.checks.has_permissions(administrator=True) # 뾰로롱
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
            await interaction.response.send_message(embed=embed, ephemeral=False)
            return
            
        for idx, (db_id, p) in enumerate(stored):
            stage_icon = "🥚" if p.stage == "알" else "🐾"
            embed.add_field(name=f"{idx+1}. {stage_icon} {p.name}", value=f"[{p.rarity}] Lv.{p.level} {p.main_type} (고유번호: {db_id})", inline=False)
            
        view = StorageSwapView(self, user_id, guild_id, stored, active_pet)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
    
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
            await interaction.response.send_message(f"❌ 보호 중인 펫 중 이름이 **[{펫이름}]**인 아이를 찾을 수 없습니다. 다시 확인해 주세요.", ephemeral=False)
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
        await interaction.response.defer() 

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
                await interaction.followup.send("🚨 **경고:** 펫을 너무 오랫동안 굶주린 상태로 방치하여 펫이 야생으로 도망갔습니다...", ephemeral=False)
                return
            elif penalty == "SICK_TRIGGERED":
                # 텍스트 변경: 보유 자산의 30% 차감 안내
                await interaction.followup.send("🚨 **경고:** 청결도를 너무 오랜 시간 방치하여 펫이 병에 걸렸습니다! 동물 보호 위반 벌금으로 **보유 자산의 30%**가 강제 차감됩니다.", ephemeral=False)
            self.save_user_pet(guild_id, user_id, pet)

        data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
        embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
        for f in data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            
        total_p = self.get_total_pet_count(guild_id, user_id)
        embed.set_footer(text=f"🔑 총 보유 펫 공간: {total_p} / 3마리")
            
        # 🚨 마지막 출력도 followup.send()로 수정
        await interaction.followup.send(embed=embed, view=MainPetHubView(self, user_id, guild_id))

    @app_commands.command(name="펫관리", description="[관리자 전용] 특정 유저의 펫 능력치 및 성장 단계를 강제 조정합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        비밀번호="관리자 비밀번호를 입력하세요",
        대상자="펫 정보를 수정할 유저",
        변경항목="수정할 수치 또는 상태를 선택하세요",
        설정값="변경 대입할 수치를 입력하세요 (단계는 알, 새끼, 유년기, 성체, 최종 진화 중 입력)"
    )
    @app_commands.choices(변경항목=[
        app_commands.Choice(name="📈 레벨 설정 (1 ~ 100)", value="level"),
        app_commands.Choice(name="🧬 성장단계 강제 설정", value="stage"),
        app_commands.Choice(name="❤️ 친밀도 수치 조정 (0 ~ 300)", value="affinity"),
        app_commands.Choice(name="🧼 질병 상태 강제 완치", value="heal_sick"),
        app_commands.Choice(name="⚡ 에너지 완충 (100)", value="heal_energy"),
        app_commands.Choice(name="강제방생", value="release")
    ])
    async def admin_set_pet_status(self, interaction: discord.Interaction, 비밀번호: str, 대상자: discord.Member, 변경항목: str, 설정값: str = None):
        # 0. 비밀번호 검증 (변경하려면 아래 값을 수정하세요)
        correct_pw = "69697474"

        if 비밀번호 != correct_pw:
            return await interaction.response.send_message(
                "🔒 비밀번호가 틀렸습니다. 명령어 사용이 거부되었습니다.",
                ephemeral=True
            )

        user_id = str(대상자.id)
        guild_id = str(interaction.guild_id)
        
        pet = self.get_user_pet(guild_id, user_id)
        if not pet:
            return await interaction.response.send_message(f"❌ {대상자.display_name}님은 현재 동행 중인 펫이 없습니다.", ephemeral=True)
        
        # 1. 강제방생 처리
        if 변경항목 == "release":
            success = await self.force_release_pet(interaction.guild_id, 대상자.id)
            if success:
                await interaction.response.send_message(f"✅ 관리자 권한으로 {대상자.mention}님의 펫을 **강제 방생**했습니다.", ephemeral=True)
            else:
                await interaction.response.send_message(f"❌ {대상자.display_name}님은 현재 보유 중인 펫이 없습니다.", ephemeral=True)
            return
        
        # 2. 설정값이 반드시 필요한 항목들 예외 처리
        if 변경항목 in ["level", "stage", "affinity"] and 설정값 is None:
            return await interaction.response.send_message("❌ 해당 항목은 `설정값`을 반드시 입력해야 합니다.", ephemeral=True)
        
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

        # 3. 변경된 펫 정보 저장 및 결과 전송
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
            
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            return False
        return True

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
        
        await interaction.response.send_message(f"🔄 성공적으로 **{target_pet.name}**(으)로 스왑(교체) 되었습니다! `/보호자` 명령어를 확인하세요.", ephemeral=False)

class MatchingCancelView(discord.ui.View):
    def __init__(self, cancel_callback):
        super().__init__(timeout=60)
        self.cancel_callback = cancel_callback

    @discord.ui.button(label="매칭 취소", style=discord.ButtonStyle.danger)
    async def btn_cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.cancel_callback(interaction)
        self.stop() # 뷰 비활성화

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
            
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            return False
        return True

    async def handle_click(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        # 1. 패널티 및 방치 상태 확인 (가장 먼저 실행)
        if pet:
            penalty = self.cog.check_penalties_and_update(self.guild_id, self.user_id, pet)
            if penalty == "RUNAWAY":
                return await interaction.response.send_message("🚨 펫이 오랫동안 방치되어 야생으로 도망갔습니다.", ephemeral=False)
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
            
        from pet_skill import DiscordUIFormatter
        
        if custom_id == "hub_펫":
            if not pet:
                return await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)
            
            # ✅ [정상 작동] 여기서 버튼에 대한 "첫 번째 응답"을 보냅니다.
            await interaction.response.edit_message(content="🔍 펫 정보를 불러오는 중...", embed=None, view=None)
            
            # 데이터 불러오기
            pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
            embed = discord.Embed(title=pet_data.get("title", "펫 정보"), description=pet_data.get("description", ""), color=0x2ecc71)
            
            image_url = pet_data.get("image_url")
            if pet.stage == "알" and not image_url:
                image_url = "https://i.imgur.com/알_이미지_주소.png" 
                pet_data["image_url"] = image_url 
            #

            # ✅ [KeyError 방지] 알 단계를 위해 안전하게 필드를 구성합니다.
            for f in pet_data.get("fields", []):
                name = f.get("name", "알 수 없음")
                value = f.get("value", "데이터 없음")
                inline = f.get("inline", False)
                embed.add_field(name=name, value=value, inline=inline)
            
            pet_image_url = pet_data.get("image_url")
            if pet_image_url:
                try:
                    embed.set_thumbnail(url=pet_image_url)
                except Exception as e:
                    print(f"이미지 로딩 실패, 무시함: {e}")
    
            await interaction.followup.send(embed=embed, view=PetInfoSubView(self.cog, self.user_id, self.guild_id))

        elif custom_id == "hub_상점":
            # 1. 상점 로직 처리
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            
            # 최상급 열매 가격 호출
            fruit_top_price = 50000
            if os.path.exists("data/pet_config.json"):
                try:
                    with open("data/pet_config.json", "r", encoding="utf-8") as f:
                        cfg = json.load(f)
                        fruit_top_price = cfg.get("fruit_high_price", 50000)
                except Exception: 
                    pass

            embed = discord.Embed(
                title="🛒 펫 상점", 
                description=f"아이템을 구매하세요!\n보유 자산: **{user_data.get('cash', 0):,}원**", 
                color=0xf1c40f
            )
            embed.add_field(name="🍎 열매 (포만감 회복)", value=f"- 최상급 열매 (포만감 +30): {fruit_top_price:,}원\n- 중급 열매 (포만감 +15): 30,000원\n- 하급 열매 (포만감 +5): 10,000원", inline=False)
            embed.add_field(name="🛡️ 일반 장비", value="- 머리/견갑/허리/다리 각 부위: 150,000원\n- 기본 스탯: HP +5, ATK +5, SPD +5", inline=False)

            # 상점 화면으로 즉시 전환 (응답을 한 번만 사용하여 에러 방지)
            await interaction.response.edit_message(content=None, embed=embed, view=ShopView(self.cog, self.user_id, self.guild_id))

        elif custom_id == "hub_가방":
            # 1. 가방 로직 처리
            fruits = pet.inventory.get("열매", {})
            equips = pet.inventory.get("장비", [])
            
            embed = discord.Embed(title="🎒 내 가방", description="보유 중인 아이템 목록입니다.", color=0x9b59b6)
            embed.add_field(name="🍎 열매", value=f"- 최상급 열매: {fruits.get('상', 0)}개\n- 중급 열매: {fruits.get('중', 0)}개\n- 하급 열매: {fruits.get('하', 0)}개", inline=False)
            
            eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
            embed.add_field(name="🛡️ 장비", value=eq_list, inline=False)
            
            # 가방 화면으로 즉시 전환
            await interaction.response.edit_message(content=None, embed=embed, view=InventoryView(self.cog, self.user_id, self.guild_id))

        elif custom_id == "hub_퀘스트":
            from pet_views import QuestView
            # 퀘스트 안내 임베드 생성
            embed = discord.Embed(
                title="📜 일일 퀘스트 센터", 
                description="매일 갱신되는 미션을 확인하고 달성하여 보상을 획득하세요.", 
                color=0x3498db
            )
            await interaction.response.edit_message(
                embed=embed, 
                view=QuestView(self.cog, self.user_id, self.guild_id)
            )

        elif custom_id == "hub_설정":
            from pet_views import SettingView
            embed = discord.Embed(
                title="⚙️ 설정 센터", 
                description="기기 설정 및 진화 방지 락 등을 관리합니다.", 
                color=0x95a5a6
            )
            await interaction.response.edit_message(
                embed=embed, 
                view=SettingView(self.cog, self.user_id, self.guild_id)
            )
            
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
            
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            return False
        return True

    async def handle_click(self, interaction: discord.Interaction):
        custom_id = interaction.data["custom_id"]
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        if pet:
            penalty = self.cog.check_penalties_and_update(self.guild_id, self.user_id, pet)
            if penalty == "RUNAWAY":
                await interaction.response.send_message("🚨 펫이 야생으로 도망갔습니다.", ephemeral=False)
                return
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
            # (여기에 있던 중복 응답 및 빈 메시지 전송 로직 삭제)

        if custom_id == "pet_처음으로":
            # 1. 즉시 응답: 로딩 중임을 알리고 기존 뷰를 해제합니다.
            await interaction.response.edit_message(content="🏠 메인 화면으로 돌아가는 중...", embed=None, view=None)
            
            # 2. 로직 처리: 데이터 조회 및 메인 화면 구성
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            
            # 3. 후속 전송 (Followup): 메인 허브 뷰 전송
            try:
                await interaction.followup.send(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception as e:
                print(f"메인 화면 복귀 실패: {e}")

        elif custom_id == "pet_장비":
            # 1. 즉시 응답: 로딩 메시지
            await interaction.response.edit_message(content="🎒 장비 및 가방을 불러오는 중...", embed=None, view=None)
            
            # 2. 데이터 처리
            fruits = pet.inventory.get("열매", {})
            equips = pet.inventory.get("장비", [])
            embed = discord.Embed(title="🎒 장비 및 가방", description="장비를 장착하거나 아이템을 사용하세요.", color=0x9b59b6)
            embed.add_field(name="🍎 열매", value=f"- 최상급: {fruits.get('상', 0)}개 | 중급: {fruits.get('중', 0)}개 | 하급: {fruits.get('하', 0)}개", inline=False)
            eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
            embed.add_field(name="🛡️ 보유 장비", value=eq_list, inline=False)
            
            # 3. 후속 전송
            await interaction.followup.send(embed=embed, view=InventoryView(self.cog, self.user_id, self.guild_id))

        elif custom_id == "pet_행동":
            # 1. 즉시 응답
            await interaction.response.edit_message(content="🎭 행동 목록을 불러오는 중...", embed=None, view=None)
            
            # 2. 로직 처리
            embed = discord.Embed(title=f"🎭 {pet.name} 행동 목록", description="행동할 상호작용 버튼을 선택하세요.")
            
            # 3. 인자 수정: action_name을 None으로 전달 (목록만 보여줄 때)
            await interaction.followup.send(
                embed=embed, 
                view=PetActionExecutionView(self.cog, self.user_id, self.guild_id, pet, action_name=None)
            )

        elif custom_id == "pet_스킬":
            # 1. 즉시 응답
            await interaction.response.edit_message(content="✨ 스킬 관리창을 불러오는 중...", embed=None, view=None)
            
            # 2. 후속 전송
            from pet_views import SkillManageView
            await interaction.followup.send(view=SkillManageView(self.cog, self.user_id, self.guild_id))
        
        elif custom_id == "pet_진화":
            # 1. 즉시 응답
            await interaction.response.edit_message(content="🆙 진화 불러오는 중...", embed=None, view=None)
            
            # 2. 후속 전송
            from pet_views import EvolutionView
            
            # ✅ response.send 대신 followup.send로 변경해야 합니다!
            await interaction.followup.send(view=EvolutionView(self.cog, self.user_id, self.guild_id))

        # 기존 뷰의 handle_click 등 내부에서 호출할 때
        elif custom_id == "pet_교배소":
            await interaction.response.edit_message(content="💞 교배소로 이동 중...", embed=None, view=None)
            from pet_views import BreedingView
    
            embed = discord.Embed(title="💞 신비섬 교배소", description="300,000 골드를 지불하고 최종 진화 펫을 교배시켜 강력한 알을 얻습니다.", color=0xff9ff3)
            await interaction.followup.send(embed=embed, view=BreedingView(self.cog, self.user_id, self.guild_id))

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
        # 0. 중복 응답 방지
        if interaction.response.is_done():
            return
        
        custom_id = interaction.data["custom_id"]
        _, item_type, item_name = custom_id.split("_")

        act_name = "상점 거래"

        if item_type == "back":
            # 1. 즉시 응답: 메인 화면으로 돌아가는 중임을 표시
            await interaction.response.edit_message(content="🏠 메인 화면으로 돌아가는 중...", embed=None, view=None)
        
        # 2. 로직 처리: 데이터 조회
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            pet = self.cog.get_user_pet(self.guild_id, self.user_id)
            
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        
        # 3. 후속 전송 (Followup): 메인 화면 전송
            try:
                await interaction.followup.send(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception as e:
                print(f"메인 화면 복귀 실패: {e}")
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
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)

        embed = discord.Embed(title=f"명령: {act_name}", description=msg, color=0x2ecc71)
        for f in pet_data.get("fields", []):
            embed.add_field(
                name=f.get("name", "\u200b"), 
                value=f.get("value", "데이터 없음"), 
                inline=f.get("inline", False)
            )

        await interaction.response.edit_message(content=f"✅ {msg}", embed=embed, view=self)
        
        # 3. 펫 상태창 필드 추가
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        
        # 4. 이미지 처리
        pet_image_url = pet_data.get("image_url")
        if pet_image_url:
            embed.set_thumbnail(url=pet_image_url)
        
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

        embed = discord.Embed(
                title="🛒 펫 상점", 
                description=f"아이템을 구매하세요!\n보유 자산: **{user_data.get('cash', 0):,}원**", 
                color=0xf1c40f
            )
        embed.add_field(name="🍎 열매 (포만감 회복)", value=f"- 최상급 열매 (포만감 +30): {fruit_top_price:,}원\n- 중급 열매 (포만감 +15): 30,000원\n- 하급 열매 (포만감 +5): 10,000원", inline=False)
        embed.add_field(name="🛡️ 일반 장비", value="- 머리/견갑/허리/다리 각 부위: 150,000원\n- 기본 스탯: HP +5, ATK +5, SPD +5", inline=False)

        # 3. 후속 전송 (Followup): 완성된 상점 페이지 전송
        try:
            await interaction.followup.send(embed=embed, view=ShopView(self.cog, self.user_id, self.guild_id))
        except Exception as e:
            print(f"상점 페이지 전송 실패: {e}")

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
        if interaction.response.is_done(): return
        
        custom_id = interaction.data["custom_id"]
        _, action, item_name = custom_id.split("_")
        
        if action == "back":
            # 1. 즉시 응답: 메인 화면 복귀 알림
            await interaction.response.edit_message(content="🏠 메인 화면으로 돌아가는 중...", embed=None, view=None)
            
            # 2. 데이터 처리
            db = self.cog._get_db(int(self.guild_id))
            user_data = db.get_user(self.user_id)
            pet = self.cog.get_user_pet(self.guild_id, self.user_id)
            data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
            
            # 3. 후속 전송
            embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
            for f in data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
            
            await interaction.followup.send(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
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
                await interaction.response.send_message(f"❌ 장착할 {item_name} 부위 장비가 가방에 없습니다.", ephemeral=False)
                return
            
            grade_val = {"일반": 1, "희귀": 2, "영웅": 3, "전설": 4}
            part_equips.sort(key=lambda x: grade_val.get(x["등급"], 0), reverse=True)
            best_equip = part_equips[0]
            
            current_equip = pet.equipment.get(item_name)
            if current_equip == best_equip["등급"]:
                await interaction.response.send_message(f"❌ 이미 {best_equip['등급']} 등급 장비를 장착 중입니다.", ephemeral=False)
                return
                
            pet.equipment[item_name] = best_equip["등급"]
            msg = f"🛡️ {best_equip['등급']} 등급 {item_name} 장비를 장착했습니다!"
            
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        
        await interaction.response.edit_message(content=f"✅ {msg}", embed=None, view=None)
        
        # 2. 로직 처리 (펫 데이터 및 가방 상태 갱신)
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        fruits = pet.inventory.get("열매", {})
        equips = pet.inventory.get("장비", [])
        
        # 3. 후속 전송 (Followup)
        embed = discord.Embed(title="🎒 내 가방", description="보유 중인 아이템 목록입니다.", color=0x9b59b6)
        embed.add_field(name="🍎 열매", value=f"- 최상급: {fruits.get('상', 0)}개...", inline=False)
        eq_list = ", ".join([f"{e['등급']} {e['부위']}" for e in equips]) if equips else "보유 장비 없음"
        embed.add_field(name="🛡️ 장비", value=eq_list, inline=False)
        
        try:
            await interaction.followup.send(embed=embed, view=self)
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
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            await interaction.response.send_message("❌ 펫 정보를 불러올 수 없습니다.", ephemeral=True)
            return
            
        old_name = pet.name
        pet.name = self.new_name.value
        pet.name_changed = True
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        # 1. 즉시 응답: 모달 제출 완료 알림 (기존 UI 수정 대신)
        await interaction.response.send_message(f"✨ 이름 변경 완료: `{old_name}` -> `{pet.name}`", ephemeral=False)

        # 2. 상태창 Followup: 펫 정보 갱신 (기존 메시지를 수정해야 할 경우)
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
        for f in pet_data["fields"]:
            embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
        try:
            # 모달이 실행된 메시지 자체를 수정하고 싶다면 followup을 사용하세요.
            await interaction.followup.edit_message(message_id=interaction.message.id, embed=embed, view=self)
        except Exception as e:
            print(f"UI 갱신 오류: {e}")

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

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            return False
        return True

    async def handle_skill(self, interaction: discord.Interaction):
        skill_name = interaction.data["custom_id"].split("_")[1]
        await self.process_turn(interaction, skill_name)

    async def process_turn(self, interaction: discord.Interaction, player_action=None):
        result = self.battle.execute_turn(player_action)
        
        log_text = "\n".join(self.battle.log[-12:])
        embed = discord.Embed(title="⚔️ PvP 배틀 진행 중!", description=log_text, color=0xe74c3c)
        embed.add_field(name=f"🟢 {self.battle.pet_a.name} (나)", value=f"HP: {max(0, self.battle.hp_a)}/{self.battle.max_hp_a}\nMP: {max(0, self.battle.mp_a)}/{self.battle.pet_a.max_mp}")
        embed.add_field(name=f"🔴 {self.battle.pet_b.name} (적)", value=f"HP: {max(0, self.battle.hp_b)}/{self.battle.max_hp_b}\nMP: {max(0, self.battle.mp_b)}/{self.battle.pet_b.max_mp}")
        
        # 1. 전투가 아직 진행 중이라면 메시지만 갱신하고 턴 유지
        if result is None:
            await interaction.response.edit_message(embed=embed, view=self)
            return
            
        # 2. 여기서부터는 승패가 났을 때(전투 종료) 로직
        self.stop()
        is_ranked = getattr(self.battle, 'is_ranked', False)
        db = self.cog._get_db(int(self.guild_id))
        
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if pet:
            pet.pvp_count = getattr(pet, 'pvp_count', 0) + 1
            
            # 랭크전 점수 처리
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
            
            # 펫 정보 업데이트
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)

            # 랭크 점수 DB 업데이트
            if is_ranked:
                try:
                    db.execute_query("UPDATE users SET pet_rank_score = ? WHERE user_id = ? AND guild_id = ?", (rank_score, self.user_id, self.guild_id), 'none')
                except Exception as e:
                    print(f"랭크 점수 업데이트 실패: {e}")

            # 최종 상태창 표시 데이터 덧붙이기
            from pet_skill import DiscordUIFormatter
            pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
            for f in pet_data["fields"]:
                embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        # 전투 종료 화면 출력 후 메인 허브로 복귀버튼 활성화
        try:
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            else:
                await interaction.followup.send(embed=embed, view=MainPetHubView(self.cog, self.user_id, self.guild_id))
        except Exception as e:
            print(f"최종 UI 전환 오류: {e}")

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
                
                # 1. 결과값 받기
                result_code, message = pet.try_learn_skill()
                
                # 2. 메시지 보완
                embed.add_field(name="결과", value="🎉 승리하여 경험치 200과 전적을 획득했습니다!", inline=False)
                
                if result_code == "CHOICE_NEEDED":
                    new_skill = message
                    from pet_views import SkillSelectionView
                    # 타임아웃 시에는 interaction이 없으므로 채널로 메시지 전송
                    await self.message.channel.send(
                        f"✨ {new_skill}을(를) 배웠지만 슬롯이 꽉 찼습니다! 어떤 스킬을 잊으시겠습니까?",
                        view=SkillSelectionView(self.cog, self.user_id, self.guild_id, new_skill)
                    )
                else:
                    embed.add_field(name="스킬 습득", value=message, inline=False)

            elif result == "DRAW":
                pet.gain_exp(50)
                embed.add_field(name="결과", value="🤝 무승부! 약간의 경험치를 획득했습니다.", inline=False)
            else:
                embed.add_field(name="결과", value="💀 패배했습니다. 다음 기회를 노리세요!", inline=False)
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)

            pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
            pet_info_embed = discord.Embed(title=pet_data["title"], description=pet_data["description"], color=0x2ecc71)
            for f in pet_data["fields"]:
                pet_info_embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])

        if self.message:
            try:
                # 두 개의 임베드를 리스트로 전달
                await self.message.edit(embeds=[embed, pet_info_embed], attachments=[], view=MainPetHubView(self.cog, self.user_id, self.guild_id))
            except Exception as e:
                print(f"타임아웃 UI 갱신 실패: {e}")
        
class PetActionExecutionView(View):
    def __init__(self, cog: PetManager, user_id: str, guild_id: str, pet: Pet, action_name: Optional[str] = None):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.pet = pet
        self.action_name = action_name
        
        if self.action_name is None:
            actions = self.pet.get_available_actions()
        else:
            actions = [self.action_name]
        
        for act in actions:
            btn = discord.ui.Button(
                label=act, 
                style=discord.ButtonStyle.success,
                custom_id=f"act_{act}"
            )
            btn.callback = self.handle_action
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if str(interaction.user.id) != str(self.user_id):
            await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            return False
        return True

    async def handle_action(self, interaction: discord.Interaction):
        from pet_skill import DiscordUIFormatter
        from pet_climate import ClimateManager
        import os
        import json
        import random
        
        act_name = interaction.data.get("custom_id", "").split("_")[1]
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        if not pet: 
            return await interaction.response.send_message("❌ 펫 없음", ephemeral=True)

        # 1. 모달(이름 변경)은 다른 화면 처리 전에 가장 먼저 호출
        if act_name == "이름 변경":
            return await interaction.response.send_modal(NameChangeModal(self.cog, self.user_id, self.guild_id))
        
        if act_name in ["먹이 주기", "먹이"] and pet.fullness >= 99:
            return await interaction.response.send_message("❌ 이미 배가 꽉 차 있습니다!", ephemeral=False)
        
        if act_name == "청소하기" and pet.cleanliness >= 99:
            return await interaction.response.send_message("❌ 이미 주변이 아주 깨끗합니다!", ephemeral=False)
        
        if act_name == "쓰다듬기" and pet.affinity >= 297: # 친밀도 300 상한
            return await interaction.response.send_message("❌ 이미 충분히 친밀해요!", ephemeral=False)

        if act_name == "벌레잡기" and pet.affinity >= 297:
            return await interaction.response.send_message("❌ 이미 충분히 친밀해요!", ephemeral=False)
        
        # 2. 통과했다면 로딩 처리 (버튼 누른 직후 로딩 표시)
        if not interaction.response.is_done():
            await interaction.response.edit_message(content="⏳ 행동 처리 중...", embed=None, view=None)

        msg = "" # 결과 대사가 들어갈 빈 변수 준비

        climate = ClimateManager().get_current_climate()
        penalty = self.cog.check_penalties_and_update(self.guild_id, self.user_id, pet)
        if penalty == "RUNAWAY":
            return await interaction.followup.send("🚨 펫이 굶주림 방치로 인해 야생으로 도망갔습니다.", ephemeral=False)
            
        # 기분 최악일 때 행동 거부 로직
        if pet.mood_state == "화남" and act_name not in ["PvP", "랭크전"]:
            refusal_chance = 0.3
            if pet.affinity_rank == "균형": refusal_chance -= 0.10
            if random.random() < refusal_chance:
                return await interaction.followup.send(f"💢 {pet.name}이(가) 기분이 최악이라 명령을 거부했습니다! 놀아주거나 산책을 일찍 시켜주세요.", ephemeral=False)

        # 기후 패널티
        energy_penalty_msg = ""
        if climate.weather == "한파" and pet.stage != "알" and act_name not in ["재우기", "휴식", "먹이 주기", "먹이", "간식 주기"]:
            pet.energy = max(0, pet.energy - 10)
            energy_penalty_msg = "\n❄️ [한파] 너무 추운 날씨로 인해 행동 시 에너지가 추가로 소모되었습니다."
                        
        # 4. PvP / 랭크전 로직 (배틀 뷰로 넘어가므로 처리 후 return)
        if act_name in ["PvP", "랭크전"]:
            if act_name == "PvP":
                if pet.mood_state == "화남":
                    return await interaction.followup.send(f"❌ {pet.name}이(가) 기분이 최악이라 배틀에 참가할 수 없습니다!", ephemeral=False)
                
                types = ["불", "물", "풀", "전기", "비행", "땅", "얼음", "어둠", "독", "에스퍼", "노말"]
                wild_pet = Pet("야생의 펫", random.choice(types))
                wild_pet.level = max(1, pet.level + random.randint(-2, 2))
                wild_pet.stage = "성체"
                wild_pet.attack = 10 + int(wild_pet.level * 2.5)
                wild_pet.defense = 10 + int(wild_pet.level * 2.5)
                wild_pet.speed = 10 + int(wild_pet.level * 2.5)
                wild_pet._max_mp = 50 + int(wild_pet.level * 5)
                wild_pet.skills = ["몸통박치기", "깨물기"]
                
                from pet_skill import PvPBattle
                battle = PvPBattle(pet, wild_pet)
                battle.is_ranked = False
                battle.log.append(f"⚔️ **배틀 시작!** {pet.name} VS {wild_pet.name}")
                
                embed = discord.Embed(
                    title="⚔️ 일반 친선전 시작!", 
                    description=f"{pet.name} 님이 {wild_pet.name}을(를) 만났습니다!\n3초 이내에 스킬을 선택하세요!", 
                    color=0xe74c3c
                )
                
                battle_view = PvPInteractiveView(self.cog, self.user_id, self.guild_id, battle)
                msg_obj = await interaction.edit_original_response(content=None, embed=embed, view=battle_view)
                battle_view.message = msg_obj
                return
            
            elif act_name == "랭크전":
                if pet.mood_state == "화남":
                    return await interaction.followup.send(f"❌ {pet.name}이(가) 기분이 최악이라 배틀에 참가할 수 없습니다!", ephemeral=False)

                await self.match_opponent(interaction, "랭크전")
                return
            
        if act_name == "교배":
            await interaction.edit_original_response(content="💞 교배소로 이동 중...", embed=None, view=None)
            from pet_views import BreedingView
            embed = discord.Embed(title="💞 신비섬 교배소", description="300,000 골드를 지불하고 최종 진화 펫을 교배시켜 강력한 알을 얻습니다.", color=0xff9ff3)
            return await interaction.followup.send(embed=embed, view=BreedingView(self.cog, self.user_id, self.guild_id))
            
        # 5. 일반 행동 수행 로직
        if pet.stage == "알":
            msg = pet.interact_egg(act_name)
        elif act_name in ["먹이 주기", "먹이"]:
            fruits = pet.inventory.get("열매", {})
            used_fruit = None
            heal_amount = 0
            pet.fullness = min(100, pet.fullness + 30)
            pet.stress = max(0, pet.stress - 10)
            # 하급 -> 중급 -> 최상급 순으로 소모
            if fruits.get("하", 0) > 0:
                used_fruit = "하"
                heal_amount = 5
            elif fruits.get("중", 0) > 0:
                used_fruit = "중"
                heal_amount = 15
            elif fruits.get("상", 0) > 0:
                used_fruit = "상"
                heal_amount = 30

            if not used_fruit:
                msg = "❌ 가방에 열매가 하나도 없습니다! [상점]에서 열매를 구매하거나 [가방]에서 사용해주세요."
            else:
                pet.inventory["열매"][used_fruit] -= 1  # 아이템 차감!
                pet.fullness = min(100, pet.fullness + heal_amount)
                pet.stress = max(0, pet.stress - 10)
                
                if climate.weather == "폭염":
                    pet.fullness = max(0, pet.fullness - 15)
                    msg = f"🍖 [{used_fruit}급 열매]를 먹였습니다. (포만감: {int(pet.fullness)}/100, 스트레스: {pet.stress}/100)\n🔥 [폭염] 더위로 인해 포만감이 빠르게 줄어듭니다."
                else:
                    msg = f"🍖 [{used_fruit}급 열매]를 1개 소모하여 먹이를 주었습니다. 포만감: {int(pet.fullness)}/100, 스트레스: {pet.stress}/100"
        
        elif act_name == "간식 주기":
            if getattr(pet, 'snack_count_today', 0) >= 1:
                msg = "❌ 사탕은 하루에 한 번만 줄 수 있습니다! 너무 많이 먹으면 건강에 안 좋아요."
            else:
                pet.snack_count_today = getattr(pet, 'snack_count_today', 0) + 1
                pet.affinity = min(300, pet.affinity + 20)
                pet.fullness = min(100, pet.fullness + 10)
                msg = f"🍬 달콤한 사탕을 주었습니다! {pet.name}이(가) 무척 행복해하며 당신을 따릅니다. (친밀도 대폭 상승)"

        elif act_name == "쓰다듬기":
            if getattr(pet, "pet_count_today", 0) >= 5:
                msg = "❌ 쓰다듬기는 하루에 다섯 번만 가능합니다!"
            else:
                pet.pet_count_today += 1
                pet.affinity = min(300, pet.affinity + 15)
                msg = "👋 정성스레 쓰다듬었습니다."
        elif act_name == "청소하기":
            pet.cleanliness = min(100, pet.cleanliness + 50)
            msg = "🧼 깨끗이 청소했습니다!"
        elif act_name in ["놀아주기", "장난감"]:
            pet.mood_score = min(100, pet.mood_score + 25)
            exp_result = pet.gain_exp(40)
            msg = f"🧸 장난감을 활용해 신나게 놀아주었습니다! 기분이 대폭 상승합니다.\n{exp_result}"
        elif act_name in ["재우기", "휴식"]:
            if getattr(pet, 'sleep_count_today', 0) >= 5:
                msg = f"❌ [{act_name}] 행동은 하루에 다섯 번만 가능합니다! 너무 많이 자면 밤에 잠을 못 자요. 내일 다시 시도하세요."
            else:
                pet.sleep_count_today = getattr(pet, 'sleep_count_today', 0) + 1
                # 👇 아래 줄부터 모두 else 안쪽으로 들여쓰기 되어야 합니다!
                heal_amount = 100 if getattr(pet, 'personality', None) == "나태" else 50
                pet.energy = min(100, pet.energy + heal_amount)
                pet.stress = max(0, pet.stress - 20)
                msg = f"💤 푹 쉬면서 편안하게 재웠습니다. (에너지: {int(pet.energy)}/100, 스트레스: {pet.stress}/100)"
                if getattr(pet, 'personality', None) == "나태":
                    msg += "\n🦥 [나태] 성격 덕분에 휴식 효율이 2배가 되었습니다!"
        elif act_name == "벌레잡기":
            if getattr(pet, "bug_count_today", 0) >= 3:
                msg = "❌ 벌레잡기는 하루에 세 번만 가능합니다!"
            else:
                pet.bug_count_today += 1
                pet.affinity = min(300, pet.affinity + 5)
                exp_result = pet.gain_exp(15)
                msg = f"🐛 펫과 힘을 합쳐 풀밭의 벌레를 잡았습니다!\n{exp_result}"
        elif act_name == "산책":
            pet.mood_score = min(100, pet.mood_score + 15)
            pet.affinity = min(300, pet.affinity + 10)
            exp_result = pet.gain_exp(20)
            msg = f"🌳 맑은 공기를 쐬며 산책을 다녀왔습니다.\n{exp_result}"
        elif act_name == "훈련":
            if pet.train_count_today >= 3:
                msg = "❌ 오늘 훈련할 수 있는 최대 횟수(3회)를 초과했습니다! 내일 다시 시도하세요."
            else:
                pet.train_count += 1
                pet.train_count_today += 1
                pet.stress = min(100, pet.stress + 15)
                exp_result = pet.gain_exp(60)
                
                # 📌 꼬여있던 부분 정리: 바로 메시지와 튜플을 받아냅니다.
                msg = f"🏋️ 집중 훈련을 단행했습니다! (오늘 훈련: {pet.train_count_today}/3)\n{exp_result}"
                result_code, message = pet.try_learn_skill()
                
                # 2. 결과에 따른 처리
                if result_code == "CHOICE_NEEDED":
                    new_skill = message
                    from pet_views import SkillSelectionView 
                    await interaction.followup.send(
                        f"✨ {new_skill}을(를) 배웠지만 슬롯이 꽉 찼습니다! 어떤 스킬을 잊으시겠습니까?",
                        view=SkillSelectionView(self.cog, self.user_id, self.guild_id, new_skill)
                    )
                else:
                    await interaction.followup.send(message)

                if pet.stage in ["성체", "최종 진화"] and random.random() < 0.20:
                    pot_gain = random.randint(1, 3)
                    pet.potential = min(100, getattr(pet, 'potential', 0) + pot_gain)
                    msg += f"\n✨ **[대성공!]** 훈련 중 한계를 돌파하여 잠재력이 {pot_gain} 상승했습니다! (현재: {pet.potential}%)"

        elif act_name == "탐험":
            # 1. 🚫 제한 사항 체크 (에너지 & 하루 탐험 횟수)
            if pet.energy < 20:
                return await interaction.followup.send("❌ 에너지가 부족하여 탐험을 떠날 수 없습니다. (필요 에너지: 20)", ephemeral=True)
        
            if pet.explore_count_today >= 3:
                return await interaction.followup.send("❌ 오늘 모험을 떠날 수 있는 최대 횟수(3회)를 초과했습니다! 내일 다시 시도하세요.", ephemeral=True)
    
            # 2. ⚡ 기본 자원 소모 및 수치 조정
            pet.energy -= 20
            pet.explore_count += 1
            pet.explore_count_today += 1
            pet.stress = min(100, pet.stress + 15)

            # 3. 📈 경험치 계산 (날씨, 계절, 호감도 버프 반영)
            base_exp = 100
            if pet.affinity_rank == "신뢰":
                base_exp = int(base_exp * 1.1)
        
            if climate.weather == "맑음":
                base_exp = int(base_exp * 1.05)
            if climate.season == "가을":
                base_exp = int(base_exp * 1.1)

            exp_result = pet.gain_exp(base_exp)

            msg = f"🗺️ **{pet.name}**이(가) 외부 지역으로 탐험을 떠났습니다! (오늘 탐험: {pet.explore_count_today}/3)\n{exp_result}"
            
            # 버프 메시지 추가
            if pet.affinity_rank == "신뢰":
                msg += "\n🤝 [신뢰] 등급 혜택으로 탐험 보상이 10% 증가했습니다!"
            if climate.weather == "맑음":
                msg += "\n☀️ [맑음] 맑은 날씨 효과로 경험치를 5% 추가로 얻었습니다!"
            if climate.season == "가을":
                msg += "\n🍁 [가을] 가을 시즌 효과로 탐험 보상이 10% 증가했습니다!"
            if climate.weather == "강풍":
                msg += "\n💨 [강풍] 강풍을 타고 이동거리가 늘어나 탐험 보상을 더 많이 발견했습니다!"

            # 4. ⚔️ 성체/최종 진화 단계 펫 전용 추가 보상 (반지 제외 일반 장비)
            if pet.stage in ["성체", "최종 진화"]:
                if random.random() < 0.10:
                    pot_gain = random.randint(2, 5)
                    pet.potential = min(100, getattr(pet, 'potential', 0) + pot_gain)
                    msg += f"\n🌟 **[신비한 조우]** 탐험 중 신비한 기운을 흡수하여 잠재력이 {pot_gain} 상승했습니다! (현재: {pet.potential}%)"

                roll = random.random()
                drop_grade = None
                if roll < 0.01:
                    drop_grade = "전설"
                elif roll < 0.06:
                    drop_grade = "영웅"
                elif roll < 0.21:
                    drop_grade = "희귀"
                        
                if drop_grade:
                    part = random.choice(["머리", "견갑", "허리", "다리"])
                    pet.inventory["장비"].append({"부위": part, "등급": drop_grade})
                    msg += f"\n🎁 **[전리품 발견]** 탐험 중에 눈부신 빛을 내는 **[{drop_grade}]** 등급 {part} 장비를 발견했습니다! (가방 확인)"

                # 5. 🎲 돌발 이벤트 처리 (확률 및 날씨 반영)
                event_chance = 0.40
                if climate.weather == "흐림":
                    event_chance += 0.05
                if climate.weather == "안개":
                    event_chance += 0.10
                
                if random.random() < event_chance:
                    event_roll = random.random()
                    db = self.cog._get_db(int(self.guild_id))
                    
                if event_roll < 0.25: # 방랑 상인
                    fruit_grade = random.choice(["상", "중", "하"])
                    pet.inventory.setdefault("열매", {})
                    pet.inventory["열매"][fruit_grade] = pet.inventory["열매"].get(fruit_grade, 0) + 1
                    pet.affinity = min(300, pet.affinity + 10)
                    msg += f"\n\n🎒 **[방랑 상인 조우]** 숲속에서 길을 잃은 상인을 도와주고 **최고급 열매({fruit_grade})** 1개를 얻었습니다!"
            
                elif event_roll < 0.45: # 옹달샘
                    pet.energy = min(100, pet.energy + 50)
                    pet.mood_score = min(100, pet.mood_score + 30)
                    pet.cleanliness = 100
                    msg += "\n\n💧 **[요정의 옹달샘]** 맑고 신비로운 옹달샘에서 휴식하여 펫의 컨디션이 최상으로 회복되었습니다!"
            
                elif event_roll < 0.65: # 폭우
                    pet.cleanliness = max(0, pet.cleanliness - 40)
                    pet.stress = min(100, pet.stress + 20)
                    msg += "\n\n⛈️ **[변덕스러운 폭우]** 갑작스러운 폭우에 진흙탕을 구르며 펫의 청결도가 깎이고 스트레스를 받았습니다..."
                    if random.random() < 0.15:
                        pet.inventory["장비"].append({"부위": "비옷", "등급": "희귀"})
                        msg += " (하지만 덤블 속에서 누군가 흘린 [비옷]을 주웠습니다!)"

                elif event_roll < 0.85: # 야생 맹수
                    pet.fullness = max(0, pet.fullness - 30)
                    extra_exp = pet.gain_exp(base_exp)
                    msg += f"\n\n🐺 **[야생 맹수의 습격]** 맹수에게서 도망치느라 포만감이 크게 줄었지만, 생존 본능이 자극되어 경험치를 두 배로 얻었습니다!\n{extra_exp}"

                else: # 🎁 보물 상자 ('변하지 않는 반지' 드롭!)
                    chest_roll = random.random()
                    drop_cut = 0.05  # 기본 5%
                    if os.path.exists("data/pet_config.json"):
                        try:
                            with open("data/pet_config.json", "r", encoding="utf-8") as f:
                                cfg = json.load(f)
                                drop_cut = cfg.get("ring_drop_rate", 0.05)
                        except Exception:
                            pass

                    msg += "\n\n🎁 **[신비한 보물 상자 발견!]** 수풀 속에서 고대의 상자를 발견했습니다!"
                    if chest_roll < drop_cut:
                        user_data = db.get_user(self.user_id)
                        if user_data:
                            user_inventory = user_data.get("inventory", [])
                            user_inventory.append("변하지 않는 반지")
                            user_data["inventory"] = user_inventory
                            db.save_user(self.user_id, user_data)
                        msg += " 안에서 **[변하지 않는 반지]**를 발견했습니다! (계정 가방으로 지급)"
                    else:
                        msg += " 하지만 합정 속에 아무것도 없었습니다..."

                # 6. 최종 데이터 저장 및 결과 전송
                self.cog.save_user_pet(self.guild_id, self.user_id, pet)
                return await interaction.followup.send(msg, ephemeral=False)

        elif act_name == "채집":
            pet.stress = min(100, pet.stress + 15)
            exp_result = pet.gain_exp(30)
            db = self.cog._get_db(interaction.guild.id)
            find_gold = random.randint(100, 300)
            db.add_user_cash(str(interaction.user.id), find_gold)
            msg = f"🌿 숲속을 채집하여 맛있는 먹이 원료와 **{find_gold:,}원**을 찾아냈습니다!\n{exp_result}"
            
        elif act_name == "간식 주기":
            if getattr(pet, 'snack_count_today', 0) >= 1:
                msg = "❌ 간식은 하루에 한 번만 줄 수 있습니다! 너무 많이 먹으면 건강에 안 좋아요."
            else:
                pet.snack_count_today = getattr(pet, 'snack_count_today', 0) + 1
                pet.affinity = min(300, pet.affinity + 20)
                pet.fullness = min(100, pet.fullness + 10)
                msg = f"🍬 달콤한 간식을 주었습니다! {pet.name}이(가) 무척 행복해하며 당신을 따릅니다. (친밀도 대폭 상승)"
        
        if "❌" not in msg:
            quest_key = None
            if act_name == "훈련": quest_key = "train"
            elif act_name == "쓰다듬기": quest_key = "stroke"
            elif act_name == "청소하기": quest_key = "clean"
            elif act_name in ["먹이 주기", "먹이"]: quest_key = "feed"

            if quest_key and hasattr(pet, 'daily_quests') and quest_key in pet.daily_quests:
                if pet.daily_quests[quest_key]["count"] < pet.daily_quests[quest_key]["target"]:
                    pet.daily_quests[quest_key]["count"] += 1

        # 6. 화면 최종 갱신 및 DB 저장 (들여쓰기 수정 완료 구역)
        if energy_penalty_msg:
            msg += energy_penalty_msg

        ult = pet.check_ultimate_skill()
        if ult:
            msg += f"\n\n🎉 **[각성]** {pet.name}이(가) 깊은 교감을 통해 전용 궁극기 `{ult}`을(를) 깨우쳤습니다!"
            
        # 1. DB 저장 (가장 먼저 안전하게 처리)
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        # 2. 임베드 만들기
        pet_data = DiscordUIFormatter.make_pet_embed_data(pet)
        
        # [결과 텍스트 + 펫 상태]가 합쳐진 최종 임베드 생성
        embed = discord.Embed(title=f"명령: {act_name}", description=msg, color=0x2ecc71)
        for f in pet_data.get("fields", []):
            embed.add_field(
                name=f.get("name", "\u200b"), 
                value=f.get("value", "데이터 없음"), 
                inline=f.get("inline", False)
            )
        
        if pet_data.get("image_url"):
            embed.set_thumbnail(url=pet_data["image_url"])

        # 3. 로딩 메시지를 이 완성된 임베드와 다음 버튼으로 덮어씌움
        await interaction.edit_original_response(
            content=None, 
            embed=embed, 
            view=PetActionExecutionView(self.cog, self.user_id, self.guild_id, pet, action_name=None)
        )
        
    async def match_opponent(self, interaction, battle_type):
        cancel_event = asyncio.Event()
        
        async def cancel_callback(cancel_interaction: discord.Interaction):
            cancel_event.set() 
            await cancel_interaction.response.edit_message(content="❌ 매칭이 취소되었습니다.", embed=None, view=None)

        # 1. 대기 화면 출력
        await interaction.edit_original_response(
            content=f"🔍 {battle_type} 상대를 찾는 중입니다... (최대 60초)", 
            embed=None, 
            view=MatchingCancelView(cancel_callback)
        )

        try:
            # 2. 대기열에서 매칭 찾기
            match_task = asyncio.create_task(self.cog.find_matching_user(self.guild_id, self.user_id))
            done, pending = await asyncio.wait(
                [match_task, asyncio.create_task(cancel_event.wait())],
                timeout=60.0,
                return_when=asyncio.FIRST_COMPLETED
            )
            
            if cancel_event.is_set():
                match_task.cancel()
                return # 취소됨

            if match_task in done:
                opponent_id = match_task.result()
                if not opponent_id:
                    raise asyncio.TimeoutError
                    
                # 3. 매칭 성공! 상대방 펫 정보 불러오기
                opponent_pet = self.cog.get_user_pet(self.guild_id, opponent_id)
                if not opponent_pet:
                    await interaction.followup.send("⚠️ 상대방의 펫 정보를 불러오지 못해 매칭이 취소되었습니다.")
                    return
                
                # 4. 실제 배틀 셋업
                from pet_skill import PvPBattle
                battle = PvPBattle(self.pet, opponent_pet)
                battle.is_ranked = True
                battle.log.append(f"⚔️ **랭크전 매칭 성공!** {self.pet.name} VS {opponent_pet.name}")
            
                embed = discord.Embed(
                    title="⚔️ 랭크전 시작!", 
                    description=f"상대 유저의 펫 **{opponent_pet.name}**을(를) 만났습니다!\n3초 이내에 스킬을 선택하세요!", 
                    color=0xe74c3c
                )

                battle_view = PvPInteractiveView(self.cog, self.user_id, self.guild_id, battle)
                msg_obj = await interaction.edit_original_response(content=None, embed=embed, view=battle_view)
                battle_view.message = msg_obj
                
            else:
                raise asyncio.TimeoutError
        
        except asyncio.TimeoutError:
            match_task.cancel() 
            await interaction.edit_original_response(
                content="⌛ 매칭 가능한 유저가 없어 랭크전이 자동으로 취소되었습니다. 나중에 다시 시도해 주세요.", 
                view=None
            )

async def setup(bot):
    await bot.add_cog(PetManager(bot))