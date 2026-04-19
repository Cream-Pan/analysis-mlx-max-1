from flask import Flask, request, jsonify
from flask_cors import CORS
import pandas as pd
import numpy as np
import io, re
from sklearn.metrics import mean_squared_error, mean_absolute_error
import warnings

app = Flask(__name__)
CORS(app)
warnings.filterwarnings('ignore', category=UserWarning, module='pandas')
warnings.filterwarnings('ignore', category=FutureWarning, module='pandas')

# ----------------------------------------
# 汎用: 時刻 or 持続時間の柔軟パーサ
# ----------------------------------------
def parse_datetime_or_duration(value, base_day=None):
    """
    value: '2025/01/01 12:34:56.789' または '32:19.3' 等
    base_day: pandas.Timestamp (datetime)
    """
    s = str(value).strip()
    # 絶対時刻 (日付付き/なし)
    dt = pd.to_datetime(s, errors='coerce')
    if pd.notna(dt):
        return dt

    # Excelシリアル (日数)
    try:
        num = float(s)
        return pd.Timestamp('1899-12-30') + pd.to_timedelta(num, unit='D')
    except Exception:
        pass

    # 分:秒(.f) or 時:分:秒(.f)
    if re.match(r'^\d{1,3}:\d{2}(\.\d+)?$', s):
        td = pd.to_timedelta("0:" + s, errors='coerce')
    else:
        td = pd.to_timedelta(s, errors='coerce')

    if pd.notna(td):
        base_day = base_day or pd.Timestamp.today().normalize()
        return base_day + td

    raise ValueError(f"未知の時刻書式: {s}")


