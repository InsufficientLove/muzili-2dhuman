from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Request  # 20250825_update: 新增 Request 用于通用性
from fastapi.responses import JSONResponse, FileResponse, StreamingResponse  # 20250825_update: 新增 StreamingResponse 用于SSE
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import shutil
import tempfile
import subprocess  # 20250825_update: 用于调用 ffmpeg 与 node 构建脚本
from typing import Optional
from pydantic import BaseModel
import json
import base64
import requests  # 20250825_update: 外呼 Ollama/Dify 等 LLM 服务

# 导入现有模块
from data_preparation_mini import data_preparation_mini
from data_preparation_web import data_preparation_web
from demo_mini import interface_mini

app = FastAPI(title="数字人训练API", version="1.0.0")

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DigitalHumanConfig(BaseModel):
    """数字人配置模型"""
    name: str = "小卿"
    personality: str = "温柔、体贴、善解人意"
    voice_type: str = "女性 - 温柔女声"
    enable_vision: bool = True
    system_prompt: Optional[str] = None

class TrainingResponse(BaseModel):
    """训练响应模型"""
    success: bool
    message: str
    digital_human_id: Optional[str] = None
    web_url: Optional[str] = None
    assets_info: Optional[dict] = None

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    provider: str  # ollama | dify
    model: Optional[str] = None
    messages: list[ChatMessage]
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = True
    provider_config: Optional[dict] = None  # 自定义端点/参数
    # 20250825_update: 新增统一 LLM 入参模型（支持多 provider）


# 环境变量配置（可在部署时覆盖）
OLLAMA_API_URL = os.getenv("OLLAMA_API_URL", "http://127.0.0.1:11434")  # 20250825_update: 新增默认 Ollama 地址
DIFY_API_URL = os.getenv("DIFY_API_URL", "https://api.dify.ai/v1")      # 20250825_update: 新增默认 Dify 地址
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")                              # 20250825_update: 新增 Dify API Key


def compress_webm(input_path: str, output_path: str, width: int = 480, crf: int = 40, bitrate: str = "500k") -> None:
    # 20250825_update: 新增 - 生成移动端自动播放用的示例 webm
    """使用ffmpeg压缩生成webm示例视频（用于移动端自动播放封面）。"""
    cmd = [
        "ffmpeg",
        "-i", input_path,
        "-vf", f"scale={width}:-2:flags=lanczos,split[s0][s1];[s0]reverse[r];[s1][r]concat",
        "-c:v", "libvpx-vp9",
        "-crf", str(crf),
        "-b:v", bitrate,
        "-row-mt", "1",
        "-quality", "good",
        "-cpu-used", "4",
        "-an", "-loop", "0",
        "-y", output_path
    ]
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        # 不中断主流程，仅记录
        print(f"ffmpeg 生成示例视频失败: {e.stderr.decode(errors='ignore')}")

@app.get("/")
async def root():
    """API根路径"""
    return {"message": "数字人训练API服务", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "service": "digital-human-api"}

