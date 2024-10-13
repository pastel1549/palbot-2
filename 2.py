import discord
import asyncio
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo  # Python 3.9 이상 필요
from discord.ext import commands, tasks
import aiohttp
import re
from bs4 import BeautifulSoup
import socket
import random
import json
import os
import pytz
import time
import openai
import tracemalloc
from random import choices, choice, randint
from discord.ui import Button, View
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from collections import defaultdict
from discord.utils import get
import os
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler  # 이 부분이 중요합니다.


# Steam 프로필 확인하는 함수
async def check_steam_profile(steam_profile_link):
    async with aiohttp.ClientSession() as session:
        async with session.get(steam_profile_link) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                if soup.find(text=re.compile(r'Sorry|Error|This profile is private.')):
                    return False
                else:
                    return True
            elif response.status == 404:
                return False
            else:
                print(f"Steam profile check failed with status code {response.status}")
                return False

# 정규식 패턴으로 Steam 프로필 링크에서 Steam 고유 ID 추출
steam_profile_regex = re.compile(r'^https?://steamcommunity.com/(id|profiles)/([a-zA-Z0-9_-]+)/?$')

# 봇 설정
intents = discord.Intents.default()


class MyView(discord.ui.View):
    def __init__(self, user):
        super().__init__(timeout=3600)  # 1시간(3600초) 후에 뷰가 자동으로 삭제됩니다.
        self.user = user
        self.prizes = ["팰 스피어 50개", "전설 스피어 20개", "케이크 50개", "케이크 20개"]

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        if self.message:
            await self.message.delete()  # 타임아웃 시 메시지를 삭제합니다.

    async def interaction_check(self, interaction) -> bool:
        if interaction.user.id in clicked_users:
            await interaction.response.send_message("이미 참여하셨습니다.", ephemeral=True)
            return False
        else:
            clicked_users.add(interaction.user.id)
            return True

    async def start(self, ctx=None, *, channel=None, wait=False):
        """뷰를 메시지에 첨부합니다."""
        if not self.children:
            raise discord.ClientException('No buttons have been added to the view.')
        
        if self.is_finished():
            raise discord.ClientException('The view has already been stopped.')

        if self.message is not None:
            raise discord.ClientException('View is already attached to a message.')

        # 메시지를 보낼 채널을 결정합니다.
        if channel is None:
            channel = ctx.channel if ctx else None
        if channel is None:
            raise discord.ClientException('Destination channel must be specified for context-less usage.')

        content = getattr(self, '_initial_message_content', None)
        embed = getattr(self, '_initial_embed', None)

        # 뷰를 첨부합니다.
        view_message = await channel.send(content=content, embed=embed, view=self)
        self.message = view_message

        if wait:
            return await self.wait()

    async def select_prize(self):
        selected_prize = random.choice(self.prizes)
        self.prizes.remove(selected_prize)
        return selected_prize

    async def edit_message_content(self, content):
        await self.message.edit(content=content, view=self)

    @discord.ui.button(label='도로롱', style=discord.ButtonStyle.red)
    async def button_a_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.edit_message_content(f"{self.user.mention}님은 꽝입니다.")
        message_content = f"{self.user.mention}님은 꽝입니다."
        
clicked_users = set()  # 이미 버튼을 클릭한 사용자의 ID를 저장하는 집합

# clicked_users 집합을 공유하기 위해 MyView 클래스의 클래스 속성으로 설정합니다.
MyView.clicked_users = clicked_users

async def get_ip_address():
    try:
        # 호스트명을 이용하여 IP 주소 가져오기
        ip_address = socket.gethostbyname(socket.gethostname())
        return ip_address
    except Exception as e:
        print(f"Error getting IP address: {e}")
        return None

async def check_steam_profile(steam_profile_link):
    async with aiohttp.ClientSession() as session:
        async with session.get(steam_profile_link) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                if soup.find(text=re.compile(r'Sorry|Error|No information given')):
                    # 프로필 페이지에 오류 문구가 포함되어 있는 경우
                    return False
                else:
                    # 프로필이 존재하고 오류 문구가 없는 경우
                    return True
            elif response.status == 404:
                # 프로필이 존재하지 않는 경우
                return False
            else:
                # 기타 오류 처리
                print(f"Steam profile check failed with status code {response.status}")
                return False

# 정규식 패턴으로 스팀 프로필 링크에서 스팀 고유 ID 추출
steam_profile_regex = re.compile(r'^https?://steamcommunity.com/(id|profiles)/([a-zA-Z0-9_-]+)/?$')

# 봇 설정
intents = discord.Intents.default()
bot = commands.Bot(command_prefix='!', intents=intents)

# 시간대 설정
KST = pytz.timezone('Asia/Seoul')

# 채널 ID 설정
CHANNEL_ID = 1218196371585368114

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    bot.loop.create_task(scheduled_task())

async def scheduled_task():
    while True:
        # 현재 시각 (KST)
        now = datetime.now(KST)

        # 매주 토요일 오후 8시에 실행
        if now.weekday() == 5 and now.hour == 20:
            await delete_channel_messages()
            await sum_items()
        
        # 월요일 0시에 실행
        if now.weekday() == 0 and now.hour == 0:
            await delete_all_messages()
        
        # 다음 토요일까지 대기
        await wait_until_next_saturday()

async def delete_channel_messages():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        # 이전 채팅 삭제
        await channel.purge(before=datetime.datetime.now(KST).replace(hour=0, minute=0), limit=None)
        print("Deleted all messages on Monday 0:00 KST.")
    else:
        print("Channel not found.")

async def sum_items():
    channel = bot.get_channel(CHANNEL_ID)
    if channel:
        # 합산 로직 실행하여 메모리에 결과 저장
        item_dict = defaultdict(lambda: defaultdict(int))
        async for message in channel.history(limit=100):
            matches = re.findall(r"<@!?(\d+)> (.+)", message.content)
            for match in matches:
                user_id, items = match
                member = await channel.guild.fetch_member(int(user_id))
                if member:  # 멤버 정보가 존재할 경우
                    mention = member.mention
                    item_matches = re.findall(r"(\w+) (\d+)", items)
                    for item_match in item_matches:
                        item, count = item_match
                        item_dict[mention][item] += int(count)

        # 채널의 모든 메시지 삭제
        await channel.purge(limit=None)

        # 합산 결과 메시지 생성
        if item_dict:
            intro_message = "# ========== 이번 시즌 룰렛 아이템 당첨 합산 결과입니다.\n매주 토요일 오후 8시부터 일요일 23시전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가되면,당첨 아이템은 초기화됩니다.** ★경과시 지급 불가!★ **\n\n"
            await channel.send(intro_message)
            
            response = ""
            for mention, items in item_dict.items():
                response += f"{mention} "
                response += " + ".join(f"{item} {count}" for item, count in items.items())
                response += "\n"
            await channel.send(response)
        else:
            await channel.send("합산할 아이템이 없습니다.")
    else:
        print("Channel not found.")

async def wait_until_next_saturday():
    # 현재 시각 (UTC)
    now_utc = datetime.now(pytz.timezone('UTC'))

    # 다음 토요일까지 대기
    days_until_next_saturday = (5 - now_utc.weekday() + 7) % 7
    next_saturday = now_utc + timedelta(days=days_until_next_saturday)
    next_saturday = next_saturday.replace(hour=20, minute=0, second=0, microsecond=0)
    await asyncio.sleep((next_saturday - now_utc).total_seconds())

# 스팀 고유 ID를 저장할 집합
registered_steam_ids = set()
steam_profile_regex = re.compile(r'^https?://steamcommunity.com/(id|profiles)/[a-zA-Z0-9_-]+/?$')

intents = discord.Intents.all()
bot = commands.Bot(command_prefix='!', intents=intents)

TOKEN = 'MTIxMDIzNjUwNzM3MDE2MDE5OQ.G35aAi.D_iAt9OOUqlz8UKkID5KzZ5SaM93_eDdIuf2MI'


RESET_TIME_KST = "00:00"
RESET_INTERVAL = 60
MESSAGE_INTERVAL = 30 * 60

# 스팀 프로필 링크에서 스팀 고유 ID를 추출하기 위한 정규식 패턴
steam_profile_regex = re.compile(r'^https?://steamcommunity.com/(id|profiles)/([a-zA-Z0-9_-]+)/?$')
def extract_steam_id(steam_profile_link):
    match = steam_profile_regex.match(steam_profile_link)
    if match:
        return match.group(2)  # 두 번째 그룹이 스팀 고유 ID에 해당합니다.
    else:
        return None

# 스팀 프로필 링크가 스팀 고유 ID를 포함하는지 확인하는 함수
def is_steam_profile_link(steam_profile_link):
    return steam_profile_regex.match(steam_profile_link) is not None

# 스팀 고유 ID를 GM2 채널로 전송하는 함수
async def send_steam_id_to_gm2(ctx, steam_id):
    gm2_channel = discord.utils.get(ctx.guild.channels, name="gm2")
    if gm2_channel:
        await gm2_channel.send(f"{ctx.author.mention}의 스팀 고유 ID: {steam_id}")
    else:
        print("gm2 채널을 찾을 수 없습니다.")

# 스팀 고유 ID를 추출하는 함수
def extract_steam_id(steam_profile_link):
    match = steam_profile_regex.match(steam_profile_link)
    if match:
        return match.group(2)  # 두 번째 그룹이 스팀 고유 ID에 해당합니다.
    else:
        return None

registered_steam_ids = set()  # registered_steam_ids 변수 정의

async def check_steam_profile(steam_profile_link):
    # 간단히 스팀 프로필 링크를 반환하는 예시
    return steam_profile_link

file_path = 'event_roulette.txt'
# 봇 명령어 접두사 설정 및 intents 설정
intents = discord.Intents.default()  # 기본 intents 가져오기
intents.messages = True  # 메시지 관련 이벤트를 받기 위해
intents.message_content = True  # 메시지 콘텐츠에 접근하기 위해
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)

def load_coupons():
    try:
        with open(file_path, 'r') as file:
            data = file.read()
            # 파일이 비었는지 확인
            if not data:
                return {}  # 파일이 비어 있으면 빈 딕셔너리 반환
            return json.loads(data)
    except FileNotFoundError:
        return {}  # 파일이 없을 경우 빈 딕셔너리 반환
    except json.JSONDecodeError:
        return {} 

def save_coupons(coupons):
    with open(file_path, 'w') as file:
        json.dump(coupons, file)


# 서버점검 진행 메시지 내용 확인
SERVER_CHECK_MESSAGE = "서버점검 : 진행"

@bot.event
async def on_message(message):
    # 봇의 메시지는 무시
    if message.author.bot:
        return
    
    # 💦｜점검보상 채널의 메시지 중 서버점검 진행이 아닌 경우 자동 삭제
    if message.channel.id == GIVEAWAY_CHANNEL_ID:
        # 지정된 메시지 내용이 아닌 경우 삭제
        if message.content.strip() != SERVER_CHECK_MESSAGE:
            try:
                await message.delete()
                print(f"Deleted message from {message.author}: {message.content}")
            except Exception as e:
                print(f"Error deleting message: {e}")
            return

    # 다른 명령어 처리
    await bot.process_commands(message)


