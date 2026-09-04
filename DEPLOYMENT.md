# 部署信息

- 部署日期：2026-09-04
- 服务器：`ChengLanServer`（`47.121.189.62`）
- 访问地址：`https://ai-detective.chenglan.tech`
- 当前版本：`V2`，部署提交以 `git -C /home/projects/AI-Detective-Game/current rev-parse HEAD` 为准
- 当前发布：以服务器 `current` 链接和本文记录的 Git 提交为准
- 稳定入口：`/home/projects/AI-Detective-Game/current`
- 持久数据：`/home/projects/AI-Detective-Game/shared/data`
- 运行方式：Nginx 托管前端，后端由 `ai-detective-api.service` 运行在 `127.0.0.1:8040`

## 当前能力

后端 11 项测试、前端检查、生产构建和端到端创建案件流程均已通过。服务器已配置 Kimi K3，并于 2026-09-04 通过真实案件生成验证；模型不可用时仍会使用内置回退内容。

Kimi 配置保存在权限为 `600` 的 `/home/projects/AI-Detective-Game/shared/.env`。如需更换密钥：

```dotenv
KIMI_ENABLED=true
KIMI_API_KEY=<your-key>
```

随后执行：

```bash
systemctl restart ai-detective-api
```

## 运维命令

```bash
systemctl status ai-detective-api
journalctl -u ai-detective-api -n 100 --no-pager
nginx -t
curl http://127.0.0.1:8040/api/health
```

HTTPS 已启用，HTTP 会自动跳转至 HTTPS。证书到期日为 2026-12-03，由 `certbot.timer` 自动续期；续期演练已通过。

```bash
systemctl status certbot.timer
certbot renew --dry-run
```
