# NapCat + AstrBot 打造 DeepSeek「AI 群友」（Windows 完整版）

> 目标：QQ 群里挂一个用 DeepSeek 驱动的机器人，能看懂群里在聊什么、有人 @ 它就接话、偶尔自己插一句，
> 说话像群友而不是客服。本机 Windows 部署，全程图形界面 + 少量命令。

---

## 0. 先看懂这张图

```
QQ 客户端（你的小号）
      │  扫码登录
      ▼
NapCatQQ  ── 把 QQ 协议翻译成 OneBot v11
      │  作为「客户端」主动连出去：ws://127.0.0.1:6199/ws
      ▼
AstrBot   ── 作为「服务端」接住连接（默认 6199），管人设/上下文/插件
      │  HTTPS
      ▼
DeepSeek API（api.deepseek.com）
```

四个端口，记牢就不会配错：

| 端口 | 谁在用 | 说明 |
|---|---|---|
| **6185** | AstrBot WebUI | 浏览器打开 `http://localhost:6185` 做所有配置 |
| **6199** | AstrBot 反向 WS | NapCat 要连的地址，路径固定 `/ws` |
| **6099** | NapCat WebUI | 建 OneBot 连接、看登录状态 |
| 3001 | NapCat HTTP/WS | 本方案用不到，别开 |

**方向别搞反**：AstrBot 是服务端（只监听，不主动连），NapCat 是客户端（主动去连 AstrBot）。
所以 NapCat 里要新建的是「**WebSockets 客户端**」，不是「WebSockets 服务器」。

---

## 1. 准备

- [ ] Windows 10/11，4 GB 内存以上（NapCat 会带一个 QQ 进程，比较吃内存）
- [ ] **一个 QQ 小号**，不要用主号（原因见第 10 节，这条最重要）
- [ ] DeepSeek API Key，账户里有余额：<https://platform.deepseek.com/api_keys>
- [ ] 这个 QQ 号已加入目标群，并且能在群里正常发言（新号建议先养几天）

> 判断你是否需要 AstrBot 的「官方 QQ 机器人」路线：那条路要企业/个人开发者资质、机器人只能在被邀请的群里用。
> 想让它像个普通群友一样待在任意群里，只能走 NapCat（非官方协议端）这条路——这也正是本教程的路线。

---

## 2. 装 AstrBot

三种方式，任选其一。**推荐 A：最省事。**

### A. 桌面客户端（图形化，Windows 首选）

1. 打开 <https://github.com/AstrBotDevs/AstrBot-desktop/releases>
2. 下载 `.exe` 安装包，安装并启动
3. 按向导初始化，记下它显示的 WebUI 地址（默认 `http://localhost:6185`）和初始密码

### B. 一键脚本（uv 方式，可控性好）

PowerShell 里执行（**不要**用管理员窗口跑，装到当前用户目录）：

```powershell
iwr -useb https://docs.astrbot.app/install.ps1 | iex
```

装完后：

```powershell
astrbot init   # 只跑一次，在当前目录初始化环境
astrbot run    # 启动；以后每次都用这条
```

启动日志里会打印 `🌈 管理面板已启动` 和**随机初始密码**（用户名 `astrbot`）。
登录后第一件事：改密码。

### C. Docker（想跟 NapCat 一起容器化，见 `docker-compose.yml`）

```powershell
docker run -itd -p 6185:6185 -p 6199:6199 -e TZ=Asia/Shanghai `
  -v "${PWD}\data:/AstrBot/data" --name astrbot soulter/astrbot:latest
docker logs -f astrbot     # 看初始密码
```

大陆网络拉不动镜像时，把镜像名换成 `m.daocloud.io/docker.io/soulter/astrbot:latest`。

> 打开 `http://localhost:6185`，能登录进管理面板，这一步就算过了。

---

## 3. 接上 DeepSeek

在 AstrBot WebUI 里操作：

1. 左侧 **模型提供商** → 顶部 **对话** → **新增**
2. 提供商类型选 **DeepSeek**（列表里没有就选 **OpenAI Compatible**，效果一样）
3. 填：

   | 字段 | 值 |
   |---|---|
   | 名称 | `deepseek` |
   | API Key | `sk-...`（也可填 `$DEEPSEEK_API_KEY` 走环境变量） |
   | API Base URL | `https://api.deepseek.com/v1` |

