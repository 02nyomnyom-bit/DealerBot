# tax_system.py - 등급별 세금 시스템 (완전한 원본 복원)
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional, Tuple
import json
import os
import asyncio

# ✅ common_utils에서 필요한 함수들 import
try:
    from common_utils import log_admin_action, format_xp, now_str
except ImportError:
    # common_utils가 없는 경우 대체 함수들
    def log_admin_action(message: str):
        print(f"[ADMIN LOG] {message}")
    
    def format_xp(xp: int) -> str:
        return f"{xp:,} XP"
    
    def now_str() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ✅ 안전한 의존성 import
def safe_import_database():
    try:
        from database_manager import DatabaseManager
        return DatabaseManager(), True
    except ImportError:
        print("⚠️ DatabaseManager 임포트 실패")
        return None, False

# 데이터베이스 로드
db_manager, DATABASE_AVAILABLE = safe_import_database()

# ✅ 데이터 디렉토리 및 파일 경로
DATA_DIR = "data"
TAX_SETTINGS_FILE = os.path.join(DATA_DIR, "tax_settings.json")

# 디렉토리 생성
os.makedirs(DATA_DIR, exist_ok=True)

class TaxManager:
    """세금 시스템 관리 클래스"""
    
    def __init__(self):
        self.tax_settings: Dict[str, Dict[str, int]] = {}  # {guild_id: {role_id: xp_amount}}
        self.load_data()
    
    def load_data(self):
        """세금 설정 데이터 로드"""
        try:
            if os.path.exists(TAX_SETTINGS_FILE):
                with open(TAX_SETTINGS_FILE, 'r', encoding='utf-8') as f:
                    self.tax_settings = json.load(f)
                print(f"✅ 세금 설정 데이터 로드 완료: {len(self.tax_settings)}개 서버")
            else:
                self.tax_settings = {}
                print("📝 새로운 세금 설정 데이터 파일 생성")
        except Exception as e:
            print(f"❌ 세금 설정 데이터 로드 실패: {e}")
            self.tax_settings = {}
    
    def save_data(self) -> bool:
        """세금 설정 데이터 저장"""
        try:
            with open(TAX_SETTINGS_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.tax_settings, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"❌ 세금 설정 데이터 저장 실패: {e}")
            return False
    
    def set_tax(self, guild_id: str, role_id: str, xp_amount: int) -> bool:
        """특정 역할에 세금 설정"""
        try:
            if guild_id not in self.tax_settings:
                self.tax_settings[guild_id] = {}
            
            self.tax_settings[guild_id][role_id] = xp_amount
            return self.save_data()
        except Exception as e:
            print(f"❌ 세금 설정 실패: {e}")
            return False
    
    def remove_tax(self, guild_id: str, role_id: str) -> bool:
        """특정 역할의 세금 설정 제거"""
        try:
            if guild_id in self.tax_settings and role_id in self.tax_settings[guild_id]:
                del self.tax_settings[guild_id][role_id]
                
                # 해당 서버의 세금 설정이 모두 없으면 서버 데이터도 제거
                if not self.tax_settings[guild_id]:
                    del self.tax_settings[guild_id]
                
                return self.save_data()
            return False
        except Exception as e:
            print(f"❌ 세금 설정 제거 실패: {e}")
            return False
    
    def clear_all_taxes(self, guild_id: str) -> bool:
        """특정 서버의 모든 세금 설정 초기화"""
        try:
            if guild_id in self.tax_settings:
                del self.tax_settings[guild_id]
                return self.save_data()
            return True
        except Exception as e:
            print(f"❌ 세금 설정 초기화 실패: {e}")
            return False
    
    def get_tax_settings(self, guild_id: str) -> Dict[str, int]:
        """특정 서버의 세금 설정 목록 반환"""
        return self.tax_settings.get(guild_id, {})
    
    def get_tax_amount(self, guild_id: str, role_id: str) -> Optional[int]:
        """특정 역할의 세금 XP 반환"""
        guild_taxes = self.tax_settings.get(guild_id, {})
        return guild_taxes.get(role_id)

# 전역 인스턴스
tax_manager = TaxManager()

