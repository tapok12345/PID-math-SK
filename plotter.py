import matplotlib
matplotlib.rcParams['path.simplify'] = True
matplotlib.rcParams['path.simplify_threshold'] = 1.0

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np

THEMES = {
    'dark': {'bg': '#2b2b2b', 'fg': 'white', 'grid': '#555555', 'spine': '#888888', 'plot_bg': '#2b2b2b'},
    'light': {'bg': 'white', 'fg': 'black', 'grid': '#cccccc', 'spine': '#666666', 'plot_bg': 'white'},
    'yellow': {'bg': '#fffde7', 'fg': '#333333', 'grid': '#dddddd', 'spine': '#999999', 'plot_bg': '#fffde7'}
}

COLORS = {
    'setpoint': 'red',
    'gyro': 'dodgerblue',
    'p': 'lime',
    'i': 'orange',
    'd': 'mediumorchid',
    'error': 'gray',
    'noise': 'cyan',
    'attitude': 'yellow',
    'motor': 'magenta'
}

LINE_STYLES = ['-', '--', '-.', ':']

def get_varied_color(base_hex, idx):
    """Возвращает измененный оттенок цвета для отличия 4 файлов."""
    if idx == 0: return base_hex
    rgb = mcolors.to_rgb(base_hex)
    if idx == 1: # Светлее
        return tuple(c + (1 - c) * 0.5 for c in rgb)
    elif idx == 2: # Темнее
        return tuple(c * 0.6 for c in rgb)
    elif idx == 3: # Самый светлый (почти пастельный)
        return tuple(c + (1 - c) * 0.8 for c in rgb)
    return base_hex

def create_figure(datasets: list, theme: str = 'dark', step: int = 1, show_legends: bool = True):
    colors = THEMES.get(theme, THEMES['dark'])
    
    fig, axs = plt.subplots(5, 1, figsize=(10, 14), sharex=False)
    fig.patch.set_facecolor(colors['bg'])
    fig.subplots_adjust(hspace=0.5, left=0.1, right=0.95, top=0.95, bottom=0.05)

    for i, ax in enumerate(axs):
        ax.set_facecolor(colors['plot_bg'])
        ax.tick_params(colors=colors['fg'])
        ax.yaxis.label.set_color(colors['fg'])
        ax.xaxis.label.set_color(colors['fg'])
        ax.grid(True, linestyle=':', alpha=0.2, color=colors['grid'])
        for spine in ax.spines.values():
            spine.set_color(colors['spine'])
        
        if i < 4:
            ax.tick_params(labelbottom=False, bottom=False)

    axs[0].set_title('Гироскоп vs Задатчик', color=colors['fg'])
    axs[0].set_ylabel('Градусы/сек', color=colors['fg'])
    axs[1].set_title('Пропорциональная (P)', color=colors['fg'])
    axs[2].set_title('Интегральная (I)', color=colors['fg'])
    axs[3].set_title('Дифференциальная (D) и Ошибка', color=colors['fg'])
    axs[4].set_title('Шум, положение и нагрузка моторов', color=colors['fg'])
    axs[4].set_ylabel('Шум / Угол / %', color=colors['fg'])
    axs[4].set_xlabel('Время (секунды)', color=colors['fg'])

    legend_kwargs = {}
    if show_legends:
        legend_kwargs = dict(loc='lower left', bbox_to_anchor=(0, 1.02, 1, 0.2), 
                             mode="expand", borderaxespad=0., ncol=2, 
                             facecolor=colors['plot_bg'], labelcolor=colors['fg'],
                             edgecolor=colors['spine'])

    for idx, ds in enumerate(datasets):
        data = ds['data']
        name = ds['filename']
        
        style = LINE_STYLES[idx % len(LINE_STYLES)]
        
        c_sp = get_varied_color(COLORS['setpoint'], idx)
        c_gyro = get_varied_color(COLORS['gyro'], idx)
        c_p = get_varied_color(COLORS['p'], idx)
        c_i = get_varied_color(COLORS['i'], idx)
        c_d = get_varied_color(COLORS['d'], idx)
        c_err = get_varied_color(COLORS['error'], idx)
        c_noise = get_varied_color(COLORS['noise'], idx)
        c_att = get_varied_color(COLORS['attitude'], idx)
        c_mot = get_varied_color(COLORS['motor'], idx)

        t = np.array(data['time'])[::step]
        
        sp = np.array(data['roll_setpoint'])[::step]
        gyro = np.array(data['roll_gyro'])[::step]
        p = np.array(data['roll_p'])[::step]
        i_term = np.array(data['roll_i'])[::step]
        d = np.array(data['roll_d'])[::step]
        err = np.array(data['roll_error'])[::step]
        att = np.array(data['attitude_roll'])[::step]
        mot_avg = np.mean([np.array(data[f'motor_{j}'])[::step] for j in range(4)], axis=0)

        axs[0].plot(t, sp, label=f'{name} (Setpoint)', linestyle='--', color=c_sp, alpha=0.8)
        axs[0].plot(t, gyro, label=f'{name} (Gyro)', linestyle=style, color=c_gyro, linewidth=1.2)
        
        axs[1].plot(t, p, label=f'{name} (P)', linestyle=style, color=c_p)
        
        axs[2].plot(t, i_term, label=f'{name} (I)', linestyle=style, color=c_i)
        
        axs[3].plot(t, d, label=f'{name} (D)', linestyle=style, color=c_d)
        axs[3].plot(t, err, label=f'{name} (Error)', linestyle=style, color=c_err, alpha=0.6)
        
        axs[4].plot(t, gyro, label=f'{name} (Noise)', linestyle=style, color=c_noise, alpha=0.7)
        axs[4].plot(t, att, label=f'{name} (Attitude)', linestyle=style, color=c_att, alpha=0.7)
        axs[4].plot(t, mot_avg, label=f'{name} (Motors)', linestyle=style, color=c_mot, alpha=0.7)

    if show_legends:
        axs[0].legend(**legend_kwargs)
        axs[1].legend(**legend_kwargs)
        axs[2].legend(**legend_kwargs)
        axs[3].legend(**legend_kwargs)
        axs[4].legend(**legend_kwargs)

    return fig, axs