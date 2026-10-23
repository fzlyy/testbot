# AGENTS.md

给在本仓库里干活的 AI 代理/协作者。**先读完第 2、5、6 节再动手**：这个项目最容易出事的三件事是「配置被运行中的实例覆盖」「密钥进仓库」「把已废弃的本地部署方式又捡回来」。

---

## 1. 项目是什么

阿里云 ECS 上跑的一套 QQ「AI 群友」：

```
QQ 小号 ←扫码登录→ NapCat（OneBot v11 协议端）← 反向 WS → AstrBot ← HTTPS → api.deepseek.com
```

**这不是 Web 项目**，没有前后端代码、没有构建产物。除了两个自写插件，其余全是现成软件的编排与配置。

**本地部署方式已废弃**（2026-10 起）：原先 Windows 本机那套 `.venv` + NapCat Shell + `start-*.cmd` 已全部删除，仓库只保留云端部署所需的编排文件、插件源码和文档。看到任何 `start-all.cmd`、`napcat/shell/`、`.venv` 的说明都是历史残留，不要恢复。

---

## 2. 线上环境（唯一权威）

| 项 | 值 |
|---|---|
| 公网 IP | `8.147.107.136` |
| 实例 ID | `i-2ze3xrryab2ets4hr7r2`（cn-beijing） |
| 系统 | Alibaba Cloud Linux 3 (OpenAnolis)，x86_64 |
| 规格 | 2 vCPU / 1.8 GB 内存 / 40 GB 盘（**已加 2 GB swap**） |
| Docker | 26.1.3 + compose v2.27.0 |
| 部署目录 | `/opt/astrbot-napcat` |

登录方式见下面 2.1。**凭据不在仓库里**；服务器上 `/opt/astrbot-napcat/CREDENTIALS.txt`（权限 600）记着面板账号、端口和目录。

### 2.1 怎么连上去

**A. 阿里云 Workbench（什么都不用装）**

控制台 → 云服务器 ECS → 实例 → 远程连接 → Workbench → 输入 root 密码。断网重连也不受影响，适合临时看一眼。

**B. 本机 ssh（Windows 10/11 自带 OpenSSH）**

```powershell
ssh root@8.147.107.136
```

首次连接会问 `The authenticity of host ... (yes/no)`，输 `yes` 回车。**密码不入库**，放在你自己的密码管理器里；输密码时屏幕上没有任何回显，不是卡住了。

**C. 配免密登录（推荐，省掉每次输密码）**

```powershell
ssh-keygen -t ed25519 -C "astrbot-ops"        # 一路回车，不设 passphrase
type $env:USERPROFILE\.ssh\id_ed25519.pub | ssh root@8.147.107.136 "mkdir -p ~/.ssh && chmod 700 ~/.ssh && cat >> ~/.ssh/authorized_keys && chmod 600 ~/.ssh/authorized_keys"
ssh root@8.147.107.136                         # 之后直接进
```

**D. 用 `deploy/remote.py` 跑命令 / 传文件**

本机已无 `.venv`，需要自己装一次依赖：

```powershell
python -m pip install paramiko
$env:AHOST='8.147.107.136'; $env:AUSER='root'
$env:APASS='<root 密码>'          # 或者用密钥： $env:AKEY="$env:USERPROFILE\.ssh\id_ed25519"

python deploy\remote.py run "cd /opt/astrbot-napcat && docker compose ps"
python deploy\remote.py run --file ops.sh         # 上传 /tmp 后执行
python deploy\remote.py put local.txt /tmp/x.txt
python deploy\remote.py get /tmp/x.txt local.txt
```

`remote.py` 里的命令默认在 `/` 下执行，涉及项目的命令记得先 `cd /opt/astrbot-napcat`。

**连不上时按这个顺序查**

| 现象 | 原因 |
|---|---|
| `Connection timed out` | 安全组没放行 22（Workbench 走控制台，不受影响） |
| `Permission denied (publickey,password)` | 密码错，或 `AUSER` 不是 `root` |
| `REMOTE HOST IDENTIFICATION HAS CHANGED` | 重置过系统/换过机器，旧指纹失效：`ssh-keygen -R 8.147.107.136` |
| 能登录但 `docker` 权限不足 | 用 `root` 登录，或 `usermod -aG docker <user>` |

