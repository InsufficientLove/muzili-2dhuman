"""
数字人训练API集成示例
演示如何在你的应用中集成数字人训练功能
"""

import requests
import json
import time
from typing import Optional

class DigitalHumanClient:
    """数字人训练客户端"""
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url.rstrip('/')
        self.session = requests.Session()
    
    def health_check(self) -> bool:
        """健康检查"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            return response.status_code == 200
        except:
            return False
    
    def train_digital_human(
        self, 
        video_path: str, 
        name: str = "小卿",
        personality: str = "温柔、体贴、善解人意",
        voice_type: str = "女性 - 温柔女声",
        enable_vision: bool = True,
        system_prompt: Optional[str] = None
    ) -> dict:
        """
        训练数字人
        
        Args:
            video_path: 训练视频文件路径
            name: 数字人名称
            personality: 性格描述
            voice_type: 声音类型
            enable_vision: 是否启用视觉功能
            system_prompt: 自定义系统提示词
            
        Returns:
            训练结果
        """
        # 准备配置数据
        config = {
            "name": name,
            "personality": personality,
            "voice_type": voice_type,
            "enable_vision": enable_vision
        }
        
        if system_prompt:
            config["system_prompt"] = system_prompt
        
        # 准备文件和数据
        files = {
            'video': open(video_path, 'rb')
        }
        
        data = {
            'config': json.dumps(config)
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/train",
                files=files,
                data=data,
                timeout=300  # 5分钟超时
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                raise Exception(f"训练失败: {response.text}")
                
        finally:
            files['video'].close()
    
    def get_digital_human_list(self) -> list:
        """获取数字人列表"""
        response = self.session.get(f"{self.base_url}/list")
        if response.status_code == 200:
            return response.json()["digital_humans"]
        else:
            raise Exception(f"获取列表失败: {response.text}")
    
    def inference_digital_human(
        self, 
        digital_human_id: str, 
        audio_path: str, 
        output_path: str
    ) -> bool:
        """
        数字人推理
        
        Args:
            digital_human_id: 数字人ID
            audio_path: 音频文件路径
            output_path: 输出视频保存路径
            
        Returns:
            是否成功
        """
        files = {
            'audio_file': open(audio_path, 'rb')
        }
        
        data = {
            'digital_human_id': digital_human_id
        }
        
        try:
            response = self.session.post(
                f"{self.base_url}/inference",
                files=files,
                data=data,
                timeout=120
            )
            
            if response.status_code == 200:
                with open(output_path, 'wb') as f:
                    f.write(response.content)
                return True
            else:
                raise Exception(f"推理失败: {response.text}")
                
        finally:
            files['audio_file'].close()
    
    def get_digital_human_url(self, digital_human_id: str) -> str:
        """获取数字人网页URL"""
        return f"{self.base_url}/digital-human/{digital_human_id}"


def example_basic_usage():
    """基础使用示例"""
    print("=== 基础使用示例 ===")
    
    # 创建客户端
    client = DigitalHumanClient("http://localhost:8000")
    
    # 健康检查
    if not client.health_check():
        print("❌ 服务不可用，请检查服务是否启动")
        return
    
    print("✅ 服务连接正常")
    
    # 训练数字人
    print("📹 开始训练数字人...")
    try:
        result = client.train_digital_human(
            video_path="examples/example1.mp4",
            name="小美",
            personality="活泼开朗，喜欢聊天",
            voice_type="女性 - 台湾女友",
            enable_vision=True
        )
        
        print(f"✅ 训练成功！")
        print(f"   数字人ID: {result['digital_human_id']}")
        print(f"   访问链接: {result['web_url']}")
        
        digital_human_id = result['digital_human_id']
        
    except Exception as e:
        print(f"❌ 训练失败: {e}")
        return
    
    # 获取数字人列表
    print("\n📋 获取数字人列表...")
    try:
        humans = client.get_digital_human_list()
        print(f"   共有 {len(humans)} 个数字人")
        for human in humans:
            print(f"   - ID: {human['id']}")
            print(f"     URL: {human['url']}")
    except Exception as e:
        print(f"❌ 获取列表失败: {e}")
    
    # 推理测试
    print(f"\n🎤 测试推理功能...")
    try:
        success = client.inference_digital_human(
            digital_human_id=digital_human_id,
            audio_path="temp/test_audio.wav",
            output_path="temp/output_video.mp4"
        )
        
        if success:
            print("✅ 推理成功，视频已保存到 temp/output_video.mp4")
        else:
            print("❌ 推理失败")
            
    except Exception as e:
        print(f"❌ 推理失败: {e}")


def example_web_integration():
    """Web应用集成示例"""
    print("\n=== Web应用集成示例 ===")
    
    # Flask应用集成示例
    flask_example = '''
from flask import Flask, request, jsonify, render_template
from integration_examples import DigitalHumanClient

app = Flask(__name__)
client = DigitalHumanClient("http://localhost:8000")

@app.route('/')
def index():
    return render_template('upload.html')

@app.route('/upload', methods=['POST'])
def upload_video():
    if 'video' not in request.files:
        return jsonify({'error': '没有上传视频'}), 400
    
    file = request.files['video']
    if file.filename == '':
        return jsonify({'error': '没有选择文件'}), 400
    
    # 保存上传的文件
    video_path = f"temp/{file.filename}"
    file.save(video_path)
    
    try:
        # 训练数字人
        result = client.train_digital_human(
            video_path=video_path,
            name=request.form.get('name', '小卿'),
            personality=request.form.get('personality', '温柔可爱'),
            voice_type=request.form.get('voice_type', '女性 - 温柔女声')
        )
        
        return jsonify({
            'success': True,
            'digital_human_id': result['digital_human_id'],
            'web_url': result['web_url']
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
    '''
    
    print("Flask集成示例代码:")
    print(flask_example)


def example_batch_training():
    """批量训练示例"""
    print("\n=== 批量训练示例 ===")
    
    client = DigitalHumanClient("http://localhost:8000")
    
    # 批量训练配置
    training_configs = [
        {
            "video_path": "examples/example1.mp4",
            "name": "小美",
            "personality": "活泼开朗",
            "voice_type": "女性 - 甜美女声"
        },
        {
            "video_path": "examples/example2.mp4", 
            "name": "小帅",
            "personality": "阳光帅气",
            "voice_type": "男性 - 阳光青年"
        },
        {
            "video_path": "examples/example3.mp4",
            "name": "小雅",
            "personality": "知性优雅", 
            "voice_type": "女性 - 知性女声"
        }
    ]
    
    results = []
    
    for i, config in enumerate(training_configs, 1):
        print(f"📹 训练第 {i}/{len(training_configs)} 个数字人: {config['name']}")
        
        try:
            result = client.train_digital_human(**config)
            results.append(result)
            print(f"   ✅ 训练成功: {result['digital_human_id']}")
            
            # 避免服务器过载，训练间隔
            time.sleep(2)
            
        except Exception as e:
            print(f"   ❌ 训练失败: {e}")
            results.append(None)
    
    print(f"\n📊 批量训练完成:")
    print(f"   成功: {len([r for r in results if r])} 个")
    print(f"   失败: {len([r for r in results if not r])} 个")
    
    return results


def example_custom_prompt():
    """自定义提示词示例"""
    print("\n=== 自定义提示词示例 ===")
    
    client = DigitalHumanClient("http://localhost:8000")
    
    # 自定义系统提示词
    custom_prompt = """
