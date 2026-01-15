# WebChannel 使用指南

BaseFeatureWindow 现在支持 WebQtChannel，允许网页与 Python 进行双向通信。

## 功能特性

- ✅ JavaScript 调用 Python 方法
- ✅ Python 调用 JavaScript 代码
- ✅ Python 向 JavaScript 发送消息
- ✅ 自动注入 WebChannel 库
- ✅ 每个功能页面独立的桥接对象

## JavaScript 调用 Python

### 1. 在 Python 中注册处理器

```python
from web.base_feature_window import BaseFeatureWindow

class MyWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "我的功能": "https://example.com",
        }
        super().__init__(features=features, parent=parent)
        
        # 注册 JavaScript 可以调用的方法
        self.register_js_handler("我的功能", "getUserInfo", self.handle_get_user_info)
        self.register_js_handler("我的功能", "saveData", self.handle_save_data)
    
    def handle_get_user_info(self, user_id):
        """处理来自 JavaScript 的调用"""
        return {
            "id": user_id,
            "name": "用户名",
            "email": "user@example.com"
        }
    
    def handle_save_data(self, data):
        """保存数据"""
        print(f"收到数据：{data}")
        return {"success": True}
```

### 2. 在 JavaScript 中调用

```javascript
// 等待 WebChannel 就绪
window.addEventListener('qtwebchannelready', function(event) {
    const bridge = event.detail.bridge;
    
    // 调用 Python 方法
    // 方法1：使用 call 方法（返回 JSON 字符串）
    const result = JSON.parse(bridge.call('getUserInfo', JSON.stringify(123)));
    console.log('用户信息:', result);
    
    // 方法2：直接调用（需要 Python 方法支持）
    bridge.getUserInfo(123).then(result => {
        console.log('用户信息:', result);
    });
    
    // 保存数据
    bridge.call('saveData', JSON.stringify({key: 'value'})).then(result => {
        const response = JSON.parse(result);
        if (response.success) {
            alert('保存成功！');
        }
    });
});
```

## Python 调用 JavaScript

```python
# 执行 JavaScript 代码
window.call_js("我的功能", """
    console.log('来自 Python 的消息');
    alert('Hello from Python!');
""")

# 调用 JavaScript 函数
window.call_js("我的功能", """
    if (typeof myFunction === 'function') {
        myFunction('参数1', '参数2');
    }
""")
```

## Python 向 JavaScript 发送消息

```python
# 发送消息到 JavaScript
window.send_message_to_js("我的功能", "dataUpdated", {
    "message": "数据已更新",
    "timestamp": "2024-01-01 12:00:00"
})
```

在 JavaScript 中接收：

```javascript
// 方式1：监听 signal
window.addEventListener('qtwebchannelready', function(event) {
    const bridge = event.detail.bridge;
    bridge.message_received.connect(function(eventName, data) {
        if (eventName === 'dataUpdated') {
            console.log('收到消息:', data);
        }
    });
});

// 方式2：监听自定义事件
window.addEventListener('dataUpdated', function(event) {
    console.log('数据已更新:', event.detail);
});
```

## 完整示例

### Python 端

```python
from web.base_feature_window import BaseFeatureWindow
from PySide6 import QtWidgets

class ExampleWindow(BaseFeatureWindow):
    def __init__(self, parent=None):
        features = {
            "示例": "https://example.com",
        }
        super().__init__(features=features, parent=parent)
        
        # 注册处理器
        self.register_js_handler("示例", "getConfig", self.get_config)
        self.register_js_handler("示例", "showMessage", self.show_message)
    
    def get_config(self):
        """返回配置信息"""
        return {
            "theme": "dark",
            "language": "zh-CN",
            "version": "1.0.0"
        }
    
    def show_message(self, message):
        """显示消息框"""
        QtWidgets.QMessageBox.information(self, "消息", message)
        return {"success": True}
```

### JavaScript 端

```html
<!DOCTYPE html>
<html>
<head>
    <title>WebChannel 示例</title>
</head>
<body>
    <h1>WebChannel 示例</h1>
    <button onclick="testCallPython()">调用 Python</button>
    <button onclick="testReceiveMessage()">接收消息</button>
    
    <script>
        let bridge = null;
        
        // 等待 WebChannel 就绪
        window.addEventListener('qtwebchannelready', function(event) {
            bridge = event.detail.bridge;
            console.log('WebChannel 已连接');
        });
        
        function testCallPython() {
            if (!bridge) {
                alert('WebChannel 尚未就绪');
                return;
            }
            
            // 获取配置
            const config = JSON.parse(bridge.call('getConfig'));
            console.log('配置:', config);
            
            // 显示消息
            const result = JSON.parse(bridge.call('showMessage', JSON.stringify('Hello from JavaScript!')));
            if (result.success) {
                console.log('消息已显示');
            }
        }
        
        function testReceiveMessage() {
            if (!bridge) {
                alert('WebChannel 尚未就绪');
                return;
            }
            
            // 监听消息
            bridge.message_received.connect(function(eventName, data) {
                console.log('收到消息:', eventName, data);
                alert(`收到消息: ${eventName}\n数据: ${JSON.stringify(data)}`);
            });
        }
    </script>
</body>
</html>
```

## API 参考

### BaseFeatureWindow 方法

#### `register_js_handler(feature_name: str, method_name: str, handler: Callable)`
注册 JavaScript 调用处理器。

#### `call_js(feature_name: str, script: str)`
在指定功能的页面中执行 JavaScript 代码。

#### `send_message_to_js(feature_name: str, event_name: str, data: dict)`
向指定功能的 JavaScript 发送消息。

#### `get_bridge(feature_name: str) -> Optional[WebChannelBridge]`
获取指定功能的 WebChannel 桥接对象。

### WebChannelBridge 方法（JavaScript 端）

#### `bridge.call(method: str, ...args: str) -> str`
调用 Python 方法，返回 JSON 字符串。

#### `bridge.message_received`
信号，当 Python 发送消息时触发。

## 注意事项

1. **等待就绪**：确保在 `qtwebchannelready` 事件后再使用 `window.bridge`
2. **JSON 序列化**：通过 `call` 方法传递的参数需要 JSON 序列化
3. **异步处理**：JavaScript 调用 Python 是异步的，使用 Promise 或回调处理结果
4. **错误处理**：Python 方法出错时会返回包含 `error` 字段的 JSON

## 调试技巧

```javascript
// 检查 WebChannel 状态
console.log('Bridge available:', typeof window.bridge !== 'undefined');
console.log('Bridge object:', window.bridge);

// 监听所有事件
window.addEventListener('qtwebchannelready', function(event) {
    console.log('WebChannel ready!', event.detail);
});
```
