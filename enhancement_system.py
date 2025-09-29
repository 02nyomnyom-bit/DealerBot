# enhancement_system.py - 순수 강화 시스템 (보상 없음, 기존 시스템 독립)\
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
import random
import json
import os
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional

# ✅ 통계 시스템만 안전하게 import (선택적)
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료 (강화시스템)")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (강화시스템 - 독립 모드)")
    
    # Mock stats manager (통계 없이도 작동)
    class MockStatsManager:
        @staticmethod
        def record_game_activity(user_id, username, game_name, **kwargs):
            pass
    
    stats_manager = MockStatsManager()

# ✅ 통계 기록 헬퍼 함수 (선택적)
def record_enhancement_attempt(user_id: str, username: str, is_success: bool):
    """강화 시도 통계 기록 (선택적)"""
    if STATS_AVAILABLE:
        try:
            stats_manager.record_game_activity(
                user_id=user_id,
                username=username,
                game_name="enhancement",
                is_win=is_success,
                attempts=1
            )
        except Exception as e:
            print(f"❌ 강화시스템 통계 기록 실패: {e}")

# ✅ 강화 시스템 설정
ENHANCEMENT_CONFIG = {
    "data_file": 'data/enhancement_data.json',
    "cooldown_time": 30,  # 강화 쿨다운 30초
    "max_level": 500,     # 최대 레벨
    "min_safe_level": 10, # 강등 방지 최소 레벨
    "level_change_range": (1, 10),  # 레벨 변동 범위
    "backup_interval": 50  # 50회마다 백업
}

# 데이터 디렉토리 생성
os.makedirs("data", exist_ok=True)

# ✅ 강화 확률 계산 함수들
def get_success_rate(level: int) -> float:
    """레벨에 따른 성공률 계산"""
    if level == 0:
        return 100.0
    
    # 레벨이 높을수록 성공률 감소
    max_level = 500
    min_rate = 0.5
    max_rate = 100.0
    
    # 2차 함수로 감소
    rate = max_rate * ((1 - level / max_level) ** 2)
    return max(rate, min_rate)

def get_downgrade_rate(level: int) -> float:
    """레벨에 따른 강등 확률 계산"""
    if level <= ENHANCEMENT_CONFIG["min_safe_level"]:
        return 0.0  # 안전구간에서는 강등 없음
    
    # 레벨이 높을수록 강등 확률 증가
    max_level = 500
    min_rate = 2.0
    max_rate = 40.0
    
    # 선형 증가
    rate = min_rate + (max_rate - min_rate) * (level / max_level)
    return min(rate, max_rate)

def get_level_tier_info(level: int) -> Dict:
    """레벨에 따른 등급 정보 반환"""
    if level <= 0:
        return {
            "name": "미강화",
            "color": 0x808080,
            "emoji": "⚪",
            "tier": "기본"
        }
    elif level <= 10:
        # 기본 등급
        tier_names = ["초급", "중급", "고급", "특급", "명품", "최고급", "프리미엄", "디럭스", "에이스", "신급"]
        return {
            "name": f"{tier_names[level-1]} {level}",
            "color": 0x00FF00,
            "emoji": "🟢",
            "tier": "기본"
        }
    elif level <= 50:
        # 마스터 등급
        return {
            "name": f"마스터 {level}",
            "color": 0x0080FF,
            "emoji": "🔵",
            "tier": "마스터"
        }
    elif level <= 100:
        # 헤로익 등급
        return {
            "name": f"헤로익 {level}",
            "color": 0x8000FF,
            "emoji": "🟣",
            "tier": "헤로익"
        }
    elif level <= 200:
        # 에픽 등급
        return {
            "name": f"에픽 {level}",
            "color": 0xFF8000,
            "emoji": "🟠",
            "tier": "에픽"
        }
    elif level <= 300:
        # 레어 등급
        return {
            "name": f"레어 {level}",
            "color": 0xFF0080,
            "emoji": "🔴",
            "tier": "레어"
        }
    elif level <= 400:
        # 유니크 등급
        return {
            "name": f"유니크 {level}",
            "color": 0x80FF00,
            "emoji": "🟡",
            "tier": "유니크"
        }
    elif level <= 450:
        # 미식 등급
        return {
            "name": f"미식 {level}",
            "color": 0xFF69B4,
            "emoji": "🍯",
            "tier": "미식"
        }
    elif level <= 499:
        # 초월 등급
        return {
            "name": f"초월 {level}",
            "color": 0x8A2BE2,
            "emoji": "🌌",
            "tier": "초월"
        }
    else:
        # 절대신 등급 (500레벨)
        return {
            "name": "절대신 500",
            "color": 0xFFFFFF,
            "emoji": "👑",
            "tier": "절대신"
        }