**进去之后先跑这三条**

```bash
cd /opt/astrbot-napcat
docker compose ps        # 两个容器应当 Up
cat CREDENTIALS.txt      # 面板账号 / 端口 / 目录
```

> 目录里那个 `CREDENTIALS.txt` 是**进去之后**才看得到的；SSH 密码本身不写进服务器上的任何文件，也不写进仓库。

---

## 3. 目录与关键路径（服务器上）

| 路径 | 是什么 | 能不能动 |
|---|---|---|
| `/opt/astrbot-napcat/docker-compose.yml` | 两个容器的编排 | 可改，改完 `docker compose up -d` |
| `/opt/astrbot-napcat/.env` | `NAPCAT_WEBUI_TOKEN` | 不要提交 |
| `/opt/astrbot-napcat/data/astrbot/` | AstrBot 的 data 目录 | 核心，动前先备份 |
| `…/data/astrbot/cmd_config.json` | **主配置**（含 API Key、人设 ID、记忆参数） | 改，但必须先停服务（见 6.1） |
| `…/data/astrbot/data_v4.db` | SQLite：会话、人设、群消息历史、统计 | 可改，先停服务 |
| `…/data/astrbot/plugins/` | 插件（含本仓库的两个） | 可改，改完重启 |
| `…/data/astrbot/plugin_data/` | 各插件自己的数据（`meme_manager` 的表情包库已占 600 MB+） | 按需清理 |
| `…/data/napcat/config/` | NapCat 配置（`onebot11.json`、`webui.json`） | 可改，删了会重新生成 |
| `…/data/qq/` | QQ 登录态 | **不要删**，删了要重新扫码 |
| `/opt/astrbot-napcat/backups/` | 人设与配置的 JSON 快照 | 保留 |

---

## 4. 架构与端口

| 端口 | 归属 | 绑定 | 说明 |
|---|---|---|---|
| 6185 | AstrBot WebUI | 宿主机 `0.0.0.0` | 面板，公网可达（靠安全组管） |
| 6099 | NapCat WebUI | 宿主机 `0.0.0.0` | 扫码/看登录状态，需要 `WEBUI_TOKEN` |
| 6199 | AstrBot 反向 WS | **仅容器网络** | NapCat 主动连 `ws://astrbot:6199/ws`，**不要映射到公网** |
| 3001 | NapCat HTTP/WS | 不用 | 本项目不涉及 |

外网能访问的只有 6185 / 6099，安全组应当把来源限制在自己的 IP。

---

## 5. 硬性约定（违反会直接坏）

### 5.1 改配置前先停服务

**运行中的 AstrBot 会在退出时用内存配置覆盖 `cmd_config.json`。** 正确顺序：

```bash
cd /opt/astrbot-napcat && docker compose stop astrbot
# 改 data/astrbot/cmd_config.json（python + json，保 BOM、indent=2、newline="\n"）
docker compose start astrbot
```

`data_v4.db` 同理——改人设、清会话都先停。

### 5.2 不要把密钥写进仓库

`cmd_config.json` 里有 DeepSeek API Key；`CREDENTIALS.txt` 里有面板密码；`deploy/.env` 里有 NapCat token。三者都不进 git。提交前：

```bash
git grep --cached -n -I -E "sk-[A-Za-z0-9]{10,}"
git grep --cached -n -I "password|token"
```

### 5.3 文件编码

- JSON 配置是 **UTF-8 带 BOM**，用 `encoding="utf-8-sig"` 读写，丢了 BOM 或换成 CRLF 都可能让 AstrBot 读出乱码配置。
- 插件 Python 源码用 UTF-8；Windows 下用 PowerShell 写文件容易带上 BOM，Python 能接受，但别用 `Set-Content -Encoding Default`（会写成 GBK）。

### 5.4 别随手升级/加插件

AstrBot 升版会动字段结构；插件市场里第三方插件（尤其 `self_learning`）会**自动改写人设**。加之前先想清楚，加之后立刻备份 `personas` 表。

---

## 6. 怎么改配置

### 6.1 `cmd_config.json`

停服务 → 用 Python 读写（保 BOM）→ 起服务 → 看日志确认没报错。

关键字段速查：

