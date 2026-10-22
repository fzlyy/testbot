# AGENTS.md

给在本仓库里干活的 AI 代理/协作者看的说明。**先读完第 5、6 节再动手**，这个项目里最容易出事的不是代码，是「配置被覆盖」和「编码」。

---

## 1. 这个项目是什么

Windows 本机跑的一套 QQ「AI 群友」：一个 QQ 小号通过 **NapCat**（OneBot v11 协议端）接到 **AstrBot**，
再由 AstrBot 调 **DeepSeek** 生成回复，人设是一条沙雕胖鲸鱼「大肥鱼」。

**不是什么**：不是 Web 项目，没有前后端代码，没有构建产物。除了一个自写的小插件，其余全是现成软件的配置与编排。
所以「改代码」通常等于改 `data/cmd_config.json`、改 SQLite 里的人设、或改 `data/plugins/` 下的插件。

## 2. 架构与端口

```
QQ 客户端(小号) ←扫码登录→ NapCat ← ws://127.0.0.1:6199/ws → AstrBot ← HTTPS → api.deepseek.com
```

| 端口 | 归属 | 绑定 | 说明 |
|---|---|---|---|
| 6185 | AstrBot WebUI | `127.0.0.1` | 管理面板，故意只绑本机 |
| 6199 | AstrBot 反向 WS | `0.0.0.0` | **NapCat 是客户端，主动连这个端口**，路径必须是 `/ws` |
| 6099 | NapCat WebUI | `0.0.0.0` | 建 OneBot 连接、看登录状态，登录要 Token（在 NapCat 控制台） |
| 3001 | NapCat HTTP/WS | 不用 | 本项目不涉及 |

## 3. 目录与关键路径

| 路径 | 是什么 | 能不能动 |
|---|---|---|
| `.venv/` | Python 3.13 虚拟环境，装的是 PyPI 上的 `astrbot` | 别手改，用 pip 重装 |
| `data/cmd_config.json` | **AstrBot 主配置**（含 API Key） | 改，但必须先停服务（见 6.1） |
| `data/data_v4.db` | SQLite：人设、会话、消息历史 | 改人设走这里（见 6.2） |
| `data/plugins/astrbot_plugin_sticker_bank/` | 自写插件：偷表情包 + 回复配图 | 可改 |
| `napcat/shell/` | NapCat 4.18.38 解压目录 | 可升级，注意版本绑定（见 6.4） |
| `napcat/QQ_installer.exe` | QQ 9.9.33 安装包（300 MB） | 留着，重装用 |
| `logs/astrbot-console.log` | AstrBot 完整输出（Tee 写入，UTF-16） | 只读 |
| `persona-dafeiyu.md` | 人设可读版（**不是生效版本**） | 文档用途 |
| `scripts/` | 安装、配置修补、自检脚本 | 可改 |
| `*.cmd` | 启停批处理 | 可改，遵守 5.1 |

## 4. 运行环境（别随意升级）

| 组件 | 版本 | 备注 |
|---|---|---|
| Windows | 11 (22621) | 控制台默认 GBK/cp936 |
| Python | 3.13.6 | AstrBot 要求 ≥3.12 |
| AstrBot | 4.29.1 | PyPI 安装，不是 uv 装的 |
| NapCat Shell | 4.18.38 | 目标 QQ 构建 `9.9.22-40990` |
| QQ NT | 9.9.33.52230 | **必须落在 NapCat 的偏移表里**，见 6.4 |
| DeepSeek 模型 | `deepseek-flash` | 已关思考模式省 token |

## 5. 硬性约定（违反会直接坏）

### 5.1 `.cmd` 一律纯 ASCII

UTF-8 无 BOM 的中文在 cmd 里会按 GBK 解析，`echo` 行会碎成命令报错（本项目踩过，`scripts/show-persona.cmd` 第一版就是这么挂的）。
需要中文说明就写进 `.md`，不要写进 `.cmd`。

### 5.2 `.ps1` 要么纯 ASCII，要么存成 UTF-8 **带 BOM**

