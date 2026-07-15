# pet_skill.py
import random
import discord
from typing import Optional, Dict
from pet_climate import ClimateManager

# [기획서 100% 매핑 완료된 상성 차트]
TYPE_CHART = {
    "불": {"풀": 2.0, "불": 0.5, "물": 0.5, "어둠": 2.0},
    "물": {"불": 2.0, "땅": 2.0, "물": 0.5, "풀": 0.5},
    "풀": {"물": 2.0, "땅": 2.0, "불": 0.5, "독": 0.5, "비행": 0.5, "풀": 0.5},
    "전기": {"물": 2.0, "비행": 2.0, "풀": 0.5, "전기": 0.5, "땅": 0.0},
    "비행": {"풀": 2.0, "전기": 0.5, "땅": 0.0},
    "땅": {"불": 2.0, "전기": 2.0, "독": 2.0, "풀": 0.5, "비행": 0.0},
    "어둠": {"에스퍼": 2.0, "노말": 2.0, "어둠": 0.5, "불": 0.5},
    "독": {"풀": 2.0, "독": 0.5, "땅": 0.5},
    "에스퍼": {"독": 2.0, "에스퍼": 0.5, "어둠": 0.5},
    "노말": {"땅": 0.5, "어둠": 0.5}
}

# [스킬 데이터베이스 통합 관리]
SKILL_DATABASE = {
    "공용": {
        "웅크리기": {"mp": 10, "type": "방어", "desc": "받는 피해량 감소"},
        "피하기": {"mp": 5, "type": "회피", "desc": "다음 공격 회피 확률 증가"},
        "기모으기": {"mp": 15, "type": "집중", "desc": "다음 턴 스킬 위력 증가"},
        "회복": {"mp": 20, "type": "회복", "desc": "체력 즉시 소량 회복"},
        "탈출": {"mp": 20, "type": "해제", "desc": "디버프 상태이상 해제"},
        "멈춰": {"mp": 25, "type": "도발", "desc": "상대의 보조 스킬 사용 제한"},
        "엿먹어라": {"mp": 30, "type": "약화", "desc": "상대의 방어력 20% 감소"},
        "거기섯!": {"mp": 20, "type": "명중", "desc": "다음 공격 절대 명중 부여"}
    },
    "불": {
        "하급": [
            {"name": "파이어", "mp": 10, "power": 30},
            {"name": "나인테일", "mp": 20, "power": 40},
            {"name": "깨물기", "mp": 5, "power": 10}
        ],
        "중급": [
            {"name": "회오리불꽃", "mp": 20, "power": 50},
            {"name": "십자베기", "mp": 20, "power": 40},
            {"name": "마구핥키기", "mp": 10, "power": 30}
        ],
        "상급": [
            {"name": "불꽃토네이도", "mp": 50, "power": 80},
            {"name": "화염차", "mp": 50, "power": 70},
            {"name": "화염비", "mp": 50, "power": 70}
        ],
        "궁극기": [
            {"name": "지옥불", "mp": 80, "power": 120}
        ]
    },
    "물": {
        "하급": [
            {"name": "깨물기", "mp": 5, "power": 10},
            {"name": "물대포", "mp": 10, "power": 30},
            {"name": "나인테일", "mp": 20, "power": 40}
        ],
        "중급": [
            {"name": "하이드로 펌프", "mp": 30, "power": 60},
            {"name": "물수제비", "mp": 10, "power": 20},
            {"name": "몸통박치기", "mp": 10, "power": 20}
        ],
        "상급": [
            {"name": "소용돌이", "mp": 50, "power": 80},
            {"name": "우비", "mp": 50, "power": 70},
            {"name": "바다가르기", "mp": 50, "power": 70}
        ],
        "궁극기": [
            {"name": "대해일", "mp": 80, "power": 120}
        ]
    },
    "풀": {
        "하급": [
            {"name": "자기방어", "mp": 10, "power": 5},
            {"name": "나뭇잎날리기", "mp": 20, "power": 20},
            {"name": "깨물기", "mp": 10, "power": 10}
        ],
        "중급": [
            {"name": "나뭇잎 수리검", "mp": 20, "power": 30},
            {"name": "씨앗 대포", "mp": 30, "power": 50},
            {"name": "덩쿨소환", "mp": 20, "power": 30}
        ],
        "상급": [
            {"name": "쏠라빔", "mp": 50, "power": 80},
            {"name": "마비시키기", "mp": 40, "power": 30},
            {"name": "독중독", "mp": 40, "power": 40}
        ],
        "궁극기": [
            {"name": "대자연의 분노", "mp": 80, "power": 120}
        ]
    },
    "전기": {
        "하급": [
            {"name": "몸통박치기", "mp": 10, "power": 10},
            {"name": "10만볼트", "mp": 30, "power": 30},
            {"name": "나인테일", "mp": 20, "power": 20}
        ],
        "중급": [
            {"name": "100만볼트", "mp": 30, "power": 50},
            {"name": "전광석화", "mp": 40, "power": 50},
            {"name": "동료부르기", "mp": 20, "power": 10}
        ],
        "상급": [
            {"name": "1000만볼트", "mp": 60, "power": 80},
            {"name": "번개", "mp": 60, "power": 90},
            {"name": "방전", "mp": 30, "power": 50}
        ],
        "궁극기": [
            {"name": "천벌", "mp": 80, "power": 120}
        ]
    },
    "비행": {
        "하급": [
            {"name": "바람가르기", "mp": 20, "power": 30},
            {"name": "몸통박치기", "mp": 10, "power": 10},
            {"name": "공기포", "mp": 20, "power": 20}
        ],
        "중급": [
            {"name": "난기류 생성", "mp": 20, "power": 20},
            {"name": "토네이도", "mp": 40, "power": 50},
            {"name": "스텔스 모드", "mp": 30, "power": 20}
        ],
        "상급": [
            {"name": "메테오", "mp": 40, "power": 50},
            {"name": "수직강하", "mp": 20, "power": 40},
            {"name": "태풍", "mp": 50, "power": 80}
        ],
        "궁극기": [
            {"name": "폭풍우", "mp": 80, "power": 120}
        ]
    },
    "땅": {
        "하급": [
            {"name": "땅울림", "mp": 20, "power": 30},
            {"name": "바위던지기", "mp": 20, "power": 40},
            {"name": "모래뿌리기", "mp": 20, "power": 30}
        ],
        "중급": [
            {"name": "대지 가르기", "mp": 20, "power": 20},
            {"name": "바위솟기", "mp": 20, "power": 20},
            {"name": "암석손바닥", "mp": 40, "power": 60}
        ],
        "상급": [
            {"name": "모래무덤", "mp": 60, "power": 80},
            {"name": "모래감옥", "mp": 50, "power": 50},
            {"name": "땅꺼트리기", "mp": 40, "power": 50}
        ],
        "궁극기": [
            {"name": "대지진", "mp": 80, "power": 120}
        ]
    },
    "어둠": {
        "하급": [
            {"name": "스피어", "mp": 20, "power": 30},
            {"name": "암전", "mp": 10, "power": 10},
            {"name": "암살", "mp": 30, "power": 40}
        ],
        "중급": [
            {"name": "기습", "mp": 20, "power": 20},
            {"name": "암흑", "mp": 30, "power": 30},
            {"name": "암흑 스피어", "mp": 40, "power": 50}
        ],
        "상급": [
            {"name": "기억상실", "mp": 50, "power": 30},
            {"name": "블랙홀", "mp": 60, "power": 80},
            {"name": "암흑 불꽃", "mp": 50, "power": 80}
        ],
        "궁극기": [
            {"name": "블랙홀", "mp": 80, "power": 120}
        ]
    },
    "독": {
        "하급": [
            {"name": "중독", "mp": 30, "power": 20},
            {"name": "독 뿌리기", "mp": 30, "power": 20},
            {"name": "나인테일", "mp": 10, "power": 20}
        ],
        "중급": [
            {"name": "독니", "mp": 30, "power": 30},
            {"name": "맹독", "mp": 50, "power": 60},
            {"name": "스크럽", "mp": 30, "power": 30}
        ],
        "상급": [
            {"name": "독구름", "mp": 30, "power": 60},
            {"name": "전광석화", "mp": 60, "power": 80},
            {"name": "독안개", "mp": 50, "power": 50}
        ],
        "궁극기": [
            {"name": "맹독지대", "mp": 80, "power": 120}
        ]
    },
    "에스퍼": {
        "하급": [
            {"name": "날개치기", "mp": 30, "power": 30},
            {"name": "포효", "mp": 20, "power": 30},
            {"name": "위엄", "mp": 10, "power": 20}
        ],
        "중급": [
            {"name": "지구던지기", "mp": 30, "power": 30},
            {"name": "쏠라빔", "mp": 50, "power": 60},
            {"name": "잡고던지기", "mp": 20, "power": 30}
        ],
        "상급": [
            {"name": "대포", "mp": 50, "power": 50},
            {"name": "천재지변", "mp": 80, "power": 100},
            {"name": "재앙", "mp": 70, "power": 80}
        ],
        "궁극기": [
            {"name": "차원절단", "mp": 80, "power": 120}
        ]
    },
    "노말": {
        "하급": [
            {"name": "웅크리기", "mp": 10, "power": 10},
            {"name": "잠자기", "mp": 10, "power": 10},
            {"name": "깨물기", "mp": 10, "power": 20},
            {"name": "할퀴기", "mp": 10, "power": 20},
            {"name": "몸통박치기", "mp": 20, "power": 20}
        ],
        "중급": [
            {"name": "기습", "mp": 30, "power": 10},
            {"name": "소매치기", "mp": 20, "power": 30},
            {"name": "잡고 던지기", "mp": 30, "power": 30},
            {"name": "어퍼컷", "mp": 40, "power": 40},
            {"name": "헤드락", "mp": 40, "power": 50}
        ],
        "상급": [
            {"name": "물건던지기", "mp": 20, "power": 30},
            {"name": "최면", "mp": 20, "power": 30},
            {"name": "토네이도", "mp": 60, "power": 80},
            {"name": "전광석화", "mp": 50, "power": 70},
            {"name": "아파트 던지기", "mp": 80, "power": 80}
        ],
        "궁극기": [
            {"name": "최후의 일격", "mp": 80, "power": 120}
        ]
    }
}

