# Discord Bot DigitalOcean 배포 가이드

## 📋 사전 준비사항

### 1. Discord Bot 설정
1. [Discord Developer Portal](https://discord.com/developers/applications)에서 봇 생성
2. Bot 토큰 복사 (나중에 `.env` 파일에 입력)
3. Bot 권한 설정:
   - `Administrator` 또는 필요한 권한 체크
   - Privileged Gateway Intents 활성화:
     - ✅ PRESENCE INTENT
     - ✅ SERVER MEMBERS INTENT
     - ✅ MESSAGE CONTENT INTENT
4. OAuth2 → URL Generator에서 초대 링크 생성 후 서버에 봇 추가

### 2. Discord 서버 ID 확인
1. Discord 앱에서 `설정 → 고급 → 개발자 모드` 활성화
2. 서버 이름 우클릭 → `서버 ID 복사`

---

## 🚀 DigitalOcean 배포 (Ubuntu 22.04)

### 1단계: Droplet 생성

```bash
# DigitalOcean 웹사이트에서:
# - Ubuntu 22.04 LTS 선택
# - Basic Plan ($6/월 이상 권장)
# - 데이터센터: 가까운 지역 선택 (예: Singapore)
# - SSH 키 등록 또는 비밀번호 설정
```

### 2단계: 서버 접속 및 초기 설정

```bash
# 로컬에서 서버 접속
ssh root@your_server_ip

# 시스템 업데이트
apt update && apt upgrade -y

# Python 및 필수 패키지 설치
apt install -y python3 python3-pip python3-venv git

# 새 사용자 생성 (보안상 root 사용 비권장)
adduser botuser
usermod -aG sudo botuser
su - botuser
```

### 3단계: 프로젝트 업로드

**방법 1: Git 사용 (권장)**
```bash
cd ~
git clone https://github.com/your-username/DealerBot.git
cd DealerBot
```

**방법 2: SCP로 직접 업로드**
```bash
# 로컬 컴퓨터에서 실행
scp -r D:\project\DealerBot botuser@your_server_ip:~/
```

### 4단계: Python 환경 설정

```bash
cd ~/DealerBot

# 가상환경 생성
python3 -m venv venv

# 가상환경 활성화
source venv/bin/activate

# 패키지 설치
pip install --upgrade pip
pip install -r requirements.txt
```

### 5단계: 환경 변수 설정

```bash
# .env 파일 생성
cp .env.example .env
nano .env
```

**`.env` 파일 내용 작성:**
```env
# Discord Bot Token (필수)
DISCORD_TOKEN=여기에_봇_토큰_입력

# 허용된 서버 ID (쉼표로 구분)
MAIN_GUILD_IDS=123456789012345678,987654321098765432

# 환경 설정
ENVIRONMENT=production
DEBUG=False
LOG_LEVEL=INFO

# 서버 제한 설정
ENABLE_GUILD_RESTRICTION=True
AUTO_LEAVE_UNAUTHORIZED=True

# 시스템 기능
ENABLE_EXIT_LOGGER=True
ENABLE_ENHANCED_UPDATES=False
```

**저장 방법:**
- `Ctrl + O` (저장)
- `Enter` (확인)
- `Ctrl + X` (종료)

### 6단계: 봇 테스트 실행

```bash
# 가상환경 활성화 (이미 활성화되어 있으면 생략)
source venv/bin/activate

# 봇 실행
python3 main.py
```

정상 작동 확인 후 `Ctrl + C`로 종료

---

## 🔄 백그라운드 실행 (systemd 사용)

### systemd 서비스 파일 생성

```bash
sudo nano /etc/systemd/system/dealerbot.service
```

**파일 내용:**
```ini
[Unit]
Description=Discord DealerBot
After=network.target

[Service]
Type=simple
User=botuser
WorkingDirectory=/home/botuser/DealerBot
Environment="PATH=/home/botuser/DealerBot/venv/bin"
ExecStart=/home/botuser/DealerBot/venv/bin/python3 main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 서비스 시작 및 활성화

```bash
# systemd 재로드
sudo systemctl daemon-reload

# 서비스 시작
sudo systemctl start dealerbot

# 부팅 시 자동 시작 설정
sudo systemctl enable dealerbot

# 상태 확인
sudo systemctl status dealerbot
```

### 로그 확인

```bash
# 실시간 로그 보기
sudo journalctl -u dealerbot -f

# 최근 로그 보기
sudo journalctl -u dealerbot -n 100

# 프로젝트 로그 파일 확인
tail -f ~/DealerBot/logs/bot.log
```

---

## 🔧 관리 명령어

```bash
# 봇 중지
sudo systemctl stop dealerbot

# 봇 재시작
sudo systemctl restart dealerbot

# 서비스 상태 확인
sudo systemctl status dealerbot

# 서비스 비활성화 (자동 시작 해제)
sudo systemctl disable dealerbot
```

---

## 🔄 코드 업데이트 방법

### Git을 사용하는 경우

```bash
cd ~/DealerBot
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
sudo systemctl restart dealerbot
```

### 수동 업로드의 경우

```bash
# 로컬에서 서버로 파일 업로드
scp -r D:\project\DealerBot\*.py botuser@your_server_ip:~/DealerBot/

# 서버에서 재시작
sudo systemctl restart dealerbot
```

---

## 🛡️ 보안 권장사항

### 1. 방화벽 설정

```bash
# UFW 방화벽 활성화
sudo ufw allow OpenSSH
sudo ufw enable
sudo ufw status
```

### 2. SSH 보안 강화

```bash
# SSH 설정 편집
sudo nano /etc/ssh/sshd_config

# 다음 설정 변경:
# PermitRootLogin no
# PasswordAuthentication no  # SSH 키 사용시만

# SSH 재시작
sudo systemctl restart sshd
```

### 3. 정기 업데이트

```bash
# 시스템 업데이트
sudo apt update && sudo apt upgrade -y

# Python 패키지 업데이트
cd ~/DealerBot
source venv/bin/activate
pip list --outdated
pip install --upgrade discord.py python-dotenv psutil
```

---

## 📊 모니터링

### 리소스 사용량 확인

```bash
# CPU, 메모리 사용량
htop

# 디스크 사용량
df -h

# 봇 프로세스 확인
ps aux | grep python
```

### 로그 로테이션 설정

```bash
sudo nano /etc/logrotate.d/dealerbot
```

**내용:**
```
/home/botuser/DealerBot/logs/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
}
```

---

## ❗ 문제 해결

### 봇이 시작되지 않는 경우

```bash
# 로그 확인
sudo journalctl -u dealerbot -n 50

