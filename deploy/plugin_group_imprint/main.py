# -*- coding: utf-8 -*-
"""群友印象：给小群维护一份长期印象档案。

工作方式
--------
1. 每天 04:30 读过去 24 小时的群消息（platform_message_history），按人聚合，
   一次 LLM 调用产出全群的印象卡（tags + note），与旧卡合并而不是重建。
2. 12:30 补跑一次增量：某人当天发言 >= ACTIVE_THRESHOLD 时才更新该群。
3. 新人第一次发言时立刻建一张极简卡（昵称 + 首句话），零 LLM 成本。
4. 每次 LLM 请求前，只把「当前发言人」那张卡注入上下文（约 60~80 字）。

只为小群设计：活跃发言人数超过 MAX_MEMBERS 的群直接跳过，避免大群把
token 和注意力都烧在陌生人身上。
"""

import asyncio
import json
import os
import re
import sqlite3
from datetime import datetime, timedelta

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent, filter
from astrbot.api.event.filter import EventMessageType
from astrbot.api.star import Context, Star, register
from astrbot.core.agent.message import TextPart
from astrbot.core.utils.astrbot_path import get_astrbot_data_path

# ---------------- 可调参数 ----------------
MAX_MEMBERS = 20          # 群活跃发言人数上限，超过就不建卡不更新
PER_USER_MSGS = 40        # 每人每天最多取多少条发言
MAX_INPUT_CHARS = 9000    # 单次更新喂给模型的最大字符数
DAILY_HHMM = (4, 30)      # 每日全量更新
INCR_HHMM = (12, 30)      # 增量检查
ACTIVE_THRESHOLD = 30     # 当天发言 >= 这个数才触发增量更新
STALE_DAYS = 30           # 超过这么多天没说话，注入时标注
INJECT_ENABLE = True

JUDGE_SYSTEM = "你在维护一份群友印象档案。只输出 JSON，不解释。"

PROMPT_TMPL = """群「{gid}」最近 24 小时的发言，按人整理如下（每人最多 {per} 条）：

{people}

已有印象（可能为空，格式：uid -> 标签 | 备注）：
{old}

任务：为上面每个发言者更新一条印象。
要求：
- tags 是 2~4 个短词，概括这个人是什么样的人（职业/身份/性格/说话习惯）
- note 一句话，不超过 40 字，写具体的事：最近在做什么、关心什么、和谁互动
- 有旧印象的，在旧印象上更新：只改有新信息的，没变化就保留原文
- 只写从发言里能看出来的，不要编造
- 输出 JSON 数组，不要 markdown 代码块，不要解释：

[{{"user_id":"123","nick":"老王","tags":["后端","爱吐槽"],"note":"最近在折腾 K8s 迁移"}}]"""


