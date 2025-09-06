import os
import threading
import pandas as pd
import akshare as ak
from functools import partial
from datetime import datetime

# 在导入kivy之前设置环境变量(如果在Windows上运行)
# 这行对于安卓打包没有影响，但保留着无妨
if os.name == 'nt':
    os.environ['KIVY_GL_BACKEND'] = 'angle_sdl2'

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.popup import Popup
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.core.text import LabelBase
from kivy.config import Config

# =============================================================================
# --- 字体设置 (安卓打包最终版) ---
# 1. 注册字体文件。Buildozer打包时会把这个字体文件一起打包进APK。
#    确保 'NotoSansSC-Regular.ttf' 文件就在这个脚本的旁边。
LabelBase.register(name='NotoSans', fn_regular='NotoSansSC-Regular.ttf')

# 2. 将 'NotoSans' 设置为 Kivy 应用的全局默认字体。
Config.set('kivy', 'default_font', 'NotoSans')
# =============================================================================


# 定义股票板块前缀和对应的中文名称
BOARD_MAP = {
    '主板': ['60', '00'],
    '创业': ['30'],
    '科创': ['68'],
    '北证': ['43', '83', '87']
}

class MainApp(App):
    def build(self):
        # --- 主布局 ---
        self.main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)
        Window.clearcolor = (0.1, 0.1, 0.1, 1) # 设置深色背景

        # --- 顶部信息汇总区 ---
        top_info_layout = GridLayout(cols=4, size_hint_y=None, height=40)
        self.summary_labels = {
            "大笔买入": Label(text="买入: 0", font_size='16sp'),
            "大笔卖出": Label(text="卖出: 0", font_size='16sp'),
            "有大买盘": Label(text="买盘: 0", font_size='16sp'),
            "有大卖盘": Label(text="卖盘: 0", font_size='16sp'),
        }
        for label in self.summary_labels.values():
            top_info_layout.add_widget(label)
        self.main_layout.add_widget(top_info_layout)

        # --- 中部控制区 ---
        controls_layout = BoxLayout(size_hint_y=None, height=50, spacing=10)

        controls_layout.add_widget(Label(text="大笔买入次数>=", size_hint_x=None, width=150))
        self.min_buy_input = TextInput(text="0", multiline=False, size_hint_x=None, width=60, halign='center', padding_y=[15,0])
        controls_layout.add_widget(self.min_buy_input)

        self.refresh_button = Button(text="刷新下载", on_press=self.start_data_fetch_thread)
        self.filter_button = Button(text="板块过滤", on_press=self.show_board_filter_popup)
        self.reset_button = Button(text="恢复默认", on_press=self.reset_filters)

        controls_layout.add_widget(self.refresh_button)
        controls_layout.add_widget(self.filter_button)
        controls_layout.add_widget(self.reset_button)
        self.main_layout.add_widget(controls_layout)

        self.status_label = Label(text="请点击'刷新下载'获取数据", size_hint_y=None, height=30)
        self.main_layout.add_widget(self.status_label)

        # --- 底部数据表格区 ---
        scroll_view = ScrollView()
        self.data_grid = GridLayout(cols=8, spacing=2, size_hint_y=None)
        self.data_grid.bind(minimum_height=self.data_grid.setter('height'))
        
        headers = ['代码', '名称', '统计开始日期', '统计结束日期', '大笔买入', '大笔卖出', '有大买盘', '有大卖盘']
        for header in headers:
            self.data_grid.add_widget(Label(text=header, bold=True, size_hint_y=None, height=40, color=(0.8, 0.8, 0.8, 1)))

        scroll_view.add_widget(self.data_grid)
        self.main_layout.add_widget(scroll_view)

        self.full_data_df = pd.DataFrame() 
        self.active_board_filters = set(BOARD_MAP.keys())

        return self.main_layout

    def start_data_fetch_thread(self, instance):
        self.status_label.text = "正在下载数据...请稍候"
        self.refresh_button.disabled = True
        threading.Thread(target=self.fetch_and_process_data).start()

    def fetch_and_process_data(self):
        symbols_to_monitor = ["大笔买入", "大笔卖出", "有大买盘", "有大卖盘"]
        all_dfs = []
        has_error = False

        for symbol in symbols_to_monitor:
            try:
                df = ak.stock_changes_em(symbol=symbol)
                if not df.empty:
                    df['异动类型'] = symbol
                    all_dfs.append(df)
            except Exception as e:
                error_message = f"获取'{symbol}'数据失败"
                Clock.schedule_once(partial(self.update_status, error_message))
                has_error = True

        if not all_dfs:
            if not has_error:
                Clock.schedule_once(partial(self.update_status, "未获取到任何异动数据。"))
            Clock.schedule_once(self.enable_refresh_button)
            return

        combined_df = pd.concat(all_dfs, ignore_index=True)
        counts_df = combined_df.groupby(['代码', '名称', '异动类型']).size().unstack(fill_value=0)
        
        for symbol in symbols_to_monitor:
            if symbol not in counts_df.columns:
                counts_df[symbol] = 0

        self.full_data_df = counts_df.reset_index()
        today_str = datetime.now().strftime('%Y-%m-%d')
        self.full_data_df['统计开始日期'] = today_str
        self.full_data_df['统计结束日期'] = today_str
        
        self.full_data_df = self.full_data_df[['代码', '名称', '统计开始日期', '统计结束日期', '大笔买入', '大笔卖出', '有大买盘', '有大卖盘']]

        Clock.schedule_once(self.update_ui)

    def update_ui(self, dt=None):
        widgets_to_remove = [widget for widget in self.data_grid.children if not getattr(widget, 'bold', False)]
        for widget in widgets_to_remove:
            self.data_grid.remove_widget(widget)

        df = self.full_data_df.copy()

        try:
            min_buys = int(self.min_buy_input.text)
            if min_buys > 0:
                 df = df[df['大笔买入'] >= min_buys]
        except (ValueError, TypeError):
            self.status_label.text = "错误: '大笔买入次数'必须是整数。"
            self.enable_refresh_button()
            return
            
        if self.active_board_filters:
            allowed_prefixes = [p for board_name in self.active_board_filters for p in BOARD_MAP.get(board_name, [])]
            if allowed_prefixes:
                 mask = df['代码'].astype(str).apply(lambda x: any(x.startswith(p) for p in allowed_prefixes))
                 df = df[mask]

        for index, row in df.iterrows():
            for col in ['代码', '名称', '统计开始日期', '统计结束日期', '大笔买入', '大笔卖出', '有大买盘', '有大卖盘']:
                cell_text = str(row[col])
                cell_color = (1, 1, 0, 1) if col in ['大笔买入', '有大买盘'] and row[col] > 0 else (0, 1, 1, 1) if col in ['大笔卖出', '有大卖盘'] and row[col] > 0 else (1,1,1,1)
                self.data_grid.add_widget(Label(text=cell_text, size_hint_y=None, height=30, color=cell_color))
        
        self.summary_labels["大笔买入"].text = f"买入: {df['大笔买入'].sum()}"
        self.summary_labels["大笔卖出"].text = f"卖出: {df['大笔卖出'].sum()}"
        self.summary_labels["有大买盘"].text = f"买盘: {df['有大买盘'].sum()}"
        self.summary_labels["有大卖盘"].text = f"卖盘: {df['有大卖盘'].sum()}"
        
        self.update_status(f"刷新完成: {datetime.now().strftime('%H:%M:%S')}, 共 {len(df)} 条记录")
        self.enable_refresh_button()

    def update_status(self, text, dt=None):
        self.status_label.text = text
    
    def enable_refresh_button(self, dt=None):
        self.refresh_button.disabled = False

    def reset_filters(self, instance):
        self.min_buy_input.text = "0"
        self.active_board_filters = set(BOARD_MAP.keys())
        self.status_label.text = "已恢复默认设置，正在刷新列表..."
        self.update_ui()

    def show_board_filter_popup(self, instance):
        content = GridLayout(cols=2, spacing=10, padding=10)
        self.popup_checkboxes = {}
        from kivy.uix.checkbox import CheckBox

        for board_name in BOARD_MAP.keys():
            layout = BoxLayout(spacing=5)
            checkbox = CheckBox(active=board_name in self.active_board_filters)
            label = Label(text=board_name)
            layout.add_widget(checkbox)
            layout.add_widget(label)
            content.add_widget(layout)
            self.popup_checkboxes[board_name] = checkbox

        confirm_button = Button(text="确定", size_hint_y=None, height=50)
        content.add_widget(confirm_button)
        
        popup = Popup(title='选择要显示的板块', content=content, size_hint=(0.8, 0.6))
        confirm_button.bind(on_press=lambda x: self.apply_board_filter(popup))
        popup.open()

    def apply_board_filter(self, popup):
        self.active_board_filters.clear()
        for board_name, checkbox in self.popup_checkboxes.items():
            if checkbox.active:
                self.active_board_filters.add(board_name)
        
        popup.dismiss()
        self.status_label.text = "板块过滤已应用，正在刷新列表..."
        self.update_ui()

if __name__ == '__main__':
    MainApp().run()