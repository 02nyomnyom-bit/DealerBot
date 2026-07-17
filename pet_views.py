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

class SkillSelectView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id, new_skill):
        super().__init__()
        self.cog, self.user_id, self.guild_id = cog, user_id, guild_id
        self.new_skill = new_skill
        
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        # 현재 배운 스킬들을 선택지로 생성
        for skill in pet.skills:
            self.add_item(SkillRemoveButton(skill, self))

class SkillRemoveButton(discord.ui.Button):
    def __init__(self, skill_name, parent_view):
        super().__init__(label=skill_name, style=discord.ButtonStyle.secondary)
        self.skill_name = skill_name
        self.parent_view = parent_view

    async def callback(self, interaction: discord.Interaction):
        # 1. 실제 삭제 및 교체 로직
        pet = self.parent_view.cog.get_user_pet(self.parent_view.guild_id, self.parent_view.user_id)
        pet.skills.remove(self.skill_name)
        pet.skills.append(self.parent_view.new_skill)
        
        # 2. DB 저장
        self.parent_view.cog.save_user_pet(self.parent_view.guild_id, self.parent_view.user_id, pet)
        
        await interaction.response.send_message(f"✅ {self.skill_name}을(를) 잊고 {self.parent_view.new_skill}을(를) 배웠습니다!", ephemeral=False)
        # 3. 홈 화면으로 복귀
        await go_to_home(interaction, self.parent_view.cog, self.parent_view.user_id, self.parent_view.guild_id)

# pet_views.py에 추가
class SkillSelectionView(discord.ui.View):

    def __init__(self, cog, user_id, guild_id, new_skill):
        super().__init__()
        pet = cog.get_user_pet(guild_id, user_id)
        # 현재 보유 스킬들을 버튼으로 나열
        for skill in pet.skills:
            self.add_item(self.create_button(skill, cog, user_id, guild_id, new_skill))
    # pet_manager.py 내부

    def create_button(self, skill_name, cog, user_id, guild_id, new_skill):
        btn = discord.ui.Button(label=f"잊기: {skill_name}", style=discord.ButtonStyle.danger)
        async def callback(interaction: discord.Interaction):
            pet = cog.get_user_pet(guild_id, user_id)
            pet.skills.remove(skill_name) # 선택한 스킬 삭제
            pet.skills.append(new_skill)  # 새 스킬 추가
            cog.save_user_pet(guild_id, user_id, pet) # DB 반영
            await interaction.response.send_message(f"✅ {skill_name}을(를) 잊고 {new_skill}을(를) 배웠습니다!", ephemeral=True)
            await go_to_home(interaction, cog, user_id, guild_id) # 메인화면 복귀
        btn.callback = callback
        return btn
    
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
            await interaction.response.send_message(f"🎉 진화에 성공했습니다!{evo_msg}", ephemeral=False)
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

        # 1. 유저(계정) 데이터 및 인벤토리 불러오기
        db = self.cog._get_db(int(self.guild_id))
        user_data = db.get_user(self.user_id)
        
        # 인벤토리가 리스트 형태(["포션", "변하지 않는 반지", ...])라고 가정한 로직
        user_inventory = user_data.get("inventory", []) if user_data else []
        current_head = pet.equipment.get("아이템")
        
        # 2. 장착 해제 로직 (펫 -> 가방)
        if current_head == "변하지 않는 반지":
            pet.equipment["아이템"] = None
            pet.locked_appearance = None
            
            # 해제했으므로 유저 인벤토리에 반지 1개 반환
            user_inventory.append("변하지 않는 반지")
            msg = "💍 [변하지 않는 반지]를 해제하여 계정 가방으로 되돌려 놓았습니다!"
            
        # 3. 장착 로직 (가방 -> 펫)
        else:
            # 가방에 반지가 있는지 먼저 확인
            if "변하지 않는 반지" not in user_inventory:
                return await interaction.response.send_message(
                    "❌ 계정 가방에 '변하지 않는 반지'가 없습니다.\n(다른 펫이 장착 중이거나 소지하고 있지 않습니다.)", 
                    ephemeral=True
                )
                
            # 장착하므로 유저 인벤토리에서 반지 1개 차감
            user_inventory.remove("변하지 않는 반지")
            
            pet.equipment["아이템"] = "변하지 않는 반지"
            pet.locked_appearance = pet.stage
            msg = "💍 [변하지 않는 반지]를 장착했습니다! (가방에서 1개 소모됨)\n앞으로 진화하더라도 이미지는 현재 모습으로 고정됩니다.\n⚠️ **주의: 이 상태로 펫을 떠나보내면 반지도 함께 사라집니다.**"
            
        # 4. 변경된 인벤토리와 펫 정보를 모두 저장
        if user_data:
            user_data["inventory"] = user_inventory
            db.save_user(self.user_id, user_data) # 유저(계정) 데이터 저장
            
        self.cog.save_user_pet(self.guild_id, self.user_id, pet) # 펫 데이터 저장
        
        await interaction.response.send_message(msg, ephemeral=True)

    @discord.ui.button(label="돌아가기", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: discord.Interaction, button: discord.ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)