# ----------------------------------------
# MLX評価 (MAE/RMSE計算)
# ----------------------------------------
def perform_mlx_evaluation(files):
    required_files = {
        'log': 'log.csv',
        'body_temp': 'body_temperature.csv',
        'device': '3-Device_Measurement.xlsx'
    }
    uploaded = {f.filename: f for f in files}
    miss = [fname for fname in required_files.values() if fname not in uploaded]
    if miss:
        return {"analysis_type": "mlx_evaluation", "status": "error",
                "message": f"必要なファイルが不足しています: {', '.join(miss)}"}

    try:
        # --- log.csv 読込 ---
        log = pd.read_csv(io.BytesIO(uploaded['log.csv'].read()))
        uploaded['log.csv'].seek(0)
        if 'Task_Name' not in log.columns or 'Timestamp' not in log.columns:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "'log.csv' に必要な列がありません．"}

        sensor_start = log[log['Task_Name'] == 'BLE_START_TIME (Main)']
        if sensor_start.empty:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "'BLE_START_TIME (Main)' の行が見つかりません．"}

        # --- body_temperature.csv 読込 (基準日) ---
        df_true = pd.read_csv(io.BytesIO(uploaded['body_temperature.csv'].read()),
                              header=None, skiprows=1, usecols=[0, 1],
                              names=['body_temperature', 'sampling_time'])
        uploaded['body_temperature.csv'].seek(0)
        df_true['sampling_dt'] = pd.to_datetime(
            df_true['sampling_time'].str.replace('"', ''), errors='coerce')
        df_true['body_temperature'] = pd.to_numeric(df_true['body_temperature'], errors='coerce')
        df_true = df_true.dropna().set_index('sampling_dt')
        base_day = df_true.index.min().normalize() if not df_true.empty else pd.Timestamp.today().normalize()

        # --- 開始時刻 ---
        raw_t1 = sensor_start['Timestamp'].iloc[0]
        t1 = parse_datetime_or_duration(raw_t1, base_day)
        
        # --- タスク時刻 ---
        task_names = ['順応(５分)', '安静状態の測定(５分)','安静状態の測定(１０分)', 
                      '朗読(１分)', '準備(３０秒)', '4km/h（３分）',
                      '6km/h（３分）', 'トレッドミルへ移動・準備(２分)',
                      'トレッドミル歩行 4km/h(５分)', '安静状態の測定(１５分)', 'トレッドミル早歩き 6km/h(５分)',
                      '椅子へ移動・準備(３０秒)', '回復状態の測定(５分)', 
                      '安静状態の測定(１/１５分)', '安静状態の測定(２/１５分)', '安静状態の測定(３/１５分)', 
                      '安静状態の測定(４/１５分)', '安静状態の測定(５/１５分)', '安静状態の測定(６/１５分)', 
                      '安静状態の測定(７/１５分)', '安静状態の測定(８/１５分)', '安静状態の測定(９/１５分)', 
                      '安静状態の測定(１０/１５分)', '安静状態の測定(１１/１５分)', '安静状態の測定(１２/１５分)', 
                      '安静状態の測定(１３/１５分)', '安静状態の測定(１４/１５分)', '安静状態の測定(１５/１５分)',
                      '安静状態の測定(１/１０分)', '安静状態の測定(２/１０分)', '安静状態の測定(３/１０分)', 
                      '安静状態の測定(４/１０分)', '安静状態の測定(５/１０分)', '安静状態の測定(６/１０分)', 
                      '安静状態の測定(７/１０分)', '安静状態の測定(８/１０分)', '安静状態の測定(９/１０分)', 
                      '安静状態の測定(１０/１０分)',
                      '安静手で覆う(６分)', '安静(５分)', '安静(４分)','実験終了']
        tasks = log[log['Task_Name'].isin(task_names)].copy()
        tasks['Timestamp_dt'] = tasks['Timestamp'].apply(lambda x: parse_datetime_or_duration(x, base_day))
        tasks = tasks.dropna(subset=['Timestamp_dt']).sort_values('Timestamp_dt')
        if len(tasks) < 1:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "タスク境界が2つ未満です．"}

        # --- Excel (MLXデータ) 読込 ---
        device = uploaded['3-Device_Measurement.xlsx']
        xls = pd.ExcelFile(io.BytesIO(device.read()))
        device.seek(0)
        sheet = None
        if 'MLX_L mini' in xls.sheet_names:
            sheet = 'MLX_L mini'
        elif 'MLX_L' in xls.sheet_names:
            sheet = 'MLX_L'
        elif 'MLX_R mini' in xls.sheet_names:
            sheet = 'MLX_R mini'
        elif 'MLX_R' in xls.sheet_names:
            sheet = 'MLX_R'
            
        if sheet is None:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "MLXシート (L/R mini, L/R) が見つかりません．"}

        # F2セル (開始オフセット)
        f2 = pd.read_excel(io.BytesIO(device.read()), sheet_name=sheet,
                           header=None, skiprows=1, nrows=1, usecols="F")
        device.seek(0)
        raw_f2 = f2.iloc[0, 0]
        print(f"--- td 計算診断 ---")
        print(f"base_day: {base_day}")
        print(f"t1:       {t1}")
        print(f"raw_f2 の値: {raw_f2}")
        print(f"raw_f2 の型: {type(raw_f2)}")
        try:
            td = pd.to_timedelta(float(raw_f2), unit='s')
        except Exception:
            td = pd.to_timedelta("0s")
        time_1 = t1 + td
        print(f"time_1:   {time_1}")

        df_raw = pd.read_excel(io.BytesIO(device.read()), sheet_name=sheet)
        device.seek(0)
        ambient_col = df_raw.columns[0]  # A列 Ambient_C
        object_col  = df_raw.columns[1]  # B列 Object_C
        elapse_col = df_raw.columns[4]
        sensor_td = pd.to_timedelta(df_raw[elapse_col], unit='ms', errors='coerce')
        diff_td = sensor_td.diff().fillna(pd.Timedelta(seconds=0))
        df = pd.DataFrame({
            'Timestamp': time_1 + diff_td.cumsum(),
            'Ambient_C': pd.to_numeric(df_raw[ambient_col], errors='coerce'),
            'Object_C': pd.to_numeric(df_raw[object_col], errors='coerce'),
        }).dropna().set_index('Timestamp')
        print(f"--- MLXデータ (df) の先頭5行 ---")
        print(df.head())
        print(f"------------------------------------")

        if df.empty or df_true.empty:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "データが空です．"}

        # 補間と誤差計算
        pred = df.reindex(df_true.index.union(df.index)).interpolate('time').reindex(df_true.index)
        comp = pd.DataFrame({'true': df_true['body_temperature'],
                             'predicted': pred['Object_C']}).dropna()
        if comp.empty:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "補間後の有効データがありません．"}

        result = []
        for i in range(len(tasks) - 1):
            start_dt = tasks.iloc[i]['Timestamp_dt']
            end_dt = tasks.iloc[i + 1]['Timestamp_dt']
            task_name = tasks.iloc[i]['Task_Name']
            
            print(f"タスク: {task_name}")
            print(f"  開始時刻: {start_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
            print(f"  終了時刻: {end_dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

            seg = comp.loc[start_dt:end_dt]
            # センサ平均用の区間（Ambient_C / Object_C）
            seg_sensor = df.loc[start_dt:end_dt]
            seg_true = df_true.loc[start_dt:end_dt]
            if seg.empty or seg_sensor.empty or seg_true.empty:
                result.append({"task": task_name, 
                               "count": 0, 
                               "mae": None, 
                               "rmse": None,
                                "mean_object_c": None,
                                "mean_ambient_c": None,
                                "mean_body_temp": None
                                })
                continue
            mae = mean_absolute_error(seg['true'], seg['predicted'])
            rmse = np.sqrt(mean_squared_error(seg['true'], seg['predicted']))
            mean_object  = float(seg_sensor['Object_C'].mean())
            mean_ambient = float(seg_sensor['Ambient_C'].mean())
            mean_bodytemp = float(seg_true['body_temperature'].mean())

            result.append({
                "task": task_name,
                "count": len(seg),
                "mae": mae,
                "rmse": rmse,
                "mean_object_c": mean_object,
                "mean_ambient_c": mean_ambient,
                "mean_body_temp": mean_bodytemp
            })

        return {"analysis_type": "mlx_evaluation", "status": "success",
                "title": f"MLX評価 結果 ({sheet})", "data": result}

    except Exception as e:
        return {"analysis_type": "mlx_evaluation", "status": "error",
                "message": f"解析中に予期せずエラーが発生しました: {e}"}
    
def perform_mlx_reevaluation(files):
    required_files = {
        'log': 'log.csv',
        'body_temp': 'body_temperature.csv',
        'device': 'mlx_re.csv'
    }
    uploaded = {f.filename: f for f in files}
    miss = [fname for fname in required_files.values() if fname not in uploaded]
    if miss:
        return {"analysis_type": "mlx_evaluation", "status": "error",
                "message": f"必要なファイルが不足しています: {', '.join(miss)}"}

    try:
        # --- log.csv 読込 ---
        log = pd.read_csv(io.BytesIO(uploaded['log.csv'].read()))
        uploaded['log.csv'].seek(0)
        if 'Task_Name' not in log.columns or 'Timestamp' not in log.columns:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "'log.csv' に必要な列がありません．"}

        sensor_start = log[log['Task_Name'] == 'BLE_START_TIME (Main)']
        if sensor_start.empty:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "'BLE_START_TIME (Main)' の行が見つかりません．"}

        # --- body_temperature.csv 読込 (基準日) ---
        df_true = pd.read_csv(io.BytesIO(uploaded['body_temperature.csv'].read()),
                              header=None, skiprows=1, usecols=[0, 1],
                              names=['body_temperature', 'sampling_time'])
        uploaded['body_temperature.csv'].seek(0)
        df_true['sampling_dt'] = pd.to_datetime(
            df_true['sampling_time'].str.replace('"', ''), errors='coerce')
        df_true['body_temperature'] = pd.to_numeric(df_true['body_temperature'], errors='coerce')
        df_true = df_true.dropna().set_index('sampling_dt')
        base_day = df_true.index.min().normalize() if not df_true.empty else pd.Timestamp.today().normalize()

        # --- 開始時刻 ---
        raw_t1 = sensor_start['Timestamp'].iloc[0]
        t1 = parse_datetime_or_duration(raw_t1, base_day)
        
        # --- タスク時刻 ---
        task_names = ['順応(５分)', '安静状態の測定(５分)','安静状態の測定(１０分)', 
                      '朗読(１分)', '準備(３０秒)', '4km/h（３分）',
                      '6km/h（３分）', 'トレッドミルへ移動・準備(２分)',
                      'トレッドミル歩行 4km/h(５分)', '安静状態の測定(１５分)', 'トレッドミル早歩き 6km/h(５分)',
                      '椅子へ移動・準備(３０秒)', '回復状態の測定(５分)', 
                      '安静状態の測定(１/１５分)', '安静状態の測定(２/１５分)', '安静状態の測定(３/１５分)', 
                      '安静状態の測定(４/１５分)', '安静状態の測定(５/１５分)', '安静状態の測定(６/１５分)', 
                      '安静状態の測定(７/１５分)', '安静状態の測定(８/１５分)', '安静状態の測定(９/１５分)', 
                      '安静状態の測定(１０/１５分)', '安静状態の測定(１１/１５分)', '安静状態の測定(１２/１５分)', 
                      '安静状態の測定(１３/１５分)', '安静状態の測定(１４/１５分)', '安静状態の測定(１５/１５分)',
                      '安静状態の測定(１/１０分)', '安静状態の測定(２/１０分)', '安静状態の測定(３/１０分)', 
                      '安静状態の測定(４/１０分)', '安静状態の測定(５/１０分)', '安静状態の測定(６/１０分)', 
                      '安静状態の測定(７/１０分)', '安静状態の測定(８/１０分)', '安静状態の測定(９/１０分)', 
                      '安静状態の測定(１０/１０分)',
                      '安静手で覆う(６分)', '安静(５分)', '安静(４分)','実験終了']
        tasks = log[log['Task_Name'].isin(task_names)].copy()
        tasks['Timestamp_dt'] = tasks['Timestamp'].apply(lambda x: parse_datetime_or_duration(x, base_day))
        tasks = tasks.dropna(subset=['Timestamp_dt']).sort_values('Timestamp_dt')
        if len(tasks) < 1:
            return {"analysis_type": "mlx_evaluation", "status": "error",
                    "message": "タスク境界が2つ未満です．"}

        # --- CSV (MLXデータ) 読込 ---
        try:
            df_raw = pd.read_csv(io.BytesIO(uploaded['mlx_re.csv'].read()))
            uploaded['mlx_re.csv'].seek(0)
        except Exception as e:
            # Shift-JIS などでリトライ
            try:
                df_raw = pd.read_csv(io.BytesIO(uploaded['mlx_re.csv'].read()), encoding='shift_jis')
                uploaded['mlx_re.csv'].seek(0)
            except Exception as e2:
                return {"analysis_type": "mlx_reevaluation", "status": "error", "message": f"CSV読み込みエラー: {e2}"}

        # [変更点] 列の指定
        # A列(0): Ambient_C (そのまま利用)
        # I列(8): TO_Final_Corrected (Object_C の代わり)
        # E列(4): SensorElapsed_ms (時間計算用)
        # F列(5): MeasureElapsed_s (オフセット用, ExcelのF2相当) -> CSVではF列の1行目データ
        
        if len(df_raw.columns) < 9:
             return {"analysis_type": "mlx_reevaluation", "status": "error", "message": "mlx_re.csv の列数が不足しています (I列まで必要)．"}

        ambient_col = df_raw.columns[0] # A列
        elapse_col = df_raw.columns[4]  # E列
        offset_col = df_raw.columns[5]  # F列
        target_col = df_raw.columns[8]  # I列 (TO_Final_Corrected)

        if 'SensorElapsed_ms' not in str(elapse_col):
             return {"analysis_type": "mlx_reevaluation", "status": "error", "message": f"E列のヘッダーが 'SensorElapsed_ms' ではありません: {elapse_col}"}
        
        # F2相当の値 (F列の最初のデータ) を取得
        f2_val_td = pd.to_timedelta(df_raw[offset_col].iloc[0], unit='s', errors='coerce')
        if pd.isna(f2_val_td):
             return {"analysis_type": "mlx_reevaluation", "status": "error", "message": "F列の先頭データ (MeasureElapsed_s) が数値（秒）ではありません．"}
        
        time_1 = t1 + f2_val_td

        sensor_td = pd.to_timedelta(df_raw[elapse_col], unit='ms', errors='coerce')
        if sensor_td.isna().any():
             return {"analysis_type": "mlx_reevaluation", "status": "error", "message": "E列 (SensorElapsed_ms) に不正な値が含まれています．"}

        diff_td = sensor_td.diff().fillna(pd.Timedelta(seconds=0))
        
        # [変更点] Object_C として I列 (target_col) を使用
        df = pd.DataFrame({
            'Timestamp': time_1 + diff_td.cumsum(),
            'Ambient_C': pd.to_numeric(df_raw[ambient_col], errors='coerce'),
            'Object_C': pd.to_numeric(df_raw[target_col], errors='coerce') # ここが I列
        }).dropna(subset=['Timestamp']).set_index('Timestamp')

        if df.empty or df_true.empty:
            return {"analysis_type": "mlx_reevaluation", "status": "error", "message": "データが空です．"}

        # 補間と誤差計算
        pred = df.reindex(df_true.index.union(df.index)).interpolate('time').reindex(df_true.index)
        comp = pd.DataFrame({'true': df_true['body_temperature'], 'predicted': pred['Object_C']}).dropna()
        if comp.empty:
            return {"analysis_type": "mlx_reevaluation", "status": "error", "message": "補間後の有効データがありません．"}

        result = []
        for i in range(len(tasks) - 1):
            start_dt = tasks.iloc[i]['Timestamp_dt']
            end_dt = tasks.iloc[i + 1]['Timestamp_dt']
            task_name = tasks.iloc[i]['Task_Name']
            
            seg = comp.loc[start_dt:end_dt]
            seg_sensor = df.loc[start_dt:end_dt]
            seg_true = df_true.loc[start_dt:end_dt]
            
            if seg.empty or seg_sensor.empty or seg_true.empty:
                result.append({"task": task_name, "count": 0, "mae": None, "rmse": None, 
                               "mean_object_c": None, "mean_ambient_c": None, "mean_body_temp": None})
                continue
            
            mae = mean_absolute_error(seg['true'], seg['predicted'])
            rmse = np.sqrt(mean_squared_error(seg['true'], seg['predicted']))
            mean_object   = float(seg_sensor['Object_C'].mean())
            mean_ambient  = float(seg_sensor['Ambient_C'].mean())
            mean_bodytemp = float(seg_true['body_temperature'].mean())

            result.append({
                "task": task_name,
                "count": len(seg),
                "mae": mae if np.isfinite(mae) else None,
                "rmse": rmse if np.isfinite(rmse) else None,
                "mean_object_c": mean_object if np.isfinite(mean_object) else None,
                "mean_ambient_c": mean_ambient if np.isfinite(mean_ambient) else None,
                "mean_body_temp": mean_bodytemp if np.isfinite(mean_bodytemp) else None
            })

        return {"analysis_type": "mlx_reevaluation", "status": "success", "title": "MLX修正後評価 結果 (mlx_re.csv)", "data": result}

    except Exception as e:
        return {"analysis_type": "mlx_reevaluation", "status": "error", "message": f"解析中に予期せずエラーが発生しました: {e}"}

