# deploy/ — 从零重建这套环境

目标是阿里云 ECS（Alibaba Cloud Linux 3 / 任意装了 Docker 26+ 的 x86_64 机器）。
全部步骤都可以在 ECS Workbench 的网页终端里完成。

## 0. 前置：Docker 与镜像源

```bash
docker version && docker compose version   # 需要 compose v2
```

**这台机器直连 Docker Hub 不通**，所以编排里的镜像都带 `m.daocloud.io/docker.io/` 前缀。换机器时先测：

```bash
curl -s -o /dev/null -w '%{http_code}\n' https://m.daocloud.io/v2/   # 期望 401（可达）
```

## 1. 放文件

```bash
mkdir -p /opt/astrbot-napcat/data/{astrbot,qq,napcat/config}
cd /opt/astrbot-napcat
# 把 docker-compose.yml 放到这里；创建 .env：
cat > .env <<'EOF'
NAPCAT_WEBUI_TOKEN=换成随机串
EOF
chmod 600 .env
```

## 2. 起容器

```bash
cd /opt/astrbot-napcat
docker compose up -d
docker compose ps                 # 两个都 Up
sleep 30 && docker logs astrbot 2>&1 | grep -E '适配器已连接|WebUI is ready'
```

首次启动时 AstrBot 会生成一份随机面板密码，打印在日志里（`Initial password: ...`），照着登录即可；
想固定成自己的密码，见下面第 4 步。

## 3. 扫码登录 QQ

```bash
docker logs -f napcat | tail -20
```

日志里会出现二维码的保存路径和 `https://txz.qq.com/p?k=...` 解码链接；
也可以直接开 NapCat 面板 `http://<IP>:6099/webui?token=<NAPCAT_WEBUI_TOKEN>` 扫码。

登录态落在 `data/qq/`，**别删**。

## 4. （可选）写死面板密码

停服务后把 pbkdf2 哈希写进配置，再起服务：

```bash
docker compose stop astrbot
python3 - <<'PY'
import hashlib, json, secrets
pw = '你的新密码'          # 至少 8 位，含大小写和数字
p = 'data/astrbot/cmd_config.json'
raw = open(p, 'rb').read(); bom = raw.startswith(b'\xef\xbb\xbf')
c = json.loads(raw.decode('utf-8-sig'))
salt = secrets.token_hex(16)
dig = hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), 600000).hex()
d = c['dashboard']
d['username'] = 'astrbot'
d['password'] = hashlib.md5(pw.encode()).hexdigest()
d['pbkdf2_password'] = 'pbkdf2_sha256$600000$%s$%s' % (salt, dig)
d['password_storage_upgraded'] = True
d['password_change_required'] = False
d['host'] = '0.0.0.0'; d['port'] = 6185
open(p, 'w', encoding='utf-8-sig' if bom else 'utf-8', newline='\n').write(
    json.dumps(c, ensure_ascii=False, indent=2) + '\n')
print('ok')
PY
docker compose start astrbot
```

## 5. 装插件

三个文件直接从本仓库拷到服务器，重启生效：

```bash
cp -r deploy/plugin_nick_wake      /opt/astrbot-napcat/data/astrbot/plugins/
cp -r deploy/plugin_group_imprint  /opt/astrbot-napcat/data/astrbot/plugins/
docker compose restart astrbot
docker logs --since 2m astrbot | grep -E 'Plugin nick_wake|Plugin group_imprint'
```

## 6. 配模型

面板 →「服务提供商」→ 用 DeepSeek 的源，建三个 provider：

| id | 模型 | `custom_extra_body` |
|---|---|---|
| `deepseek/deepseek-flash` | deepseek-flash | `{}` |
| `deepseek/deepseek-flash-high` | deepseek-flash | `{"reasoning_effort": "high"}` |
| `deepseek/deepseek-v4-pro` | deepseek-v4-pro | `{}` |

然后把 `agent_runner.config.model.provider_id` 设成要用的那个。

## 7. 检查清单

```bash
docker compose ps
docker logs astrbot 2>&1 | grep '适配器已连接'
curl -s -o /dev/null -w '%{http_code}\n' http://127.0.0.1:6185/   # 200
```

- [ ] 两个容器 Up
- [ ] 日志有 `aiocqhttp(OneBot v11) 适配器已连接。`
- [ ] 面板能登录
- [ ] 群里 @ 它有回复
- [ ] 安全组只放行 6185 / 6099，且来源限自家 IP

## 备注

- 内存 1.8 GB 偏紧，建议加 swap（`fallocate -l 2G /swapfile && mkswap /swapfile && swapon /swapfile`）。
- NapCat 容器里跑的是 Linux QQ + Xvfb，首次启动要几十秒才出二维码。
- `data/napcat/config/onebot11.json` 由 `MODE=astrbot` 模板自动生成，指向 `ws://astrbot:6199/ws`；不要手动改成公网地址。
