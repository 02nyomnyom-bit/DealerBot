# pet_climate.py
import time
import json
import urllib.request
import random
from datetime import datetime
from dataclasses import dataclass
from typing import Optional

@dataclass
class ClimateState:
    season: str
    weather: str # 맑음, 흐림, 비, 강풍, 폭염, 한파, 눈, 안개
    is_night: bool
    special_weather: Optional[str] # 폭풍우, 무지개, 유성우, 화산 활동, 오로라, 개기월식, 보름달 등
    temperature: int
    wind_speed: int
    raw_desc: str

class ClimateManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ClimateManager, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        self.last_fetch_time = 0
        self.cached_state: Optional[ClimateState] = None

    def get_season(self, month: int) -> str:
        if 3 <= month <= 5: return "봄"
        elif 6 <= month <= 8: return "여름"
        elif 9 <= month <= 11: return "가을"
        else: return "겨울"

    def fetch_weather_api(self):
        try:
            req = urllib.request.urlopen("https://wttr.in/Jeju?format=j1", timeout=5)
            data = json.loads(req.read())
            current = data['current_condition'][0]
            temp = int(current['temp_C'])
            wind = int(current['windspeedKmph'])
            desc = current['weatherDesc'][0]['value'].lower()
            return temp, wind, desc
        except Exception as e:
            print(f"Weather API Fetch Error: {e}")
            # API 에러 시 임시 디폴트 (맑음, 20도, 바람 5)
            return 20, 5, "clear"

    def get_current_climate(self) -> ClimateState:
        now = time.time()
        # 1시간(3600초) 단위 캐싱
        if self.cached_state is None or (now - self.last_fetch_time) > 3600:
            self.last_fetch_time = now
            
            from datetime import timezone, timedelta
            tz_kst = timezone(timedelta(hours=9))
            dt = datetime.now(tz_kst)
            
            month = dt.month
            hour = dt.hour
            
            season = self.get_season(month)
            is_night = (hour >= 19 or hour <= 6)
            
            temp, wind, raw_desc = self.fetch_weather_api()
            
            # 1. 기본 날씨 판별 로직
            weather = "맑음"
            
            if temp >= 33:
                weather = "폭염"
            elif temp <= 5:
                weather = "한파"
            elif wind >= 28: # 28km/h ≒ 7.7m/s
                weather = "강풍"
            elif "snow" in raw_desc or "ice" in raw_desc or "blizzard" in raw_desc:
                weather = "눈"
            elif "rain" in raw_desc or "drizzle" in raw_desc or "shower" in raw_desc:
                weather = "비"
            elif "fog" in raw_desc or "mist" in raw_desc:
                weather = "안개"
            elif "cloud" in raw_desc or "overcast" in raw_desc:
                weather = "흐림"
            elif "clear" in raw_desc or "sunny" in raw_desc:
                weather = "맑음"
            else:
                weather = "흐림" # fallback
                
            # 2. 특수 기상 이벤트 산출
            special = None
            prob = random.random()
            
            if prob < 0.05: # 매 시간 5% 확률로 특수 기상 체크
                event_roll = random.random()
                if weather == "강풍" and "rain" in raw_desc:
                    special = "폭풍우"
                elif weather == "맑음" and event_roll < 0.2:
                    special = "무지개"
                elif is_night and event_roll < 0.15:
                    special = "유성우"
                elif season == "겨울" and is_night and event_roll < 0.1:
                    special = "오로라"
                elif event_roll < 0.05:
                    special = "화산 활동"
            
            # 보름달 및 개기월식 (임의의 확률 또는 특정 날짜)
            if is_night and dt.day in [14, 15, 16] and special is None:
                if random.random() < 0.1:
                    special = "개기월식"
                else:
                    special = "보름달"
                    
            self.cached_state = ClimateState(
                season=season,
                weather=weather,
                is_night=is_night,
                special_weather=special,
                temperature=temp,
                wind_speed=wind,
                raw_desc=raw_desc
            )
            
        return self.cached_state