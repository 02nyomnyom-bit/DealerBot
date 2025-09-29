from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
import datetime
import json
import os

# 실시간 업데이트 시스템 안전 import
UPDATE_SYSTEM_AVAILABLE = False
try:
    from update_system import get_realtime_updates_summary, get_update_statistics
    UPDATE_SYSTEM_AVAILABLE = True
except ImportError:
    def get_realtime_updates_summary(count=5):
        return "⚠️ 실시간 업데이트 시스템이 로드되지 않았습니다."
    def get_update_statistics():
        return {
            'total_active': 0, 'total_archived': 0, 'today_count': 0,
            'priority_counts': {'긴급': 0, '중요': 0, '일반': 0}
        }

# ✅ JSON 파일 로드 헬퍼 함수 추가
def load_json_file(file_path):
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return []
    except Exception as e:
        print(f"❌ JSON 파일 로드 오류: {file_path} - {e}")
        return []

# ✅ 게임 데이터 로드
GAMES_DATA = load_json_file('data/games.json')

# 📖 도움말 카테고리 선택 드롭다운
class HelpCategorySelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="카테고리를 선택하세요!",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="통합 출석 & XP", description="출석, 레벨업, 순위표 등", emoji="📆", value="attendance"),
                discord.SelectOption(label="현금 시스템", description="현금, 지갑, 선물 등", emoji="💰", value="cash"),
                discord.SelectOption(label="게임 명령어", description="블랙잭, 주사위, 강화 등", emoji="🎮", value="games"),
                discord.SelectOption(label="기타", description="봇 정보, 업데이트 등", emoji="✨", value="other")
            ]
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        embed = discord.Embed(title="📖 도움말 메뉴", color=discord.Color.blue())
        
        if category == "attendance":
            embed.add_field(name="📆 통합 출석 & XP 명령어",
                    value="`/출석체크` - 하루 한번 출석체크 (현금 + XP 동시 지급)\n"
                          "`/출석현황` - 나의 현재 출석 현황을 확인합니다.\n"
                          "`/출석랭킹` - 서버 내 출석 랭킹을 확인합니다\n"
                          "`/레벨` - 자신 또는 다른 사용자의 레벨 및 XP를 확인합니다.\n"
                          "`/레벨순위` - XP 리더보드를 확인합니다\n"
                          "`/보이스시간` - 통화방에서 보낸 총 시간을 확인합니다.\n"
                          "`/보이스랭크` - 사용자의 통화 시간을 공개적으로 확인합니다\n"
                          "`/보이스통계` - 기간별 통화 순위를 공개적으로 확인합니다 (상위 10명)\n"
                          "`/보이스현황` - 현재 통화 중인 사용자들을 확인합니다\n",
                    inline=False)
        elif category == "cash":
            embed.add_field(name="💰 현금 시스템 명령어",
                    value="`/등록` - Gamble에 플레이어로 등록합니다\n"
                          "`/지갑` - 현재 보유 현금을 확인합니다\n"
                          "`/선물` - 다른 사용자에게 현금을 선물합니다\n"
                          "`/현금순위` - 현금 보유 순위를 확인합니다\n"
                          "`/탈퇴` - Gamble에서 탈퇴합니다 (모든 데이터 삭제)\n"
                          "`/현금교환` - XP를 현금으로 교환합니다. 수수료가 부과됩니다.\n"
                          "`/경험치교환` - 현금을 XP로 교환합니다. 수수료가 부과됩니다.\n"
                          "`/교환현황` - XP/현금 교환 시스템의 현재 상태를 확인합니다.\n",
                    inline=False)
        elif category == "games":
            embed.add_field(name="🎮 게임 명령어",
                    value="`/블랙잭` - 🃏 블랙잭 게임을 플레이합니다.\n"
                          "`        배팅 = 배팅할 현금 (기본값: 10원, 최대 2,000원)`\n"
                          "\n"
                          "`/주사위` - 주사위 게임을 플레이합니다.\n"
                          "`        모드 = 싱글(봇과 대결) 또는 멀티(다른 유저와 대결)`\n"
                          "`        배팅 = 배팅할 현금 (기본값: 10원, 싱글 모드 최대 1,000원)`\n"
                          "`        상대방 = 멀티 모드에서 특정 상대방 지정 (선택사항)`\n"
                          "\n"
                          "`/강화` - 아이템을 강화합니다.\n"
                          "`     아이템명 = 강화할 아이템의 이름`\n"
                          "`/내강화` - 내가 소유한 아이템 목록을 확인합니다.\n"
                          "`/강화순위` - 전체 강화 순위를 확인합니다.\n"
                          "`/강화정보` - 강화 시스템에 대한 정보를 확인합니다.\n"
                          "\n"
                          "`/경마` - 경마 게임을 생성합니다.\n"
                          "`      모드 = 경마 모드를 선택하세요`\n"
                          "`      인원 = 수동 모드: 최대 참가자 수 / 자동 모드: 참가자 이름 (쉼표로 구분)`\n"
                          "\n"
                          "`/홀짝` - 홀짝 게임을 플레이합니다.\n"
                          "`      모드 = 싱글(봇과 대결) 또는 멀티(다른 유저와 대결)`\n"
                          "`      배팅 = 배팅할 현금 (기본값: 10원, 최대 1,000원)`\n"
                          "`      상대방 = 멀티 모드에서 특정 상대방 지정 (선택사항)`\n"
                          "\n"
                          "`/가위바위보` - 가위바위보 게임 시작\n"
                          "`            모드 = 싱글 또는 멀티 선택`\n"
                          "`            배팅 = 배팅할 현금 (1~1,000원), 미입력시 10원이 나갑니다.`\n"
                          "`            상대방 = (선택 사항) 상대 플레이어를 지정하세요.`\n"
                          "\n"
                          "`/슬롯머신` - 🎰 슬롯머신 게임을 플레이합니다.\n"
                          "`         배팅 = 배팅할 현금 (기본값: 10원, 최대 5,000원)`\n"
                          "\n"
                          "`/야바위게임` - 야바위 게임을 시작합니다.\n"
                          "`           배팅 = 배팅할 현금 (기본값: 10원, 최대 500원)`\n",
                    inline=False)
            view = HelpCategoryView(include_game_select=True)
            await interaction.response.edit_message(embed=embed, view=view)
            return
        elif category == "other":
            embed.add_field(name="✨ 기타 명령어",
                    value="`도움말` - 봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.\n"
                          "`안녕` - 딜러양과 인사하고 최신 업데이트를 확인합니다\n"
                          "`업데이트` - 실시간 업데이트 내용만 확인합니다\n",
                            inline=False)

        view = HelpCategoryView()
        await interaction.response.edit_message(embed=embed, view=view)

