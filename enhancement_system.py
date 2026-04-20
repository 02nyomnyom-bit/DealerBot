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
import string
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
                    
                    if "event_codes" not in data or not isinstance(data["event_codes"], dict):
                        data["event_codes"] = {}
                        
                    if "user_buffs" not in data or not isinstance(data["user_buffs"], dict):
                        data["user_buffs"] = {}
                    
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
            "event_codes": {},
            "user_buffs": {},
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
            
            # 만료된 코드 정리
            self.clean_expired_codes()
            
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

    def generate_event_code(self, creator_id: str, item_name: str) -> str:
        """3시간 유효한 히든 이벤트 코드 생성 (아이템 정보 포함)"""
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        expires_at = (datetime.now() + timedelta(hours=3)).isoformat()
        
        if "event_codes" not in self.data:
            self.data["event_codes"] = {}
            
        self.data["event_codes"][code] = {
            "creator_id": creator_id,
            "item_name": item_name,
            "expires_at": expires_at,
            "used_by": []
        }
        self.save_data()
        return code

    def verify_event_code(self, code: str, user_id: str) -> Tuple[bool, str]:
        """코드 검증 및 랜덤 버프 지급"""
        if "event_codes" not in self.data or code not in self.data["event_codes"]:
            return False, "❌ 존재하지 않거나 유효하지 않은 코드입니다."
            
        event = self.data["event_codes"][code]
        
        if event.get("creator_id") != user_id:
            return False, "🚫 **권한 없음:** 이 코드는 본인이 직접 획득한 코드가 아니므로 사용할 수 없습니다."
            
        target_item_name = event.get("item_name")
        item_key = f"{user_id}_{target_item_name.lower()}"
        if item_key not in self.data.get("items", {}):
            return False, f"❌ **아이템 상실:** 코드를 획득했던 아이템(**{target_item_name}**)을 더 이상 보유하고 있지 않아 인증이 불가능합니다."

        try:
            expires_at = datetime.fromisoformat(event["expires_at"])
        except Exception:
            return False, "❌ 코드 데이터 형식 오류입니다."
            
        if datetime.now() > expires_at:
            return False, "⏰ 해당 코드는 이미 만료되었습니다 (3시간 경과)."
            
        if user_id in event.get("used_by", []):
            return False, "🚫 이미 사용하신 코드입니다."
            
        # --- 랜덤 버프 로직 ---
        buff_type = random.choice(["SUCCESS_BOOST", "ATTACK_SHIELD", "ENHANCE_BAN_RIGHT"])
        buff_msg = ""
        
        if "user_buffs" not in self.data:
            self.data["user_buffs"] = {}
        if user_id not in self.data["user_buffs"]:
            self.data["user_buffs"][user_id] = {"ban_rights": 0, "success_boost_until": None}
            
        item_data = self.data["items"][item_key]
        
        if buff_type == "SUCCESS_BOOST":
            until = (datetime.now() + timedelta(hours=1)).isoformat()
            self.data["user_buffs"][user_id]["success_boost_until"] = until
            buff_msg = "✨ **[버프 획득] 1시간 동안 성공 확률 10% 상승!**\n지금 바로 강화를 시도해보세요!"
        elif buff_type == "ATTACK_SHIELD":
            item_data["shield_count"] = item_data.get("shield_count", 0) + 1
            buff_msg = f"🛡️ **[아이템 강화] 공격 1회 방어권 획득!**\n아이템 **{target_item_name}**이(가) 다음 공격을 1회 무효화합니다."
        elif buff_type == "ENHANCE_BAN_RIGHT":
            self.data["user_buffs"][user_id]["ban_rights"] = self.data["user_buffs"][user_id].get("ban_rights", 0) + 1
            buff_msg = "🚫 **[권한 획득] 상대지정 1시간 강화 이용금지권!**\n`/강화금지 @유저` 명령어로 상대를 1시간 동안 강화 불가능 상태로 만듭니다."

        event.setdefault("used_by", []).append(user_id)
        self.save_data()
        return True, f"✅ **히든 이벤트 인증 성공!**\n\n{buff_msg}\n\n*아이템: {target_item_name}*"

    def clean_expired_codes(self):
        """만료된 코드 삭제 (데이터 파일 관리용)"""
        if "event_codes" not in self.data:
            return
            
        current_time = datetime.now()
        to_delete = []
        for code, info in self.data["event_codes"].items():
            try:
                expires_at = datetime.fromisoformat(info["expires_at"])
                if current_time > expires_at:
                    to_delete.append(code)
            except Exception:
                to_delete.append(code)
        
        for code in to_delete:
            del self.data["event_codes"][code]

    def get_item_data(self, item_name: str, owner_id: str, owner_name: str, guild_id: str) -> Dict:
        """아이템 데이터 조회/생성"""
        item_key = f"{owner_id}_{item_name.lower()}"
        
        if not isinstance(self.data, dict):
            self.data = self._create_default_data()
        
        if "items" not in self.data or not isinstance(self.data["items"], dict):
            self.data["items"] = {}
        
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
                "total_levels_gained": 0,
                "total_levels_lost": 0,
                "created_at": datetime.now().isoformat(),
                "last_attempt": None,
                "consecutive_fails": 0,
                "shield_count": 0
            }
        
        # 보정
        item = self.data["items"][item_key]
        for field in ["downgrade_count", "total_levels_gained", "total_levels_lost", "shield_count"]:
            if field not in item: item[field] = 0
            
        return item

    def get_existing_item_data(self, item_name: str, owner_id: str) -> Optional[Dict]:
        item_key = f"{owner_id}_{item_name.lower()}"
        return self.data.get("items", {}).get(item_key)

    def attempt_enhancement(self, item_name: str, owner_id: str, owner_name: str, guild_id: str) -> Tuple:
        try:
            # 강화 금지 체크
            buffs = self.data.get("user_buffs", {}).get(owner_id, {})
            banned_until = buffs.get("banned_until")
            if banned_until and datetime.now() < datetime.fromisoformat(banned_until):
                remaining = (datetime.fromisoformat(banned_until) - datetime.now()).total_seconds()
                return False, 0, 0, 0, 0, f"BANNED_{int(remaining//60)}", 0, 0

            item_data = self.get_item_data(item_name, owner_id, owner_name, guild_id)
            current_level = int(item_data.get("level", 0))
            
            if current_level >= ENHANCEMENT_CONFIG["max_level"]:
                return False, current_level, current_level, 0, 0, "최대 레벨", 0, 0
            
            success_rate = get_success_rate(current_level)
            
            # 확률 보정 버프
            boost_until = buffs.get("success_boost_until")
            if boost_until and datetime.now() < datetime.fromisoformat(boost_until):
                success_rate += 10.0
                
            downgrade_rate = get_downgrade_rate(current_level)
            consec_fail = item_data.get("consecutive_fails", 0)

            if consec_fail >= 5:
                result_type = "success"
            else:
                roll = random.randint(1, 10000)
                success_threshold = success_rate * 100
                downgrade_threshold = success_threshold + (downgrade_rate * 100)
                
                if roll <= success_threshold: result_type = "success"
                elif roll <= downgrade_threshold: result_type = "downgrade"
                else: result_type = "fail"

            item_data["total_attempts"] += 1
            item_data["last_attempt"] = datetime.now().isoformat()
            self.data["server_stats"]["total_attempts"] += 1

            level_change = 0
            if result_type == "success":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                item_data["level"] += level_change
                item_data["success_count"] += 1
                item_data["total_levels_gained"] += level_change
                item_data["consecutive_fails"] = 0
                if item_data["level"] > self.data["server_stats"]["highest_level"]:
                    self.data["server_stats"]["highest_level"] = item_data["level"]
                self.data["server_stats"]["total_successes"] += 1
                record_enhancement_attempt(owner_id, owner_name, True)
            elif result_type == "downgrade":
                level_change = random.randint(*ENHANCEMENT_CONFIG["level_change_range"])
                actual_lost = min(current_level, level_change)
                item_data["level"] -= actual_lost
                item_data["total_levels_lost"] += actual_lost
                item_data["consecutive_fails"] += 1
                item_data["downgrade_count"] += 1
                level_change = -actual_lost
                record_enhancement_attempt(owner_id, owner_name, False)
            else:
                item_data["consecutive_fails"] += 1
                record_enhancement_attempt(owner_id, owner_name, False)

            self.backup_counter += 1
            if self.backup_counter >= ENHANCEMENT_CONFIG["backup_interval"]:
                self.save_data()
                self.backup_counter = 0

            return (result_type == "success", current_level, item_data["level"], success_rate, 
                    downgrade_rate, result_type, level_change, item_data["consecutive_fails"])
        except Exception as e:
            print(f"❌ 강화 시도 중 오류: {e}")
            return False, 0, 0, 0, 0, "오류", 0, 0

    def get_user_items(self, user_id: str) -> List[Dict]:
        user_items = [v for k, v in self.data.get("items", {}).items() if v.get("owner_id") == user_id]
        user_items.sort(key=lambda x: int(x.get("level", 0)), reverse=True)
        return user_items

    def get_server_stats(self) -> Dict:
        return self.data.get("server_stats", {}).copy()

    def get_top_items(self, guild_id: str, limit: int = 10) -> List[Dict]:
        items = [v for v in self.data.get("items", {}).values() if v.get("guild_id") == guild_id]
        items.sort(key=lambda x: int(x.get("level", 0)), reverse=True)
        return items[:limit]