4. 点 **保存并获取模型**
5. 在模型列表里找到 **`deepseek-flash`**，点右边 `+` 启用；顺手点「测试模型」确认能通
   - 追求质量、不在意价格 → 同时启用 `deepseek-v4-pro`
   - 列表里没有想要的：点 **自定义模型**，模型 ID 直接填 `deepseek-flash`
6. 左侧 **配置文件** → 选默认配置 → **AI** → **模型** → 把「对话模型」设为刚启用的 `deepseek-flash` → 右下角 **保存配置**

> 模型名注意：DeepSeek 现在的正式模型是 `deepseek-flash` 和 `deepseek-v4-pro`，
> 老的 `deepseek-chat` / `deepseek-reasoner` 已不是主推，别照抄旧教程。
> 群聊场景建议 `deepseek-flash`：快、便宜，接话体验比「深思熟虑 20 秒」好得多。

**先自测**：点右上角 **Chat** 进 ChatUI，发一句「你好，用一句话介绍你自己」。
有正常回复 → 模型这条链路通了，再往下做 QQ。

---

## 4. 装 NapCat 并登录 QQ

### 方案 A：一键安装包（连 QQ 一起装，最省事）

1. 下载 `NapCat.Shell.Windows.OneKey.zip`：<https://github.com/NapNeko/NapCatQQ/releases/latest>
2. 解压，运行 `NapCatInstaller.exe`，等它装完
3. 进入生成的 `NapCat.XXXX.Shell` 目录，双击 `napcat.bat` 启动
4. 按控制台提示扫码 / 快速登录（`napcat.bat 123456789` 可带 QQ 号快速登录）

### 方案 B：Shell 包（你机器上已有 QQ）

1. 安装 QQ，下载并解压 `NapCat.Shell.zip`（同一个 Releases 页）
2. 双击 `launcher.bat`；Win10 用 `launcher-win10.bat`，也可 `launcher.bat 123456789`
3. 按提示登录

登录成功后控制台会打印 **NapCat WebUI 地址**（默认 `http://127.0.0.1:6099`）和 **Token**，
把这行日志复制出来留着，下一步要用。

> 建议顺手在 NapCat WebUI 的「配置文件」里把 `fileLog` / 日志级别调到 info，出问题时好排查。

---

## 5. 打通 OneBot v11（唯一容易翻车的一步，对照做）

### 5.1 AstrBot 端：开一个「接收端口」

左侧 **机器人** → **创建机器人** → 选 **OneBot v11**：

| 字段 | 填写 |
|---|---|
| ID | `qq` （随意，仅用于区分实例） |
| 启用 | ✅ 勾选 |
| 反向 WebSocket 主机地址 | `0.0.0.0` |
| 反向 WebSocket 端口 | `6199` |
| 反向 Websocket Token | 留空；若你要设，必须和 NapCat 那边**完全一致** |

点 **保存**。

### 5.2 NapCat 端：建一个「往外连」的客户端

打开 NapCat WebUI（`http://127.0.0.1:6099`，用日志里的 Token 登录）：

1. **网络配置** → **新建** → 选 **WebSockets 客户端**
2. 填写：

   | 字段 | 填写 |
   |---|---|
   | 启用 | ✅ |
   | URL | `ws://127.0.0.1:6199/ws` ← 注意 **`/ws` 不能少** |
   | Token | 留空（或与 AstrBot 端一致） |
   | 心跳间隔 | `1000` |
   | 重连间隔 | `1000` |

3. 保存

### 5.3 验证

回到 AstrBot → **数据与日志** → **日志**，看到这条蓝色日志就成了：

```
aiocqhttp(OneBot v11) 适配器已连接。
```

没出现、过几秒反而出现「aiocqhttp 适配器已被关闭」→ 连接失败，按顺序查：

1. AstrBot 那条机器人配置是否 **启用**（未启用时 6199 端口根本不监听）
2. URL 是不是漏了 `/ws`
3. 两端 Token 是否一致（一边空一边有也会失败）
4. 本机防火墙是否拦了 6199（本机互连一般不受影响）
5. NapCat 里建的是不是「WebSockets **客户端**」

### 5.4 第一次真机测试

在 QQ 里用**另一个号**（或让群友）在群里 **@ 你的机器人** 发一句「你好」。

- 有回复 → 主链路完全打通，进入第 6 节调参
- 没回复 → 看第 9 节排查表

---

## 6. 从「问答机」调成「群友」

