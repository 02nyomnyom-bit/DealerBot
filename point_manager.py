# point_manager.py - 포인트 시스템
from __future__ import annotations
import discord
from discord import app_commands, Interaction, Member, User
from discord.ext import commands
from typing import Optional, Dict, List, Union
import asyncio
import json
import os
from datetime import datetime, timedelta, timezone
import traceback

# --- 시간대 설정 ---
KST = timezone(timedelta(hours=9), 'KST')

# 안전한 데이터베이스 매니저 import
try:
    from database_manager import DatabaseManager, get_guild_db_manager
    DATABASE_AVAILABLE = True
    print("✅ DatabaseManager를 성공적으로 불러왔습니다.")
except ImportError as e:
    print(f"⚠️ DatabaseManager를 찾을 수 없습니다: {e}")
    DATABASE_AVAILABLE = False
    
    class MockDatabaseManager:
        def __init__(self):
            self.users = {}
            print("⚠️ Mock 데이터베이스를 사용합니다. 실제 저장되지 않습니다!")
        
        def create_user(self, user_id, username='', display_name='', initial_cash=0):
            try:
                self.users[user_id] = {
                    'cash': initial_cash, 
                    'username': username, 
                    'display_name': display_name,
                    'user_id': user_id  # user_id도 명시적으로 추가
                }
                print(f"[MOCK] 사용자 생성 성공: {user_id} - {display_name} ({initial_cash}원)")
                return True
            except Exception as e:
                print(f"[MOCK] 사용자 생성 실패: {e}")
                return False
        
        def get_user(self, user_id):
            user = self.users.get(user_id)
            print(f"[MOCK] 사용자 조회: {user_id} -> {user}")
            return user
        
        def get_user_cash(self, user_id):
            cash = self.users.get(user_id, {}).get('cash', 0)
            print(f"[MOCK] 현금 조회: {user_id} -> {cash}원")
            return cash
        
        def update_user_cash(self, user_id, amount):
            if user_id in self.users:
                self.users[user_id]['cash'] = amount
                print(f"[MOCK] 현금 설정: {user_id} -> {amount}원")
                return True
            else:
                print(f"[MOCK] 사용자를 찾을 수 없음: {user_id}")
                return False
        
        def add_user_cash(self, user_id, amount):
            current = self.get_user_cash(user_id)
            new_amount = current + amount
            
            if self.update_user_cash(user_id, new_amount):
                print(f"[MOCK] 현금 추가 성공: {user_id} -> +{amount}원 (총 {new_amount}원)")
                return new_amount
            else:
                print(f"[MOCK] 현금 추가 실패: {user_id}")
                return current
        
        def add_transaction(self, user_id, t_type, amount, desc=''):
            print(f"[MOCK] 거래 기록: {user_id} - {t_type}: {amount}원 ({desc})")
            # Mock에서는 거래 기록을 실제로 저장하지 않음
            return True
        
        def get_user_transactions(self, user_id, limit=50):
            print(f"[MOCK] 거래 내역 조회: {user_id}")
            # Mock에서는 빈 리스트 반환
            return []
        
        def delete_user(self, user_id):
            if user_id in self.users:
                del self.users[user_id]
                print(f"[MOCK] 사용자 삭제: {user_id}")
                return {'users': 1}
            return {'users': 0}
        
        def execute_query(self, query, params=(), fetch_type='all'):
            print(f"[MOCK] 쿼리 실행: {query}")
            if 'SELECT user_id, cash FROM users' in query:
                # 현금 순위 조회를 위한 Mock 데이터 반환
                return [{'user_id': uid, 'cash': data['cash'], 'username': data['username'], 'display_name': data['display_name']} 
                       for uid, data in self.users.items() if data['cash'] > 0]
            return []

# 선물 설정 파일 경로
GIFT_SETTINGS_FILE = "data/gift_settings.json"

def format_money(amount: int) -> str:
    """돈 형식 포맷"""
    return f"{amount:,}원"