@app.post("/train", response_model=TrainingResponse)
async def train_digital_human(
    video: UploadFile = File(..., description="训练视频文件"),
    config: str = Form(..., description="数字人配置JSON字符串")
):
    """
    训练数字人模型
    
    Args:
        video: 上传的训练视频文件
        config: 数字人配置信息
    
    Returns:
        训练结果和数字人ID
    """
    try:
        # 解析配置
        config_data = json.loads(config)
        digital_config = DigitalHumanConfig(**config_data)
        
        # 生成唯一ID
        digital_human_id = str(uuid.uuid4())
        
        # 创建临时目录保存上传的视频
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_video:
            content = await video.read()
            temp_video.write(content)
            temp_video_path = temp_video.name
        
        try:
            # 执行数据预处理
            video_dir_path = f"video_data/{digital_human_id}"
            video_dir_path = os.path.join(os.path.dirname(__file__), video_dir_path)
            
            # 调用现有的预处理函数
            data_preparation_mini(temp_video_path, video_dir_path, False)
            data_preparation_web(video_dir_path)
            
            # 创建Web资源
            website_dir = f"website/{digital_human_id}"
            website_dir = os.path.join(os.path.dirname(__file__), website_dir)
            
            if os.path.exists(website_dir):
                shutil.rmtree(website_dir)
            
            src_web_dir = os.path.join(os.path.dirname(__file__), "web_source")  # 20250825_update: 使用绝对路径更稳健
            shutil.copytree(src_web_dir, website_dir)  # 20250825_update
            
            # 复制资源文件
            assets_dir = f"{website_dir}/assets"
            if not os.path.exists(assets_dir):
                os.makedirs(assets_dir)
            
            shutil.copy(f"{video_dir_path}/assets/01.mp4", f"{assets_dir}/01.mp4")
            shutil.copy(f"{video_dir_path}/assets/data", f"{assets_dir}/data")

            # 生成移动端预览示例视频，非关键步骤失败可忽略
            try:
                compress_webm(temp_video_path, f"{assets_dir}/example.webm", width=360, crf=45, bitrate="300k")  # 20250825_update
            except Exception as _:
                pass  # 20250825_update: 非关键失败忽略
            
            # 读取数据文件并转换为base64
            with open(f"{video_dir_path}/assets/data", 'rb') as f:
                file_data = f.read()
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            # 更新JavaScript配置（先更新 js_source，再构建 jsCode15）
            logic_path = f"{website_dir}/js_source/logic.js"  # 20250825_update: 训练后将数据二进制替换进 js
            with open(logic_path, 'r', encoding='utf-8') as f:
                js_content = f.read()
            updated_js = js_content.replace("数据文件需要替换的地方", base64_data)
            with open(logic_path, 'w', encoding='utf-8') as f:
                f.write(updated_js)
            
            # 更新人物配置
            human_logic_path = f"{website_dir}/js_source/humanLogic.js"
            with open(human_logic_path, 'r', encoding='utf-8') as f:
                human_logic_content = f.read()
            
            # 替换配置信息
            system_prompt = digital_config.system_prompt or generate_default_prompt(digital_config)
            human_logic_content = human_logic_content.replace("大模型身份信息覆盖", system_prompt)
            human_logic_content = human_logic_content.replace("声音id信息覆盖", get_voice_filename(digital_config.voice_type))
            human_logic_content = human_logic_content.replace("是否开启视觉", str(digital_config.enable_vision).lower())
            
            with open(human_logic_path, 'w', encoding='utf-8') as f:
                f.write(human_logic_content)
            
            # 构建混淆版脚本，确保 index.html 引用的 jsCode15 可用
            test_js_path = os.path.join(website_dir, "test.js")  # 20250825_update: 构建混淆版 jsCode15
            js_code15_dir = os.path.join(website_dir, "jsCode15")  # 20250825_update
            js_source_dir = os.path.join(website_dir, "js_source")  # 20250825_update
            if os.path.exists(test_js_path):
                try:
                    subprocess.run(["node", test_js_path], check=True)  # 20250825_update
                except Exception as e:
                    print(f"构建 jsCode15 失败: {e}")  # 20250825_update
            
            # 如果 jsCode15 仍缺少关键文件，退化为直接复制 js_source
            required_js = [
                "humanLogic.js", "zip.js", "v.js", "opengl.js",
                "logic.js", "loadMode1.js", "loadMode2.js", "load.js"
            ]
            try:
                os.makedirs(js_code15_dir, exist_ok=True)  # 20250825_update
                for fname in required_js:
                    src = os.path.join(js_source_dir, fname)
                    dst = os.path.join(js_code15_dir, fname)
                    if os.path.exists(src) and not os.path.exists(dst):
                        shutil.copy(src, dst)  # 20250825_update: 回退复制，保障前端引用可用
            except Exception as e:
                print(f"复制 js_source 到 jsCode15 失败: {e}")  # 20250825_update

            # 清理临时文件
            shutil.rmtree(video_dir_path)
            
            return TrainingResponse(
                success=True,
                message="数字人训练完成",
                digital_human_id=digital_human_id,
                web_url=f"/digital-human/{digital_human_id}",
                assets_info={
                    "video_size": len(content),
                    "config": config_data
                }
            )
            
        finally:
            # 清理临时视频文件
            if os.path.exists(temp_video_path):
                os.remove(temp_video_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"训练失败: {str(e)}")