def evaluate_device(df_true, df_device, device_name, resample_minutes, start_time, end_time):
    """
    特定のデバイスデータを真値と比較して評価指標を計算し、辞書で返す
    """
    
    # この評価の結果を格納する辞書
    result_dict = {
        "device_name": device_name,
        "raw_mae": None, "raw_rmse": None, "raw_count": 0,
        "resampled_mae": None, "resampled_rmse": None, "resampled_count": 0,
        "error": None
    }

    if df_true.empty or df_device.empty:
        result_dict["error"] = "比較対象データが空のためスキップ"
        return result_dict

    try:
        interpolated_true = df_true.reindex(
            df_true.index.union(df_device.index)
        ).interpolate(method='time').reindex(df_device.index)
    except Exception as e:
        result_dict["error"] = f"時刻合わせ (補間) 中にエラー: {e}"
        return result_dict
        
    eval_columns = {'true_hr': interpolated_true['HeartRate_BPM']}
    # MAX (PPG_BPM) は 'HR_BPM' カラムのみを持つと仮定
    eval_columns['device_hr_bpm'] = df_device['HR_BPM']
    
    comparison_df_full = pd.DataFrame(eval_columns).dropna()

    if comparison_df_full.empty:
        result_dict["error"] = "時刻合わせの結果、比較できるデータなし"
        return result_dict

    comparison_df = comparison_df_full.loc[start_time:end_time]
    
    if comparison_df.empty:
        result_dict["error"] = f"タスク期間内に有効なデータなし"
        return result_dict
        
    result_dict["raw_count"] = len(comparison_df)
    
    # --- 元データでの評価 ---
    raw_mae = mean_absolute_error(comparison_df['true_hr'], comparison_df['device_hr_bpm'])
    raw_rmse = np.sqrt(mean_squared_error(comparison_df['true_hr'], comparison_df['device_hr_bpm']))
    result_dict["raw_mae"] = raw_mae if np.isfinite(raw_mae) else None
    result_dict["raw_rmse"] = raw_rmse if np.isfinite(raw_rmse) else None

    # --- 平均データでの評価 ---
    resample_freq = f'{resample_minutes}min'
    df_resampled_avg = comparison_df.resample(resample_freq, origin=start_time).mean().dropna()

    if len(df_resampled_avg) > 0:
        result_dict["resampled_count"] = len(df_resampled_avg)
        mae_resampled = mean_absolute_error(df_resampled_avg['true_hr'], df_resampled_avg['device_hr_bpm'])
        rmse_resampled = np.sqrt(mean_squared_error(df_resampled_avg['true_hr'], df_resampled_avg['device_hr_bpm']))
        result_dict["resampled_mae"] = mae_resampled if np.isfinite(mae_resampled) else None
        result_dict["resampled_rmse"] = rmse_resampled if np.isfinite(rmse_resampled) else None
    else:
        result_dict["error"] = (result_dict["error"] or "") + f" {resample_minutes}分平均データが1点以下"

    return result_dict

