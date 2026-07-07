# sticky_memo.py - 접착 메모 (Cog 기반, 안전망 추가버전)
import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from typing import Dict, Any

class StickyMemoCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.sticky_memos: Dict[int, Dict[str, Any]] = {}

    async def send_sticky_memo(self, channel: discord.TextChannel, title: str, content: str, use_embed: bool) -> discord.Message:
        """접착 메모 메시지를 전송하는 내부 함수"""
        formatted_content = content.replace("\\n", "\n")
        
        if use_embed:
            embed = discord.Embed(title=title, description=formatted_content, color=0xFFFF00)
            return await channel.send(embed=embed)
        else:
            full_message = f"{title}\n{formatted_content}"
            return await channel.send(full_message)

    @app_commands.command(name="접착메모", description="[관리자 전용] 채팅방 하단에 고정되는 메모를 생성합니다.")
    @app_commands.checks.has_permissions(administrator=True)
    @app_commands.default_permissions(administrator=True)
    @app_commands.describe(
        자동갱신="True: 3초 후 갱신(빠름) | False: 채팅 정지 15초 후 갱신(안전)",
        임베드모양="True: 노란색 박스로 표시 | False: 일반 텍스트로 표시",
        제목="메모의 제목 (#, ##, ### 등으로 크기 조절 가능)",
        내용="메모의 내용 (삭제하려면 '삭제' 라고 입력하세요. \\n으로 줄바꿈 가능)"
    )
    async def sticky_memo(
        self,
        interaction: discord.Interaction, 
        자동갱신: bool, 
        임베드모양: bool, 
        제목: str, 
        내용: str
    ):
            
        await interaction.response.defer(ephemeral=True)
        channel_id = interaction.channel_id

        # 1. 삭제 모드 로직
        if 내용.strip() == "삭제":
            if channel_id in self.sticky_memos:
                if self.sticky_memos[channel_id]["task"]:
                    self.sticky_memos[channel_id]["task"].cancel()
                try:
                    await self.sticky_memos[channel_id]["message"].delete()
                except:
                    pass
                del self.sticky_memos[channel_id]
                await interaction.followup.send("🗑️ 이 채널의 접착 메모가 성공적으로 삭제되었습니다.", ephemeral=True)
            else:
                await interaction.followup.send("❌ 이 채널에는 활성화된 접착 메모가 없습니다.", ephemeral=True)
            return
        
        # 2. 기존 메모 덮어쓰기 로직
        if channel_id in self.sticky_memos:
            if self.sticky_memos[channel_id]["task"]:
                self.sticky_memos[channel_id]["task"].cancel()
            try:
                await self.sticky_memos[channel_id]["message"].delete()
            except:
                pass

        # 3. 새로운 메모 전송 및 저장
        try:
            msg = await self.send_sticky_memo(interaction.channel, 제목, 내용, 임베드모양)
            
            self.sticky_memos[channel_id] = {
                "message": msg,
                "title": 제목,
                "content": 내용,
                "auto_renew": 자동갱신,
                "use_embed": 임베드모양,
                "task": None
            }
            await interaction.followup.send("✅ 접착 메모가 성공적으로 설정되었습니다!", ephemeral=True)
        except discord.Forbidden:
            await interaction.followup.send("❌ 봇에게 메시지를 전송하거나 관리할 권한이 없습니다.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ 오류가 발생했습니다: {e}", ephemeral=True)

    async def delayed_renew(self, channel_id: int, channel: discord.TextChannel, delay: float):
        """지정된 시간 대기 후 메시지를 갱신하는 타이머(디바운스) 함수"""
        # 🚨 [수정] 시스템 내부 지연 타이머 함수이므로 interaction 체크 구문을 완전히 제거했습니다.
        try:
            await asyncio.sleep(delay)
            if channel_id in self.sticky_memos:
                memo_data = self.sticky_memos[channel_id]
                try:
                    await memo_data["message"].delete()
                except:
                    pass
                new_msg = await self.send_sticky_memo(channel, memo_data["title"], memo_data["content"], memo_data["use_embed"])
                self.sticky_memos[channel_id]["message"] = new_msg
                self.sticky_memos[channel_id]["task"] = None
        except asyncio.CancelledError:
            pass
        except Exception as e:
            print(f"[접착메모] 갱신 중 오류 발생: {e}")

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return

        channel_id = message.channel.id
        
        if channel_id in self.sticky_memos:
            memo_data = self.sticky_memos[channel_id]
            
            if memo_data["task"]:
                memo_data["task"].cancel()
            
            delay = 3.0 if memo_data["auto_renew"] else 15.0
            
            task = asyncio.create_task(self.delayed_renew(channel_id, message.channel, delay))
            self.sticky_memos[channel_id]["task"] = task

async def setup(bot: commands.Bot):
    existing_commands = [cmd.name for cmd in bot.tree.get_commands()]
    if "접착메모" in existing_commands:
        bot.tree.remove_command("접착메모")
        
    await bot.add_cog(StickyMemoCog(bot))
    print("✅ StickyMemoCog (접착 메모 모듈) 정상 로드됨!")