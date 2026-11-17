from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
from research_agent_v2 import stream_research

app = FastAPI()

# 跨域，前端打开html不会报跨域错误
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 简易内存缓存，生产换成Redis
task_cache = {}

@app.get("/api/research/new")
async def new_research(q: str, fmt: str = "要点清单", filter_ad: bool = True, task_id: str = "task1"):
    def sse_generator():
        for chunk in stream_research(user_query=q, output_format=fmt, filter_ad=filter_ad):
            data = json.loads(chunk)
            if data["type"] == "done":
                task_cache[task_id] = data["full_state"]
            yield f"data: {chunk}\n\n"
    return StreamingResponse(sse_generator(), media_type="text/event-stream")


@app.get("/api/research/append")
async def append_research(task_id: str, msg: str):
    old_state = task_cache.get(task_id)
    if not old_state:
        def err_gen():
            yield f"data: {json.dumps({'type':'error','msg':'任务不存在或已过期'})}\n\n"
        return StreamingResponse(err_gen(), media_type="text/event-stream")

    def sse_generator():
        for chunk in stream_research(
            user_query=old_state["user_query"],
            output_format=old_state["output_format"],
            filter_ad=old_state["filter_ad"],
            append_prompt=msg,
            old_state=old_state
        ):
            data = json.loads(chunk)
            if data["type"] == "done":
                task_cache[task_id] = data["full_state"]
            yield f"data: {chunk}\n\n"
    return StreamingResponse(sse_generator(), media_type="text/event-stream")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
