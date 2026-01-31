# tax_system.py - 세금 시스템
from __future__ import annotations
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, List, Optional, Tuple
import json
import os
from discord.ui import View

# 외부 유틸리티 함수 임포트
try:
    from common_utils import log_admin_action, format_xp, now_str
except ImportError:
    # 모듈이 없을 경우를 대비한 대체(Fallback) 함수 정의
    def log_admin_action(message: str):
        print(f"[ADMIN LOG] {message}")
    
    def format_xp(xp: int) -> str:
        return f"{xp:,} XP"
    
    def now_str() -> str:
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# 데이터베이스 관리자 임포트
def safe_import_database():
    try:
        from database_manager import get_guild_db_manager
        return get_guild_db_manager, True
    except ImportError:
        print("⚠️ DatabaseManager 임포트 실패")
        return None, False

# DB 함수 및 사용 가능 여부 확인
get_guild_db_manager_func, DATABASE_AVAILABLE = safe_import_database()

# 데이터 저장 경로 설정
DATA_DIR = "data"
TAX_SETTINGS_FILE = os.path.join(DATA_DIR, "tax_settings.json")

# 저장 디렉토리 자동 생성
os.makedirs(DATA_DIR, exist_ok=True)

class TaxManager:
    """세금 시스템 관리 클래스"""
    
    def __init__(self):
        self.tax_settings: Dict[str, Dict[str, int]] = {}
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
    
    def set_tax(self, guild_id: str, role_id: str, tax_rate: float) -> bool:
        """특정 역할에 세금 비율(%) 설정"""
        try:
            if guild_id not in self.tax_settings:
                self.tax_settings[guild_id] = {}
        
            # tax_rate는 0.01 (1%) ~ 1.0 (100%) 사이의 값으로 저장
            self.tax_settings[guild_id][role_id] = tax_rate
            return self.save_data()
        except Exception as e:
            print(f"❌ 세금 설정 실패: {e}")
            return False
    
# 전역 인스턴스
tax_manager = TaxManager()

class TaxPagingView(View):
    def __init__(self, title, members_list, chunk_size=15):
        super().__init__(timeout=120) # 시간을 조금 더 늘림
        self.title = title
        self.members_list = members_list
        self.chunk_size = chunk_size
        self.current_index = chunk_size

    @discord.ui.button(label="다음 목록 보기", style=discord.ButtonStyle.gray, emoji="⏭️")
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        next_chunk = self.members_list[self.current_index : self.current_index + self.chunk_size]
        
        # 다음 페이지 내용 생성
        embed = discord.Embed(
            title=f"{self.title} (추가 목록 {self.current_index // self.chunk_size + 1}P)",
            description="\n".join(next_chunk),
            color=discord.Color.orange()
        )
        
        self.current_index += self.chunk_size
        
        # 더 이상 줄 데이터가 없으면 버튼 비활성화
        if self.current_index >= len(self.members_list):
            button.disabled = True
            button.label = "마지막 페이지"

        await interaction.response.send_message(embed=embed, ephemeral=False, view=self if not button.disabled else None)

class TaxSystemCog(commands.Cog):
    """등급별 세금 시스템 Cog"""
    
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.tax_manager = tax_manager
    
    @app_commands.command(name="세금수거", description="[관리자 전용] 특정 역할 유저들에게 % 단위로 세금을 수거합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(역할="세금을 수거할 역할", 퍼센트="징수할 비율 (%)")
    async def collect_tax_percent(self, interaction: discord.Interaction, 역할: discord.Role, 퍼센트: float):
        if not 0 < 퍼센트 <= 100:
            return await interaction.response.send_message("❌ 퍼센트는 0보다 크고 100 이하이어야 합니다.", ephemeral=True)

        await interaction.response.defer()
        
        db = get_guild_db_manager_func(str(interaction.guild.id))
        members = 역할.members
        
        tax_results = [] 
        total_collected = 0 # 수거 총액 변수
        success_count = 0
        
        for member in members:
            if member.bot: continue
            
            user_data = db.get_user(str(member.id))
            if not user_data: continue
            
            before_cash = user_data.get('cash', 0)
            tax_amount = int(before_cash * (퍼센트 / 100))
            after_cash = before_cash - tax_amount
            
            if tax_amount > 0:
                db.update_user_cash(str(member.id), after_cash)
                db.add_transaction(str(member.id), "세금징수", -tax_amount, f"{역할.name} 세금 {퍼센트}%")
                success_count += 1
                total_collected += tax_amount # 총액 누적

            tax_results.append(f"{member.display_name} {before_cash:,}원 -> {after_cash:,}원 (수거액: {tax_amount:,}원)")

        if not tax_results:
            return await interaction.followup.send(f"ℹ️ {역할.name} 역할에 등록된 유저가 없습니다.")

        # --- 출력 부분 ---
        embed = discord.Embed(
            title="💰 세금 수거 및 국고 환수 결과",
            description=f"**역할명:** {역할.name}\n**징수 비율:** {퍼센트}%\n**총 수거액:** ✨ `{total_collected:,}원` ✨",
            color=discord.Color.gold(), # 총액 강조를 위해 금색으로 변경
            timestamp=discord.utils.utcnow()
        )

        chunk_size = 15
        first_chunk = tax_results[:chunk_size]
        formatted_list = "\n".join([f"{i+1}. {line}" for i, line in enumerate(first_chunk)])

        embed.add_field(
            name=f"📊 상세 내역 (대상: {success_count}명)",
            value=f"```\n{formatted_list}```",
            inline=False
        )

        # 요약 필드 추가
        embed.set_footer(text=f"합계: {total_collected:,}원 이 수거되었습니다.")

        if len(tax_results) > chunk_size:
            view = TaxPagingView(f"{역할.name} 수거 상세 목록", tax_results)
            await interaction.followup.send(embed=embed, view=view)
        else:
            await interaction.followup.send(embed=embed)

        log_admin_action(f"[세금수거] {interaction.user.display_name} : {역할.name} {퍼센트}% 수거 (총액: {total_collected:,}원)") 

async def setup(bot: commands.Bot):
    await bot.add_cog(TaxSystemCog(bot))