默认配置下的机器人是这样的：只在被 @ 时回答，不知道群里前面聊了什么，一次吐一大段。
下面每一项都在 **配置文件 → 平台与消息 / 扩展功能** 里，改完记得点右下角 **保存配置**。

### 6.1 触发方式：它什么时候该说话

**平台与消息 → 消息触发方式**

- 群聊默认：**@ 它** 才回；也可以设「唤醒词」（如 `小D`），群里喊「小D 在吗」就唤醒
- `empty_mention_waiting`（只 @ 不说话时等 60 秒合并下一条）建议**开**，手机上「先 @ 再打字」很常见
- 私聊一般不需要唤醒词；如果你想连私聊也要前缀，再开 `friend_message_needs_wake_prefix`

### 6.2 人设：这是「像不像群友」的决定性因素

**AI → 人格 → 新建**，把 `persona-ai-groupmate.md` 里的内容整段粘进 system prompt，再按你们群的调性改。

要点（比堆砌关键词有用得多）：

- 交代**身份和关系**：它在这个群里是什么角色、跟谁熟
- 限定**长度**：群聊一条回复 1~3 句，别写小作文
- 给**具体口癖**，别给形容词：「习惯性反问」「偶尔用『草』」，而不是「说话幽默风趣」
- 明确**不知道就说不知道**，禁止编造群内事实
- 禁止它自称 AI 助手、客服、模型

### 6.3 让它知道群里在聊什么（最关键的一项）

**扩展功能 → 群聊上下文感知**

| 配置 | 建议值 | 作用 |
|---|---|---|
| 群聊记录注入上下文 | **开** | 把最近的群消息塞进系统提示词，它才看得懂上下文 |
| 保留群聊消息条数 | `30 ~ 60` | 默认 1000 太夸张，token 会爆、还会答非所问 |
| 群聊图片转述 | 先**关** | 开了每张图都要额外调一次模型，费用翻倍 |

关联项（**AI → 高级** 附近）：

- `identifier` 开 → 提示词里带发言人昵称，它能分清「谁在说」，多人接话时体验提升明显（略费 token）
- `group_name_display` 开 → 让它知道自己在哪个群（仅 QQ 生效）

### 6.4 让它「自己插话」

**扩展功能 → 主动回复**

- 启用，方式 `possibility_reply`
- 概率 `0.05 ~ 0.15`（**别超过 0.2**，否则变成刷屏怪，很快被群友踢）
- 白名单填你的目标群会话 ID：先在群里发 `/sid` 拿到类似 `aiocqhttp:GroupMessage:123456789`，粘进去

配合 6.3 的上下文注入，才有「看懂气氛后接一句」的效果；没开上下文它插话就是随机抽风。

### 6.5 让输出像人打的字

**平台与消息 → 发送行为** / **扩展功能 → 分段回复**

| 配置 | 建议 | 效果 |
|---|---|---|
| 分段回复 | 开，间隔 `1.0,2.5` 秒 | 长回复拆成几条发，像连续打字 |
| 引用回复 `reply_with_quote` | 开 | 群聊里指代清楚，不@也不会认错人 |
| 回复时 @ `reply_with_mention` | 看群习惯 | 人少的群建议关，@ 多了像告示 |
| 转发阈值 `forward_threshold` | `800 ~ 1200` | 超长回复折叠，防刷屏 |

### 6.6 会话隔离：每个群友各聊各的

**平台与消息 → 会话隔离（`unique_session`）**

- **关**（默认）：整个群共用一份上下文，像真群聊，大家能接彼此的话
- **开**：每个群成员独立上下文，私密性好，但群里「你一句我一句」会断裂

做「AI 群友」→ **关**；做「群里每人一个专属助手」→ **开**。

### 6.7 控制成本

| 手段 | 位置 | 说明 |
|---|---|---|
| `max_context_length` | AI → 高级 | 设 `20~40` 轮，历史太长又贵又慢 |
| 群聊消息条数 | 扩展功能 | ≤ 60 条 |
| 图片转述 | 扩展功能 | 非必要不开 |
| 模型 | 模型提供商 | 群聊用 `deepseek-flash` |
| 限速 | 平台与消息 | `rate_limit` 保持默认 30 条/60 秒，防炸群 |
| 白名单 | 访问控制 | 只放行你的群，别让它进一堆群乱说话 |

---

## 7. 推荐配置一览（照抄即可）