# 📖 관리자 도움말 카테고리 선택 드롭다운
class AdminHelpCategorySelect(discord.ui.Select):
    def __init__(self):
        super().__init__(
            placeholder="관리자 카테고리를 선택하세요!",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="현금 및 경험치", description="현금, XP, 교환, 세금 등", emoji="💰", value="admin_cash_xp"),
                discord.SelectOption(label="역할 및 채널", description="레벨 역할, 환영 메시지 등", emoji="🛠️", value="admin_roles_channels"),
                discord.SelectOption(label="백업 및 시스템", description="백업, 시스템 통계, 에러 등", emoji="💾", value="admin_system"),
                discord.SelectOption(label="사용자 및 업데이트", description="사용자 관리, 업데이트 시스템 등", emoji="📊", value="admin_users_updates")
            ]
        )
    
    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        
        embed = discord.Embed(title="📖 도움말 메뉴", color=discord.Color.blue())
        
        if category == "admin_cash_xp":
            embed.add_field(name="🛠️ 현금 및 경험치",
                    value="`/경험치관리` - XP 및 레벨 관리\n"
                          "`            XP 지급 / XP 차감 / XP 설정`\n"
                          "`            레벨 설정`\n"
                          "`            사용자 초기화`\n"
                          "`            서버 통계`\n"
                          "`            설정 보기`\n"
                          "`            채팅XP설정 / 음성XP설정 / 출석XP설정 / 채팅쿨다운설정`\n"
                          "`/경험치데이터확인` - 등록되지 않은 사용자의 경험치 데이터를 확인합니다\n"
                          "\n"                         
                          "`/현금지급` - 사용자에게 현금을 지급합니다\n"
                          "`/현금차감` - 사용자의 현금을 차감합니다\n"
                          "\n" 
                          "`/선물설정` - `선물 시스템 설정을 변경합니다\n"
                          "`             수수료율 = 수수료율 (0.0 ~ 1.0, 예: 0.1 = 10%)`\n"
                          "`             최소금액 = 최소 선물 금액`\n"
                          "`             최대금액 = 최대 선물 금액`\n"
                          "`             일일제한 = 일일 선물 횟수 제한`\n"
                          "`             쿨다운분 = 선물 쿨다운 시간 (분)`\n"
                          "\n"
                          "`/교환설정` - 교환 시스템 설정을 변경합니다\n"
                          "`          현금수수료 = 현금 교환시 차감할 수수료율 (%)`\n"
                          "`          경험치수수료 = XP 교환시 차감할 수수료율 (%)`\n"
                          "`          횟수= 하루 최대 교환 횟수`\n"
                          "`          쿨다운 = 교환 쿨다운 시간`\n"
                          "\n"
                          "`/세금설정` - 특정 역할에 대한 세금 XP를 설정합니다\n"
                          "`/세금목록` - 현재 설정된 세금 목록을 확인합니다\n"
                          "`/세금삭제` - 특정 역할의 세금 설정을 삭제합니다\n"
                          "`/세금초기화` - 모든 세금 설정을 초기화합니다\n"
                          "\n"
                          "`/리더보드관리` - 리더보드 시스템 통합 관리\n"
                          "`/리더보드설정` - 리더보드 및 출석 설정을 확인하고 수정합니다\n"
                          "`             💰 출석 현금 보상 / ✨ 출석 XP 보상`\n"
                          "`             🎁 7일 현금 보너스 / ✨ 7일 XP 보너스`\n"
                          "`             🏆 30일 현금 보너스 / ⭐ 30일 XP 보너스`\n",
                    inline=False)
        elif category == "admin_roles_channels":
            embed.add_field(name="🛠️ 역할 및 채널",
                    value="`/레벨업채널설정` - 레벨업 알림을 받을 채널을 설정합니다\n"
                          "\n"
                          "`/역할설정` - 특정 레벨에 도달시 부여할 역할을 설정합니다\n"
                          "`/역할목록` - 설정된 레벨별 역할 보상 목록을 확인합니다\n"
                          "`/역할삭제` - 특정 레벨의 역할 보상을 삭제합니다\n"
                          "`/역할초기화` - 모든 레벨별 역할 보상을 삭제합니다\n"
                          "`/역할알림채널설정` - 레벨 역할 지급 안내 채널을 설정합니다\n"
                          "`/역할알림채널해제` - 레벨 역할 지급 안내 채널 설정을 해제합니다\n"
                          "\n"
                          "`/환영설정` - 서버의 환영 메시지 시스템을 설정합니다\n"
                          "`          기능 = 설정할 기능을 선택하세요`\n"
                          "`          채널 = 환영 메시지를 보낼 채널`\n"
                          "`          메시지 = 사용자 정의 환영 메시지`\n"
                          "`          dm_사용 = DM 환영 메시지 사용 여부`\n"
                          "`          자동역할 = 새 멤버에게 자동으로 부여할 역할`\n"
                          "`/환영테스트` - 환영 메시지를 테스트합니다\n"
                          "\n"
                          "`/퇴장로그설정` - 멤버 퇴장 로그 채널을 설정합니다\n"
                          "`/퇴장로그비활성화` - 멤버 퇴장 로그를 비활성화합니다\n"
                          "`/퇴장로그상태` - 현재 퇴장 로그 설정 상태를 확인합니다\n",
                    inline=False)
        elif category == "admin_system":
            embed.add_field(name="🛠️ 백업 및 시스템",
                    value="`/데이터초기화` - 사용자의 모든 데이터를 초기화합니다\n"
                          "`/보이스초기화` - 통화 시간 데이터를 초기화합니다\n"
                          "`/강화초기화` - 모든 강화 데이터를 초기화합니다\n"
                          "\n"
                          "`/글삭제` - 메시지를 삭제합니다\n",
                    inline=False)
            
        elif category == "admin_users_updates":
            embed.add_field(name="🛠️ 사용자 및 업데이트",
                    value="`/사용자관리` - 통합 사용자 관리 패널을 표시합니다\n"
                          "`/사용자정보` - 특정 사용자의 상세 정보를 확인합니다\n"
                          "\n"
                          "`/등록목록` - 등록된 사용자 목록을 확인합니다\n"
                          "\n"
                          "`/업데이트추가` - 새로운 업데이트를 추가합니다\n"
                          "`/업데이트목록` - 현재 실시간 업데이트 목록을 확인합니다\n"
                          "`/업데이트삭제` - 특정 ID의 업데이트를 삭제합니다\n"
                          "`/전체업데이트정리` - 모든 실시간 및 보관된 업데이트를 삭제합니다\n"
                          "`/업데이트통계` - 실시간 업데이트 시스템 통계를 확인합니다\n"
                          "\n"
                          "`/서버제한상태` - 현재 서버 제한 설정 상태를 확인합니다\n"
                          "`/시스템상태` - 봇의 현재 시스템 상태를 확인합니다\n"
                          "`/데이터베이스상태` - 현재 데이터베이스 연결 상태를 확인합니다\n",
                    inline=False)
            
        # 뷰 업데이트
        view = AdminHelpCategoryView()
        await interaction.response.edit_message(embed=embed, view=view)