# --- MAX評価 (main) ---
def perform_max_evaluation(files):
    """
    MAX評価 (MAE/RMSE計算) のメイン処理 (テーブル形式で結果を返す)
    """
    
    # 1. 必要なファイルがアップロードされているか検証
    required_files = { 'ecg': 'ecg.csv', 'ppg_bpm': 'PPG_BPM.csv', 'ppg_fin': 'PPG_fin_BPM.csv', 'log': 'log.csv' }
    uploaded_files = {file.filename: file for file in files}
    missing_files = [fname for key, fname in required_files.items() if fname not in uploaded_files]
    if missing_files:
        return { "analysis_type": "max_evaluation", "status": "error", "message": f"必要なファイルが不足しています: {', '.join(missing_files)}" }

    try:
        resample_minutes = 1 # 1分平均

        # --- 1. データ読み込みと準備 ---
        try:
            df_true_raw = pd.read_csv(io.BytesIO(uploaded_files['ecg.csv'].read()), usecols=['Timestamp', 'HeartRate_BPM'])
            df_ppg_device_raw = pd.read_csv(io.BytesIO(uploaded_files['PPG_BPM.csv'].read()), usecols=['RecvJST', 'HR_BPM'])
            df_ppg_fin_raw = pd.read_csv(io.BytesIO(uploaded_files['PPG_fin_BPM.csv'].read()), usecols=['RecvJST', 'HR_BPM'])
            df_log_raw = pd.read_csv(io.BytesIO(uploaded_files['log.csv'].read()), usecols=['Task_Name', 'Timestamp'])
        except ValueError as e: 
             return {"analysis_type": "max_evaluation", "status": "error", "message": f"CSV列名エラー: {e}"}

        # --- 2. 真値データ (ECG) のクリーンアップと整形 ---
        df_true = df_true_raw.dropna(subset=['HeartRate_BPM']).copy()
        cleaned_timestamp = df_true['Timestamp'].str.replace('="', '').str.replace('"', '')
        df_true['Timestamp'] = pd.to_datetime(cleaned_timestamp, errors='coerce')
        df_true['HeartRate_BPM'] = pd.to_numeric(df_true['HeartRate_BPM'], errors='coerce')
        df_true.dropna(inplace=True)
        df_true.set_index('Timestamp', inplace=True)
        df_true.sort_index(inplace=True)
        df_true = df_true[~df_true.index.duplicated(keep='first')]

        # --- 3. デバイスデータ (PPG_BPM) のクリーンアップと整形 ---
        df_ppg_device = df_ppg_device_raw.copy()
        df_ppg_device['RecvJST'] = pd.to_datetime(df_ppg_device['RecvJST'], errors='coerce')
        df_ppg_device['HR_BPM'] = pd.to_numeric(df_ppg_device['HR_BPM'], errors='coerce')
        df_ppg_device.dropna(inplace=True)
        df_ppg_device.set_index('RecvJST', inplace=True)
        df_ppg_device.sort_index(inplace=True)
        df_ppg_device = df_ppg_device[~df_ppg_device.index.duplicated(keep='first')]

        # --- 4. デバイスデータ (PPG_fin_BPM) のクリーンアップと整形 ---
        df_ppg_fin = df_ppg_fin_raw.copy()
        df_ppg_fin['RecvJST'] = pd.to_datetime(df_ppg_fin['RecvJST'], errors='coerce')
        df_ppg_fin['HR_BPM'] = pd.to_numeric(df_ppg_fin['HR_BPM'], errors='coerce')
        df_ppg_fin.dropna(inplace=True)
        df_ppg_fin.set_index('RecvJST', inplace=True)
        df_ppg_fin.sort_index(inplace=True)
        df_ppg_fin = df_ppg_fin[~df_ppg_fin.index.duplicated(keep='first')]

        # --- 5. タスクログデータ (log.csv) のクリーンアップと整形 ---
        df_log = df_log_raw.copy()
        df_log['Timestamp'] = pd.to_datetime(df_log['Timestamp'].str.replace('"', ''), errors='coerce')
        df_log['Task_Name'] = df_log['Task_Name'].str.replace('"', '')
        df_log.dropna(inplace=True)
        df_log.sort_values('Timestamp', inplace=True)
        df_log = df_log[~df_log['Task_Name'].isin(['BLE_START_TIME (Main)', 'スタート'])]
        df_log.reset_index(drop=True, inplace=True)
        df_log['End_Timestamp'] = df_log['Timestamp'].shift(-1)
        df_log.dropna(subset=['End_Timestamp'], inplace=True)

        # print(f"--- タスク: {task_name} ---")
        # print(f"  開始時刻: {start_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
        # print(f"  終了時刻: {end_time.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")

        if df_log.empty:
            return {"analysis_type": "max_evaluation", "status": "error", "message": "評価対象となるタスク期間がlog.csvから見つかりませんでした．"}

        # --- 6. 評価の実行 (タスクごと) ---
        df_ppg_fin_for_eval = df_ppg_fin.rename(columns={'HR_BPM': 'HeartRate_BPM'})
        
        # フロントエンドに返す結果リスト
        results_list = []
        
        for index, row in df_log.iterrows():
            task_name = row['Task_Name']
            start_time = row['Timestamp']
            end_time = row['End_Timestamp']
            
            # 評価1: 真値 (ECG) vs PPG_BPM
            eval_1 = evaluate_device(df_true, df_ppg_device, "ECG vs PPG_BPM", resample_minutes, start_time, end_time)
            # 評価2: PPG_fin_BPM vs PPG_BPM
            eval_2 = evaluate_device(df_ppg_fin_for_eval, df_ppg_device, "PPG_fin vs PPG_BPM", resample_minutes, start_time, end_time)
            
            # タスクごとの結果をまとめる
            results_list.append({
                "task": task_name,
                "eval_1": eval_1, # "ECG vs PPG_BPM" の結果辞書
                "eval_2": eval_2  # "PPG_fin vs PPG_BPM" の結果辞書
            })

        # 正常終了
        return {
            "analysis_type": "max_evaluation",
            "status": "success",
            "title": "MAX評価 結果 (タスク別)",
            "data": results_list # 結果辞書のリスト
        }

    except Exception as e:
        return {
            "analysis_type": "max_evaluation",
            "status": "error",
            "message": f"解析中に予期せずエラーが発生しました: {e}"
        }