基本信息：
名字：小智
职业：AI助手
专长：编程、技术咨询、问题解决

性格特点：
- 专业严谨，逻辑清晰
- 耐心细致，善于解释复杂概念  
- 积极主动，乐于帮助他人

对话风格：
- 使用专业术语但保持通俗易懂
- 提供具体的解决方案和代码示例
- 回复简洁明了，重点突出
- 字数控制在80字以内

特殊技能：
- 代码审查和优化建议
- 技术架构设计咨询
- 调试问题分析
    """
    
    try:
        result = client.train_digital_human(
            video_path="examples/example1.mp4",
            name="小智",
            personality="专业的技术助手",
            voice_type="男性 - 儒雅青年",
            enable_vision=True,
            system_prompt=custom_prompt
        )
        
        print("✅ 自定义数字人训练成功！")
        print(f"   数字人ID: {result['digital_human_id']}")
        print(f"   访问链接: {result['web_url']}")
        
    except Exception as e:
        print(f"❌ 训练失败: {e}")


if __name__ == "__main__":
    print("🤖 数字人训练API集成示例")
    print("=" * 50)
    
    # 运行示例
    example_basic_usage()
    example_web_integration() 
    example_batch_training()
    example_custom_prompt()
    
    print("\n✨ 所有示例运行完成！") 