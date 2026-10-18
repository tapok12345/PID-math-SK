import numpy as np

def calculate_metrics(data: dict) -> dict:
    metrics = {}
    
    roll_err = np.abs(np.array(data['roll_error']))
    metrics['Средняя |ошибка| (Roll)'] = f"{np.mean(roll_err):.2f} град/с"
    metrics['Макс |ошибка| (Roll)'] = f"{np.max(roll_err):.2f} град/с"
    
    p_term = np.abs(np.array(data['roll_p']))
    metrics['Средний |P-терм|'] = f"{np.mean(p_term):.2f}"
    metrics['Макс |P-терм|'] = f"{np.max(p_term):.2f}"
    
    i_term = np.abs(np.array(data['roll_i']))
    metrics['Средний |I-терм|'] = f"{np.mean(i_term):.2f}"
    metrics['Макс |I-терм|'] = f"{np.max(i_term):.2f}"
    
    d_term = np.abs(np.array(data['roll_d']))
    metrics['Средний |D-терм|'] = f"{np.mean(d_term):.2f}"
    metrics['Макс |D-терм|'] = f"{np.max(d_term):.2f}"
    
    return metrics