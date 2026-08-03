# pet_views.py
import discord
from discord import ui, Interaction
from discord.ui import View
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

class FaintedPetView(View):
    def __init__(self, cog, user_id, guild_id, pet):
        super().__init__(timeout=60)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.pet = pet

    @discord.ui.button(label="치료하기 (500,000 골드)", style=discord.ButtonStyle.danger)
    async def heal_pet(self, interaction: discord.Interaction, button: discord.ui.Button):
        if str(interaction.user.id) != str(self.user_id):
            return await interaction.response.send_message("🚫 보호자가 아닙니다.", ephemeral=True)
            
        db = self.cog._get_db(int(self.guild_id))
        user_data = db.get_user(self.user_id)
        cash = user_data.get('cash', 0) if user_data else 0
        
        if cash < 500000:
            return await interaction.response.send_message("❌ 골드가 부족합니다.", ephemeral=True)
            
        # 골드 차감 및 상태 완전 회복
        db.add_user_cash(self.user_id, -500000)
        self.pet.is_fainted = False
        self.pet.faint_time = None
        self.pet.zero_fullness_time = None
        self.pet.zero_cleanliness_time = None
        self.pet.fullness = 100
        self.pet.cleanliness = 100
        self.pet.energy = self.pet.max_energy
        self.pet.stress = 0
        self.pet.mood_score = 100
        self.cog.save_user_pet(self.guild_id, self.user_id, self.pet)
        
        await interaction.response.send_message("💖 펫이 성공적으로 치료되었습니다! 다시 건강해졌습니다.", ephemeral=True)
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)


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

    @discord.ui.button(label="🧪 망각의 물약 사용", style=discord.ButtonStyle.secondary, row=1)
    async def use_forget_potion(self, interaction: discord.Interaction, button: discord.ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet or not pet.skills:
            return await interaction.response.send_message("❌ 지울 스킬이 없습니다.", ephemeral=True)
            
        potion_count = pet.inventory.get("소모품", {}).get("망각", 0)
        if potion_count <= 0:
            return await interaction.response.send_message("❌ [망각의 물약]이 없습니다. 상점에서 구매해주세요.", ephemeral=True)
            
        await interaction.response.send_message(
            "🧪 어떤 스킬을 지우시겠습니까? (망각의 물약 1개 소모)",
            view=SkillForgetSelectionView(self.cog, self.user_id, self.guild_id),
            ephemeral=True
        )

# pet_views.py에 추가
class SkillForgetSelectionView(discord.ui.View):
    def __init__(self, cog, user_id, guild_id):
        super().__init__()
        pet = cog.get_user_pet(guild_id, user_id)
        for skill in pet.skills:
            self.add_item(self.create_button(skill, cog, user_id, guild_id))

    def create_button(self, skill_name, cog, user_id, guild_id):
        btn = discord.ui.Button(label=f"{skill_name} 지우기", style=discord.ButtonStyle.danger)
        
        async def callback(interaction: discord.Interaction):
            pet = cog.get_user_pet(guild_id, user_id)
            potion_count = pet.inventory.get("소모품", {}).get("망각", 0)
            if potion_count <= 0:
                return await interaction.response.send_message("❌ [망각의 물약]이 부족합니다.", ephemeral=True)
                
            if skill_name in pet.skills:
                # 아이템 차감
                pet.inventory["소모품"]["망각"] -= 1
                pet.skills.remove(skill_name)
                cog.save_user_pet(guild_id, user_id, pet)
                await interaction.response.edit_message(
                    content=f"🧪 **{skill_name}** 스킬을 잊었습니다... (남은 물약: {pet.inventory['소모품']['망각']}개)",
                    view=None
                )
            else:
                await interaction.response.send_message("❌ 해당 스킬을 찾을 수 없습니다.", ephemeral=True)
                
        btn.callback = callback
        return btn

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
            await go_to_home(interaction, cog, user_id, guild_id) # 메인화면 복귀
            await interaction.followup.send(f"✅ {skill_name}을(를) 잊고 {new_skill}을(를) 배웠습니다!", ephemeral=True)
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

        # 진화 조건 현황 embed 생성
        stage = pet.stage

        if stage == "새끼":
            lv_ok    = pet.level >= 15
            aff_ok   = pet.affinity >= 30
            all_ok   = lv_ok and aff_ok

            embed = discord.Embed(
                title="🌱 새끼 → 유년기 진화 조건",
                color=0x2ecc71 if all_ok else 0x95a5a6
            )
            embed.add_field(
                name="📊 달성 현황",
                value=(
                    f"{'✅' if lv_ok  else '❌'} 레벨 **{pet.level}** / 15 이상\n"
                    f"{'✅' if aff_ok else '❌'} 친밀도 **{pet.affinity}** / 30 이상"
                ),
                inline=False
            )
            if all_ok:
                embed.set_footer(text="✨ 조건 충족! 진화를 시도합니다...")
            else:
                embed.set_footer(text="⏳ 아직 조건이 충족되지 않았습니다.")

        elif stage == "유년기":
            lv_ok  = pet.level >= 40
            tr_ok  = pet.train_count >= 50
            ex_ok  = pet.explore_count >= 50
            all_ok = lv_ok and tr_ok and ex_ok

            embed = discord.Embed(
                title="⚡ 유년기 → 성체 진화 조건",
                color=0xf39c12 if all_ok else 0x95a5a6
            )
            embed.add_field(
                name="📊 달성 현황",
                value=(
                    f"{'✅' if lv_ok else '❌'} 레벨 **{pet.level}** / 40 이상\n"
                    f"{'✅' if tr_ok else '❌'} 훈련 **{pet.train_count}회** / 50회 이상\n"
                    f"{'✅' if ex_ok else '❌'} 탐험 **{pet.explore_count}회** / 50회 이상"
                ),
                inline=False
            )
            if all_ok:
                embed.set_footer(text="✨ 조건 충족! 진화를 시도합니다...")
            else:
                embed.set_footer(text="⏳ 아직 조건이 충족되지 않았습니다.")

        elif stage == "성체":
            lv_ok  = pet.level >= 75
            pv_ok  = pet.pvp_count >= 30
            af_ok  = pet.affinity >= 70
            pt_ok  = pet.potential >= 50
            all_ok = lv_ok and pv_ok and af_ok and pt_ok

            embed = discord.Embed(
                title="🔥 성체 → 최종 진화 조건",
                color=0xe74c3c if all_ok else 0x95a5a6
            )
            embed.add_field(
                name="📊 달성 현황",
                value=(
                    f"{'✅' if lv_ok else '❌'} 레벨 **{pet.level}** / 75 이상\n"
                    f"{'✅' if pv_ok else '❌'} PvP **{pet.pvp_count}회** / 30회 이상\n"
                    f"{'✅' if af_ok else '❌'} 친밀도 **{pet.affinity}** / 70 이상\n"
                    f"{'✅' if pt_ok else '❌'} 잠재력 **{pet.potential}%** / 50% 이상"
                ),
                inline=False
            )
            if all_ok:
                embed.set_footer(text="✨ 조건 충족! 진화를 시도합니다...")
            else:
                embed.set_footer(text="⏳ 아직 조건이 충족되지 않았습니다.")

        else:
            # 최종 진화 상태
            embed = discord.Embed(
                title="🏆 최종 진화 완료",
                description="이미 최고 단계에 도달했습니다. 더 이상 진화할 수 없습니다.",
                color=0x9b59b6
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 조건 미충족 시 현황만 보여주고 종료
        if not all_ok:
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # 조건 충족 시 실제 진화 시도
        evo_msg, evo_embed = pet.check_evolution_conditions()

        if evo_msg:
            self.cog.save_user_pet(self.guild_id, self.user_id, pet)
            await interaction.response.send_message(f"🎉 진화에 성공했습니다!{evo_msg}", embed=evo_embed, ephemeral=False)
            await go_to_home(interaction, self.cog, self.user_id, self.guild_id)
        else:
            await interaction.response.send_message(embed=embed, ephemeral=True)

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

    @discord.ui.button(label="📜 퀘스트 현황 보기", style=discord.ButtonStyle.primary, row=0)
    async def view_progress(self, interaction: Interaction, button: ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)

        # 퀘스트 할당 (이미 있다면 무시됨)
        self.cog.assign_daily_quests(pet)
        # 뽑은 퀘스트가 날아가지 않게 즉시 DB에 세이브
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
                    done = "✅" if progress >= target else "🔲"
                    embed.add_field(
                        name=f"{done} {quest_info['name']}",
                        value=f"{quest_info['desc']} ({progress}/{target})",
                        inline=False
                    )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="🎁 보상 수령", style=discord.ButtonStyle.success, row=0)
    async def claim_reward(self, interaction: Interaction, button: ui.Button):
        pet = self.cog.get_user_pet(self.guild_id, self.user_id)
        if not pet:
            return await interaction.response.send_message("❌ 활성화된 펫이 없습니다.", ephemeral=True)

        # 1. 한국 시간 기준 오늘 날짜
        today = time.strftime('%Y-%m-%d', time.localtime(time.time() + 32400))

        # 2. 중복 수령 방지
        if getattr(pet, 'last_reward_date', None) == today:
            return await interaction.response.send_message("❌ 오늘은 이미 보상을 수령했습니다. 내일 다시 도전하세요!", ephemeral=True)

        # 3. daily_quests 달성 여부 검증
        daily_quests = getattr(pet, 'daily_quests', None)
        if not daily_quests:
            return await interaction.response.send_message(
                "❌ 오늘의 퀘스트가 할당되지 않았습니다. '📜 퀘스트 현황 보기'를 먼저 눌러주세요!",
                ephemeral=True
            )

        # 미완료 퀘스트 목록 수집 (부분 완료도 보상 지급 - 달성한 수만큼 지급)
        completed = 0
        incomplete = []
        for q_id, status in daily_quests.items():
            if status["count"] >= status["target"]:
                completed += 1
            else:
                quest_info = next((q for q in self.cog.quest_pool if q["id"] == q_id), None)
                name = quest_info["name"] if quest_info else q_id
                incomplete.append(f"• {name} ({status['count']}/{status['target']}회)")

        if completed == 0:
            return await interaction.response.send_message(
                "❌ 아직 달성한 퀘스트가 없습니다!\n" + "\n".join(incomplete),
                ephemeral=True
            )

        # 4. 보상 지급 — 달성 퀘스트 수에 비례한 보상
        db = self.cog._get_db(int(self.guild_id))
        if "열매" not in pet.inventory:
            pet.inventory["열매"] = {}

        reward_lines = []
        total_quests = len(daily_quests)

        if completed == total_quests:
            # 전체 달성 보상 — 최상급
            pet.inventory["열매"]["중"] = pet.inventory["열매"].get("중", 0) + 3
            pet.inventory["열매"]["하"] = pet.inventory["열매"].get("하", 0) + 5
            gold_reward = 30000
            exp_reward = 300
            reward_lines.append("🏆 **[완벽 달성]** 중급 열매 3개 + 하급 열매 5개 + 경험치 300 + 30,000 골드")
        elif completed >= total_quests // 2 + 1:
            # 절반 이상 달성
            pet.inventory["열매"]["하"] = pet.inventory["열매"].get("하", 0) + 5
            gold_reward = 15000
            exp_reward = 150
            reward_lines.append("🎁 **[부분 달성]** 하급 열매 5개 + 경험치 150 + 15,000 골드")
        else:
            # 1개 이상 달성
            pet.inventory["열매"]["하"] = pet.inventory["열매"].get("하", 0) + 2
            gold_reward = 5000
            exp_reward = 50
            reward_lines.append("📦 **[일부 달성]** 하급 열매 2개 + 경험치 50 + 5,000 골드")

        db.add_user_cash(self.user_id, gold_reward)
        pet.gain_exp(exp_reward)

        if incomplete:
            reward_lines.append(f"\n미완료 퀘스트 ({len(incomplete)}개):\n" + "\n".join(incomplete))

        # 5. 수령 기록 업데이트 및 저장
        pet.last_reward_date = today
        self.cog.save_user_pet(self.guild_id, self.user_id, pet)

        await interaction.response.send_message(
            f"🎁 일일 퀘스트 **{completed}/{total_quests}** 달성!\n" + "\n".join(reward_lines),
            ephemeral=False
        )

    @discord.ui.button(label="처음으로", style=discord.ButtonStyle.danger, row=1)
    async def back(self, interaction: Interaction, button: ui.Button):
        await go_to_home(interaction, self.cog, self.user_id, self.guild_id)