class TaxClearConfirmView(discord.ui.View):
    """세금 초기화 확인 뷰"""
    
    def __init__(self, admin_id: int, guild_id: str, tax_manager):
        super().__init__(timeout=60)
        self.admin_id = admin_id
        self.guild_id = guild_id
        self.tax_manager = tax_manager
    
    @discord.ui.button(label="✅ 확인", style=discord.ButtonStyle.danger)
    async def confirm_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 권한 재확인
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message(
                "❌ 본인만 이 작업을 승인할 수 있습니다.", 
                ephemeral=True
            )
        
        # 초기화 실행
        success = self.tax_manager.clear_all_taxes(self.guild_id)
        
        if success:
            embed = discord.Embed(
                title="✅ 세금 설정 초기화 완료",
                description="모든 세금 설정이 삭제되었습니다.",
                color=discord.Color.green()
            )
            embed.add_field(
                name="ℹ️ 안내",
                value="새로운 세금을 설정하려면 `/세금설정` 명령어를 사용하세요.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[세금초기화] {interaction.user.display_name} ({interaction.user.id}) 모든 세금 설정 삭제")
        else:
            embed = discord.Embed(
                title="❌ 초기화 실패",
                description="세금 설정 초기화 중 오류가 발생했습니다.",
                color=discord.Color.red()
            )
        
        await interaction.response.edit_message(embed=embed, view=None)
    
    @discord.ui.button(label="❌ 취소", style=discord.ButtonStyle.secondary)
    async def cancel_clear(self, interaction: discord.Interaction, button: discord.ui.Button):
        # 권한 재확인
        if interaction.user.id != self.admin_id:
            return await interaction.response.send_message(
                "❌ 본인만 이 작업을 취소할 수 있습니다.", 
                ephemeral=True
            )
        
        embed = discord.Embed(
            title="✅ 취소됨",
            description="세금 설정 초기화가 취소되었습니다.",
            color=discord.Color.blue()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class TaxSystemCog(commands.Cog):
    """등급별 세금 시스템 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tax_manager = tax_manager
        self.db = db_manager
    
    @app_commands.command(name="세금설정", description="특정 역할에 대한 세금 XP를 설정합니다 (관리자 전용)")
    @app_commands.describe(역할="세금을 부과할 역할", xp="빼앗을 XP 양")
    async def set_tax(self, interaction: discord.Interaction, 역할: discord.Role, xp: int):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        # XP 유효성 검사
        if xp <= 0:
            return await interaction.response.send_message(
                "❌ 세금 XP는 1 이상이어야 합니다.", 
                ephemeral=True
            )
        
        if xp > 100000:
            return await interaction.response.send_message(
                "❌ 세금 XP는 100,000 이하여야 합니다.", 
                ephemeral=True
            )
        
        # @everyone 역할 확인
        if 역할.is_default():
            return await interaction.response.send_message(
                "❌ @everyone 역할에는 세금을 설정할 수 없습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        role_id = str(역할.id)
        
        # 기존 설정이 있는지 확인
        existing_tax = self.tax_manager.get_tax_amount(guild_id, role_id)
        
        # 세금 설정
        success = self.tax_manager.set_tax(guild_id, role_id, xp)
        
        if success:
            embed = discord.Embed(
                title="✅ 세금 설정 완료",
                description=f"**{역할.name}** 역할에 대한 세금이 설정되었습니다.",
                color=discord.Color.green()
            )
            
            embed.add_field(
                name="💰 세금 정보",
                value=f"역할: **{역할.name}**\n"
                      f"세금 XP: **{format_xp(xp)}**\n"
                      f"대상 사용자: **{len([m for m in interaction.guild.members if 역할 in m.roles and not m.bot])}명**",
                inline=True
            )
            
            # 기존 설정과 비교
            if existing_tax:
                embed.add_field(
                    name="🔄 변경사항",
                    value=f"이전: **{format_xp(existing_tax)}**\n새로운: **{format_xp(xp)}**",
                    inline=True
                )
            else:
                embed.add_field(
                    name="🆕 새 설정",
                    value="처음 설정된 세금입니다.",
                    inline=True
                )
            
            embed.add_field(
                name="ℹ️ 사용법",
                value=f"`/세금수거 역할:{역할.name}`로 세금을 수거할 수 있습니다.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[세금설정] {interaction.user.display_name} ({interaction.user.id}) {역할.name} 세금 설정: {format_xp(xp)}")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            await interaction.response.send_message(
                "❌ 세금 설정에 실패했습니다. 다시 시도해주세요.", 
                ephemeral=True
            )
    
    @app_commands.command(name="세금수거", description="특정 역할의 사용자들로부터 세금을 수거합니다 (관리자 전용)")
    @app_commands.describe(역할="세금을 수거할 역할")
    async def collect_tax(self, interaction: discord.Interaction, 역할: discord.Role):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        # 데이터베이스 연결 확인
        if not DATABASE_AVAILABLE or not self.db:
            return await interaction.response.send_message(
                "❌ 데이터베이스를 사용할 수 없습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        role_id = str(역할.id)
        
        # 세금 설정 확인
        tax_amount = self.tax_manager.get_tax_amount(guild_id, role_id)
        if not tax_amount:
            return await interaction.response.send_message(
                f"❌ **{역할.name}** 역할에 설정된 세금이 없습니다.\n"
                f"`/세금설정 역할:{역할.name} xp:100` 같은 형태로 먼저 세금을 설정해주세요.", 
                ephemeral=True
            )
        
        # 대상 사용자 확인
        target_members = [m for m in interaction.guild.members if 역할 in m.roles and not m.bot]
        
        if not target_members:
            return await interaction.response.send_message(
                f"❌ **{역할.name}** 역할을 가진 사용자가 없습니다.", 
                ephemeral=True
            )
        
        # 진행 상황 알림
        embed = discord.Embed(
            title="🔄 세금 수거 진행 중...",
            description=f"**{역할.name}** 역할의 **{len(target_members)}명**에게서 세금을 수거하고 있습니다.",
            color=discord.Color.yellow()
        )
        await interaction.response.send_message(embed=embed, ephemeral=False)
        
        # 세금 수거 실행
        success_count = 0
        failed_count = 0
        total_collected = 0
        success_details = []
        failed_details = []
        
        for member in target_members:
            try:
                user_id = str(member.id)
                
                # 사용자 등록 확인
                if not self.db.get_user(user_id):
                    failed_count += 1
                    failed_details.append(f"{member.display_name} (미등록)")
                    continue
                
                # 현재 XP 확인
                current_xp_data = self.db.get_user_xp(guild_id, user_id)
                if not current_xp_data:
                    failed_count += 1
                    failed_details.append(f"{member.display_name} (XP 데이터 없음)")
                    continue
                
                current_xp = current_xp_data['xp']
                
                # 실제 수거할 XP 계산 (보유 XP보다 많으면 보유 XP만큼만)
                actual_tax = min(tax_amount, current_xp)
                
                if actual_tax <= 0:
                    failed_count += 1
                    failed_details.append(f"{member.display_name} (XP 부족: {format_xp(current_xp)})")
                    continue
                
                # 이전 레벨 기록
                old_level = current_xp_data['level']
                
                # XP 차감 (마이너스 값으로 추가)
                result = self.db.add_user_xp(guild_id, user_id, -actual_tax)
                
                success_count += 1
                total_collected += actual_tax
                
                # 레벨 다운 여부 확인
                level_change = ""
                if isinstance(result, dict) and result.get('level', old_level) < old_level:
                    level_change = f" (Lv.{old_level}→{result['level']})"
                
                success_details.append(f"{member.display_name}: -{format_xp(actual_tax)}{level_change}")
                
            except Exception as e:
                failed_count += 1
                failed_details.append(f"{member.display_name} (오류: {str(e)})")
        
        # 결과 임베드 생성
        if success_count > 0:
            result_embed = discord.Embed(
                title="✅ 세금 수거 완료",
                description=f"**{역할.name}** 역할에서 세금을 성공적으로 수거했습니다.",
                color=discord.Color.green()
            )
        else:
            result_embed = discord.Embed(
                title="❌ 세금 수거 실패",
                description=f"**{역할.name}** 역할에서 세금을 수거할 수 없었습니다.",
                color=discord.Color.red()
            )
        
        # 수거 통계
        result_embed.add_field(
            name="📊 수거 통계",
            value=f"**성공**: {success_count}명\n**실패**: {failed_count}명\n**총 수거량**: {format_xp(total_collected)}",
            inline=True
        )
        
        result_embed.add_field(
            name="💰 세금 정보",
            value=f"설정 세금: {format_xp(tax_amount)}\n평균 수거량: {format_xp(total_collected // max(success_count, 1))}",
            inline=True
        )
        
        # 성공 목록 (최대 10명)
        if success_details:
            success_text = "\n".join(success_details[:10])
            if len(success_details) > 10:
                success_text += f"\n... 외 {len(success_details) - 10}명"
            
            result_embed.add_field(
                name="✅ 수거 성공",
                value=f"```{success_text}```",
                inline=False
            )
        
        # 실패 목록 (최대 5명)
        if failed_details:
            failed_text = "\n".join(failed_details[:5])
            if len(failed_details) > 5:
                failed_text += f"\n... 외 {len(failed_details) - 5}명"
            
            result_embed.add_field(
                name="❌ 수거 실패",
                value=f"```{failed_text}```",
                inline=False
            )
        
        # 로그 기록
        log_admin_action(f"[세금수거] {interaction.user.display_name} ({interaction.user.id}) {역할.name} 수거: 성공 {success_count}명, 실패 {failed_count}명, 총 {format_xp(total_collected)}")
        
        await interaction.edit_original_response(embed=result_embed)
    
    @app_commands.command(name="세금목록", description="현재 설정된 세금 목록을 확인합니다")
    async def tax_list(self, interaction: discord.Interaction):
        guild_id = str(interaction.guild.id)
        guild_taxes = self.tax_manager.get_tax_settings(guild_id)
        
        embed = discord.Embed(
            title="💸 세금 설정 목록",
            description="현재 서버에 설정된 세금 목록입니다.",
            color=discord.Color.gold()
        )
        
        if not guild_taxes:
            embed.add_field(
                name="ℹ️ 설정 현황",
                value="설정된 세금이 없습니다.\n`/세금설정` 명령어로 세금을 설정할 수 있습니다.",
                inline=False
            )
        else:
            # 세금 목록 정리
            valid_taxes = []
            invalid_taxes = []
            total_target_users = 0
            
            for role_id, xp_amount in guild_taxes.items():
                try:
                    role = interaction.guild.get_role(int(role_id))
                    if role:
                        target_count = len([m for m in interaction.guild.members if role in m.roles and not m.bot])
                        valid_taxes.append({
                            'role': role,
                            'xp': xp_amount,
                            'target_count': target_count
                        })
                        total_target_users += target_count
                    else:
                        invalid_taxes.append({'role_id': role_id, 'xp': xp_amount})
                except:
                    invalid_taxes.append({'role_id': role_id, 'xp': xp_amount})
            
            # 유효한 세금 목록 표시
            if valid_taxes:
                # XP 높은 순으로 정렬
                valid_taxes.sort(key=lambda x: x['xp'], reverse=True)
                
                tax_list = ""
                for i, tax_info in enumerate(valid_taxes, 1):
                    tax_list += f"**{i}. {tax_info['role'].name}**\n"
                    tax_list += f"   세금: {format_xp(tax_info['xp'])}\n"
                    tax_list += f"   대상: {tax_info['target_count']}명\n\n"
                
                embed.add_field(
                    name="📋 세금 목록",
                    value=tax_list,
                    inline=False
                )
            
            # 통계 정보
            embed.add_field(
                name="📊 통계",
                value=f"**설정된 역할**: {len(valid_taxes)}개\n"
                      f"**총 대상 사용자**: {total_target_users}명\n"
                      f"**평균 세금**: {format_xp(sum(tax['xp'] for tax in valid_taxes) // max(len(valid_taxes), 1))}",
                inline=True
            )
            
            # 잘못된 설정 알림
            if invalid_taxes:
                embed.add_field(
                    name="⚠️ 정리 필요",
                    value=f"삭제된 역할 {len(invalid_taxes)}개의 세금 설정이 있습니다.\n관리자가 `/세금초기화`를 실행하여 정리할 수 있습니다.",
                    inline=True
                )
        
        embed.set_footer(text=f"확인자: {interaction.user.display_name}")
        await interaction.response.send_message(embed=embed, ephemeral=False)
    
    @app_commands.command(name="세금삭제", description="특정 역할의 세금 설정을 삭제합니다 (관리자 전용)")
    @app_commands.describe(역할="세금 설정을 삭제할 역할")
    async def remove_tax(self, interaction: discord.Interaction, 역할: discord.Role):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        role_id = str(역할.id)
        
        # 기존 설정 확인
        existing_tax = self.tax_manager.get_tax_amount(guild_id, role_id)
        if not existing_tax:
            return await interaction.response.send_message(
                f"❌ **{역할.name}** 역할에 설정된 세금이 없습니다.", 
                ephemeral=True
            )
        
        # 세금 설정 제거
        success = self.tax_manager.remove_tax(guild_id, role_id)
        
        if success:
            embed = discord.Embed(
                title="✅ 세금 삭제 완료",
                description=f"**{역할.name}** 역할의 세금 설정이 삭제되었습니다.",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="🗑️ 삭제된 세금",
                value=f"{역할.name} → **{format_xp(existing_tax)}**",
                inline=False
            )
            
            embed.add_field(
                name="ℹ️ 안내",
                value="• 이미 수거된 세금은 되돌려지지 않습니다.\n"
                      "• `/세금목록`으로 남은 세금 설정을 확인할 수 있습니다.",
                inline=False
            )
            
            # 로그 기록
            log_admin_action(f"[세금삭제] {interaction.user.display_name} ({interaction.user.id}) {역할.name} 세금 삭제 ({format_xp(existing_tax)})")
            
            await interaction.response.send_message(embed=embed, ephemeral=False)
        else:
            await interaction.response.send_message(
                "❌ 세금 삭제에 실패했습니다. 다시 시도해주세요.", 
                ephemeral=True
            )
    
    @app_commands.command(name="세금초기화", description="모든 세금 설정을 초기화합니다 (관리자 전용)")
    async def clear_all_taxes(self, interaction: discord.Interaction):
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(
                "🚫 이 명령어는 관리자만 사용할 수 있습니다.", 
                ephemeral=True
            )
        
        guild_id = str(interaction.guild.id)
        guild_taxes = self.tax_manager.get_tax_settings(guild_id)
        
        if not guild_taxes:
            return await interaction.response.send_message(
                "ℹ️ 삭제할 세금 설정이 없습니다.", 
                ephemeral=True
            )
        
        # 확인 버튼이 있는 임베드 표시
        embed = discord.Embed(
            title="⚠️ 세금 설정 전체 초기화",
            description=f"정말로 **{len(guild_taxes)}개**의 모든 세금 설정을 삭제하시겠습니까?",
            color=discord.Color.orange()
        )
        
        # 현재 설정 미리보기
        preview_list = ""
        for i, (role_id, xp_amount) in enumerate(list(guild_taxes.items())[:5], 1):
            try:
                role = interaction.guild.get_role(int(role_id))
                role_name = role.name if role else f"삭제된 역할 ({role_id})"
                preview_list += f"{i}. {role_name}: {format_xp(xp_amount)}\n"
            except:
                preview_list += f"{i}. 오류 역할: {format_xp(xp_amount)}\n"
        
        if len(guild_taxes) > 5:
            preview_list += f"... 외 {len(guild_taxes) - 5}개"
        
        embed.add_field(
            name="🗑️ 삭제될 설정 (미리보기)",
            value=preview_list,
            inline=False
        )
        
        embed.add_field(
            name="⚠️ 주의사항",
            value="• 이 작업은 **되돌릴 수 없습니다**\n• 이미 수거된 세금은 되돌려지지 않습니다",
            inline=False
        )
        
        view = TaxClearConfirmView(interaction.user.id, guild_id, self.tax_manager)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ✅ setup 함수
async def setup(bot: commands.Bot):
    await bot.add_cog(TaxSystemCog(bot))
    print("✅ 등급별 세금 시스템 로드 완료")