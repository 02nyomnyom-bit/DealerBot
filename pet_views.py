# pet_views.py
import discord
from discord.ui import View, Button
from pet_skill import DiscordUIFormatter

# 처음으로 돌아가는 임시 헬퍼 함수
async def go_to_home(interaction, cog, user_id, guild_id):
    db = cog._get_db(int(guild_id))
    user_data = db.get_user(user_id)
    pet = cog.get_user_pet(guild_id, user_id)
    data = DiscordUIFormatter.make_user_embed_data(user_data, pet)
    embed = discord.Embed(title=data["title"], description=data["description"], color=0x3498db)
    for f in data["fields"]:
        embed.add_field(name=f["name"], value=f["value"], inline=f["inline"])
    
    # 순환 참조 방지를 위해 MainPetHubView를 동적 임포트하여 메시지를 수정합니다.
    from pet_manager import MainPetHubView
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
    async def claim_reward(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 펫이 없습니다.", ephemeral=True)
            
        if not getattr(pet, "action_done_today", False):
            return await interaction.response.send_message("❌ 아직 오늘의 1회 행동을 완료하지 않아 보상을 받을 수 없습니다!", ephemeral=True)
            
        # 보상 지급 (골드 지급)
        db = self.cog._get_db(int(self.guild_id))
        db.add_user_cash(self.user_id, 5000)
        
        # 퀘스트 완료 처리 후 일일 행동 카운터를 강제 조절하여 오늘 퀘스트를 이미 받았음을 표기할 수도 있습니다.
        # 여기서는 중복 지급을 막기 위해 퀘스트 보상을 수령했음을 알리고 메인화면으로 보냅니다.
        await interaction.response.send_message("🪙 일일 교감 연구 완료 보상으로 **5,000 골드**를 수령했습니다!", ephemeral=True)
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)