| 字段 | 含义 |
|---|---|
| `agent_runner.config.persona.persona_id` | 当前生效人设的 `persona_id` |
| `agent_runner.config.model.provider_id` | 当前对话模型 |
| `agent_runner.config.compression.max_turns` / `trim_turns` | 会话保留轮数 / 超限丢弃轮数 |
| `provider_ltm_settings.group_icl_enable` / `group_message_max_cnt` | 群聊上下文注入 |
| `provider_ltm_settings.group_message_history_enable` | 群消息落库（`platform_message_history`） |
| `provider_ltm_settings.active_reply` | 随机插话（`possibility_reply` 概率、`whitelist` 群号） |
| `platform_settings.segmented_reply` | 分段回复（`interval`、`content_cleanup_rule`） |
| `platform_settings.rate_limit` | 出站限流，**按单条消息计** |

### 6.2 人设（`personas` 表）

```bash
cd /opt/astrbot-napcat && docker compose stop astrbot
python3 - <<'PY'
import sqlite3
db = sqlite3.connect('data/astrbot/data_v4.db')
for pid, n in db.execute("select persona_id, length(system_prompt) from personas"):
    print(pid, n)
PY
```

表字段：`persona_id / system_prompt / begin_dialogs / tools / skills / custom_error_message / folder_id / sort_order`。

**`begin_dialogs` 的格式很坑**：必须是**偶数条**的字符串数组，按位置交替当 user / assistant，**不要写 `"user: xxx"` 前缀**（`persona_mgr.py` 按 `user_turn` 交替赋值，前缀会被当成正文）。

改完必须重启（人设在启动时加载），并把 `persona_id` 指过去。

> 线上人设随时可能被人在面板里改，**以服务器实际值为准**，不要相信仓库里某份 md 就是生效版本。`persona-jingyuni.md` 是某版草稿与调参记录，`persona-dafeiyu.md` / `persona-ai-groupmate.md` 是历史备选。

### 6.3 模型与 provider

`provider_sources[]` 存连接（`api_base`、`key[]`、`timeout`），`provider[]` 存具体模型实例，用 `provider_source_id` 关联。当前布局：

| provider id | 模型 | `custom_extra_body` | 用途 |
|---|---|---|---|
| `deepseek/deepseek-flash` | flash | `{}` | 默认档，备用/回退 |
| `deepseek/deepseek-flash-high` | flash | `{"reasoning_effort": "high"}` | **对话 + 判别都在用** |
| `deepseek/deepseek-v4-pro` | v4-pro | `{}` | 更会说话但慢，未启用 |

实测结论（别再重复踩）：

- 这个 API 端点对 `deepseek-chat` / `deepseek-reasoner` 会**静默映射成 flash**，只有 `deepseek-flash` 和 `deepseek-v4-pro` 是真模型。
- `thinking: {"type": "disabled"}` 有效（reasoning 0、0.4s）；`reasoning_effort: high` 有效但方差大（思考 token 约 1.7 倍）。
- 在**二分类判别**任务上，关思考明显不比开思考差；v4-pro 更慢且更差。判别器该优先调提示词和 few-shot，不是加思考。

---

## 7. 记忆是怎么分层的

| 层 | 存在哪 | 现在 |
|---|---|---|
| 会话上下文 | `data_v4.db` 的 `conversations.content`（JSON） | 每会话 30 轮，超了丢最早 6 轮，再超走 `llm_compress` |
| 群聊上下文 | **进程内存** deque，不落盘 | 40 条，注入后即消费，重启清空 |
| 群历史库 | `platform_message_history` 表 | 700 条/群，模型可用 `get_group_message_history` 工具翻 |
| 群友印象 | `plugin_data/group_imprint/imprint.db` | 自研插件，见 8.2 |
| 知识库 | `data/astrbot/knowledge_base/kb.db` | 空 |

---

## 8. 自研插件（仓库里有源码，改完拷到服务器）

### 8.1 `astrbot_plugin_nick_wake` — 什么时候该说话

AstrBot 默认只有「@机器人 / 引用机器人 / @全体 / `/` 开头」才唤醒。这个插件补三层判定：

1. 消息含昵称（大肥鱼/肥鱼/鱼娘/鲸鱼娘）→ 直接唤醒
2. 它 90 秒内说过话，或含高精度信号词（它/这鱼/这货/是不是在说我）→ 调一次判别
3. 判别为 YES → 唤醒（带 20 秒冷却、每小时 20 次唤醒上限、每小时 60 次判别上限）

