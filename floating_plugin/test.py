import json
import os


def generate_params_js(
    params_dict, output_file="params_config.js", var_name="GLOBAL_PARAMS"
):
    """
    将 Python 字典转换为 JavaScript 变量定义并写入文件

    Args:
        params_dict: Python 字典对象
        output_file: 输出的 .js 文件路径
        var_name: JavaScript 中的变量名
    """
    try:
        # 使用 json.dumps 将 Python 字典转换为 JSON 字符串
        # indent=4 使生成的 JS 文件易于阅读
        # ensure_ascii=False 确保中文字符不会被转义为 Unicode 编码
        json_content = json.dumps(params_dict, indent=4, ensure_ascii=False)

        # 构造 JavaScript 变量定义语句
        js_content = f"// 自动生成的参数配置文件\nconst {var_name} = {json_content};\n"

        # 写入文件
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(js_content)

        print(f"成功生成 JS 文件: {os.path.abspath(output_file)}")
        return True
    except Exception as e:
        print(f"生成 JS 文件失败: {e}")
        return False


# 你的数据
params = {
    "BA-C(CM)": {"name": "长(cm)", "value": "10"},
    "BA-K(CM)": {"name": "宽(cm)", "value": "10"},
    "BA-SL": {"name": "数量", "value": "1000"},
    "BA-KS": {"name": "款数", "value": "1"},
    "产品": {
        "name": "手提袋配件",
        "value": "FP-STDDB",
        "FP-STDDB": {
            "BA-C": {"name": "长", "value": "500"},
            "BA-K": {"name": "宽", "value": "500"},
            "材质": {"name": "", "value": "MK-300-33-JH-BBZ", "label": "250克白板纸"},
        },
        "label": "手提袋垫板",
    },
    "BA-ZZZGY": {"name": "种子纸工艺", "value": ""},
    "材质": {"name": "种子纸", "value": "MK-HHZZ", "label": "混合种子"},
}

if __name__ == "__main__":
    # 执行生成
    generate_params_js(params)
