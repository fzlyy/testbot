# -*- coding: utf-8 -*-
"""昵称唤醒 + 语义指代识别（v2.3）

三层判定：
  1. 命中昵称              → 直接唤醒（零成本）
  2. 它 90 秒内说过话       → 必判
  3. 含高精度信号词         → 判
判别走 reasoning_effort=high 的 provider：更慢（2~6 秒）但思考更充分。
"""

import asyncio
import time
from collections import deque

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register

# ---- 可调参数 -------------------------------------------------------------
NICKNAMES = ["大肥鱼", "肥鱼", "鱼娘", "鲸鱼娘"]      # 命中即唤醒

MAX_LEN = 120          # 超过这个长度的消息不判，避免长文/转发误触
WINDOW_SEC = 90        # 机器人说完话多久内，别人的发言必判
COOLDOWN_SEC = 20      # 语义唤醒后同群冷却（原来 60，压住了不少真实回复）
HOURLY_CAP = 20        # 每群每小时最多唤醒次数
JUDGE_HOURLY_CAP = 60  # 每群每小时最多判别调用次数
BUFFER_SIZE = 12       # 每群保留多少条上下文
JUDGE_TIMEOUT = 12.0   # 判别调用超时；高思考档下要放宽，否则会被误判成 NO

# 判别专用 provider：同一个 API source、同一个模型，思考档位拉满。
# 取不到就退回当前对话 provider（行为不变）。
JUDGE_PROVIDER_ID = "deepseek/deepseek-flash-high"

# 只保留高精度信号词。「你」「吗」「怎么」在群里太常见，会把每小时的
# 判别额度全耗在无关消息上。
SIGNALS = (
    "它", "这鱼", "这条鱼", "这货", "这玩意",
    "是不是在说我", "是不是在说它", "被说",
)

GROUP_WHITELIST: list[str] = []  # 空 = 所有群生效

JUDGE_SYSTEM = "你是群聊过滤器，只输出 YES 或 NO。"

JUDGE_TMPL = """群里的机器人叫「鲸鱼娘」，大家也叫它「大肥鱼」。

判断最后一条消息：是不是在跟这个机器人说话、问它、评论它，或者接着它刚才的话往下说。
（「我」代表机器人自己说的话）

规则：
- 两个人互相聊、对别人说、与它无关的话题 → NO
- 提到它、问它、评价它、回它 → YES
- 纯笑声、纯表情、单字（哈、6、草、啊这）→ 一般是 NO
- 拿不准 → NO

例子：
1)
我: 今天白饭又没了
老王: 哈哈哈哈
→ NO

2)
我: 你行你上
小李: 我上就我上
→ YES

3)
老王: 这鱼是不是死了
小李: 死了死了
→ YES

4)
老王: 今晚谁值班
小李: 我
→ NO

现在判断：
{context}

{sender}: {text}

只输出 YES 或 NO。"""


