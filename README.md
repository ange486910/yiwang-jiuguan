# 遗忘酒馆 · 不卖酒，只收记忆

一个**带记忆的 AI NPC** 国风文字冒险。你走进一间开在雾里的酒馆，和老板娘阿晚讲自己的往事。她不安慰、不劝说、不评价，只负责把你说的记下来。四轮之后你只能三选一：把这段记忆倒进杯子、自己带走、或者说完就走。

**在线试玩**：https://modelscope.cn/studios/oyj486910/yiwang-jiuguan

---

## 为什么它是「AI 原生」而不是「AI 套壳」

阿晚的每一句台词都是大模型**在运行时生成**的，并且必须按固定 JSON 结构返回：

```json
{"npc_reply": "台词", "trust_change": 2, "secret_change": 3, "new_memory": "一句话记忆"}
```

这三个字段直接写进游戏状态：台词决定你听到什么，增量决定进度条怎么走，记忆摘要进入下一轮的 Prompt。**结局不是剧情树写死的，是由状态阈值算出来的。**

---

## AI NPC 的四条硬指标（对应代码位置）

| 指标 | 本项目怎么做到 | 在哪看 |
|---|---|---|
| 角色状态可量化 | 信任、秘密两条 0–100 进度，每轮由模型输出增量驱动；另存最近 8 条记忆摘要 | `index.html` 状态机 / `app.py` 入参校验 |
| 行为决策可经规则层校验 | 模型给的增量**不能直接生效**：服务端强制把 `trust_change` 夹在 -10~10、`secret_change` 夹在 0~15，越界值截断 | `app.py` 的 clamp 逻辑 |
| 对话与行为闭环 | 对话 → 改状态 → 状态过阈值 → 触发不同结局版本（共 5 个变体：雾散正篇/冷淡版、沉梦、归途正篇/半篇） | `index.html` 的 `ending()` 判定 |
| 可复现、可跑起来 | Docker 一键部署；没有后端也能双击 `index.html` 跑完整流程（前端有兜底引擎） | 见下方「本地跑」 |

> 一句话：**模型负责「说人话」，规则层负责「算账」**。台词可以千变万化，但角色状态和结局永远可复现、可解释。

---

## 玩法与状态

| 状态 | 范围 | 作用 |
|---|---|---|
| 信任 | 0–100 | 决定「先交出」能否走进《雾散》正篇 |
| 秘密 | 0–100 | 与信任共同决定《归途》正篇是否触发 |
| 记忆 | 最近 8 条 | 拼进 Prompt，让她记得你说过什么 |

第 4 轮对话后出现三选一：

- **倒进去** → 信任 ≥ 50 走《雾散》正篇；否则走冷淡版
- **带走** → 《沉梦》
- **说完再走** → 秘密 ≥ 50 且信任 ≥ 50 走《归途》正篇；否则只走一半

进度存在浏览器 `localStorage`，刷新不丢，重开会清档；二次进入时她会用一句“记忆招呼语”接住你。

---

## 人设约束（写进 Prompt 的硬规则）

- 每次不超过 3 句，每句不超过 15 字，短句、留白、不解释
- 绝不评价玩家选择，绝不劝说、安慰、鼓励
- 禁用词：愿你 / 抱抱 / 一定要 / 成长 / 治愈 / 和解
- 被问无关话题，用「这里只谈这个」轻轻拉回
- 永远不承认自己是 AI，不跳出现场

---

## 技术结构

```
index.html          前端：界面、状态机、结局判定、本地兜底对话引擎
app.py              服务端：FastAPI，持有 token 调模型，清洗/校验模型输出
requirements.txt    fastapi / uvicorn / httpx
Dockerfile          python:3.11-slim，监听 7860
ms_deploy.json      魔搭创空间部署配置（sdk_type: docker，port: 7860）
awen.jpg / cover.jpg / ending_*.jpg   美术素材
```

**安全设计**：token 只放在服务端环境变量，网页源码里看不到；`/api/chat` 返回 503/502 时前端自动退回本地引擎，游戏永远能玩到底。

---

## 环境变量

| 变量 | 说明 |
|---|---|
| `MODELSCOPE_TOKEN` | 魔搭访问令牌（在 https://modelscope.cn/my/settings/token 复制） |
| `MODELSCOPE_MODEL` | 模型 ID，本项目用 `Qwen/Qwen3.8-Flash-Next`（2026-11-24 实测可用，单轮 4–8 秒，稳定返回合法 JSON） |

打开 `/api/health` 可验证配置是否生效，返回 `{"ok": true, "model": "..."}`。

---

## 本地跑

```bash
pip install -r requirements.txt
export MODELSCOPE_TOKEN=ms-xxx
export MODELSCOPE_MODEL=Qwen/Qwen3.8-Flash-Next
python app.py          # 默认 7860 端口
```

- 不配环境变量也能跑：`/api/chat` 返回 503，前端自动用本地兜底引擎
- 直接双击 `index.html` 也能完整玩到结局（纯前端模式）

Docker：

```bash
docker build -t yiwang-jiuguan .
docker run -p 7860:7860 -e MODELSCOPE_TOKEN=ms-xxx -e MODELSCOPE_MODEL=Qwen/Qwen3.8-Flash-Next yiwang-jiuguan
```

---

## 踩过的坑（供后来者少走弯路）

1. **气泡不显示**：`@keyframes` 里带了 `opacity:0` 且用 `both`，动画未执行时元素停在透明态。改成只做位移。
2. **模型返回带 ```json 包裹**：服务端先剥代码块，再取首尾花括号；解析失败重试一次，仍失败返回 502 交给前端兜底。
3. **上下文膨胀**：只带最近 8 条记忆摘要，前端上限 12 条，避免 prompt 越滚越大。
4. **魔搭 `.gitignore` 会忽略 `ms_deploy.json`**：平台自动生成的 `.gitignore` 里就写着这个文件名，导致部署配置推不上去，需要 `git add -f`。
5. **模型下线**：`Qwen/Qwen2.5-7B-Instruct` 在魔搭已「无可用提供方」，换模型前先拉 `/v1/models` 确认。

---

## 素材与致谢

- 美术：AI 生成（国风水墨），立绘 + 三张结局插画
- 代码：自写，无第三方 UI 组件
- 平台：魔搭 ModelScope 创空间 / API-Inference
- 模型：Qwen3.8-Flash-Next（阿里通义）

## License

MIT，见 [LICENSE](./LICENSE)。

## 参赛

AI + ∞ 开发者创作大赛 · 第三期「AI 造游戏」参赛作品。
