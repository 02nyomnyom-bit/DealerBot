# enhancement_system.py - 강화 시스템
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

# 통계 시스템
try:
    from statistics_system import stats_manager
    STATS_AVAILABLE = True
    print("✅ 통계 시스템 연동 완료")
except ImportError:
    STATS_AVAILABLE = False
    print("⚠️ 통계 시스템을 찾을 수 없습니다 (강화시스템 - 독립 모드)")
    
    # Mock stats manager (통계 없이도 작동)
    class MockStatsManager:
        @staticmethod
        def record_game_activity(user_id, username, game_name, **kwargs):
            pass
    
    stats_manager = MockStatsManager()

# 통계 기록 헬퍼 함수
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
    "cooldown_time": 30,            # 강화 쿨다운 30초
    "max_level": 1000,              # 최대 레벨
    "min_safe_level": 10,           # 강등 방지 최소 레벨
    "level_change_range": (1, 5),   # 레벨 변동 범위
    "backup_interval": 30,          # 50회마다 백업
    "max_items_per_user": 3,        # 갯수제한
    "special_reward_chance": 0.1    # 당첨 확률
}

# 데이터 디렉토리 생성
os.makedirs("data", exist_ok=True)


# 강화 확률 계산 함수들
def get_success_rate(level: int) -> float:
    """레벨에 따른 성공률 계산"""
    if level == 0:
        return 100.0
    
    # 레벨이 높을수록 성공률 감소
    max_level = 1000
    min_rate = 0.5
    max_rate = 100.0
    
    # 2차 함수로 감소
    rate = max_rate * ((1 - level / max_level) ** 3)
    return max(rate, min_rate)

def get_downgrade_rate(level: int) -> float:
    """레벨에 따른 강등 확률 계산"""
    if level <= ENHANCEMENT_CONFIG["min_safe_level"]:
        return 0.0  # 안전구간에서는 강등 없음
    
    # 레벨이 높을수록 강등 확률 증가
    max_level = 1000
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
    elif level <= 50:
        # 기본 등급 (1-50)
        return {
            "name": f"기본 {level}",
            "color": 0x00FF00,
            "emoji": "🟢",
            "tier": "기본"
        }
    elif level <= 150:
        # 아이언 등급
        return {
            "name": f"아이언 {level}",
            "color": 0x0080FF,
            "emoji": "🔵",
            "tier": "아이언"
        }
    elif level <= 250:
        # 브론즈 등급
        return {
            "name": f"브론즈 {level}",
            "color": 0x8000FF,
            "emoji": "🟣",
            "tier": "브론즈"
        }
    elif level <= 350:
        # 실버 등급
        return {
            "name": f"실버 {level}",
            "color": 0xFF8000,
            "emoji": "🟠",
            "tier": "실버"
        }
    elif level <= 450:
        # 골드 등급
        return {
            "name": f"골드 {level}",
            "color": 0xFF0080,
            "emoji": "🔴",
            "tier": "골드"
        }
    elif level <= 600:
        # 플래티넘 등급
        return {
            "name": f"플래티넘 {level}",
            "color": 0x80FF00,
            "emoji": "🟡",
            "tier": "플래티넘"
        }
    elif level <= 750:
        # 마스터 등급
        return {
            "name": f"마스터 {level}",
            "color": 0xFF69B4,
            "emoji": "🍯",
            "tier": "마스터"
        }
    elif level <= 950:
        # 그랜드마스터 등급
        return {
            "name": f"그랜드마스터 {level}",
            "color": 0x8A2BE2,
            "emoji": "🌌",
            "tier": "그랜드마스터"
        }
    else:
        # 챌린저 등급 (1000레벨)
        return {
            "name": "챌린저 1000",
            "color": 0xFFFFFF,
            "emoji": "👑",
            "tier": "챌린저"
        }

