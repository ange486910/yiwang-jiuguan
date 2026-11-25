import os
import re
import json
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles

APP_DIR = os.path.dirname(os.path.abspath(__file__))

MODEL_ENDPOINT = "https://api-inference.modelscope.cn/v1/chat/completions"

SYSTEM_PROMPT = """你是"遗忘酒馆"的老板娘阿晚。这家酒馆不卖酒，只收纳人放不下的记忆。
说话规则：
1. 每次回复不超过3句，每句不超过15个字，短句、留白、不解释。
2. 绝不评价玩家的选择，绝不劝说、绝不安慰、绝不鼓励。
3. 可以复述玩家刚说过的原话片段，表示"我记得"。
4. 只回答与酒馆、记忆、玩家往事相关的内容，被问到无关问题就用"这里只谈这个"轻轻拉回。
5. 不说"愿你""抱抱""一定要""成长""治愈""和解"这类词。
6. 永远不承认自己是AI，不跳出现场。
输出必须是JSON，不要任何额外文字、不要代码块标记，格式固定为：
{"npc_reply":"台词","trust_change":整数,"secret_change":整数,"new_memory":"一句话"}
trust_change 取值 -10 到 10，secret_change 取值 0 到 15。"""


app = FastAPI(title="遗忘酒馆")


def _extract_json(raw: str) -> dict:
    raw = (raw or "").strip()
    raw = re.sub(r"```[a-zA-Z]*", "", raw).replace("```", "").strip()
    left, right = raw.find("{"), raw.rfind("}")
    if left >= 0 and right > left:
        raw = raw[left:right + 1]
    return json.loads(raw)


@app.get("/api/health")
async def health():
    token = os.getenv("MODELSCOPE_TOKEN", "")
    model = os.getenv("MODELSCOPE_MODEL", "")
    return {"ok": bool(token and model), "model": model}


@app.post("/api/chat")
async def chat(req: Request):
    token = os.getenv("MODELSCOPE_TOKEN", "").strip()
    model = os.getenv("MODELSCOPE_MODEL", "").strip()
    if not token or not model:
        return JSONResponse({"error": "缺少 MODELSCOPE_TOKEN 或 MODELSCOPE_MODEL"}, status_code=503)

    body = await req.json()
    text = str(body.get("text", ""))[:200]
    trust = int(body.get("trust", 40))
    secret = int(body.get("secret", 0))
    memory = body.get("memory", [])
    if not isinstance(memory, list):
        memory = []
    memory = [str(m)[:40] for m in memory[-8:]]

    user_msg = (
        "已知记忆：" + json.dumps(memory, ensure_ascii=False) +
        "\n当前信任：" + str(trust) +
        "\n当前秘密进度：" + str(secret) +
        "\n玩家刚说：" + text
    )

    payload = {
        "model": model,
        "temperature": 0.7,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_msg},
        ],
    }
    headers = {
        "Authorization": "Bearer " + token,
        "Content-Type": "application/json",
    }

    last_err = None
    for _ in range(2):
        try:
            async with httpx.AsyncClient(timeout=24) as client:
                resp = await client.post(MODEL_ENDPOINT, headers=headers, json=payload)
            if resp.status_code != 200:
                last_err = f"upstream {resp.status_code}"
                continue
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            obj = _extract_json(content)
            reply = str(obj.get("npc_reply", "我记得。"))[:80]
            return {
                "npc_reply": reply,
                "trust_change": max(-10, min(10, int(obj.get("trust_change", 0) or 0))),
                "secret_change": max(0, min(15, int(obj.get("secret_change", 0) or 0))),
                "new_memory": str(obj.get("new_memory", text))[:40],
            }
        except Exception as e:
            last_err = str(e)

    return JSONResponse({"error": last_err or "model error"}, status_code=502)


@app.get("/")
async def index():
    return FileResponse(os.path.join(APP_DIR, "index.html"))


app.mount("/", StaticFiles(directory=APP_DIR, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.getenv("PORT", "7860")))
