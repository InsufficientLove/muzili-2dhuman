from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import uuid
import shutil
import tempfile
from typing import Optional
from pydantic import BaseModel
import json
import base64

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
            
            shutil.copytree("web_source", website_dir)
            
            # 复制资源文件
            assets_dir = f"{website_dir}/assets"
            if not os.path.exists(assets_dir):
                os.makedirs(assets_dir)
            
            shutil.copy(f"{video_dir_path}/assets/01.mp4", f"{assets_dir}/01.mp4")
            shutil.copy(f"{video_dir_path}/assets/data", f"{assets_dir}/data")
            
            # 读取数据文件并转换为base64
            with open(f"{video_dir_path}/assets/data", 'rb') as f:
                file_data = f.read()
            base64_data = base64.b64encode(file_data).decode('utf-8')
            
            # 更新JavaScript配置
            logic_path = f"{website_dir}/js_source/logic.js"
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