# ----------------------------------------
# ファイルプレビュー
# ----------------------------------------
def perform_file_preview(files):
    results = []
    for f in files:
        fn = f.filename
        try:
            if fn.endswith(('.xlsx', '.xls')):
                xls = pd.read_excel(io.BytesIO(f.read()), sheet_name=None, header=None)
                f.seek(0)
                results.append({
                    "filename": fn,
                    "type": "excel",
                    "sheets": [{"sheet_name": s, "data": df.head(5).astype(str).iloc[:, 0].tolist()} for s, df in xls.items()]
                })
            elif fn.endswith('.csv'):
                df = pd.read_csv(io.BytesIO(f.read()), header=None, nrows=5)
                f.seek(0)
                results.append({"filename": fn, "type": "csv",
                                "sheets": [{"sheet_name": None, "data": df.iloc[:, 0].astype(str).tolist()}]})
        except Exception as e:
            f.seek(0)
            results.append({"filename": fn, "type": "error",
                            "sheets": [{"sheet_name": None, "data": [f"エラー: {e}"]}]})
    return results


# ----------------------------------------
# Flask エンドポイント
# ----------------------------------------
@app.route('/upload', methods=['POST'])
def upload_files():
    analysis_types = request.form.getlist('analysis_types[]')
    files = request.files.getlist('files')
    if not files:
        return jsonify([{"analysis_type": "error", "status": "error", "message": "ファイルが選択されていません"}]), 400
    if not analysis_types:
        return jsonify([{"analysis_type": "error", "status": "error", "message": "解析タイプが選択されていません"}]), 400

    results = []
    for atype in analysis_types:
        if atype == 'mlx_evaluation':
            results.append(perform_mlx_evaluation(files))
        elif atype == 'max_evaluation':
            results.append(perform_max_evaluation(files))
        elif atype == 'show_files':
            results.append({"analysis_type": "show_files", "status": "success",
                            "data": perform_file_preview(files)})
        elif atype == 'mlx_reevaluation':
            results.append(perform_mlx_reevaluation(files))
        else:
            results.append({"analysis_type": atype, "status": "error", "message": "未対応の解析タイプです"})

    for file in files:
            file.seek(0)
    return jsonify(results)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
