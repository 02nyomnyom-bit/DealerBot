# ladder_game.py
from __future__ import annotations
import discord
from discord.ext import commands
from discord.ui import View, Button
from discord import app_commands
from typing import Optional
import random

class LadderGameCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="사다리타기", description="사다리타기 게임을 합니다.")
    @app_commands.describe(
        인원="쉼표로 구분된 참여자 목록 (예: 철수,영희,아영)",
        결과="쉼표로 구분된 결과 목록 (예: 당첨,꽝,꽝)"
    )
    async def 사다리타기(
        self,
        ctx: commands.Context,
        인원: str,
        결과: Optional[str] = ""
    ):
        # interaction 객체 추출
        interaction = ctx.interaction if hasattr(ctx, 'interaction') else None

        # 인원/결과 파싱
        participants = [p.strip() for p in 인원.split(",") if p.strip()]
        results = [r.strip() for r in 결과.split(",") if r.strip()] if 결과 else []

        # 유효성 검사
        if len(participants) < 2:
            return await ctx.send("❌ 최소 2명 이상의 참여자가 필요합니다.", ephemeral=True)
        if len(participants) > 10:
            return await ctx.send("❌ 최대 10명까지만 참여할 수 있어요.", ephemeral=True)
        if len(set(participants)) != len(participants):
            return await ctx.send("❌ 중복된 참여자가 있습니다.", ephemeral=True)

        # 결과 부족 시 '꽝' 자동 채움
        while len(results) < len(participants):
            results.append("꽝")

        if len(results) > len(participants):
            return await ctx.send("❌ 결과 수가 참여자보다 많아요. 맞춰주세요.", ephemeral=True)

        # 결과 매핑
        random.shuffle(results)
        result_map = dict(zip(participants, results))

        # 버튼 뷰 클래스
        class LadderView(View):
            @discord.ui.button(label="👤 개인 결과 보기", style=discord.ButtonStyle.primary)
            async def 개인결과(self, interaction_button: discord.Interaction, button: Button):
                user_name = interaction_button.user.display_name
                if user_name not in result_map:
                    await interaction_button.response.send_message(
                        f"❌ 당신({user_name})은 참여자 명단에 없습니다.", ephemeral=True)
                    return
                await interaction_button.response.send_message(
                    f"🎯 **{user_name}** 님의 결과는 → **{result_map[user_name]}** 입니다!",
                    ephemeral=True
                )

            @discord.ui.button(label="📢 전체 결과 보기", style=discord.ButtonStyle.success)
            async def 전체결과(self, interaction_button: discord.Interaction, button: Button):
                result_text = "\n".join(
                    [f"{i+1}. {name} → 🎯 **{res}**" for i, (name, res) in enumerate(result_map.items())]
                )
                embed = discord.Embed(
                    title="🪜 사다리타기 결과",
                    description=result_text,
                    color=discord.Color.orange()
                )
                await interaction_button.response.send_message(embed=embed)

        await ctx.send(
            content="🎮 **사다리타기 시작!** 아래 버튼을 눌러 결과를 확인하세요.",
            view=LadderView()
        )

# ✅ setup 함수 (확장 로드용)
async def setup(bot: commands.Bot):
    await bot.add_cog(LadderGameCog(bot))