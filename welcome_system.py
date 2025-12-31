# welcome_system.py
from __future__ import annotations
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
import json
import os
from datetime import datetime
import asyncio

class WelcomeSystem(commands.Cog):
    """
    Discord 서버 환영 시스템
    
    주요 기능:
    1. 새 멤버 입장 시 설정된 채널로 환영 메시지(Embed) 전송
    2. 중복 메시지 전송 방지 로직 포함
    3. 관리자 명령어를 통한 서버별 맞춤 설정 (메시지, 채널, 역할 등)
    4. 입장 시 자동 역할 부여 및 개인 DM 전송 기능
    """
    def __init__(self, bot):
        self.bot = bot
        self.welcome_config_file = "welcome_config.json"    # 설정 저장 파일명
        self.welcome_configs = self.load_welcome_configs()  # 설정 로드
        
        # 중복 방지를 위한 처리된 멤버 추적
        self.processed_members = set()
        
        # 중복 방지 데이터 정리 작업 시작 (백그라운드 루프)
        self.cleanup_task = None
        self.start_cleanup_task()

    def start_cleanup_task(self):
        """중복 방지 데이터 정리 작업 시작"""
        async def cleanup_old_members():
            while True:
                await asyncio.sleep(300)                # 5분대기
                if len(self.processed_members) > 1000:  # 캐시가 1000개 이상 쌓이면 초기화하여 메모리 관리
                    self.processed_members.clear()
                    print("🧹 환영 시스템: 중복 방지 캐시 정리됨")
        
        if self.cleanup_task is None or self.cleanup_task.done():
            self.cleanup_task = asyncio.create_task(cleanup_old_members())

    def cog_unload(self):
        """Cog가 제거될 때 실행 중인 백그라운드 태스크 취소"""
        if self.cleanup_task:
            self.cleanup_task.cancel()

    def load_welcome_configs(self):
        """JSON 파일에서 서버별 환영 설정을 읽어옴"""
        try:
            if os.path.exists(self.welcome_config_file):
                with open(self.welcome_config_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            print(f"환영 설정 로드 오류: {e}")
            return {}

    def save_welcome_configs(self):
        """현재 설정을 JSON 파일에 물리적으로 저장"""
        try:
            with open(self.welcome_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.welcome_configs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"환영 설정 저장 오류: {e}")

    def get_guild_config(self, guild_id: str):
        """특정 서버의 설정을 반환, 설정이 없으면 기본값 반환"""
        return self.welcome_configs.get(guild_id, {
            "enabled": False,
            "channel_id": None,
            "welcome_message": None,
            "embed_enabled": True,
            "dm_enabled": False,
            "auto_role": None
        })

    @commands.Cog.listener()
    async def on_member_join(self, member):
        """새 멤버가 서버에 입장했을 때 환영 메시지 전송"""
        if member.bot:
            return
        
        # 중복 처리 방지 체크
        member_key = f"{member.guild.id}-{member.id}-{datetime.utcnow().strftime('%Y%m%d%H%M')}"
        if member_key in self.processed_members:
            print(f"❌ 중복 환영 메시지 방지: {member.display_name} ({member.guild.name})")
            return
        
        # 처리 목록에 추가
        self.processed_members.add(member_key)
        
        guild_id = str(member.guild.id)
        config = self.get_guild_config(guild_id)
        
        # 환영 시스템이 비활성화된 경우 중단
        if not config.get("enabled", False):
            print(f"📴 환영 시스템 비활성화: {member.guild.name}")
            return
        
        try:
            print(f"🎊 새 멤버 환영 처리 시작: {member.display_name} → {member.guild.name}")
            
            # 채널 메시지 전송
            channel_id = config.get("channel_id")
            if channel_id:
                channel = self.bot.get_channel(int(channel_id))
                if channel:
                    # 권한 확인 후 전송
                    bot_permissions = channel.permissions_for(member.guild.me)
                    if bot_permissions.send_messages and bot_permissions.embed_links:
                        success = await self.send_welcome_message(member, channel, config)
                        if success:
                            print(f"✅ 환영 메시지 전송 완료: {channel.name}")
                        else:
                            print(f"❌ 환영 메시지 전송 실패: {channel.name}")
                    else:
                        print(f"⚠️ 권한 부족: {channel.name}에 환영 메시지를 보낼 수 없습니다.")
                else:
                    print(f"❌ 환영 채널을 찾을 수 없음: ID {channel_id}")
            
            # 개인 DM 전송 (설정 시)
            if config.get("dm_enabled", False):
                dm_success = await self.send_welcome_dm(member, config)
                if dm_success:
                    print(f"✅ DM 환영 메시지 전송 완료: {member.display_name}")
            
            # 자동 역할 부여 (설정 시)
            auto_role_id = config.get("auto_role")
            if auto_role_id:
                role_success = await self.assign_auto_role(member, int(auto_role_id))
                if role_success:
                    print(f"✅ 자동 역할 부여 완료: {member.display_name}")
        
        except Exception as e:
            print(f"❌ 환영 메시지 전송 오류: {e}") # 실패 시 재시도 가능하게 캐시 삭제
            self.processed_members.discard(member_key)

    async def send_welcome_message(self, member, channel, config):
        """서버 채널에 임베드 형태의 환영 메시지 제작 및 전송"""
        try:
            # 봇 권한 확인
            bot_permissions = channel.permissions_for(channel.guild.me)
            if not bot_permissions.send_messages:
                print(f"권한 오류: {channel.name}에 메시지 보내기 권한이 없습니다.")
                return False
            
            if not bot_permissions.embed_links:
                print(f"권한 오류: {channel.name}에 링크 첨부 권한이 없습니다.")
                return False
            
            welcome_message = config.get("welcome_message") or self.get_default_welcome_message()
            welcome_message = welcome_message.replace('\\n', '\n') # 사용자가 입력한 \\n을 실제 줄바꿈으로 변환
            
            # 변수 치환 ({user}, {server} 등)
            message = welcome_message.format(
                user=member.mention,
                username=member.display_name,
                server=member.guild.name,
                member_count=member.guild.member_count
            )
            
            if config.get("embed_enabled", True):
                # 임베드 형태로 전송
                embed = discord.Embed(
                    title="🎉 새로운 멤버가 도착했어요!",
                    description=message,
                    color=discord.Color.green(),
                    timestamp=datetime.utcnow()
                )
                
                # 사용자 아바타 추가
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(
                    text=f"서버 멤버 수: {member.guild.member_count}명",
                    icon_url=member.guild.icon.url if member.guild.icon else None
                )
                
                await channel.send(embed=embed)
            else:
                await channel.send(message) # 일반 텍스트로 전송
            
            return True
            
        except discord.Forbidden:
            print(f"권한 오류: {channel.name}에 메시지를 보낼 권한이 없습니다.")
            return False
        except Exception as e:
            print(f"환영 메시지 전송 오류: {e}")
            return False

    async def send_welcome_dm(self, member, config):
        """사용자에게 1:1 DM으로 환영 인사를 보냄"""
        try:
            dm_message = config.get("dm_message") or self.get_default_dm_message()
            
            # 메시지 변수 치환
            message = dm_message.format(
                username=member.display_name,
                server=member.guild.name
            )
            
            embed = discord.Embed(
                title=f"🎊 {member.guild.name}에 오신 것을 환영합니다!",
                description=message,
                color=discord.Color.blue(),
                timestamp=datetime.utcnow()
            )
            
            embed.set_thumbnail(url=member.guild.icon.url if member.guild.icon else None)
            
            await member.send(embed=embed)
            return True
            
        except discord.Forbidden:
            print(f"DM 전송 실패: {member.display_name}님이 DM을 차단했습니다.")
            return False
        except Exception as e:
            print(f"DM 환영 메시지 오류: {e}")
            return False

    async def assign_auto_role(self, member, role_id):
        """입장한 멤버에게 자동으로 특정 역할 부여"""
        try:
            role = member.guild.get_role(role_id)
            if not role:
                print(f"자동 역할을 찾을 수 없습니다: {role_id}")
                return False
            
            # 봇 권한 확인
            bot_member = member.guild.me
            if not bot_member.guild_permissions.manage_roles:
                print("봇에게 역할 관리 권한이 없습니다.")
                return False
            
            if role >= bot_member.top_role:
                print(f"역할 {role.name}이 봇의 최고 역할보다 높습니다.")
                return False
            
            await member.add_roles(role, reason="환영 시스템 자동 역할 부여")
            print(f"{member.display_name}님에게 {role.name} 역할을 부여했습니다.")
            return True
            
        except discord.Forbidden:
            print(f"권한 부족: {member.display_name}님에게 역할을 부여할 수 없습니다.")
            return False
        except Exception as e:
            print(f"자동 역할 부여 오류: {e}")
            return False
        
    # 기본 템플릿 정의 (설정되지 않았을 때 사용)
    def get_default_welcome_message(self):
        """기본 환영 메시지"""
        return """안녕하세요 {user}님! 🎉

**{server}**에 오신 것을 환영합니다!

🔸 현재 **{member_count}번째** 멤버가 되셨어요!
🔸 먼저 서버 규칙을 확인해주세요.  
🔸 그 밖에도 궁금한 점이 있으시면 언제든 문의해주세요.

즐거운 시간 보내세요! ✨"""

    def get_default_dm_message(self):
        """기본 DM 환영 메시지"""
        return """안녕하세요 {username}님!

**{server}** 서버에 오신 것을 환영합니다! 🎊

저희 서버에서 즐거운 시간 보내시길 바라며,
궁금한 점이 있으시면 언제든 관리자에게 문의해주세요.

감사합니다! ✨"""

# === 슬래시 명령어: /환영설정 ===
    
    @app_commands.command(name="환영설정", description="[관리자 전용] 서버의 환영 메시지 시스템을 설정합니다.")
    @app_commands.describe(
        기능="설정할 기능을 선택하세요.",
        채널="환영 메시지를 보낼 채널",
        메시지="사용자 정의 환영 메시지",
        dm_사용="DM 환영 메시지 사용 여부",
        자동역할="새 멤버에게 자동으로 부여할 역할"
    )
    @app_commands.choices(기능=[
        app_commands.Choice(name="🔧 환영 시스템 활성화", value="enable"),
        app_commands.Choice(name="❌ 환영 시스템 비활성화", value="disable"),
        app_commands.Choice(name="📝 환영 메시지 설정", value="message"),
        app_commands.Choice(name="📍 환영 채널 설정", value="channel"),
        app_commands.Choice(name="💌 DM 설정", value="dm"),
        app_commands.Choice(name="🎭 자동 역할 설정", value="role"),
        app_commands.Choice(name="📊 현재 설정 보기", value="status"),
        app_commands.Choice(name="🧹 중복 방지 캐시 정리", value="cleanup")
    ])
    async def welcome_config(
        self, 
        interaction: discord.Interaction,
        기능: app_commands.Choice[str],
        채널: Optional[discord.TextChannel] = None,
        메시지: Optional[str] = None,
        dm_사용: Optional[bool] = None,
        자동역할: Optional[discord.Role] = None
    ):
        # 먼저 interaction을 defer하여 시간 연장
        await interaction.response.defer(ephemeral=True)
        
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                "❌ 이 명령어는 **관리자** 권한이 필요합니다."
            )
        
        guild_id = str(interaction.guild.id)
        config = self.get_guild_config(guild_id)
        embed = None
        
        try:
            if 기능.value == "cleanup":
                # 🧹 중복 방지 캐시 정리
                before_count = len(self.processed_members)
                self.processed_members.clear()
                
                embed = discord.Embed(
                    title="🧹 중복 방지 캐시 정리 완료",
                    description=f"처리된 멤버 기록 **{before_count}개**가 정리되었습니다.\n"
                              f"이제 환영 메시지 중복 방지 캐시가 초기화되었습니다.",
                    color=discord.Color.blue()
                )
                embed.add_field(
                    name="ℹ️ 안내",
                    value="중복 메시지 문제가 발생했을 때만 사용하세요.\n"
                          "정상적으로는 자동으로 관리됩니다.",
                    inline=False
                )
                
            elif 기능.value == "enable":
                config["enabled"] = True
                self.welcome_configs[guild_id] = config
                self.save_welcome_configs()
                
                embed = discord.Embed(
                    title="✅ 환영 시스템 활성화",
                    description="환영 메시지 시스템이 활성화되었습니다!\n🛡️ 중복 방지 시스템이 포함되어 있습니다.",
                    color=discord.Color.green()
                )
                
            elif 기능.value == "disable":
                config["enabled"] = False
                self.welcome_configs[guild_id] = config
                self.save_welcome_configs()
                
                embed = discord.Embed(
                    title="❌ 환영 시스템 비활성화",
                    description="환영 메시지 시스템이 비활성화되었습니다.",
                    color=discord.Color.red()
                )
                
            elif 기능.value == "channel":
                if not 채널:
                    embed = discord.Embed(
                        title="❌ 설정 오류",
                        description="환영 메시지를 보낼 채널을 선택해주세요.",
                        color=discord.Color.red()
                    )
                else:
                    # 봇 권한 확인
                    bot_permissions = 채널.permissions_for(interaction.guild.me)
                    missing_permissions = []
                    
                    if not bot_permissions.send_messages:
                        missing_permissions.append("메시지 보내기")
                    if not bot_permissions.embed_links:
                        missing_permissions.append("링크 첨부")
                    if not bot_permissions.view_channel:
                        missing_permissions.append("채널 보기")
                    
                    config["channel_id"] = 채널.id
                    self.welcome_configs[guild_id] = config
                    self.save_welcome_configs()
                    
                    embed = discord.Embed(
                        title="📍 환영 채널 설정 완료",
                        description=f"환영 메시지가 {채널.mention}에서 전송됩니다.",
                        color=discord.Color.green()
                    )
                    
                    # 권한 상태 표시
                    if not missing_permissions:
                        embed.add_field(
                            name="✅ 봇 권한 상태",
                            value="모든 필요한 권한이 있습니다!",
                            inline=False
                        )
                    else:
                        embed.add_field(
                            name="⚠️ 봇 권한 상태",
                            value=f"부족한 권한: {', '.join(missing_permissions)}\n\n"
                                  f"💡 **권한 부여 방법:**\n"
                                  f"1. {채널.mention} → 설정 ⚙️ → 권한\n"
                                  f"2. 봇 역할에게 위 권한들 허용",
                            inline=False
                        )
                
            elif 기능.value == "message":
                if not 메시지:
                    embed = discord.Embed(
                        title="❌ 설정 오류",
                        description="환영 메시지 내용을 입력해주세요.",
                        color=discord.Color.red()
                    )
                else:
                    config["welcome_message"] = 메시지
                    self.welcome_configs[guild_id] = config
                    self.save_welcome_configs()
                    
                    embed = discord.Embed(
                        title="📝 환영 메시지 설정 완료",
                        description="사용자 정의 환영 메시지가 설정되었습니다.",
                        color=discord.Color.blue()
                    )
                    embed.add_field(
                        name="💡 사용 가능한 변수",
                        value="`{user}` - 사용자 멘션\n"
                              "`{username}` - 사용자 이름\n"
                              "`{server}` - 서버 이름\n"
                              "`{member_count}` - 총 멤버 수",
                        inline=False
                    )
                    embed.add_field(
                        name="📝 줄바꿈 팁",
                        value="메시지에서 줄바꿈을 하려면 `\n`을 사용하세요!\n"
                              "예: `안녕하세요!\n환영합니다!`",
                        inline=False
                    )
                    
            elif 기능.value == "dm":
                if dm_사용 is None:
                    embed = discord.Embed(
                        title="❌ 설정 오류",
                        description="DM 사용 여부를 선택해주세요 (True/False).",
                        color=discord.Color.red()
                    )
                else:
                    config["dm_enabled"] = dm_사용
                    self.welcome_configs[guild_id] = config
                    self.save_welcome_configs()
                    
                    status = "활성화" if dm_사용 else "비활성화"
                    embed = discord.Embed(
                        title=f"💌 DM 환영 메시지 {status}",
                        description=f"새 멤버에게 DM으로 환영 메시지를 {'보냅니다' if dm_사용 else '보내지 않습니다'}.",
                        color=discord.Color.green() if dm_사용 else discord.Color.red()
                    )
                    
            elif 기능.value == "role":
                if not 자동역할:
                    # 자동 역할 제거
                    config["auto_role"] = None
                    self.welcome_configs[guild_id] = config
                    self.save_welcome_configs()
                    
                    embed = discord.Embed(
                        title="🎭 자동 역할 제거",
                        description="자동 역할 부여가 비활성화되었습니다.",
                        color=discord.Color.orange()
                    )
                else:
                    # 봇 권한 확인
                    bot_member = interaction.guild.me
                    
                    if not bot_member.guild_permissions.manage_roles:
                        embed = discord.Embed(
                            title="❌ 권한 부족",
                            description=f"봇이 **역할 관리** 권한이 없습니다.\n"
                                      f"서버 설정에서 봇에게 역할 관리 권한을 부여해주세요.",
                            color=discord.Color.red()
                        )
                    elif 자동역할 >= bot_member.top_role:
                        embed = discord.Embed(
                            title="❌ 역할 위치 오류",
                            description=f"**{자동역할.name}** 역할이 봇 역할보다 높습니다.\n"
                                      f"봇 역할을 더 높은 위치로 이동하거나, 더 낮은 역할을 선택해주세요.\n\n"
                                      f"💡 **해결 방법:**\n"
                                      f"서버 설정 → 역할 → 봇 역할을 **{자동역할.name}**보다 위로 드래그",
                            color=discord.Color.red()
                        )
                    else:
                        # 자동 역할 설정
                        config["auto_role"] = 자동역할.id
                        self.welcome_configs[guild_id] = config
                        self.save_welcome_configs()
                        
                        embed = discord.Embed(
                            title="🎭 자동 역할 설정 완료",
                            description=f"새 멤버에게 **{자동역할.name}** 역할을 자동으로 부여합니다.",
                            color=discord.Color.purple()
                        )
                        
                        embed.add_field(
                            name="✅ 권한 확인 완료",
                            value="봇이 해당 역할을 부여할 수 있습니다!",
                            inline=False
                        )
                        
            elif 기능.value == "status":
                # 현재 설정 보기
                embed = discord.Embed(
                    title="📊 환영 시스템 현재 설정",
                    color=discord.Color.blue()
                )
                
                status_emoji = "🟢" if config.get("enabled") else "🔴"
                embed.add_field(
                    name="시스템 상태",
                    value=f"{status_emoji} {'활성화' if config.get('enabled') else '비활성화'}",
                    inline=True
                )
                
                # 중복 방지 상태 추가
                embed.add_field(
                    name="중복 방지 캐시",
                    value=f"🛡️ 활성 ({len(self.processed_members)}개 기록)",
                    inline=True
                )
                
                channel_id = config.get("channel_id")
                if channel_id:
                    channel = self.bot.get_channel(int(channel_id))
                    if channel:
                        channel_name = channel.mention
                        
                        # 봇 권한 확인
                        bot_permissions = channel.permissions_for(interaction.guild.me)
                        missing_permissions = []
                        
                        if not bot_permissions.send_messages:
                            missing_permissions.append("메시지 보내기")
                        if not bot_permissions.embed_links:
                            missing_permissions.append("링크 첨부")
                        if not bot_permissions.view_channel:
                            missing_permissions.append("채널 보기")
                        
                        if missing_permissions:
                            channel_name += f"\n⚠️ 권한 부족: {', '.join(missing_permissions)}"
                        else:
                            channel_name += "\n✅ 권한 양호"
                    else:
                        channel_name = "삭제된 채널"
                else:
                    channel_name = "설정되지 않음"
                
                embed.add_field(
                    name="환영 채널",
                    value=channel_name,
                    inline=True
                )
                
                dm_status = "🟢 활성화" if config.get("dm_enabled") else "🔴 비활성화"
                embed.add_field(
                    name="DM 환영 메시지",
                    value=dm_status,
                    inline=True
                )
                
                auto_role_id = config.get("auto_role")
                if auto_role_id:
                    role = interaction.guild.get_role(int(auto_role_id))
                    if role:
                        role_name = role.name
                        
                        # 봇 역할 관리 권한 확인
                        bot_member = interaction.guild.me
                        if not bot_member.guild_permissions.manage_roles:
                            role_name += "\n⚠️ 봇에게 역할 관리 권한 없음"
                        elif role >= bot_member.top_role:
                            role_name += "\n⚠️ 역할이 봇보다 높음"
                        else:
                            role_name += "\n✅ 권한 양호"
                    else:
                        role_name = "삭제된 역할"
                else:
                    role_name = "없음"
                
                embed.add_field(
                    name="자동 역할",
                    value=role_name,
                    inline=True
                )
                
                has_custom_message = bool(config.get("welcome_message"))
                embed.add_field(
                    name="환영 메시지",
                    value="🟢 사용자 정의" if has_custom_message else "🔷 기본 메시지",
                    inline=True
                )
            
            # 모든 경우에 대해 embed가 설정되어야 함
            if embed is None:
                embed = discord.Embed(
                    title="❌ 알 수 없는 오류",
                    description="요청을 처리하는 중 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
            
            await interaction.followup.send(embed=embed)
            
        except Exception as e:
            print(f"환영설정 명령어 오류: {e}")
            error_embed = discord.Embed(
                title="❌ 시스템 오류",
                description=f"설정 중 오류가 발생했습니다: {str(e)}",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=error_embed)

    @app_commands.command(name="환영테스트", description="환영 메시지를 테스트합니다")
    async def welcome_test(self, interaction: discord.Interaction):
        # 먼저 interaction을 defer하여 시간 연장
        await interaction.response.defer(ephemeral=True)
        
        # 관리자 권한 확인
        if not interaction.user.guild_permissions.administrator:
            return await interaction.followup.send(
                "❌ 이 명령어는 **관리자** 권한이 필요합니다."
            )
        
        guild_id = str(interaction.guild.id)
        config = self.get_guild_config(guild_id)
        
        if not config.get("enabled"):
            return await interaction.followup.send(
                "❌ 환영 시스템이 비활성화되어 있습니다.\n"
                "`/환영설정 기능:🔧환영_시스템_활성화`로 먼저 활성화해주세요."
            )
        
        channel_id = config.get("channel_id")
        if not channel_id:
            return await interaction.followup.send(
                "❌ 환영 채널이 설정되지 않았습니다.\n"
                "`/환영설정 기능:📍환영_채널_설정`으로 채널을 설정해주세요."
            )
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return await interaction.followup.send(
                "❌ 설정된 환영 채널을 찾을 수 없습니다.\n"
                "채널을 다시 설정해주세요."
            )
        
        # 봇 권한 확인
        bot_permissions = channel.permissions_for(interaction.guild.me)
        missing_permissions = []
        
        if not bot_permissions.send_messages:
            missing_permissions.append("메시지 보내기")
        if not bot_permissions.embed_links:
            missing_permissions.append("링크 첨부")
        if not bot_permissions.view_channel:
            missing_permissions.append("채널 보기")
        
        if missing_permissions:
            return await interaction.followup.send(
                f"❌ 봇이 {channel.mention}에서 다음 권한이 없습니다:\n"
                f"**{', '.join(missing_permissions)}**\n\n"
                f"🔍 **권한 상세 확인:**\n"
                f"• 메시지 보내기: {'✅' if bot_permissions.send_messages else '❌'}\n"
                f"• 링크 첨부: {'✅' if bot_permissions.embed_links else '❌'}\n"
                f"• 채널 보기: {'✅' if bot_permissions.view_channel else '❌'}\n\n"
                f"💡 **해결 방법:**\n"
                f"1. {channel.mention} → 설정 ⚙️ → 권한\n"
                f"2. 봇 역할 추가 → 위 권한들 **✅ 허용**으로 설정\n"
                f"3. 또는 서버 설정 → 역할 → 봇 역할에서 기본 권한 활성화"
            )
        
        # 테스트 환영 메시지 전송 (중복 방지 우회)
        try:
            # 테스트는 중복 방지를 우회하여 항상 전송
            print(f"🧪 환영 메시지 테스트 시작: {interaction.user.display_name}")
            
            # 실제 환영 메시지 전송
            success = await self.send_welcome_message(interaction.user, channel, config)
            
            if success:
                embed = discord.Embed(
                    title="✅ 환영 메시지 테스트 완료",
                    description=f"테스트 환영 메시지가 {channel.mention}에 전송되었습니다!",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="✅ 권한 확인 완료",
                    value="봇이 모든 필요한 권한을 가지고 있습니다!",
                    inline=False
                )
                embed.add_field(
                    name="🛡️ 중복 방지 시스템",
                    value="실제 새 멤버에게는 중복 메시지가 발송되지 않습니다.",
                    inline=False
                )
            else:
                embed = discord.Embed(
                    title="❌ 환영 메시지 테스트 실패",
                    description=f"환영 메시지 전송 중 오류가 발생했습니다.",
                    color=discord.Color.red()
                )
        
        except discord.Forbidden as e:
            embed = discord.Embed(
                title="❌ 권한 테스트 실패",
                description=f"봇이 {channel.mention}에서 다음 작업을 할 수 없습니다.",
                color=discord.Color.red()
            )
            
            if "50013" in str(e):
                embed.add_field(
                    name="❌ 권한 부족",
                    value="봇에게 **메시지 보내기** 및 **링크 첨부** 권한을 부여해주세요.",
                    inline=False
                )
            
            embed.add_field(
                name="💡 정확한 해결 방법",
                value=f"1. {channel.mention} 우클릭\n"
                      f"2. **채널 편집** → **권한** 탭\n"
                      f"3. **봇 역할** 추가\n"
                      f"4. **메시지 보내기** ✅\n"
                      f"5. **링크 첨부** ✅\n"
                      f"6. **저장**",
                inline=False
            )
        
        except Exception as e:
            embed = discord.Embed(
                title="❌ 예상치 못한 오류",
                description=f"오류: {str(e)}",
                color=discord.Color.red()
            )
        
        await interaction.followup.send(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(WelcomeSystem(bot))