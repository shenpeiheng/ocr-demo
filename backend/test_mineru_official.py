"""
测试 MinerU 官方 API 集成

测试流程：
1. 文件上传服务测试
2. MinerU 官方 API 调用测试
3. 端到端集成测试
"""

import os
import sys
import logging

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_file_upload_service():
    """测试文件上传服务"""
    logger.info("=" * 60)
    logger.info("测试 1: 文件上传服务")
    logger.info("=" * 60)

    from file_upload_service import create_file_upload_service
    import time

    # 创建测试文件
    test_file = "test_upload.txt"
    with open(test_file, "w", encoding="utf-8") as f:
        f.write("这是一个测试文件，用于测试文件上传服务。\n")
        f.write(f"创建时间: {time.time()}\n")

    try:
        upload_service = create_file_upload_service("transfer.sh")
        logger.info(f"上传测试文件: {test_file}")

        result = upload_service.upload_file(test_file)

        if result.get("success"):
            logger.info(f"✓ 上传成功")
            logger.info(f"  URL: {result['url']}")
            logger.info(f"  服务: {result['service']}")
            logger.info(f"  有效期: {result['expires_in'] // 3600} 小时")
            return True
        else:
            logger.error(f"✗ 上传失败: {result.get('error')}")
            return False

    finally:
        # 清理测试文件
        if os.path.exists(test_file):
            os.remove(test_file)
            logger.info(f"清理测试文件: {test_file}")


def test_mineru_official_api():
    """测试 MinerU 官方 API"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 2: MinerU 官方 API")
    logger.info("=" * 60)

    from mineru_official_api import create_mineru_official_client
    from config import Config

    if not Config.MINERU_OFFICIAL_TOKEN:
        logger.error("✗ 未配置 MINERU_OFFICIAL_TOKEN")
        return False

    try:
        client = create_mineru_official_client(Config.MINERU_OFFICIAL_TOKEN)
        logger.info("✓ MinerU 客户端创建成功")

        # 使用一个公开的测试 PDF URL
        test_url = "https://www.w3.org/WAI/ER/tests/xhtml/testfiles/resources/pdf/dummy.pdf"
        logger.info(f"测试 PDF URL: {test_url}")

        result = client.parse_pdf_url(
            file_url=test_url,
            model_version="vlm",
            enable_formula=True,
            enable_table=True,
            is_ocr=True,
            language="en",
            max_wait_time=120
        )

        if result.get("success"):
            logger.info(f"✓ API 调用成功")
            logger.info(f"  任务ID: {result.get('task_id')}")
            logger.info(f"  状态: {result.get('state')}")
            if result.get("markdown_url"):
                logger.info(f"  Markdown URL: {result['markdown_url']}")
            return True
        else:
            logger.error(f"✗ API 调用失败: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"✗ 测试异常: {str(e)}")
        return False


def test_mineru_processor_official():
    """测试 MinerU 处理器（官方 API 模式）"""
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试 3: MinerU 处理器集成测试")
    logger.info("=" * 60)

    from mineru_processor import create_mineru_processor
    from config import Config

    if not Config.MINERU_OFFICIAL_TOKEN:
        logger.error("✗ 未配置 MINERU_OFFICIAL_TOKEN")
        return False

    # 查找测试 PDF 文件
    test_pdf = None
    possible_paths = [
        "../frontend/uploads",
        "uploads",
        "../frontend/static/images/demo"
    ]

    for base_path in possible_paths:
        if os.path.exists(base_path):
            for filename in os.listdir(base_path):
                if filename.lower().endswith('.pdf'):
                    test_pdf = os.path.join(base_path, filename)
                    break
        if test_pdf:
            break

    if not test_pdf or not os.path.exists(test_pdf):
        logger.warning("✗ 未找到测试 PDF 文件，跳过集成测试")
        logger.info("  提示：将 PDF 文件放在 ../frontend/uploads 目录下")
        return None

    try:
        logger.info(f"使用测试 PDF: {test_pdf}")
        logger.info(f"文件大小: {os.path.getsize(test_pdf)} bytes")

        processor = create_mineru_processor(
            request_mode="mineru_official",
            official_token=Config.MINERU_OFFICIAL_TOKEN,
            timeout=300
        )

        if not processor.initialized:
            logger.error("✗ 处理器未初始化")
            return False

        logger.info("✓ 处理器初始化成功")
        logger.info("开始处理 PDF（这可能需要几分钟）...")

        result = processor.process_pdf(
            pdf_path=test_pdf,
            max_pages=2
        )

        if result.get("success"):
            logger.info(f"✓ PDF 处理成功")
            combined = result.get("combined_results", {})
            logger.info(f"  总页数: {combined.get('total_pages')}")
            logger.info(f"  文本项数: {combined.get('total_items')}")
            logger.info(f"  处理时间: {combined.get('total_processing_time')} 秒")

            markdown = combined.get("markdown", "")
            if markdown:
                logger.info(f"  Markdown 长度: {len(markdown)} 字符")
                logger.info(f"  前200字符预览:\n{markdown[:200]}...")

            processing_info = result.get("processing_info", {})
            logger.info(f"  引擎: {processing_info.get('engine')}")
            logger.info(f"  提供商: {processing_info.get('provider')}")

            return True
        else:
            logger.error(f"✗ PDF 处理失败: {result.get('error')}")
            return False

    except Exception as e:
        logger.error(f"✗ 测试异常: {str(e)}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """运行所有测试"""
    logger.info("开始 MinerU 官方 API 集成测试")
    logger.info("")

    results = {}

    # 测试 1: 文件上传服务
    results["file_upload"] = test_file_upload_service()

    # 测试 2: MinerU 官方 API
    results["mineru_api"] = test_mineru_official_api()

    # 测试 3: MinerU 处理器集成
    results["mineru_processor"] = test_mineru_processor_official()

    # 汇总结果
    logger.info("")
    logger.info("=" * 60)
    logger.info("测试结果汇总")
    logger.info("=" * 60)

    for test_name, result in results.items():
        if result is True:
            status = "✓ 通过"
        elif result is False:
            status = "✗ 失败"
        else:
            status = "⊘ 跳过"

        logger.info(f"{test_name:20s} {status}")

    passed = sum(1 for r in results.values() if r is True)
    total = sum(1 for r in results.values() if r is not None)
    logger.info("")
    logger.info(f"通过: {passed}/{total}")

    if passed == total and total > 0:
        logger.info("")
        logger.info("🎉 所有测试通过！")
        return 0
    else:
        logger.info("")
        logger.info("⚠️ 部分测试失败，请检查日志")
        return 1


if __name__ == "__main__":
    sys.exit(main())