# ✅ 강화 데이터 관리 클래스 (완전 독립)
class EnhancementDataManager:
    def __init__(self):
        self.data_file = ENHANCEMENT_CONFIG["data_file"]
        self.data = self.load_data()
        self.backup_counter = 0

    def load_data(self) -> Dict:
        """데이터 로드 (안전성 강화)"""
        if os.path.exists(self.data_file):
            try:
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    
                    # ✅ 데이터 구조 검증 및 수정
                    if not isinstance(data, dict):
                        print("❌ enhancement_data가 dict가 아닙니다. 기본 구조로 초기화합니다.")
                        return self._create_default_data()
                    
                    # 기본 구조 보장
                    if "items" not in data or not isinstance(data["items"], dict):
                        data["items"] = {}
                    
                    if "server_stats" not in data or not isinstance(data["server_stats"], dict):
                        data["server_stats"] = {
                            "total_attempts": 0,
                            "total_successes": 0,
                            "highest_level": 0,
                            "total_users": 0
                        }
                    
                    # ✅ total_users 정확한 계산
                    unique_users = set()
                    for item_key, item_data in data["items"].items():
                        if isinstance(item_data, dict) and "owner_id" in item_data:
                            unique_users.add(item_data["owner_id"])
                    
                    data["server_stats"]["total_users"] = len(unique_users)
                    
                    return data
            except (json.JSONDecodeError, FileNotFoundError) as e:
                print(f"❌ 강화 데이터 로드 오류: {e}. 기본 구조로 초기화합니다.")
        
        return self._create_default_data()

    def _create_default_data(self) -> Dict:
        """기본 데이터 구조 생성"""
        return {
            "items": {},
            "server_stats": {
                "total_attempts": 0,
                "total_successes": 0,
                "highest_level": 0,
                "total_users": 0
            }
        }

    def save_data(self) -> bool:
        """데이터 저장 (안전성 강화)"""
        try:
            # ✅ 저장 전 데이터 검증
            if not isinstance(self.data, dict):
                print("❌ self.data가 dict가 아닙니다. 저장을 건너뜁니다.")
                return False
            
            # ✅ total_users 재계산 (저장 직전)
            unique_users = set()
            items = self.data.get("items", {})
            if isinstance(items, dict):
                for item_key, item_data in items.items():
                    if isinstance(item_data, dict) and "owner_id" in item_data:
                        unique_users.add(item_data["owner_id"])
            
            if "server_stats" not in self.data:
                self.data["server_stats"] = {}
            self.data["server_stats"]["total_users"] = len(unique_users)
            
            # 파일 저장
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 강화 데이터 저장 실패: {e}")
            return False

    def get_item_data(self, item_name: str, owner_id: str, owner_name: str) -> Dict:
        """아이템 데이터 조회/생성 (완전 수정)"""
        item_key = f"{owner_id}_{item_name.lower()}"
        
        # ✅ 데이터 구조 안전성 확인
        if not isinstance(self.data, dict):
            self.data = self._create_default_data()
        
        if "items" not in self.data or not isinstance(self.data["items"], dict):
            self.data["items"] = {}
        
        if "server_stats" not in self.data or not isinstance(self.data["server_stats"], dict):
            self.data["server_stats"] = {
                "total_attempts": 0,
                "total_successes": 0,
                "highest_level": 0,
                "total_users": 0
            }
        
        # 새 아이템 생성
        if item_key not in self.data["items"]:
            self.data["items"][item_key] = {
                "item_name": item_name,
                "owner_id": owner_id,
                "owner_name": owner_name,
                "level": 0,
                "total_attempts": 0,
                "success_count": 0,
                "created_at": datetime.now().isoformat(),
                "last_attempt": None,
                "consecutive_fails": 0
            }
            
            # ✅ total_users 정확한 업데이트
            unique_users = set()
            for existing_key, existing_data in self.data["items"].items():
                if isinstance(existing_data, dict) and "owner_id" in existing_data:
                    unique_users.add(existing_data["owner_id"])
            
            self.data["server_stats"]["total_users"] = len(unique_users)
        
        return self.data["items"][item_key]

    def attempt_enhancement(self, item_name: str, owner_id: str, owner_name: str) -> Tuple[bool, int, int, float, float, str, int, int]:
        """강화 시도 (안전성 강화)"""
        try:
            item_data = self.get_item_data(item_name, owner_id, owner_name)
            current_level = item_data.get("level", 0)
            
            # 타입 검증
            if not isinstance(current_level, (int, float)):
                current_level = 0
                item_data["level"] = 0
            else:
                current_level = int(current_level)
            
            # 최대 레벨 체크
            if current_level >= ENHANCEMENT_CONFIG["max_level"]:
                return False, current_level, current_level, 0, 0, "최대 레벨", 0, 0
            
            # 강화 확률 계산
            success_rate = get_success_rate(current_level)
            downgrade_rate = get_downgrade_rate(current_level)
            
            # 연속 실패 횟수 가져오기
            consec_fail = item_data.get("consecutive_fails", 0)
            if not isinstance(consec_fail, (int, float)):
                consec_fail = 0
                item_data["consecutive_fails"] = 0

            # 특별 보정 조건
            force_result = None
            if consec_fail >= 5:
                # 연속 5회 실패 시 성공/강등 중 하나 보장
                total = success_rate + downgrade_rate
                rand_val = random.uniform(0, total)
                if rand_val <= success_rate:
                    force_result = "success"
                else:
                    force_result = "downgrade"
            
            # 강화 시도 결과 계산
            if force_result:
                result_type = force_result
            else:
                # 일반 강화 시도
                roll = random.randint(1, 10000)  # 0.01% 단위
                success_threshold = success_rate * 100
                downgrade_threshold = success_threshold + (downgrade_rate * 100)
                
                if roll <= success_threshold:
                    result_type = "success"
                elif roll <= downgrade_threshold:
                    result_type = "downgrade"
                else:
                    result_type = "fail"

            # 통계 업데이트 (안전한 증가)
            item_data["total_attempts"] = int(item_data.get("total_attempts", 0)) + 1
            item_data["last_attempt"] = datetime.now().isoformat()
            
            # 서버 통계 업데이트
            if isinstance(self.data.get("server_stats"), dict):
                self.data["server_stats"]["total_attempts"] = int(self.data["server_stats"].get("total_attempts", 0)) + 1

            # 결과 처리
            level_change = 0
            if result_type == "success":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                item_data["level"] = current_level + level_change
                item_data["success_count"] = int(item_data.get("success_count", 0)) + 1
                item_data["consecutive_fails"] = 0
                
                # 서버 최고 레벨 업데이트
                if isinstance(self.data.get("server_stats"), dict):
                    current_highest = self.data["server_stats"].get("highest_level", 0)
                    if item_data["level"] > current_highest:
                        self.data["server_stats"]["highest_level"] = item_data["level"]
                    self.data["server_stats"]["total_successes"] = int(self.data["server_stats"].get("total_successes", 0)) + 1
                
                # ✅ 통계 기록 (성공)
                record_enhancement_attempt(owner_id, owner_name, True)
                
            elif result_type == "downgrade":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                item_data["level"] = max(0, current_level - level_change)
                level_change = -level_change  # 음수로 표시
                item_data["consecutive_fails"] = int(item_data.get("consecutive_fails", 0)) + 1
                
                # ✅ 통계 기록 (실패)
                record_enhancement_attempt(owner_id, owner_name, False)
                
            else:  # fail
                item_data["consecutive_fails"] = int(item_data.get("consecutive_fails", 0)) + 1
                
                # ✅ 통계 기록 (실패)
                record_enhancement_attempt(owner_id, owner_name, False)

            # 주기적 저장
            self.backup_counter += 1
            if self.backup_counter >= ENHANCEMENT_CONFIG["backup_interval"]:
                self.save_data()
                self.backup_counter = 0

            return (
                result_type == "success",
                current_level,
                item_data["level"],
                success_rate,
                downgrade_rate,
                result_type,
                level_change,
                item_data["consecutive_fails"]
            )
        except Exception as e:
            print(f"❌ 강화 시도 중 오류: {e}")
            return False, 0, 0, 0, 0, "오류", 0, 0

    def get_user_items(self, user_id: str) -> List[Dict]:
        """사용자의 모든 아이템 조회 (안전성 강화)"""
        try:
            user_items = []
            items = self.data.get("items", {})
            
            if isinstance(items, dict):
                for item_key, item_data in items.items():
                    if isinstance(item_data, dict) and item_data.get("owner_id") == user_id:
                        user_items.append(item_data)
            
            # 레벨순으로 정렬 (안전한 정렬)
            def safe_level_sort(item):
                level = item.get("level", 0)
                return int(level) if isinstance(level, (int, float)) else 0
            
            user_items.sort(key=safe_level_sort, reverse=True)
            return user_items
        except Exception as e:
            print(f"❌ 사용자 아이템 조회 오류: {e}")
            return []

    def get_server_stats(self) -> Dict:
        """서버 통계 조회 (안전성 강화)"""
        try:
            if isinstance(self.data, dict) and isinstance(self.data.get("server_stats"), dict):
                return self.data["server_stats"].copy()
            else:
                return {
                    "total_attempts": 0,
                    "total_successes": 0,
                    "highest_level": 0,
                    "total_users": 0
                }
        except Exception as e:
            print(f"❌ 서버 통계 조회 오류: {e}")
            return {
                "total_attempts": 0,
                "total_successes": 0,
                "highest_level": 0,
                "total_users": 0
            }

    def get_top_items(self, limit: int = 10) -> List[Dict]:
        """전체 상위 아이템 목록 (안전성 강화)"""
        try:
            all_items = []
            items = self.data.get("items", {})
            
            if isinstance(items, dict):
                for item_data in items.values():
                    if isinstance(item_data, dict):
                        all_items.append(item_data)
            
            # 레벨순으로 정렬 (안전한 정렬)
            def safe_level_sort(item):
                level = item.get("level", 0)
                return int(level) if isinstance(level, (int, float)) else 0
            
            all_items.sort(key=safe_level_sort, reverse=True)
            return all_items[:limit]
        except Exception as e:
            print(f"❌ 상위 아이템 조회 오류: {e}")
            return []