Windows PowerShell 5.1 会把无 BOM 的 UTF-8 当 ANSI 读，中文字符串会破坏解析（报 `hash literal was incomplete` 之类）。
现成做法：`scripts/01b-install-astrbot.ps1`、`run-astrbot.ps1` 全 ASCII。

### 5.3 停进程用 `Stop-Process`，不要用 `taskkill`

这台机器上 `taskkill /F /PID` 会返回 `ERROR: Access denied`（即使同用户），而 `Stop-Process -Id … -Force` 正常。
`stop-all.cmd` 已按此实现。

### 5.4 日志是 UTF-16，读的时候别指定 utf8

`logs/astrbot-console.log` 由 `Tee-Object` 写入，是 UTF-16LE。用 `Get-Content` 直接读，**不要** `Select-String -Encoding utf8`。
控制台输出本身是 GBK，中文在终端里可能显示成乱码，那是显示问题，不是数据问题。

### 5.5 改配置前先停服务

见 6.1。这是本项目最大的坑。

## 6. 怎么改配置（照抄流程）

### 6.1 改 `data/cmd_config.json`

**运行中的 AstrBot 会在退出/保存时用内存里的配置覆盖文件。** 所以：

1. `stop-all.cmd`（确认 6185/6199 都没监听）
2. 用 Python 改，且保持编码与缩进：

```python
import io, json
p = "data/cmd_config.json"
with io.open(p, encoding="utf-8-sig") as f:   # 文件带 BOM
    cfg = json.load(f)
# ... 修改 ...
with io.open(p, "w", encoding="utf-8-sig", newline="\n") as f:
    json.dump(cfg, f, ensure_ascii=False, indent=2)
```

3. `start-astrbot.cmd`，然后看日志确认没有加载报错

> 不要用 PowerShell 的 `ConvertFrom-Json | ConvertTo-Json` 往返，会丢 `null`/空数组语义，还可能改编码。

### 6.2 改人设（「大肥鱼」）

人设正文存在 `data/data_v4.db` 的 `personas` 表；**当前选中哪个人设**在
`cmd_config.json` → `agent_runner.config.persona.persona_id`。

```python
import sqlite3
db = sqlite3.connect("data/data_v4.db")
db.execute("update personas set system_prompt=?, updated_at=datetime('now') where persona_id=?",
           (new_prompt, "大肥鱼"))
db.commit()
```

- 只改库不改 `persona_id` → 不生效
- 只改 `persona_id` 不建对应 id → 回落默认人格
- 改完必须重启（人设只在启动时加载）
- 4.29 已废弃 `provider_settings.default_personality`，**别再往那里写**

### 6.3 改模型 / 换模型

`provider_sources[]` 存连接（`api_base`、`key[]`、`timeout`、`proxy`），`provider[]` 存具体模型实例，
用 `provider_source_id` 关联。当前 provider id 形如 **`deepseek/deepseek-flash`**（`源/模型`），
`provider_settings.default_provider_id` 必须与之一致。

Key 支持 `$ENV_VAR` 写法走环境变量；目前是明文存在 json 里。

### 6.4 升级 QQ / NapCat（高危）

NapCat 靠**精确的 QQ 构建号**定位内存偏移，偏移表在 `napcat/shell/napcat.mjs` 里，形如：

```
"9.9.33-52230-x64": { send: "BF2B5F", recv: "23BB4DD" },
```

升级 QQ 前先确认新构建号在表里，否则启动会显示「当前 QQ 版本低于 NativePacketClient 要求」并拒绝注入。
换 QQ 大版本时，NapCat 也要跟着换到匹配的 release。

## 7. 常用命令

```powershell
.\start-all.cmd          # AstrBot → 等 6199 → NapCat（日常）
.\start-astrbot.cmd      # 只起 AstrBot
.\start-napcat.cmd       # 只起 NapCat（会弹 UAC，需要扫码）
.\stop-all.cmd           # 按端口停两者
.\status.cmd             # 端口 / 面板 HTTP / 表情包库存 / 当前人设

.\scripts\show-persona.cmd                    # 打印当前生效人设全文
.\scripts\check-stack.cmd -ApiKey sk-xxx      # 全链路自检（端口/进程/API/模型）
.\scripts\check-stack.cmd -SkipApi            # 只查端口和进程
```