def get_skill_info(skill_name):
    for category, content in SKILL_DATABASE.items():
        if isinstance(content, dict) and "하급" in content:
            for rank in ["하급", "중급", "상급", "궁극기"]:
                if rank in content:
                    for skill in content[rank]:
                        if skill["name"] == skill_name:
                            s = skill.copy()
                            s["element"] = category
                            return s
        elif isinstance(content, dict):
            if skill_name in content:
                skill_data = content[skill_name].copy()
                skill_data["name"] = skill_name
                skill_data["power"] = 0
                skill_data["element"] = category
                return skill_data
    return {"name": "몸통박치기", "mp": 0, "power": 10, "element": "노말"}

EQUIPMENT_STATS = {
    "일반": {"hp": 5, "atk": 5, "spd": 5, "crit": 0.0},
    "희귀": {"hp": 8, "atk": 8, "spd": 8, "crit": 0.01},
    "영웅": {"hp": 10, "atk": 10, "spd": 10, "crit": 0.03},
    "전설": {"hp": 5, "atk": 15, "spd": 5, "crit": 0.05}
}

def get_equipment_bonus(pet):
    bonus = {"hp": 0, "atk": 0, "spd": 0, "crit": 0.0}
    equipment = getattr(pet, "equipment", {"머리": None, "견갑": None, "허리": None, "다리": None})
    for part, grade in equipment.items():
        if grade and grade in EQUIPMENT_STATS:
            st = EQUIPMENT_STATS[grade]
            bonus["hp"] += st["hp"]
            bonus["atk"] += st["atk"]
            bonus["spd"] += st["spd"]
            bonus["crit"] += st["crit"]
    return bonus

