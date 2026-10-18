"""
Модуль для чтения логов Betaflight (файлы .bbl).
"""
from orangebox import Parser
import numpy as np

def parse_bbl(file_path: str) -> dict:
    try:
        parser = Parser.load(file_path)
    except Exception as e:
        raise ValueError(f"Ошибка при открытии файла: {e}")

    field_names = parser.field_names
    idx = {name: i for i, name in enumerate(field_names)}

    data = {
        'time': [],
        'roll_gyro': [], 'pitch_gyro': [], 'yaw_gyro': [],
        'roll_setpoint': [], 'pitch_setpoint': [], 'yaw_setpoint': [],
        'roll_p': [], 'pitch_p': [], 'yaw_p': [],
        'roll_i': [], 'pitch_i': [], 'yaw_i': [],
        'roll_d': [], 'pitch_d': [], 'yaw_d': [],
        'roll_f': [], 'pitch_f': [], 'yaw_f': [],
        'roll_error': [], 'pitch_error': [], 'yaw_error': [],
        'motor_0': [], 'motor_1': [], 'motor_2': [], 'motor_3': [],
        'attitude_roll': [], 'attitude_pitch': []
    }

    def get_val(frame_data, name):
        i = idx.get(name)
        if i is None or i >= len(frame_data):
            return 0
        return frame_data[i]

    for frame in parser.frames():
        fd = frame.data
        data['time'].append(get_val(fd, 'time'))
        
        roll_g = get_val(fd, 'gyroADC[0]')
        pitch_g = get_val(fd, 'gyroADC[1]')
        yaw_g = get_val(fd, 'gyroADC[2]')
        data['roll_gyro'].append(roll_g)
        data['pitch_gyro'].append(pitch_g)
        data['yaw_gyro'].append(yaw_g)

        roll_s = get_val(fd, 'setpoint[0]')
        pitch_s = get_val(fd, 'setpoint[1]')
        yaw_s = get_val(fd, 'setpoint[2]')
        data['roll_setpoint'].append(roll_s)
        data['pitch_setpoint'].append(pitch_s)
        data['yaw_setpoint'].append(yaw_s)

        data['roll_p'].append(get_val(fd, 'axisP[0]'))
        data['pitch_p'].append(get_val(fd, 'axisP[1]'))
        data['yaw_p'].append(get_val(fd, 'axisP[2]'))

        data['roll_i'].append(get_val(fd, 'axisI[0]'))
        data['pitch_i'].append(get_val(fd, 'axisI[1]'))
        data['yaw_i'].append(get_val(fd, 'axisI[2]'))

        data['roll_d'].append(get_val(fd, 'axisD[0]'))
        data['pitch_d'].append(get_val(fd, 'axisD[1]'))
        data['yaw_d'].append(get_val(fd, 'axisD[2]'))

        data['roll_f'].append(get_val(fd, 'axisF[0]'))
        data['pitch_f'].append(get_val(fd, 'axisF[1]'))
        data['yaw_f'].append(get_val(fd, 'axisF[2]'))

        data['roll_error'].append(roll_s - roll_g)
        data['pitch_error'].append(pitch_s - pitch_g)
        data['yaw_error'].append(yaw_s - yaw_g)

        for i in range(4):
            raw = get_val(fd, f'motor[{i}]')
            data[f'motor_{i}'].append(raw / 2047.0 * 100.0 if raw > 0 else 0.0)

        data['attitude_roll'].append(roll_s)
        data['attitude_pitch'].append(pitch_s)

    time_arr = np.array(data['time'])
    if len(time_arr) > 0:
        if time_arr[-1] > 10000:
            time_arr = (time_arr - time_arr[0]) / 1_000_000.0
        else:
            time_arr = time_arr - time_arr[0]
        data['time'] = time_arr.tolist()

    return data