# 강화 데이터 관리 클래스
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
                    
                    if not isinstance(data, dict):
                        print("❌ enhancement_data가 dict가 아닙니다. 기본 구조로 초기화합니다.")
                        return self._create_default_data()
                    
                    if "items" not in data or not isinstance(data["items"], dict):
                        data["items"] = {}
                    
                    if "server_stats" not in data or not isinstance(data["server_stats"], dict):
                        data["server_stats"] = {
                            "total_attempts": 0,
                            "total_successes": 0,
                            "highest_level": 0,
                            "total_users": 0
                        }
                    
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
            if not isinstance(self.data, dict):
                print("❌ self.data가 dict가 아닙니다. 저장을 건너뜁니다.")
                return False
            
            unique_users = set()
            items = self.data.get("items", {})
            if isinstance(items, dict):
                for item_key, item_data in items.items():
                    if isinstance(item_data, dict) and "owner_id" in item_data:
                        unique_users.add(item_data["owner_id"])
            
            if "server_stats" not in self.data:
                self.data["server_stats"] = {}
            self.data["server_stats"]["total_users"] = len(unique_users)
            
            with open(self.data_file, 'w', encoding='utf-8') as f:
                json.dump(self.data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 강화 데이터 저장 실패: {e}")
            return False

    def get_item_data(self, item_name: str, owner_id: str, owner_name: str, guild_id: str) -> Dict:
        """아이템 데이터 조회/생성 (완전 수정)"""
        item_key = f"{owner_id}_{item_name.lower()}"
        
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
                "guild_id": guild_id,
                "owner_name": owner_name,
                "level": 0,
                "total_attempts": 0,
                "success_count": 0,
                "downgrade_count": 0, 
                "total_levels_gained": 0, # ✅ 추가: 누적 상승한 총 레벨
                "total_levels_lost": 0,   # ✅ 추가: 누적 하락한 총 레벨
                "created_at": datetime.now().isoformat(),
                "last_attempt": None,
                "consecutive_fails": 0
            }
            
            unique_users = set()
            for existing_key, existing_data in self.data["items"].items():
                if isinstance(existing_data, dict) and "owner_id" in existing_data:
                    unique_users.add(existing_data["owner_id"])
            
            self.data["server_stats"]["total_users"] = len(unique_users)
        
        # 데이터 로드 시 누락된 필드 보정 (기존 데이터 호환성 유지)
        if "downgrade_count" not in self.data["items"][item_key]:
            self.data["items"][item_key]["downgrade_count"] = 0
        if "total_levels_gained" not in self.data["items"][item_key]: # ✅ 기존 데이터 호환 패치
            self.data["items"][item_key]["total_levels_gained"] = 0
        if "total_levels_lost" not in self.data["items"][item_key]: # ✅ 기존 데이터 호환 패치
            self.data["items"][item_key]["total_levels_lost"] = 0
            
        return self.data["items"][item_key]

    def get_existing_item_data(self, item_name: str, owner_id: str) -> Optional[Dict]:
        """아이템 데이터 조회 (존재하지 않으면 None 반환)"""
        item_key = f"{owner_id}_{item_name.lower()}"
        items = self.data.get("items", {})
        if isinstance(items, dict) and item_key in items:
            return items[item_key]
        return None

    def attempt_enhancement(self, item_name: str, owner_id: str, owner_name: str, guild_id: str) -> Tuple:
        """강화 시도 (guild_id 추가)"""
        try:
            item_data = self.get_item_data(item_name, owner_id, owner_name, guild_id)
            current_level = item_data.get("level", 0)
            
            if not isinstance(current_level, (int, float)):
                current_level = 0
                item_data["level"] = 0
            else:
                current_level = int(current_level)
            
            if current_level >= ENHANCEMENT_CONFIG["max_level"]:
                return False, current_level, current_level, 0, 0, "최대 레벨", 0, 0
            
            success_rate = get_success_rate(current_level)
            downgrade_rate = get_downgrade_rate(current_level)
            
            consec_fail = item_data.get("consecutive_fails", 0)
            if not isinstance(consec_fail, (int, float)):
                consec_fail = 0
                item_data["consecutive_fails"] = 0

            force_result = None
            if consec_fail >= 5:
                force_result = "success"
            
            if force_result:
                result_type = force_result
            else:
                roll = random.randint(1, 10000)
                success_threshold = success_rate * 100
                downgrade_threshold = success_threshold + (downgrade_rate * 100)
                
                if roll <= success_threshold:
                    result_type = "success"
                elif roll <= downgrade_threshold:
                    result_type = "downgrade"
                else:
                    result_type = "fail"

            item_data["total_attempts"] = int(item_data.get("total_attempts", 0)) + 1
            item_data["last_attempt"] = datetime.now().isoformat()
            
            if isinstance(self.data.get("server_stats"), dict):
                self.data["server_stats"]["total_attempts"] = int(self.data["server_stats"].get("total_attempts", 0)) + 1

            level_change = 0
            if result_type == "success":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                item_data["level"] = current_level + level_change
                item_data["success_count"] = int(item_data.get("success_count", 0)) + 1
                item_data["total_levels_gained"] = int(item_data.get("total_levels_gained", 0)) + level_change # ✅ 누적 상승치 증가
                item_data["consecutive_fails"] = 0
                
                if isinstance(self.data.get("server_stats"), dict):
                    current_highest = self.data["server_stats"].get("highest_level", 0)
                    if item_data["level"] > current_highest:
                        self.data["server_stats"]["highest_level"] = item_data["level"]
                    self.data["server_stats"]["total_successes"] = int(self.data["server_stats"].get("total_successes", 0)) + 1
                
                record_enhancement_attempt(owner_id, owner_name, True)
                
            elif result_type == "downgrade":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                
                # 안전 하락 (음수 보정)
                actual_lost = min(current_level, level_change) 
                item_data["level"] = current_level - actual_lost
                item_data["total_levels_lost"] = int(item_data.get("total_levels_lost", 0)) + actual_lost # ✅ 누적 하락치 증가 (0 미만으로 떨어지지 않는 실제 하락치만 기록)
                
                level_change = -level_change
                item_data["consecutive_fails"] = int(item_data.get("consecutive_fails", 0)) + 1
                item_data["downgrade_count"] = int(item_data.get("downgrade_count", 0)) + 1
                
                record_enhancement_attempt(owner_id, owner_name, False)
                
            else:  # fail
                item_data["consecutive_fails"] = int(item_data.get("consecutive_fails", 0)) + 1
                record_enhancement_attempt(owner_id, owner_name, False)

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

    def get_top_items(self, guild_id: str, limit: int = 10) -> List[Dict]:
        """해당 서버(guild_id)의 상위 아이템 목록 조회"""
        try:
            all_items = []
            items = self.data.get("items", {})
        
            if isinstance(items, dict):
                for item_data in items.values():
                    if isinstance(item_data, dict) and item_data.get("guild_id") == guild_id:
                        all_items.append(item_data)
        
            def safe_level_sort(item):
                level = item.get("level", 0)
                return int(level) if isinstance(level, (int, float)) else 0
        
            all_items.sort(key=safe_level_sort, reverse=True)
            return all_items[:limit]
        except Exception as e:
            print(f"❌ 상위 아이템 조회 오류: {e}")
            return []