enhancement_data = EnhancementDataManager()
enhancement_cooldowns = {}

def check_cooldown(user_id: str, item_name: str) -> Tuple[bool, int]:
    key = f"{user_id}_{item_name.lower()}"
    now = time.time()
    if key in enhancement_cooldowns:
        rem = ENHANCEMENT_CONFIG["cooldown_time"] - (now - enhancement_cooldowns[key])
        if rem > 0: return False, int(rem)
    enhancement_cooldowns[key] = now
    return True, 0

class EnhancementSystemCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.enhancement_data = enhancement_data

    @app_commands.command(name="강화", description="아이템을 강화합니다.")
    async def enhance_item(self, interaction: discord.Interaction, 아이템명: str):
        config_cog = self.bot.get_cog("ChannelConfig")
        if config_cog and not await config_cog.check_permission(interaction.channel_id, "enhancement", interaction.guild.id):
            return await interaction.response.send_message("🚫 허용되지 않은 채널입니다.", ephemeral=True)
        
        user_id, guild_id, username = str(interaction.user.id), str(interaction.guild_id), interaction.user.display_name
        
        if not self.enhancement_data.get_existing_item_data(아이템명, user_id):
            if len(self.enhancement_data.get_user_items(user_id)) >= ENHANCEMENT_CONFIG["max_items_per_user"]:
                return await interaction.response.send_message("❎ 아이템 보유 한도를 초과했습니다.", ephemeral=True)
        
        can, rem = check_cooldown(user_id, 아이템명)
        if not can: return await interaction.response.send_message(f"⏰ {아이템명} 쿨다운 중 ({rem}초)", ephemeral=True)
        
        res = self.enhancement_data.attempt_enhancement(아이템명, user_id, username, guild_id)
        if res[5].startswith("BANNED_"):
            return await interaction.response.send_message(f"🚫 강화 금지 상태입니다. ({res[5].split('_')[1]}분 남음)", ephemeral=True)
        
        success, old_lv, new_lv, rate, d_rate, r_type, change, c_fails = res
        tier = get_level_tier_info(new_lv)
        item_data = self.enhancement_data.get_item_data(아이템명, user_id, username, guild_id)
        
        embed = discord.Embed(title="강화 결과", color=tier["color"])
        if r_type == "success":
            embed.title = "✅ 강화 성공!"
            if random.random() * 100 <= ENHANCEMENT_CONFIG["special_reward_chance"]:
                code = self.enhancement_data.generate_event_code(user_id, 아이템명)
                embed.add_field(name="🎁 히든 이벤트 발생!", value=f"코드: `{code}` (3시간 유효)\n`/강화이벤트 코드:{code}`로 버프를 받으세요!", inline=False)
        elif r_type == "downgrade": embed.title = "💥 강화 실패 (강등)"
        elif r_type == "최대 레벨": return await interaction.response.send_message("👑 최대 레벨입니다.")
        else: embed.title = "❌ 강화 실패"
        
        embed.add_field(name="아이템", value=f"**{아이템명}**", inline=False)
        embed.add_field(name="레벨 변화", value=f"Lv{old_lv} → **Lv{new_lv}** ({change:+})", inline=True)
        embed.add_field(name="상태", value=f"🎯 시도: {item_data['total_attempts']}회 | 🛡️ 방어막: {item_data.get('shield_count', 0)}회", inline=False)
        
        if c_fails >= 3: embed.add_field(name="🛡️ 연속 실패 보호", value=f"현재 {c_fails}/5회 실패 (5회 시 성공 보장)")
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화이벤트", description="히든 이벤트 코드를 인증하여 랜덤 버프를 받습니다.")
    @app_commands.describe(코드="발급받은 히든 이벤트 코드")
    async def use_event_code(self, interaction: discord.Interaction, 코드: str):
        user_id = str(interaction.user.id)
        if not self.enhancement_data.get_user_items(user_id):
            return await interaction.response.send_message("❌ 아이템 소지자만 사용 가능합니다.", ephemeral=True)
            
        success, message = self.enhancement_data.verify_event_code(코드, user_id)
        await interaction.response.send_message(message, ephemeral=not success)

    @app_commands.command(name="강화금지", description="상대방을 1시간 동안 강화 불가능 상태로 만듭니다. (권한 소모)")
    @app_commands.describe(상대방="강화를 금지할 유저")
    async def ban_user_enhancement(self, interaction: discord.Interaction, 상대방: discord.Member):
        user_id, target_id = str(interaction.user.id), str(상대방.id)
        if user_id == target_id: return await interaction.response.send_message("❌ 본인에게는 사용 불가!", ephemeral=True)
        
        buffs = self.enhancement_data.data.get("user_buffs", {}).get(user_id, {})
        rights = buffs.get("ban_rights", 0)
        if rights <= 0: return await interaction.response.send_message("❌ 이용금지권이 없습니다.", ephemeral=True)
        
        self.enhancement_data.data["user_buffs"][user_id]["ban_rights"] = rights - 1
        if target_id not in self.enhancement_data.data["user_buffs"]:
            self.enhancement_data.data["user_buffs"][target_id] = {"ban_rights": 0, "success_boost_until": None}
        
        self.enhancement_data.data["user_buffs"][target_id]["banned_until"] = (datetime.now() + timedelta(hours=1)).isoformat()
        self.enhancement_data.save_data()
        
        await interaction.response.send_message(f"🚫 **{상대방.display_name}**님을 1시간 동안 강화 금지 시켰습니다! (남은 권한: {rights-1}개)")

    @app_commands.command(name="내강화", description="내 아이템 목록을 확인합니다.")
    async def my_items(self, interaction: discord.Interaction):
        items = self.enhancement_data.get_user_items(str(interaction.user.id))
        buffs = self.enhancement_data.data.get("user_buffs", {}).get(str(interaction.user.id), {})
        
        embed = discord.Embed(title="📦 내 아이템 및 버프", color=discord.Color.blue())
        if not items: embed.description = "보유 아이템 없음"
        else:
            for item in items[:10]:
                embed.add_field(name=f"Lv{item['level']} {item['item_name']}", 
                                value=f"🛡️ 방어막: {item.get('shield_count', 0)}회", inline=True)
        
        ban_rights = buffs.get("ban_rights", 0)
        boost_until = buffs.get("success_boost_until")
        boost_msg = "없음"
        if boost_until and datetime.now() < datetime.fromisoformat(boost_until):
            rem = (datetime.fromisoformat(boost_until) - datetime.now()).total_seconds()
            boost_msg = f"활성 중 ({int(rem//60)}분 남음)"
            
        embed.add_field(name="🎁 보유 권한/버프", 
                        value=f"• 이용금지권: {ban_rights}개\n• 확률업: {boost_msg}", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="공격", description="상대방의 아이템을 공격합니다.")
    async def attack_item(self, interaction: discord.Interaction, 내아이템: str, 상대방: discord.Member, 상대아이템: str):
        user_id, target_id = str(interaction.user.id), str(상대방.id)
        my_item = self.enhancement_data.get_existing_item_data(내아이템, user_id)
        target_item = self.enhancement_data.get_existing_item_data(상대아이템, target_id)
        
        if not my_item or not target_item: return await interaction.response.send_message("❌ 아이템을 찾을 수 없습니다.", ephemeral=True)
        
        # 방어막 체크
        if target_item.get("shield_count", 0) > 0:
            target_item["shield_count"] -= 1
            self.enhancement_data.save_data()
            return await interaction.response.send_message(f"🛡️ **{상대방.display_name}**의 방어막이 공격을 막아냈습니다! (남은 방어막: {target_item['shield_count']}회)")
        
        rate = 100.0 - get_success_rate(my_item['level'])
        if random.uniform(0, 100) <= rate:
            lost = random.randint(1, 10)
            target_item['level'] = max(0, target_item['level'] - lost)
            msg = f"💥 공격 성공! **{상대방.display_name}**의 레벨이 {lost} 하락했습니다."
            if target_item['level'] == 0:
                del self.enhancement_data.data["items"][f"{target_id}_{상대아이템.lower()}"]
                msg += " (아이템 파괴!)"
            await interaction.response.send_message(msg)
        else:
            lost = random.randint(1, 5)
            my_item['level'] = max(0, my_item['level'] - lost)
            await interaction.response.send_message(f"🛡️ 공격 실패! 내 아이템 레벨이 {lost} 하락했습니다.")
        self.enhancement_data.save_data()

    @app_commands.command(name="강화정보", description="강화 시스템 정보를 확인합니다.")
    async def info(self, interaction: discord.Interaction):
        embed = discord.Embed(title="⚒️ 강화 시스템 정보", color=discord.Color.purple())
        embed.add_field(name="🎮 명령어", value="`/강화`, `/내강화`, `/공격`, `/강화금지`, `/강화이벤트`, `/강화순위`", inline=False)
        embed.add_field(name="🎁 히든 이벤트 버프", value="• **확률업**: 1시간 동안 성공확률 +10%\n• **방어권**: 상대의 공격을 1회 자동 방어\n• **금지권**: 지정한 유저를 1시간 동안 강화 불가 상태로 만듦", inline=False)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화순위", description="전체 순위를 확인합니다.")
    async def ranking(self, interaction: discord.Interaction):
        top = self.enhancement_data.get_top_items(str(interaction.guild_id))
        embed = discord.Embed(title="🏆 강화 순위", color=discord.Color.gold())
        for i, item in enumerate(top[:10], 1):
            embed.add_field(name=f"{i}위. {item['item_name']}", value=f"Lv{item['level']} ({item['owner_name']})", inline=True)
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="강화초기화", description="[관리자] 모든 데이터를 초기화합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    async def reset(self, interaction: discord.Interaction):
        self.enhancement_data.data = self.enhancement_data._create_default_data()
        self.enhancement_data.save_data()
        await interaction.response.send_message("✅ 모든 강화 데이터가 초기화되었습니다.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(EnhancementSystemCog(bot))