@register("group_imprint", "local", "群友印象：小群长期记忆", "1.0.0")
class GroupImprint(Star):
    def __init__(self, context: Context):
        super().__init__(context)
        self.dir = os.path.join(get_astrbot_data_path(), "plugin_data", "group_imprint")
        os.makedirs(self.dir, exist_ok=True)
        self.db_path = os.path.join(self.dir, "imprint.db")
        self._init_db()
        self._known = set()       # (umo, uid) 已建卡的缓存
        self._task = None

    # ---------------- 存储 ----------------
    def _conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._conn() as c:
            c.execute(
                """create table if not exists cards (
                    group_id text not null,
                    user_id  text not null,
                    nick     text,
                    tags     text,
                    note     text,
                    msg_count integer default 0,
                    first_seen text,
                    last_seen  text,
                    updated_at text,
                    primary key (group_id, user_id))"""
            )
            c.execute(
                """create table if not exists runs (
                    id integer primary key autoincrement,
                    group_id text, kind text, started_at text, updated integer, note text)"""
            )

    def _cards(self, umo: str) -> dict:
        with self._conn() as c:
            return {r["user_id"]: dict(r) for r in c.execute(
                "select * from cards where group_id=?", (umo,))}

    def _card(self, umo: str, uid: str):
        with self._conn() as c:
            r = c.execute(
                "select * from cards where group_id=? and user_id=?", (umo, uid)).fetchone()
            return dict(r) if r else None

    def _upsert(self, umo: str, card: dict, now: str, count: int = 0) -> None:
        with self._conn() as c:
            old = c.execute(
                "select first_seen, msg_count from cards where group_id=? and user_id=?",
                (umo, card["user_id"])).fetchone()
            first = old["first_seen"] if old else now
            total = (old["msg_count"] if old else 0) + count
            c.execute(
                """insert into cards (group_id,user_id,nick,tags,note,msg_count,first_seen,last_seen,updated_at)
                   values (?,?,?,?,?,?,?,?,?)
                   on conflict(group_id,user_id) do update set
                     nick=excluded.nick, tags=excluded.tags, note=excluded.note,
                     msg_count=excluded.msg_count, last_seen=excluded.last_seen,
                     updated_at=excluded.updated_at""",
                (umo, card["user_id"], card.get("nick", ""), card.get("tags", ""),
                 card.get("note", ""), total, first, now, now),
            )
        self._known.add((umo, card["user_id"]))

    # ---------------- 读历史 ----------------
    @staticmethod
    def _text_of(content) -> str:
        try:
            parts = json.loads(content) if isinstance(content, str) else content
        except Exception:
            return ""
        out = []
        for p in parts or []:
            if not isinstance(p, dict):
                continue
            if p.get("type") == "plain":
                out.append(str(p.get("text", "")))
            elif p.get("type") == "at":
                out.append("@" + str(p.get("name") or p.get("user_id") or ""))
        return "".join(out).strip()

    def _fetch(self, umo: str, since: datetime) -> list:
        path = os.path.join(get_astrbot_data_path(), "data_v4.db")
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)
        except Exception as e:
            logger.error("[imprint] 打开历史库失败: %s", e)
            return []
        try:
            rows = conn.execute(
                """select sender_id, sender_name, content, created_at
                   from platform_message_history
                   where user_id = ? and created_at >= ?
                   order by id""",
                (umo, since.strftime("%Y-%m-%d %H:%M:%S")),
            ).fetchall()
        except Exception as e:
            logger.error("[imprint] 查询历史失败: %s", e)
            rows = []
        finally:
            conn.close()
        out = []
        for sid, name, content, ts in rows:
            if not sid or sid == "bot":
                continue
            text = self._text_of(content)
            if text:
                out.append({"uid": str(sid), "nick": name or str(sid), "text": text, "ts": ts})
        return out

    @staticmethod
    def _groups() -> list:
        path = os.path.join(get_astrbot_data_path(), "data_v4.db")
        try:
            conn = sqlite3.connect("file:%s?mode=ro" % path, uri=True, timeout=5)
            rows = [r[0] for r in conn.execute(
                "select distinct user_id from platform_message_history where user_id like '%GroupMessage%'")]
            conn.close()
            return rows
        except Exception as e:
            logger.error("[imprint] 列群失败: %s", e)
            return []

    # ---------------- 核心：更新一个群 ----------------
    async def _update_group(self, umo: str, since: datetime, kind: str) -> int:
        msgs = self._fetch(umo, since)
        if not msgs:
            return 0

        agg = {}
        for m in msgs:
            a = agg.setdefault(m["uid"], {"nick": m["nick"], "texts": []})
            a["nick"] = m["nick"]
            if len(a["texts"]) < PER_USER_MSGS:
                a["texts"].append(m["text"][:80])

        if len(agg) > MAX_MEMBERS:
            logger.info("[imprint] %s 有 %d 个发言者，超过 %d，跳过", umo, len(agg), MAX_MEMBERS)
            self._log_run(umo, kind, 0, "too many members")
            return 0

        cards = self._cards(umo)
        lines, used = [], 0
        for uid, a in agg.items():
            block = ["%s(%s):" % (a["nick"], uid)]
            for i, t in enumerate(a["texts"], 1):
                block.append("  %d. %s" % (i, t))
            chunk = "\n".join(block)
            if used + len(chunk) > MAX_INPUT_CHARS:
                break
            lines.append(chunk)
            used += len(chunk)

        old = "\n".join(
            "%s -> %s" % (uid, ("，".join(filter(None, [c.get("tags"), c.get("note")]))))
            for uid, c in cards.items() if uid in agg
        ) or "（无）"

        prompt = PROMPT_TMPL.format(
            gid=umo.split(":")[-1], per=PER_USER_MSGS,
            people="\n\n".join(lines), old=old,
        )

        provider = await self.context.get_using_provider_async(umo)
        if provider is None:
            logger.error("[imprint] 没有可用的 provider")
            return 0
        resp = await asyncio.wait_for(
            provider.text_chat(prompt=prompt, system_prompt=JUDGE_SYSTEM, contexts=[]),
            timeout=180,
        )
        raw = getattr(resp, "completion_text", "") or ""
        data = self._parse_json_array(raw)
        if not data:
            logger.error("[imprint] 模型没返回合法 JSON: %r", raw[:200])
            self._log_run(umo, kind, 0, "bad json")
            return 0

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        n = 0
        for item in data:
            if not isinstance(item, dict):
                continue
            uid = str(item.get("user_id") or "").strip()
            if not uid or uid not in agg:
                continue
            tags = item.get("tags") or []
            if isinstance(tags, list):
                tags = ",".join(str(t).strip() for t in tags if str(t).strip())
            else:
                tags = str(tags)
            self._upsert(umo, {
                "user_id": uid,
                "nick": str(item.get("nick") or agg[uid]["nick"])[:24],
                "tags": tags[:80],
                "note": str(item.get("note") or "")[:80],
            }, now, count=len(agg[uid]["texts"]))
            n += 1
        self._log_run(umo, kind, n, "")
        logger.info("[imprint] %s 更新 %d 张印象卡（%s）", umo, n, kind)
        return n

    @staticmethod
    def _parse_json_array(raw: str):
        if not raw:
            return None
        s = raw.strip()
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
        i, j = s.find("["), s.rfind("]")
        if i < 0 or j <= i:
            return None
        try:
            return json.loads(s[i:j + 1])
        except Exception:
            return None

    def _log_run(self, umo, kind, updated, note):
        try:
            with self._conn() as c:
                c.execute(
                    "insert into runs (group_id,kind,started_at,updated,note) values (?,?,?,?,?)",
                    (umo, kind, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), updated, note))
        except Exception:
            pass

    # ---------------- 定时器 ----------------
    def _next_tick(self) -> tuple:
        now = datetime.now()
        cands = []
        for h, m, kind in (DAILY_HHMM[0], DAILY_HHMM[1], "daily"), (INCR_HHMM[0], INCR_HHMM[1], "incr"):
            t = now.replace(hour=h, minute=m, second=0, microsecond=0)
            if t <= now:
                t += timedelta(days=1)
            cands.append((t, kind))
        return min(cands, key=lambda x: x[0])

    async def _scheduler(self):
        while True:
            target, kind = self._next_tick()
            wait = (target - datetime.now()).total_seconds()
            logger.info("[imprint] 下次 %s 更新在 %s（%.0f 分钟后）", kind, target.strftime("%m-%d %H:%M"), wait / 60)
            await asyncio.sleep(max(5, wait))
            try:
                await self._run(kind)
            except Exception:
                logger.exception("[imprint] 定时任务出错")

    async def _run(self, kind: str):
        groups = self._groups()
        logger.info("[imprint] 开始 %s 更新，共 %d 个群", kind, len(groups))
        now = datetime.now()
        for umo in groups:
            since = now - timedelta(hours=24) if kind == "daily" else now - timedelta(hours=12)
            if kind == "incr":
                msgs = self._fetch(umo, since)
                cnt = {}
                for m in msgs:
                    cnt[m["uid"]] = cnt.get(m["uid"], 0) + 1
                if not cnt or max(cnt.values()) < ACTIVE_THRESHOLD:
                    continue
            try:
                await self._update_group(umo, since, kind)
            except Exception:
                logger.exception("[imprint] 更新 %s 失败", umo)

    @filter.on_astrbot_loaded()
    async def start_scheduler(self):
        if self._task and not self._task.done():
            return
        self._task = asyncio.create_task(self._scheduler())
        logger.info("[imprint] 定时器已启动，每日 %02d:%02d 全量、%02d:%02d 增量",
                    DAILY_HHMM[0], DAILY_HHMM[1], INCR_HHMM[0], INCR_HHMM[1])

    async def terminate(self):
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except Exception:
                pass

    # ---------------- 新人即时建卡 ----------------
    @filter.event_message_type(EventMessageType.GROUP_MESSAGE)
    async def new_member_card(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        uid = str(event.get_sender_id() or "")
        if not uid or (umo, uid) in self._known:
            return
        if self._card(umo, uid) is not None:
            self._known.add((umo, uid))
            return
        # 群太大就不建：用已有的卡数当活跃人数上限的近似
        with self._conn() as c:
            n = c.execute("select count(*) from cards where group_id=?", (umo,)).fetchone()[0]
        if n >= MAX_MEMBERS:
            return
        text = (event.message_str or "").strip().replace("\n", " ")[:40]
        if not text:
            return
        nick = getattr(getattr(event.message_obj, "sender", None), "nickname", "") or uid
        self._upsert(umo, {
            "user_id": uid, "nick": str(nick)[:24], "tags": "", "note": "初次见面：" + text,
        }, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), count=0)

    # ---------------- 注入 ----------------
    @filter.on_llm_request()
    async def inject_card(self, event: AstrMessageEvent, req=None):
        if not INJECT_ENABLE or event.is_private_chat():
            return
        umo = event.unified_msg_origin
        uid = str(event.get_sender_id() or "")
        card = self._card(umo, uid)
        if not card:
            return
        bits = []
        if card.get("tags"):
            bits.append("，".join(card["tags"].split(",")))
        if card.get("note"):
            bits.append(card["note"])
        if not bits:
            return
        line = "【你对这个群友的印象】%s：%s" % (card.get("nick") or uid, "；".join(bits))
        try:
            last = datetime.strptime(card.get("last_seen") or "", "%Y-%m-%d %H:%M:%S")
            if (datetime.now() - last).days >= STALE_DAYS:
                line += "（已经 %d 天没来了）" % (datetime.now() - last).days
        except Exception:
            pass
        req.extra_user_content_parts.append(TextPart(text=line))

    # ---------------- 指令 ----------------
    @filter.command("印象")
    async def cmd_imprint(self, event: AstrMessageEvent):
        umo = event.unified_msg_origin
        arg = (event.message_str or "").lstrip("/").replace("印象", "", 1).strip()
        cards = self._cards(umo)

        if arg in ("更新", "刷新"):
            try:
                admins = self.context.get_config(umo=umo).get("admins_id", [])
            except Exception:
                admins = []
            if admins and str(event.get_sender_id()) not in [str(a) for a in admins]:
                yield event.plain_result("这个只有管理员能按")
                return
            yield event.plain_result("行，我去翻记录")
            try:
                n = await self._update_group(umo, datetime.now() - timedelta(hours=24), "manual")
                yield event.plain_result("更新了 %d 个人的印象" % n)
            except Exception as e:
                yield event.plain_result("翻车了：%s" % e)
            return
        if not cards:
            yield event.plain_result("这个群我还没有印象，等我说两天话")
            return
        if arg:
            hit = [c for c in cards.values() if arg in (c.get("nick") or "") or arg == c["user_id"]]
            if not hit:
                yield event.plain_result("没这个人")
                return
            c = hit[0]
            yield event.plain_result("%s：%s %s" % (c.get("nick"), c.get("tags") or "", c.get("note") or ""))
            return
        uid = str(event.get_sender_id() or "")
        c = cards.get(uid)
        if not c:
            yield event.plain_result("我还没记住你，多聊两句")
            return
        yield event.plain_result("%s：%s %s" % (c.get("nick"), c.get("tags") or "", c.get("note") or ""))