enhancement_data = EnhancementDataManager()
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
        return True, 0

# ===== Discord Cog =====

class EnhancementSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enhancement_data = enhancement_data

    @app_commands.command(name="강화", description="아이템을 강화합니다.")
    async def enhance_item(self, interaction: discord.Interaction, 아이템명: str):
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True # 기본값
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)

        user_id = str(interaction.user.id)
        guild_id = str(interaction.guild_id)
        username = interaction.user.display_name
        
        try:
            if len(아이템명) < 1 or len(아이템명) > 20:
                return await interaction.response.send_message("❌ 아이템명은 1~20자 사이여야 합니다.", ephemeral=True)
            
            existing_item = self.enhancement_data.get_existing_item_data(아이템명, user_id)
            if not existing_item:
                user_items = self.enhancement_data.get_user_items(user_id)
                max_limit = ENHANCEMENT_CONFIG["max_items_per_user"]
                
                if len(user_items) >= max_limit:
                    return await interaction.response.send_message(
                        f"❎ **아이템 보유 제한:** 최대 **{max_limit}개**의 아이템만 소유할 수 있습니다.\n"
                        f"현재 보유 중인 아이템을 관리하거나 다른 아이템을 강화할 수 없습니다.", 
                        ephemeral=True
                    )
                
            can_enhance, remaining = check_cooldown(user_id, 아이템명)
            if not can_enhance:
                return await interaction.response.send_message(
                    f"⏰ 아이템 **{아이템명}**은(는) 아직 강화할 수 없습니다. ({remaining}초 남음)", 
                    ephemeral=True
                )
            
            success, old_level, new_level, success_rate, downgrade_rate, result_type, level_change, consecutive_fails = \
                self.enhancement_data.attempt_enhancement(아이템명, user_id, username, guild_id)
            
            tier_info = get_level_tier_info(new_level)
            item_data = self.enhancement_data.get_item_data(아이템명, user_id, username, guild_id)
            
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

                is_winner = random.random() * 100 <= ENHANCEMENT_CONFIG.get("special_reward_chance", 1.0)
                if is_winner:
                    embed.add_field(
                        name="🎁 특별 이벤트 발생!",
                        value="### **당첨. 관리자에게 문의주세요**",
                        inline=False
                    )

                embed.add_field(
                    name=emotion,
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
                
                success_msgs = [
                    f"🎊 {tier_info['tier']}로 강화에 성공함당!",
                    f"✨ 멋진 {level_change}레벨 상승!",
                    f"🔥 {아이템명}이(가) 더욱 강해졌습니다!"
                ]
                embed.add_field(
                    name="🎉 성공!",
                    value=f"{random.choice(success_msgs)}\n📈 랜덤 수치로 **{level_change}레벨** 상승",
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
            
            total_attempts = item_data.get("total_attempts", 0)
            success_count = item_data.get("success_count", 0)
            downgrade_count = item_data.get("downgrade_count", 0)
            total_gained = item_data.get("total_levels_gained", 0) # ✅ 가져오기
            total_lost = item_data.get("total_levels_lost", 0)     # ✅ 가져오기
            no_change_fail_count = total_attempts - success_count - downgrade_count
            
            embed.add_field(
                name="📊 아이템 통계",
                value=f"🎯 총 시도: **{total_attempts}회**\n" +
                      f"✅ 성공 (레벨 상승): **{success_count}회** (누적 **+{total_gained}레벨**)\n" + # ✅ 누적치 표시
                      f"💀 강등 (레벨 하락): **{downgrade_count}회** (누적 **-{total_lost}레벨**)\n" + # ✅ 누적치 표시
                      f"❌ 실패 (현상 유지): **{no_change_fail_count}회**",
                inline=True
            )
            
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
            
            if consecutive_fails >= 3:
                embed.add_field(
                    name="🛡️ 연속 실패 보호",
                    value=f"🔥 연속 **{consecutive_fails}회** 실패!\n" +
                          f"💡 **{5 - consecutive_fails}회** 더 실패하면\n" +
                          f"🎯 다음 강화는 **성공 보장**!",
                    inline=False
                )
            
            embed.set_footer(
                text=f"소유자: {username} | {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            )
            
            await interaction.response.send_message(embed=embed)
            
        except Exception as e:
            print(f"❌ 강화 명령어 오류: {e}")
            await interaction.response.send_message("❌ 강화 중 오류가 발생했습니다.", ephemeral=True)

    @app_commands.command(name="내강화", description="내가 소유한 아이템 목록을 확인합니다.")
    async def my_items(self, interaction: discord.Interaction):
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
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
                
                for i, item in enumerate(user_items[:10], 1):
                    tier_info = get_level_tier_info(item.get("level", 0))
                    total_attempts = item.get("total_attempts", 0)
                    success_count = item.get("success_count", 0)
                    total_gained = item.get("total_levels_gained", 0) # ✅ 내정보에도 추가
                    
                    embed.add_field(
                        name=f"{i}. {tier_info['emoji']} {item.get('item_name', 'Unknown')}",
                        value=f"**{tier_info['name']}**\n성공: {success_count}/{total_attempts}회 (+{total_gained}레벨)",
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
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        try:
            guild_id = str(interaction.guild_id)
            top_items = self.enhancement_data.get_top_items(guild_id, 10)
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

    @app_commands.command(name="공격", description="상대방의 아이템을 공격합니다. (등급별 일일 횟수 제한)")
    @app_commands.describe(내아이템="내가 사용할 아이템 이름", 상대방="공격할 대상 유저", 상대아이템="상대방의 아이템 이름")
    async def attack_item(self, interaction: discord.Interaction, 내아이템: str, 상대방: discord.Member, 상대아이템: str):
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
            
        xp_cog = self.bot.get_cog("XPLeaderboardCog")
        if xp_cog:
            await xp_cog.process_command_xp(interaction)
            
        user_id = str(interaction.user.id)
        target_id = str(상대방.id)
        
        if user_id == target_id:
            return await interaction.response.send_message("❌ 본인의 아이템은 공격할 수 없습니다!", ephemeral=True)

        my_item = self.enhancement_data.get_existing_item_data(내아이템, user_id)
        if not my_item:
            return await interaction.response.send_message(f"❌ **{내아이템}** 아이템을 소유하고 있지 않습니다.", ephemeral=True)

        target_item = self.enhancement_data.get_existing_item_data(상대아이템, target_id)
        if not target_item:
            return await interaction.response.send_message(f"❌ **{상대방.display_name}**님은 **{상대아이템}** 아이템을 소유하고 있지 않습니다.", ephemeral=True)

        if my_item['level'] <= 0:
            return await interaction.response.send_message(f"❌ Lv.0 아이템으로는 공격할 수 없습니다.", ephemeral=True)

        tier_info = get_level_tier_info(my_item['level'])
        tier_name = tier_info['tier']
        
        attack_limits = {
            "챌린저": 1,
            "그랜드마스터": 2,
            "마스터": 2,
            "플래티넘": 3,
            "골드": 5
        }
        
        if tier_name in attack_limits:
            max_daily = attack_limits[tier_name]
            today = datetime.now().strftime("%Y-%m-%d")
            
            if "last_attack_date" not in my_item: my_item["last_attack_date"] = today
            if "daily_attack_count" not in my_item: my_item["daily_attack_count"] = 0
            
            if my_item["last_attack_date"] != today:
                my_item["last_attack_date"] = today
                my_item["daily_attack_count"] = 0
            
            if my_item["daily_attack_count"] >= max_daily:
                return await interaction.response.send_message(
                    f"🚫 **공격 제한:** {tier_name} 등급은 하루에 **{max_daily}회**만 공격 가능합니다.\n내일 다시 시도하세요!", 
                    ephemeral=True
                )

        my_success_rate = get_success_rate(my_item['level'])
        attack_success_rate = 100.0 - my_success_rate 
        
        if "attack_fail_stack" not in my_item: my_item["attack_fail_stack"] = 0
        if "last_tier" not in my_item: my_item["last_tier"] = tier_name

        if my_item["last_tier"] != tier_name:
            my_item["attack_fail_stack"] = 0
            my_item["last_tier"] = tier_name

        roll = random.uniform(0, 100)
        level_change = random.randint(1, 10)
        embed = discord.Embed(title="⚔️ 아이템 공격 결과", color=discord.Color.red())
        
        if roll <= attack_success_rate:
            old_target_level = target_item['level']
            actual_lost = min(old_target_level, level_change) # 안전 하락
            target_item['level'] = old_target_level - actual_lost
            target_item['total_levels_lost'] = int(target_item.get('total_levels_lost', 0)) + actual_lost # ✅ 공격 피격 하락치도 누적
            my_item["attack_fail_stack"] = 0 
            
            result_msg = f"💥 **공격 성공!**\n**{상대방.display_name}**의 **{상대아이템}** 레벨이 **-{actual_lost}** 하락했습니다."
            
            if old_target_level > 0 and target_item['level'] <= 0:
                item_key = f"{target_id}_{상대아이템.lower()}"
                if item_key in self.enhancement_data.data["items"]:
                    del self.enhancement_data.data["items"][item_key]
                result_msg += f"\n💀 **[파괴]** 레벨이 0이 되어 아이템이 소멸했습니다!"
            
            embed.add_field(name="✅ 결과: 성공", value=result_msg, inline=False)
            embed.color = discord.Color.green()
        else:
            old_my_level = my_item['level']
            actual_lost = min(old_my_level, level_change) # 안전 하락
            my_item['level'] = old_my_level - actual_lost
            my_item['total_levels_lost'] = int(my_item.get('total_levels_lost', 0)) + actual_lost # ✅ 반동 하락치도 하락 누적에 기록
            my_item["attack_fail_stack"] += 1
            
            fail_msg = f"🛡️ **공격 실패 (반동 저항)**\n내 **{내아이템}** 레벨이 **-{actual_lost}** 하락했습니다."
            
            if my_item["attack_fail_stack"] >= 5:
                item_key = f"{user_id}_{내아이템.lower()}"
                if item_key in self.enhancement_data.data["items"]:
                    del self.enhancement_data.data["items"][item_key]
                fail_msg = f"💀 **[아이템 파괴]**\n공격 연속 **5회 실패**로 아이템이 파괴되었습니다!"
                embed.color = discord.Color.dark_red()
            else:
                embed.add_field(name="⚠️ 파괴 경고", value=f"현재 등급 내 연속 실패: **{my_item['attack_fail_stack']}/5**", inline=False)
            
            embed.add_field(name="❌ 결과: 실패", value=fail_msg, inline=False)

        if tier_name in attack_limits:
            my_item["daily_attack_count"] += 1
            embed.add_field(name="📅 남은 공격 횟수", value=f"**{max_daily - my_item['daily_attack_count']}회** / {max_daily}회", inline=True)

        embed.add_field(name="📊 확률", value=f"성공률: **{attack_success_rate:.1f}%**", inline=True)
        self.enhancement_data.save_data()
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화정보", description="강화 시스템에 대한 정보를 확인합니다.")
    async def enhancement_info(self, interaction: discord.Interaction):
        config_cog = self.bot.get_cog("ChannelConfig")
        is_allowed = True
        if config_cog:
            is_allowed = await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 게임 사용이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="⚒️ 순수 강화 시스템",
            description="🎲 **완전 무료 랜덤 레벨 변동 시스템 (보상 없음)**",
            color=discord.Color.purple()
        )
        
        embed.add_field(
            name="🎯 기본 규칙",
            value="• 각 아이템별로 독립적인 강화\n• 30초 쿨다운 (아이템별)\n• 1~5레벨 랜덤 변동\n• **완전 무료, 보상 없음**",
            inline=False
        )
        
        embed.add_field(
            name="📊 확률 시스템",
            value="• 레벨이 높을수록 성공률 감소\n• 레벨 10 이하는 강등 없음 (안전구간)\n• 연속 5회 실패 시 다음 강화는 **성공 보장**",
            inline=False
        )
        
        embed.add_field(
            name="🏆 등급 시스템",
            value="• **기본** (1-50)\n• **아이언** (51-150)\n• **브론즈** (151-250)\n• **실버** (251-350)\n• **골드** (351-450)\n• **플래티넘** (451-600)\n• **마스터** (601-750)\n• **그랜드마스터** (751-950)\n• **챌린저** (951~1000): 최고 등급",
            inline=False
        )
        
        embed.add_field(
            name="🎮 사용법",
            value="`/강화 아이템명` - 아이템 강화\n`/내강화` - 내 아이템 목록\n`/강화순위` - 전체 순위\n`/공격` - 아이템 공격 (골드 등급 이상)\n`/강화정보` - 시스템 정보",
            inline=False
        )
        
        embed.set_footer(text="각 아이템마다 다른 이름으로 여러 개 강화 가능! • 기존 시스템과 완전 독립")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화초기화", description="[관리자 전용] 모든 강화 데이터를 초기화합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    async def reset_enhancement(self, interaction: discord.Interaction):
        try:
            total_items = len(self.enhancement_data.data.get("items", {}))
            server_stats = self.enhancement_data.get_server_stats()
            
            if total_items == 0:
                return await interaction.response.send_message(
                    "ℹ️ 초기화할 강화 데이터가 없습니다.",
                    ephemeral=True
                )
            
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

async def setup(bot):
    await bot.add_cog(EnhancementSystemCog(bot))