@register("nick_wake", "local", "昵称唤醒 + 语义指代识别", "2.3.1")
class NickWake(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self._buf: dict[str, deque] = {}
        self._last_bot: dict[str, float] = {}
        self._last_wake: dict[str, float] = {}
        self._wakes: dict[str, deque] = {}
        self._judges: dict[str, deque] = {}
        self._judged: dict[str, bool] = {}

    # ---- 小工具 ----
    @staticmethod
    def _rate(store: dict, key: str, cap: int) -> bool:
        q = store.setdefault(key, deque())
        now = time.time()
        while q and now - q[0] > 3600:
            q.popleft()
        if len(q) >= cap:
            return False
        q.append(now)
        return True

    def _push(self, umo: str, role: str, name: str, text: str) -> None:
        buf = self._buf.setdefault(umo, deque(maxlen=BUFFER_SIZE))
        buf.append({"ts": time.time(), "role": role, "name": name, "text": text})

    def _allowed(self, event: AstrMessageEvent) -> bool:
        if not GROUP_WHITELIST:
            return True
        gid = event.get_group_id()
        return (gid in GROUP_WHITELIST) or (event.unified_msg_origin in GROUP_WHITELIST)

    # ---- 记录它自己说过的话 ----
    @filter.on_llm_response()
    async def remember_bot_reply(self, event: AstrMessageEvent, resp=None):
        if event.is_private_chat():
            return
        try:
            text = (resp.completion_text or "") if resp is not None else ""
        except Exception:
            text = ""
        if text.strip():
            umo = event.unified_msg_origin
            self._push(umo, "bot", "bot", text.strip())
            self._last_bot[umo] = time.time()

    # ---- 主入口 ----
    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def wake_on_context(self, event: AstrMessageEvent):
        if event.is_at_or_wake_command:
            return
        if not self._allowed(event):
            return

        text = (event.message_str or "").strip()
        if not text or len(text) > MAX_LEN:
            return

        umo = event.unified_msg_origin
        name = getattr(getattr(event.message_obj, "sender", None), "nickname", "") or "群友"
        self._push(umo, "user", name, text)
        now = time.time()

        # 1) 昵称命中
        if any(n in text for n in NICKNAMES):
            if not self._rate(self._wakes, umo, HOURLY_CAP):
                logger.info("[nick_wake] %s 命中昵称，但本小时额度已用完", umo)
                return
            event.is_wake = True
            event.is_at_or_wake_command = True
            logger.info("[nick_wake] 昵称唤醒 %s | %r", name, text[:30])
            return

        # 2/3) 必判条件：它刚说过话，或者出现高精度信号词
        recent_bot = now - self._last_bot.get(umo, 0) < WINDOW_SEC
        has_signal = any(s in text for s in SIGNALS)
        if not (recent_bot or has_signal):
            return
        if not self._rate(self._judges, umo, JUDGE_HOURLY_CAP):
            return

        msg_id = str(getattr(event.message_obj, "message_id", "") or "")
        if msg_id and msg_id in self._judged:
            verdict = self._judged[msg_id]
        else:
            verdict = await self._judge(event, umo, name, text)
            if msg_id:
                if len(self._judged) > 500:
                    self._judged.clear()
                self._judged[msg_id] = verdict

        if not verdict:
            return
        if now - self._last_wake.get(umo, 0) < COOLDOWN_SEC:
            logger.info("[nick_wake] %s 语义命中但冷却中", umo)
            return
        if not self._rate(self._wakes, umo, HOURLY_CAP):
            return

        self._last_wake[umo] = now
        event.is_wake = True
        event.is_at_or_wake_command = True
        logger.info("[nick_wake] 语义唤醒 %s | %r", name, text[:30])

    async def _judge_provider(self, umo: str):
        if JUDGE_PROVIDER_ID:
            try:
                p = self.context.get_provider_by_id(JUDGE_PROVIDER_ID)
                if p is not None:
                    return p
            except Exception:
                pass
        return await self.context.get_using_provider_async(umo)

    async def _judge(self, event: AstrMessageEvent, umo: str, name: str, text: str) -> bool:
        try:
            provider = await self._judge_provider(umo)
            if provider is None:
                return False
            ctx = list(self._buf.get(umo, []))[-7:-1]
            lines = []
            for e in ctx:
                who = "我" if e["role"] == "bot" else e["name"]
                lines.append("%s: %s" % (who, e["text"][:60]))
            prompt = JUDGE_TMPL.format(
                context="\n".join(lines) if lines else "（无）",
                sender=name,
                text=text,
            )
            resp = await asyncio.wait_for(
                provider.text_chat(prompt=prompt, system_prompt=JUDGE_SYSTEM, contexts=[]),
                timeout=JUDGE_TIMEOUT,
            )
            ans = (getattr(resp, "completion_text", "") or "").strip().upper()
            logger.debug("[nick_wake] judge %r -> %r", text[:30], ans[:10])
            return ans.startswith("YES")
        except asyncio.TimeoutError:
            logger.info("[nick_wake] 判别超时，按 NO 处理")
            return False
        except Exception as e:
            logger.error("[nick_wake] 判别失败: %s", e)
            return False
