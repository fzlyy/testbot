# NapCat + AstrBot 的 DeepSeek「AI 群友」

一个 QQ 小号通过 **NapCat**（OneBot v11 协议端）接到 **AstrBot**，由 DeepSeek 生成回复，人设是一只傲娇的胖鲸鱼。

**现在只跑在阿里云 ECS 上**（Docker Compose，两个容器）。本机 Windows 那套已经删掉了，不要再照着旧的本地部署步骤做。

```
QQ 小号 ──扫码──> NapCat ──反向 WS──> AstrBot ──HTTPS──> api.deepseek.com
```

## 快速索引

| 想干什么 | 看哪 |
|---|---|
| 了解服务器、端口、目录、改配置的规矩 | [AGENTS.md](AGENTS.md) |
| 从零重建这套环境 | [deploy/README.md](deploy/README.md) |
| 看某个版本的人设草稿 | `persona-jingyuni.md`（现用）、`persona-dafeiyu.md`、`persona-ai-groupmate.md` |
| 拿插件源码 | `deploy/plugin_nick_wake/`、`deploy/plugin_group_imprint/` |

## 面板入口

- AstrBot：`http://8.147.107.136:6185`
- NapCat：`http://8.147.107.136:6099/webui`

账号、令牌、端口都在服务器 `/opt/astrbot-napcat/CREDENTIALS.txt`（权限 600）。**仓库里不放任何密钥。**

## 仓库里有什么

```
AGENTS.md                 服务器运维与配置的权威说明
README.md                 本文件
persona-*.md              人设草稿与调参记录（线上以数据库为准）
deploy/
  docker-compose.yml      两个容器的编排
  .env.example            NAPCAT_WEBUI_TOKEN 模板
  remote.py               paramiko 的 SSH 助手（凭据走环境变量）
  plugin_nick_wake/       「什么时候该说话」判定插件
  plugin_group_imprint/   「群友印象」长期记忆插件
```

## 红线

- 6199（反向 WS）永远不要映射到公网
- 不要提交 API Key / 面板密码 / WebUI token / QQ 登录态
- 非官方客户端，有封号风险：只用小号，别刷屏