@bot.command()
async def 룰렛쿠폰(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return

    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1 이상의 값을 입력해주세요.")
        return

    coupons = load_coupons()
    coupons[member.display_name] = coupons.get(member.display_name, 0) + count
    save_coupons(coupons)
    await ctx.send(f"**{member.mention}님**, 이벤트 룰렛 쿠폰이 **{count}장** 지급되었습니다. \nhttps://discord.com/channels/1208238905896345620/1226495859622019122 채널에서 !룰렛을 입력해주세요. [현재 보유 중인 쿠폰 : **{coupons[member.display_name]}**개]")

@tasks.loop(seconds=60)
async def scheduled_messages():
    now = datetime.datetime.now(ZoneInfo("Asia/Seoul"))
    print(f"현재 시간: {now.strftime('%Y-%m-%d %H:%M:%S')}, 스케줄러 실행 중...")

@bot.event
async def on_message(message):
    if message.author.bot:
        return  # 봇이 보낸 메시지인 경우 무시합니다.

    if isinstance(message.channel, discord.DMChannel):
        content = message.content.strip()
        if not content.startswith("!인증") or not is_steam_profile_link(content[len("!인증"):].strip()):
            await message.channel.send("올바른 스팀 프로필 링크를 입력해주세요. 형식: `!인증(스페이스바 공백)스팀프로필링크-> !인증 스팀프로필링크`")
        return  # DM 채널에서는 추가적인 처리 없이 종료합니다.

    if is_steam_verification_channel(message.channel):
        content = message.content.strip()
        if not content.startswith("!인증") or not is_steam_profile_link(content[len("!인증"):].strip()):
            await message.channel.send("올바른 스팀 프로필 링크를 입력해주세요. 형식: `!인증(스페이스바 공백)스팀프로필링크-> !인증 스팀프로필링크`")
            return  # 메시지가 보내졌으므로 여기서 종료합니다.
    
    await bot.process_commands(message)


def is_steam_verification_channel(channel):
    return channel.name == "🎟｜스팀인증"
pp_info_links = {
    "하루": "1213172621928300645",
    "안보여": "1213172628274020432",
    "아저씨": "1213172631440719942",
    "마담파니": "1213172634636910602",
    "흑사과": "1213172636876677190",
    "반달곰": "1213172644674015303",
    "SINSIA": "1213172652299132928",
    "수다월드": "1213172655755370636",
    "형반이": "1213172659911655506",
    "새봄여름": "1213172663124631583",  
    "진돗개": "1213172666991771658",
    "비비": "1213172670775173242",
    "혁": "1213172674499575889",
    "개동": "1213172678161072148",
    "헤롱": "1213172681630027856",
    "캐시": "1213172685857628201", 
    "멍멍이": "1213172690874011748",
    "별손": "1213172694036647957",
    "카이": "1213172699908800552",
    "춘식이": "1217811521665765397",
    "오뚜기": "1213172704006381640",
    "찹찹": "1217811539751604254",
    "하마": "1217811543505371196",
    "진부한": "1217811535892713532",
    "도도": "1217811553663979572",
    "유월": "1217811557191520307",
    "원붕어": "1217811560123207764",
    "Noglin": "1217811563029860372",
    "두더지": "1236512443283537941",
    "리무르": "1238723132383170612",
    "반달": "1238723129900007546",
    "미니": "1238723131246514176",
    "대롱": "1238723134320939119",
}

# 메시지 발송 함수
async def send_pp_info(ctx, user_query, message_id):
    target_channel_id = 1213171694278021141  # PP 정보가 등록된 채널 ID
    channel = bot.get_channel(target_channel_id)
    
    try:
        message = await channel.fetch_message(message_id)
        kst_now = datetime.now(ZoneInfo('Asia/Seoul'))
        dm_message = await ctx.author.send(f"{user_query}님의 **[{kst_now.strftime('%m월 %d일 %H시 %M분')}]** 기준 PP 정보를 안내드립니다.\n{message.content}")
        await ctx.message.delete()

        kst_now = datetime.now(ZoneInfo('Asia/Seoul'))
        response_msg = f"{ctx.author.mention}님께서, {kst_now.strftime('%m월 %d일 %H시 %M분')}에 **{user_query}**님의 PP 정보를 요청하셨습니다."
        
        if dm_message:
            response_msg += "\nDM으로 PP 정보를 발송하였습니다."
        else:
            response_msg += "\nDM으로 PP 정보를 발송하는데 실패하였습니다."
        
        await ctx.send(response_msg)

    except Exception as e:
        print(f"PP 정보 조회 중 오류 발생: {e}")
        await ctx.send("PP 정보 조회 중 오류가 발생했습니다.")



@bot.command()
@commands.has_permissions(administrator=True)
async def 이벤트(ctx):
    await ctx.message.delete()
    view = MyView(ctx.author)
    message = await ctx.send("#PASTEL WORLD! RANDOM 이벤트! 버튼 중 하나를 선택해주세요:", view=view)
    view.message = message  # MyView 인스턴스에 메시지 참조를 저장합니다.
    
@이벤트.error
async def 이벤트_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")

@bot.command()
@commands.has_permissions(administrator=True)
async def 이벤트초기화(ctx):
    global clicked_users
    clicked_users.clear()
    await ctx.send("이벤트 참여 기록이 초기화되었습니다.")

@tasks.loop(hours=24)  # 매일 0시에 실행되도록 설정
async def daily_reset():
    now_kst = datetime.now(ZoneInfo('Asia/Seoul'))  # 현재 시간 가져오기
    if now.hour == 0 and now.minute == 0:  # 현재 시간이 0시 0분이면
        # 여기에 초기화 작업을 추가합니다.
        await reset_daily_counts()  # 예를 들어, 매일 카운트 초기화 함수를 호출

async def reset_daily_counts():
    # 매일 카운트 초기화 작업을 여기에 구현합니다.
    # 파일을 열어서 기록을 초기화하거나 데이터베이스에서 값을 업데이트하는 등의 작업을 수행합니다.
    pass  # 이 예시에서는 아무 작업도 수행하지 않습니다.

# 봇이 시작될 때 daily_reset 함수를 시작합니다.



# 봇이 준비되면 루프 시작
@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    daily_reset.start()



# 봇 기본 설정
intents = discord.Intents.default()  # 기본 intents 가져오기
intents.messages = True  # 메시지 관련 이벤트를 받기 위해
intents.message_content = True  # 메시지 콘텐츠에 접근하기 위해
intents.members = True
intents.guilds = True
bot = commands.Bot(command_prefix='!', intents=intents)

# 보상 신청자 목록 초기화
reward_applicants = []
file_path = 'coupon_inventory.txt'  # 파일 경로를 먼저 정의합니다.

# 보상 쿠폰 불러오기 함수
def load_coupons():
    try:
        with open(file_path, 'r') as file:
            data = file.read()
            # 파일이 비었는지 확인
            if not data:
                return {}  # 파일이 비어 있으면 빈 딕셔너리 반환
            return json.loads(data)
    except FileNotFoundError:
        return {}  # 파일이 없을 경우 빈 딕셔너리 반환
    except json.JSONDecodeError:
        return {}

# 보상 쿠폰 저장하기 함수
def save_coupons(coupons):
    with open(file_path, 'w') as file:
        json.dump(coupons, file)

# 룰렛쿠폰 명령어 구현
@bot.command()
async def 룰렛쿠폰(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return

    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1 이상의 값을 입력해주세요.")
        return

    coupons = load_coupons()
    coupons[member.display_name] = coupons.get(member.display_name, 0) + count
    save_coupons(coupons)
    await ctx.send(f"**{member.mention}님**, 이벤트 룰렛 쿠폰이 **{count}장** 지급되었습니다. https://discord.com/channels/1208238905896345620/1226495859622019122 채널에서 !룰렛을 입력해주세요. [현재 보유 중인 쿠폰 : **{coupons[member.display_name]}**개]")

@bot.command()
async def 룰렛(ctx):
    member = ctx.author
    nickname = member.display_name
    coupons = load_coupons()
    if nickname not in coupons or coupons[nickname] <= 0:
        await ctx.send(f"{member.mention}님은 보유하고 있는 쿠폰이 없습니다.")
        return

    probabilities = [80, 12, 7, 1]
    prizes = [
        [('금속주괴', 2, 5), ('케이크', 1, 2), ('골드', 100, 500)],
        [('금속주괴', 3, 6), ('케이크', 2, 3), ('골드', 500, 1000)],
        [('금속주괴', 4, 7), ('케이크', 3, 4), ('골드', 1000, 2000)],
        [('금속주괴', 5, 8), ('케이크', 4, 5), ('골드', 2000, 3000)]
    ]

    selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
    selected_prize_info = choice(selected_prize_category)
    selected_prize, min_qty, max_qty = selected_prize_info
    qty = randint(min_qty, max_qty)

    coupons[nickname] -= 1
    save_coupons(coupons)

    # await ctx.send(f"{member.mention} {selected_prize} {qty}개 당첨되었습니다. (남은 기회: {coupons[nickname]}회)")
    await ctx.send(f"{member.mention} {selected_prize} {qty}")
    winning_channel = discord.utils.get(ctx.guild.channels, name="💞｜당첨내역")
    if winning_channel:
        now_kst = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%Y-%m-%d %H:%M:%S")
        await winning_channel.send(f"{member.mention} [이벤] {selected_prize} {qty}")
            

file_path = 'coupon_inventory.txt'

# 보상 쿠폰 불러오기 함수
def load_coupons():
    try:
        with open(file_path, 'r') as file:
            data = file.read()
            # 파일이 비었는지 확인
            if not data:
                return {}  # 파일이 비어 있으면 빈 딕셔너리 반환
            return json.loads(data)
    except FileNotFoundError:
        return {}  # 파일이 없을 경우 빈 딕셔너리 반환
    except json.JSONDecodeError:
        return {}

# 보상 쿠폰 저장하기 함수
def save_coupons(coupons):
    with open(file_path, 'w') as file:
        json.dump(coupons, file)

@bot.command()
async def 점검보상(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return
    global reward_applicants
    reward_applicants = []
    await ctx.message.delete()

    current_time = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%Y년 %m월 %d일 %H시 %M분")

    await ctx.send("# 안녕하세요 PASTEL WORLD 유저 여러분 점검 보상 관련이 준비되었습니다.")
    await ctx.send(f"## [{current_time}] 보상으로 인한 대박 룰렛쿠폰 3장이 지급 될 예정입니다.")
    await ctx.send("# 주의사항")
    await ctx.send("- **디스코드 닉네임**과 **게임 닉네임**은 동일하여야 합니다.\n"
                   "- 점검 **보상은 서버 오픈 후 30분 이내 접속을 하신 분께만** 지급됩니다.\n"
                   "- 보상은 해당 **메시지가 등록된 후 10분까지만 신청 가능**합니다.\n"
                   "- 보상 신청 방법은 해당 채널에 "
                   "정확히 **보상신청** 이라는 메시지를 입력 부탁드립니다.")

    await asyncio.sleep(600)
    async for msg in ctx.channel.history(limit=None):
        await msg.delete()
    await ctx.send("## ======== 신청이 마감되었습니다. 이후 신청하신 분은 지급 대상이 되지 않습니다. ========")

    # 대상자에게 룰렛쿠폰 지급 로직 추가
    for member in reward_applicants:
        coupons = load_coupons()
        coupons[member.display_name] = coupons.get(member.display_name, 0) + 1
        save_coupons(coupons)
        await ctx.send(f"{member.mention}님, **점검 보상** 대박룰렛 쿠폰 **3장** 지급되었습니다. https://discord.com/channels/1208238905896345620/1226495859622019122 채널에서 !대박룰렛을 입력해주세요. **[현재 보유 중인 쿠폰 : {coupons[member.display_name]}개]")

    await asyncio.sleep(600)
    async for msg in ctx.channel.history(limit=None):
        await msg.delete()
    # 신청자 목록 초기화
    reward_applicants = []

    # 신청자가 있는지 확인하고 메시지 전송
    if reward_applicants:
        await ctx.send(" # - 완료 -")

def choose_prize(prize_configurations):
    # 랜덤 숫자 생성
    random_number = random.uniform(0, 100)
    cumulative = 0
    
    # 누적 확률을 사용하여 등급 결정
    for config in prize_configurations:
        cumulative += config["cumulative_probability"]
        if random_number <= cumulative:
            # 선택된 등급 내에서 아이템 선택
            items = config["items"]
            selected_item = random.choice(items)
            item_name = list(selected_item.keys())[0]
            quantity_range = selected_item[item_name]["quantity"]
            quantity = random.randint(quantity_range[0], quantity_range[1])
            return f"{item_name} {quantity}"

async def process_roulette(ctx, role_name, prizes, max_attempts):
    user = ctx.author
    today = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%Y-%m-%d")
    filename = f"{role_name.upper()}_{today}.txt"

    if not os.path.exists(filename):
        with open(filename, "w"):
            pass

    with open(filename, "r+") as file:
        lines = file.readlines()
        user_line = next((line for line in lines if user.name in line), None)

        if user_line:
            _, _, remaining = user_line.strip().split(" / ")
            remaining = int(remaining)
        else:
            remaining = max_attempts

        if remaining <= 0:
            await ctx.send(f"{today} {user.mention}, 오늘 사용 가능한 횟수를 모두 소진하였습니다.")
            return

        # 확률 계산을 위한 변수 설정
        probabilities = [prize["cumulative_probability"] for prize in prizes]
        total_probability = sum(probabilities)

        # 확률에 따라 아이템 선택
        random_number = random.uniform(0, total_probability)
        cumulative_probability = 0
        chosen_prize = None
        for prize, probability in zip(prizes, probabilities):
            cumulative_probability += probability
            if random_number <= cumulative_probability:
                chosen_prize = prize
                break

        remaining -= 1
        timestamp = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H:%M:%S")
        new_line = f"{user.name} / {timestamp} / {remaining}\n"

        if user_line:
            lines[lines.index(user_line)] = new_line
        else:
            lines.append(new_line)

        file.seek(0)
        file.writelines(lines)
        file.truncate()

    chosen_prize_result = choose_prize(prizes)  # choose_prize 함수를 한 번만 호출

    await ctx.send(f"# [{role_name.upper()}룰렛] - {user.mention}, 축하합니다! \n ## {chosen_prize_result}개 에 당첨되었습니다. (남은 기회: {remaining}회)\n매주 토요일 오후 8시부터 일요일 23시전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가되면,당첨 아이템은 초기화됩니다.** ★경과시 지급 불가!★ **")
    
    winnings_channel = discord.utils.get(ctx.guild.channels, name="💞｜당첨내역")
    if winnings_channel:
        await winnings_channel.send(f"{user.mention} {chosen_prize_result}")
    else:
        print("💞｜당첨내업 채널을 찾을 수 없습니다.")

# 데이터 관리 함수 수정
def load_user_data(member_id):
    file_name = f"RED_{member_id}.json"
    try:
        with open(file_name, "r") as file:
            data = json.load(file)
    except FileNotFoundError:
        data = {"attempts": 0, "event_pp": 0}
    
    return data

def save_user_data(member_id, data):
    file_name = f"RED_{member_id}.json"
    with open(file_name, "w") as file:
        json.dump(data, file, indent=4)
        
# red_roulette_usage 초기화 예시
def initialize_red_roulette_usage():
    global red_roulette_usage
    # 어떤 방식으로든 사용자 정보를 초기화합니다.
    red_roulette_usage = {}
    # 혹은 필요에 따라 사용자 정보를 불러올 때 초기화할 수 있습니다.

# 초기화 함수 호출
initialize_red_roulette_usage()


def load_red_usage():
    red_usage = {}
    today = datetime.utcnow().date()
    filename = f"RED_{today}.txt"
    
    if os.path.exists(filename):
        with open(filename, "r") as f:
            for line in f:
                member_id, count = line.strip().split(",")
                red_usage[member_id] = {"count": int(count), "date": today}
    
    return red_usage

def save_red_usage(red_usage):
    today = datetime.utcnow().date()
    filename = f"RED_{today}.txt"
    
    with open(filename, "w") as f:
        for member_id, data in red_usage.items():
            f.write(f"{member_id},{data['count']}\n")

    print(f"Saved RED usage data to {filename}")

def increment_red_count(member_id):
    red_usage = load_red_usage()
    today = datetime.utcnow().date()
    
    if member_id in red_usage and red_usage[member_id]["date"] == today:
        red_usage[member_id]["count"] += 1
    else:
        red_usage[member_id] = {"count": 1, "date": today}
    
    save_red_usage(red_usage)
    
    return red_usage[member_id]["count"]

def reset_red_usage():
    today = datetime.utcnow().date()
    filename = f"RED_{today}.txt"
    
    if os.path.exists(filename):
        os.remove(filename)
        print(f"Reset RED usage data for {today}")



# 레드룰렛 보상 설정
red_roulette_configurations = {
    "Red": [
        {
            "cumulative_probability": 50,  # 50% 확률
            "items": [
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 마그마드라고[궁극]의석판": {"quantity": [1, 1]}},
                {"[레드] 벨르누아르의석판": {"quantity": [1, 1]}},
                {"[레드] 마그마드라고의석판": {"quantity": [1, 1]}}
            ]
        },
        {
            "cumulative_probability": 40,  # 40% 확률
            "items": [
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 마그마드라고[궁극]의석판": {"quantity": [1, 1]}},
                {"[레드] 벨르누아르의석판": {"quantity": [1, 1]}},
                {"[레드] 마그마드라고의석판": {"quantity": [1, 1]}}
            ]
        },
        {
            "cumulative_probability": 9,   # 9% 확률
            "items": [
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 마그마드라고[궁극]의석판": {"quantity": [1, 1]}},
                {"[레드] 벨르누아르의석판": {"quantity": [1, 1]}},
                {"[레드] 마그마드라고의석판": {"quantity": [1, 1]}}
            ]
        },
        {
            "cumulative_probability": 1,   # 1% 확률
            "items": [
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 플라스틸": {"quantity": [1, 3]}},
                {"[레드] 원유": {"quantity": [1, 2]}},  
                {"[레드] 도그코인": {"quantity": [1, 2]}},
                {"[레드] 카본섬유": {"quantity": [1, 2]}},
                {"[레드] 팰금속주괴": {"quantity": [1, 10]}},
                {"[레드] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(L)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(M)": {"quantity": [1, 2]}},
                {"[레드] 수련의서(S)": {"quantity": [1, 2]}},
                {"[레드] 운석파편": {"quantity": [1, 2]}},
                {"[레드] 얼티밋스피어": {"quantity": [1, 3]}},
                {"[레드] 마그마드라고[궁극]의석판": {"quantity": [1, 1]}},
                {"[레드] 벨르누아르의석판": {"quantity": [1, 1]}},
                {"[레드] 마그마드라고의석판": {"quantity": [1, 1]}}
            ]
        }
    ]
}

# 이용 가능한 명령어 사용 횟수를 저장할 딕셔너리
red_roulette_usage = {}

@bot.command(name="레드룰렛")
async def red_roulette(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    
    # 레드 등급 확인
    if "Red" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Red 등급만 사용할 수 있습니다.")
        return
    
    member_id = str(ctx.author.id)
    
    # 사용 가능 횟수 증가 및 남은 횟수 확인
    count = increment_red_count(member_id)
    if count > 3:
        await ctx.send("하루 사용 가능한 횟수를 모두 사용하셨습니다.")
        return
    
    user_data = load_user_data(member_id)
    if "attempts" not in user_data:
        user_data["attempts"] = 0
    
    max_attempts = 2
    rewards = []
    event_pp_awarded = False  # 이벤트 PP 지급 여부 확인을 위한 변수
    
    for _ in range(max_attempts):
        prize = spin_red_roulette(red_roulette_configurations["Red"])
        rewards.extend(prize)
        user_data["attempts"] += 1
        
        # 보상 처리 및 이벤트 PP 지급
        for item in prize:
            item_name = list(item.keys())[0]
            quantity = random.randint(item[item_name]["quantity"][0], item[item_name]["quantity"][1])
            
            # 무조건 이벤트 PP 지급
            if item_name == "[레드] ★PP★":
                event_pp = random.randint(100, 500)
                user_data["event_pp"] += event_pp
                event_pp_awarded = True
    
    save_user_data(member_id, user_data)
    
    # 보상 embed 메시지 생성
    embed = discord.Embed(title="🎉 축하합니다!", description=f"{ctx.author.mention}님께서 레드룰렛을 통해 다음과 같은 보상을 받았습니다:", color=discord.Color.gold())
    embed.set_author(name="레드룰렛 결과", icon_url=ctx.guild.icon.url)  # icon_url 수정
    
    # 사용자의 아바타 설정
    if ctx.author.avatar:
        embed.set_thumbnail(url=ctx.author.avatar.url)
    else:
        embed.set_thumbnail(url=ctx.author.default_avatar.url)
    
    # 랜덤으로 2개 아이템 선택
    selected_rewards = random.sample(rewards, min(2, len(rewards)))
    
    # 이미 선택된 보상의 이름을 저장하는 리스트
    selected_names = []
    
    for idx, prize in enumerate(selected_rewards):
        item_name = list(prize.keys())[0]
        
        # 이미 선택된 보상의 이름인 경우, 다시 선택
        while item_name in selected_names:
            prize = spin_red_roulette(red_roulette_configurations["Red"])
            item_name = list(prize.keys())[0]
        
        selected_names.append(item_name)
        
        quantity = random.randint(prize[item_name]["quantity"][0], prize[item_name]["quantity"][1])
        embed.add_field(name=f"[{idx+1}번 보상]", value=f"{item_name}: {quantity}", inline=False)
    
    # 이벤트 PP 지급 내역 추가
    if event_pp_awarded:
        event_pp_amount = user_data["event_pp"]
        embed.add_field(name="[이벤트 PP]", value=f"{event_pp_amount}", inline=False)
        
        # 사용자 데이터에도 이벤트 PP 추가
        data = load_data()
        if member_id in data:
            data[member_id]["이벤트 PP"] += event_pp_amount
            save_data(data)
        else:
            await ctx.send("사용자 데이터를 찾을 수 없습니다.")
    
    # 메시지 보내기
    await ctx.send(embed=embed)
    
    # 당첨내역 채널에 개별 메시지 발송
    winning_channel = discord.utils.get(ctx.guild.channels, name="💞｜당첨내역")
    if winning_channel:
        for prize in selected_rewards:
            item_name = list(prize.keys())[0]
            quantity = random.randint(prize[item_name]["quantity"][0], prize[item_name]["quantity"][1])
            await winning_channel.send(f"{ctx.author.mention} [레드] {item_name} {quantity}개")
    else:
        await ctx.send("💞｜당첨내역 채널을 찾을 수 없습니다.")
    
    # 사용 가능한 횟수 남은 횟수 메시지 발송
    remaining_attempts = 3 - count
    await ctx.send(f"오늘 레드룰렛 사용 가능 횟수: {remaining_attempts}번")


# 레드룰렛 보상 선택 함수
def spin_red_roulette(configuration):
    rand_num = random.randint(1, 100)
    cumulative_probability = 0
    
    for option in configuration:
        cumulative_probability += option["cumulative_probability"]
        if rand_num <= cumulative_probability:
            return option["items"]
    
    return []


# 각 등급별 확률 및 아이템 설정
prize_configurations = {
    "Black": [
        {
            "cumulative_probability": 70,  # 70% 확률
            "items": [
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 이벤트pp": {"quantity": [100, 300]}},
                {"[블랙] 얼티밋스피어": {"quantity": [1, 3]}}
            ]
        },
        {
            "cumulative_probability": 22,  # 22% 확률
            "items": [
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 이벤트pp": {"quantity": [100, 300]}},
                {"[블랙] 얼티밋스피어": {"quantity": [1, 3]}}
            ]
        },
        {
            "cumulative_probability": 7,   # 7% 확률
            "items": [
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 이벤트pp": {"quantity": [100, 300]}},
                {"[블랙] 얼티밋스피어": {"quantity": [1, 3]}}
            ]
        },
        {
            "cumulative_probability": 1,   # 1% 확률
            "items": [
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 원유": {"quantity": [1, 10]}},  
                {"[블랙] 도그코인": {"quantity": [1, 3]}},
                {"[블랙] 카본섬유": {"quantity": [1, 2]}},
                {"[블랙] 팰금속주괴": {"quantity": [1, 10]}},
                {"[블랙] 금속주괴": {"quantity": [1, 5]}},
                {"[블랙] 케이크": {"quantity": [1, 5]}},  
                {"[블랙] 골드": {"quantity": [100, 300]}},
                {"[블랙] 수련의서(XL)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(L)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(M)": {"quantity": [1, 2]}},
                {"[블랙] 수련의서(S)": {"quantity": [1, 2]}},
                {"[블랙] 운석파편": {"quantity": [1, 2]}},
                {"[블랙] 이벤트pp": {"quantity": [100, 300]}},
                {"[블랙] 얼티밋스피어": {"quantity": [1, 3]}}
            ]
        }
    ],
    "Orange": [
        {
            "cumulative_probability": 70,  # 70% 확률
            "items": [
                {"[오렌] 금속주괴": {"quantity": [1, 5]}},
                {"[오렌] 케이크": {"quantity": [1, 5]}},  
                {"[오렌] 골드": {"quantity": [500, 1000]}},
                {"[오렌] 메가스피어": {"quantity": [1, 10]}},
                {"[오렌] 기가스피어": {"quantity": [1, 10]}},
                {"[오렌] 테라스피어": {"quantity": [1, 10]}},
                {"[오렌] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 22,  # 22% 확률
            "items": [
                {"[오렌] 금속주괴": {"quantity": [1, 5]}},
                {"[오렌] 케이크": {"quantity": [1, 5]}},  
                {"[오렌] 골드": {"quantity": [500, 1000]}},
                {"[오렌] 메가스피어": {"quantity": [1, 10]}},
                {"[오렌] 기가스피어": {"quantity": [1, 10]}},
                {"[오렌] 테라스피어": {"quantity": [1, 10]}},
                {"[오렌] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 7,   # 7% 확률
            "items": [
                {"[오렌] 금속주괴": {"quantity": [1, 5]}},
                {"[오렌] 케이크": {"quantity": [1, 5]}},  
                {"[오렌] 골드": {"quantity": [500, 1000]}},
                {"[오렌] 메가스피어": {"quantity": [1, 10]}},
                {"[오렌] 기가스피어": {"quantity": [1, 10]}},
                {"[오렌] 테라스피어": {"quantity": [1, 10]}},
                {"[오렌] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 1,   # 1% 확률
            "items": [
                {"[오렌] 아누비스": {"quantity": [1, 1]}},
                {"[오렌] 켄타나이트": {"quantity": [1, 1]}},
                {"[오렌] 제트래곤": {"quantity": [1, 1]}},
                {"[오렌] 라바드래곤": {"quantity": [1, 1]}},
                {"[오렌] ★PP★": {"quantity": [1, 100]}},
                {"[오렌] 팔라디우스": {"quantity": [1, 1]}}
            ]
        }
    ],
    "Yellow": [
        {
            "cumulative_probability": 70,  # 70% 확률
            "items": [
                {"[옐로] 금속주괴": {"quantity": [1, 5]}},
                {"[옐로] 케이크": {"quantity": [1, 5]}},  
                {"[옐로] 골드": {"quantity": [500, 1000]}},
                {"[옐로] 메가스피어": {"quantity": [1, 10]}},
                {"[옐로] 기가스피어": {"quantity": [1, 10]}},
                {"[옐로] 테라스피어": {"quantity": [1, 10]}},
                {"[옐로] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 22,  # 22% 확률
            "items": [
                {"[옐로] 금속주괴": {"quantity": [1, 5]}},
                {"[옐로] 케이크": {"quantity": [1, 5]}},  
                {"[옐로] 골드": {"quantity": [500, 1000]}},
                {"[옐로] 메가스피어": {"quantity": [1, 10]}},
                {"[옐로] 기가스피어": {"quantity": [1, 10]}},
                {"[옐로] 테라스피어": {"quantity": [1, 10]}},
                {"[옐로] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 7,   # 7% 확률
            "items": [
                {"[옐로] 금속주괴": {"quantity": [1, 5]}},
                {"[옐로] 케이크": {"quantity": [1, 5]}},  
                {"[옐로] 골드": {"quantity": [500, 1000]}},
                {"[옐로] 메가스피어": {"quantity": [1, 10]}},
                {"[옐로] 기가스피어": {"quantity": [1, 10]}},
                {"[옐로] 테라스피어": {"quantity": [1, 10]}},
                {"[옐로] 전설스피어": {"quantity": [1, 10]}}
            ]
        },
        {
            "cumulative_probability": 1,   # 1% 확률
            "items": [
                {"[옐로] 아누비스": {"quantity": [1, 1]}},
                {"[옐로] 켄타나이트": {"quantity": [1, 1]}},
                {"[옐로] 제트래곤": {"quantity": [1, 1]}},
                {"[옐로] 라바드래곤": {"quantity": [1, 1]}},
                {"[옐로] ★PP★": {"quantity": [1, 1]}},
                {"[옐로] 팔라디우스": {"quantity": [1, 1]}}
            ]
        }
    ],
    "Green": [
    {
        "cumulative_probability": 70,  # 70% 확률
        "items": [
            {"[그린] 금속주괴": {"quantity": [1, 5]}},
            {"[그린] 케이크": {"quantity": [1, 5]}},
            {"[그린] 골드": {"quantity": [500, 1000]}},
            {"[그린] 메가스피어": {"quantity": [1, 3]}},
            {"[그린] 기가스피어": {"quantity": [1, 3]}},
            {"[그린] 테라스피어": {"quantity": [1, 3]}},
            {"[그린] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 22,  # 22% 확률
        "items": [
            {"[그린] 금속주괴": {"quantity": [1, 5]}},
            {"[그린] 케이크": {"quantity": [1, 5]}},
            {"[그린] 골드": {"quantity": [500, 1000]}},
            {"[그린] 메가스피어": {"quantity": [1, 3]}},
            {"[그린] 기가스피어": {"quantity": [1, 3]}},
            {"[그린] 테라스피어": {"quantity": [1, 3]}},
            {"[그린] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 7,   # 7% 확률
        "items": [
            {"[그린] 금속주괴": {"quantity": [1, 5]}},
            {"[그린] 케이크": {"quantity": [1, 5]}},
            {"[그린] 골드": {"quantity": [500, 1000]}},
            {"[그린] 메가스피어": {"quantity": [1, 3]}},
            {"[그린] 기가스피어": {"quantity": [1, 3]}},
            {"[그린] 테라스피어": {"quantity": [1, 3]}},
            {"[그린] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 1,   # 1% 확률
        "items": [
            {"[그린] 꽝": {"quantity": [1, 1]}}
            ]
        }
    ],
    "Blue": [
    {
        "cumulative_probability": 70,  # 70% 확률
        "items": [
            {"[블루] 금속주괴": {"quantity": [1, 5]}},
            {"[블루] 케이크": {"quantity": [1, 5]}},
            {"[블루] 골드": {"quantity": [500, 1000]}},
            {"[블루] 메가스피어": {"quantity": [1, 3]}},
            {"[블루] 기가스피어": {"quantity": [1, 3]}},
            {"[블루] 테라스피어": {"quantity": [1, 3]}},
            {"[블루] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 22,  # 22% 확률
        "items": [
            {"[블루] 금속주괴": {"quantity": [1, 5]}},
            {"[블루] 케이크": {"quantity": [1, 5]}},
            {"[블루] 골드": {"quantity": [500, 1000]}},
            {"[블루] 메가스피어": {"quantity": [1, 3]}},
            {"[블루] 기가스피어": {"quantity": [1, 3]}},
            {"[블루] 테라스피어": {"quantity": [1, 3]}},
            {"[블루] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 7,   # 7% 확률
        "items": [
            {"[블루] 금속주괴": {"quantity": [1, 5]}},
            {"[블루] 케이크": {"quantity": [1, 5]}},
            {"[블루] 골드": {"quantity": [500, 1000]}},
            {"[블루] 메가스피어": {"quantity": [1, 3]}},
            {"[블루] 기가스피어": {"quantity": [1, 3]}},
            {"[블루] 테라스피어": {"quantity": [1, 3]}},
            {"[블루] 전설스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 1,   # 1% 확률
        "items": [
            {"[블루]아누비스": {"quantity": [1, 1]}},
            {"[블루] 켄타나이트": {"quantity": [1, 1]}},
            {"[블루] 제트래곤": {"quantity": [1, 1]}},
            {"[블루] 팔라디우스": {"quantity": [1, 1]}}
            ]
        }
    ],
    "Purple": [
    {
        "cumulative_probability": 70,  # 70% 확률
        "items": [
            {"[퍼플] 금속주괴": {"quantity": [1, 3]}},
            {"[퍼플] 케이크": {"quantity": [1, 3]}},
            {"[퍼플] 골드": {"quantity": [500, 1000]}},
            {"[퍼플] 팰스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 22,  # 22% 확률
        "items": [
            {"[퍼플] 금속주괴": {"quantity": [1, 3]}},
            {"[퍼플] 케이크": {"quantity": [1, 3]}},
            {"[퍼플] 골드": {"quantity": [500, 1000]}},
            {"[퍼플] 팰스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 7,   # 7% 확률
        "items": [
            {"[퍼플] 금속주괴": {"quantity": [1, 3]}},
            {"[퍼플] 케이크": {"quantity": [1, 3]}},
            {"[퍼플] 골드": {"quantity": [500, 1000]}},
            {"[퍼플] 팰스피어": {"quantity": [1, 3]}}
        ]
    },
    {
        "cumulative_probability": 1,   # 1% 확률
        "items": [
            {"[퍼플] 꽝": {"quantity": [1, 1]}}
        ]
    }
]
}
# 각 등급별 최대 사용 횟수 설정
max_attempts_by_role = {
    "Black": 3,
    "Orange": 3,
    "Yellow": 2,
    "Green": 2,
    "Blue": 2,
    "Purple": 1
}

# 서버점검 진행 메시지 내용 확인
SERVER_CHECK_MESSAGE = "서버점검 : 진행"

# 룰렛 명령어 등록
@bot.command()
async def 블랙룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Black" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Black 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Black", prize_configurations["Black"], max_attempts_by_role["Black"])

@bot.command()
async def 오렌지룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Orange" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Orange 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Orange", prize_configurations["Orange"], max_attempts_by_role["Orange"])

@bot.command()
async def 옐로우룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Yellow" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Purple 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Yellow", prize_configurations["Yellow"], max_attempts_by_role["Yellow"])

@bot.command()
async def 그린룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Green" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Green 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Green", prize_configurations["Green"], max_attempts_by_role["Green"])

@bot.command()
async def 블루룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Blue" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Blue 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Blue", prize_configurations["Blue"], max_attempts_by_role["Blue"])

@bot.command()
async def 퍼플룰렛(ctx):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return
    if "Purple" not in [role.name for role in ctx.author.roles]:
        await ctx.send("이 명령어는 Purple 등급만 사용할 수 있습니다.")
        return
    await process_roulette(ctx, "Purple", prize_configurations["Purple"], max_attempts_by_role["Purple"])

@bot.event
async def on_message(message):
    # 봇의 메시지는 무시
    if message.author.bot:
        return
    
    # 💦｜점검보상 채널의 메시지 중 서버점검 진행이 아닌 경우 자동 삭제
    if message.channel.id == GIVEAWAY_CHANNEL_ID:
        # 지정된 메시지 내용이 아닌 경우 삭제
        if message.content.strip() != SERVER_CHECK_MESSAGE:
            try:
                await message.delete()
                print(f"Deleted message from {message.author}: {message.content}")
            except Exception as e:
                print(f"Error deleting message: {e}")
            return

    await bot.process_commands(message)

    # 채널 이름이 '당첨내역'이고 메시지 내용이 '사용 가능한 쿠폰이 없습니다.'인 경우
    if message.channel.name == '💞｜당첨내역' and ('가능한' in message.content or '쿠폰' in message.content):
        await message.delete()


GUILD_ID = '1208238905896345620'  # 서버 ID
ATTENDANCE_FILE = 'user_attendance.json'
PRIZE_CHANNEL_ID = 1218196371585368114  # 당첨내역 채널 ID (예시)

# 출석 체크와 등급에 따른 PP 범위 설정
GRADE_RANGES = {
    'Red': (50, 300),
    'Black': (50, 250),
    'Orange': (10, 150),
    'Yellow': (5, 100),
    'Green': (0, 100),
}

def load_attendance_data():
    try:
        with open(ATTENDANCE_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        # Create a new file with default data
        default_data = {}
        save_attendance_data(default_data)
        return default_data

def save_attendance_data(data):
    with open(ATTENDANCE_FILE, 'w') as file:
        json.dump(data, file, indent=4)


# 데이터 저장 파일 경로
DATA_FILE = 'color.json'

# 유저 등급과 포인트 범위 정의
POINTS = {
    'Black': (200, 300),
    'Orange': (150, 200),
    'Yellow': (100, 150),
    'Green': (50, 100),
    'Blue': (0, 50),
    'Purple': (0, 20),
    'Red': (0, 100)
}

# 파일 로드 및 생성
def load_data():
    if os.path.isfile(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    else:
        # 파일이 없으면 기본 데이터로 새 파일 생성
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f, indent=4)
        return {}

# 파일 저장
def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# 출석 체크 명령어
@bot.command()
async def 컬러출첵(ctx):
    user_id = str(ctx.author.id)
    user_name = ctx.author.display_name

    # 데이터 로드
    data = load_data()
    user_data = data.get(user_id, {})
    last_check = user_data.get('last_check')
    check_count = user_data.get('check_count', 0)

    # 현재 시간
    now = datetime.utcnow()
    last_check_time = datetime.strptime(last_check, '%Y-%m-%dT%H:%M:%S') if last_check else None

    # 하루가 지났는지 확인
    if last_check_time and (now - last_check_time) < timedelta(days=1):
        await ctx.send("⏰ 하루에 한 번만 출석체크가 가능합니다.")
        return

    # 유저 등급 확인
    member = ctx.guild.get_member(ctx.author.id)
    role = [r.name for r in member.roles if r.name in POINTS]
    
    if not role:
        await ctx.send("⚠️ 컬러 유저만 사용 가능한 명령어입니다.")
        return

    # 포인트 지급
    role_name = role[0]
    min_points, max_points = POINTS[role_name]
    points = random.randint(min_points, max_points)

    # 데이터 업데이트
    user_data.update({
        'last_check': now.strftime('%Y-%m-%dT%H:%M:%S'),
        'points': points,
        'check_count': check_count + 1
    })
    data[user_id] = user_data
    save_data(data)

    # 당첨 내역 채널에 메시지 발송
    channel = bot.get_channel(1218196371585368114)
    if channel:
        await channel.send(f"{ctx.author.mention} [출첵] 이벤트PP {points}개")

    # 출석체크 메시지
    embed = discord.Embed(
        title=f"🎉 출석체크 완료! 🎉",
        description=f"**출석체크**\n{ctx.author.mention}님, 출석체크가 완료되었습니다! 🎊\n\n**포인트 지급 내역**\n이벤트PP: {points}개\n\n**출석 횟수**\n오늘까지 총 {check_count + 1}회 출석하셨습니다! 🎯",
        color=0x1abc9c
    )
    embed.set_thumbnail(url=ctx.guild.icon.url)  # 서버의 썸네일 URL로 수정
    embed.set_footer(text="🎈 축하합니다!")

    await ctx.send(embed=embed)


# 데이터 삭제 명령어
@bot.command()
@commands.has_permissions(administrator=True)  # 관리자만 사용 가능
async def 데이터삭제(ctx):
    if os.path.isfile(DATA_FILE):
        os.remove(DATA_FILE)
        # 빈 데이터 파일 생성
        with open(DATA_FILE, 'w') as f:
            json.dump({}, f, indent=4)
        await ctx.send("📂 데이터 파일이 삭제되었으며, 새로 생성되었습니다.")
    else:
        await ctx.send("⚠️ 데이터 파일이 존재하지 않습니다.")

tracemalloc.start()
# discord.Client 객체를 intents와 함께 생성
client = discord.Client(intents=intents)







@bot.command(name='PP미사용')
async def pp(ctx, *, query: str):
    if ctx.channel.name != "💳｜pp확인":
        await ctx.send("이 명령어는 `💳｜pp확인` 채널에서만 사용할 수 있습니다.")
        return

    if query not in pp_info_links:
        await ctx.send("잘못된 PP 정보 조회 요청입니다. 올바른 닉네임을 입력해주세요.")
        return

    message_id = pp_info_links[query]
    await send_pp_info(ctx, query, message_id)

@bot.command(name='pp')
async def pp(ctx, *, query: str):
    if ctx.channel.name != "💳｜pp확인":
        await ctx.send("이 명령어는 `💳｜pp확인` 채널에서만 사용할 수 있습니다.")
        return

    if query not in pp_info_links:
        await ctx.send("잘못된 PP 정보 조회 요청입니다. 올바른 닉네임을 입력해주세요.")
        return

    message_id = pp_info_links[query]
    await send_pp_info(ctx, query, message_id)

gp_info_links = {
    "비키니시티": "1243789494268854344",
    "로켓단": "1243789501323673721",
    "미호상점": "1243789502816981135",
}

@bot.command(name='GP')
async def send_gp_info(ctx, user_query):
    target_channel_id = 1243789425566158902  # GP 정보가 등록된 채널 ID
    channel = bot.get_channel(target_channel_id)
    
    if user_query in gp_info_links:
        message_id = int(gp_info_links[user_query])
        try:
            message = await channel.fetch_message(message_id)
            kst_now = datetime.now(ZoneInfo('Asia/Seoul'))
            await ctx.send(f"## {user_query}길드의 **[{kst_now.strftime('%m월 %d일 %H시 %M분')}]** 기준 정보를 안내드립니다.\n{message.content}")

        except Exception as e:
            print(f"GP 정보 조회 중 오류 발생: {e}")
            await ctx.send("GP 정보 조회 중 오류가 발생했습니다.")
    else:
        await ctx.send(f"'{user_query}'에 대한 정보를 찾을 수 없습니다. 올바른 길드명을 입력해주세요.")

@bot.event
async def on_ready():
    print(f'[Ver 2.3.1] {bot.user}이 로그인했습니다. 해당 봇은 PASTEL WORLD GM이 제작하였습니다.')
    general_channel = discord.utils.get(bot.get_all_channels(), name="일반")

    if general_channel:
        await general_channel.send(f'[Ver 2.3.1] {bot.user}이 로그인했습니다. 해당 봇은 PASTEL WORLD GM이 제작하였습니다.')
    else:
        print("일반 채널을 찾을 수 없습니다.")

    for guild in bot.guilds:
        print(f"Roles in {guild.name}: {guild.roles}")

    bot.loop.create_task(daily_message())

    # 봇 로그인
    await bot.login(TOKEN)

async def daily_message():
    while True:
        await asyncio.sleep(MESSAGE_INTERVAL)
        print("Daily Message Logic")

@bot.command(name='명령어')
async def say_hello(ctx):
    if ctx.message.author.bot:
        return
    print("Received command: !명령어")
    await ctx.send('!봇버전, !오류')

@bot.command(name='봇버전')
async def say_hello(ctx):
    if ctx.message.author.bot:
        return
    print("Received command: !봇버전")
    await ctx.send('현재 PASTEL WORLD 봇은 [2.3.1] 버전입니다. - PASTEL WORLD GM')

@bot.command(name='오류')
async def say_hello(ctx):
    if ctx.message.author.bot:
        return
    print("Received command: !오류")
    await ctx.send('현재 겪고 계신 오류가 음식을 먹어도 배고픔이 차지 않는 경우라면 https://discord.com/channels/1208238905896345620/1212600081082097804/1212718167139557416 를 통해 모드 설치를 부탁드립니다. 다른 오류인 경우 질문채널에 글을 남겨주세요.')

@bot.command(name='역할_초기화')
@commands.has_permissions(administrator=True)
async def take_role(ctx, user: discord.Member):
    role_name = "White"
    role = discord.utils.get(ctx.guild.roles, name=role_name)

    if role:
        try:
            await user.remove_roles(role)
            await ctx.send(f'{user.display_name}님의 {role_name} 역할을 뺏었습니다.')
        except discord.Forbidden:
            await ctx.send("사용하신 명령어는 관리자만 사용 가능합니다. - 해당 봇은 PASTEL WORLD GM이 제작하였습니다.")
        except Exception as e:
            await ctx.send(f'역할 뺏기 중 오류 발생: {e}')
    else:
        await ctx.send(f'{role_name} 역할을 찾을 수 없습니다.')

def is_apply_channel(ctx):
    return ctx.channel.name == "🎆｜입장신청"

last_command_time = {}

async def check_steam_profile(steam_profile_link):
    async with aiohttp.ClientSession() as session:
        async with session.get(steam_profile_link) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                if soup.find(text=re.compile(r'Sorry|Error|This profile is private.')):
                    # 프로필 페이지에 오류 문구가 포함되어 있는 경우
                    return False
                else:
                    # 프로필이 존재하고 오류 문구가 없는 경우
                    return True
            elif response.status == 404:
                # 프로필이 존재하지 않는 경우
                return False
            else:
                # 기타 오류 처리
                print(f"Steam profile check failed with status code {response.status}")
                return False

steam_profile_regex = re.compile(r'^https?://steamcommunity.com/(id|profiles)/([a-zA-Z0-9_-]+)/?$')

# 스팀 프로필 링크가 스팀 고유 ID를 포함하는지 확인하는 함수
def is_steam_profile_link(steam_profile_link):
    return steam_profile_regex.match(steam_profile_link) is not None

# 스팀 프로필 링크를 검사하여 오류 문구가 있는지 확인하는 함수
async def check_steam_profile(steam_profile_link):
    async with aiohttp.ClientSession() as session:
        async with session.get(steam_profile_link) as response:
            if response.status == 200:
                html_content = await response.text()
                soup = BeautifulSoup(html_content, 'html.parser')
                if soup.find(string=re.compile(r'Sorry|Error|This profile is private.')):
                    # 프로필 페이지에 오류 문구가 포함되어 있는 경우
                    return False
                else:
                    # 프로필이 존재하고 오류 문구가 없는 경우
                    return True
            elif response.status == 404:
                # 프로필이 존재하지 않는 경우
                return False
            else:
                # 기타 오류 처리
                print(f"Steam profile check failed with status code {response.status}")
                return False

# 스팀 고유 ID를 추출하는 함수
def extract_steam_id(steam_profile_link):
    match = steam_profile_regex.match(steam_profile_link)
    if match:
        return match.group(2)  # 두 번째 그룹이 스팀 고유 ID에 해당합니다.
    else:
        return None

# 스팀 고유 ID를 GM2 채널로 전송하는 함수
async def send_steam_id_to_gm2(ctx, steam_id):
    gm2_channel = discord.utils.get(ctx.guild.channels, name="gm2")
    if gm2_channel:
        await gm2_channel.send(f"{ctx.author.mention}의 스팀 고유 ID: {steam_id}")
    else:
        print("gm2 채널을 찾을 수 없습니다.")

from datetime import datetime
from zoneinfo import ZoneInfo

@bot.command(name='신청', aliases=['!신청'])
@commands.check(is_apply_channel)
async def apply(ctx):
    # 사용자가 명령어를 실행한 시간을 확인
    last_time = last_command_time.get(ctx.author.id)

    # 마지막으로 명령어를 실행한 시간이 존재하고, 120초 이내에 실행했다면 명령어를 실행하지 못하도록 막음
    if last_time and datetime.now(ZoneInfo('Asia/Seoul')) - last_time < timedelta(seconds=120):
        await ctx.send(f"{ctx.author.mention}, 명령어를 120초에 한 번만 사용할 수 있습니다.")
        return

    # 명령어 실행 후 현재 시간을 저장
    last_command_time[ctx.author.id] = datetime.now(ZoneInfo('Asia/Seoul'))

    # 여기에 디버깅 코드 추가
    apply_channel_name = "🎆｜입장신청"
    apply_channel = discord.utils.get(ctx.guild.channels, name=apply_channel_name)

    # 추가된 디버깅 코드
    print(f"apply_channel: {apply_channel}")

    # 주어진 디스코드 메시지 링크의 내용을 가져와서 해당 내용으로 메시지를 보냄
    ippw_message_link = "https://discord.com/channels/1208238905896345620/1210617813463601193/1210617961711407135"
    channel_id, _, message_id = ippw_message_link.split("/")[-3:]

    # 수정된 부분: 디버깅 정보 출력
    print(f"message_id: {message_id}")

    try:
        ippw_channel_name = "ippw"
        ippw_channel = discord.utils.get(ctx.guild.channels, name=ippw_channel_name)
        linked_message = await ippw_channel.fetch_message(int(message_id))
        print(f"linked_message: {linked_message}")

        # 디버깅 정보 출력
        print(f"linked_message content: {linked_message.content}")

        # DM으로 메시지 전송
        dm_message = await ctx.author.send(linked_message.content)

        # Grey 역할 제거
        grey_role = discord.utils.get(ctx.guild.roles, name="Grey")
        if grey_role in ctx.author.roles:
            await ctx.author.remove_roles(grey_role)

        # White 역할 추가
        white_role = discord.utils.get(ctx.guild.roles, name="White")
        if white_role:
            await ctx.author.add_roles(white_role)

        # 서버-입장-채널에 메시지 전송
        await apply_channel.send(f"{ctx.author.mention}님이 {datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y년 %m월 %d일 %H시 %M분')}에 1서버에 접속 요청을 하였습니다. "
        #                f"IP와 Password는 DM으로 발송드렸으며 해당 DM은 2분 후 삭제되오니 빠르게 확인 부탁드립니다.")
                        f"IP : 121.164.10.178:8211 비밀번호 : pal3492")
        # 2분 후에 DM으로 보낸 메시지 삭제
        await asyncio.sleep(120)
        await dm_message.delete()

    except discord.NotFound as not_found_error:
        print(f"Error fetching message: {not_found_error}")
        await ctx.send("메시지를 찾을 수 없습니다.")
    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("오류가 발생했습니다.")

@bot.command(name='신청2', aliases=['!신청2'])
@commands.check(is_apply_channel)
async def apply(ctx):
    # 사용자가 명령어를 실행한 시간을 확인
    last_time = last_command_time.get(ctx.author.id)

    # 마지막으로 명령어를 실행한 시간이 존재하고, 120초 이내에 실행했다면 명령어를 실행하지 못하도록 막음
    if last_time and datetime.now(ZoneInfo('Asia/Seoul')) - last_time < timedelta(seconds=120):
        await ctx.send(f"{ctx.author.mention}, 명령어를 120초에 한 번만 사용할 수 있습니다.")
        return

    # 명령어 실행 후 현재 시간을 저장
    last_command_time[ctx.author.id] = datetime.now(ZoneInfo('Asia/Seoul'))

    # 여기에 디버깅 코드 추가
    apply_channel_name = "🎆｜입장신청"
    apply_channel = discord.utils.get(ctx.guild.channels, name=apply_channel_name)

    # 추가된 디버깅 코드
    print(f"apply_channel: {apply_channel}")

    # 주어진 디스코드 메시지 링크의 내용을 가져와서 해당 내용으로 메시지를 보냄
    ippw_message_link = "https://discord.com/channels/1208238905896345620/1210617813463601193/1225172410819547146"
    channel_id, _, message_id = ippw_message_link.split("/")[-3:]

    # 수정된 부분: 디버깅 정보 출력
    print(f"message_id: {message_id}")

    try:
        ippw_channel_name = "ippw"
        ippw_channel = discord.utils.get(ctx.guild.channels, name=ippw_channel_name)
        linked_message = await ippw_channel.fetch_message(int(message_id))
        print(f"linked_message: {linked_message}")

        # 디버깅 정보 출력
        print(f"linked_message content: {linked_message.content}")

        # DM으로 메시지 전송
        dm_message = await ctx.author.send(linked_message.content)

        # Grey 역할 제거
        grey_role = discord.utils.get(ctx.guild.roles, name="Grey")
        if grey_role in ctx.author.roles:
            await ctx.author.remove_roles(grey_role)

        # White 역할 추가
        white_role = discord.utils.get(ctx.guild.roles, name="White")
        if white_role:
            await ctx.author.add_roles(white_role)

        # 서버-입장-채널에 메시지 전송
        await apply_channel.send(f"{ctx.author.mention}님이 {datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y년 %m월 %d일 %H시 %M분')}에 2서버에 접속 요청을 하였습니다. "
                        f"IP와 Password는 DM으로 발송드렸으며 해당 DM은 2분 후 삭제되오니 빠르게 확인 부탁드립니다.")

        # 2분 후에 DM으로 보낸 메시지 삭제
        await asyncio.sleep(120)
        await dm_message.delete()

    except discord.NotFound as not_found_error:
        print(f"Error fetching message: {not_found_error}")
        await ctx.send("메시지를 찾을 수 없습니다.")
    except Exception as e:
        print(f"Error: {e}")
        await ctx.send("오류가 발생했습니다.")

@bot.command(name='인증')
async def authenticate(ctx, steam_profile_link: str = None):
    if not steam_profile_link:
        await ctx.send("스팀 프로필 링크를 입력해주세요.")
        return

    if not is_steam_profile_link(steam_profile_link):
        await ctx.send("올바른 스팀 프로필 링크를 입력해주세요. 형식: `!인증 스팀프로필링크`")
        return

    # 스팀 프로필 링크가 유효한지 확인
    if await check_steam_profile(steam_profile_link):
        steam_id = extract_steam_id(steam_profile_link)
        if steam_id:
            if steam_id in registered_steam_ids:
                await ctx.send("이미 등록된 스팀 계정입니다.")
            else:
                # 스팀 고유 ID를 gm2 채널로 전송
                gm2_channel = discord.utils.get(ctx.guild.channels, name="gm2")
                if gm2_channel:
                    await gm2_channel.send(f"{ctx.author.mention}의 스팀 고유 ID: {steam_id}")
                else:
                    print("gm2 채널을 찾을 수 없습니다.")

                success_message = f"{ctx.author.mention}님, {datetime.now(ZoneInfo('Asia/Seoul')).strftime('%Y년 %m월 %d일 %H시 %M분 %S초')}에 스팀 인증이 완료되었습니다. **<#1210425834205347890>** 채널에서 **!신청** 명령어를 통해 서버 정보를 확인해주세요."
                dm_message = f"안녕하세요! {ctx.author.name}님의 스팀 프로필 링크가 성공적으로 인증되었습니다. **<#1210425834205347890>** 채널에서 **!신청** 명령어를 통해 서버 정보를 확인해주세요."
                await ctx.author.send(dm_message)
                await ctx.send(success_message)
                registered_steam_ids.add(steam_id)

                # Grey 등급 추가
                grey_role = discord.utils.get(ctx.guild.roles, name="Grey")
                if grey_role:
                    await ctx.author.add_roles(grey_role)
                else:
                    print("Grey 역할을 찾을 수 없습니다.")
                
                # 사용자의 메시지 삭제
                await ctx.message.delete()
        else:
            await ctx.send("유효하지 않은 스팀 프로필 링크입니다.")
    else:
        await ctx.send(f"비공개 상태거나 존재하지 않는 스팀 프로필입니다. "
                       f"정확한 프로필이나, 비공개 상태인 경우 `{steam_profile_link}edit/settings`링크를 통해 "
                       f"프로필을 공개 상태로 전환해주세요.")

# 파일 경로 설정
dbcoupon_file_path = 'dbcoupon_inventory.txt'

def update_user_dbcoupon_inventory(user_id):
    """유저 ID로 쿠폰 수를 파일에 기록하거나 업데이트합니다."""
    coupons = {}
    if os.path.exists(dbcoupon_file_path):
        with open(dbcoupon_file_path, "r") as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
                
    coupons[user_id] = coupons.get(user_id, 0) + 1
    
    with open(dbcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")
    
    return coupons[user_id]

def process_roulette_command(user_id):
    """쿠폰을 사용하여 확률에 따른 아이템을 할당하고, 사용된 쿠폰 수를 감소시킵니다."""
    if not os.path.exists(dbcoupon_file_path):
        return "쿠폰 데이터 파일이 존재하지 않습니다.", 0
    
    coupons = {}
    with open(dbcoupon_file_path, "r") as file:
        for line in file:
            user, count = line.strip().split(":")
            coupons[user] = int(count)
    
    if user_id not in coupons or coupons[user_id] == 0:
        return f"<@{user_id}> 님, 사용 가능한 쿠폰이 없습니다.", 0
    
    coupons[user_id] -= 1
    with open(dbcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")

    # 확률별 아이템 할당
    probability_groups = [
        (70, ["[노말] 골드 10000개", "[노말] 케이크 10개", "[노말] 금속주괴 20개", "[노말] 전설스피어 10개", "[노말] 팰의체액 10개", "[노말] 고대문명의부품 20개", "[노말] 시멘트 100개", "[노말] 펠의체액 50개", "[노말] 제련금속주괴 20개"]),
        (20, ["[레어] 골드 30000개", "[레어] 케이크 20개", "[레어] 금속주괴 30개", "[레어] 전설스피어 20개", "[레어] 팰의체액 20개", "[레어] 고대문명의부품 300개", "[레어] 시멘트 200개", "[레어] 펠의체액 100개", "[레어] 제련금속주괴 30개"]),
        (9, ["[에픽] 스텟초기화물약 1개","[에픽] 골드 50000개", "[에픽] 케이크 30개", "[에픽] 금속주괴 60개", "[에픽] 전설스피어 30개", "[에픽] 팰의체액 30개", "[에픽] 고대문명의부품 40개", "[에픽] 시멘트 100개", "[에픽] 펠기름 200개", "[에픽] 제련금속주괴 40개"]),
        (1, ["[유니크] 스텟초기화물약 2개","[유니크] 골드 60000개", "[유니크] 케이크 40개", "[유니크] 금속주괴 500개", "[유니크] 전설스피어 40개", "[유니크] 팰의체액 40개", "[유니크] 고대문명의부품 50개", "[유니크] 시멘트 200개", "[유니크] 펠기름 300개", "[유니크] 제련금속주괴 50개"])
    ]
    
    draw = random.choices(probability_groups, weights=[group[0] for group in probability_groups], k=1)[0]
    item = random.choice(draw[1])
    return f"<@{user_id}> {item}", coupons[user_id]

# 파일 경로 설정
bigcoupon_file_path = 'bigcoupon_inventory.txt'

def update_user_bigcoupon_inventory(user_id):
    """유저 ID로 쿠폰 수를 파일에 기록하거나 업데이트합니다."""
    coupons = {}
    if os.path.exists(bigcoupon_file_path):
        with open(bigcoupon_file_path, "r") as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
                
    coupons[user_id] = coupons.get(user_id, 0) + 1
    
    with open(bigcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")
    
    return coupons[user_id]

def process_roulettes_command(user_id):
    """쿠폰을 사용하여 확률에 따른 아이템을 할당하고, 사용된 쿠폰 수를 감소시킵니다."""
    if not os.path.exists(bigcoupon_file_path):
        return "쿠폰 데이터 파일이 존재하지 않습니다.", 0
    
    coupons = {}
    with open(bigcoupon_file_path, "r") as file:
        for line in file:
            user, count = line.strip().split(":")
            coupons[user] = int(count)
    
    if user_id not in coupons or coupons[user_id] == 0:
        return f"<@{user_id}> 님, 사용 가능한 쿠폰이 없습니다.", 0
    
    coupons[user_id] -= 1
    with open(bigcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")

    # 확률별 아이템 할당
    probability_groups = [
        (70, ["[에픽] 스텟초기화물약 1개","[에픽] 골드 60000개", "[에픽] 케이크 30개", "[에픽] 금속주괴 30개", "[에픽] 전설스피어 30개", "[에픽] 팰의체액 50개", "[에픽] 고대문명의부품 50개", "[에픽] 시멘트 50개", "[에픽] 펠기름 50개", "[에픽] 제련금속주괴 40개"]),
        (20, ["[에픽] 스텟초기화물약 1개","[에픽] 골드 60000개", "[에픽] 케이크 30개", "[에픽] 금속주괴 30개", "[에픽] 전설스피어 30개", "[에픽] 팰의체액 50개", "[에픽] 고대문명의부품 50개", "[에픽] 시멘트 50개", "[에픽] 펠기름 50개", "[에픽] 제련금속주괴 40개"]),
        (9, ["[에픽] 스텟초기화물약 1개","[에픽] 골드 80000개", "[에픽] 케이크 40개", "[에픽] 금속주괴 40개", "[에픽] 전설스피어 40개", "[에픽] 팰의체액 70개", "[에픽] 고대문명의부품 70개", "[에픽] 시멘트 70개", "[에픽] 펠기름 70개", "[에픽] 제련금속주괴 50개"]),
        (1, ["[유니크] 스텟초기화물약 2개","[유니크] 골드 100000개", "[유니크] 케이크 50개", "[유니크] 금속주괴 60개", "[유니크] 전설스피어 50개", "[유니크] 팰의체액 100개", "[유니크] 고대문명의부품 100개", "[유니크] 시멘트 100개", "[유니크] 펠기름 100개", "[유니크] 제련금속주괴 70개"])
    ]
    
    draw = random.choices(probability_groups, weights=[group[0] for group in probability_groups], k=1)[0]
    item = random.choice(draw[1])
    return f"<@{user_id}> {item}", coupons[user_id]

# 파일 경로 설정
supercoupon_file_path = 'supercoupon_inventory.txt'

def update_user_supercoupon_inventory(user_id, count=1):
    """유저 ID로 쿠폰 수를 파일에 기록하거나 업데이트합니다."""
    coupons = {}
    if os.path.exists(supercoupon_file_path):
        with open(supercoupon_file_path, "r") as file:
            for line in file:
                user, count_str = line.strip().split(":")
                coupons[user] = int(count_str)  # 문자열을 정수로 변환하여 저장
                
    current_count = coupons.get(user_id, 0)
    new_count = current_count + count
    coupons[user_id] = new_count
    
    with open(supercoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")
    
    return new_count
def process_roulettess_command(user_id):
    """쿠폰을 사용하여 확률에 따른 아이템을 할당하고, 사용된 쿠폰 수를 감소시킵니다."""
    if not os.path.exists(supercoupon_file_path):
        return "쿠폰 데이터 파일이 존재하지 않습니다.", 0
    
    coupons = {}
    with open(supercoupon_file_path, "r") as file:
        for line in file:
            user, count = line.strip().split(":")
            coupons[user] = int(count)
    
    if user_id not in coupons or coupons[user_id] == 0:
        return f"<@{user_id}> 님, 사용 가능한 쿠폰이 없습니다.", 0
    
    coupons[user_id] -= 1
    with open(supercoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")

    # 확률별 아이템 할당
    probability_groups = [
        (70, ["[유니크] 스텟초기화물약 1개","[유니크] 원유 30개","[유니크] 카본섬유 50개","[유니크] 팰금속주괴 100개","[유니크] 얼티밋스피어 10개","[유니크] 플라스틸 50개","[유니크] 고대문명의코어 1개","[유니크] 운석파편 3개","[유니크] 벨르누아르의석판 3개","[유니크] 벨라루즈석판 3개","[유니크] 수련의서(S) 3개","[유니크] 수련의서(M) 3개","[유니크] 수련의서(L) 3개","[유니크] 수련의서(XL) 3개","[유니크] 벨라루주[궁극]의석판 3개","[유니크] 마그마드라고의석판 2개","[유니크] 마그마드라고[궁극]의석판 2개"]),
        (20, ["[유니크] 스텟초기화물약 1개","[유니크] 원유 30개","[유니크] 카본섬유 50개","[유니크] 팰금속주괴 100개","[유니크] 얼티밋스피어 10개","[유니크] 플라스틸 50개","[유니크] 고대문명의코어 1개","[유니크] 운석파편 3개","[유니크] 벨르누아르의석판 3개","[유니크] 벨라루즈석판 3개","[유니크] 수련의서(S) 3개","[유니크] 수련의서(M) 3개","[유니크] 수련의서(L) 3개","[유니크] 수련의서(XL) 3개","[유니크] 벨라루주[궁극]의석판 3개","[유니크] 마그마드라고의석판 2개","[유니크] 마그마드라고[궁극]의석판 2개"]),
        (9, ["[유니크] 스텟초기화물약 1개","[유니크] 원유 30개","[유니크] 카본섬유 50개","[유니크] 팰금속주괴 100개","[유니크] 얼티밋스피어 10개","[유니크] 플라스틸 50개","[유니크] 고대문명의코어 1개","[유니크] 운석파편 3개","[유니크] 벨르누아르의석판 3개","[유니크] 벨라루즈석판 3개","[유니크] 수련의서(S) 3개","[유니크] 수련의서(M) 3개","[유니크] 수련의서(L) 3개","[유니크] 수련의서(XL) 3개","[유니크] 벨라루주[궁극]의석판 3개","[유니크] 마그마드라고의석판 2개","[유니크] 마그마드라고[궁극]의석판 2개"]),
        (1, ["[유니크] 스텟초기화물약 1개","[유니크] 원유 30개","[유니크] 카본섬유 50개","[유니크] 팰금속주괴 100개","[유니크] 얼티밋스피어 10개","[유니크] 플라스틸 50개","[유니크] 고대문명의코어 1개","[유니크] 운석파편 3개","[유니크] 벨르누아르의석판 3개","[유니크] 벨라루즈석판 3개","[유니크] 수련의서(S) 3개","[유니크] 수련의서(M) 3개","[유니크] 수련의서(L) 3개","[유니크] 수련의서(XL) 3개","[유니크] 벨라루주[궁극]의석판 3개","[유니크] 마그마드라고의석판 2개","[유니크] 마그마드라고[궁극]의석판 2개"])
    ]
    draw = random.choices(probability_groups, weights=[group[0] for group in probability_groups], k=1)[0]
    item = random.choice(draw[1])
    return f"<@{user_id}> {item}", coupons[user_id]


@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

def is_admin(ctx):
    admin_permission = ctx.author.guild_permissions.administrator
    print(f"User is administrator: {admin_permission}")
    return admin_permission

@bot.command(name='확정룰렛쿠폰')
async def add_big_coupon(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1개 이상의 쿠폰을 입력해주세요.")
        return

    coupon_count = update_user_bigcoupon_inventory(str(member.id), count)
    
    embed = discord.Embed(
        title="확정 룰렛 쿠폰 지급 완료",
        description=f"**{member.mention} 님**, 총 **{count}장**의 확정 룰렛 쿠폰이 지급되었습니다.",
        color=discord.Color.green()
    )
    embed.add_field(name="쿠폰 사용 채널 바로가기", value="[여기를 클릭하세요](https://discord.com/channels/1208238905896345620/1226495859622019122)", inline=False)
    embed.add_field(name="명령어 입력", value="!확정룰렛을 입력해주세요.", inline=False)
    embed.add_field(name="현재 보유중인 쿠폰 갯수", value=f"**{coupon_count}개**", inline=False)
    embed.set_footer(text="©｜쿠폰사용 채널에서 쿠폰을 사용해주세요.")
    
    await ctx.send(embed=embed)

@bot.command(name='대박확정룰렛쿠폰')
async def add_super_coupon(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1개 이상의 쿠폰을 입력해주세요.")
        return

    coupon_count = update_user_supercoupon_inventory(str(member.id), count)
    
    embed = discord.Embed(
        title="대박 확정 룰렛 쿠폰 지급 완료",
        description=f"**{member.mention} 님**, 총 **{count}장**의 대박 확정 룰렛 쿠폰이 지급되었습니다.",
        color=discord.Color.purple()
    )
    embed.add_field(name="쿠폰 사용 채널 바로가기", value="[여기를 클릭하세요](https://discord.com/channels/1208238905896345620/1226495859622019122)", inline=False)
    embed.add_field(name="명령어 입력", value="!대박확정룰렛을 입력해주세요.", inline=False)
    embed.add_field(name="현재 보유중인 쿠폰 갯수", value=f"**{coupon_count}개**", inline=False)
    embed.set_footer(text="©｜쿠폰사용 채널에서 쿠폰을 사용해주세요.")
    
    await ctx.send(embed=embed)

@bot.command(name='대박룰렛쿠폰')
async def add_super_coupon(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1개 이상의 쿠폰을 입력해주세요.")
        return

    coupon_count = update_user_dbcoupon_inventory(str(member.id), count)
    
    embed = discord.Embed(
        title="대박 룰렛 쿠폰 지급 완료",
        description=f"**{member.mention} 님**, 총 **{count}장**의 대박 룰렛 쿠폰이 지급되었습니다.",
        color=discord.Color.blue()
    )
    embed.add_field(name="쿠폰 사용 채널 바로가기", value="[여기를 클릭하세요](https://discord.com/channels/1208238905896345620/1226495859622019122)", inline=False)
    embed.add_field(name="명령어 입력", value="!대박룰렛을 입력해주세요.", inline=False)
    embed.add_field(name="현재 보유중인 쿠폰 갯수", value=f"**{coupon_count}개**", inline=False)
    embed.set_footer(text="©｜쿠폰사용 채널에서 쿠폰을 사용해주세요.")
    
    await ctx.send(embed=embed)

@bot.command(name='길드보급쿠폰')
async def add_guild_supply_coupon(ctx, member: discord.Member, count: int):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return
    
    if count <= 0:
        await ctx.send("잘못된 쿠폰 갯수입니다. 1개 이상의 쿠폰을 입력해주세요.")
        return

    coupon_count = update_guild_supply_coupon_inventory(str(member.id), count)
    
    embed = discord.Embed(
        title="길드 보급 쿠폰 지급 완료",
        description=f"**{member.mention} 님**, 총 **{count}개**의 길드 보급 쿠폰이 지급되었습니다.",
        color=discord.Color.gold()
    )
    embed.add_field(name="현재 보유중인 길드 보급 쿠폰", value=f"**{coupon_count}개**", inline=False)
    embed.add_field(name="사용 안내", value="쿠폰은 ©｜쿠폰사용 채널에서 `!길드보급` 으로 사용 부탁드립니다.", inline=False)
    embed.set_footer(text="★보급품은 길드마스터가 분배 / 독점이 가능합니다.★")
    
    await ctx.message.delete()
    await ctx.send(embed=embed)

# 채널 ID와 파일 경로 설정
GIVEAWAY_CHANNEL_ID = 1218543871907201166  # 💦｜점검보상 채널의 실제 ID
GENERAL_CHAT_CHANNEL_ID = 1208300374478426132  # 📧｜자유채팅 채널의 실제 ID
COUPON_FILE = 'fixcoupon.txt'

# 쿠폰 데이터 로드 및 저장
def load_coupon_data():
    if not os.path.exists(COUPON_FILE):
        return {}
    
    with open(COUPON_FILE, 'r') as f:
        data = {}
        for line in f.readlines():
            user_id, count = line.strip().split('/')
            data[int(user_id)] = int(count)
        return data

def save_coupon_data(data):
    with open(COUPON_FILE, 'w') as f:
        for user_id, count in data.items():
            # 구분자를 '/'로 일관성 있게 수정
            f.write(f"{user_id}/{count}\n")

# !점검쿠폰지급 명령어
@bot.command(name='점검쿠폰지급')
async def give_coupons(ctx, count: int):
    # 일반 채팅 채널에서만 명령어를 실행할 수 있도록 제한
    if ctx.channel.id != GENERAL_CHAT_CHANNEL_ID:
        await ctx.send(f"❌ 이 명령어는 일반 채팅 채널에서만 사용할 수 있습니다.")
        return
    
    # 점검 보상 채널을 찾음
    giveaway_channel = bot.get_channel(GIVEAWAY_CHANNEL_ID)
    
    if giveaway_channel is None:
        await ctx.send("❌ 점검 보상 채널을 찾을 수 없습니다.")
        return

    # 참여자 목록을 매번 새로 초기화
    participants = set()

    try:
        # 메시지 기록을 가져와서 !보상신청 메시지를 보낸 유저만 participants에 추가 (중복 방지)
        async for message in giveaway_channel.history(limit=None):
            if message.content.strip() == "!보상신청" and not message.author.bot:
                participants.add(message.author.id)

        # 쿠폰 데이터 로드
        coupon_data = load_coupon_data()
        
        # 참여자들에게 쿠폰 지급
        for user_id in participants:
            if user_id not in coupon_data:
                coupon_data[user_id] = 0
            coupon_data[user_id] += count

            # 임베드 메시지 생성
            user = await bot.fetch_user(user_id)
            embed = discord.Embed(
                title="🎁 점검 쿠폰 지급 완료!",
                description=f"{user.mention}님, 점검 쿠폰 **{count}개**가 지급되었습니다!\n현재 보유 중인 쿠폰 수: **{coupon_data[user_id]}개**",
                color=discord.Color.blue()
            )
            embed.set_footer(text="점검보상 쿠폰 시스템")
            embed.set_thumbnail(url="https://example.com/coupon-image.png")  # 적절한 이미지를 URL로 추가하세요.
            await ctx.send(embed=embed)

        # 쿠폰 데이터 저장
        save_coupon_data(coupon_data)

        # 완료 메시지
        await ctx.send("✅ 점검 보상 쿠폰이 지급되었습니다. https://discord.com/channels/1208238905896345620/1226495859622019122 채널에서 !점검쿠폰 명령어를 사용해주세요.")

        # 점검 보상 채널의 메시지 기록 중 !보상신청 메시지만 삭제
        async for message in giveaway_channel.history(limit=None):
                    bot_message = await ctx.send(embed=embed)
                    await message.delete()
                    await bot_message.delete()

        # 참여자 목록 초기화
        participants.clear()

    except Exception as e:
        print(f"Error fetching channel history: {e}")
        await ctx.send("❌ 메시지 기록을 가져오는 중 문제가 발생했습니다.")

# 공격 이벤트 정보를 저장하는 변수들
event_active = False
event_item = ""
event_quantity = 0
participants = {}

# !공격이벤 명령어
@bot.command(name="공격이벤")
async def start_event(ctx, item_name: str, quantity: int):
    global event_active, event_item, event_quantity, participants
    if event_active:
        await ctx.send("이미 이벤트가 진행 중입니다!")
        return

    event_active = True
    event_item = item_name
    event_quantity = quantity
    participants = {}

    # 명령어 보낸 채팅 삭제
    await ctx.message.delete()

    embed = discord.Embed(
        title="🛡️ 일렉판다 등장! 공격 이벤트 시작! 🛡️",
        description=f"**일렉판다** 보스 몬스터가 나타났습니다! 여러분의 힘을 모아 처치하세요!\n\n**아이템**: {item_name}\n**수량**: {quantity}",
        color=0xff0000
    )
    embed.set_footer(text="!공격신청 명령어로 공격에 참가하세요!")
    await ctx.send(embed=embed)

# !공격신청 명령어
@bot.command(name="공격신청")
async def attack(ctx):
    global participants
    if not event_active:
        await ctx.send("이벤트가 시작되지 않았습니다!")
        return

    user = ctx.author
    if user in participants:
        await ctx.send(f"{user.mention}님은 이미 공격을 신청하셨습니다!")
        return

    attack_power = random.randint(1, 1000)
    participants[user] = attack_power

    embed = discord.Embed(
        title="⚔️ 공격 성공! ⚔️",
        description=f"{user.display_name}님이 일렉판다에게 **{attack_power}**의 공격력을 입혔습니다!",
        color=0x00ff00
    )
    await ctx.send(embed=embed)

# !공격마감 명령어
@bot.command(name="공격마감")
async def end_event(ctx):
    global event_active, participants, event_item, event_quantity

    if not event_active:
        await ctx.send("진행 중인 이벤트가 없습니다!")
        return

    if not participants:
        await ctx.send("아직 아무도 공격을 신청하지 않았습니다!")
        return

    # 명령어 보낸 채팅 삭제
    await ctx.message.delete()

    # 참가자들의 공격력에 따라 정렬
    sorted_participants = sorted(participants.items(), key=lambda x: x[1], reverse=True)
    total_participants = len(sorted_participants)

    # 보상 정보
    reward_distribution = [(1, event_quantity)]
    if total_participants >= 3:
        reward_distribution.append((2, event_quantity // 2))
    if total_participants >= 5:
        reward_distribution.append((3, event_quantity // 4))

    # 당첨자에게 보상 지급 및 당첨 메시지 전송
    log_channel_id = 1218196371585368114
    log_channel = bot.get_channel(log_channel_id)

    for place, reward in reward_distribution:
        winner = sorted_participants[place - 1][0]
        if log_channel:
            await log_channel.send(f"{winner.mention} [공격] {event_item} {reward}개")

    # 참여자 공격력 결과 메시지
    embed = discord.Embed(
        title="⚔️ 공격 이벤트 결과 ⚔️",
        description="참여한 유저들의 공격력 결과는 다음과 같습니다:",
        color=0x00ff00
    )

    # 멋있게 꾸며진 등수
    place_decorations = {
        1: "🥇 **1등**",
        2: "🥈 **2등**",
        3: "🥉 **3등**"
    }

    for idx, (user, attack_power) in enumerate(sorted_participants):
        place_text = place_decorations.get(idx + 1, f"{idx + 1}등")  # 1, 2, 3등은 꾸며줌, 그 외는 기본 등수
        reward_text = ""
        # 해당 유저가 보상을 받았다면 보상 정보 추가
        if idx + 1 <= len(reward_distribution):
            reward_amount = reward_distribution[idx][1]
            reward_text = f" - {event_item} {reward_amount}개"

        # 닉네임 대신 유저 태그 사용
        embed.add_field(
            name=f"{place_text} {user.display_name}",  # 유저의 디스코드 닉네임을 표시
            value=f"일렉판다에게 **{attack_power}** 만큼의 공격력을 입혔습니다.{reward_text}",
            inline=False
        )
    await ctx.send(embed=embed)

    # 이벤트 리셋
    event_active = False
    event_item = ""
    event_quantity = 0
    participants = {}


# 돌림판 이벤트 정보를 저장하는 변수들
wheel_active = False
wheel_item = ""
wheel_quantity = 0
wheel_participants = []

# !돌림판이벤 명령어
@bot.command(name="돌림판이벤")
async def start_wheel_event(ctx, item_name: str, quantity: int):
    global wheel_active, wheel_item, wheel_quantity, wheel_participants
    if wheel_active:
        await ctx.send("이미 돌림판 이벤트가 진행 중입니다!")
        return

    wheel_active = True
    wheel_item = item_name
    wheel_quantity = quantity
    wheel_participants = []

    # 명령어 보낸 채팅 삭제
    await ctx.message.delete()

    embed = discord.Embed(
        title="🎡 **돌려~ 돌려~ 돌림판 이벤트 시작!** 🎡",
        description=f"**아이템**: {item_name}\n**수량**: {quantity}\n\n참여하려면 `!돌림판신청` 명령어를 입력하세요!",
        color=0xffa500
    )
    embed.set_footer(text="지금 바로 참가하세요!")
    await ctx.send(embed=embed)

# !돌림판신청 명령어
@bot.command(name="돌림판신청")
async def join_wheel_event(ctx):
    global wheel_participants
    if not wheel_active:
        await ctx.send("돌림판 이벤트가 시작되지 않았습니다!")
        return

    user = ctx.author
    if user in wheel_participants:
        await ctx.send(f"{user.mention}님은 이미 돌림판에 참가하셨습니다!")
        return

    wheel_participants.append(user)
    await ctx.send(f"{user.mention}님이 돌림판 이벤트에 참가하셨습니다!")

    # 명령어 보낸 채팅 삭제
    await ctx.message.delete()

# !돌림판마감 명령어
@bot.command(name="돌림판마감")
async def end_wheel_event(ctx):
    global wheel_active, wheel_item, wheel_quantity, wheel_participants

    if not wheel_active:
        await ctx.send("진행 중인 돌림판 이벤트가 없습니다!")
        return

    if not wheel_participants:
        await ctx.send("아직 아무도 돌림판에 참가하지 않았습니다!")
        return

    # 명령어 보낸 채팅 삭제
    await ctx.message.delete()

    # 3초 카운트다운 (크게 표시하고 이모지로 꾸밈)
    countdown_message = await ctx.send("🎉 **돌림판 이벤트에 참여하신 유저분들입니다!** 🎉\n**3초 후 돌림판이 돌아갑니다!** ⏳")
    for i in range(3, 0, -1):
        await countdown_message.edit(content=f"🎉 **돌림판 이벤트에 참여하신 유저분들입니다!** 🎉\n**{i}초 후 돌림판이 돌아갑니다!** ⏳")
        await asyncio.sleep(1)

    # 돌림판 애니메이션 시작 (5초 동안)
    placeholder = "[         ]"
    animation_message = await ctx.send("\n".join([f"**{user.display_name}** {placeholder}" for user in wheel_participants]))

    for _ in range(5):
        for idx, user in enumerate(wheel_participants):
            updated_message = ""
            for i, participant in enumerate(wheel_participants):
                if i == idx:
                    updated_message += f"**{participant.display_name}** [    🎯    ]\n"
                else:
                    updated_message += f"**{participant.display_name}** {placeholder}\n"
            await animation_message.edit(content=updated_message)
            await asyncio.sleep(0.3)

    # 랜덤 당첨자 선택
    winner = random.choice(wheel_participants)

    # 마지막으로 당첨자에게만 [    O    ] 표시
    final_message = ""
    for participant in wheel_participants:
        if participant == winner:
            final_message += f"**{participant.display_name}** [    🎯    ]\n"
        else:
            final_message += f"**{participant.display_name}** {placeholder}\n"
    await animation_message.edit(content=final_message)

    # 당첨 메시지
    log_channel_id = 1218196371585368114
    log_channel = bot.get_channel(log_channel_id)

    # 당첨자 채널로 메시지 전송
    if log_channel:
        await log_channel.send(f"{winner.mention} [돌판] {wheel_item} {wheel_quantity}개")

    # 당첨자 발표 메시지
    embed = discord.Embed(
        title="🎉 **돌림판 이벤트 결과** 🎉",
        description=f"축하합니다! {winner.mention}님이 **{wheel_item}** {wheel_quantity}개를 획득하셨습니다! 🎊",
        color=0x00ff00
    )
    await ctx.send(embed=embed)

    # 이벤트 리셋
    wheel_active = False
    wheel_item = ""
    wheel_quantity = 0
    wheel_participants = []


@bot.command(name='대박룰렛')
async def roulette(ctx):
    # 허용된 채널에서만 명령어를 사용할 수 있게 하기 위한 예시 ID, 실제 ID로 교체 필요
    allowed_channel_id = '1226495859622019122'
    
    # 메시지가 보내진 채널의 ID를 비교
    if str(ctx.channel.id) != allowed_channel_id:
        await ctx.send("이 명령어는 ©｜쿠폰사용 채널에서만 사용할 수 있습니다.")
        return
    
    # 명령어 실행 로직
    result, _ = process_roulette_command(str(ctx.author.id))
    
    # 사용자가 명령어를 사용한 채널에 메시지 발송
    await ctx.send(result)

    # 📰｜룰렛당첨 채널에도 같은 메시지 발송
    announcement_channel_id = '1218196371585368114'  # 실제 📰｜룰렛당첨 채널의 ID로 교체
    announcement_channel = bot.get_channel(int(announcement_channel_id))
    if announcement_channel:
        await announcement_channel.send(result)
    else:
        print(f"Error: 📰｜룰렛당첨 채널(ID: {announcement_channel_id})을 찾을 수 없습니다.")

@bot.command(name='길드보급')
async def roulette(ctx):
    # 허용된 채널에서만 명령어를 사용할 수 있게 하기 위한 예시 ID, 실제 ID로 교체 필요
    allowed_channel_id = '1226495859622019122'
    
    # 메시지가 보내진 채널의 ID를 비교
    if str(ctx.channel.id) != allowed_channel_id:
        await ctx.send("이 명령어는 ©｜쿠폰사용 채널에서만 사용할 수 있습니다.")
        return
    
    # 명령어 실행 로직
    result, _ = process_roulette_command(str(ctx.author.id))
    
    # 사용자가 명령어를 사용한 채널에 메시지 발송
    await ctx.send(result)

    # 📰｜룰렛당첨 채널에도 같은 메시지 발송
    announcement_channel_id = '1218196371585368114'  # 실제 📰｜룰렛당첨 채널의 ID로 교체
    announcement_channel = bot.get_channel(int(announcement_channel_id))
    if announcement_channel:
        await announcement_channel.send(result)
    else:
        print(f"Error: 📰｜룰렛당첨 채널(ID: {announcement_channel_id})을 찾을 수 없습니다.")

@bot.command(name='확정룰렛')
async def roulette(ctx):
    # 허용된 채널에서만 명령어를 사용할 수 있게 하기 위한 예시 ID, 실제 ID로 교체 필요
    allowed_channel_id = '1226495859622019122'
    
    # 메시지가 보내진 채널의 ID를 비교
    if str(ctx.channel.id) != allowed_channel_id:
        await ctx.send("이 명령어는 ©｜쿠폰사용 채널에서만 사용할 수 있습니다.")
        return
    
    # 명령어 실행 로직
    result, _ = process_roulettes_command(str(ctx.author.id))
    
    # 사용자가 명령어를 사용한 채널에 메시지 발송
    await ctx.send(result)

    # 📰｜룰렛당첨 채널에도 같은 메시지 발송
    announcement_channel_id = '1218196371585368114'  # 실제 📰｜룰렛당첨 채널의 ID로 교체
    announcement_channel = bot.get_channel(int(announcement_channel_id))
    if announcement_channel:
        await announcement_channel.send(result)
    else:
        print(f"Error: 📰｜룰렛당첨 채널(ID: {announcement_channel_id})을 찾을 수 없습니다.")

@bot.command(name='대박확정룰렛')
async def roulette(ctx):
    # 허용된 채널에서만 명령어를 사용할 수 있게 하기 위한 예시 ID, 실제 ID로 교체 필요
    allowed_channel_id = '1226495859622019122'
    
    # 메시지가 보내진 채널의 ID를 비교
    if str(ctx.channel.id) != allowed_channel_id:
        await ctx.send("이 명령어는 ©｜쿠폰사용 채널에서만 사용할 수 있습니다.")
        return
    
    # 명령어 실행 로직
    result, _ = process_roulettess_command(str(ctx.author.id))
    
    # 사용자가 명령어를 사용한 채널에 메시지 발송
    await ctx.send(result)

    # 📰｜룰렛당첨 채널에도 같은 메시지 발송
    announcement_channel_id = '1218196371585368114'  # 실제 📰｜룰렛당첨 채널의 ID로 교체
    announcement_channel = bot.get_channel(int(announcement_channel_id))
    if announcement_channel:
        await announcement_channel.send(result)
    else:
        print(f"Error: 📰｜룰렛당첨 채널(ID: {announcement_channel_id})을 찾을 수 없습니다.")


@bot.command(name='대박룰렛쿠폰확인')
async def check_coupon(ctx, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    coupons = {}
    if os.path.exists(dbcoupon_file_path):
        with open(dbcoupon_file_path, 'r') as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
    coupon_count = coupons.get(user_id, 0)
    if coupon_count > 0:
        await ctx.send(f"{member.mention} 님께서 현재 보유중인 대박 룰렛 쿠폰은 [{coupon_count}]개입니다.")
    else:
        await ctx.send(f"{member.mention} 님, 사용 가능한 쿠폰이 없습니다.")

@bot.command(name='룰렛쿠폰확인')
async def check_coupon(ctx, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    coupons = {}
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
    coupon_count = coupons.get(user_id, 0)
    if coupon_count > 0:
        await ctx.send(f"{member.mention} 님께서 현재 보유중인 대박 룰렛 쿠폰은 [{coupon_count}]개입니다.")
    else:
        await ctx.send(f"{member.mention} 님, 사용 가능한 쿠폰이 없습니다.")

@bot.command(name='확정룰렛쿠폰확인')
async def check_coupon(ctx, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    coupons = {}
    if os.path.exists(bigcoupon_file_path):
        with open(bigcoupon_file_path, 'r') as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
    coupon_count = coupons.get(user_id, 0)
    if coupon_count > 0:
        await ctx.send(f"{member.mention} 님께서 현재 보유중인 확정 룰렛 쿠폰은 [{coupon_count}]개입니다.")
    else:
        await ctx.send(f"{member.mention} 님, 사용 가능한 쿠폰이 없습니다.")
def is_apply_channel(ctx):
    return ctx.channel.name == "🎆｜입장신청"

@bot.command(name='대박확정룰렛쿠폰확인')
async def check_coupon(ctx, *, member: discord.Member=None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    coupons = {}
    if os.path.exists(supercoupon_file_path):
        with open(supercoupon_file_path, 'r') as file:
            for line in file:
                user, count = line.strip().split(":")
                coupons[user] = int(count)
    coupon_count = coupons.get(user_id, 0)
    if coupon_count > 0:
        await ctx.send(f"{member.mention} 님께서 현재 보유중인 대박 확정 룰렛 쿠폰은 [{coupon_count}]개입니다.")
    else:
        await ctx.send(f"{member.mention} 님, 사용 가능한 쿠폰이 없습니다.")

def is_apply_channel(ctx):
    return ctx.channel.name == "🎆｜입장신청"

# 최신 메시지를 가져오는 함수
async def get_latest_message(channel):
    async for message in channel.history(limit=1):
        return message

# 사용자 ID를 닉네임으로 변환하는 함수
async def id_to_nickname(guild, user_id):
    user = guild.get_member(user_id)
    return user.display_name if user else None

# 사용자 ID를 멘션으로 변환하는 함수
async def id_to_mention(guild, user_id):
    user = guild.get_member(user_id)
    return f"<@{user_id}>" if user else None

@bot.command(name='지급신청')
async def apply_for_grant(ctx):
    # 해당 명령어가 입력된 채널이 📧｜자유채팅이 아니면 무시
    if ctx.channel.name != '📧｜자유채팅':
        return

    # 검사할 메시지 링크 목록
    message_links = [
        "https://discord.com/channels/1208238905896345620/1208303811039600660/1287031702505394387"
    ]

    for link in message_links:
        try:
            # 링크에서 server_id, channel_id, message_id 추출
            parts = link.split('/')
            server_id = int(parts[4])
            channel_id = int(parts[5])
            message_id = int(parts[6])

            # 해당 서버와 채널에서 메시지 가져오기
            guild = bot.get_guild(server_id)
            channel = guild.get_channel(channel_id)
            message = await channel.fetch_message(message_id)

            # 메시지 내용에 '지급불가' 포함 여부 확인
            if "지급불가" in message.content:
                embed = discord.Embed(
                    title="🚫 지급 불가",
                    description="현재 운영진이 활동 중이지 않으므로 신청이 불가능합니다.\n나중에 다시 시도해주세요.\n★지급신청은 매주 토요일 오후 8시 한 주의 당첨 아이템들이 합산되면 신청이 가능합니다.",
                    color=discord.Color.orange()
                )
                await ctx.send(embed=embed)
                return

        except discord.NotFound:
            embed = discord.Embed(
                title="❌ 메시지 오류",
                description=f"링크에서 메시지를 찾을 수 없습니다: {link}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return
        except discord.Forbidden:
            embed = discord.Embed(
                title="🚫 권한 오류",
                description=f"봇이 링크의 메시지를 읽을 권한이 없습니다: {link}",
                color=discord.Color.orange()
            )
            await ctx.send(embed=embed)
            return
        except discord.HTTPException as e:
            embed = discord.Embed(
                title="⚠️ 메시지 오류",
                description=f"메시지를 가져오는 중에 오류가 발생했습니다: {str(e)}",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed)
            return

    # 만약 '지급불가'가 포함된 메시지가 없을 경우, 계속 진행
    user = ctx.author
    user_mention = f"<@{user.id}>"
    user_mention_ex = f"<@!{user.id}>"

    # 당첨내역 채널 가져오기
    lottery_channel = discord.utils.get(ctx.guild.channels, name='합산내역')
    if lottery_channel is None:
        embed = discord.Embed(
            title="❌ 채널 오류",
            description="합산내역 채널을 찾을 수 없습니다.",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
        return

    # 최신 메시지들 중 사용자의 당첨내역 찾기
    found_message = None
    async for message in lottery_channel.history(limit=1000):
        if user_mention in message.content or user_mention_ex in message.content:
            found_message = message.content
            break

    if not found_message:
        embed = discord.Embed(
            title="🔍 지급 내역 없음",
            description=f"{user.mention}님은 이번 주 지급받을 합산 아이템이 없습니다.",
            color=discord.Color.blue()
        )
        await ctx.send(embed=embed)
        return

    # 결과를 자유채팅 채널에 멘션하여 보내기
    embed = discord.Embed(
        title="✅ 지급 신청 완료",
        description=f"<@904332905474564158>에게 지급 신청을 합니다.\n**{found_message}**",
        color=discord.Color.green()
    )
    await ctx.send(embed=embed)

@bot.command(name='합산확인')
async def apply_for_grant(ctx):
    # 해당 명령어가 입력된 채널이 📧｜자유채팅이 아니면 무시
    if ctx.channel.name != '📧｜자유채팅':
        return

    user_id = ctx.author.id
    user_mention = f"<@{user_id}>"  # 일반 멘션
    user_mention_ex = f"<@!{user_id}>"  # 닉네임 변경이 있는 경우의 멘션

    # 당첨내역 채널 가져오기
    lottery_channel = discord.utils.get(ctx.guild.channels, name='합산내역')
    if lottery_channel is None:
        await ctx.send("합산내역 채널을 찾을 수 없습니다.")
        return

    # 최신 메시지들 중 사용자의 당첨내역 찾기
    found_message = None
    async for message in lottery_channel.history(limit=1000):  # 최신 100개 메시지 검색
        if user_mention in message.content or user_mention_ex in message.content:  # 사용자 멘션을 메시지에서 찾기
            found_message = message.content
            break

    if not found_message:
        await ctx.send("합산내역에서 해당 사용자의 메시지를 찾을 수 없습니다.")
        return

    # 결과를 자유채팅 채널에 멘션하여 보내기
    await ctx.send(f"지급신청은 !지급신청을 해주세요. \n **{found_message}**")

@bot.command(name='합산', help='아이템 갯수를 합산합니다.')
async def sum_items(ctx):
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
        return

    channel = ctx.channel
    now = datetime.now(ZoneInfo("Asia/Seoul")).strftime('%Y-%m-%d-%H-%M-%S')
    filename = f'{now}-sum.txt'

    # "합산내역" 채널을 찾아서 모든 메시지를 삭제합니다.
    target_channel = discord.utils.get(ctx.guild.channels, name="합산내역")
    if not target_channel:
        await ctx.send("합산내역 채널을 찾을 수 없습니다.")
        return

    await target_channel.purge(limit=None)

    # 메시지를 파일로 저장합니다.
    with open(filename, 'w', encoding='utf-8') as file:
        async for message in channel.history(limit=1000):
            file.write(f"{message.author.id} {message.content}\n")

    # 파일에서 아이템 합산 로직 실행
    item_dict = defaultdict(lambda: defaultdict(int))
    with open(filename, 'r', encoding='utf-8') as file:
        for line in file:
            line = line.strip()
            if line:
                user_id, *content = line.split(maxsplit=1)
                if content:
                    content = content[0].strip()
                    matches = re.findall(r"<@!?(\d+)> (.+)", content)
                    for match in matches:
                        mention, items = match
                        item_matches = re.findall(r"(\w+) (\d+)", items)
                        for item, count in item_matches:
                            item_dict[mention][item] += int(count)

    # 결과 메시지 생성 및 타겟 채널에 개별적으로 전송
    if item_dict:
        for mention, items in item_dict.items():
            response = f"<@{mention}>님의 합산 결과입니다\n"
            response += "\n".join(f"  {item}: {count}개" for item, count in items.items())
            response += "\n"
            await target_channel.send(response)
    else:
        await target_channel.send("합산할 아이템이 없습니다.")

    # 채널의 모든 메시지 삭제
    await channel.purge(limit=None)

    # 합산 결과 메시지 생성
    if item_dict:
        intro_message = "# ========== 이번 주 룰렛 아이템 당첨 합산이 마무리되었습니다.\n결과는 https://discord.com/channels/1208238905896345620/1208300374478426132 채널에서 !합산확인을 통해 이번주 결과를 확인 부탁드립니다. \n 합산 지급신청은 <@904332905474564158>에게 https://discord.com/channels/1208238905896345620/1208300374478426132 채널에서 !지급신청 부탁드립니다.월요일이 되면 당첨 아이템은 초기화되며, 지급이 불가합니다.\n\n"
        await ctx.send(intro_message)
        
# !아이템지급 명령어 정의 (운영자만 사용 가능)
@bot.command(name='아이템지급')
@commands.has_permissions(administrator=True)
async def give_item(ctx, nickname: str):
    # 합산내역 채널 ID 설정
    summary_channel_id = 123456789012345678  # 실제 채널 ID로 교체 필요
    summary_channel = bot.get_channel(summary_channel_id)

    # 닉네임에 '@'가 없다면 붙이기
    if not nickname.startswith('@'):
        nickname = f'@{nickname}'

    # 서버 멤버 중 해당 닉네임을 가진 멤버 찾기
    member_to_mention = None
    for member in ctx.guild.members:
        if member.display_name == nickname.lstrip('@'):
            member_to_mention = member
            break

    if not member_to_mention:
        await ctx.send(f"{nickname}이라는 닉네임을 가진 사용자를 찾을 수 없습니다.")
        return

    # 합산내역 채널의 메시지들 삭제
    def is_matching_message(message):
        return nickname in message.content

    if summary_channel:
        deleted = await summary_channel.purge(limit=100, check=is_matching_message)
        print(f"Deleted {len(deleted)} messages containing {nickname} in {summary_channel.name}")

    # 멘션 메시지 보내기
    mention_message = f"""
    ✨✨✨ **{member_to_mention.mention}님, 아이템 지급을 시작합니다.** ✨✨✨

    > 접속하지 않은 상태에서 지급신청을 한 경우 당첨된 아이템은 초기화됩니다.
    > 
    > 예외적인 사항없이 **!지급신청**은 게임에 접속하신 상태에서 사용하셔야하며, 접속하지 않은 상태에서 사용하신 불이익은 책임지지 않습니다.
    > 
    > 게임 닉네임과 디스코드 닉네임이 불일치하는 경우 아이템 지급은 절대 불가합니다.
    > 
    > 만약, 이번 주 합산 아이템 내용이 궁금하시다면 **!합산확인** 명령어를 사용해주셔야합니다.
    """

    await ctx.send(mention_message)

# 채널 ID 설정
COUPON_USE_CHANNEL_ID = 1226495859622019122  # ©｜쿠폰사용 채널의 실제 ID
ANNOUNCEMENT_CHANNEL_ID = 1218196371585368114  # 📰｜룰렛당첨 채널의 실제 ID

# 당첨 아이템 리스트와 확률 설정
probability_groups = [
    (70, ["[점검] 골드 10000개","[점검] 플라스틱 20개","[점검] 전설스피어 10개","[점검] 얼티밋스피어 10개","[점검] 케이크 10개","[점검] 제련금속주괴 20개","[점검] 도그코인 2개","[점검] 도그코인 3개","[점검] 도그코인 4개","[점검] 도그코인 5개"]),
    (20, ["[점검] 골드 10000개","[점검] 플라스틱 20개","[점검] 전설스피어 10개","[점검] 얼티밋스피어 10개","[점검] 케이크 10개","[점검] 제련금속주괴 20개","[점검] 도그코인 2개","[점검] 도그코인 3개","[점검] 도그코인 4개","[점검] 도그코인 5개"]),
    (9, ["[점검] 골드 10000개","[점검] 플라스틱 20개","[점검] 전설스피어 10개","[점검] 얼티밋스피어 10개","[점검] 케이크 10개","[점검] 제련금속주괴 20개","[점검] 도그코인 2개","[점검] 도그코인 3개","[점검] 도그코인 4개","[점검] 도그코인 5개"]),
    (1, ["[점검] 골드 10000개","[점검] 플라스틱 20개","[점검] 전설스피어 10개","[점검] 얼티밋스피어 10개","[점검] 케이크 10개","[점검] 제련금속주괴 20개","[점검] 도그코인 2개","[점검] 도그코인 3개","[점검] 도그코인 4개","[점검] 도그코인 5개"])
]

def choose_reward():
    rand = random.randint(1, 100)
    cumulative = 0
    
    for probability, items in probability_groups:
        cumulative += probability
        if rand <= cumulative:
            return random.choice(items)
    
    # 기본 값으로 노말 아이템 제공
    return "[노말] 골드 10000개"

# 점검 쿠폰 사용 명령어
@bot.command(name='점검쿠폰')
async def use_coupon(ctx):
    user_id = ctx.author.id
    
    # 특정 채널에서만 명령어를 사용할 수 있도록 제한
    if ctx.channel.id != COUPON_USE_CHANNEL_ID:
        await ctx.send("❌ 이 명령어는 ©｜쿠폰사용 채널에서만 사용할 수 있습니다.")
        return
    
    # 쿠폰 데이터 로드
    coupon_data = load_coupon_data()

    # 사용자의 쿠폰 수량 확인
    if user_id not in coupon_data or coupon_data[user_id] <= 0:
        await ctx.send("❌ 사용 가능한 점검 쿠폰이 없습니다.")
        return

    # 쿠폰 1개 사용
    coupon_data[user_id] -= 1

    # 룰렛 결과 아이템 추출
    reward_item = choose_reward()
    
    # 쿠폰 데이터 저장
    save_coupon_data(coupon_data)
    
    # 남은 쿠폰 수량
    remaining_coupons = coupon_data[user_id]

    # 임베드 메시지 생성 (사용한 채널에서 보낼 메시지)
    embed = discord.Embed(
        title="🎊 점검 쿠폰 사용 결과!",
        description=f"{ctx.author.mention}님, 점검 쿠폰을 사용하여 다음 아이템을 획득하셨습니다:\n**{reward_item}**\n\n남은 점검 쿠폰: **{remaining_coupons}장**",
        color=discord.Color.green()
    )
    embed.set_footer(text="축하드립니다!")
    embed.set_thumbnail(url="https://example.com/reward-image.png")  # 적절한 이미지를 URL로 추가하세요.

    # 명령어 사용 채널에 결과 전송
    await ctx.send(embed=embed)

    # 📰｜룰렛당첨 채널에 보낼 메시지 내용 생성
    result_message = f"{ctx.author.mention} {reward_item}"

    # 📰｜룰렛당첨 채널에도 같은 메시지 발송
    announcement_channel_id = '1218196371585368114'  # 실제 📰｜룰렛당첨 채널의 ID로 교체
    announcement_channel = bot.get_channel(int(announcement_channel_id))
    if announcement_channel:
        await announcement_channel.send(result_message)
    else:
        print(f"Error: 📰｜룰렛당첨 채널(ID: {announcement_channel_id})을 찾을 수 없습니다.")

first_run = True  # 첫 실행 여부를 확인하기 위한 플래그

# 아이템 및 확률 설정
probabilities = [90, 7, 2, 1]
prizes = [
    [('금속주괴', 1, 10), ('케이크', 5, 10), ('골드', 100, 1000), ('팰스피어', 2, 5), ('메가스피어', 2, 5), ('기가스피어', 1, 2), ('꿀', 1, 1)],
    [('금속주괴', 20, 30), ('케이크', 10, 20), ('골드', 1000, 2000), ('팰스피어', 5, 10), ('메가스피어', 5, 6), ('기가스피어', 2, 3), ('꿀', 1, 2)],
    [('금속주괴', 81, 92), ('케이크', 35, 50), ('골드', 3000, 4000), ('팰스피어', 31, 45), ('메가스피어', 24, 28), ('기가스피어', 16, 20), ('꿀', 8, 10)],
    [('금속주괴', 93, 120), ('케이크', 51, 60), ('골드', 4000, 5000), ('팰스피어', 46, 50), ('메가스피어', 29, 35), ('기가스피어', 21, 25), ('꿀', 11, 15)]
]

def get_random_prize():
    selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
    selected_prize_info = choice(selected_prize_category)
    selected_prize, min_qty, max_qty = selected_prize_info
    qty = randint(min_qty, max_qty)
    return selected_prize, qty

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    bot.loop.create_task(schedule_reset_job(bot.guilds[0]))


RESET_INTERVAL = 60  # 예시: 1분 마다 체크. 실제 사용 시간에 맞게 조정하세요.
RESET_TIME_KST = "23:59"  # 자정 리셋을 원하는 경우 "00:00"으로 설정하세요.

async def schedule_reset_job(guild):
    while True:
        await asyncio.sleep(RESET_INTERVAL)

        now_kst = datetime.now(ZoneInfo('Asia/Seoul'))  # 한국 표준시(KST)로 현재 시간 설정
        reset_time_kst = datetime.strptime(RESET_TIME_KST, "%H:%M").replace(tzinfo=timezone(timedelta(hours=9)))  # 리셋 시간 설정

        # 현재 시간과 리셋 시간 비교
        if now_kst.hour == reset_time_kst.hour and now_kst.minute == reset_time_kst.minute:
            role_name = "White"  # 역할 이름
            role = get(guild.roles, name=role_name)

            if role:
                try:
                    print(f"Total Members in Server: {len(guild.members)}")
                    for member in guild.members:
                        print(f"Checking member {member.name} ({member.id})")
                        if role in member.roles:
                            print(f"Found member {member.name} ({member.id}) with {role_name} role.")
                            grey_role = get(guild.roles, name="Grey")

                            # White 역할을 제거하고 Grey 역할을 부여
                            await member.remove_roles(role)
                            await member.add_roles(grey_role)

                    announcement_channel = get(guild.channels, name="🎈｜일반공지")
                    if announcement_channel:
                        await announcement_channel.send(f"White 등급 유저분들은 자정이 지나 Grey 등급으로 변경되었습니다. 다시 한번 <#1210425834205347890> 메뉴를 통해 신청 부탁드립니다.")
                    else:
                        print("일반-공지 채널을 찾을 수 없습니다.")
                except discord.Forbidden:
                    print("자정 초기화 명령을 실행할 권한이 부족합니다.")
                except Exception as e:
                    print(f'자정 초기화 중 오류 발생: {e}')
            else:
                print(f'{role_name} 역할을 찾을 수 없습니다.')

# 경고 정보를 저장할 파일
warning_file = 'warnings.json'

# 경고 정보를 로드하는 함수
def load_warnings():
    try:
        with open(warning_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# 경고 정보를 저장하는 함수
def save_warnings(warnings):
    with open(warning_file, 'w') as f:
        json.dump(warnings, f, indent=4)

# 경고 정보를 업데이트하는 함수
def update_warnings(user_id, reason):
    warnings = load_warnings()
    if user_id in warnings:
        warnings[user_id]['count'] += 1
    else:
        warnings[user_id] = {'count': 1, 'reasons': []}
    warnings[user_id]['reasons'].append({'reason': reason, 'timestamp': datetime.now().isoformat()})
    save_warnings(warnings)
    return warnings[user_id]['count']

@bot.event
async def on_message(message):
    if "@일렉판다" in message.content:
        print("일렉판다 태그가 포함된 메시지를 수신했습니다.")  # 로그 출력
        # 메시지를 보낸 사용자에게 경고를 발급
        if str(message.author.id) != "884385313257050122":  # 봇 자신을 제외하고 경고를 발급
            reason = "일렉판다-태그"
            warning_count = update_warnings(str(message.author.id), reason)
            await message.channel.send(f"{message.author.mention}님, 현재 경고 {warning_count}회입니다. 경고가 접수되었습니다. 경고 접수 채널을 확인바랍니다. 이의제기는 7일 이내 가능하며 3회 누적 시 벤처리 진행됩니다. [경고 사유: {reason}]")
            print(f"{message.author}에게 경고를 발급하였습니다.")  # 로그 출력
            if warning_count == 3:
                자유채팅_channel = discord.utils.get(message.guild.text_channels, name='📧｜자유채팅')
                관리자_role = discord.utils.get(message.guild.roles, name='관리자')  # 관리자 역할 이름
                if 자유채팅_channel and 관리자_role:
                    await 자유채팅_channel.send(f"{관리자_role.mention} {message.author.mention}님이 최종 경고 3회가 되었습니다.")
                    print("최종 경고가 발급되었습니다.")  # 로그 출력
    await bot.process_commands(message)  # 다른 명령어도 계속 처리되도록 합니다.


@bot.command()
@commands.has_permissions(administrator=True)
async def 경고(ctx, member: discord.Member, *, reason: str):
    if str(member.id) == "884385313257050122":
        reason = "일렉판다-태그"
    
    warning_count = update_warnings(str(member.id), reason)
    
    now = datetime.now().strftime("%Y년 %m월 %d일 %H시 %M분 %S초")
    warning_channel = discord.utils.get(ctx.guild.text_channels, name='경고누적')
    if warning_channel:
        await warning_channel.send(f"[{now}] {member.mention}님 [{reason}]로 인해 현재 경고 {warning_count}회가 누적되었습니다.")
    
    await ctx.send(f"{member.mention}님, 현재 경고 {warning_count}회입니다. 경고가 접수되었습니다. 경고 접수 채널을 확인바랍니다. 이의제기는 7일 이내 가능하며 3회 누적 시 벤처리 진행됩니다. [경고 사유: {reason}]")
    
    if warning_count == 3:
        자유채팅_channel = discord.utils.get(ctx.guild.text_channels, name='📧｜자유채팅')
        관리자_role = discord.utils.get(ctx.guild.roles, name='관리자')  # 관리자 역할 이름
        
        if 자유채팅_channel and 관리자_role:
            await 자유채팅_channel.send(f"{관리자_role.mention} {member.mention}님이 [{now}] 최종 경고 3회가 되었습니다.")

@경고.error
async def 경고_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("이 명령어는 관리자만 사용할 수 있습니다.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("명령어 사용법: !경고 @사용자 사유")
    elif isinstance(error, commands.BadArgument):
        await ctx.send("유효한 사용자 멘션을 제공해주세요.")

recommendations_file = 'recommendations.txt'
dbcoupon_file_path = 'dbcoupon_inventory.txt'
bigcoupon_file_path = 'bigcoupon_inventory.txt'
specific_channel_name = '😻│추천인'  # 명령어를 사용할 수 있는 특정 채널 이름
join_date_threshold = datetime(2024, 1, 20, tzinfo=timezone.utc)  # 기준 날짜

def update_user_dbcoupon_inventory(user_id, count=1):
    """유저 ID로 쿠폰 수를 파일에 기록하거나 업데이트합니다."""
    coupons = {}
    if os.path.exists(dbcoupon_file_path):
        with open(dbcoupon_file_path, "r") as file:
            for line in file:
                user, count_str = line.strip().split(":")
                coupons[user] = int(count_str)  # 파일에서 읽은 값을 정수로 변환

    coupons[user_id] = coupons.get(user_id, 0) + count

    with open(dbcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")

    return coupons[user_id]

def update_user_bigcoupon_inventory(user_id, count=1):
    """유저 ID로 쿠폰 수를 파일에 기록하거나 업데이트합니다."""
    coupons = {}
    if os.path.exists(bigcoupon_file_path):
        with open(bigcoupon_file_path, "r") as file:
            for line in file:
                user, count_str = line.strip().split(":")
                coupons[user] = int(count_str)  # 파일에서 읽은 값을 정수로 변환

    coupons[user_id] = coupons.get(user_id, 0) + count

    with open(bigcoupon_file_path, "w") as file:
        for user, count in coupons.items():
            file.write(f"{user}:{count}\n")

    return coupons[user_id]

def load_recommendations():
    recommendations = {}
    if os.path.exists(recommendations_file):
        with open(recommendations_file, "r") as file:
            for line in file:
                recommender, recommended = line.strip().split(":")
                if recommender not in recommendations:
                    recommendations[recommender] = []
                recommendations[recommender].append(recommended)
    return recommendations

def save_recommendation(recommender_id, recommended_id):
    with open(recommendations_file, "a") as file:
        file.write(f"{recommender_id}:{recommended_id}\n")

@bot.command()
async def 추천인(ctx, *, nickname: str):
    if ctx.channel.name != specific_channel_name:
        await ctx.send(f"이 명령어는 {specific_channel_name} 채널에서만 사용할 수 있습니다.")
        return

    # 사용자가 서버에 가입한 날짜를 확인
    if ctx.author.joined_at is None or ctx.author.joined_at < join_date_threshold:
        await ctx.send(f"{ctx.author.mention}님은 {join_date_threshold.strftime('%Y-%m-%d')} 이후에 가입한 경우에만 추천인을 등록할 수 있습니다.")
        return

    member = discord.utils.find(lambda m: m.display_name == nickname, ctx.guild.members)
    if member is None:
        await ctx.send(f"{nickname}님은 이 서버의 멤버가 아닙니다.")
        return

    recommender_id = str(ctx.author.id)
    recommended_id = str(member.id)

    if recommender_id == recommended_id:
        await ctx.send("자기 자신을 추천할 수 없습니다.")
        return

    recommendations = load_recommendations()

    # 사용자가 이미 추천을 했는지 확인
    if recommender_id in recommendations:
        recommended_user_id = recommendations[recommender_id][0]
        recommended_user = ctx.guild.get_member(int(recommended_user_id))
        recommended_user_nickname = recommended_user.display_name if recommended_user else "알 수 없음"
        await ctx.send(f"이미 {recommended_user_nickname}님을 추천하셨습니다. 더이상 추천인 등록이 불가합니다.")
        return

    # 추천 등록
    if recommender_id not in recommendations:
        recommendations[recommender_id] = []
    recommendations[recommender_id].append(recommended_id)

    save_recommendation(recommender_id, recommended_id)

    recommender_coupons = update_user_dbcoupon_inventory(recommender_id, 3)
    recommended_coupons = update_user_dbcoupon_inventory(recommended_id, 2)

    recommendation_count = sum([1 for rec in recommendations.values() if recommended_id in rec])

    # 추천 받은 횟수가 5, 10, 15, ... 일 때 확정 룰렛 쿠폰 지급
    if recommendation_count % 5 == 0:
        bigcoupon_count = update_user_bigcoupon_inventory(recommended_id)
        await ctx.send(f"{member.mention}님, {recommendation_count}회의 추천을 축하드립니다! 확정 룰렛 쿠폰 1장이 지급되었습니다. "
                       f"현재 보유중인 쿠폰 갯수: {bigcoupon_count}개")

    # 현재 시간 KST로 변환
    KST = timezone(timedelta(hours=9))
    current_time = datetime.now(KST)
    formatted_time = current_time.strftime('%Y-%m-%d %H:%M:%S')

    await ctx.send(f"{ctx.author.mention}님이 {member.mention}님을 추천인으로 등록하셨습니다. "
               f"현재 {member.mention}님이 추천인으로 등록된 횟수는 {recommendation_count}회 입니다.\n"
               f"{ctx.author.mention}님, 총 3개의 쿠폰이 지급되었습니다. 현재 보유중인 쿠폰 갯수: {recommender_coupons}개\n"
               f"{member.mention}님, 총 2개의 쿠폰이 지급되었습니다. 현재 보유중인 쿠폰 갯수: {recommended_coupons}개\n"
               f"쿠폰 사용은 https://discord.com/channels/1208238905896345620/1226495859622019122 채널에서 !쿠폰조회 명령어 입력 후 사용 부탁드립니다. \n"
               f"추천인 등록 시간: {formatted_time} KST")
    

answer = None  # answer 변수를 전역으로 선언



# 사용자 출석 체크 데이터를 저장하기 위한 파일 경로
attendance_file = 'attendance_data.json'

# 날짜별 지급 아이템 리스트
items = [
    "공격 스탯 물약 [1개] + 대박룰렛 쿠폰 2장", "도그 코인 [10개] + 대박룰렛 쿠폰 2장", "테라 스피어 [10개] + 대박룰렛 쿠폰 2장", 
    "도그코인 [20개] + 대박룰렛 쿠폰 2장", "5000골드 + 대박룰렛 쿠폰 2장", "도그코인 [30개] + 대박룰렛 쿠폰 2장", "기력 스탯 물약 [1개] + 대박룰렛 쿠폰 2장"
]

# 출석 체크 데이터를 불러오는 함수
def load_attendance_data():
    if os.path.exists(attendance_file):
        with open(attendance_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

# 출석 체크 데이터를 저장하는 함수
def save_attendance_data(data):
    with open(attendance_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# 출석 체크 데이터를 메모리로 불러옴
attendance_data = load_attendance_data()

reward_applicants = []
file_path = 'coupon_inventory.txt'

def load_coupons():
    try:
        with open(file_path, 'r') as file:
            data = file.read()
            if not data:
                return {}
            return json.loads(data)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}

def save_coupons(coupons):
    with open(file_path, 'w') as file:
        json.dump(coupons, file)


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')


@bot.command(name='파스텔월드의220일을축하해')
async def check_attendance(ctx):
    user = ctx.author
    user_id = str(user.id)
    today = datetime.now().date()
    start_date = datetime(2024, 8, 30).date()
    end_date = datetime(2024, 9, 5).date()

    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    # 시작일 이전에 명령어를 사용한 경우
    if today < start_date:
        await ctx.send(f"[파스텔월드] - {user.mention}, 출석 체크는 {start_date.strftime('%m월 %d일')}부터 가능합니다.")
        return

    # 9월 6일 이후에 명령어를 사용할 수 없도록 설정
    if today > end_date:
        await ctx.send(f"[파스텔월드] - {user.mention}, 09월 6일 이후로는 더 이상 출석 체크를 할 수 없습니다.")
        return

    # 유저가 처음 출석체크를 하는 경우 초기화
    if user_id not in attendance_data:
        attendance_data[user_id] = []

    # 기존 출석 기록 불러오기
    user_attendance = attendance_data[user_id]

    # 출석 체크
    if user_attendance and user_attendance[-1]['date'] == today.isoformat():
        await ctx.send(f"[파스텔월드] - {user.mention}, 오늘 이미 출석 체크를 완료하셨습니다.")
        return

    # 출석 기록 업데이트
    expected_date = start_date + timedelta(days=len(user_attendance))
    if today > expected_date:
        # 중간에 결석한 날짜가 있는 경우
        while expected_date < today:
            user_attendance.append({'date': expected_date.isoformat(), 'status': '실패', 'item': None})
            expected_date += timedelta(days=1)

    # 오늘 날짜 기록 추가
    item = items[len(user_attendance) % len(items)]
    user_attendance.append({'date': today.isoformat(), 'status': '성공', 'item': item})
    attendance_data[user_id] = user_attendance
    save_attendance_data(attendance_data)  # 출석 체크 데이터를 파일에 저장

    # 개근 아이템 확인 및 추가
    if len(user_attendance) == 7 and all(entry['status'] == '성공' for entry in user_attendance):
        user_attendance.append({'date': '개근', 'status': '성공', 'item': '[개근]대박룰렛 쿠폰2장+도그 코인40개'})
        save_attendance_data(attendance_data)

    # 출석 결과 메시지 생성
    message = f"## [파스텔월드] - {user.mention}, {today.strftime('%m월 %d일')} 출석 체크가 완료되었습니다.\n"
    message += f"## 현재 {user.mention}님이 참여하신 [파스텔 월드 220일기념 출석체크] 이벤트 정보를 안내드리니 참고 부탁드립니다.\n\n"
    for i, entry in enumerate(user_attendance, start=1):
        status_message = f"## [{i}일차 {datetime.fromisoformat(entry['date']).strftime('%m.%d')}] - 출석체크 {entry['status']}" if entry['date'] != '개근' else f"[{entry['date']}] - 출석체크 {entry['status']}"
        message += f"{status_message}\n"

    # 지급 예정 아이템 목록 추가
    items_list = [entry['item'] for entry in user_attendance if entry['item']]
    message += "## 지급 아이템\n"
    message += ", ".join([f"[{item}]" for item in items_list])

    await ctx.send(message)

@bot.command(name='출첵')
async def show_attendance(ctx):
    user = ctx.author
    user_id = str(user.id)

    if user_id not in attendance_data or not attendance_data[user_id]:
        await ctx.send(f"{user.mention}님은 출석체크 기록이 없습니다.")
        return

    user_attendance = attendance_data[user_id]
    message = f"{user.mention}님의 7월에도 스텔월드!! 출석 체크 현황:\n\n"

    for i, entry in enumerate(user_attendance, start=1):
        status_message = f"[{i}일차 {datetime.fromisoformat(entry['date']).strftime('%m.%d')}] - 출석체크 {entry['status']}" if entry['date'] != '개근' else f"[{entry['date']}] - 출석체크 {entry['status']}"
        message += f"{status_message}\n"

    # 지급 예정 아이템 목록 추가
    items_list = [entry['item'] for entry in user_attendance if entry['item']]
    message += "지급 예정 아이템\n"
    message += ", ".join([f"[{item}]" for item in items_list])

    await ctx.send(message)

@bot.command(name='출첵확인')
async def check_all_attendance(ctx):
    if not attendance_data:
        await ctx.send("아직 출석 체크를 한 유저가 없습니다.")
        return

    message = ""
    for user_id, user_attendance in attendance_data.items():
        user = await bot.fetch_user(user_id)
        member = ctx.guild.get_member(int(user_id))
        if member:
            mention = member.mention  # 유저를 태그하기 위해 mention 사용
        else:
            mention = user.mention  # 만약 member가 없으면 일반 유저 태그 사용
        
        # 날짜와 아이템 리스트 생성
        dates = [datetime.fromisoformat(entry['date']).strftime('%m월 %d일') for entry in user_attendance if entry['status'] == '성공' and entry['date'] != '개근']
        items_list = [entry['item'] for entry in user_attendance if entry['item']]
        if len(user_attendance) == 8 and all(entry['status'] == '성공' for entry in user_attendance[:-1]):
            items_list.append("[개근]대박룰렛 쿠폰2장+도그 코인40개")
        
        message_part = f"{mention} - {', '.join(dates)} 참여\n지급 대상 아이템 : {', '.join(items_list)}\n\n"
        
        # 메시지 파트가 2000자를 넘을 수 있으므로 체크
        if len(message) + len(message_part) > 2000:
            await ctx.send(message)  # 기존 메시지를 전송하고
            message = ""  # 메시지를 초기화
        
        message += message_part  # 메시지를 추가

    # 마지막 남은 메시지 전송
    if message:
        await ctx.send(message)

@bot.command(name='뉴시즌출첵')
@commands.has_permissions(administrator=True)
async def update_attendance(ctx, nickname: str, day: int):
    user = None
    for member in ctx.guild.members:
        if member.display_name == nickname:
            user = member
            break

    if not user:
        await ctx.send(f"{nickname} 닉네임을 가진 사용자를 찾을 수 없습니다.")
        return

    user_id = str(user.id)
    start_date = datetime(2024, 6, 20).date()
    target_date = start_date + timedelta(days=day - 1)
    end_date = datetime(2024, 6, 27).date()
    today = datetime.now().date()

    # target_date가 end_date보다 크거나 today보다 크면 안 된다.
    if target_date > end_date or target_date >= today:
        await ctx.send(f"{day}일자는 출석 체크를 업데이트할 수 없습니다.")
        return

    if user_id not in attendance_data:
        attendance_data[user_id] = []

    user_attendance = attendance_data[user_id]

    # 출석 체크 기록 업데이트
    updated = False
    for entry in user_attendance:
        if entry['date'] == target_date.isoformat():
            if entry['status'] == '실패':
                entry['status'] = '성공'
                entry['item'] = items[(day - 1) % len(items)]
                updated = True
                break
            else:
                await ctx.send(f"{nickname}님의 {target_date.strftime('%m월 %d일')} 출석 체크는 이미 성공 상태입니다.")
                return

    # 기록이 없으면 새로 추가
    if not updated:
        user_attendance.append({'date': target_date.isoformat(), 'status': '성공', 'item': items[(day - 1) % len(items)]})

    # 개근 아이템 확인 및 추가
    if len(user_attendance) == 7 and all(entry['status'] == '성공' for entry in user_attendance):
        user_attendance.append({'date': '개근', 'status': '성공', 'item': '[개근]대박룰렛 쿠폰2장+도그 코인40개'})

    attendance_data[user_id] = user_attendance
    save_attendance_data(attendance_data)

    await ctx.send(f"{nickname}님의 {target_date.strftime('%m월 %d일')} 출석 체크가 성공으로 업데이트되었습니다.")


@tasks.loop(seconds=60)
async def scheduled_messagesq():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    channel_name = "💦｜점검보상"
    channel = discord.utils.get(bot.get_all_channels(), name=channel_name)

    if not channel:
        print(f"채널 '{channel_name}'을(를) 찾을 수 없습니다.")
        return

    if now.strftime('%H:%M') in ['08:58', '20:58', '14:58', '02:58']:
        await channel.send("# [자동 리붓] : 자동리붓 시간이 되어 보상이 준비되었습니다.")
        reward_applicants.clear()
        current_time = now.strftime("%Y년 %m월 %d일 %H시 %M분")
        await channel.send("# 안녕하세요 PASTEL WORLD 유저 여러분 리붓 보상 관련이 준비되었습니다.")
        await channel.send(f"## [{current_time}] 보상으로 인한 룰렛쿠폰이 지급 될 예정입니다.")
        await channel.send("# 주의사항\n- **디스코드 닉네임**과 **게임 닉네임**은 동일하여야 합니다.\n"
                           "- 점검 **보상은 리붓 시간동안만** 지급됩니다.\n"
                           "- 보상은 해당 **메시지가 등록된 후 7분 이내까지만 신청 가능**합니다.\n"
                           "- 보상 신청 방법은 해당 채널에 **보상** 이라는 메시지를 입력 부탁드립니다.")

        await asyncio.sleep(480)
        async for msg in channel.history(limit=None):
            await msg.delete()
        await channel.send("## ======== 신청이 마감되었습니다. 이후 신청하신 분은 지급 대상이 되지 않습니다. ========")

        for member in reward_applicants:
            coupons = load_coupons()
            coupons[member.display_name] = coupons.get(member.display_name, 0) + 3
            save_coupons(coupons)
            await channel.send(f"{member.mention}님, **리붓 보상** 대박 룰렛 쿠폰이 지급되었습니다. "
                               f"©｜쿠폰사용 채널에서 !대박룰렛을 입력해주세요. **[현재 보유 중인 쿠폰: {coupons[member.display_name]}개]")

        await asyncio.sleep(600)
        async for msg in channel.history(limit=None):
            await msg.delete()
        reward_applicants.clear()

def get_random_prize():
    selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
    selected_prize_info = choice(selected_prize_category)
    selected_prize, min_qty, max_qty = selected_prize_info
    qty = randint(min_qty, max_qty)
    return selected_prize, qty

async def trigger_event():
    channel = discord.utils.get(bot.get_all_channels(), name='📧｜자유채팅')
    if channel:
        kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
        view = View()
        button = Button(label="파스텔 버튼 누르기!", style=discord.ButtonStyle.danger)
        button.timeout = None

        async def button_callback(interaction):
            selected_prize, qty = get_random_prize()
            kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
            await interaction.response.edit_message(content=f"## 🌟[{kst_now}] 버튼 이벤트 당첨자는 {interaction.user.mention}님 입니다!🌟\n ### 당첨 결과는 {selected_prize} {qty}개 입니다! \n매주 토요일 오후 8시부터 일요일 23시 전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가 되면, 당첨 아이템은 초기화됩니다. **★경과 시 지급 불가!★**", view=None)
            winning_channel = discord.utils.get(interaction.guild.channels, name="💞｜당첨내역")
            if winning_channel:
                await winning_channel.send(f"{interaction.user.mention} [버튼] {selected_prize} {qty}개")
            # 버튼이 눌렸으므로 5분 후의 메시지 수정 취소
            nonlocal message_edit_task
            if message_edit_task:
                message_edit_task.cancel()

        button.callback = button_callback
        view.add_item(button)
        # 메시지 전송
        message = await channel.send(f"# {kst_now} 🌟파스텔 버튼 이벤트 출현!🌟\n 제한시간: 5분! 시간 경과 시 버튼을 눌러도 작동하지 않습니다.", view=view)

        # 5분 후에 메시지 수정
        async def edit_message():
            await asyncio.sleep(300)
            await message.edit(content=f"## 🌟[{kst_now}] 타임 당첨자는 아무도 없습니다. 다음 타임을 기다려주세요! 🌟")

        message_edit_task = asyncio.create_task(edit_message())

def get_random_prize():
    selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
    selected_prize_info = choice(selected_prize_category)
    selected_prize, min_qty, max_qty = selected_prize_info
    qty = randint(min_qty, max_qty)
    return selected_prize, qty

async def trigger_event():
    channel = discord.utils.get(bot.get_all_channels(), name='📧｜자유채팅')
    if channel:
        kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
        view = View()
        button = Button(label="파스텔 버튼 누르기!", style=discord.ButtonStyle.danger)
        button.timeout = None

        async def button_callback(interaction):
            selected_prize, qty = get_random_prize()
            kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
            await interaction.response.edit_message(content=f"## 🌟[{kst_now}] 버튼 이벤트 당첨자는 {interaction.user.mention}님 입니다!🌟\n ### 당첨 결과는 {selected_prize} {qty}개 입니다! \n매주 토요일 오후 8시부터 일요일 23시 전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가 되면, 당첨 아이템은 초기화됩니다. **★경과 시 지급 불가!★**", view=None)
            winning_channel = discord.utils.get(interaction.guild.channels, name="💞｜당첨내역")
            if winning_channel:
                await winning_channel.send(f"{interaction.user.mention} [버튼] {selected_prize} {qty}개")
            # 버튼이 눌렸으므로 5분 후의 메시지 수정 취소
            nonlocal message_edit_task
            if message_edit_task:
                message_edit_task.cancel()

        button.callback = button_callback
        view.add_item(button)
        # 메시지 전송
        message = await channel.send(f"# {kst_now} 🌟파스텔 버튼 이벤트 출현!🌟\n 제한시간: 5분! 시간 경과 시 버튼을 눌러도 작동하지 않습니다.", view=view)

        # 5분 후에 메시지 수정
        async def edit_message():
            await asyncio.sleep(300)
            await message.edit(content=f"## 🌟[{kst_now}] 타임 당첨자는 아무도 없습니다. 다음 타임을 기다려주세요! 🌟")

        message_edit_task = asyncio.create_task(edit_message())

def get_random_prize():
    selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
    selected_prize_info = choice(selected_prize_category)
    selected_prize, min_qty, max_qty = selected_prize_info
    qty = randint(min_qty, max_qty)
    return selected_prize, qty

async def trigger_event():
    channel = discord.utils.get(bot.get_all_channels(), name='📧｜자유채팅')
    if channel:
        kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
        view = View()
        button = Button(label="파스텔 버튼 누르기!", style=discord.ButtonStyle.danger)
        button.timeout = None

        async def button_callback(interaction):
            selected_prize, qty = get_random_prize()
            kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
            await interaction.response.edit_message(content=f"## 🌟[{kst_now}] 버튼 이벤트 당첨자는 {interaction.user.mention}님 입니다!🌟\n ### 당첨 결과는 {selected_prize} {qty}개 입니다! \n매주 토요일 오후 8시부터 일요일 23시 전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가 되면, 당첨 아이템은 초기화됩니다. **★경과 시 지급 불가!★**", view=None)
            winning_channel = discord.utils.get(interaction.guild.channels, name="💞｜당첨내역")
            if winning_channel:
                await winning_channel.send(f"{interaction.user.mention} [버튼] {selected_prize} {qty}개")
            # 버튼이 눌렸으므로 5분 후의 메시지 수정 취소
            nonlocal message_edit_task
            if message_edit_task:
                message_edit_task.cancel()

        button.callback = button_callback
        view.add_item(button)
        # 메시지 전송
        message = await channel.send(f"# {kst_now} 🌟파스텔 버튼 이벤트 출현!🌟\n 제한시간: 5분! 시간 경과 시 버튼을 눌러도 작동하지 않습니다.", view=view)

        # 5분 후에 메시지 수정
        async def edit_message():
            await asyncio.sleep(300)
            await message.edit(content=f"## 🌟[{kst_now}] 타임 당첨자는 아무도 없습니다. 다음 타임을 기다려주세요! 🌟")

        message_edit_task = asyncio.create_task(edit_message())

@bot.command()
@commands.has_permissions(administrator=True)
async def 퀴즈출제(ctx):
    """퀴즈를 출제하는 명령어"""
    global answer, quiz_creator, quiztype
    words = ["고릴라", "오랑우탄", "햄스터", "다람쥐", "독수리", "메추라기", "고등어", "오징어", "랍스터", "올리브", "아몬드", "헤이즐넛", "마카다미아넛", "바나나", "블루베리", "복숭아", "파인애플", "오렌지", "파파야", "아보카도", "파슬리", "미나리", "양배추", "고구마", "호박씨", "다시마", "깍두기", "배추김치",
 "콩나물", "토마토", "오이피클", "로즈마리", "고추장", "된장찌개", "삼계탕", "갈비탕", "비빔밥", "떡볶이", "파스타", "샐러드", "샌드위치", "스테이크", "아이스크림", "케이크", "초콜릿","크로와상", "마카롱",
"요구르트", "생크림", "훈제연어", "연어회", "장어구이", "해산물", "오징어숙회", "가자미",  "홍합살", "전복죽", "땅콩버터", "바나나우유",  "블루베리스무디", "바나나", "참외", "오렌지", "파인애플", "청포도", "파파야", "블루베리", "라즈베리", "블랙베리", "아보카도", "파프리카", "토마토", "고구마", "로즈마리", "파슬리", "레몬밤", "캐슈넛", "피스타치오", "헤이즐넛"]
    word = random.choice(words)

    # 단어를 랜덤으로 고르고 1글자를 랜덤으로 가리기
    hidden_index = random.choice(range(len(word)))
    hint = word[:hidden_index] + 'O' + word[hidden_index+1:]

    answer = word  # answer 변수에 정답을 설정
    quiz_creator = ctx.author  # 퀴즈 출제자를 저장
    quiztype = "퀴즈출제"

    await ctx.send(f"{quiz_creator.mention}님이 퀴즈를 출제하였습니다! 아래 단어를 맞추시면 선물이 펑펑!.\n힌트: {hint}")
    await ctx.send(f"정답을 입력해주세요!-> !정답 단어")
    # 3분 후에 퀴즈 종료
    await asyncio.sleep(180)
    if answer is not None:
        await ctx.send("퀴즈 시간이 종료되었습니다!")
        answer = None  # 퀴즈 종료 시 answer 변수를 None으로 설정

# 각 등급별 사용 횟수 제한
LIMITS = {
    "Mint": 5,
    "Black": 4,
    "Orange": 3,
    "Yellow": 3,
    "Green": 3,
    "Blue": 2
}

USAGE_FILE = "usage_counts.json"

# 사용자별 명령어 사용 횟수를 로컬 파일에 저장하고 불러오기
def load_usage_counts():
    try:
        with open(USAGE_FILE, 'r') as file:
            return json.load(file)
    except FileNotFoundError:
        return {}

def save_usage_counts(usage_counts):
    with open(USAGE_FILE, 'w') as file:
        json.dump(usage_counts, file)

usage_counts = load_usage_counts()
last_reset = datetime.now().date()

@bot.command()
async def 컬러퀴즈(ctx):
    """퀴즈를 출제하는 명령어"""
    global answer, quiz_creator, last_reset, usage_counts, quiztype

    # 날짜가 변경되면 사용 횟수를 초기화
    if datetime.now().date() != last_reset:
        usage_counts.clear()
        last_reset = datetime.now().date()
        save_usage_counts(usage_counts)

    # 사용자 등급 확인
    member = ctx.author
    role_names = [role.name for role in member.roles]
    allowed_roles = LIMITS.keys()
    user_role = None
    quiztype = "컬러퀴즈"

    for role in role_names:
        if role in allowed_roles:
            user_role = role
            break

    if user_role is None:
        await ctx.send(f"{ctx.author.mention}님은 이 명령어를 사용할 수 없습니다.")
        return

    # 사용 횟수 확인 및 제한
    if user_role not in usage_counts:
        usage_counts[user_role] = {}

    if str(member.id) not in usage_counts[user_role]:
        usage_counts[user_role][str(member.id)] = 0

    if usage_counts[user_role][str(member.id)] >= LIMITS[user_role]:
        await ctx.send(f"{ctx.author.mention}님은 오늘 이 명령어를 더 이상 사용할 수 없습니다.")
        return

    remaining_attempts = LIMITS[user_role] - usage_counts[user_role][str(member.id)]

    usage_counts[user_role][str(member.id)] += 1
    save_usage_counts(usage_counts)

    words = ["고릴라", "오랑우탄", "햄스터", "다람쥐", "독수리", "메추라기", "고등어", "오징어", "랍스터", "올리브", "아몬드", "헤이즐넛", "마카다미아넛", "바나나", "블루베리", "복숭아", "파인애플", "오렌지", "파파야", "아보카도", "파슬리", "미나리", "양배추", "고구마", "호박씨", "다시마", "깍두기", "배추김치",
             "콩나물", "토마토", "오이피클", "로즈마리", "고추장", "된장찌개", "삼계탕", "갈비탕", "비빔밥", "떡볶이", "파스타", "샐러드", "샌드위치", "스테이크", "아이스크림", "케이크", "초콜릿", "크로와상", "마카롱",
             "요구르트", "생크림", "훈제연어", "연어회", "장어구이", "해산물", "오징어숙회", "가자미",  "홍합살", "전복죽", "땅콩버터", "바나나우유",  "블루베리스무디", "바나나", "참외", "오렌지", "파인애플", "청포도", "파파야", "블루베리", "라즈베리", "블랙베리", "아보카도", "파프리카", "토마토", "고구마", "로즈마리", "파슬리", "레몬밤", "캐슈넛", "피스타치오", "헤이즐넛"]

    word = random.choice(words)

    # 단어를 랜덤으로 고르고 1글자를 랜덤으로 가리기
    hidden_index = random.choice(range(len(word)))
    hint = word[:hidden_index] + 'O' + word[hidden_index+1:]

    answer = word  # answer 변수에 정답을 설정
    quiz_creator = ctx.author  # 퀴즈 출제자를 저장

    await ctx.send(f"{quiz_creator.mention}님이 퀴즈를 출제하였습니다! 아래 단어를 맞추시면 선물이 펑펑!.\n힌트: {hint}")
    await ctx.send(f"정답을 입력해주세요! -> !정답 단어")

    # 남은 출제 가능 횟수 알려주기
    await ctx.send(f"{ctx.author.mention}님의 오늘 남은 출제 가능 횟수는 {remaining_attempts - 1}회입니다.")

    # 3분 후에 퀴즈 종료
    await asyncio.sleep(180)
    if answer is not None:
        await ctx.send("퀴즈 시간이 종료되었습니다!")
        answer = None  # 퀴즈 종료 시 answer 변수를 None으로 설정

@bot.command()
@commands.has_permissions(administrator=True)
async def 대박퀴즈(ctx):
    """대박퀴즈를 출제하는 명령어"""
    global answer, quiz_creator, quiztype

    words = ["가면놀이", "갈팡질팡", "갑오징어", "거울속나", "건곤일척", "검은기사", "경상남도", "경상북도", "계란말이",
             "고기고기", "고등학교", "고등학생", "고슴도치", "곤지곤지", "곰돌이푸", "곰실곰실", "공부의신", "국가대표", "국민연금",
             "국어사전", "귀염둥이", "귀차니즘", "금상첨화", "기말고사", "기억상실", "김치라면", "깐따삐아", "꼬깃꼬깃", "꼬마공주",
             "꼬마신사", "꿀벌마야", "꿈을꾸다", "난공불락", "냄비뚜껑", "네트워크", "노트필기", "눈의여왕", "뉴발란스", "다이어리",
             "달바라기", "달빛가루", "달콤짭짤", "닭가슴살", "닭대가리", "대형마트", "더블에스", "던킨도넛", "데스노트", "도깨비불",
             "도라에몽", "동그라미", "두런두런", "뒤뚱뒤뚱", "딸기소녀", "딸기우유", "라라시아", "러브러브", "러브비트", "러브홀릭",
             "레드카드", "레스토랑", "레인보우", "롯데마트", "르네상스", "마스크팩", "마시마로", "마요네즈", "마이너스", "마이동풍",
             "막상막하", "만리장성", "매니큐어", "메추리알", "멘탈붕괴", "멜크리오", "명명백백", "모래시계", "모태솔로", "몽글몽글",
             "몽실몽실", "무림황제", "무지개떡", "무한도전", "문어머리", "물레방아", "물컹물컹", "뮤직뱅크", "미니어처", "바나나맛",
             "바다여행", "바람둥이", "바리공주", "바보온달", "바보이반", "바이올렛", "박하사탕", "반짝반짝", "방긋방긋", "방방곡곡",
             "방울방울", "백과사전", "백설공주", "밸런타인", "버블버블", "버터구이", "베르나르", "벨제비트", "별바라기", "별주부전",
             "보드게임", "보라돌이", "부어부어", "북두칠성", "분수대장", "불고기버", "불타는밤", "비눗거품", "비닐봉투", "비빔국수",
             "비타민제", "빙글빙글", "빨간구두", "빨간머리", "빨간모자", "빵긋빵긋", "빵빠레빵", "사랑해요", "사이언스", "살랑살랑",
             "상큼발칙", "새콤달콤", "생긋생긋", "서든어택", "선덕여왕", "성형미인", "센티멘탈", "소녀시대", "소주한잔", "소탐대실",
             "슈퍼노바", "스나이퍼", "스마트폰", "스믈스믈", "스타워즈", "스타일링", "스타트업", "스테이크", "스파게티", "스펙트럼",
             "스포츠카", "슬림라인", "시시껄렁", "시시비비", "신데렐라", "신사임당", "신혼여행", "싱숭생수", "아기자기", "아기팬더",
             "아들뭐해", "아롱다롱", "아름아름", "아리따움", "아스피린", "아이디어", "아이리스", "아이스티", "아침이슬", "아카시아",
             "아프리카", "악세서리", "안성탕면", "알록달록", "알바천국", "알쏭달쏭", "알콩달콩", "애니타임", "어벤져스", "어쿠스틱",
             "엄지공주", "에이핑크", "에일리언", "여유만발", "연금술사", "연지곤지", "영어사전", "예쁨둥이", "오늘도난", "오락가락",
             "오토바이", "오피스텔", "올망졸망", "옹긋쫑긋", "옹알옹알", "와이파이", "요로코롬", "요리조리", "요술램프", "요술부채",
             "요조숙녀", "용쟁호투", "우두머리", "우락부락", "우렁각시", "우주소년", "울룩불룩", "원자폭탄", "위풍당당", "윈드러너",
             "유라시아", "유리구슬", "유리그릇", "유리상자", "유성타임", "유아독존", "이런저런", "이렁저렁", "이만저만", "이솝우화",
             "이심전심", "이카루스", "인공지능", "인기가요", "인어공주", "인페르노", "인형의꿈", "일기예보", "일어사전", "자린고비",
             "자유분방", "자유시간", "장화홍련", "재즈카페", "전래동화", "전자기기", "전자렌지", "전자사전", "전전긍긍", "정정당당",
             "종이봉투", "주렁주렁", "중간고사", "즐겨찾기", "질주본능", "천사날개", "천상천하", "천일야화", "청둥오리", "청춘고백",
             "청풍명월", "체리앵두", "초등학교", "초등학생", "초롱초롱", "초코우유", "추석연휴", "충청남도", "충청북도", "치즈케익",
             "치카치카", "캐리커쳐", "커뮤니티", "커피우유", "코델리아", "코드네임", "코카콜라", "콩쥐팥쥐", "크래프트", "크레센도",
             "크레파스", "크리스탈", "클라우드", "테디베어", "텔레비전", "투명구슬", "트레이닝", "특수문자", "티키타카", "파도타기",
             "팝업노트", "팽이버섯", "페르소나", "평강공주", "포스트잇", "퐁당퐁당", "푸른하늘", "풀스크린", "풀잎이슬", "프로젝트",
             "프로포즈", "프링글스", "플라스틱", "플란다스", "플로렌스", "피노키오", "필기도구", "핑크홀릭", "하늘색꿈", "하루살이",
             "하루하루", "하모니카", "하얀고래", "하얀장미", "하이마트", "하하호호", "할리우드", "할아버지", "해님달님", "해바라기",
             "핸드믹서", "허리케인", "허수아비", "허허실실", "헤이보이", "헤이즐넛", "호동왕자", "호두까기", "홍길동전", "효녀심청",
             "휴머니즘", "흥부놀부"]

    word = random.choice(words)
    hidden_indices = random.sample(range(len(word)), 2)
    hint = ''.join('O' if i in hidden_indices else char for i, char in enumerate(word))

    answer = word  # answer 변수에 정답을 설정
    quiz_creator = ctx.author  # 퀴즈 출제자를 저장
    quiztype = "대박퀴즈"
    await ctx.send(f"{quiz_creator.mention}님이 대박퀴즈를 출제하였습니다! \n 아래 단어를 맞추시면 선물이 펑펑!.\n힌트: {hint} - 60초간 정답자가 없는 경우 1글자가 추가로 공개됩니다.")
    await ctx.send(f"정답을 입력해주세요! -> !정답 단어")

    for i in range(2):
        await asyncio.sleep(60)
        if answer is None:
            return
        # 가려진 문자 하나 공개
        revealed_index = hidden_indices.pop()
        hint = hint[:revealed_index] + word[revealed_index] + hint[revealed_index+1:]
        await ctx.send(f"60초 경과! 추가 힌트: {hint}")

    if answer is not None:
        await ctx.send("퀴즈 시간이 종료되었습니다!")
        answer = None  # 퀴즈 종료 시 answer 변수를 None으로 설정

@bot.command()
async def 정답(ctx, user_answer: str):
    global answer, quiz_creator, quiztype  # quiztype도 글로벌 변수로 설정

    if answer is None:
        await ctx.send(f"{ctx.author.mention}님, 현재 진행 중인 퀴즈가 없거나 이미 정답자가 나왔습니다. 다음 퀴즈를 기다려주세요.")
        return

    if ctx.author == quiz_creator:
        await ctx.send(f"{ctx.author.mention}님, 본인이 출제한 문제에는 정답을 맞출 수 없습니다.")
        return

    if user_answer.lower() == answer.lower():
        if quiztype == "대박퀴즈":
            selected_prize_1, qty_1 = get_random_prize()
            selected_prize_2, qty_2 = get_random_prize()
            prize_message_1 = f"[대박 퀴즈 보상] {selected_prize_1} {qty_1}개"
            prize_message_2 = f"[대박 퀴즈 보상] {selected_prize_2} {qty_2}개"
            embed = discord.Embed(
                title="퀴즈 정답 발표",
                # description=f"{ctx.author.mention}님, 정답입니다!",
                description=f"{ctx.author.mention}님, 정답입니다! \n**당첨 결과**\n{prize_message_1}\n{prize_message_2}\n\n**당첨된 아이템**\n매주 토요일 오후 8시부터 일요일 23시 전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가 되면, 당첨 아이템은 초기화됩니다.\n**★경과 시 지급 불가!★**",
                color=discord.Color.green()
            )
        else:
            selected_prize, qty = get_random_prize()
            prize_message = f"[퀴즈 보상] {selected_prize} {qty}개"
            embed = discord.Embed(
                title="퀴즈 정답 발표",
                description=f"{ctx.author.mention}님, 정답입니다! \n **당첨 결과**\n{prize_message}\n\n**당첨된 아이템**\n매주 토요일 오후 8시부터 일요일 23시 전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가 되면, 당첨 아이템은 초기화됩니다.\n**★경과 시 지급 불가!★**",
                color=discord.Color.green()
            )

        # await ctx.send(f"{quiz_creator.mention}님이 출제한 퀴즈의 정답자는 {ctx.author.mention}님 입니다")
        await ctx.send(embed=embed)

        # Send prize message to the specific channel
        prize_channel_id = 1218196371585368114  # Replace with the actual channel ID
        prize_channel = bot.get_channel(prize_channel_id)
        if prize_channel:
            if quiztype == "대박퀴즈":
                await prize_channel.send(f"{ctx.author.mention} [퀴즈] {selected_prize_1} {qty_1}개")
                await prize_channel.send(f"{ctx.author.mention} [퀴즈] {selected_prize_2} {qty_2}개")
            else:
                await prize_channel.send(f"{ctx.author.mention} [퀴즈] {selected_prize} {qty}개")

        answer = None  # 퀴즈 종료 시 answer 변수를 None으로 설정
    else:
        await ctx.send(f"{ctx.author.mention}님, 정답이 아닙니다. 다시 시도해주세요!")


# 파일 경로 정의
bigcoupon_file_path = 'bigcoupon_inventory.txt'
dbcoupon_file_path = 'dbcoupon_inventory.txt'
supercoupon_file_path = 'supercoupon_inventory.txt'
fixcoupon_file_path = 'fixcoupon.txt'  # 정확한 파일 이름을 확인하세요.

@bot.command(name='쿠폰확인')
async def check_all_coupons(ctx, *, member: discord.Member = None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    
    # 다양한 쿠폰 유형과 파일 경로 정의
    dbcoupontypes = {
        "대박 룰렛 쿠폰": dbcoupon_file_path,
        "확정 룰렛 쿠폰": bigcoupon_file_path,
        "대박 확정 룰렛 쿠폰": supercoupon_file_path
    }
    
    coupons = {coupon_type: 0 for coupon_type in dbcoupontypes}
    
    # 각 파일을 읽어 사용자가 보유한 쿠폰 수를 계산
    for coupon_type, path in dbcoupontypes.items():
        # 파일이 존재하는지 확인
        print(f"Checking file path: {path} - Exists: {os.path.exists(path)}")  # 디버깅 추가
        if os.path.exists(path):
            try:
                with open(path, 'r') as file:
                    for line in file:
                        parts = line.strip().split(":")
                        if len(parts) == 2:
                            user, count = parts
                            print(f"Checking {coupon_type} - File user: {user}, count: {count}, target user: {user_id}")  # 디버깅 메시지
                            if user.strip() == user_id:
                                coupons[coupon_type] = int(count.strip())
                                break
            except Exception as e:
                print(f"Error reading file {path}: {e}")
    
    # Embed 생성
    embed = discord.Embed(title="총 보유 쿠폰",
                          description=f"{member.mention} 님의 쿠폰 보유 현황을 안내드립니다.",
                          color=discord.Color.green())
    
    for coupon_type, count in coupons.items():
        embed.add_field(name=coupon_type, value=f"{count} 장", inline=False)
    
    await ctx.send(embed=embed)

# 점검 쿠폰 파일 경로
fixcoupons_file_path = 'fixcoupons.txt'

@bot.command(name='쿠폰쿠폰')
async def check_fix_coupons(ctx, *, member: discord.Member = None):
    if member is None:
        member = ctx.author
    user_id = str(member.id)
    
    fix_coupons = 0

    # 점검 쿠폰 파일 읽기
    if os.path.exists(fixcoupons_file_path):
        try:
            with open(fixcoupons_file_path, 'r') as file:
                for line in file.readlines():
                    parts = line.strip().split("/")
                    if len(parts) == 2:
                        file_user_id, count = parts
                        if file_user_id.strip() == user_id:
                            fix_coupons = int(count.strip())
                            break
        except Exception as e:
            print(f"Error reading file {fixcoupons_file_path}: {e}")
    
    # Embed 생성
    embed = discord.Embed(
        title="점검 쿠폰 조회 결과",
        description=f"{member.mention} 님의 점검 쿠폰 수량입니다.",
        color=discord.Color.blue()
    )
    embed.add_field(name="점검 쿠폰", value=f"{fix_coupons} 장", inline=False)
    
    await ctx.send(embed=embed)

intents = discord.Intents.default()
intents.message_content = True  # To enable reading message content

@bot.command(name='카운트다운')
async def countdown(ctx, seconds: int, *, message: str):
    minutes = seconds // 60
    seconds = seconds % 60
    countdown_message = f"# **{message} [ {minutes}분 {seconds}초 ] 남았습니다.**"

    countdown_msg = await ctx.send(countdown_message)
    
    while seconds > 0 or minutes > 0:
        await asyncio.sleep(1)
        if seconds == 0:
            if minutes > 0:
                minutes -= 1
                seconds = 59
        else:
            seconds -= 1

        countdown_message = f"# **{message} [ {minutes}분 {seconds}초 ] 남았습니다.**"
        await countdown_msg.edit(content=countdown_message)

    await countdown_msg.edit(content=f"**{message} [ 0분 0초 ] 남았습니다.**")
    await ctx.send("**시작 합니다!**")

OPENAI_API_KEY = 'sk-proj-xwv12jJr0s9x9BsliiUYT3BlbkFJup5G1E9e049h9kuoGZIr'

# 봇이 준비되었을 때 실행되는 이벤트 핸들러
@client.event
async def on_ready():
    print(f'We have logged in as {client.user}')

# 봇이 메시지를 받았을 때 실행되는 이벤트 핸들러
@client.event
async def on_message(message):
    # 메시지를 보낸 사람이 봇 자신이면 무시
    if message.author == client.user:
        return

    if message.content.startswith('!안녕'):
        await message.channel.send('안녕하세요!')

# 관리자 확인 데코레이터
def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# 데이터 파일 경로
DATA_FILE = "pp_data.json"

def load_data():
    if not os.path.exists(DATA_FILE):
        return {}
    with open(DATA_FILE, "r", encoding="utf-8") as file:
        return json.load(file)

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=4)

def format_number(number):
    return "{:,}".format(number)

def is_admin():
    async def predicate(ctx):
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

# 채널과 메시지 ID 매핑
CHANNEL_MESSAGE_MAP = {
    "A-1": 1238723136535400529,
    "A-2": 1238723138049544283
}


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    bot.loop.create_task(send_random_message())
    scheduled_messages.start()  # 스케줄러 시작
    await schedule_next_event()
    scheduled_messagesq.start()

@bot.command()
@is_admin()
async def 등록(ctx, nickname: str, amount: int):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    # 서버 내에서 해당 닉네임을 가진 멤버를 찾습니다.
    member = discord.utils.get(ctx.guild.members, display_name=nickname)
    if not member:
        await ctx.send(f"❌ '{nickname}'이라는 디스플레이 이름을 가진 사용자는 서버에 존재하지 않습니다.")
        return

    user_id = str(member.id)
    data = load_data()
    
    # 기본값을 설정하여 데이터가 항상 필요한 키를 포함하도록 합니다.
    user_data = data.get(user_id, {
        "nickname": nickname,
        "pp": 0,
        "이벤트 PP": 0,
        "충전 내역": [],  # 기본값으로 빈 리스트 설정
        "사용 내역": []   # 기본값으로 빈 리스트 설정
    })

    # pp와 이벤트 PP의 기본값을 설정합니다.
    user_data.setdefault("pp", 0)
    user_data.setdefault("이벤트 PP", 0)
    user_data.setdefault("충전 내역", [])  # 충전 내역 키가 없으면 빈 리스트로 초기화
    user_data.setdefault("사용 내역", [])   # 사용 내역 키가 없으면 빈 리스트로 초기화

    # 기존 보유 PP에 충전할 PP 추가
    user_data["pp"] += amount

    # 충전 내역 업데이트
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data["충전 내역"].append(f"[{timestamp}] : {format_number(amount)} PP 충전")

    data[user_id] = user_data
    save_data(data)

    # 임베드 메시지 생성
    embed = discord.Embed(
        title="🎉 PP 충전 완료! 🎉",
        description=f"✨ {member.mention}님, PP 충전이 완료되었습니다! ✨",
        color=0xffd700
    )
    embed.add_field(name="💼 기존 보유중인 PP", value=f"💰 {format_number(user_data['pp'])} PP", inline=False)
    embed.add_field(name="\n🔋 충전한 PP", value=f"💎 {format_number(amount)} PP", inline=False)
    embed.add_field(name="\n🌟 이벤트 PP", value=f"🎉 {format_number(user_data['이벤트 PP'])} PP", inline=False)
    embed.add_field(name="\n💳 보유중인 총 PP", value=f"🪙 {format_number(user_data['pp'] + user_data['이벤트 PP'])} PP", inline=False)

    # 충전 내역 필드 추가
    충전내역 = "\n".join(user_data["충전 내역"])
    embed.add_field(name="📥 충전 내역", value=충전내역 if 충전내역 else "없음", inline=False)

    # 사용 내역 필드 추가
    사용내역 = "\n".join(user_data["사용 내역"])
    embed.add_field(name="📤 사용 내역", value=사용내역 if 사용내역 else "없음", inline=False)

    # PP SHOP 링크 추가
    embed.add_field(name="**PP SHOP 링크**", value="**[PP SHOP 바로 가기](https://docs.google.com/spreadsheets/d/1n9LKIyKCXUdCfDHuKf6xvSRoERg/edit#gid=0)**", inline=False)

    # 메시지 보내기
    try:
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"메시지를 보내는 도중 오류가 발생했습니다: {e}")

    # 명령어 호출 메시지 삭제
    await ctx.message.delete()


@bot.command()
@is_admin()
async def 이벤트등록(ctx, nickname: str, amount: int):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    # 서버 내에서 해당 닉네임을 가진 멤버를 찾습니다.
    member = discord.utils.get(ctx.guild.members, display_name=nickname)
    if not member:
        await ctx.send(f"❌ '{nickname}'이라는 디스플레이 이름을 가진 사용자는 서버에 존재하지 않습니다.")
        return

    user_id = str(member.id)
    data = load_data()
    user_data = data.get(user_id, {"nickname": nickname, "pp": 0, "이벤트 PP": 0, "충전 내역": [], "사용 내역": []})

    # 이벤트 PP에 충전할 amount 추가
    user_data["이벤트 PP"] += amount

    # 충전 내역 업데이트
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data["충전 내역"].append(f"[{timestamp}] : {format_number(amount)} 이벤트 PP 충전")

    data[user_id] = user_data
    save_data(data)

    # 임베드 메시지 생성
    embed = discord.Embed(
        title="🎉 이벤트 PP 충전 완료! 🎉",
        description=f"✨ {member.mention}님, 이벤트 PP 충전이 완료되었습니다! ✨",
        color=0xffd700
    )
    embed.add_field(name="💼 기존 보유중인 PP", value=f"💰 {format_number(user_data['pp'])} PP", inline=False)
    embed.add_field(name="\n🔋 충전한 이벤트 PP", value=f"💎 {format_number(amount)} PP", inline=False)
    embed.add_field(name="\n🌟 이벤트 PP", value=f"🎉 {format_number(user_data['이벤트 PP'])} PP", inline=False)
    embed.add_field(name="\n💳 보유중인 총 PP", value=f"🪙 {format_number(user_data['pp'] + user_data['이벤트 PP'])} PP", inline=False)

    # 충전 내역 필드 추가
    충전내역 = "\n".join(user_data["충전 내역"])
    embed.add_field(name="📥 충전 내역", value=충전내역 if 충전내역 else "없음", inline=False)

    # 사용 내역 필드 추가
    사용내역 = "\n".join(user_data["사용 내역"])
    embed.add_field(name="📤 사용 내역", value=사용내역 if 사용내역 else "없음", inline=False)

    # PP SHOP 링크 추가
    embed.add_field(name="**PP SHOP 링크**", value="**[PP SHOP 바로 가기](https://docs.google.com/spreadsheets/d/1n9LKIyKCXUdCfDHuKf6xvSRoERg/edit#gid=0)**", inline=False)

    # 메시지 보내기
    try:
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"메시지를 보내는 도중 오류가 발생했습니다: {e}")

    # 명령어 호출 메시지 삭제
    await ctx.message.delete()


@bot.command()
async def pp명령어(ctx):
    embed = discord.Embed(
        title="PP 관리 명령어",
        description="현재 사용 가능한 PP 관리 명령어들입니다.",
        color=0x00ff00
    )
    embed.add_field(
        name="!지급 <닉네임> <수치> <문장>",
        value="지정한 닉네임의 유저에게 지정한 수치만큼 PP를 차감하고, 사용 내역에 문장을 기록합니다.",
        inline=False
    )
    embed.add_field(
        name="!이벤트지급 <닉네임> <수치>",
        value="지정한 닉네임의 유저에게 지정한 수치만큼 이벤트 PP를 지급합니다.",
        inline=False
    )
    embed.add_field(
        name="!PP초기화 <닉네임>",
        value="지정한 닉네임의 유저의 PP를 초기화하고 충전된 PP만 복구합니다. 이벤트 PP는 0으로 설정됩니다.",
        inline=False
    )
    embed.add_field(
        name="!PP전부초기화",
        value="모든 유저의 PP를 초기화하고 충전된 PP만 복구합니다. 이벤트 PP는 0으로 설정됩니다.",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command()
@is_admin()
async def 사용(ctx, nickname: str, amount: int, *, reason: str = ""):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    # 서버 내에서 해당 닉네임을 가진 멤버를 찾습니다.
    member = discord.utils.get(ctx.guild.members, display_name=nickname)
    if not member:
        await ctx.send(f"❌ '{nickname}'이라는 디스플레이 이름을 가진 사용자는 서버에 존재하지 않습니다.")
        return

    user_id = str(member.id)
    data = load_data()
    user_data = data.get(user_id, {"nickname": nickname, "pp": 0, "이벤트 PP": 0, "충전 내역": [], "사용 내역": []})

    기존_pp = user_data["pp"]
    이벤트_pp = user_data["이벤트 PP"]
    총_pp = 기존_pp + 이벤트_pp

    if amount > 총_pp:
        await ctx.send(f"❌ {nickname}님의 보유 PP({format_number(총_pp)} PP)보다 사용할 PP({format_number(amount)} PP)가 많습니다.")
        return

    # 먼저 기존 PP에서 차감하고, 부족한 경우 이벤트 PP에서 차감
    if 기존_pp >= amount:
        user_data["pp"] -= amount
    else:
        remaining_amount = amount - 기존_pp
        user_data["pp"] = 0
        user_data["이벤트 PP"] -= remaining_amount

    total_pp_after = user_data["pp"] + user_data["이벤트 PP"]

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data["사용 내역"].append(f"[{timestamp}] : {format_number(amount)} PP 사용 - 사유: {reason}")

    data[user_id] = user_data
    save_data(data)

    embed = discord.Embed(
        title="💸 PP 사용 완료! 💸",
        description=f"✨ {member.mention}님, PP {format_number(amount)}을(를) 성공적으로 사용했습니다! ✨",
        color=0xff0000
    )
    embed.add_field(name="💳 기존 보유 PP", value=f"💰 {format_number(총_pp)} PP", inline=False)
    embed.add_field(name="🎉 기존 이벤트 PP", value=f"🎉 {format_number(user_data['이벤트 PP'])} PP", inline=False)
    embed.add_field(name="\n💸 사용된 PP", value=f"💎 {format_number(amount)} PP", inline=False)
    embed.add_field(name="\n🪙 총 보유 PP", value=f"🪙 {format_number(total_pp_after)} PP", inline=False)

    사용내역 = "\n".join(user_data["사용 내역"])
    embed.add_field(name="📤 사용 내역", value=사용내역 if 사용내역 else "없음", inline=False)

    충전내역 = "\n".join(user_data["충전 내역"])
    embed.add_field(name="📥 충전 내역", value=충전내역 if 충전내역 else "없음", inline=False)

    embed.add_field(name="**PP SHOP 링크**", value="**[PP SHOP 바로 가기](https://docs.google.com/spreadsheets/d/1n9LKIyKCXUdCfDHuKf6xvSRoERg/edit#gid=0)**", inline=False)

    try:
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"메시지를 보내는 도중 오류가 발생했습니다: {e}")

    await ctx.message.delete()


@bot.command(name="PP전부초기화")
@commands.check_any(commands.is_owner(), commands.has_permissions(administrator=True))
async def pp_reset_all(ctx):
    data = load_data()
    initializations = []

    for nickname, user_data in data.items():
        total_charged_pp = sum(int(entry.split(": ")[1].replace(" PP", "").replace(",", "")) for entry in user_data["충전 내역"])
        initializations.append(f"사용자: {ctx.guild.get_member_named(nickname).mention}, 초기화 전: {format_number(user_data['pp'])} PP, 초기화 후: {format_number(total_charged_pp)} PP")
        user_data["pp"] = total_charged_pp
        user_data["이벤트 PP"] = 0
        user_data["사용 내역"] = []
        data[nickname] = user_data

    save_data(data)

    embed = discord.Embed(
        title="🔄 모든 유저 PP 초기화 완료! 🔄",
        description="💡 모든 유저의 PP가 초기화되었습니다.",
        color=0x00ff00
    )

    for init in initializations:
        embed.add_field(name="초기화 내역", value=init, inline=False)

    channel = discord.utils.get(ctx.guild.channels, name="📧｜자유채팅")
    if channel:
        await channel.send(embed=embed)

    await ctx.message.delete()


@bot.command()
@is_admin()
async def 지급(ctx, nickname: str, amount: int, *, reason: str = ""):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    member = discord.utils.get(ctx.guild.members, display_name=nickname)
    if not member:
        await ctx.send(f"❌ '{nickname}'이라는 디스플레이 이름을 가진 사용자는 서버에 존재하지 않습니다.")
        return
    
    user_id = str(member.id)
    data = load_data()
    user_data = data.get(user_id, {"pp": 0, "이벤트 PP": 0, "충전 내역": [], "사용 내역": []})

    기존_pp = user_data["pp"]
    이벤트_pp = user_data["이벤트 PP"]
    총_pp = 기존_pp + 이벤트_pp

    # 기존 PP에서 amount만큼 차감
    if amount > 총_pp:
        await ctx.send(f"❌ {nickname}님의 보유 PP({format_number(총_pp)} PP)보다 지급할 PP({format_number(amount)} PP)가 많습니다.")
        return
    
    # 먼저 기존 PP에서 차감하고, 부족한 경우 이벤트 PP에서 차감
    if 기존_pp >= amount:
        user_data["pp"] -= amount
    else:
        remaining_amount = amount - 기존_pp
        user_data["pp"] = 0
        user_data["이벤트 PP"] -= remaining_amount

    total_pp_after = user_data["pp"] + user_data["이벤트 PP"]
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    user_data["사용 내역"].append(f"[{timestamp}] : {format_number(amount)} PP 사용 - 사유: {reason}")
    
    data[user_id] = user_data
    save_data(data)
    
    embed = discord.Embed(
        title="💸 PP 지급 완료! 💸",
        description=f"✨ {ctx.guild.get_member_named(nickname).mention}님, PP {format_number(amount)}을(를) 성공적으로 차감했습니다! ✨",
        color=0xff0000
    )
    embed.add_field(name="💳 기존 보유 PP", value=f"💰 {format_number(총_pp)} PP", inline=False)
    embed.add_field(name="🎉 기존 이벤트 PP", value=f"🎉 {format_number(user_data['이벤트 PP'])} PP", inline=False)
    embed.add_field(name="\n💸 사용된 PP", value=f"💎 {format_number(amount)} PP", inline=False)
    embed.add_field(name="\n🪙 총 보유 PP", value=f"🪙 {format_number(total_pp_after)} PP", inline=False)
    
    사용내역 = "\n".join(user_data["사용 내역"])
    embed.add_field(name="📤 사용 내역", value=사용내역 if 사용내역 else "없음", inline=False)
    
    충전내역 = "\n".join(user_data["충전 내역"])
    embed.add_field(name="📥 충전 내역", value=충전내역 if 충전내역 else "없음", inline=False)
    
    embed.add_field(name="**PP SHOP 링크**", value="**[PP SHOP 바로 가기](https://docs.google.com/spreadsheets/d/1n9LKIyKCXUdCfDHuKf6xvSRoERg/edit#gid=0)**", inline=False)

    try:
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"메시지를 보내는 도중 오류가 발생했습니다: {e}")

    await ctx.message.delete()

@bot.command()
async def 조회(ctx, *, nickname_or_self: str = None):
    if ctx.channel.name != "📧｜자유채팅":
        await ctx.send("이 명령어는 📧｜자유채팅 채널에서만 사용할 수 있습니다.")
        return

    if nickname_or_self is None:
        nickname_or_self = ctx.author.display_name
    
    member = discord.utils.get(ctx.guild.members, display_name=nickname_or_self)
    
    if not member:
        await ctx.send(f"❌ '{nickname_or_self}'이라는 디스플레이 이름을 가진 사용자는 서버에 존재하지 않습니다.")
        return
    
    user_id = str(member.id)
    data = load_data()
    user_data = data.get(user_id, {"pp": 0, "이벤트 PP": 0, "충전 내역": [], "사용 내역": []})
    
    총_pp = user_data["pp"] + user_data["이벤트 PP"]
    
    embed = discord.Embed(
        title=f"💳 {member.display_name}님의 PP 조회 💳",
        description=f"🪙 총 보유중인 PP: {format_number(총_pp)} PP",
        color=0x008080
    )
    embed.add_field(name="💼 기존 보유 PP", value=f"💰 {format_number(user_data['pp'])} PP", inline=False)
    embed.add_field(name="\n🎉 이벤트 PP", value=f"🎉 {format_number(user_data['이벤트 PP'])} PP", inline=False)
    
    충전내역 = "\n".join(user_data["충전 내역"])
    embed.add_field(name="📥 충전 내역", value=충전내역 if 충전내역 else "없음", inline=False)
    
    사용내역 = "\n".join(user_data["사용 내역"])
    embed.add_field(name="📤 사용 내역", value=사용내역 if 사용내역 else "없음", inline=False)
    
    embed.add_field(name="**PP SHOP 링크**", value="**[PP SHOP 바로 가기](https://docs.google.com/spreadsheets/d/1n9LKIyKCXUdCfDHuKf6xvSRoERg/edit#gid=0)**", inline=False)

    try:
        await ctx.send(embed=embed)
    except Exception as e:
        await ctx.send(f"메시지를 보내는 도중 오류가 발생했습니다: {e}")


# 지정된 채널 ID
ANNOUNCEMENT_CHANNEL_ID = 1208434637060186162  # 점검 공지를 보낼 채널의 ID
REWARD_CHANNEL_LINK = "https://discord.com/channels/1208238905896345620/1218543871907201166"  # 점검보상 채널 링크
REWARD_CHANNEL_NAME = "💦｜점검보상"  # 점검보상 채널 이름

@bot.command()
async def 점검공지(ctx):
    def check(m):
        return m.author == ctx.author and m.channel == ctx.channel

    # 진행 날짜 입력
    await ctx.send("🗓️ **점검 진행 날짜를 입력해주세요 (예: 2024년 10월 10일 10시 00분 ~ 10시 20분):**")
    date_msg = await bot.wait_for('message', check=check)
    date = date_msg.content

    # 점검 사유 입력
    await ctx.send("🔧 **점검 사유를 입력해주세요 (여러 개일 경우 줄바꿈으로 구분):**")
    reason_msg = await bot.wait_for('message', check=check)
    reasons = reason_msg.content.split('\n')

    # 점검 보상 입력
    await ctx.send("🎁 **점검 보상을 입력해주세요 (여러 개일 경우 줄바꿈으로 구분):**")
    reward_msg = await bot.wait_for('message', check=check)
    rewards = reward_msg.content.split('\n')

    # 임베드 생성
    embed = discord.Embed(
        title="🔔 서버 점검 공지 🔔",
        description="안녕하세요, PASTEL WORLD 여러분!\n아래와 같이 점검이 예정되어 있으니 참고 부탁드립니다.",
        color=0x1abc9c
    )
    
    # 날짜 필드 추가 (큰 글씨로 강조)
    embed.add_field(name="🗓️ **점검 날짜**", value=f"**__{date}__** @everyone", inline=False)

    # 점검 사유 필드 추가 (굵게 표시)
    reasons_formatted = "\n".join([f"**- {reason}**" for reason in reasons])
    embed.add_field(name="🔧 **점검 사유**", value=reasons_formatted, inline=False)

    # 점검 보상 필드 추가 (굵게 표시)
    rewards_formatted = "\n".join([f"**- {reward}**" for reward in rewards])
    embed.add_field(name="🎁 **점검 보상**", value=rewards_formatted, inline=False)

    # 임베드 하단에 푸터 추가 (링크를 채널 이름으로 표시)
    embed.set_footer(text=f"[{REWARD_CHANNEL_NAME}]({REWARD_CHANNEL_LINK}) 채널에서 점검 보상을 신청해주시면 보상이 지급됩니다.\n최대한 빠르게 점검을 마무리 하도록 하겠습니다. 감사합니다.\n (주의사항 : 꼭 보상 신청 시 !보상신청 명령어를 통해 신청 후 정상 신청되었다는 메시지를 확인해주셔야 됩니다.)")

    # 색상 강조 (파란색 사이드 바)
    embed.color = discord.Color.dark_magenta()

    # 공지 채널 가져오기
    announcement_channel = bot.get_channel(ANNOUNCEMENT_CHANNEL_ID)

    # 메시지 보내기
    if announcement_channel:
        await announcement_channel.send(embed=embed)
        # 원래 메시지를 삭제합니다.
        await date_msg.delete()
        await reason_msg.delete()
        await reward_msg.delete()
        await ctx.message.delete()
    else:
        await ctx.send("❌ 점검 공지를 보낼 채널을 찾을 수 없습니다.")

@bot.command()
async def 보상신청(ctx):
    # 특정 채널에서만 명령어 실행 (점검보상 채널 ID 사용)
    allowed_channel_id = 1218543871907201166  # 해당 채널 ID

    if ctx.channel.id != allowed_channel_id:
        await ctx.send("이 명령어는 `#점검보상` 채널에서만 사용할 수 있습니다.")
        return
    
    # 확인할 메시지 링크 및 채널 ID 및 메시지 ID 추출
    channel_id = 1208303811039600660  # 서버 점검 상태를 확인하는 채널 ID
    message_id = 1291767836951314483  # 해당 메시지 ID
    
    # 채널 객체 가져오기
    channel = bot.get_channel(channel_id)
    if not channel:
        await ctx.send("채널을 찾을 수 없습니다.")
        return
    
    # 메시지 가져오기
    try:
        message = await channel.fetch_message(message_id)
        message_content = message.content.strip()
    except Exception as e:
        await ctx.send(f"메시지를 가져오는 중 오류가 발생했습니다: {e}")
        return
    
    # 메시지 내용이 "서버점검 : 진행"인지 확인
    if message_content == "서버점검 : 진행":
        # 점검 진행 중일 때 임베드 생성 및 메시지 전송
        embed = discord.Embed(
            title="🎁 보상 신청 완료 🎁",
            description=f"{ctx.author.mention}님, 점검 보상 신청이 완료되었습니다!\n점검 종료 후 아이템이 지급될 예정이오니 조금만 기다려 주세요. 😊",
            color=0x1abc9c
        )
        embed.set_footer(text="신청해주셔서 감사합니다!")

        await ctx.send(embed=embed)
    else:
        # 점검 진행 중이 아닐 때 안내 임베드 전송 후 10초 뒤 삭제
        embed = discord.Embed(
            title="⛔ 보상 신청 불가 ⛔",
            description="현재는 서버 점검 보상 신청 기간이 아닙니다.\n점검 기간에 보상 신청을 해주세요!",
            color=0xe74c3c
        )
        bot_message = await ctx.send(embed=embed)
        
        # 10초 후 메시지 삭제
        await asyncio.sleep(10)
        await bot_message.delete()
        await ctx.message.delete()
        await ctx.send("채널을 찾을 수 없습니다.")


async def send_random_message():
    channel_name = "📧｜자유채팅"  # 메시지를 보낼 채널의 이름
    while True:
        await asyncio.sleep(14400)  # 50분마다 메시지를 보냄 (50분 * 60초 = 3000초)
        channel = discord.utils.get(bot.get_all_channels(), name=channel_name)

        # 커스텀 이모지 가져오기
        guild = bot.get_guild(1208238905896345620)  # 봇이 속한 서버의 ID
        emoji7 = discord.utils.get(guild.emojis, name='file5')
        emoji8 = discord.utils.get(guild.emojis, name='file3')
        emoji9 = discord.utils.get(guild.emojis, name='file1')
        
        # 이모지 리스트
        emojis = [emoji7, emoji8, emoji9]

        # 랜덤으로 전송할 메시지 리스트
        messages = [
            " : 초대박 후원 이벤트를 통해 PP를 충전하여 전설 아이템부터 팰까지 구매가 가능합니다! https://discord.com/channels/1208238905896345620/1213843314579869776/1292812988369342525 \n 선착순 1명 2배 지급 이벤트 진행중! https://discord.com/channels/1208238905896345620/1213843314579869776/1293223109314478100",
            " : PP 충전 이벤트를 확인해주세요! https://discord.com/channels/1208238905896345620/1213843314579869776/1292812988369342525 \n 선착순 1명 2배 지급 이벤트 진행중! https://discord.com/channels/1208238905896345620/1213843314579869776/1293223109314478100",
            " : 후원을 통해 PP를 충전하여 전설 아이템부터 팰까지 구매가 가능합니다! https://discord.com/channels/1208238905896345620/1213843314579869776/1292812988369342525 \n 선착순 1명 2배 지급 이벤트 진행중! https://discord.com/channels/1208238905896345620/1213843314579869776/1293223109314478100 ",
            " : PP 충전 이벤트를 확인해주세요! https://discord.com/channels/1208238905896345620/1213843314579869776/1292812988369342525 \n 선착순 1명 2배 지급 이벤트 진행중! https://discord.com/channels/1208238905896345620/1213843314579869776/1293223109314478100",
        ]

        if channel:
            # 랜덤 메시지 선택
            selected_message = random.choice(messages)
            
            # 랜덤 이모지 선택
            selected_emoji = random.choice(emojis)
            
            # 이모지를 메시지 앞에 추가
            if selected_emoji:
                final_message = f"# [{selected_emoji}PASTEL WORLD{selected_emoji}] {selected_message}"
            else:
                final_message = selected_message

            # 메시지 전송
            await channel.send(final_message)
@tasks.loop(seconds=60)
async def scheduled_messages():
    now = datetime.now(ZoneInfo("Asia/Seoul"))
    channel_name = "📧｜자유채팅"  # 메시지를 보낼 채널의 이름입니다.
    
    # 메시지를 보낼 채널을 찾습니다.
    channel = discord.utils.get(bot.get_all_channels(), name=channel_name)

    if not channel:
        print(f"채널 '{channel_name}'을(를) 찾을 수 없습니다.")
        return

    # 정의된 시간에 맞춰 메시지를 보냅니다.
    # if now.strftime('%H:%M') == '04:55' or now.strftime('%H:%M') == '10:55' or \
    if now.strftime('%H:%M') == '09:25' or now.strftime('%H:%M') == '21:25':
        await channel.send("# [자동 리붓] : 5분 후 자동 리붓이 진행 될 예정입니다. 게임 이용에 참고 부탁드립니다.")
    #elif now.strftime('%H:%M') == '06:05' or now.strftime('%H:%M') == '18:05' or \
    elif now.strftime('%H:%M') == '09:31' or now.strftime('%H:%M') == '21:31':
        await channel.send("# [자동 리붓] : 자동 리붓이 완료되었으며 서버가 실행되었습니다. 접속 부탁드립니다.")

async def schedule_next_event():
    global first_run
    now = datetime.now(ZoneInfo('Asia/Seoul'))
    
    # 0시부터 23시까지의 범위에 속하는지 확인 0 <= now.hour <24 가 기본값
    if 24 <= now.hour < 24:
        if first_run:
            # 첫 실행 시 1분 후에 이벤트 시작
            delay = (60 - now.second) + 60  # 현재 분의 나머지 초와 1분 추가
            first_run = False
        else:
            # 다음 이벤트까지의 대기 시간 계산 (30분 간격)
            delay = (60 - now.minute % 60) * 60 - now.second + random.randint(0, 59) * 60
            # delay = (60 - now.minute % 60) * 60 - now.second + random.randint(0, 59) * 60
            
        await asyncio.sleep(delay)  # 대기
        await trigger_event()  # 이벤트 트리거
        await schedule_next_event()  # 다음 이벤트 예약
    else:
        # 0시부터 23시까지가 아니라면 다음 정각까지 대기 후 재확인
        delay = ((24 - now.hour) * 60 - now.minute) * 60 - now.second
        await asyncio.sleep(delay)
        await schedule_next_event()

async def trigger_event():
    channel = discord.utils.get(bot.get_all_channels(), name='📧｜자유채팅')
    if channel:
        kst_now = datetime.now(ZoneInfo('Asia/Seoul')).strftime("%H시 %M분")
        view = View()
        button = Button(label="파스텔 버튼 누르기!", style=discord.ButtonStyle.danger)
        button.timeout = None

        async def button_callback(interaction):
            selected_prize_category = choices(prizes, weights=probabilities, k=1)[0]
            selected_prize_info = choice(selected_prize_category)
            selected_prize, min_qty, max_qty = selected_prize_info
            qty = randint(min_qty, max_qty)

            await interaction.response.edit_message(content=f"## 🌟[{kst_now}] 버튼 이벤트 당첨자는 {interaction.user.mention}님 입니다!🌟\n ### 당첨 결과는 {selected_prize} {qty}개 입니다! \n매주 토요일 오후 8시부터 일요일 23시전까지 초록판다에게 지급 신청 부탁드립니다. 다음 주가되면,당첨 아이템은 초기화됩니다.** ★경과시 지급 불가!★ **", view=None)
            winning_channel = discord.utils.get(interaction.guild.channels, name="💞｜당첨내역")
            if winning_channel:
                await winning_channel.send(f"{interaction.user.mention} [버튼] {selected_prize} {qty}개")
            # 버튼이 눌렸으므로 5분 후의 메시지 수정 취소
            nonlocal message_edit_task
            if message_edit_task:
                message_edit_task.cancel()

        button.callback = button_callback
        view.add_item(button)
        # 메시지 전송
        message = await channel.send(f"# {kst_now} 🌟파스텔 버튼 이벤트 출현!🌟\n 제한시간: 5분! 시간 경과 시 버튼을 눌러도 작동하지 않습니다.", view=view)

        # 5분 후에 메시지 수정
        async def edit_message():
            await asyncio.sleep(300)
            await message.edit(content=f"## 🌟[{kst_now}] 타임 당첨자는 아무도 없습니다. 다음 타임을 기다려주세요! 🌟")
        
        message_edit_task = asyncio.create_task(edit_message())

bot.run(TOKEN)