@app.get("/digital-human/{digital_human_id}")
async def get_digital_human_page(digital_human_id: str):
    """获取数字人网页"""
    website_dir = f"website/{digital_human_id}"
    index_path = os.path.join(os.path.dirname(__file__), website_dir, "index.html")
    
    if not os.path.exists(index_path):
        raise HTTPException(status_code=404, detail="数字人不存在")
    
    return FileResponse(index_path, media_type="text/html")

@app.get("/digital-human/{digital_human_id}/assets/{asset_path:path}")
async def get_digital_human_assets(digital_human_id: str, asset_path: str):
    """获取数字人资源文件"""
    asset_full_path = os.path.join(os.path.dirname(__file__), f"website/{digital_human_id}", asset_path)
    
    if not os.path.exists(asset_full_path):
        raise HTTPException(status_code=404, detail="资源文件不存在")
    
    return FileResponse(asset_full_path)

@app.post("/inference")
async def inference_digital_human(
    digital_human_id: str = Form(...),
    audio_file: UploadFile = File(..., description="音频文件")
):
    """
    数字人推理接口
    
    Args:
        digital_human_id: 数字人ID
        audio_file: 音频文件
    
    Returns:
        生成的视频文件
    """
    try:
        # 检查数字人是否存在
        assets_dir = f"website/{digital_human_id}/assets"
        if not os.path.exists(assets_dir):
            raise HTTPException(status_code=404, detail="数字人不存在")
        
        # 保存上传的音频文件
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_audio:
            audio_content = await audio_file.read()
            temp_audio.write(audio_content)
            temp_audio_path = temp_audio.name
        
        # 生成输出视频路径
        output_video_path = f"temp/output_{uuid.uuid4()}.mp4"
        
        try:
            # 调用推理函数
            interface_mini(assets_dir, temp_audio_path, output_video_path)
            
            return FileResponse(
                output_video_path, 
                media_type="video/mp4",
                filename=f"digital_human_{digital_human_id}.mp4"
            )
            
        finally:
            # 清理临时音频文件
            if os.path.exists(temp_audio_path):
                os.remove(temp_audio_path)
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"推理失败: {str(e)}")

@app.get("/list")
async def list_digital_humans():
    """获取所有数字人列表"""
    website_dir = "website"
    digital_humans = []
    
    if os.path.exists(website_dir):
        for item in os.listdir(website_dir):
            if os.path.isdir(os.path.join(website_dir, item)):
                digital_humans.append({
                    "id": item,
                    "url": f"/digital-human/{item}",
                    "created_at": os.path.getctime(os.path.join(website_dir, item))
                })
    
    return {"digital_humans": digital_humans}


@app.get("/templates")
async def list_templates():
    """模板/形象列表（同 /list 的别名）。"""
    return await list_digital_humans()
    # 20250825_update: 新增别名接口，便于前端语义调用


@app.get("/llm/providers")
async def llm_providers():
    """返回可用的大模型提供方及配置可用性。"""
    providers = []
    providers.append({
        "name": "ollama",
        "base_url": OLLAMA_API_URL,
        "available": True
    })
    providers.append({
        "name": "dify",
        "base_url": DIFY_API_URL,
        "available": bool(DIFY_API_KEY)
    })
    return {"providers": providers}
    # 20250825_update: 新增 - 查询可用 LLM 提供方