| 区域 | 配置项 | 值 |
|---|---|---|
| 访问控制 | 白名单 | 你的群 ID |
| 平台与消息 | 会话隔离 | 关 |
| 平台与消息 | 引用回复 | 开 |
| 平台与消息 | 回复时 @ | 关 |
| 平台与消息 | 限速 | 30 次 / 60 秒，stall |
| 扩展功能 | 群聊上下文 | 开，30 条 |
| 扩展功能 | 主动回复 | 开，0.1，白名单=你的群 |
| 扩展功能 | 分段回复 | 开，`1.0,2.5` |
| AI | 对话模型 | `deepseek-flash` |
| AI | 人格 | 你写的「群友」人格 |
| AI | 上下文长度 | 30 |
| 其他 | 转发阈值 | 1000 |

`config-snippet.json` 里是同名的 JSON 键值，可在 WebUI 右下角 `{}` → **编辑配置文件** 里对照修改。

---

## 8. 日常使用与维护

| 操作 | 做法 |
|---|---|
| 清空这个群的记忆 | 群里发 `/new` 或 `/reset` |
| 查会话 ID（配白名单/主动回复用） | 群里发 `/sid` |
| 加/删管理员 | `/op`、`/deop`，或 访问控制 → 管理员 ID |
| 看它到底收到什么、调了什么 | 数据与日志 → 日志（把级别调 DEBUG） |
| 它被 @ 却装死 | 先看日志有没有 `GroupMessage` 事件进来：有事件=逻辑问题，无事件=连接/白名单问题 |
| 换人设 | AI → 人格，改完保存；必要时 `/new` 让新人格立刻生效 |
| 备份 | 整个 `data/` 目录拷走即可（含配置、人格、对话记录） |

---

### 8.5 一键自检

配完不确定哪里不通时，先跑这个（只读，不改任何东西）：

```powershell
.\scripts\check-stack.cmd -ApiKey sk-你的key
```

它会逐项报告：6185 / 6199 / 6099 是否在监听（附占用进程）、QQ 与 AstrBot 进程、配置文件位置、
到 `api.deepseek.com:443` 的连通性、Key 是否有效、可用模型列表、`deepseek-flash` 实测延迟与 tokens。

- 被「禁止运行脚本」拦住时用 `.cmd`（内部已带 `-ExecutionPolicy Bypass`）；
  或手动：`powershell -ExecutionPolicy Bypass -File .\scripts\check-stack.ps1`
- 需要走代理：`-Proxy http://127.0.0.1:7890`（或先设环境变量 `HTTPS_PROXY`）
- 只想查端口/进程：加 `-SkipApi`
- 全部通过也不代表 QQ 能收发消息——真正的连接成功标志仍是日志里那句
  `aiocqhttp(OneBot v11) 适配器已连接。`

---

## 9. 排查表

| 现象 | 常见原因 | 处理 |
|---|---|---|
| 日志无「适配器已连接」 | URL 少 `/ws`、Token 不一致、AstrBot 机器人未启用 | 逐项核对 5.1 / 5.2 |
| 连上又立刻断开 | 端口冲突（6185/6199 被占）、AstrBot 崩溃 | 换端口；看 AstrBot 报错日志 |
| 适配器已连接但 @ 不回复 | ID 白名单开了却没加这个群；被 @ 的是机器人自己发的消息 | 访问控制加群 ID；或先关白名单测试 |
| 有人说话它反而插嘴 | 主动回复概率过高 | 降到 0.05~0.1 |
| 回复内容跟群里话题无关 | 没开群聊上下文，或条数太少 | 开 `group_icl_enable`，条数调到 30+ |
| 回复很慢（10 秒+） | 用了 pro 模型 / 上下文太长 / 开了思考模式 | 换 `deepseek-flash`，上下文降到 20 轮 |
| 报 401 / 403 | Key 错、被删除、复制带了空格 | 重新生成 Key，注意 Base URL 带 `/v1` |
| 报 402 / 余额不足 | 账户没钱 | 去平台充值 |
| 报 429 | 频率超限 | 降低主动回复概率，限速保持默认 |
| 回复报错「发送失败」 | QQ 风控 / 号被限制 / 群禁言 | 换号；确认号能在群里正常发言 |
| 中文乱码 / 时间不对 | 时区 | 系统设置 → 常规 → 时区 `Asia/Shanghai` |
| 重启电脑后失效 | 两个程序都没开机自启 | 加计划任务；或改用 Docker + `restart: unless-stopped` |