class BreedingView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    @discord.ui.button(label="💞 교배 진행 (30만 G)", style=discord.ButtonStyle.primary, row=0)
    async def breeding(self, interaction: Interaction, button: ui.Button):
        # 1. 봇 응답 지연 처리 (연산이 길어질 경우를 대비)
        await interaction.response.defer(ephemeral=False)

        # 2. 교배 로직 연결 (매니저의 start_breeding 호출)
        status, error_msg, embed = await self.cog.start_breeding(self.guild_id, self.user_id)
        
        if status == "SUCCESS":
            # 3-A. 교배 성공 시: 성공 메시지(임베드) 전송 후 메인 화면으로 복귀
            await interaction.followup.send(embed=embed, ephemeral=False)
            await go_to_home(interaction, self.cog, self.user_id, self.guild_id)
        else:
            # 3-B. 조건 미달 시: 실패 사유 출력
            await interaction.followup.send(error_msg, ephemeral=True)

    @discord.ui.button(label="처음으로", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        # 취소 시 안전하게 메인 화면(MainPetHubView)으로 복귀
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)

# 4. 📋 퀘스트 관리 뷰
class QuestView(View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id

    # pet_views.py의 PetQuestView 내부 view_progress 함수 수정

    @discord.ui.button(label="📜 퀘스트 현황 보기", style=discord.ButtonStyle.primary, row=0)
    async def view_progress(self, interaction: Interaction, button: ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        
        # 퀘스트 할당 (이미 있다면 무시됨)
        self.cog.assign_daily_quests(pet)
        # ✅ [추가] 뽑은 퀘스트가 날아가지 않게 즉시 DB에 세이브합니다.
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)
        
        embed = discord.Embed(title=f"📜 {pet.name}의 오늘의 미션", color=0x3498db)
        
        if not getattr(pet, 'daily_quests', None):
            embed.description = "현재 단계에서 수행할 수 있는 미션이 없습니다."
        else:
            for q_id, status in pet.daily_quests.items():
                quest_info = next((item for item in self.cog.quest_pool if item["id"] == q_id), None)
                if quest_info:
                    progress = status["count"]
                    target = status["target"]
                    embed.add_field(
                        name=quest_info["name"],
                        value=f"{quest_info['desc']} ({progress}/{target})",
                        inline=False
                    )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎁 보상 수령", style=discord.ButtonStyle.success, row=0)
    async def claim_reward(self, interaction: Interaction, button: ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)

        # 날짜 변경 체크 및 초기화
        if hasattr(self.cog, 'check_and_reset_daily_quest'):
            self.cog.check_and_reset_daily_quest(pet)
        elif hasattr(self.cog.pet_manager, 'check_and_reset_daily_quest'):
            self.cog.pet_manager.check_and_reset_daily_quest(pet)

        # 1. 한국 시간 기준 오늘 날짜 생성
        today = time.strftime('%Y-%m-%d', time.localtime(time.time() + 32400))
        
        # 2. 이미 받았는지 중복 체크
        if getattr(pet, 'last_reward_date', None) == today:
            return await interaction.response.send_message("❌ 오늘은 이미 보상을 수령했습니다. 내일 다시 도전하세요!", ephemeral=True)

        # 3. 🚨 [강화된 조건] 퀘스트 달성 여부 검증 (훈련 1회 이상)
        if pet.train_count_today < 1:
            return await interaction.response.send_message(
                f"❌ 퀘스트 조건을 달성하지 못했습니다!\n급무: 오늘 최소 **1회 이상 훈련**을 완료해야 합니다. (현재: {pet.train_count_today}회)", 
                ephemeral=False
            )

        # 4. 보상 지급 로직 (골드 추가 등)
        db = self.cog._get_db(int(self.guild_id))
        db.add_user_cash(self.user_id, 5000) # 5,000골드 지급
        
        # 5. 수령 기록 업데이트 및 저장
        pet.last_reward_date = today
        if hasattr(self.cog, 'save_user_pet'):
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
        
        await interaction.response.send_message("🎁 일일 퀘스트 완료! **5,000 골드**가 지급되었습니다.", ephemeral=False)

    @discord.ui.button(label="처음으로", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)