def _stream_ollama(chat: ChatRequest):  # 20250825_update: 新增 - Ollama SSE 代理
    base_url = (chat.provider_config or {}).get("base_url", OLLAMA_API_URL).rstrip("/")
    url = f"{base_url}/api/chat"
    payload = {
        "model": chat.model or "qwen2.5:7b",
        "messages": [m.model_dump() for m in chat.messages],
        "stream": True,
        "options": {"temperature": chat.temperature or 0.7}
    }
    with requests.post(url, json=payload, stream=True) as r:
        r.raise_for_status()
        for line in r.iter_lines(decode_unicode=True):
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if obj.get("done"):
                yield "event: done\n".encode()
                yield b"data: {\"type\":\"done\"}\n\n"
                break
            delta = obj.get("message", {}).get("content") or obj.get("response") or ""
            if delta:
                data = json.dumps({"type": "delta", "content": delta}, ensure_ascii=False)
                yield f"data: {data}\n\n".encode()


def _stream_dify(chat: ChatRequest):  # 20250825_update: 新增 - Dify SSE 代理
    base_url = (chat.provider_config or {}).get("base_url", DIFY_API_URL).rstrip("/")
    api_key = (chat.provider_config or {}).get("api_key", DIFY_API_KEY)
    if not api_key:
        # 立即结束（避免非ASCII字节字面量，使用UTF-8编码）  # 20250825_update
        err_json = json.dumps({"type": "error", "message": "DIFY_API_KEY 未配置"}, ensure_ascii=False)
        yield f"data: {err_json}\n\n".encode("utf-8")
        yield b"event: done\n\n"
        return

    url = f"{base_url}/chat-messages"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    # Dify 需要一个单条输入，使用 messages 合并为字符串
    user_content = "\n".join([m.content for m in chat.messages if m.role == "user"]) or chat.messages[-1].content
    payload = {
        "inputs": {},
        "query": user_content,
        "response_mode": "streaming",
        "conversation_id": None,
        "user": "web"
    }
    with requests.post(url, headers=headers, json=payload, stream=True) as r:
        r.raise_for_status()
        for raw in r.iter_lines(decode_unicode=True):
            if not raw:
                continue
            # SSE 形如: event: message / data: {...}
            if raw.startswith("data:"):
                try:
                    data_json = json.loads(raw[5:].strip())
                except Exception:
                    continue
                # dify 流字段: answer 聚合增量
                delta = data_json.get("answer")
                if delta:
                    data = json.dumps({"type": "delta", "content": delta}, ensure_ascii=False)
                    yield f"data: {data}\n\n".encode()
            elif raw.startswith("event:") and "end" in raw:
                yield b"event: done\n\n"
                yield b"data: {\"type\":\"done\"}\n\n"
                break


@app.post("/llm/stream")
def llm_stream(chat: ChatRequest):  # 20250825_update: 新增 - 统一 LLM 流式接口 (SSE)
    """统一的大模型SSE流接口。

    返回格式为 text/event-stream，其中 data 字段的 JSON 为:
    { "type": "delta" | "done" | "error", "content": "..." }
    """
    provider = (chat.provider or '').lower()

    if provider == "ollama":
        generator = _stream_ollama(chat)
    elif provider == "dify":
        generator = _stream_dify(chat)
    else:
        def _err():  # 20250825_update: 同上，避免非ASCII字节字面量
            err_json = json.dumps({"type": "error", "message": "不支持的provider"}, ensure_ascii=False)
            yield f"data: {err_json}\n\n".encode("utf-8")
            yield b"event: done\n\n"
        generator = _err()

    return StreamingResponse(generator, media_type="text/event-stream")

def generate_default_prompt(config: DigitalHumanConfig) -> str:
    """生成默认的系统提示词"""
    return f"""基本信息：
名字：{config.name}
性格：{config.personality}

对话风格：
根据设定的性格特点进行对话，保持一致的人设。
回复字数限制在50字以内。"""

def get_voice_filename(voice_type: str) -> str:
    """根据声音类型获取文件名"""
    # 这里需要根据实际的音频文件映射关系来实现
    voice_mapping = {
        "女性 - 温柔女声": "3",
        "女性 - 台湾女友": "6",
        "男性 - 主持男生": "2",
        # 添加更多映射...
    }
    return voice_mapping.get(voice_type, "3")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 