class DiscordUIFormatter:
    @staticmethod
    def make_pet_embed_data(pet):
        pet.update_passive_decay()
        bonus = get_equipment_bonus(pet)
        hp_str = f" (+{bonus['hp']})" if bonus['hp'] else ""
        atk_str = f" (+{bonus['atk']})" if bonus['atk'] else ""
        spd_str = f" (+{bonus['spd']})" if bonus['spd'] else ""
        
        # 희귀도 계산 및 최종 스탯 도출
        mult = pet.rarity_multiplier
        f_atk = int((pet.attack + bonus['atk']) * mult)
        f_def = int((pet.defense) * mult)
        f_spd = int((pet.speed + bonus['spd']) * mult)
        
        fields = [
            {"name": "성장 단계 및 레벨", "value": f"**[{pet.stage}]** Lv.{pet.level} (EXP: {pet.exp})", "inline": True},
            {"name": "원소 타입", "value": f"🧬 메인: {pet.main_type}" + (f" / 부: {pet.sub_type}" if pet.sub_type else ""), "inline": True},
            {"name": "교감 친밀도", "value": f"❤️ {pet.affinity} [등급: {pet.affinity_rank}]", "inline": True},
            {"name": "현재 기분", "value": f"🎭 {pet.mood_state} (점수: {int(pet.mood_score)})", "inline": True},
            {"name": "신체 지표", "value": f"🍗 포만감: {int(pet.fullness)}/100 | 🧼 청결도: {int(pet.cleanliness)}/100\n⚡ 에너지: {int(pet.energy)}/100 | 💢 스트레스: {pet.stress}/100", "inline": False},
            {"name": f"실제 전투 스탯 (x{mult} 배율 및 장비 반영)", "value": f"⚔️ 공격: {f_atk}{atk_str} | 🛡️ 방어: {f_def}\n💨 속도: {f_spd}{spd_str} | 🍀 행운: {pet.luck}", "inline": False}
        ]
        
        skill_text = ", ".join(pet.skills) if pet.skills else "장착된 스킬 없음"
        fields.append({"name": "⚔️ 장착 중인 스킬 셋", "value": f"`{skill_text}`", "inline": False})
        
        eq = getattr(pet, "equipment", {"머리": None, "견갑": None, "허리": None, "다리": None})
        eq_text = f"머리: {eq.get('머리') or '없음'} | 견갑: {eq.get('견갑') or '없음'} | 허리: {eq.get('허리') or '없음'} | 다리: {eq.get('다리') or '없음'}"
        fields.append({"name": "🛡️ 착용 중인 장비", "value": f"`{eq_text}`", "inline": False})

        
        if pet.stage == "알":
            fields.append({"name": "🧬 알 유전 정보", "value": "개체값(IV) 및 성격 씨앗 비공개 상태", "inline": False})
        else:
            fields.append({"name": "📊 유전 능력치", "value": f"🧠 성격: {pet.personality} | 📊 IV: {pet.iv}/31", "inline": False})

        # 병걸림 상태 경고 추가
        if getattr(pet, "is_sick", False):
            fields.append({"name": "⚠️ 상태 이상: [질병]", "value": "🧼 청결도 방치로 병에 걸렸습니다! 모든 전투 능력치(공격, 방어, 속도)가 30% 감소합니다.", "inline": False})

        rarity_emoji = {"일반": "🐾", "희귀": "✨", "영웅": "🌟", "전설": "👑"}.get(pet.rarity, "🐾")
        
        IMAGE_DATABASE = {
            "불": { # 호랑이
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774743368470578/A.png?ex=6a583f48&is=6a56edc8&hm=34a1d61d61ceecfedfde9ee0880b752a65d343a74e8d7bcd700a857d64cede53&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774743666130994/AA.png?ex=6a583f48&is=6a56edc8&hm=fb5576020c837b427ae4f239cdd87d707525480b2eae929ac77467a80518472d&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774743988961311/AAA.png?ex=6a583f49&is=6a56edc9&hm=12d7029151472280d640d2c4d5b8d060fda9dda9f1aaea379bbdba2317324875&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774744324767844/AAAA.png?ex=6a583f49&is=6a56edc9&hm=7af9ddefb21f97a1cc5f43af483f3f58c249f129658c02dae4a672c97264eae5&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774744618238034/AAAAA.png?ex=6a583f49&is=6a56edc9&hm=45f4694a27c19e17eae845e018f050f9c3a08bdf51915748f737641d32f40083&=&format=webp&quality=lossless"
            },
            "물": { # 개
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774807201447986/B.png?ex=6a583f58&is=6a56edd8&hm=2fd9c762dce3ab580576fe571031ef8442d477f879a15401483771607fa22ea3&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774805490303066/BB.png?ex=6a583f57&is=6a56edd7&hm=c509005573bf2805f30e7c0dc5fa9847e20bb5514a560ee2a40f11c061dcebe6&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774805859143700/BBB.png?ex=6a583f57&is=6a56edd7&hm=f50cea725593fa1e7601dc596c631baa1c5e4f0d4eaec0b2762081a70bb2b915&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774806228238406/BBBB.png?ex=6a583f57&is=6a56edd7&hm=3af2613cbd0b0e9a1582c0522345335d6835a350380f929419ad542bcaf7aa4c&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774806756982885/BBBBB.png?ex=6a583f58&is=6a56edd8&hm=22b3b6d8a1d4b2a80880ed975d5b37176c81fa00184e2786ff3f67d8aac12f86&=&format=webp&quality=lossless"
            },
            "풀": { # 토끼
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774731792060447/C.png?ex=6a583f46&is=6a56edc6&hm=2853e975f15074af227b2b2b5852b7fda6ec29e74b387e44ebc9d8ac0adaad88&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774732115017849/CC.png?ex=6a583f46&is=6a56edc6&hm=26300ff32e9bc3c056c4e562609fb9d6e3a277e085f90c3db6cad0ff7ee8fe0f&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774732421075014/CCC.png?ex=6a583f46&is=6a56edc6&hm=fcd98dc7674fdea3d8da8d014ebfa0f4220d39d464fd94bbc74b689dd18c3917&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774732760940675/CCCC.png?ex=6a583f46&is=6a56edc6&hm=8f5c91c278e568b577408e74bd0ca4ef6fa4559ed9e240be0944e5fadedd8f37&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774733113135235/CCCCC.png?ex=6a583f46&is=6a56edc6&hm=06995f13ab3ec7d222894d3f8f28c1bd9f297f2633c89f31fcece2c28ab47a9c&=&format=webp&quality=lossless"
            },
            "전기": { # 말
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774714771443712/D.png?ex=6a583f42&is=6a56edc2&hm=900383bc20d9dcbfa9f4d236e23470d6047ae0445d29416df220393dfd5cb72b&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774715174228008/DD.png?ex=6a583f42&is=6a56edc2&hm=8d323041c0dbc093b0a9a541473f1853927800bab88de22301304b1778a1d300&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774715501252688/DDD.png?ex=6a583f42&is=6a56edc2&hm=617421f85cf370938b131fd74179aecd3dbdd082882c9b1ddff2b940d75d87df&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774715845316729/DDDD.png?ex=6a583f42&is=6a56edc2&hm=0ea9a600eb9214e2cce4794d789a3be635feac6efa389347cd9adc582f64ff6d&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774716193312809/DDDDD.png?ex=6a583f42&is=6a56edc2&hm=bdb5fa41272408c9b94269db45f5af00f787de67098d6afaedf9cdec95e8d7a5&=&format=webp&quality=lossless"
            },
            "비행": { # 닭
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774699101523978/E.png?ex=6a583f3e&is=6a56edbe&hm=0848e2e6b7c3839c924239e1a672349d44e7381fc0834a3c2c4a94e30f9400b9&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774699512561885/EE.png?ex=6a583f3e&is=6a56edbe&hm=9d6df9a756b75b909e12d34fce716e627847d07d16975a0ba55392b169ea8943&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774699865149610/EEE.png?ex=6a583f3e&is=6a56edbe&hm=65909203fd13e530c08dce0d92261b6a2a18fe1493fd1bec1afb3b9bf830c658&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774700246827170/EEEE.png?ex=6a583f3e&is=6a56edbe&hm=05e0f544bbfaa1a92a0e376efea0b4f8a80ef7af9c47dc502d7f239f52b693f6&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774700636635247/EEEEE.png?ex=6a583f3e&is=6a56edbe&hm=89ccd60444a75b60374c1b6473dc73c2ba3ee4529bc8f260429c9678544812b5&=&format=webp&quality=lossless"
            },
            "땅": { # 쥐
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774772132876472/J.png?ex=6a583f4f&is=6a56edcf&hm=4edc766c9adeb6b5b80ad576344b59c5f086f390b0fee8b3d997fd512f14f669&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774772493713428/JJ.png?ex=6a583f4f&is=6a56edcf&hm=05fa0602ec72dcfbf106e9a2f4e2616c7ee3771ab533d94b753dd7d2a46ad19d&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774772816543855/JJJ.png?ex=6a583f4f&is=6a56edcf&hm=10e9644b1add2b4b9575f49027d9173174a9a8683365c92178d29c1fa40710c5&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774773105823815/JJJJ.png?ex=6a583f50&is=6a56edd0&hm=fdedabe0270513e7faad6d39b9954fc9929fcf9f0cef99d94101639d91c41ac5&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774773403877426/JJJJJ.png?ex=6a583f50&is=6a56edd0&hm=f681d179b88bac82c82cb0b462ab2dc202fd78fd67de5a36df7bf801b69c73de&=&format=webp&quality=lossless"
            },
            "얼음": { # 원숭이
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774759227134112/K.png?ex=6a583f4c&is=6a56edcc&hm=92a4288abe7d8fb57a217571c54b4c8d9bfcd2bb80db0302ac47a8fba56b6933&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774759818268672/KK.png?ex=6a583f4c&is=6a56edcc&hm=11f078618f33fd4d25c4b612e974f31e4f189c8b1d24014a625c497bf553e241&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774760313458728/KKK.png?ex=6a583f4c&is=6a56edcc&hm=38a6a52ae0fded7806ae64af59e054325f31642189fa0aa4a65549aad1ad522d&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774760682426519/KKKK.png?ex=6a583f4d&is=6a56edcd&hm=75148244ea816b382274acd61af3eb5899fec94fe251d75ed9725d2b97426e2d&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774761257041920/KKKKK.png?ex=6a583f4d&is=6a56edcd&hm=a57158599a5cc5d71fb9a2b955817eaf51c1ece6cadc279a5a036f80baf00a9b&=&format=webp&quality=lossless"
            },
            "어둠": { # 양
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774647738208256/I.png?ex=6a583f32&is=6a56edb2&hm=6464e6919af5616a39d0ca67c18ee3da748106078819047bb8a18ca26dcca979&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774648107438080/II.png?ex=6a583f32&is=6a56edb2&hm=541ea7b9470aef626e8d19a832a47758f3d01e309d033c621da82b0625d29e58&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774648669343884/III.png?ex=6a583f32&is=6a56edb2&hm=5bcaac1af5901db44211d3caeb8b3659b02524fb426841fa01538584bf273230&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774649034375288/IIII.png?ex=6a583f32&is=6a56edb2&hm=e38202f6fd808505daab9a413004a223db153724822f53ed6def933470b8d835&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774649491423232/IIIII.png?ex=6a583f32&is=6a56edb2&hm=614c74fe90ff0b614da45f86a6d58acf682a623f7a8ba101a3941312cdbd7ea7&=&format=webp&quality=lossless"
            },
            "독": { # 뱀
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774786519339090/H.png?ex=6a583f53&is=6a56edd3&hm=3d2d9784476ff39e9a17cf7e7a0c9b04a4ab17f2cd098b0aefaf72171ef9c0cd&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774786879914055/HH.png?ex=6a583f53&is=6a56edd3&hm=4721687b41d26267f1e227688b291168c57456b32a325678ed6034e0eb670f7c&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774787186360380/HHH.png?ex=6a583f53&is=6a56edd3&hm=90f946ca7c254b3288086249658e901f10184bc58031c72512d5fbfcf4f857af&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774787551137843/HHHH.png?ex=6a583f53&is=6a56edd3&hm=dad80420f1804058544c1356a62b90110ed791154c0c077ccafffe31cb017558&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774787882352701/HHHHH.png?ex=6a583f53&is=6a56edd3&hm=6245951787235f2e230d1e9fa993b0fdd8bfc0ea519b26ff6bae9b47d0c34463&=&format=webp&quality=lossless"
            },
            "에스퍼": { # 용
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774664569946255/G.png?ex=6a583f36&is=6a56edb6&hm=cda1b8301ac54889157462cc7d84e366b5d84b7df2d32885ab994cfe7fa62fd3&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774664880328934/GG.png?ex=6a583f36&is=6a56edb6&hm=f241a6c11b4d61dd7db8c7cdec73e990dfe75f078787b63d1674247f4f417aba&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774665257947276/GGG.png?ex=6a583f36&is=6a56edb6&hm=dd3b31fe2477da592b66eb6e55e5cf001b2467d068fc0f8417eefa33feb6cf76&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774665564127273/GGGG.png?ex=6a583f36&is=6a56edb6&hm=2aa09b87bcc9225bd879c7328904a48be274a7d16616122e60a3b1b7fe01fedb&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774665849344010/GGGGG.png?ex=6a583f36&is=6a56edb6&hm=503e9a65a80652e006581e9fc5249f84496a320b18b1b55894b09349feb7e43f&=&format=webp&quality=lossless"
            },
            "노말": { # 노말 기본종
                "알": "https://media.discordapp.net/attachments/1464543163669680171/1526774685377888356/F.png?ex=6a583f3b&is=6a56edbb&hm=52a8a2c610292b66de5e372ab3f35cefa2b305556133cf1581f61af09706f218&=&format=webp&quality=lossless",
                "새끼": "https://media.discordapp.net/attachments/1464543163669680171/1526774685755379832/FF.png?ex=6a583f3b&is=6a56edbb&hm=a402b6573ec4e708e0484d34817a490a692197d84f3c3446eaa579e35ba57883&=&format=webp&quality=lossless",
                "유년기": "https://media.discordapp.net/attachments/1464543163669680171/1526774686208229376/FFF.png?ex=6a583f3b&is=6a56edbb&hm=e0a229400a569c0fedef15805e230d289b04ac1a83a398e0cb85e01067a05ae8&=&format=webp&quality=lossless",
                "성체": "https://media.discordapp.net/attachments/1464543163669680171/1526774686950625410/FFFF.png?ex=6a583f3b&is=6a56edbb&hm=06f69f4514ad2687eac4d60deaad0ec28e7d897de4e7f723cace39f86de44a48&=&format=webp&quality=lossless",
                "최종 진화": "https://media.discordapp.net/attachments/1464543163669680171/1526774687349080205/FFFFF.png?ex=6a583f3b&is=6a56edbb&hm=89d65476e63dc853e3b31bdd387cf6f8a76900eb2c2df28792f7334ca0786490&=&format=webp&quality=lossless"
            }
        }
        
        # 메인 타입에 맞는 데이터셋 확인 후 현재 단계의 이미지 URL을 가져옵니다.
        # 데이터가 비어있거나 타입이 존재하지 않으면 기본 에러 방지용 대체 이미지가 들어갑니다.
        type_data = IMAGE_DATABASE.get(pet.main_type, IMAGE_DATABASE["노말"])
        pet_image_url = type_data.get(pet.stage, "https://media.discordapp.net/attachments/1464543163669680171/1526779055507243008/L.png?ex=6a58434d&is=6a56f1cd&hm=897ce048910664429eb78e074902125342f612bf4cac8c10e914e7f6c2b254b8&=&format=webp&quality=lossless")
        if not pet_image_url:
            pet_image_url = "https://media.discordapp.net/attachments/1464543163669680171/1526779055507243008/L.png?ex=6a58434d&is=6a56f1cd&hm=897ce048910664429eb78e074902125342f612bf4cac8c10e914e7f6c2b254b8&=&format=webp&quality=lossless" # 링크 빈 칸 대비 백업 주소
        
        return {
            "title": f"{rarity_emoji} [{pet.rarity}] {pet.name}의 상세 상태창",
            "description": f"주인과 동행 중인 파트너 펫의 상태입니다.",
            "fields": fields,
            "image_url": pet_image_url # 👈 웹 URL 전송 키로 최종 반환[cite: 20]
        }
    
    @staticmethod
    def get_tier_str(score):
        if score < 1000: return "🪨 아이언"
        elif score < 1200: return "🥉 브론즈"
        elif score < 1400: return "🥈 실버"
        elif score < 1600: return "🥇 골드"
        elif score < 2000: return "💎 플래티넘"
        else: return "👑 다이아몬드"

    @staticmethod
    def make_user_embed_data(user_db_row, pet):
        active_pet_name = pet.name if pet else "없음"
        cash = user_db_row.get('cash', 0) if user_db_row else 0
        rank_score = user_db_row.get('pet_rank_score', 1000) if user_db_row else 1000
        tier = DiscordUIFormatter.get_tier_str(rank_score)
        
        return {
            "title": f"🛡️ 보호자 프로필 허브",
            "description": f"**동행 중인 메인 펫:** `{active_pet_name}`",
            "fields": [
                {"name": "💰 보유 자산", "value": f"**{cash:,}원**", "inline": True},
                {"name": "🏆 현재 랭크", "value": f"{tier} ({rank_score}점)", "inline": True},
                {"name": "📋 출석 현황", "value": "정상 출석 완료", "inline": True}
            ]
        }


