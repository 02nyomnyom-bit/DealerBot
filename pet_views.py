import discord
from discord import ui, Interaction, ButtonStyle
from discord.ui import View, Button
import time
# MainPetHubView는 pet_manager에서 불러와야 하므로 내부에서 로드합니다.

# 수정된 헬퍼 함수
async def go_to_home(interaction, cog, user_id, guild_id):
    from pet_manager import MainPetHubView
    db = cog._get_db(int(guild_id))
    user_data = db.get_user(user_id)
    pet = cog.get_user_pet(guild_id, user_id)
    
    from pet_skill import DiscordUIFormatter
    data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
    embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
    for f in data["fields"]:
        embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
    
    # 💡 응답이 나갔는지 확인 후 edit_original_response 또는 edit_message 사용
    if interaction.response.is_done():
        await interaction.edit_original_response(embed=embed, view=MainPetHubView(cog, user_id, guild_id))
    else:
        await interaction.response.edit_message(embed=embed, view=MainPetHubView(cog, user_id, guild_id))

# 1. ⚔️ 스킬 관리 뷰
class SkillManageView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="스킬 설명 보기", style=discord.ButtonStyle.primary, row=0)
    async def show_desc(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet or not pet.skills:
            return await interaction.response.send_message("조회할 스킬이 없습니다.", ephemeral=True)
            
        from pet_skill import get_skill_info
        desc_list = []
        for s_name in pet.skills:
            info = get_skill_info(s_name)
            desc_list.append(f"• **{s_name}** (소모 MP: {info.get('mp', 0)} | 위력: {info.get('power', 0)})")
            
        embed = discord.Embed(title=f"📜 {pet.name}의 스킬 상세 정보", description="\n".join(desc_list), color=0x9b59b6)
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)


# 2. 🧬 진화 관리 뷰
class EvolutionView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="수동 진화 시도하기", style=discord.ButtonStyle.success, row=0)
    async def try_evolution(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 펫이 없습니다.", ephemeral=True)

        # 진화 조건 수동 검사 진행
        old_stage = pet.stage
        evo_msg = pet.check_evolution_conditions()
        
        if evo_msg:
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
            await interaction.response.send_message(f"🎉 진화에 성공했습니다!{evo_msg}", ephemeral=True)
            # 상태 새로고침
            await go_to_home(interaction, self.cog, self.user_id, self.guild_id)
        else:
            await interaction.response.send_message("⏳ 아직 다음 단계로 진화하기 위한 성장 조건(레벨, 누적 횟수 등)이 충족되지 않았습니다.", ephemeral=True)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)


# 3. ⚙️ 설정 관리 뷰
class SettingView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="진화 방지 반지 장착 토글", style=discord.ButtonStyle.secondary, row=0)
    async def toggle_evolution_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 펫이 없습니다.", ephemeral=True)
            
        equips = pet.inventory.get("장비", [])
        has_ring = any(e.get("부위") == "변하지 않는 반지" for e in equips)
        
        if not has_ring:
            return await interaction.response.send_message("❌ 가방에 '변하지 않는 반지' 장비 아이템이 없습니다. (탐험 중 보물상자 조우를 통해 획득할 수 있습니다)", ephemeral=True)
            
        # 변하지 않는 반지를 장착/해제 토글 처리
        current_head = pet.equipment.get("머리")
        if current_head == "변하지 않는 반지":
            pet.equipment["머리"] = None
            msg = "💍 [변하지 않는 반지]를 해제했습니다! 이제 성장 조건 만족 시 정상적으로 진화합니다."
        else:
            pet.equipment["머리"] = "변하지 않는 반지"
            msg = "💍 [변하지 않는 반지]를 장착했습니다! 성장 조건을 달성해도 강제로 진화하지 않고 현재 모습을 유지합니다."
            
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)


# 4. 📋 퀘스트 관리 뷰
class QuestView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="일일 퀘스트 보상 수령", style=discord.ButtonStyle.success, row=0)
    async def claim_reward(self, interaction: Interaction, button: ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)

        # 1. 한국 시간 기준 오늘 날짜 생성
        today = time.strftime('%Y-%m-%d', time.localtime(time.time() + 32400))
        
        # 2. 마지막 수령일 체크[cite: 5]
        last_reward = getattr(pet, 'last_reward_date', None)
        
        if last_reward == today:
            return await interaction.response.send_message("❌ 오늘은 이미 보상을 수령했습니다. 내일 다시 시도하세요!", ephemeral=True)

        # 3. 보상 지급 로직[cite: 5]
        # 예: 골드 추가, 경험치 획득 등
        db = self.cog._get_db(int(self.guild_id))
        db.add_user_cash(self.user_id, 5000) # 5,000골드 지급 예시
        
        # 4. 수령 기록 업데이트[cite: 5]
        pet.last_reward_date = today
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)
        
        # 5. UI 갱신 (이미 응답 여부 확인 후 조치)
        from pet_views import go_to_home # go_to_home 함수 호출
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)