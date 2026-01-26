# improved_user_management.py - 사용자 관리
from __future__ import annotations
import discord
from discord import app_commands, Interaction, Member
from discord.ext import commands
from datetime import datetime, timezone
import asyncio
from typing import Optional, Any

# 데이터베이스 매니저 임포트는 더 이상 필요 없습니다. cog_load에서 가져옵니다.

# 유틸리티 함수들
def format_money(amount):
    """돈 포맷팅"""
    return f"{amount:,}"

def format_xp(xp):
    """XP 포맷팅"""
    return f"{xp:,}"

def log_admin_action(message):
    """관리자 액션 로그"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] ADMIN: {message}")

class UserDeleteConfirmView(discord.ui.View):
    """사용자 삭제 확인 UI"""
    def __init__(self, target_user: Member, admin_user: Member, db_cog: Any): # db_cog 인자 추가
        super().__init__(timeout=60)
        self.target_user = target_user
        self.admin_user = admin_user
        self.target_id = str(target_user.id)
        self.target_name = target_user.display_name
        self.db_cog = db_cog # db_cog 저장

    @discord.ui.button(label="✅ 탈퇴 확정", style=discord.ButtonStyle.danger)
    async def confirm_delete(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 확정할 수 있습니다.", 
                ephemeral=True
            )
        
        await interaction.response.defer()
        
        try:
            db = self.db_cog.get_manager(str(self.target_user.guild.id)) # db_cog를 통해 manager 가져오기
            # 사용자 데이터 삭제
            deleted_counts = db.delete_user(self.target_id)
            
            for item in self.children:
                item.disabled = True
            
            embed = discord.Embed(
                title="✅ 탈퇴 완료",
                description=f"**{self.target_name}**님의 모든 데이터가 삭제되었습니다.",
                color=discord.Color.green()
            )
            
            # 삭제된 데이터 통계
            deleted_total = sum(deleted_counts.values())
            stats_text = ""
            for table, count in deleted_counts.items():
                if count > 0:
                    stats_text += f"• {table}: {count}건\n"
            
            embed.add_field(
                name="📊 삭제된 데이터",
                value=stats_text if stats_text else "삭제된 데이터가 없습니다.",
                inline=False
            )
            
            embed.add_field(
                name="🏃 실행자",
                value=self.admin_user.display_name,
                inline=True
            )
            
            embed.set_footer(text=f"삭제 완료 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # 관리자 액션 로그
            log_admin_action(f"{self.admin_user.display_name}이(가) {self.target_name}을(를) 탈퇴시킴 (총 {deleted_total}건 삭제)")
            
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ 탈퇴 실패", 
                description=f"데이터 삭제 중 오류가 발생했습니다: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_delete(self, interaction: Interaction, button: discord.ui.Button):
        if interaction.user != self.admin_user:
            return await interaction.response.send_message(
                "❌ 명령어를 실행한 관리자만 취소할 수 있습니다.", 
                ephemeral=True
            )
        
        for item in self.children:
            item.disabled = True
        
        embed = discord.Embed(
            title="❌ 탈퇴 취소",
            description=f"**{self.target_name}**님의 탈퇴가 취소되었습니다.",
            color=discord.Color.orange()
        )
        
        await interaction.response.edit_message(embed=embed, view=self)

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True

# ✅ UserUnregisterView 별칭 추가 (user_management.py 호환성을 위해)
UserUnregisterView = UserDeleteConfirmView

class UserManagementCog(commands.Cog):
    """개선된 사용자 관리 시스템"""
    
    def __init__(self, bot):
        self.bot = bot
        self.db_cog: Optional[Any] = None # DatabaseCog 인스턴스를 저장할 변수
    
    async def cog_load(self):
        """Cog가 로드된 후 DatabaseManager Cog를 가져옵니다."""
        self.db_cog = self.bot.get_cog("DatabaseManager")
        if not self.db_cog:
            print("❌ DatabaseManager Cog를 찾을 수 없습니다. 사용자 관리 기능이 제한됩니다.")
        else:
            print("✅ DatabaseManager Cog 연결 성공.")

    @app_commands.command(name="사용자관리", description="[관리자 전용] 통합 사용자 관리 패널을 표시합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    async def user_management_panel(self, interaction: Interaction):
        # DatabaseCog 로드 여부 확인
        if not self.db_cog:
            return await interaction.response.send_message("❌ 데이터베이스 시스템이 로드되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            guild_id = str(interaction.guild.id)
            db = self.db_cog.get_manager(guild_id) # db_cog를 통해 manager 가져오기
            
            # 총 사용자 수
            total_users_result = db.execute_query('SELECT COUNT(*) FROM users WHERE guild_id = ?', (guild_id,), 'one')
            # ✅ Row 객체를 딕셔너리로 변환하거나 인덱스로 접근
            total_users = dict(total_users_result)['COUNT(*)'] if total_users_result else 0
            
            # TOP 5 현금 보유자
            top_cash_users_results = db.execute_query('''
                SELECT user_id, username, display_name, cash 
                FROM users 
                WHERE guild_id = ?
                ORDER BY cash DESC 
                LIMIT 5
            ''', (guild_id,), 'all')
            
            # TOP 5 XP 보유자 (길드별)
            top_xp_users_results = db.execute_query('''
                SELECT ux.user_id, u.username, u.display_name, ux.xp, ux.level
                FROM user_xp ux
                JOIN users u ON ux.user_id = u.user_id AND u.guild_id = ?
                ORDER BY ux.xp DESC 
                LIMIT 5
            ''', (guild_id,), 'all')
            
            # ✅ Row 객체들을 딕셔너리로 변환
            top_cash_users = [dict(row) for row in top_cash_users_results] if top_cash_users_results else []
            top_xp_users = [dict(row) for row in top_xp_users_results] if top_xp_users_results else []
            
            # 최근 가입자 (TOP 5)
            recent_users_results = db.execute_query('''
                SELECT user_id, username, display_name, created_at 
                FROM users 
                WHERE guild_id = ?
                ORDER BY created_at DESC 
                LIMIT 5
            ''', (guild_id,), 'all')
            recent_users = [dict(row) for row in recent_users_results] if recent_users_results else []
            
            # 임베드 생성
            embed = discord.Embed(
                title="🛡️ 사용자 관리 패널",
                description=f"**{interaction.guild.name}** 서버의 사용자 통계 및 관리",
                color=discord.Color.blue()
            )
            
            # 기본 통계
            embed.add_field(
                name="📊 기본 통계",
                value=f"총 등록 사용자: **{total_users}명**\n현재 서버 멤버: **{interaction.guild.member_count}명**",
                inline=False
            )
            
            # TOP 5 현금 보유자
            cash_text = ""
            for i, user in enumerate(top_cash_users, 1):
                name = user.get('display_name') or user.get('username') or "알 수 없음"
                cash_text += f"{i}. {name}: **{format_money(user['cash'])}원**\n"
            
            embed.add_field(
                name="💰 TOP 5 현금 보유자",
                value=cash_text if cash_text else "데이터 없음",
                inline=True
            )
            
            # TOP 5 XP 보유자
            xp_text = ""
            for i, user in enumerate(top_xp_users, 1):
                name = user.get('display_name') or user.get('username') or "알 수 없음"
                xp_text += f"{i}. {name}: **Lv.{user['level']}** ({format_xp(user['xp'])})\n"
            
            embed.add_field(
                name="✨ TOP 5 XP 보유자",
                value=xp_text if xp_text else "데이터 없음",
                inline=True
            )
            
            # 최근 가입자
            recent_text = ""
            for user in recent_users:
                name = user.get('display_name') or user.get('username') or "알 수 없음"
                recent_text += f"• {name} ({user['created_at'][:10]})\n"
            
            embed.add_field(
                name="🆕 최근 가입자",
                value=recent_text if recent_text else "데이터 없음",
                inline=False
            )
            
            # 관리 명령어 안내
            embed.add_field(
                name="🔧 관리 명령어",
                value="`/등록목록` - 사용자 목록\n`/사용자정보` - 상세 정보\n`/데이터초기화` - 데이터 리셋",
                inline=False
            )
            
            embed.set_footer(text="SQLite 기반 사용자 관리 시스템")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 관리 패널 로드 중 오류: {str(e)}")

    @app_commands.command(name="등록목록", description="[관리자 전용] 등록된 사용자 목록을 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(페이지="확인할 페이지 번호 (기본값: 1)")
    async def list_registered_users(self, interaction: Interaction, 페이지: int = 1):
        # DatabaseCog 로드 여부 확인
        if not self.db_cog:
            return await interaction.response.send_message("❌ 데이터베이스 시스템이 로드되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=False)
        
        try:
            guild_id = str(interaction.guild.id)
            db = self.db_cog.get_manager(guild_id) # db_cog를 통해 manager 가져오기
            
            # 페이지 설정 (1페이지당 10명)
            page_size = 10
            offset = (페이지 - 1) * page_size
            
            # 사용자 목록 조회 (생성일순)
            users_results = db.execute_query('''
                SELECT user_id, username, display_name, cash, created_at 
                FROM users 
                WHERE guild_id = ?
                ORDER BY created_at DESC 
                LIMIT ? OFFSET ?
            ''', (guild_id, page_size, offset), 'all')
            
            if not users_results:
                return await interaction.followup.send("📋 해당 페이지에 사용자가 없습니다.")
            
            # ✅ Row 객체들을 딕셔너리로 변환
            users = [dict(row) for row in users_results]
            
            # 총 사용자 수와 총 페이지 수 계산
            total_users_result = db.execute_query('SELECT COUNT(*) FROM users WHERE guild_id = ?', (guild_id,), 'one')
            total_users = dict(total_users_result)['COUNT(*)'] if total_users_result else 0
            total_pages = (total_users + 9) // 10  # 올림 계산
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"📋 등록 사용자 목록 (페이지 {페이지}/{total_pages})",
                color=discord.Color.green()
            )
            
            user_list_text = ""
            for i, user in enumerate(users, 1):
                rank = offset + i
                user_id = user['user_id']
                
                # XP 데이터 조회
                xp_data = db.get_user_xp(user_id)
                xp = xp_data.get('xp', 0) if xp_data else 0
                level = xp_data.get('level', 1) if xp_data else 1
                
                # ✅ 이제 딕셔너리이므로 .get() 메서드 사용 가능
                name = user.get('display_name') or user.get('username') or "알 수 없음"
                
                user_list_text += f"**{rank}.** {name}\n"
                user_list_text += f"   💰 {format_money(user.get('cash', 0))}원 | ✨ Lv.{level} ({format_xp(xp)})\n"
                user_list_text += f"   📅 등록일: {user.get('created_at', 'Unknown')[:10]}\n\n"
            
            embed.description = user_list_text
            
            # 통계 정보
            embed.add_field(
                name="📊 통계",
                value=f"총 사용자: **{total_users}명**\n현재 페이지: **{페이지}/{total_pages}**",
                inline=False
            )
            
            # 페이지 이동 안내
            if total_pages > 1:
                embed.add_field(
                    name="📖 페이지 이동",
                    value=f"`/등록목록 페이지:{페이지+1}` - 다음 페이지\n`/등록목록 페이지:{max(1, 페이지-1)}` - 이전 페이지",
                    inline=False
                )
            
            embed.set_footer(text="SQLite 기반 사용자 관리 시스템")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 사용자 목록 조회 중 오류: {str(e)}")

    @app_commands.command(name="사용자정보", description="[관리자 전용] 특정 사용자의 상세 정보를 확인합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(대상="정보를 확인할 사용자")
    async def user_info(self, interaction: Interaction, 대상: Member):
        # DatabaseCog 로드 여부 확인
        if not self.db_cog:
            return await interaction.response.send_message("❌ 데이터베이스 시스템이 로드되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
    
        await interaction.response.defer(ephemeral=False)
        
        try:
            target_id = str(대상.id)
            guild_id = str(interaction.guild.id)
            db = self.db_cog.get_manager(guild_id) # db_cog를 통해 manager 가져오기
            
            # 기본 사용자 정보
            user_data = db.get_user(target_id)
            if not user_data:
                return await interaction.followup.send(
                    f"❌ {대상.display_name}님은 등록되어 있지 않습니다."
                )
            
            # XP 정보
            xp_data = db.get_user_xp(target_id)
            
            # 출석 통계
            attendance_stats = db.get_attendance_stats(target_id)
            
            # 강화 정보
            enhancement_data = db.execute_query(
                'SELECT * FROM enhancement WHERE user_id = ?',
                (target_id,), 'one'
            )
            
            # 임베드 생성
            embed = discord.Embed(
                title=f"👤 {대상.display_name} 사용자 정보",
                color=discord.Color.blue()
            )
            
            # 기본 정보
            embed.add_field(
                name="💰 경제 정보",
                value=f"현금: **{format_money(user_data['cash'])}원**\n등록일: **{user_data['created_at'][:10]}**",
                inline=False
            )
            
            # XP 정보
            if xp_data:
                embed.add_field(
                    name="✨ 레벨 정보",
                    value=f"레벨: **{xp_data.get('level', 1)}**\nXP: **{format_xp(xp_data.get('xp', 0))}**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="✨ 레벨 정보",
                    value="XP 데이터 없음",
                    inline=False
                )
            
            # 출석 정보
            if attendance_stats:
                embed.add_field(
                    name="📅 출석 정보",
                    value=f"총 출석: **{attendance_stats.get('total_days', 0)}일**\n연속 출석: **{attendance_stats.get('streak_days', 0)}일**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="📅 출석 정보",
                    value="출석 기록 없음",
                    inline=False
                )
            
            # 강화 정보
            if enhancement_data:
                enhancement_dict = dict(enhancement_data)
                embed.add_field(
                    name="⚔️ 강화 정보",
                    value=f"강화 레벨: **+{enhancement_dict.get('level', 0)}**",
                    inline=False
                )
            else:
                embed.add_field(
                    name="⚔️ 강화 정보",
                    value="강화 데이터 없음",
                    inline=False
                )
            
            # 추가 정보
            embed.add_field(
                name="📋 추가 정보",
                value=f"사용자명: **{user_data.get('username', '없음')}**\n표시명: **{user_data.get('display_name', '없음')}**",
                inline=False
            )
            
            embed.set_thumbnail(url=대상.display_avatar.url)
            embed.set_footer(text="SQLite 기반 사용자 관리 시스템")
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            await interaction.followup.send(f"❌ 사용자 정보 조회 중 오류: {str(e)}")

    @app_commands.command(name="데이터초기화", description="[관리자 전용] 사용자의 모든 데이터를 초기화합니다.")
    @app_commands.checks.has_permissions(administrator=True) # 서버 내 실제 권한 체크
    @app_commands.default_permissions(administrator=True)    # 디스코드 메뉴 노출 설정
    @app_commands.describe(사용자="데이터를 초기화할 사용자")
    async def reset_user_data(self, interaction: Interaction, 사용자: Member):
        # DatabaseCog 로드 여부 확인
        if not self.db_cog:
            return await interaction.response.send_message("❌ 데이터베이스 시스템이 로드되지 않았습니다. 관리자에게 문의하세요.", ephemeral=True)
        
        target_id = str(사용자.id)
        guild_id = str(interaction.guild.id)
        db = self.db_cog.get_manager(guild_id) # db_cog를 통해 manager 가져오기
        
        # 사용자 등록 확인
        if not db.get_user(target_id):
            return await interaction.response.send_message("❌ 해당 사용자가 등록되지 않았습니다.", ephemeral=True)
        
        # 자기 자신 초기화 방지
        if target_id == str(interaction.user.id):
            return await interaction.response.send_message("❌ 자기 자신의 데이터는 초기화할 수 없습니다.", ephemeral=True)
        
        try:
            
            # 1. 현금 초기화
            db.update_user_cash(target_id, 10000)
            
            # 2. XP 초기화
            db.execute_query('''
                UPDATE user_xp SET xp = 0, level = 1, updated_at = CURRENT_TIMESTAMP
                WHERE user_id = ?
            ''', (target_id,))
            
            # 3. 출석 기록 삭제
            db.execute_query('DELETE FROM attendance WHERE user_id = ?', (target_id,))
            
            # 4. 강화 데이터 초기화
            db.execute_query('DELETE FROM enhancement WHERE user_id = ?', (target_id,))
            
            embed = discord.Embed(
                title="✅ 데이터 초기화 완료",
                description=f"**{사용자.display_name}**님의 데이터가 초기화되었습니다!",
                color=discord.Color.green()
            )
            embed.add_field(
                name="🔄 초기화된 항목",
                value="• 💰 현금: 10,000원으로 재설정\n" 
                      "• ✨ XP/레벨: Lv.1 (0 XP)\n" 
                      "• 📅 출석 기록: 삭제\n" 
                      "• ⚡ 강화 데이터: 삭제",
                inline=False
            )
            embed.add_field(
                name="📋 보존된 항목",
                value="• 💳 거래 기록 (감사 목적)\n" 
                      "• 👤 기본 사용자 정보",
                inline=False
            )
            embed.add_field(name="🔧 실행자", value=interaction.user.mention, inline=True)
            
            # 로그 기록
            log_admin_action(f"데이터 초기화: {사용자.display_name} ({target_id}) by {interaction.user.display_name}")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ 데이터 초기화 중 오류: {str(e)}", ephemeral=True)

async def setup(bot):
    """Cog 로드를 위한 setup 함수"""
    await bot.add_cog(UserManagementCog(bot))