class PvPBattle:
    def __init__(self, pet_a, pet_b):
        self.pet_a = pet_a
        self.pet_b = pet_b
        self.log = []
        self.turn_count = 1
        self.winner = None
        
        self.status_a = None
        self.status_b = None
        self.poison_stack_a = 0
        self.poison_stack_b = 0
        
        # 기분이 최악인 펫은 참가 불가 처리 사전 정의
        if pet_a.mood_state == "화남" or pet_b.mood_state == "화남":
             raise ValueError("기분이 최악(화남) 상태인 펫은 배틀에 출전시킬 수 없습니다!")

        bonus_a = get_equipment_bonus(pet_a)
        bonus_b = get_equipment_bonus(pet_b)

        mult_a = getattr(pet_a, "rarity_multiplier", 1.0)
        mult_b = getattr(pet_b, "rarity_multiplier", 1.0)
        
        self.hp_a = int((10 + int((250 * pet_a.level) / 100) + pet_a.iv + bonus_a["hp"]) * mult_a)
        self.hp_b = int((10 + int((250 * pet_b.level) / 100) + pet_b.iv + bonus_b["hp"]) * mult_b)
        self.max_hp_a = self.hp_a
        self.max_hp_b = self.hp_b
        
        self.mp_a = int(pet_a.max_mp * mult_a)
        self.mp_b = int(pet_b.max_mp * mult_b)
        
        self.atk_a = int((pet_a.attack + bonus_a["atk"]) * mult_a)
        self.atk_b = int((pet_b.attack + bonus_b["atk"]) * mult_b)
        self.def_a = int((pet_a.defense) * mult_a)
        self.def_b = int((pet_b.defense) * mult_b)
        self.spd_a = int((pet_a.speed + bonus_a["spd"]) * mult_a)
        self.spd_b = int((pet_b.speed + bonus_b["spd"]) * mult_b)
        
        self.crit_bonus_a = bonus_a["crit"]
        self.crit_bonus_b = bonus_b["crit"]

    def execute_turn(self, player_action=None):
        if self.hp_a <= 0 or self.hp_b <= 0 or self.turn_count > 20:
            return self.get_result()
            
        self.log.append(f"\n**[Round {self.turn_count}]**")
        
        # 턴 시작 마비 체크
        skip_a = False
        skip_b = False
        if self.status_a == "마비" and random.random() < 0.5:
            self.log.append(f"⚡ {self.pet_a.name}이(가) [마비]로 인해 몸이 저려 움직일 수 없습니다!")
            skip_a = True
        if self.status_b == "마비" and random.random() < 0.5:
            self.log.append(f"⚡ {self.pet_b.name}이(가) [마비]로 인해 몸이 저려 움직일 수 없습니다!")
            skip_b = True
            
        first = self.check_first_strike()
        if first == "SPEED_BASED":
            first = "A" if self.spd_a >= self.spd_b else "B"
            
        if first == "A":
            if not skip_a: self.process_attack(self.pet_a, self.pet_b, player_action, is_a=True)
            if self.hp_b > 0 and not skip_b:
                self.process_attack(self.pet_b, self.pet_a, None, is_a=False)
        else:
            if not skip_b: self.process_attack(self.pet_b, self.pet_a, None, is_a=False)
            if self.hp_a > 0 and not skip_a:
                self.process_attack(self.pet_a, self.pet_b, player_action, is_a=True)
                
        self.process_end_of_turn_effects()
            
        self.turn_count += 1
        
        if self.hp_a <= 0 or self.hp_b <= 0:
            return self.get_result()
        return None
        
    def process_end_of_turn_effects(self):
        # 도트 데미지 처리 (A)
        if self.status_a == "화상" and self.hp_a > 0:
            dmg = max(1, int(self.max_hp_a * 0.10))
            self.hp_a -= dmg
            self.log.append(f"🔥 {self.pet_a.name}이(가) [화상] 피해를 입었습니다! (-{dmg})")
        elif self.status_a == "맹독" and self.hp_a > 0:
            self.poison_stack_a += 1
            dmg = max(1, int(self.max_hp_a * (self.poison_stack_a / 16.0)))
            self.hp_a -= dmg
            self.log.append(f"☠️ {self.pet_a.name}이(가) [맹독] 피해를 입었습니다! (-{dmg})")
            
        # 도트 데미지 처리 (B)
        if self.status_b == "화상" and self.hp_b > 0:
            dmg = max(1, int(self.max_hp_b * 0.10))
            self.hp_b -= dmg
            self.log.append(f"🔥 {self.pet_b.name}이(가) [화상] 피해를 입었습니다! (-{dmg})")
        elif self.status_b == "맹독" and self.hp_b > 0:
            self.poison_stack_b += 1
            dmg = max(1, int(self.max_hp_b * (self.poison_stack_b / 16.0)))
            self.hp_b -= dmg
            self.log.append(f"☠️ {self.pet_b.name}이(가) [맹독] 피해를 입었습니다! (-{dmg})")
            
        # [물] 타입 패시브: 잃은 체력의 5% 재생
        climate = ClimateManager().get_current_climate()
        water_heal_mult = 1.0
        if climate.weather == "한파" or climate.weather == "맑음":
            water_heal_mult = 1.05
        elif climate.weather == "폭염":
            water_heal_mult = 0.95
            
        if self.pet_a.main_type == "물" and self.hp_a > 0 and self.hp_a < self.max_hp_a:
            heal = max(1, int((self.max_hp_a - self.hp_a) * 0.05 * water_heal_mult))
            self.hp_a = min(self.max_hp_a, self.hp_a + heal)
            self.log.append(f"💧 {self.pet_a.name}이(가) [물] 패시브로 상처를 재생했습니다! (+{heal})")
        if self.pet_b.main_type == "물" and self.hp_b > 0 and self.hp_b < self.max_hp_b:
            heal = max(1, int((self.max_hp_b - self.hp_b) * 0.05 * water_heal_mult))
            self.hp_b = min(self.max_hp_b, self.hp_b + heal)
            self.log.append(f"💧 {self.pet_b.name}이(가) [물] 패시브로 상처를 재생했습니다! (+{heal})")

    def process_attack(self, attacker, defender, chosen_skill_name, is_a=True):
        skill_name = chosen_skill_name
        if not skill_name:
            avail_skills = attacker.skills if attacker.skills else ["몸통박치기"]
            skill_name = random.choice(avail_skills)
            
        skill_info = get_skill_info(skill_name)
        mp_cost = self.calculate_mp_cost(attacker, skill_info.get("mp", 0))
        
        current_mp = self.mp_a if is_a else self.mp_b
        if current_mp < mp_cost:
            skill_name = "몸통박치기"
            skill_info = {"name": "몸통박치기", "mp": 0, "power": 10}
            mp_cost = 0
            
        if is_a:
            self.mp_a -= mp_cost
        else:
            self.mp_b -= mp_cost
            
        if not self.check_skill_activation(attacker, 0.8):
            self.log.append(f"💨 {attacker.name}이(가) {skill_name}을(를) 시도했으나 빗나갔습니다!")
            return
            
        if self.check_evasion(defender):
            self.log.append(f"🍃 {defender.name}이(가) [비행] 패시브로 공격을 회피했습니다!")
            return
            
        atk = self.atk_a if is_a else self.atk_b
        dfn = self.def_b if is_a else self.def_a
        
        base_dmg = skill_info.get("power", 10) * (atk / max(1, dfn))
        
        # [어둠] 타입 개성: 상대가 상태이상일 경우 피해량 1.5배
        target_status = self.status_b if is_a else self.status_a
        if attacker.main_type == "어둠" and target_status:
            base_dmg *= 1.5
            
        final_dmg = self.apply_type_advantage(attacker, defender, base_dmg, skill_info)
        
        crit_bns = self.crit_bonus_a if is_a else self.crit_bonus_b
        if random.random() < 0.1 + crit_bns:
            if self.check_crit_resist(defender):
                self.log.append(f"🛡️ {defender.name}이(가) [수호] 혜택으로 치명타를 방어했습니다!")
            else:
                final_dmg *= self.calculate_crit_multiplier(attacker, defender)
                self.log.append(f"💥 **치명타 적중!**")
                
        final_dmg *= self.calculate_affinity_damage_multiplier(attacker)
        
        # 기후 기반 배틀 데미지 및 보정 로직
        climate = ClimateManager().get_current_climate()
        if climate.weather == "맑음" and attacker.main_type == "불":
            final_dmg *= 1.05
        elif climate.weather == "비":
            if attacker.main_type == "물": final_dmg *= 1.05
            elif attacker.main_type == "불": final_dmg *= 0.95
        elif climate.weather == "폭염":
            if attacker.main_type == "불": final_dmg *= 1.05
        elif climate.weather == "한파":
            if attacker.main_type == "불": final_dmg *= 0.95
        
        final_dmg = max(1, int(final_dmg))
        
        # [땅] 타입 개성: 단단한 피부 (모든 받는 데미지 15% 감소) + 눈 날씨 방어력 보정
        ground_def_mult = 0.85
        if climate.weather == "눈" and defender.main_type == "물":
            ground_def_mult -= 0.05 # 방어 5% 추가 (물)
        
        if defender.main_type == "땅":
            final_dmg = max(1, int(final_dmg * ground_def_mult))
        elif climate.weather == "눈" and defender.main_type == "물":
            final_dmg = max(1, int(final_dmg * 0.95))
            
        if is_a:
            self.hp_b -= final_dmg
        else:
            self.hp_a -= final_dmg
            
        self.log.append(f"⚔️ {attacker.name}이(가) {skill_name}을(를) 사용! ({final_dmg} 데미지)")
        
        # [풀] 타입 개성: 흡혈 (준 데미지의 20% 회복)
        if attacker.main_type == "풀":
            heal = max(1, int(final_dmg * 0.20))
            if is_a:
                self.hp_a = min(self.max_hp_a, self.hp_a + heal)
            else:
                self.hp_b = min(self.max_hp_b, self.hp_b + heal)
            self.log.append(f"🌿 {attacker.name}이(가) [풀] 패시브로 체력을 흡수했습니다! (+{heal})")
            
        # 상태이상 부여 패시브 (불, 독, 전기)
        if attacker.main_type == "불" and random.random() < 0.15:
            if is_a and self.status_b != "화상":
                self.status_b = "화상"
                self.log.append(f"🔥 {defender.name}에게 [화상]이 부여되었습니다!")
            elif not is_a and self.status_a != "화상":
                self.status_a = "화상"
                self.log.append(f"🔥 {defender.name}에게 [화상]이 부여되었습니다!")
                
        if attacker.main_type == "독" and random.random() < 0.20:
            if is_a and self.status_b != "맹독":
                self.status_b = "맹독"
                self.poison_stack_b = 0
                self.log.append(f"☠️ {defender.name}에게 [맹독]이 부여되었습니다!")
            elif not is_a and self.status_a != "맹독":
                self.status_a = "맹독"
                self.poison_stack_a = 0
                self.log.append(f"☠️ {defender.name}에게 [맹독]이 부여되었습니다!")
                
        if attacker.main_type == "전기":
            paralysis_chance = 0.15
            if climate.weather == "비": paralysis_chance += 0.05
            
            if random.random() < paralysis_chance:
                if is_a and self.status_b != "마비":
                    self.status_b = "마비"
                    self.log.append(f"⚡ {defender.name}에게 [마비]가 부여되었습니다!")
                elif not is_a and self.status_a != "마비":
                    self.status_a = "마비"
                    self.log.append(f"⚡ {defender.name}에게 [마비]가 부여되었습니다!")

    def get_result(self):
        if self.hp_a <= 0 and self.hp_b <= 0:
            self.winner = "DRAW"
            self.log.append("\n🤝 무승부입니다!")
        elif self.hp_b <= 0:
            self.winner = "A"
            self.log.append(f"\n🎉 {self.pet_a.name} 승리!")
        elif self.hp_a <= 0:
            self.winner = "B"
            self.log.append(f"\n🎉 {self.pet_b.name} 승리!")
        else:
            self.winner = "DRAW"
            self.log.append("\n⏳ 턴 초과로 무승부입니다!")
        return self.winner

    def apply_type_advantage(self, attacker, defender, base_dmg, skill_info):
        skill_element = skill_info.get("element", "노말")
        
        # 1. 방어자의 메인 타입 및 서브 타입에 따른 속성 배율 계산
        comp_main = TYPE_CHART.get(skill_element, {}).get(defender.main_type, 1.0)
        comp_sub = 1.0
        if defender.sub_type:
            comp_sub = TYPE_CHART.get(skill_element, {}).get(defender.sub_type, 1.0)
            
        comp = comp_main * comp_sub
        
        if comp > 1.0:
            self.log.append(f"💥 효과가 굉장했다! (상성 우위 x{comp})")
        elif comp < 1.0 and comp > 0.0:
            if attacker.main_type == "노말":
                comp = 1.0
                self.log.append(f"✨ [노말] 패시브 발동! 상성 열위를 무시하고 안정적인 데미지를 가합니다! (x1.0)")
            else:
                self.log.append(f"📉 효과가 별로인 것 같다... (상성 열위 x{comp})")
        elif comp == 0.0:
            if attacker.main_type == "노말":
                comp = 1.0
                self.log.append(f"✨ [노말] 패시브 발동! 상성 무효를 무시하고 데미지를 가합니다! (x1.0)")
            else:
                self.log.append(f"❌ 효과가 없다! (상성 무효)")
            
        final_dmg = base_dmg * comp
        
        # 2. 자속 보정 (STAB - Same Type Attack Bonus): 공격자의 타입과 스킬 타입이 일치하면 1.5배
        if skill_element in [attacker.main_type, attacker.sub_type]:
            final_dmg *= 1.5
            
        # 병걸림 스탯 감소 디버프 30% 반영
        if getattr(attacker, "is_sick", False):
            final_dmg *= 0.7
            
        # 나태: 스킬 피해 -30%
        if attacker.personality == "나태":
            final_dmg *= 0.7

        if attacker.main_type == "불" and random.random() < 0.15:
            print("🔥 [불 타입 개성] 상대에게 지속 화상 피해 조건 부여!")
            
        if attacker.main_type == "어둠":
            final_dmg *= 1.2
            
        if attacker.personality == "신중함" and comp > 1.0:
            if random.random() < 0.5:
                final_dmg *= 2.5
                print("🧠 [신중함 성격] 상성 허점을 찔러 2.5배 약점 데미지 폭발!")
                
        return int(final_dmg)

    def check_first_strike(self):
        """다혈질 성격 및 [전기] 타입 개성에 의한 선제공격 판정"""
        a_first_chance = 0.3 if self.pet_a.personality == "다혈질" else 0.0
        b_first_chance = 0.3 if self.pet_b.personality == "다혈질" else 0.0
        
        # [전기] 타입 개성: 선공 확률 10% 증가
        if self.pet_a.main_type == "전기":
            a_first_chance += 0.1
        if self.pet_b.main_type == "전기":
            b_first_chance += 0.1
        
        # 선공 우선권 난수 처리
        roll_a = random.random() < a_first_chance
        roll_b = random.random() < b_first_chance
        
        if roll_a and not roll_b: return "A"
        if roll_b and not roll_a: return "B"
        return "SPEED_BASED"

    def check_stun_effect(self, attacker, skill_name):
        """용맹함 성격 등에 의한 스턴 효과 판정"""
        base_stun_chance = 0.0
        # 기본 공격 (몸통박치기, 할퀴기, 깨물기 등) 시 스턴 확률 기본 10%
        if skill_name in ["몸통박치기", "할퀴기", "깨물기"]:
            base_stun_chance = 0.1
            
        if attacker.personality == "용맹함":
            base_stun_chance += 0.5 # 50%p 증가
            
        if random.random() < base_stun_chance:
            return True
        return False

    # 📌 [인덴트 조정] PvPBattle 클래스 안쪽의 들여쓰기로 밀어 넣었습니다.[cite: 20]
    def calculate_mp_cost(self, pet, base_cost):
        """[에스퍼] 타입 개성: 스킬 MP 소모 30% 감소"""
        if pet.main_type == "에스퍼":
            return int(base_cost * 0.7)
        return base_cost

    def check_evasion(self, defender):
        """[비행] 타입 개성: 회피율 15% 증가"""
        base_evasion = 0.05  # 기본 회피율 5% 가정
        if defender.main_type == "비행":
            base_evasion += 0.15
        return random.random() < base_evasion

    def calculate_crit_multiplier(self, attacker, defender):
        """[어둠] 치명타 피해 +20%, [땅] 받는 치명타 피해 -20% 개성"""
        base_crit_mult = 1.5
        if attacker.main_type == "어둠":
            base_crit_mult += 0.20
        if defender.main_type == "땅":
            base_crit_mult -= 0.20
        return max(1.0, base_crit_mult)

    def get_status_effect_duration(self, caster, effect_type, base_duration):
        """[독] 중독 턴수 연장, [에스퍼] 버프/디버프 턴수 연장 개성"""
        duration = base_duration
        if caster.main_type == "독" and effect_type == "중독":
            duration += 1
        return duration

    def calculate_affinity_damage_multiplier(self, attacker):
        """[야성] 친밀도 등급 혜택: 공격력 5% 증가"""
        if getattr(attacker, "affinity_rank", None) == "야성":
            return 1.05
        return 1.0

    def check_skill_activation(self, pet, base_chance):
        """[신뢰] 친밀도 등급 혜택: 스킬 발동률 10% 증가"""
        chance = base_chance
        if getattr(pet, "affinity_rank", None) == "신뢰":
            chance += 0.10
        return random.random() < chance

    def check_crit_resist(self, defender):
        """[수호] 친밀도 등급 혜택: 치명타 저항 확률 10% 부여"""
        if getattr(defender, "affinity_rank", None) == "수호":
            return random.random() < 0.10
        return False