读日志：

```powershell
Get-Content logs\astrbot-console.log -Tail 50
# 连接成功的唯一标志
Select-String -Path logs\astrbot-console.log -Pattern 'aiocqhttp' -SimpleMatch
```

## 8. 已知坑速查

| 现象 | 原因 | 做法 |
|---|---|---|
| 配置改完没生效 | 运行中的实例用内存配置覆盖了文件 | 先停服务再改（6.1） |
| 6199 不监听 | `platform` 里没有 `aiocqhttp` 条目，或条目 `enable=false` | 检查 `platform[]` |
| 适配器连上又断 | URL 少了 `/ws`、两边 Token 不一致 | 对齐 AstrBot 与 NapCat 的网络配置 |
| 面板登录 401 | 初始密码早已被改过，且 `password_change_required=true` | 别猜密码；让用户提供或改库 |
| 人设不生效 | 只改了 DB 没改 `persona_id`，或没重启 | 见 6.2 |
| 回复慢/烧 token | 思考模式没关、上下文太长 | `provider[].custom_extra_body.thinking.type=disabled`，`max_context_length` ≤ 40 |
| 群聊上下文为空 | `group_icl_enable=false` | 打开，条数 30 左右 |
| 启动报 `Cannot acquire lock file` | 还有实例占着 `astrbot.lock` | 用 `status.cmd` 找残留进程并 `Stop-Process` |
| `.cmd` 报 `'设' is not recognized` | 文件里有中文且无 BOM | 改成 ASCII（5.1） |
| 日志里有 `UnicodeEncodeError: 'gbk'` | 控制台编码装不下 emoji（✨） | 无害，忽略 |

## 9. 敏感数据与红线

- `data/cmd_config.json` 里有 **DeepSeek API Key 明文**；`data/data_v4.db` 里有群聊记录。**不要外传、不要提交到任何仓库。**
- 这是**非官方 QQ 客户端**（NapCat），有封号风险：只能用小号；不要做自动加群/群发/刷屏。
- 6185 / 6099 / 6199 **绝不要映射到公网**。
- 群聊内容会发给 DeepSeek，新增功能时不要扩大发送范围（比如别把历史全量塞进 prompt）。
- 插件 `sticker_bank` 会把群友图片落盘，加清理机制时注意别误删 `index.json`。

## 10. 改完之后必须做的验证

1. `status.cmd`：6185、6199 都要 `LISTENING`
2. 日志出现 `aiocqhttp(OneBot v11) 适配器已连接`（NapCat 在跑时）
3. 插件加载行：`[sticker_bank] loaded, N stickers in bank`
4. 人设：`scripts\show-persona.cmd` 输出与预期一致
5. 真机冒烟：群里 `@大肥鱼 在吗`，确认回复风格与延迟（正常 1~3 秒）

没有 1、2、5 就不算改完，别只凭「文件改对了」下结论。

## 11. 当前未完成 / 待办

- **主动回复白名单为空**（`provider_ltm_settings.active_reply.whitelist = []`），等于所有群都生效；有群号后应锁死
- `sticker_bank` 的配图是**纯随机**，没有语义匹配（要做需视觉模型打标签 + LLM 选图）
- 表情包库存目前为 0，还没跑过真实流量验证偷图链路
- 没有 git 仓库；建议 `git init` 并加 `.gitignore`（排除 `.venv/`、`data/`、`logs/`、`napcat/`、`*.bak-*`）
- 无开机自启（可把 `start-all.cmd` 的快捷方式放进 `shell:startup`）

## 12. 不要做的事

- 不要 `pip install -U astrbot` 之类的顺手升级（4.29 的字段位置和 4.x 早期版本不一样，升了要重测）
- 不要删除 `data/cmd_config.json.bak-*`（配置被覆盖时的唯一后悔药）
- 不要在服务运行时直接编辑器保存 config（会被覆盖，且可能写坏 BOM）
- 不要把 `logs/` 或 `data/` 加进版本控制
- 不要为了「跑通」把面板 `host` 改回 `0.0.0.0`