---

## 10. 风险与合规（务必读）

1. **用非官方客户端登录 QQ 存在封号风险。** NapCat 属于第三方协议端，腾讯不保证兼容。
   请用小号、别绑重要资产、别开自动加群/群发/刷屏功能，出事不要牵连主号。
2. **别把 6099 / 6199 暴露到公网。** 这两个端口一旦开放且无鉴权，等于把 QQ 号和机器人交给别人。
   只在 `127.0.0.1` 用；要在云服务器上跑，用 SSH 隧道或加防火墙白名单。
3. **群里的对话会发给 DeepSeek。** 提醒群友，别在群里发身份证、密码、公司内部资料。
4. **别让它自动转发/搬运别人的聊天记录** 到别处，这既是隐私问题也容易起冲突。
5. **群规优先。** 主动插话频率、是否 @、是否允许调戏，先跟群主和群友说清楚；被投诉就关掉主动回复。
6. 未成年人、医疗、法律、投资类话题，人格里明确要求「给方向、不给结论」。

---

## 11.5 一键启停（批处理）

日常只需要这几个 `.cmd`，双击即可，不用记命令。**顺序永远是 AstrBot 先、NapCat 后**。

| 脚本 | 作用 |
|---|---|
| `start-all.cmd` | 先起 AstrBot，等 6199 真正监听后再起 NapCat（推荐日常用这个） |
| `start-astrbot.cmd` | 只起 AstrBot，输出同时写进 `logs\astrbot-console.log` |
| `start-napcat.cmd` | 只起 NapCat，会先查注册表确认 QQ 已安装 |
| `stop-all.cmd` | 按端口停掉两者（停 NapCat 会连带关掉那个 QQ 实例） |
| `status.cmd` | 查三个端口、面板 HTTP、表情包库存、当前人设 |

细节：

- 每个启动脚本都会先检查端口，**已经在跑就跳过**，不会起第二个实例抢锁
- AstrBot 窗口里是实时日志，关窗口或 `Ctrl+C` 都会停服
- NapCat 会弹 UAC（要管理员权限注入 QQ），点「是」后扫码登录
- `stop-all.cmd` 用端口定位进程，所以 NapCat 的 PID 变了也不影响
- 想让它们在开机时自启，把 `start-all.cmd` 的快捷方式丢进
  `shell:startup`（Win+R 输入即可打开该目录）

---

## 12. 参考

- AstrBot 文档 · 接入 OneBot v11（NapCat 附录）：<https://docs.astrbot.app/platform/aiocqhttp.html>
- AstrBot 文档 · 接入模型服务（DeepSeek 步骤）：<https://docs.astrbot.app/providers/start.html>
- AstrBot 文档 · 配置文件全字段（上下文注入 / 主动回复）：<https://docs.astrbot.app/dev/astrbot-config.html>
- AstrBot 文档 · WebUI 菜单对照：<https://docs.astrbot.app/use/webui.html>
- DeepSeek 官方 · 接入 AstrBot：<https://api-docs.deepseek.com/quick_start/agent_integrations/astrbot/>
- DeepSeek 官方 · 模型与价格：<https://api-docs.deepseek.com/quick_start/pricing>
- NapCat 文档 · Shell / Windows 安装：<https://napneko.github.io/guide/boot/Shell>

---

## 本目录文件

| 文件 | 用途 |
|---|---|
| `README.md` | 就是本文 |
| `persona-ai-groupmate.md` | 「群友」人设提示词模板，直接粘进 AstrBot 人格 |
| `config-snippet.json` | 第 7 节配置对应的 JSON 键值，供 `编辑配置文件` 对照 |
| `docker-compose.yml` | 想用 Docker 同时跑 AstrBot + NapCat 的话用这份 |
| `scripts/check-stack.ps1` | 一键自检脚本（端口 / 进程 / API / 配置） |
| `scripts/check-stack.cmd` | 自检脚本的启动器，绕过 PowerShell 执行策略限制 |
| `start-all.cmd` / `start-astrbot.cmd` / `start-napcat.cmd` | 一键启动（见 11.5 节） |
| `stop-all.cmd` / `status.cmd` | 一键停止 / 状态检查 |
| `persona-dafeiyu.md` | 「大肥鱼」人设全文与调参对照 |
| `scripts/show-persona.cmd` | 打印当前生效的人设 |
