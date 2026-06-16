"""
商机解析路由
"""
import os
import json
import requests
from flask import Blueprint, jsonify, request
from config import Config

opportunity_bp = Blueprint("opportunity", __name__)


@opportunity_bp.route('/api/opportunity/parse', methods=['POST'])
def parse_opportunity():
    """
    使用 ModelScope DeepSeek-V4-Flash 解析商机自然语言描述
    """
    try:
        data = request.get_json()

        if not data or 'text' not in data:
            return jsonify({
                'success': False,
                'error': '缺少必需参数：text'
            }), 400

        user_text = data.get('text', '').strip()

        if not user_text:
            return jsonify({
                'success': False,
                'error': '输入文本不能为空'
            }), 400

        # 从环境变量读取配置
        modelscope_api_url = os.getenv('MODELSCOPE_API_URL', 'https://api-inference.modelscope.cn/v1/chat/completions')
        modelscope_api_key = os.getenv('MODELSCOPE_API_KEY', '')

        if not modelscope_api_key:
            return jsonify({
                'success': False,
                'error': 'ModelScope API Key 未配置，请在 .env 文件中设置 MODELSCOPE_API_KEY'
            }), 500

        # 构造提示词
        system_prompt = """你是一个商机信息提取助手。请从用户的自然语言描述中提取商机相关信息。

请严格按照以下JSON格式返回，只返回JSON对象，不要包含任何markdown标记或其他文字：

{
  "customerName": "客户名称/公司名称",
  "opportunityName": "商机名称/项目名称",
  "contactPerson": "联系人姓名",
  "contactPhone": "联系电话",
  "contactEmail": "联系邮箱",
  "opportunitySource": "商机来源（从以下选择：市场活动/客户推荐/电话营销/网络推广/展会/其他）",
  "estimatedAmount": 预计金额数字（单位：元，不含逗号），
  "expectedCloseDate": "预计成交时间（YYYY-MM-DD格式）",
  "opportunityStage": "商机阶段（从以下选择：初步接触/需求确认/方案报价/商务谈判/合同签订）",
  "winProbability": "成交概率（从以下选择：10%/30%/50%/70%/90%）",
  "productService": "产品或服务名称",
  "industry": "行业（从以下选择：制造业/金融/互联网/零售/医疗/教育/房地产/其他）",
  "customerRequirement": "客户需求描述",
  "painPoints": "痛点分析",
  "budgetRange": "预算范围（文本描述）",
  "decisionMaker": "决策人信息",
  "competitors": "竞争对手",
  "ourAdvantages": "我方优势",
  "riskAssessment": "风险评估",
  "owner": "负责人",
  "notes": "备注"
}

注意事项：
1. 如果某个字段在描述中没有提到，则不要包含该字段
2. 时间相关描述（如"3个月后"）请计算具体日期
3. 金额单位统一为元
4. 只返回JSON对象，不要包含```json```等标记
"""

        user_prompt = f"请从以下描述中提取商机信息：\n\n{user_text}"

        # 调用 ModelScope API
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {modelscope_api_key}'
        }

        payload = {
            'model': 'deepseek-ai/DeepSeek-V4-Flash',
            'messages': [
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': user_prompt}
            ],
            'temperature': 0.3,
            'max_tokens': 2000
        }

        # 发送请求
        response = requests.post(
            modelscope_api_url,
            headers=headers,
            json=payload,
            timeout=30
        )

        if response.status_code != 200:
            error_msg = f'ModelScope API 调用失败: {response.status_code}'
            try:
                error_data = response.json()
                error_msg += f' - {error_data.get("message", "")}'
            except:
                pass

            return jsonify({
                'success': False,
                'error': error_msg
            }), 500

        result = response.json()

        # 提取AI返回的内容
        ai_response = result['choices'][0]['message']['content']

        # 解析JSON（处理可能的markdown代码块）
        try:
            # 尝试提取JSON
            ai_response = ai_response.strip()

            # 移除可能的markdown代码块标记
            if ai_response.startswith('```json'):
                ai_response = ai_response[7:]
            if ai_response.startswith('```'):
                ai_response = ai_response[3:]
            if ai_response.endswith('```'):
                ai_response = ai_response[:-3]

            ai_response = ai_response.strip()

            # 解析JSON
            parsed_data = json.loads(ai_response)

            return jsonify({
                'success': True,
                'data': parsed_data
            })

        except json.JSONDecodeError as e:
            return jsonify({
                'success': False,
                'error': f'AI返回的JSON格式错误: {str(e)}',
                'raw_response': ai_response
            }), 500

    except requests.Timeout:
        return jsonify({
            'success': False,
            'error': 'API请求超时，请重试'
        }), 504

    except requests.RequestException as e:
        return jsonify({
            'success': False,
            'error': f'网络请求失败: {str(e)}'
        }), 500

    except Exception as e:
        return jsonify({
            'success': False,
            'error': f'服务器内部错误: {str(e)}'
        }), 500
