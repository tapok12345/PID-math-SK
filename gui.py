import sys
import os
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QComboBox, QCheckBox, QSpinBox, QDialog,
                             QTextEdit, QFileDialog, QMessageBox, QDockWidget, QLabel, QAction,
                             QColorDialog, QFormLayout)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QColor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.backends.backend_qt5agg import NavigationToolbar2QT as NavigationToolbar

from bbl_parser import parse_bbl
from plotter import create_figure
from pid_calculator import calculate_metrics

class LineStylerDialog(QDialog):
    def __init__(self, axs, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Настройка линий")
        self.resize(350, 250)
        self.axs = axs
        self.lines = []
        
        layout = QVBoxLayout()
        for ax in self.axs:
            for line in ax.lines:
                lbl = line.get_label()
                if not lbl.startswith('_'): # Игнорируем служебные линии (включая курсор)
                    self.lines.append((ax, line, lbl))
                    
        self.line_combo = QComboBox()
        for _, _, lbl in self.lines:
            self.line_combo.addItem(lbl)
        self.line_combo.currentIndexChanged.connect(self.update_ui_from_line)
        
        form = QFormLayout()
        form.addRow("Линия:", self.line_combo)
        
        self.btn_color = QPushButton("Выбрать цвет")
        self.btn_color.clicked.connect(self.pick_color)
        form.addRow("Цвет:", self.btn_color)
        
        self.combo_style = QComboBox()
        self.combo_style.addItems(["Сплошная (-)", "Пунктир (--)", "Точки (:)", "Штрих-пунктир (-.)"])
        form.addRow("Стиль:", self.combo_style)
        
        layout.addLayout(form)
        
        btn_layout = QHBoxLayout()
        btn_apply = QPushButton("Применить")
        btn_apply.clicked.connect(self.apply_style)
        btn_close = QPushButton("Закрыть")
        btn_close.clicked.connect(self.close)
        btn_layout.addWidget(btn_apply)
        btn_layout.addWidget(btn_close)
        
        layout.addLayout(btn_layout)
        self.setLayout(layout)
        
        self.update_ui_from_line()

    def update_ui_from_line(self):
        idx = self.line_combo.currentIndex()
        if idx < 0: return
        _, line, _ = self.lines[idx]
        self.current_color = line.get_color()
        self.btn_color.setStyleSheet(f"background-color: {self.current_color}; color: black;")
        
        ls = line.get_linestyle()
        if ls in ['-', 'solid']: self.combo_style.setCurrentIndex(0)
        elif ls in ['--', 'dashed']: self.combo_style.setCurrentIndex(1)
        elif ls in [':', 'dotted']: self.combo_style.setCurrentIndex(2)
        elif ls in ['-.', 'dashdot']: self.combo_style.setCurrentIndex(3)

    def pick_color(self):
        color = QColorDialog.getColor(QColor(self.current_color), self, "Выберите цвет")
        if color.isValid():
            self.current_color = color.name()
            self.btn_color.setStyleSheet(f"background-color: {self.current_color}; color: black;")

    def apply_style(self):
        idx = self.line_combo.currentIndex()
        if idx < 0: return
        _, line, _ = self.lines[idx]
        
        line.set_color(self.current_color)
        styles = ['-', '--', ':', '-.']
        line.set_linestyle(styles[self.combo_style.currentIndex()])
        line.axes.figure.canvas.draw()


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("PID Анализатор логов")
        self.resize(1400, 900)

        self.datasets = []
        self.canvas = None
        self.toolbar = None
        self.axs = None
        
        # Элементы курсора
        self.cursor_text = None
        self.cursor_vline = None
        self.cursor_hline = None
        self.cursor_marker = None
        
        self.expand_mode = False
        self.reset_mode = False
        self.maximized_ax = None
        
        self.current_plot_theme = 'dark'
        self.step = 1
        
        self._pan_ax = None
        self._pan_mode = None
        self._pan_start_x = None
        self._pan_start_y = None
        self._pan_xlim = None
        self._pan_ylim = None
        
        self.initial_lims = []
        self.styler_dialog = None

        self.init_ui()

    def init_ui(self):
        toolbar = self.addToolBar("Настройки")
        toolbar.setMovable(False)
        
        toolbar.addWidget(QLabel(" Интерфейс: "))
        self.combo_app_theme = QComboBox()
        self.combo_app_theme.addItems(["Светлая", "Темная"])
        self.combo_app_theme.currentIndexChanged.connect(self.on_app_theme_changed)
        toolbar.addWidget(self.combo_app_theme)

        toolbar.addSeparator()
        toolbar.addWidget(QLabel(" Графики: "))
        self.combo_plot_theme = QComboBox()
        self.combo_plot_theme.addItems(["Темная", "Белая", "Желто-белая"])
        self.combo_plot_theme.currentIndexChanged.connect(self.on_plot_theme_changed)
        toolbar.addWidget(self.combo_plot_theme)

        toolbar.addSeparator()
        self.action_maximize = QAction("Развернуть график", self)
        self.action_maximize.triggered.connect(self.toggle_maximize)
        toolbar.addAction(self.action_maximize)
        
        self.action_reset = QAction("↺ Сброс графика", self)
        self.action_reset.triggered.connect(self.toggle_reset)
        toolbar.addAction(self.action_reset)

        left_dock = QDockWidget("Управление", self)
        left_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        left_widget = QWidget()
        left_layout = QVBoxLayout()
        
        self.btn_load = QPushButton("Добавить лог (.bbl)")
        self.btn_load.setStyleSheet("padding: 10px; font-weight: bold;")
        self.btn_load.clicked.connect(self.load_file)
        left_layout.addWidget(self.btn_load)

        self.files_layout = QVBoxLayout()
        left_layout.addLayout(self.files_layout)

        self.btn_styles = QPushButton("Настроить цвета/стили")
        self.btn_styles.clicked.connect(self.open_styles)
        left_layout.addWidget(self.btn_styles)

        left_layout.addSpacing(15)
        
        # Курсор по умолчанию ВЫКЛЮЧЕН
        self.cb_cursor = QCheckBox("Показывать координаты (X, Y)")
        self.cb_cursor.setChecked(False)
        self.cb_cursor.stateChanged.connect(self.toggle_cursor)
        left_layout.addWidget(self.cb_cursor)

        self.cb_legends = QCheckBox("Показывать легенды")
        self.cb_legends.setChecked(True)
        self.cb_legends.stateChanged.connect(self.on_legends_changed)
        left_layout.addWidget(self.cb_legends)

        left_layout.addSpacing(15)
        left_layout.addWidget(QLabel("<b>Прореживание точек:</b>"))
        self.spin_decimate = QSpinBox()
        self.spin_decimate.setRange(1, 5000)
        self.spin_decimate.setValue(1)
        left_layout.addWidget(self.spin_decimate)
        
        # Обновленная подсказка (100-200)
        lbl_hint = QLabel("Рекомендуется: 1 (все точки)\nдо 100-200 (быстро)")
        lbl_hint.setStyleSheet("color: gray; font-size: 10px;")
        left_layout.addWidget(lbl_hint)

        self.btn_apply_decimate = QPushButton("Применить прореживание")
        self.btn_apply_decimate.clicked.connect(self.apply_decimation)
        left_layout.addWidget(self.btn_apply_decimate)
        
        left_layout.addStretch()
        left_widget.setLayout(left_layout)
        left_dock.setWidget(left_widget)
        self.addDockWidget(Qt.LeftDockWidgetArea, left_dock)

        right_dock = QDockWidget("Графики и Статистика", self)
        right_dock.setFeatures(QDockWidget.NoDockWidgetFeatures)
        right_widget = QWidget()
        right_layout = QVBoxLayout()

        right_layout.addWidget(QLabel("<b>Отображение графиков:</b>"))
        self.cb_plots = {}
        plot_names = ['Гироскоп/Задатчик', 'P-терм', 'I-терм', 'D-терм', 'Ошибка']
        for i, name in enumerate(plot_names):
            cb = QCheckBox(name)
            cb.setChecked(True)
            cb.stateChanged.connect(self.update_visibility)
            self.cb_plots[i] = cb
            right_layout.addWidget(cb)

        right_layout.addSpacing(10)
        right_layout.addWidget(QLabel("<b>5-й график (Шум и моторы):</b>"))
        self.cb_noise = QCheckBox("Шум (гироскоп)")
        self.cb_noise.setChecked(True)
        self.cb_noise.stateChanged.connect(self.update_visibility)
        right_layout.addWidget(self.cb_noise)

        self.cb_attitude = QCheckBox("Положение (Setpoint)")
        self.cb_attitude.setChecked(True)
        self.cb_attitude.stateChanged.connect(self.update_visibility)
        right_layout.addWidget(self.cb_attitude)

        self.cb_motor_load = QCheckBox("Нагрузка моторов")
        self.cb_motor_load.setChecked(True)
        self.cb_motor_load.stateChanged.connect(self.update_visibility)
        right_layout.addWidget(self.cb_motor_load)

        right_layout.addSpacing(20)
        right_layout.addWidget(QLabel("<b>Статистика:</b>"))
        self.text_stats = QTextEdit()
        self.text_stats.setReadOnly(True)
        self.text_stats.setStyleSheet("background-color: #2b2b2b; color: white; font-family: monospace;")
        right_layout.addWidget(self.text_stats)

        right_widget.setLayout(right_layout)
        right_dock.setWidget(right_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, right_dock)

        self.central_widget = QWidget()
        self.central_layout = QVBoxLayout()
        self.central_widget.setLayout(self.central_layout)
        self.setCentralWidget(self.central_widget)
        
        self.lbl_active_files = QLabel("Файлы не загружены")
        self.lbl_active_files.setStyleSheet("font-weight: bold; padding: 5px;")
        self.central_layout.addWidget(self.lbl_active_files)

        self.statusBar().showMessage("Готов к работе")
        
        self.combo_app_theme.setCurrentIndex(1)
        self.combo_plot_theme.setCurrentIndex(0)
        self.on_app_theme_changed(1)

    def on_app_theme_changed(self, index):
        if index == 1:
            self.setStyleSheet("""
                QMainWindow, QWidget { background-color: #2b2b2b; color: white; }
                QDockWidget { color: white; }
                QLabel { color: white; }
                QCheckBox { color: white; }
                QPushButton { background-color: #444; color: white; border: 1px solid #666; padding: 5px;}
                QPushButton:hover { background-color: #555; }
                QComboBox { background-color: #444; color: white; border: 1px solid #666; }
                QSpinBox { background-color: #444; color: white; border: 1px solid #666; }
                QToolBar { background-color: #333; border-bottom: 1px solid #555; }
                QStatusBar { background-color: #333; color: white; }
            """)
        else:
            self.setStyleSheet("")

    def on_plot_theme_changed(self, index):
        themes = ['dark', 'light', 'yellow']
        self.current_plot_theme = themes[index]
        self.rebuild_plots()

    def on_legends_changed(self):
        self.rebuild_plots()

    def apply_decimation(self):
        self.step = self.spin_decimate.value()
        self.rebuild_plots()

    def load_file(self):
        file_paths, _ = QFileDialog.getOpenFileNames(self, "Добавить логи", "", "Blackbox Logs (*.bbl *.txt);;All Files (*)")
        if not file_paths: return
        
        for file_path in file_paths:
            filename = os.path.basename(file_path)
            if any(ds['filename'] == filename for ds in self.datasets): continue
                
            try:
                data = parse_bbl(file_path)
                if data:
                    self.datasets.append({'filename': filename, 'data': data, 'visible': True})
            except Exception as e:
                QMessageBox.critical(self, "Ошибка", f"Не удалось загрузить {filename}:\n{e}")

        self.update_file_list()
        self.rebuild_plots()

    def update_file_list(self):
        for i in reversed(range(self.files_layout.count())):
            widget = self.files_layout.itemAt(i).widget()
            if widget: widget.setParent(None)

        for ds in self.datasets:
            row = QWidget()
            layout = QHBoxLayout()
            layout.setContentsMargins(0, 0, 0, 0)
            
            cb = QCheckBox()
            cb.setChecked(ds['visible'])
            cb.stateChanged.connect(lambda state, d=ds: self.toggle_file_visibility(d, state))
            
            lbl = QLabel(ds['filename'])
            
            layout.addWidget(cb)
            layout.addWidget(lbl)
            layout.addStretch()
            row.setLayout(layout)
            self.files_layout.addWidget(row)

    def toggle_file_visibility(self, ds, state):
        ds['visible'] = (state == Qt.Checked)
        self.rebuild_plots()

    def open_styles(self):
        if self.axs is not None:
            self.styler_dialog = LineStylerDialog(self.axs, self)
            self.styler_dialog.setModal(False)
            self.styler_dialog.show()

    def rebuild_plots(self):
        if self.canvas:
            self.central_layout.removeWidget(self.canvas)
            self.canvas.deleteLater()
        if self.toolbar:
            self.central_layout.removeWidget(self.toolbar)
            self.toolbar.deleteLater()

        active_datasets = [ds for ds in self.datasets if ds['visible']]
        
        if active_datasets:
            names = ", ".join([ds['filename'] for ds in active_datasets])
            self.lbl_active_files.setText(f"Активные логи: {names}")
        else:
            self.lbl_active_files.setText("Нет активных логов")

        fig, self.axs = create_figure(active_datasets, self.current_plot_theme, step=self.step, show_legends=self.cb_legends.isChecked())
        
        self.initial_lims = []
        for ax in self.axs:
            self.initial_lims.append((ax.get_xlim(), ax.get_ylim()))

        self.canvas = FigureCanvas(fig)
        self.toolbar = NavigationToolbar(self.canvas, self)

        self.central_layout.addWidget(self.toolbar)
        self.central_layout.addWidget(self.canvas)

        self.canvas.mpl_connect('motion_notify_event', self.on_motion)
        self.canvas.mpl_connect('button_press_event', self.on_press)
        self.canvas.mpl_connect('button_release_event', self.on_release)
        self.canvas.mpl_connect('scroll_event', self.on_scroll)

        # Сбрасываем ссылки на старые элементы курсора
        self.cursor_text = None
        self.cursor_vline = None
        self.cursor_hline = None
        self.cursor_marker = None

        self.update_visibility()
        self.update_stats(active_datasets)

    def on_press(self, event):
        if self.expand_mode:
            if event.inaxes:
                self.maximize_plot(event.inaxes)
            return
            
        if self.reset_mode:
            if event.inaxes:
                self.reset_plot(event.inaxes)
            return

        if event.inaxes is None:
            return

        self._pan_ax = event.inaxes
        self._pan_start_x = event.x
        self._pan_start_y = event.y
        self._pan_xlim = self._pan_ax.get_xlim()
        self._pan_ylim = self._pan_ax.get_ylim()
        self._pan_ax.set_autoscale_on(False)

        if event.button == 1:
            self._pan_mode = 'both'
            self.canvas.setCursor(Qt.ClosedHandCursor)
        elif event.button == 2:
            self._pan_mode = 'y_only'
            self.canvas.setCursor(Qt.SizeVerCursor)
        elif event.button == 3:
            self._pan_mode = 'x_only'
            self.canvas.setCursor(Qt.SizeHorCursor)

    def on_release(self, event):
        if event.button in (1, 2, 3):
            self._pan_ax = None
            if not self.expand_mode and not self.reset_mode:
                self.canvas.setCursor(Qt.ArrowCursor)

    def on_motion(self, event):
        # 1. Обработка перемещения (Pan)
        if self._pan_ax is not None and event.x is not None and event.y is not None:
            inv = self._pan_ax.transData.inverted()
            start_data = inv.transform((self._pan_start_x, self._pan_start_y))
            current_data = inv.transform((event.x, event.y))
            
            dx = start_data[0] - current_data[0]
            dy = start_data[1] - current_data[1]
            
            if self._pan_mode == 'both':
                self._pan_ax.set_xlim(self._pan_xlim[0] + dx, self._pan_xlim[1] + dx)
                self._pan_ax.set_ylim(self._pan_ylim[0] + dy, self._pan_ylim[1] + dy)
            elif self._pan_mode == 'x_only':
                self._pan_ax.set_xlim(self._pan_xlim[0] + dx, self._pan_xlim[1] + dx)
            elif self._pan_mode == 'y_only':
                self._pan_ax.set_ylim(self._pan_ylim[0] + dy, self._pan_ylim[1] + dy)
                
            self.canvas.draw_idle()
            return

        # 2. Обработка курсора координат
        if not self.cb_cursor.isChecked() or not event.inaxes:
            if self.cursor_marker is not None and self.cursor_marker.get_visible():
                self.cursor_marker.set_visible(False)
                self.cursor_vline.set_visible(False)
                self.cursor_hline.set_visible(False)
                self.cursor_text.set_visible(False)
                self.canvas.draw_idle()
            return

        ax = event.inaxes
        x, y = event.xdata, event.ydata
        
        # Если курсора нет или мы перешли на другой график
        if self.cursor_marker is None or self.cursor_marker.axes != ax:
            # Удаляем старые элементы, если они были
            if self.cursor_marker is not None:
                self.cursor_marker.remove()
                self.cursor_vline.remove()
                self.cursor_hline.remove()
                self.cursor_text.remove()

            # Создаем новые элементы: перекрестие и точку
            self.cursor_vline = ax.axvline(x, color='lime', alpha=0.4, linestyle='--', linewidth=1)
            self.cursor_hline = ax.axhline(y, color='lime', alpha=0.4, linestyle='--', linewidth=1)
            self.cursor_marker, = ax.plot([x], [y], marker='o', color='lime', markersize=6, alpha=0.8)
            self.cursor_text = ax.text(x, y, "", bbox=dict(boxstyle="round", fc="lime", ec="darkgreen", alpha=0.3), fontsize=9, color="white")
        else:
            # Обновляем позицию существующих элементов
            self.cursor_vline.set_xdata([x, x])
            self.cursor_hline.set_ydata([y, y])
            self.cursor_marker.set_data([x], [y])
            self.cursor_text.set_position((x, y))

        # Устанавливаем текст и делаем видимым
        self.cursor_text.set_text(f"X: {x:.2f}, Y: {y:.2f}")
        self.cursor_marker.set_visible(True)
        self.cursor_vline.set_visible(True)
        self.cursor_hline.set_visible(True)
        self.cursor_text.set_visible(True)
        
        self.canvas.draw_idle()

    def on_scroll(self, event):
        if event.inaxes is None:
            return
        
        ax = event.inaxes
        cur_xlim = ax.get_xlim()
        cur_ylim = ax.get_ylim()
        xdata = event.xdata
        ydata = event.ydata
        
        is_ctrl = bool(QApplication.keyboardModifiers() & Qt.ControlModifier)

        base_scale = 1.2
        if event.button == 'up':
            scale_factor = 1 / base_scale
        elif event.button == 'down':
            scale_factor = base_scale
        else:
            return

        if is_ctrl:
            new_width = (cur_xlim[1] - cur_xlim[0]) * scale_factor
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            relx = (cur_xlim[1] - xdata) / (cur_xlim[1] - cur_xlim[0])
            rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_xlim([xdata - new_width * (1 - relx), xdata + new_width * relx])
            ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])
        else:
            new_height = (cur_ylim[1] - cur_ylim[0]) * scale_factor
            rely = (cur_ylim[1] - ydata) / (cur_ylim[1] - cur_ylim[0])
            ax.set_ylim([ydata - new_height * (1 - rely), ydata + new_height * rely])

        self.canvas.draw_idle()

    def toggle_maximize(self):
        if self.maximized_ax is not None:
            self.restore_layout()
        else:
            self.expand_mode = True
            self.reset_mode = False
            self.action_maximize.setText("Кликните на график...")
            self.action_reset.setText("↺ Сброс графика")
            self.canvas.setCursor(Qt.CrossCursor)

    def maximize_plot(self, ax):
        self.expand_mode = False
        self.canvas.setCursor(Qt.ArrowCursor)
        
        if not hasattr(self, 'orig_positions'):
            self.orig_positions = [a.get_position().bounds for a in self.axs]
        
        for a in self.axs:
            if a != ax: a.set_visible(False)
        
        ax.set_position([0.05, 0.05, 0.9, 0.9])
        self.canvas.draw_idle()
        
        self.maximized_ax = ax
        self.action_maximize.setText("Свернуть обратно")

    def toggle_reset(self):
        self.reset_mode = True
        self.expand_mode = False
        self.action_reset.setText("Кликните на график для сброса...")
        self.action_maximize.setText("Развернуть график")
        self.canvas.setCursor(Qt.CrossCursor)

    def reset_plot(self, ax):
        self.reset_mode = False
        self.canvas.setCursor(Qt.ArrowCursor)
        self.action_reset.setText("↺ Сброс графика")
        
        try:
            idx = list(self.axs).index(ax)
            if idx < len(self.initial_lims):
                xlim, ylim = self.initial_lims[idx]
                ax.set_xlim(xlim)
                ax.set_ylim(ylim)
        except ValueError:
            pass
        
        self.canvas.draw_idle()

    def restore_layout(self):
        for i, a in enumerate(self.axs):
            a.set_position(self.orig_positions[i])
        
        self.maximized_ax = None
        self.update_visibility()
        self.action_maximize.setText("Развернуть график")
        self.canvas.draw_idle()

    def toggle_cursor(self, state):
        if state != Qt.Checked:
            if self.cursor_marker is not None:
                self.cursor_marker.set_visible(False)
                self.cursor_vline.set_visible(False)
                self.cursor_hline.set_visible(False)
                self.cursor_text.set_visible(False)
                self.canvas.draw_idle()

    def update_visibility(self):
        if self.canvas is None or self.axs is None: return
        if self.maximized_ax is not None: return

        self.axs[0].set_visible(self.cb_plots[0].isChecked())
        self.axs[1].set_visible(self.cb_plots[1].isChecked())
        self.axs[2].set_visible(self.cb_plots[2].isChecked())
        
        if self.cb_plots[3].isChecked() or self.cb_plots[4].isChecked():
            self.axs[3].set_visible(True)
            for line in self.axs[3].lines:
                lbl = line.get_label()
                if lbl.startswith('_'): continue # Пропускаем служебные линии
                if 'Error' in lbl:
                    line.set_visible(self.cb_plots[4].isChecked())
                else:
                    line.set_visible(self.cb_plots[3].isChecked())
        else:
            self.axs[3].set_visible(False)

        ax5 = self.axs[4]
        ax5.set_visible(True)
        for line in ax5.lines:
            lbl = line.get_label()
            if lbl.startswith('_'): continue
            if 'Noise' in lbl:
                line.set_visible(self.cb_noise.isChecked())
            elif 'Attitude' in lbl:
                line.set_visible(self.cb_attitude.isChecked())
            elif 'Motors' in lbl:
                line.set_visible(self.cb_motor_load.isChecked())
        
        self.canvas.draw_idle()

    def update_stats(self, active_datasets):
        if not active_datasets:
            self.text_stats.clear()
            return
            
        text = ""
        for i, ds in enumerate(active_datasets):
            metrics = calculate_metrics(ds['data'])
            text += f"--- Файл {i+1}: {ds['filename']} ---\n"
            for key, val in metrics.items():
                text += f"{key}: {val}\n"
            text += "\n"
            
        self.text_stats.setText(text)