# 뷰 클래스
class AdminHelpCategoryView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(AdminHelpCategorySelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class HelpCategoryView(discord.ui.View):
    def __init__(self, include_game_select=False):
        super().__init__(timeout=60)
        self.add_item(HelpCategorySelect())

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        await self.message.edit(view=self)

class HelpCommandCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.bot_start_time = datetime.datetime.now(datetime.timezone.utc)
        print("✅ 도움말 시스템 로드 완료")

    # 일반 사용자를 위한 도움말 명령어
    @app_commands.command(name="도움말", description="봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.")
    async def help_command(self, interaction: discord.Interaction):
        try:
            # 실시간 업데이트 요약 정보 가져오기 (update_system.py 로드 확인)
            updates_summary = "⚠️ 실시간 업데이트 시스템이 로드되지 않았습니다."
            if UPDATE_SYSTEM_AVAILABLE:
                updates_summary = get_realtime_updates_summary()

            # 도움말 임베드 생성
            embed = discord.Embed(
                title="📖 딜러양 도움말 메뉴",
                description="아래 드롭다운 메뉴에서 **카테고리**를 선택하여 원하는 명령어의 도움말을 확인하세요.",
                color=discord.Color.blue()
            )
            embed.add_field(
                name="📢 최신 업데이트",
                value=updates_summary,
                inline=False
            )
        
            embed.set_footer(text="메뉴는 60초 후 만료됩니다")
        
            view = HelpCategoryView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
            
            message = await interaction.original_response()
            view.message = message
            
        except Exception as e:
            print(f"도움말 명령어 오류: {e}")
            embed = discord.Embed(
                title="📖 도움말 메뉴",
                description="일부 기능에 오류가 발생했습니다. 기본 기능은 정상적으로 사용 가능합니다.",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    # In HelpCommandCog class
    @app_commands.command(name="관리자도움말", description="봇의 모든 명령어와 기능을 확인할 수 있는 메뉴입니다.")
    async def admin_help_command(self, interaction: discord.Interaction):
        if not interaction.user.guild_permissions.administrator:
            return await interaction.response.send_message(":x: 관리자 권한이 필요합니다.", ephemeral=True)
        try:
            embed = discord.Embed(
                title="📖 딜러양 관리자 도움말 메뉴",
                description="아래 드롭다운 메뉴에서 **카테고리**를 선택하여 원하는 관리자 명령어의 도움말을 확인하세요.",
                color=discord.Color.blue()
            )
        
            # 관리자 전용 드롭다운 뷰 생성
            view = AdminHelpCategoryView()
            await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

            message = await interaction.original_response()
            view.message = message
            
        except Exception as e:
            print(f"관리자 도움말 명령어 오류: {e}")
            await interaction.response.send_message("오류가 발생했습니다. 잠시 후 다시 시도해주세요.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(HelpCommandCog(bot))