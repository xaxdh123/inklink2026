import sys
import time
import threading

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLineEdit, QTextEdit, QLabel
)
from PySide6.QtCore import Qt, Signal, Slot

# --- 爬虫相关库 ---
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup


# --------------------


class ScraperApp(QMainWindow):
    """主窗口应用程序类"""

    # 定义信号，用于跨线程更新 GUI 文本区域
    update_log_signal = Signal(str)

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PySide6 网页抓取工具")
        self.setGeometry(100, 100, 300, 600)

        # 爬虫状态变量
        self.driver = None
        self.is_scraping = False

        # 连接信号到槽函数
        self.update_log_signal.connect(self.update_log)

        self.init_ui()

    def init_ui(self):
        """初始化用户界面"""
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # --- 1. URL 输入及控件区 ---
        url_layout = QHBoxLayout()
        url_layout.addWidget(QLabel("目标 URL:"))
        self.url_input = QLineEdit("http://books.toscrape.com/")
        url_layout.addWidget(self.url_input)
        main_layout.addLayout(url_layout)

        # --- 2. 按钮集合区 ---
        button_layout = QHBoxLayout()

        self.btn_open = QPushButton("① 打开浏览器 (启动)")
        self.btn_open.clicked.connect(self.start_browser_thread)
        button_layout.addWidget(self.btn_open)

        self.btn_scrape = QPushButton("② 开始抓取内容")
        self.btn_scrape.setEnabled(False)  # 初始禁用
        self.btn_scrape.clicked.connect(self.start_scrape_thread)
        button_layout.addWidget(self.btn_scrape)

        self.btn_close = QPushButton("③ 关闭浏览器")
        self.btn_close.setEnabled(False)  # 初始禁用
        self.btn_close.clicked.connect(self.close_browser)
        button_layout.addWidget(self.btn_close)

        main_layout.addLayout(button_layout)

        # --- 3. 日志和结果显示区 ---
        main_layout.addWidget(QLabel("--- 抓取日志和结果 ---"))
        self.log_output = QTextEdit()
        self.log_output.setReadOnly(True)
        main_layout.addWidget(self.log_output)

        # 初始状态更新
        self.update_log("应用已启动。请点击 '打开浏览器' 按钮。")

    @Slot(str)
    def update_log(self, text):
        """槽函数：接收信号并更新日志文本框"""
        self.log_output.append(text)

    # --------------------------------------------------------------------------
    # 按钮操作逻辑 - 使用线程避免 UI 冻结
    # --------------------------------------------------------------------------

    def start_browser_thread(self):
        """启动浏览器操作，放入新线程"""
        self.update_log("尝试启动浏览器...")
        # 禁用按钮防止重复点击
        self.btn_open.setEnabled(False)
        self.btn_close.setEnabled(True)

        thread = threading.Thread(target=self._open_browser_worker)
        thread.start()

    def _open_browser_worker(self):
        """线程工作函数：打开浏览器"""
        try:
            url = self.url_input.text()

            # 使用 webdriver_manager 自动安装驱动
            service = Service(ChromeDriverManager().install())
            options = webdriver.ChromeOptions()
            options.binary_location = r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
            # 可以添加 options.add_argument('--headless') 实现无头模式

            self.driver = webdriver.Chrome(service=service, options=options)
            self.driver.implicitly_wait(10)
            self.driver.get(url)

            self.update_log_signal.emit(f"✅ 浏览器已打开，并导航到: {url}")
            # 成功后启用抓取按钮
            self.btn_scrape.setEnabled(True)

        except Exception as e:
            self.update_log_signal.emit(f"❌ 启动浏览器失败: {e}")
            self.btn_open.setEnabled(True)  # 失败则重新启用打开按钮
            self.btn_close.setEnabled(False)
            if self.driver:
                self.driver.quit()
                self.driver = None

    def close_browser(self):
        """关闭浏览器"""
        if self.driver:
            self.driver.quit()
            self.driver = None
            self.update_log("🔴 浏览器已关闭。")
            self.btn_open.setEnabled(True)
            self.btn_close.setEnabled(False)
            self.btn_scrape.setEnabled(False)
        else:
            self.update_log("浏览器未运行。")

    def start_scrape_thread(self):
        """开始抓取操作，放入新线程"""
        if self.is_scraping:
            self.update_log("抓取正在进行中，请勿重复点击。")
            return

        self.is_scraping = True
        self.btn_scrape.setEnabled(False)  # 禁用抓取按钮
        self.update_log("尝试开始抓取...")

        thread = threading.Thread(target=self._scrape_worker)
        thread.start()

    def _scrape_worker(self):
        """线程工作函数：抓取和解析"""
        try:
            if not self.driver:
                self.update_log_signal.emit("❌ 抓取失败：请先打开浏览器。")
                return

            # --- 模拟用户操作和等待 (如果需要) ---
            self.update_log_signal.emit("➡️ 模拟操作：等待 2 秒加载动态内容...")
            time.sleep(2)

            # --- 核心抓取步骤：获取 Selenium 渲染后的 HTML ---
            html_source = self.driver.page_source
            self.update_log_signal.emit("✅ 成功获取当前页面的 HTML 源码。")

            # --- 使用 BeautifulSoup 解析 ---
            soup = BeautifulSoup(html_source, 'html.parser')

            # 示例解析：提取所有书名
            books = soup.find_all('h3')  # 在 books.toscrape.com 网站上，书名在 h3 标签内

            results = f"--- 抓取结果 ({len(books)} 本书) ---\n"
            for i, book_tag in enumerate(books):
                if i < 10:  # 只展示前 10 个
                    results += f"{i + 1}. {book_tag.text.strip()}\n"
                else:
                    results += "...\n"
                    break
            results += "--------------------------------------"

            self.update_log_signal.emit(results)

        except Exception as e:
            self.update_log_signal.emit(f"❌ 抓取或解析过程中发生错误: {e}")

        finally:
            self.is_scraping = False
            self.btn_scrape.setEnabled(True)  # 恢复抓取按钮


# --- 主程序入口 ---
if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ScraperApp()
    window.show()
    sys.exit(app.exec())