class GiftSettings:
    """선물 시스템 설정 클래스"""
    def __init__(self):
        self.settings = self.load_settings()
    
    def load_settings(self) -> Dict:
        """설정 로드"""
        default = {
            "fee_rate": 0.1,  # 10% 수수료
            "min_amount": 100,
            "max_amount": 1000000,
            "daily_limit": 5,
            "cooldown_minutes": 30
        }
        
        if os.path.exists(GIFT_SETTINGS_FILE):
            try:
                with open(GIFT_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default.update(loaded)
                print("✅ 선물 설정 로드 완료")
            except Exception as e:
                print(f"⚠️ 선물 설정 로드 실패: {e}")
        else:
            print("⚠️ 선물 설정 파일이 없습니다. 기본값을 사용합니다.")
        
        return default
    
    def save_settings(self):
        """설정 저장"""
        os.makedirs(os.path.dirname(GIFT_SETTINGS_FILE), exist_ok=True)
        try:
            with open(GIFT_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            print("✅ 선물 설정 저장 완료")
            return True
        except Exception as e:
            print(f"❌ 선물 설정 저장 실패: {e}")
            return False

class LeaveConfirmView(discord.ui.View):
    def __init__(self, user_id: str, db, target_name: str):
        super().__init__(timeout=30)
        self.user_id = user_id
        self.db = db
        self.target_name = target_name

    @discord.ui.button(label="✅ 탈퇴하기", style=discord.ButtonStyle.danger)
    async def confirm_leave(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # 1. 역할 제거 로직 추가
            member = interaction.guild.get_member(int(self.user_id))
            removed_roles_count = 0
            
            if member:
                # @everyone을 제외한 모든 역할 필터링 (위치 기반으로 봇보다 높은 역할은 제거 불가)
                roles_to_remove = [role for role in member.roles if not role.is_default()]
                if roles_to_remove:
                    try:
                        await member.remove_roles(*roles_to_remove, reason="포인트 시스템 자발적 탈퇴")
                        removed_roles_count = len(roles_to_remove)
                    except discord.Forbidden:
                        print(f"⚠️ {self.target_name}의 역할을 제거할 권한이 없습니다.")
                    except Exception as e:
                        print(f"⚠️ 역할 제거 중 오류 발생: {e}")

            # 2. 데이터베이스 사용자 삭제 실행
            self.db.delete_user(self.user_id)
            
            # 3. 결과 알림
            role_msg = f" 및 {removed_roles_count}개의 역할이 회수" if removed_roles_count > 0 else ""
            embed = discord.Embed(
                title="👋 탈퇴 완료",
                description=f"{self.target_name}님의 모든 데이터가 삭제{role_msg}되었습니다.\n언제든지 다시 가입할 수 있습니다.",
                color=discord.Color.red()
            )
            await interaction.response.edit_message(embed=embed, view=None)
            print(f"✅ 사용자 수동 탈퇴 및 역할 제거: {self.target_name} ({self.user_id})")

        except Exception as e:
            print(f"❌ 탈퇴 처리 중 오류: {e}")
            if not interaction.response.is_done():
                await interaction.response.send_message(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)
            else:
                await interaction.edit_original_response(content=f"❌ 오류 발생: {e}", embed=None, view=None)
    async def on_timeout(self):
        self.stop()

class PointManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.db_managers: Dict[str, DatabaseManager] = {}
        self.gift_settings = GiftSettings()
        self.user_cooldowns: Dict[str, datetime] = {}
        # 일일 선물 횟수 저장을 위한 새로운 데이터 구조
        # {'user_id': {'date': 'YYYY-MM-DD', 'count': 5}}
        self.daily_gift_counts: Dict[str, Dict[str, Union[str, int]]] = {}
        
        # DatabaseManager 확인
        self.DATABASE_AVAILABLE = True
        try:
            _ = DatabaseManager(guild_id="temp_check") 
        except Exception:
            self.DATABASE_AVAILABLE = False
        
        print(f"📊 데이터베이스 상태: {'실제 DB' if self.DATABASE_AVAILABLE else 'Mock DB'}")
        print("✅ 통합 포인트 관리 시스템 + 고급 선물 시스템 초기화 완료")

    def _get_db(self, guild_id: Optional[int]) -> Union[DatabaseManager, MockDatabaseManager]:
        if guild_id is None:
            print("⚠️ guild_id가 None입니다. MockDatabaseManager를 반환합니다.")
            return MockDatabaseManager() # Fallback for DMs or unexpected None
        
        guild_id_str = str(guild_id)
        if guild_id_str not in self.db_managers:
            if self.DATABASE_AVAILABLE:
                try:
                    self.db_managers[guild_id_str] = DatabaseManager(guild_id=guild_id_str)
                    print(f"✅ 길드 {guild_id_str}에 대한 DatabaseManager 인스턴스 생성 완료.")
                except Exception as e:
                    print(f"❌ 길드 {guild_id_str}에 대한 DatabaseManager 인스턴스 생성 실패: {e}")
                    print(f"상세 오류:\n{traceback.format_exc()}")
                    print(f"⚠️ 길드 {guild_id_str}에 대해 Mock 데이터베이스로 대체합니다.")
                    self.db_managers[guild_id_str] = MockDatabaseManager()
            else:
                print(f"⚠️ DATABASE_AVAILABLE이 False입니다. 길드 {guild_id_str}에 대해 Mock 데이터베이스를 사용합니다.")
                self.db_managers[guild_id_str] = MockDatabaseManager()
        return self.db_managers[guild_id_str]

    def _get_daily_count(self, user_id: str) -> int:
        """오늘 선물 횟수를 KST 기준으로 조회하고, 날짜가 바뀌었으면 초기화합니다."""
        today_kst = datetime.now(KST).strftime('%Y-%m-%d')
        
        if user_id not in self.daily_gift_counts or self.daily_gift_counts[user_id].get('date') != today_kst:
            # 날짜가 다르거나, 기록이 없으면 새로 생성
            self.daily_gift_counts[user_id] = {'date': today_kst, 'count': 0}
        
        return self.daily_gift_counts[user_id]['count']

    def _increment_daily_count(self, user_id: str):
        """일일 선물 횟수를 KST 기준으로 1 증가시킵니다."""
        # _get_daily_count를 호출하여 리셋 로직을 먼저 수행
        current_count = self._get_daily_count(user_id)
        self.daily_gift_counts[user_id]['count'] = current_count + 1

    def _check_cooldown(self, user_id: str) -> Optional[int]:
        """쿨다운 체크 (KST 기준)"""
        if user_id in self.user_cooldowns:
            # 모든 시간을 KST 기준으로 통일하여 계산
            now_kst = datetime.now(KST)
            cooldown_end_time = self.user_cooldowns[user_id]
            
            if now_kst < cooldown_end_time:
                remaining = cooldown_end_time - now_kst
                return int(remaining.total_seconds())
        return None

    def _set_cooldown(self, user_id: str):
        """쿨다운 설정 (KST 기준)"""
        now_kst = datetime.now(KST)
        cooldown_duration = timedelta(minutes=self.gift_settings.settings["cooldown_minutes"])
        self.user_cooldowns[user_id] = now_kst + cooldown_duration

    # 기본 포인트 관리 명령어들
    # point_manager.py - updated register command

    @app_commands.command(name="등록", description="서버의 멤버로 등록합니다.")
    async def register(self, interaction: Interaction):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'point_1' 권한이 있는지 체크 (channel_config.py의 value="point_1"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "point_1", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 등록이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        user_id = str(interaction.user.id)
        username = interaction.user.name
        display_name = interaction.user.display_name

        print(f"🔍 등록 시도 시작: {display_name} (ID: {user_id})")
        
        try:
            db = self._get_db(interaction.guild_id)
            # 기존 사용자 체크
            existing_user = db.get_user(user_id)
            print(f"🔍 기존 사용자 확인: {existing_user}")
            
            if existing_user:
                print(f"⚠️ 이미 등록된 사용자: {display_name}")
                await interaction.response.send_message("⚠️ 이미 등록된 사용자입니다!", ephemeral=True)
                return
            
            # 사용자 생성 (초기 현금 10,000원)
            print(f"📝 새 사용자 생성 시도: {display_name}")
            # create_user는 성공 시 True, 실패 시 False 또는 None 반환
            success = db.create_user(user_id, username, display_name, initial_cash=10000)
            
            created_user = db.get_user(user_id)
            if not created_user:
                # MockDB에서 False를 반환했지만 실제로는 유저가 생성되지 않은 경우
                print(f"❌ 사용자 생성 실패로 판단: created_user is None")
                await interaction.response.send_message(
                    "❌ 사용자 생성에 실패했습니다. 다시 시도해주세요.", 
                    ephemeral=True
                )
                return
            
            # 성공적으로 사용자 생성 확인
            print(f"✅ 사용자 생성 성공으로 판단: {created_user}")
            
            # 가입 보너스 거래 기록
            transaction_success = db.add_transaction(user_id, "회원가입", 10000, "신규 회원가입 보너스")
            print(f"📝 거래 기록 결과: {transaction_success}")
            
            # 최종 현금 확인
            final_cash = db.get_user_cash(user_id)
            print(f"💰 최종 현금 확인: {final_cash}원")
            embed = discord.Embed(
                title="🎉 환영합니다!",
                description=f"{display_name}님이 서버에 성공적으로 등록되었습니다!",
                color=discord.Color.green()
            )
            embed.add_field(name="💰 시작 현금", value="10,000원", inline=True)
            embed.add_field(
                name="📋 사용 가능한 명령어", 
                value="`/지갑` - 현재 잔액 확인\n`/선물` - 다른 사용자에게 현금 선물\n`/데이터베이스상태` - 시스템 상태 확인", 
                inline=False
            )
            embed.add_field(
                name="🔍 등록 상태", 
                value=f"데이터베이스: {'✅ 실제 DB' if DATABASE_AVAILABLE else '⚠️ 임시 DB'}\n현재 잔액: {final_cash:,}원", 
                inline=False
            )
            
            if not DATABASE_AVAILABLE:
                embed.add_field(
                    name="⚠️ 중요 안내",
                    value="현재 임시 데이터베이스를 사용 중입니다.\n봇 재시작 시 데이터가 사라질 수 있습니다.\n실제 DB 연결을 위해 database_manager.py를 확인하세요.",
                    inline=False
                )
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            print(f"✅ 등록 완료 응답 전송: {display_name}")
                
        except Exception as e:
            print(f"❌ 등록 처리 중 예외 발생: {e}")
            print(f"상세 오류:\n{traceback.format_exc()}")
            
            await interaction.response.send_message(
                f"❌ 등록 중 오류가 발생했습니다.\n오류: {str(e)}\n\n`/데이터베이스상태` 명령어로 시스템 상태를 확인해보세요.", 
                ephemeral=True
            )

    @app_commands.command(name="지갑", description="자신의 보유 현금 또는 다른 사용자의 현금을 확인합니다.")
    @app_commands.describe(
        대상자="[관리자 전용] 현금을 확인할 사용자",
        비공개="결과를 나만 볼지 여부 (기본값: 네)"
    )
    @app_commands.choices(비공개=[
        app_commands.Choice(name="네", value="True"),
        app_commands.Choice(name="아니오", value="False")
    ])
    async def wallet(self, interaction: Interaction, 대상자: Optional[Member] = None, 비공개: str = "True"):
        """지갑(보유 현금) 및 오늘 활동 확인 명령어"""
        
        # 1. 권한 체크: 다른 사용자를 볼 때는 관리자 권한 필요
        if 대상자 and 대상자 != interaction.user:
            if not interaction.user.guild_permissions.administrator:
                return await interaction.response.send_message(
                    "🚫 다른 사용자의 지갑 조회는 관리자만 가능합니다.", 
                    ephemeral=True
                )
        
        # 2. 비공개 설정 적용
        is_ephemeral = True if 비공개 == "True" else False
        await interaction.response.defer(ephemeral=is_ephemeral)
        
        target = 대상자 if 대상자 else interaction.user
        user_id = str(target.id)
        
        try:
            db = self._get_db(interaction.guild_id)
            user_id = str(target.id)
        
            # 사용자 데이터 조회
            user_data = db.get_user(user_id)
            
            if user_data:
            # 닉네임이 변경되었다면 실시간 업데이트
                if target.display_name != user_data.get('display_name'):
                    db.execute_query(
                        'UPDATE users SET display_name = ?, username = ? WHERE user_id = ? AND guild_id = ?',
                        (target.display_name, target.name, user_id, str(interaction.guild.id))
                    )

            # 4. 사용자 데이터 조회
            user_data = db.get_user(user_id)
            
            if not user_data:
                embed = discord.Embed(
                    title="❌ 조회 실패",
                    description=f"{target.display_name}님은 아직 서비스에 등록되지 않았습니다.\n`/등록` 명령어를 먼저 사용해주세요.",
                    color=discord.Color.red()
                )
                return await interaction.followup.send(embed=embed)

            # 5. 오늘 보낸 선물 횟수 계산 (KST 기준)
            today_str = datetime.now(KST).strftime('%Y-%m-%d')

            gift_count_query = """
                SELECT COUNT(*) as count 
                FROM point_history 
                WHERE user_id = ? AND transaction_type = '선물 보내기' AND DATE(created_at) = DATE(?)
            """
            
            gift_result = db.execute_query(gift_count_query, (user_id, today_str), 'one')
            today_gifts = gift_result['count'] if gift_result else 0
            
            # 6. 임베드 구성 및 전송
            cash = user_data.get('cash', 0)
            formatted_cash = f"{cash:,}원"
            
            embed = discord.Embed(
                title=f"💰 {target.display_name}님의 지갑",
                color=discord.Color.gold(),
                timestamp=datetime.now(KST)
            )
            
            embed.set_thumbnail(url=target.display_avatar.url)
            embed.add_field(name="💵 현재 잔액", value=f"**{formatted_cash}**", inline=True)
            embed.add_field(name="🎁 오늘 보낸 선물", value=f"**{today_gifts}회**", inline=True)
            
            if 대상자 and 대상자 != interaction.user:
                embed.set_footer(text=f"관리자 조회 모드 | 실행자: {interaction.user.display_name}")
            else:
                embed.set_footer(text="자정(00:00) 기준 선물 횟수가 초기화됩니다.")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"❌ 지갑 조회 중 오류 발생: {e}")
            traceback.print_exc()
            await interaction.followup.send("❌ 정보를 불러오는 중 오류가 발생했습니다.", ephemeral=True)   

    @app_commands.command(name="선물", description="다른 사용자에게 현금을 선물합니다.")
    @app_commands.describe(
        받는사람="현금을 받을 사용자",
        금액="선물할 현금 최소현금과 최대현금은 바뀔수있습니다."
    )
    async def gift(self, interaction: Interaction, 받는사람: Member, 금액: int):
        # 1. 중앙 설정 Cog(ChannelConfig) 가져오기
        config_cog = self.bot.get_cog("ChannelConfig")
    
        if config_cog:
        # 2. 현재 채널에 'point_2' 권한이 있는지 체크 (channel_config.py의 value="point_2"와 일치해야 함)
            is_allowed = await config_cog.check_permission(interaction.channel_id, "point_2", interaction.guild.id)
        
        if not is_allowed:
            return await interaction.response.send_message(
                "🚫 이 채널은 선물이 허용되지 않은 채널입니다.\n지정된 채널을 이용해 주세요!", 
                ephemeral=True
            )
        
        sender_id = str(interaction.user.id)
        receiver_id = str(받는사람.id)
        
        # 자기 자신에게 선물 방지
        if sender_id == receiver_id:
            await interaction.response.send_message("❌ 자기 자신에게는 선물할 수 없습니다.", ephemeral=True)
            return
        
        # 봇에게 선물 방지
        if 받는사람.bot:
            await interaction.response.send_message("❌ 봇에게는 선물할 수 없습니다.", ephemeral=True)
            return
        
        # 금액 유효성 검사
        settings = self.gift_settings.settings
        if 금액 < settings["min_amount"] or 금액 > settings["max_amount"]:
            await interaction.response.send_message(
                f"❌ 선물 금액은 {format_money(settings['min_amount'])} ~ {format_money(settings['max_amount'])} 사이여야 합니다.",
                ephemeral=True
            )
            return
        
        db = self._get_db(interaction.guild_id)
        # 보내는 사람 등록 확인
        if not db.get_user(sender_id):
            await interaction.response.send_message("❗ 먼저 `/등록` 명령어로 플레이어 등록해주세요.", ephemeral=True)
            return
        
        # 받는 사람 등록 확인 (자동 등록)
        if not db.get_user(receiver_id):
            success = db.create_user(receiver_id, 받는사람.name, 받는사람.display_name, initial_cash=0)
            if not success:
                await interaction.response.send_message("❌ 받는 사람의 계정 생성에 실패했습니다.", ephemeral=True)
                return
        
        # 쿨다운 확인
        cooldown = self._check_cooldown(sender_id)
        if cooldown:
            minutes, seconds = divmod(cooldown, 60)
            await interaction.response.send_message(
                f"⏰ 선물 쿨다운 중입니다. {minutes}분 {seconds}초 후에 다시 시도해주세요.",
                ephemeral=True
            )
            return
        
        # 일일 제한 확인
        daily_count = self._get_daily_count(sender_id)
        if daily_count >= settings["daily_limit"]:
            await interaction.response.send_message(
                f"📊 오늘 선물 한도를 초과했습니다. (오늘: {daily_count}/{settings['daily_limit']}회)",
                ephemeral=True
            )
            return
        
        # 잔액 확인
        sender_cash = db.get_user_cash(sender_id)
        fee = int(금액 * settings["fee_rate"])
        total_cost = 금액 + fee
        
        if sender_cash < total_cost:
            await interaction.response.send_message(
                f"❌ 잔액이 부족합니다.\n"
                f"필요 금액: {format_money(total_cost)} (선물 {format_money(금액)} + 수수료 {format_money(fee)})\n"
                f"현재 잔액: {format_money(sender_cash)}",
                ephemeral=True
            )
            return
        
        # 선물 실행
        try:
            db.add_user_cash(sender_id, -total_cost)
            db.add_user_cash(receiver_id, 금액)
            
            # 거래 내역 기록
            db.add_transaction(sender_id, "선물 보내기", -total_cost, f"{받는사람.display_name}에게 선물 (수수료 포함)")
            db.add_transaction(receiver_id, "선물 받기", 금액, f"{interaction.user.display_name}님으로부터 선물")
            
            # 쿨다운 및 일일 카운트 설정
            self._set_cooldown(sender_id)
            self._increment_daily_count(sender_id)
            
            # 성공 메시지
            embed = discord.Embed(
                title="🎁 선물 전송 완료",
                description=f"{interaction.user.display_name}님이 {받는사람.display_name}님에게 현금을 선물했습니다!",
                color=discord.Color.green()
            )
            embed.add_field(name="🎁 선물 금액", value=format_money(금액), inline=True)
            embed.add_field(name="💸 수수료", value=format_money(fee), inline=True)
            embed.add_field(name="💰 총 차감", value=format_money(total_cost), inline=True)
            embed.set_footer(text=f"남은 일일 선물 횟수: {settings['daily_limit'] - daily_count - 1}/{settings['daily_limit']}회")
            
            await interaction.response.send_message(embed=embed)
            
            # 받는 사람에게 DM 발송 시도
            try:
                dm_embed = discord.Embed(
                    title="🎁 선물을 받았습니다!",
                    description=f"{interaction.user.display_name}님이 {format_money(금액)}을 선물해주셨습니다!",
                    color=discord.Color.green()
                )
                await 받는사람.send(embed=dm_embed)
            except:
                pass  # DM 발송 실패해도 무시
                
        except Exception as e:
            print(f"❌ 선물 처리 중 오류: {e}")
            await interaction.response.send_message(f"❌ 선물 처리 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @app_commands.command(name="데이터베이스상태", description="현재 데이터베이스 연결 상태를 확인합니다")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def database_status(self, interaction: Interaction):
        """데이터베이스 연결 상태 확인"""
        
        db = self._get_db(interaction.guild_id)
        
        embed = discord.Embed(
            title="📊 데이터베이스 상태",
            color=discord.Color.green() if self.DATABASE_AVAILABLE else discord.Color.red()
        )
        
        embed.add_field(
            name="연결 상태",
            value=f"{'✅ 실제 데이터베이스 연결됨' if self.DATABASE_AVAILABLE else '⚠️ Mock 데이터베이스 사용 중'}",
            inline=False
        )
        
        # Mock DB 사용 중일 경우 경고
        if not self.DATABASE_AVAILABLE:
            embed.add_field(
                name="⚠️ 주의사항",
                value="• 현재 임시 메모리 데이터베이스를 사용 중입니다\n• 봇 재시작 시 모든 데이터가 사라집니다\n• database_manager.py 파일을 확인해주세요\n• 실제 DB가 필요하면 DB 설정을 확인하세요",
                inline=False
            )
            
            # Mock DB의 현재 사용자 수 표시
            mock_users = len(db.users) if hasattr(db, 'users') else 0
            embed.add_field(
                name="임시 DB 상태",
                value=f"등록된 사용자: {mock_users}명",
                inline=True
            )
            
            # Mock DB의 사용자 목록 표시 (최대 5명)
            if hasattr(db, 'users') and db.users:
                user_list = []
                for i, (uid, data) in enumerate(db.users.items()):
                    if i >= 5:
                        user_list.append("...")
                        break
                    user_list.append(f"• {data.get('display_name', '이름없음')}: {data.get('cash', 0):,}원")
                
                if user_list:
                    embed.add_field(
                        name="등록된 사용자 (최대 5명)",
                        value="\n".join(user_list),
                        inline=False
                    )
        else:
            embed.add_field(
                name="✅ 정상 운영",
                value="실제 데이터베이스에 연결되어 있습니다.\n모든 데이터가 영구 저장됩니다.",
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="현금순위", description="해당 서버의 현금 보유 순위를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(페이지="확인할 페이지 번호 (기본: 1)")
    async def cash_ranking(self, interaction: Interaction, 페이지: int = 1):
        await interaction.response.defer()
        
        if 페이지 < 1:
            return await interaction.followup.send("❌ 페이지 번호는 1 이상이어야 합니다.", ephemeral=True)
        
        try:
            db = self._get_db(interaction.guild_id)
            # 해당 서버(guild_id) 데이터 전체 조회
            results = db.execute_query('''
                SELECT username, display_name, cash 
                FROM users 
                WHERE guild_id = ? 
                ORDER BY cash DESC
            ''', (str(interaction.guild_id),), 'all')
            
            if not results:
                return await interaction.followup.send("📊 해당 서버에 순위 데이터가 없습니다.")

           # 설정: 한 페이지에 100명 (임베드 5개 x 20명)
            users_per_page = 100
            chunk_size = 20
            total_pages = (len(results) - 1) // users_per_page + 1

            if 페이지 > total_pages:
                return await interaction.followup.send(f"❌ 데이터가 부족합니다. (최대 페이지: {total_pages})", ephemeral=True)
            
            # 해당 페이지에 해당하는 유저 슬라이싱
            start_idx = (페이지 - 1) * users_per_page
            end_idx = start_idx + users_per_page
            page_data = results[start_idx:end_idx]

            embeds = []
            # 20명씩 끊어서 임베드 생성 (최대 5개)
            for i in range(0, len(page_data), chunk_size):
                chunk = page_data[i:i + chunk_size]
                current_rank_start = start_idx + i + 1
                
                embed = discord.Embed(
                    title=f"💰 서버 현금 순위 ({페이지}/{total_pages} 페이지)" if i == 0 else None,
                    description=f"**{current_rank_start}위 ~ {current_rank_start + len(chunk) - 1}위**",
                    color=discord.Color.gold(),
                    timestamp=datetime.now(KST)
                )
                
                ranking_text = []
                for j, user in enumerate(chunk, current_rank_start):
                    name = user['display_name'] or user['username'] or "알 수 없음"
                    cash = user['cash']
                    emoji = "🥇" if j == 1 else "🥈" if j == 2 else "🥉" if j == 3 else f"**{j}.**"
                    cash_str = f"🛑 `-{abs(cash):,}원`" if cash < 0 else f"`{cash:,}원`"
                    ranking_text.append(f"{emoji} {name} : {cash_str}")
                
                embed.add_field(name="목록", value="\n".join(ranking_text), inline=False)
                
                if i + chunk_size >= len(page_data): # 마지막 임베드
                    embed.set_footer(text=f"페이지 {페이지} / {total_pages} | 총 {len(results)}명")
                
                embeds.append(embed)

            # 최대 10개의 임베드를 한 번에 전송 (디스코드 제한)
            await interaction.followup.send(embeds=embeds)
            
        except Exception as e:
            print(f"❌ 순위 조회 오류: {e}")
            await interaction.followup.send("❌ 순위 정보를 불러오는 중 오류가 발생했습니다.")

    @app_commands.command(name="탈퇴", description="서버에서 탈퇴합니다. (모든 데이터 삭제)")
    async def leave(self, interaction: Interaction):
        user_id = str(interaction.user.id)
        db = self._get_db(interaction.guild_id)
        
        user_data = db.get_user(user_id)
        if not user_data:
            await interaction.response.send_message("❌ 등록되지 않은 사용자입니다.", ephemeral=True)
            return
        
        try:
            cash = db.get_user_cash(user_id)
            # 외부로 뺀 LeaveConfirmView를 호출합니다.
            view = LeaveConfirmView(user_id, db, interaction.user.display_name)
            
            embed = discord.Embed(
                title="⚠️ 탈퇴 확인",
                description=f"정말로 탈퇴하시겠습니까?\n\n**현재 보유 현금**: {format_money(cash)}\n\n⚠️ **주의**: 탈퇴 시 모든 데이터가 영구 삭제됩니다.",
                color=discord.Color.orange()
            )
            
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 탈퇴 명령어 오류: {e}")
            await interaction.response.send_message(f"❌ 처리 중 오류가 발생했습니다.", ephemeral=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        # 길드 ID가 없는 DM에서는 처리하지 않음
        if member.guild is None:
            return

        user_id = str(member.id)
        guild_id = str(member.guild.id)
        db = self._get_db(guild_id)

        if db.get_user(user_id):
            try:
                db.delete_user(user_id)
                print(f"✅ 회원 탈퇴 처리: {member.display_name} (ID: {user_id}) (Guild: {guild_id})")
            except Exception as e:
                print(f"❌ 자동 탈퇴 처리 중 오류: {member.display_name} - {e} (Guild: {guild_id})")

# ==================== 관리자 명령어들 ====================

    @app_commands.command(name="현금지급", description="[관리자 전용] 사용자에게 현금을 지급합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(사용자="현금을 받을 사용자", 금액="지급할 현금")
    async def give_cash(self, interaction: Interaction, 사용자: Member, 금액: int): 
        # 🟢 추가: 길드별 DB 인스턴스를 가져옵니다.
        db = self._get_db(interaction.guild_id)
        
        user_id = str(사용자.id)
        if not db.get_user(user_id):
            await interaction.response.send_message("❌ 등록되지 않은 사용자입니다.", ephemeral=True)
            return
        
        try:
            db.add_user_cash(user_id, 금액)
            db.add_transaction(user_id, "관리자 지급", 금액, f"{interaction.user.display_name}이 지급")
            
            embed = discord.Embed(
                title="💰 현금 지급 완료",
                description=f"{사용자.display_name}님에게 {format_money(금액)}을 지급했습니다.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:


            print(f"❌ 현금 지급 중 오류: {e}")
            await interaction.response.send_message(f"❌ 현금 지급 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @app_commands.command(name="현금차감", description="[관리자 전용] 사용자의 현금을 차감합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(사용자="현금을 차감할 사용자", 금액="차감할 현금")
    async def deduct_cash(self, interaction: Interaction, 사용자: Member, 금액: int):
        db = self._get_db(interaction.guild_id)
        
        user_id = str(사용자.id)
        if not db.get_user(user_id): 
            await interaction.response.send_message("❌ 등록되지 않은 사용자입니다.", ephemeral=True)
            return
        
        try:
            db.add_user_cash(user_id, -금액)
            db.add_transaction(user_id, "관리자 차감", -금액, f"{interaction.user.display_name}이 차감")
            
            embed = discord.Embed(
                title="💸 현금 차감 완료",
                description=f"{사용자.display_name}님의 현금 {format_money(금액)}을 차감했습니다.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            print(f"❌ 현금 차감 중 오류: {e}")
            await interaction.response.send_message(f"❌ 현금 차감 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @app_commands.command(name="선물설정", description="[관리자 전용] 선물 시스템 설정을 변경합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(
        수수료율="수수료율 (0.0 ~ 1.0, 예: 0.1 = 10%)",
        최소금액="최소 선물 금액",
        최대금액="최대 선물 금액",
        일일제한="일일 선물 횟수 제한",
        쿨다운분="선물 쿨다운 시간 (분)"
    )
    async def gift_settings_cmd(self, interaction: Interaction, 수수료율: Optional[float] = None, 
                               최소금액: Optional[int] = None, 최대금액: Optional[int] = None,
                               일일제한: Optional[int] = None, 쿨다운분: Optional[int] = None):

        settings = self.gift_settings.settings
        changes = []
        
        try:
            if 수수료율 is not None:
                if 0.0 <= 수수료율 <= 1.0:
                    settings["fee_rate"] = 수수료율
                    changes.append(f"수수료율: {수수료율*100:.1f}%")
            
            if 최소금액 is not None and 최소금액 > 0:
                settings["min_amount"] = 최소금액
                changes.append(f"최소금액: {format_money(최소금액)}")
            
            if 최대금액 is not None and 최대금액 > 0:
                settings["max_amount"] = 최대금액
                changes.append(f"최대금액: {format_money(최대금액)}")
            
            if 일일제한 is not None and 일일제한 > 0:
                settings["daily_limit"] = 일일제한
                changes.append(f"일일제한: {일일제한}회")
            
            if 쿨다운분 is not None and 쿨다운분 >= 0:
                settings["cooldown_minutes"] = 쿨다운분
                changes.append(f"쿨다운: {쿨다운분}분")
            
            if changes:
                if self.gift_settings.save_settings():
                    embed = discord.Embed(
                        title="⚙️ 선물 설정 변경 완료",
                        description="\n".join(changes),
                        color=discord.Color.green()
                    )
                else:
                    embed = discord.Embed(
                        title="❌ 설정 저장 실패",
                        description="설정 변경에 실패했습니다.",
                        color=discord.Color.red()
                    )
            else:
                # 현재 설정 표시
                embed = discord.Embed(
                    title="⚙️ 현재 선물 설정",
                    color=discord.Color.blue()
                )
                embed.add_field(name="수수료율", value=f"{settings['fee_rate']*100:.1f}%", inline=True)
                embed.add_field(name="금액 범위", value=f"{format_money(settings['min_amount'])} ~ {format_money(settings['max_amount'])}", inline=True)
                embed.add_field(name="일일 제한", value=f"{settings['daily_limit']}회", inline=True)
                embed.add_field(name="쿨다운", value=f"{settings['cooldown_minutes']}분", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
            
        except Exception as e:
            print(f"❌ 선물 설정 변경 중 오류: {e}")
            await interaction.response.send_message(f"❌ 설정 변경 중 오류가 발생했습니다: {str(e)}", ephemeral=True)


# ==================== 호환성 함수들 ====================

# 기존 시스템과의 호환성을 위한 전역 함수들 (bot과 guild_id를 인자로 받아 PointManager cog를 통해 DB 접근)
async def load_points(bot, guild_id: int):
    """기존 시스템 호환 - 모든 사용자 포인트 로드"""
    try:
        point_manager_cog = bot.get_cog("PointManager")
        if point_manager_cog:
            db = point_manager_cog._get_db(guild_id)
            results = db.execute_query('SELECT user_id, cash FROM users', (), 'all')
            return {row['user_id']: row['cash'] for row in (results or [])}
        else:
            print("PointManager cog not found for load_points.")
            return {}
    except Exception as e:
        print(f"load_points 오류: {e}")
        return {}

async def save_points(bot, guild_id: int, points_data):
    """기존 시스템 호환 - 포인트 데이터 저장"""
    try:
        point_manager_cog = bot.get_cog("PointManager")
        if point_manager_cog:
            db = point_manager_cog._get_db(guild_id)
            for user_id, cash in points_data.items():
                try:
                    db.update_user_cash(user_id, cash)
                except Exception as e:
                    print(f"save_points 오류 (사용자 {user_id}): {e}")
        else:
            print("PointManager cog not found for save_points.")
    except Exception as e:
        print(f"save_points 전역 오류: {e}")

async def add_point(bot, guild_id, user_id, amount):
    """
    Cog 인스턴스가 있다면 그것을 사용하고, 없다면 직접 DB에 연결합니다.
    """
    cog = bot.get_cog("PointManager")
    if cog:
        db = cog._get_db(guild_id)
        new_cash = db.add_user_cash(str(user_id), int(amount))
        db.add_transaction(str(user_id), "게임 결과", int(amount))
        return True
    
    # Cog를 찾을 수 없을 때의 Fallback
    try:
        from database_manager import DatabaseManager
        db = DatabaseManager(guild_id=str(guild_id))
        db.add_user_cash(str(user_id), int(amount))
        return True
    except:
        return False

async def get_point(bot, guild_id, user_id):
    """직접 DB에서 포인트 조회"""
    try:
        from database_manager import DatabaseManager
        db = DatabaseManager(guild_id=str(guild_id))
        user_data = db.get_user(str(user_id))
        return user_data['cash'] if user_data else 0
    except:
        return 0

async def is_registered(bot, guild_id: int, user_id):
    """기존 시스템 호환 - 등록 여부 확인"""
    try:
        point_manager_cog = bot.get_cog("PointManager")
        if point_manager_cog:
            db = point_manager_cog._get_db(guild_id)
            return db.get_user(str(user_id)) is not None
        else:
            print("PointManager cog not found for is_registered.")
            return False
    except Exception as e:
        print(f"is_registered 오류 (사용자 {user_id}): {e}")
        return False

async def register_user(bot, guild_id: int, user_id, username='', display_name=''):
    """기존 시스템 호환 - 사용자 등록"""
    try:
        point_manager_cog = bot.get_cog("PointManager")
        if point_manager_cog:
            db = point_manager_cog._get_db(guild_id)
            # 사용자 생성 (초기 현금 10,000원)
            success = db.create_user(str(user_id), username, display_name, initial_cash=10000)
            if success:
                db.add_transaction(str(user_id), "회원가입", 10000, "신규 회원가입 보너스")
            return success
        else:
            print("PointManager cog not found for register_user.")
            return False
    except Exception as e:
        print(f"register_user 오류 (사용자 {user_id}): {e}")
        return False

async def set_point(bot, guild_id: int, user_id, amount):
    """기존 시스템 호환 - 포인트 설정"""
    try:
        point_manager_cog = bot.get_cog("PointManager")
        if point_manager_cog:
            db = point_manager_cog._get_db(guild_id)
            db.update_user_cash(str(user_id), amount)
            return True
        else:
            print("PointManager cog not found for set_point.")
            return False
    except Exception as e:
        print(f"set_point 오류 (사용자 {user_id}): {e}")
        return False

async def setup(bot):
    """봇에 PointManager Cog를 추가하는 함수"""
    try:
        # 기존 명령어가 이미 등록되어 있는지 확인
        existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
        
        # PointManager가 등록하려는 명령어들
        point_commands = [
            "등록", "지갑", "선물", "선물기록", "선물설정", 
            "현금순위", "현금지급", "현금차감", "탈퇴", "데이터베이스상태"
        ]
        
        # 중복 명령어 체크
        conflicting_commands = [cmd for cmd in point_commands if cmd in existing_commands]
        
        if conflicting_commands:
            print(f"⚠️ 중복 명령어 발견: {conflicting_commands}")
            print("🔄 기존 명령어를 제거하고 새로 등록합니다...")
            
            # 기존 명령어 제거 (필요시)
            for cmd_name in conflicting_commands:
                try:
                    bot.tree.remove_command(cmd_name)
                    print(f"   ✅ {cmd_name} 명령어 제거됨")
                except Exception as e:
                    print(f"   ⛔ {cmd_name} 명령어 제거 실패: {e}")
        
        # PointManager Cog 등록
        await bot.add_cog(PointManager(bot))
        
        if not DATABASE_AVAILABLE:
            print("⚠️ 경고: Mock 데이터베이스 사용 중 - 봇 재시작 시 데이터 손실됨")
            print("💡 해결방법: database_manager.py 파일과 DB 연결 설정을 확인하세요")
            
    except Exception as e:
        print(f"❌ PointManager 로드 중 오류: {e}")
        print(f"상세 오류:\n{traceback.format_exc()}")
        raise