# ✅ 전역 강화 데이터 매니저
enhancement_data = EnhancementDataManager()

# ✅ 쿨다운 관리
enhancement_cooldowns = {}

def check_cooldown(user_id: str, item_name: str) -> Tuple[bool, int]:
    """쿨다운 확인"""
    try:
        cooldown_key = f"{user_id}_{item_name.lower()}"
        current_time = time.time()
        
        if cooldown_key in enhancement_cooldowns:
            time_passed = current_time - enhancement_cooldowns[cooldown_key]
            remaining = ENHANCEMENT_CONFIG["cooldown_time"] - time_passed
            
            if remaining > 0:
                return False, int(remaining)
        
        enhancement_cooldowns[cooldown_key] = current_time
        return True, 0
    except Exception as e:
        print(f"❌ 쿨다운 확인 오류: {e}")
        return True, 0  # 오류 시 쿨다운 무시

# ===== Discord Cog =====

class EnhancementSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enhancement_data = enhancement_data

    @app_commands.command(name="강화", description="아이템을 강화합니다.")
    @app_commands.describe(아이템명="강화할 아이템의 이름")
    async def enhance_item(self, interaction: discord.Interaction, 아이템명: str):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        
        try:
            # 입력 검증
            if len(아이템명) < 1 or len(아이템명) > 20:
                return await interaction.response.send_message("❌ 아이템명은 1~20자 사이여야 합니다.", ephemeral=True)
            
            # 쿨다운 확인
            can_enhance, remaining = check_cooldown(user_id, 아이템명)
            if not can_enhance:
                return await interaction.response.send_message(
                    f"⏰ 아이템 **{아이템명}**은(는) 아직 강화할 수 없습니다. ({remaining}초 남음)", 
                    ephemeral=True
                )
            
            # 강화 시도
            success, old_level, new_level, success_rate, downgrade_rate, result_type, level_change, consecutive_fails = \
                self.enhancement_data.attempt_enhancement(아이템명, user_id, username)
            
            # 등급 정보
            tier_info = get_level_tier_info(new_level)
            
            # 아이템 데이터 가져오기
            item_data = self.enhancement_data.get_item_data(아이템명, user_id, username)
            
            # 임베드 생성 (화려한 스타일)
            if result_type == "success":
                if level_change >= 8:
                    title = "✨ 강화 대성공!"
                    emotion = "😍 환희"
                elif level_change >= 5:
                    title = "🔥 강화 성공!"
                    emotion = "😊 기쁨"
                else:
                    title = "✅ 강화 성공!"
                    emotion = "😌 만족"
                    
                embed = discord.Embed(
                    title=title,
                    color=tier_info["color"]
                )
                
                embed.add_field(
                    name="😨 절망" if level_change <= 2 else emotion,
                    value=f"**{아이템명}**",
                    inline=False
                )
                
                old_tier = get_level_tier_info(old_level)
                embed.add_field(
                    name="📈 강화 결과",
                    value=f"{old_tier['emoji']} Lv{old_level} ({old_tier['tier']}) → {tier_info['emoji']} **Lv{new_level} ({tier_info['tier']} {new_level})**\n" +
                          f"🎉 **+{level_change}레벨 상승**",
                    inline=False
                )
                
                # 성공 메시지
                success_msgs = [
                    f"🎊 {tier_info['tier']}로 강화에 성공함당!",
                    f"✨ 멋진 {level_change}레벨 상승!",
                    f"🔥 {아이템명}이(가) 더욱 강해졌습니다!"
                ]
                embed.add_field(
                    name="🎉 성공!",
                    value=f"{random.choice(success_msgs)}\n📈 렌딩으로 **{level_change}레벨** 상승",
                    inline=False
                )
                
            elif result_type == "downgrade":
                embed = discord.Embed(
                    title="💥 강화 실패 (강등)",
                    color=discord.Color.orange()
                )
                
                embed.add_field(
                    name="😱 절망",
                    value=f"**{아이템명}**",
                    inline=False
                )
                
                old_tier = get_level_tier_info(old_level)
                embed.add_field(
                    name="📉 강등 결과",
                    value=f"{old_tier['emoji']} Lv{old_level} ({old_tier['tier']}) → {tier_info['emoji']} **Lv{new_level} ({tier_info['tier']} {new_level})**\n" +
                          f"💀 **{abs(level_change)}레벨 하락**",
                    inline=False
                )
                
                embed.add_field(
                    name="💀 강등됨",
                    value=f"😭 아쉽게도 강등되었습니다...\n📉 {abs(level_change)}레벨 하락",
                    inline=False
                )
                
            elif result_type == "최대 레벨":
                embed = discord.Embed(
                    title="👑 최대 레벨 달성!",
                    description=f"**{아이템명}**은(는) 이미 최강입니다!",
                    color=discord.Color.gold()
                )
                return await interaction.response.send_message(embed=embed)
                
            elif result_type == "오류":
                embed = discord.Embed(
                    title="❌ 시스템 오류",
                    description="강화 중 예상치 못한 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
                return await interaction.response.send_message(embed=embed, ephemeral=True)
                
            else:  # fail
                embed = discord.Embed(
                    title="❌ 강화 실패",
                    color=discord.Color.red()
                )
                
                embed.add_field(
                    name="😔 실망",
                    value=f"**{아이템명}**",
                    inline=False
                )
                
                embed.add_field(
                    name="💔 실패",
                    value=f"{tier_info['emoji']} **Lv{new_level} ({tier_info['tier']} {new_level})**\n" +
                          f"💸 아무 변화 없음",
                    inline=False
                )
                
                embed.add_field(
                    name="😢 실패함",
                    value=f"💔 아쉽게도 실패했습니다...\n🎯 다음 번엔 성공하길!",
                    inline=False
                )
            
            # 아이템 통계 정보
            total_attempts = item_data.get("total_attempts", 0)
            success_count = item_data.get("success_count", 0)
            fail_count = total_attempts - success_count
            item_success_rate = (success_count / total_attempts * 100) if total_attempts > 0 else 0
            
            # 다운그레이드 횟수 계산 (실패 중에서 강등된 것들)
            downgrade_count = 0  # 단순화를 위해 0으로 설정
            
            embed.add_field(
                name="📊 아이템 통계",
                value=f"🎯 총 시도: **{total_attempts}회**\n" +
                      f"✅ 성공: **{success_count}회**\n" +
                      f"❌ 실패: **{fail_count}회**\n" +
                      f"📉 강등: **{downgrade_count}회**",
                inline=True
            )
            
            # 다음 강화 정보
            next_success_rate = get_success_rate(new_level)
            next_downgrade_rate = get_downgrade_rate(new_level)
            
            embed.add_field(
                name="🔮 다음 강화",
                value=f"📈 성공률: **{next_success_rate:.1f}%**\n" +
                      f"📉 강등률: **{next_downgrade_rate:.1f}%**\n" +
                      f"💰 강화비: **무료**\n" +
                      f"⏰ 쿨타임: **30초**",
                inline=True
            )
            
            # 추가 정보
            if consecutive_fails >= 3:
                embed.add_field(
                    name="🛡️ 연속 실패 보호",
                    value=f"🔥 연속 **{consecutive_fails}회** 실패!\n" +
                          f"💡 **{5 - consecutive_fails}회** 더 실패하면\n" +
                          f"🎯 다음 강화는 **성공/강등 보장**!",
                    inline=False
                )
            
            # 푸터 정보
            embed.set_footer(
                text=f"소유자: {username} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ 강화 명령어 오류: {e}")
            await interaction.response.send_message("❌ 강화 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="내강화", description="내가 소유한 아이템 목록을 확인합니다.")
    async def my_items(self, interaction: discord.Interaction):
        user_id = str(interaction.user.id)
        username = interaction.user.display_name
        
        try:
            user_items = self.enhancement_data.get_user_items(user_id)
            
            if not user_items:
                embed = discord.Embed(
                    title="📦 내 아이템 목록",
                    description="아직 강화한 아이템이 없습니다.\n`/강화 아이템명`으로 첫 아이템을 강화해보세요!",
                    color=discord.Color.light_grey()
                )
            else:
                embed = discord.Embed(
                    title="📦 내 아이템 목록",
                    description=f"총 **{len(user_items)}개**의 아이템을 보유하고 있습니다.",
                    color=discord.Color.blue()
                )
                
                # 상위 10개 아이템만 표시
                for i, item in enumerate(user_items[:10], 1):
                    tier_info = get_level_tier_info(item.get("level", 0))
                    total_attempts = item.get("total_attempts", 0)
                    success_count = item.get("success_count", 0)
                    success_rate = (success_count / total_attempts * 100) if total_attempts > 0 else 0
                    
                    embed.add_field(
                        name=f"{i}. {tier_info['emoji']} {item.get('item_name', 'Unknown')}",
                        value=f"**{tier_info['name']}**\n시도: {total_attempts}회, 성공률: {success_rate:.1f}%",
                        inline=True
                    )
                
                if len(user_items) > 10:
                    embed.add_field(
                        name="📝 안내",
                        value=f"상위 10개 아이템만 표시됩니다. (총 {len(user_items)}개)",
                        inline=False
                    )
            
            embed.set_footer(text=f"{username}님의 아이템 목록 • 순수 강화 시스템")
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ 내강화 명령어 오류: {e}")
            await interaction.response.send_message("❌ 아이템 목록 조회 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="강화순위", description="전체 강화 순위를 확인합니다.")
    async def enhancement_ranking(self, interaction: discord.Interaction):
        try:
            top_items = self.enhancement_data.get_top_items(10)
            server_stats = self.enhancement_data.get_server_stats()
            
            embed = discord.Embed(
                title="🏆 강화 순위",
                description="전체 서버의 최고 강화 아이템들입니다.",
                color=discord.Color.gold()
            )
            
            if top_items:
                for i, item in enumerate(top_items, 1):
                    tier_info = get_level_tier_info(item.get("level", 0))
                    owner_name = item.get("owner_name", "Unknown")
                    item_name = item.get("item_name", "Unknown")
                    level = item.get("level", 0)
                    
                    # 랭킹 이모지
                    rank_emoji = ["🥇", "🥈", "🥉"][i-1] if i <= 3 else f"{i}."
                    
                    embed.add_field(
                        name=f"{rank_emoji} {tier_info['emoji']} {item_name}",
                        value=f"**{tier_info['name']}**\n소유자: {owner_name}",
                        inline=True
                    )
            else:
                embed.add_field(
                    name="📝 안내",
                    value="아직 강화된 아이템이 없습니다.",
                    inline=False
                )
            
            # 서버 통계
            embed.add_field(
                name="📊 서버 통계",
                value=f"총 시도: **{server_stats['total_attempts']:,}회**\n" +
                      f"총 성공: **{server_stats['total_successes']:,}회**\n" +
                      f"참여자: **{server_stats['total_users']:,}명**\n" +
                      f"최고 레벨: **{server_stats['highest_level']}**",
                inline=False
            )
            
            embed.set_footer(text="순수 강화 시스템 • 보상 없음")
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ 강화순위 명령어 오류: {e}")
            await interaction.response.send_message("❌ 순위 조회 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="강화정보", description="강화 시스템에 대한 정보를 확인합니다.")
    async def enhancement_info(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="⚒️ 순수 강화 시스템",
            description="🎲 **완전 무료 랜덤 레벨 변동 시스템 (보상 없음)**",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🎯 기본 규칙",
            value="• 각 아이템별로 독립적인 강화\n• 30초 쿨다운 (아이템별)\n• 1~10레벨 랜덤 변동\n• **완전 무료, 보상 없음**",
            inline=False
        )
        
        embed.add_field(
            name="📊 확률 시스템",
            value="• 레벨이 높을수록 성공률 감소\n• 레벨 10 이하는 강등 없음 (안전구간)\n• 연속 5회 실패 시 다음은 성공/강등 보장",
            inline=False
        )
        
        embed.add_field(
            name="🏆 등급 시스템",
            value="• **기본** (1-10): 초급~신급\n• **마스터** (11-50)\n• **헤로익** (51-100)\n• **에픽** (101-200)\n• **레어** (201-300)\n• **유니크** (301-400)\n• **미식** (401-450)\n• **초월** (451-499)\n• **절대신** (500): 최고 등급",
            inline=False
        )
        
        embed.add_field(
            name="❌ 보상 시스템",
            value="• **강화 성공 시 보상 없음**\n• **순수 재미를 위한 시스템**\n• **레벨 달성이 목표**",
            inline=False
        )
        
        embed.add_field(
            name="🎮 사용법",
            value="`/강화 아이템명` - 아이템 강화\n`/내강화` - 내 아이템 목록\n`/강화순위` - 전체 순위\n`/강화정보` - 시스템 정보",
            inline=False
        )
        
        embed.set_footer(text="각 아이템마다 다른 이름으로 여러 개 강화 가능! • 기존 시스템과 완전 독립")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화초기화", description="모든 강화 데이터를 초기화합니다. (관리자 전용)")
    async def reset_enhancement(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "❌ 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        try:
            # 데이터 확인
            total_items = len(self.enhancement_data.data.get("items", {}))
            server_stats = self.enhancement_data.get_server_stats()
            
            # 초기화할 데이터가 없는 경우
            if total_items == 0:
                return await interaction.response.send_message(
                    "ℹ️ 초기화할 강화 데이터가 없습니다.",
                    ephemeral=True
                )
            
            # 실제 초기화 실행
            self.enhancement_data.data = self.enhancement_data._create_default_data()
            success = self.enhancement_data.save_data()
            
            if success:
                embed = discord.Embed(
                    title="✅ 강화 데이터 초기화 완료",
                    description="모든 강화 데이터가 성공적으로 초기화되었습니다.",
                    color=discord.Color.green()
                )
                
                embed.add_field(
                    name="🗑️ 삭제된 데이터",
                    value=f"• 아이템 수: **{total_items}개**\n" +
                          f"• 총 시도: **{server_stats['total_attempts']:,}회**\n" +
                          f"• 참여자: **{server_stats['total_users']:,}명**\n" +
                          f"• 최고 레벨: **{server_stats['highest_level']}**",
                    inline=False
                )
                
                embed.add_field(
                    name="🔄 새로 시작",
                    value="이제 `/강화 아이템명`으로 새로운 강화를 시작할 수 있습니다!",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ 초기화 실패",
                    description="데이터 초기화 중 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
                
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 강화초기화 명령어 오류: {e}")
            await interaction.response.send_message("❌ 초기화 중 오류가 발생했습니다.", ephemeral=True)

# ✅ Cog setup 함수
async def setup(bot):
    await bot.add_cog(EnhancementSystemCog(bot))