判别用 `JUDGE_PROVIDER_ID` 指定的 provider，**提示词里有 4 个 few-shot 例子**，改判别行为优先改例子，不要先动参数。

> 历史教训：v2.1 曾允许「紧跟在它后面的短句直接唤醒」，在活跃群里把 `cd了`、`omg`、`下锅了` 全当成在跟它说话。**不要再加这种免检旁路。**

### 8.2 `astrbot_plugin_group_imprint` — 群友印象

- 每天 **04:30** 读过去 24h 的 `platform_message_history`，按人聚合，一次 LLM 调用产出印象卡（标签 + 一句话），与旧卡**合并**而非重建
- **12:30** 增量：某人当天发言 ≥30 条才补跑
- 新人第一次说话立刻建极简卡（零 LLM）
- 注入时**只给当前发言人**那一张（约 60~80 字），不给全群
- 只服务小群：过去 24h 发言人数 > 20 直接跳过

指令：`/印象`、`/印象 昵称`、`/印象 更新`（管理员）。

---

## 9. 已知坑速查

| 现象 | 原因 | 做法 |
|---|---|---|
| `docker pull` 卡死/超时 | 这台机器直连 Docker Hub 不通 | 镜像名一律加 `m.daocloud.io/docker.io/` 前缀 |
| 装完面板密码登不上 | 运行中改配置被内存覆盖，或密码没写进去 | 停服务再写；用 `pbkdf2_sha256$600000$…` 格式写入 `dashboard.pbkdf2_password` |
| 群里不回复 | 没 @ 它；或 `nick_wake` 判 NO | `docker logs astrbot \| grep nick_wake` |
| 它乱接话 | 判别阈值/温度问题 | 调 `nick_wake/main.py` 顶部的 `WINDOW_SEC`、`SIGNALS`、冷却 |
| 突然发不出消息，日志 `-10203 Ban state forbit write req` | QQ 风控：短时间批量发送 | 停发一段时间；`rate_limit` 收紧；不要新号当天刷屏 |
| 人设突然变了 | `self_learning` 的 `enable_persona_evolution` | 关掉演化，或从 `backups/` 恢复 |
| 回复慢 3 秒+ | `reasoning_effort: high` | 把 `model.provider_id` 换回 `deepseek/deepseek-flash` |
| `@全体成员` 也回 | `ignore_at_all` 为 false | 现为 true，别改回去 |
| 改完 `.md` 但行为没变 | 人设/配置只在启动时读 | 重启 `astrbot` 容器 |

---

## 10. 运维命令

```bash
cd /opt/astrbot-napcat
docker compose ps
docker compose restart astrbot        # 改完配置/人设/插件
docker compose stop astrbot           # 改配置前
docker logs -f astrbot
docker logs -f napcat
docker stats --no-stream              # 内存：napcat ~200MB, astrbot ~250MB

# 备份（配置 + 人设库）
tar czf /root/astrbot-backup-$(date +%F).tgz \
  -C /opt/astrbot-napcat data/astrbot/cmd_config.json data/astrbot/data_v4.db
```

---

## 11. 红线

- **6199 永远不要映射到公网**；6185/6099 的安全组来源尽量限自家 IP。
- **不要提交任何密钥**（API Key、面板密码、WebUI token、QQ 登录态）。
- NapCat 是非官方客户端，**有封号风险**：只用小号，不做加群/群发/刷屏。
- 群聊内容会发给第三方 API（DeepSeek），开 `group_icl` / 长期记忆时注意扩大范围的影响。
- `data/qq/` 是登录态，删了要重新扫码；`plugin_data/meme_manager/` 已 600 MB+，清理时别无脑删整个目录。

---

## 12. 改完之后必须做的验证

1. `docker compose ps`：两个容器 `Up`
2. `docker logs astrbot | grep '适配器已连接'`：出现 `aiocqhttp(OneBot v11) 适配器已连接。`
3. 面板 `http://<IP>:6185` 能登录
4. 群里 @ 它一句，确认有回复且风格符合人设

没有 2、4 就不算改完，别只凭「文件改对了」下结论。