# 수동 실행으로 에러 확인
cd ~/DealerBot
source venv/bin/activate
python3 main.py
```

### 일반적인 오류

1. **"DISCORD_TOKEN이 설정되지 않았습니다"**
   - `.env` 파일 확인
   - `DISCORD_TOKEN` 값이 제대로 입력되었는지 확인

2. **"discord.py 모듈을 찾을 수 없습니다"**
   ```bash
   source venv/bin/activate
   pip install -r requirements.txt
   ```

3. **권한 오류**
   ```bash
   # 파일 소유권 확인
   ls -la ~/DealerBot

   # 필요시 소유권 변경
   sudo chown -R botuser:botuser ~/DealerBot
   ```

---

## 📞 추가 지원

- Discord Bot 개발자 문서: https://discord.com/developers/docs
- discord.py 문서: https://discordpy.readthedocs.io/
- DigitalOcean 튜토리얼: https://www.digitalocean.com/community/tutorials

---

## ✅ 배포 체크리스트

- [ ] Discord Bot 생성 및 토큰 발급
- [ ] Bot 권한 및 Intents 설정
- [ ] DigitalOcean Droplet 생성
- [ ] Python 및 의존성 설치
- [ ] `.env` 파일 설정
- [ ] 봇 테스트 실행 성공
- [ ] systemd 서비스 등록
- [ ] 자동 시작 활성화
- [ ] 로그 확인
- [ ] 방화벽 및 보안 설정
- [ ] Discord 서버에서 봇 작동 확인

---

**배포 완료! 🎉**