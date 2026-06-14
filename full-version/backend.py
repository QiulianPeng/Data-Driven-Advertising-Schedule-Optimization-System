# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, Response, send_file
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from collections import defaultdict
from pulp import LpProblem, LpVariable, lpSum, LpMaximize, LpBinary
import os
import sqlite3
from datetime import datetime
import time
import psutil
import functools


app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, '赛题数据(天)_组别211_渠道替换.xlsx')
DB_PATH = os.path.join(BASE_DIR, "ads.db")

# ---------------- 性能监控装饰器 ----------------

# 装饰器已经存在
def performance_monitoring(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        process = psutil.Process(os.getpid())
        mem_before = process.memory_info().rss / 1024**2  # MB
        t0 = time.time()
        result = func(*args, **kwargs)
        t1 = time.time()
        mem_after = process.memory_info().rss / 1024**2  # MB
        perf_info = {
            "time_s": round(t1-t0,2),
            "mem_before_MB": round(mem_before,1),
            "mem_after_MB": round(mem_after,1),
            "mem_increase_MB": round(mem_after-mem_before,1)
        }
        print(f"[PERFORMANCE] Function '{func.__name__}': {perf_info}")

        # 如果返回值是 Response 或其他类型，先把它转 dict
        if isinstance(result, Response):
            import json
            data = json.loads(result.get_data())
            data['performance'] = perf_info
            return jsonify(data)
        elif isinstance(result, dict):
            result['performance'] = perf_info
            return result
        else:
            return result
    return wrapper


# ---------------- 数据库初始化 ----------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # 原始广告数据表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS ads_data (
        活动 TEXT,
        活动第几天 INTEGER,
        渠道 TEXT,
        广告系列ID_h TEXT,
        广告组ID_h TEXT,
        业绩 REAL,
        订单 REAL,
        花费 REAL,
        曝光 REAL,
        点击 REAL
    )
    """)

    # 优化结果表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS plan_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        活动 TEXT,
        日期 TEXT,
        渠道 TEXT,
        广告系列ID TEXT,
        广告组ID TEXT,
        花费 REAL,
        曝光 REAL,
        点击 REAL,
        预测订单量 REAL,
        业绩 REAL,
        run_time TEXT
    )
    """)

    # 汇总结果表
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS summary_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        活动 TEXT,
        总投放天数 INTEGER,
        总花费 REAL,
        总曝光 REAL,
        总点击 REAL,
        总预测订单 REAL,
        总业绩 REAL,
        run_time TEXT
    )
    """)

    conn.commit()
    conn.close()

# ---------------- 保存结果到数据库 ----------------
def save_results(plan_df, summary_df):
    run_time = datetime.now().strftime("%Y%m%d_%H%M%S")  # 唯一标识每次优化
    plan_df = plan_df.copy()
    summary_df = summary_df.copy()

    plan_df["run_time"] = run_time
    summary_df["run_time"] = run_time

    conn = sqlite3.connect(DB_PATH)
    plan_df.to_sql("plan_results", conn, if_exists="append", index=False)
    summary_df.to_sql("summary_results", conn, if_exists="append", index=False)
    conn.close()

    return run_time  # 返回 run_time 供前端使用

# ---------------- 数据加载 ----------------
df = pd.read_excel(DATA_PATH)
df.columns = df.columns.str.strip()
num_cols = ['业绩', '订单', '花费', '曝光', '点击']
df[num_cols] = df[num_cols].replace([np.inf, -np.inf], np.nan).fillna(0.0)

# 初始化数据库并存入原始数据
init_db()
conn = sqlite3.connect(DB_PATH)
df.to_sql("ads_data", conn, if_exists="replace", index=False)
conn.close()

# ---------------- 模型训练 ----------------
train_features = ['渠道', '广告系列ID_h', '广告组ID_h', '花费', '曝光', '点击', '业绩','活动第几天']
target = '订单'

df[train_features] = df[train_features].astype('category')
X = df[train_features]
y = df[target].astype(float)
X_enc = pd.get_dummies(X, columns=['渠道', '广告系列ID_h', '广告组ID_h'], drop_first=False).astype(float)

rf = RandomForestRegressor(n_estimators=300, max_depth=None, random_state=42, n_jobs=-1)
rf.fit(X_enc, y)

# ---------------- MAB 参数 ----------------
alpha = defaultdict(lambda: 1.0)
beta = defaultdict(lambda: 1.0)

# ---------------- 前端 HTML ----------------
@app.route('/')
def index():
    with open(os.path.join(BASE_DIR, 'frontend.html'), 'r', encoding='utf-8') as f:
        html_content = f.read()
    return Response(html_content, mimetype='text/html')

# ---------------- 获取活动列表接口 ----------------
@app.route('/get_activities', methods=['GET'])
def get_activities():
    activities = df['活动'].unique().tolist()
    return jsonify(activities)

# ---------------- 优化接口 ----------------
@app.route('/optimize', methods=['POST'])
@performance_monitoring
def optimize():
    data = request.get_json()
    if not data:
        return jsonify([])

    holiday_dates = ['2026-12-20','2026-12-22','2026-12-24','2026-12-25']
    holiday_weight = 1.5
    TOTAL_BUDGET = 1_000_000
    month_dates = pd.date_range(start='2026-12-01', end='2026-12-31')

    temp_list = []
    for item in data:
        act = item['活动']
        max_days = int(item['天数'])
        temp = df[df['活动']==act].copy()
        temp['活动第几天'] = temp['活动第几天'].astype(int)
        temp = temp[temp['活动第几天'] <= max_days]
        temp_list.append(temp)
    if not temp_list:
        return jsonify([])

    filtered_data = pd.concat(temp_list, ignore_index=True).reset_index(drop=True)

    # LP 决策变量
    decision_vars = {}
    for i, row in filtered_data.iterrows():
        for date in month_dates:
            decision_vars[(i, date)] = LpVariable(f"x_{i}_{date.strftime('%Y%m%d')}", cat=LpBinary)

    prob = LpProblem("Ad_Optimization", LpMaximize)

    # 预测订单量
    features = filtered_data[['花费','曝光','点击','业绩','活动第几天','渠道','广告系列ID_h','广告组ID_h']]
    features_enc = pd.get_dummies(features, columns=['渠道','广告系列ID_h','广告组ID_h'], drop_first=False).astype(float)
    for col in X_enc.columns:
        if col not in features_enc.columns:
            features_enc[col] = 0.0
    features_enc = features_enc[X_enc.columns]
    predictions = rf.predict(features_enc)

    ts_noise = []
    for idx, row in filtered_data.iterrows():
        arm = (row['活动'], row['渠道'])
        theta = np.random.beta(alpha[arm], beta[arm])
        ts_noise.append((1-0.1) + theta*0.2)
    filtered_data['predicted_orders'] = predictions * np.array(ts_noise)

    # 目标函数
    prob += lpSum([decision_vars[(i,date)] * filtered_data.loc[i,'predicted_orders'] *
                   (holiday_weight if date.strftime('%Y-%m-%d') in holiday_dates else 1)
                   for i in filtered_data.index for date in month_dates])

    # ---------------- 约束：活动天数（每天多个渠道/广告组只算一天） ----------------
    day_vars = {}
    for item in data:
        act = item['活动']
        max_days = int(item['天数'])
        for date in month_dates:
            day_var = LpVariable(f"{act}_{date.strftime('%Y%m%d')}_day", cat=LpBinary)
            day_vars[(act, date)] = day_var

            # 如果当天至少有一个组合被选中 → day_var = 1
            prob += day_var <= lpSum([decision_vars[(idx, date)]
                                      for idx in filtered_data[filtered_data['活动'] == act].index])
            for idx in filtered_data[filtered_data['活动'] == act].index:
                prob += day_var >= decision_vars[(idx, date)]

        # 限制总投放天数（关键点：用 day_var 计数，而不是组合数）
        prob += lpSum([day_vars[(act, date)] for date in month_dates]) <= max_days

    # 预算约束
    filtered_data['花费_for_lp'] = pd.to_numeric(filtered_data['花费'], errors='coerce').fillna(100.0)
    prob += lpSum([decision_vars[(i,date)] * filtered_data.loc[i,'花费_for_lp']
                   for i in filtered_data.index for date in month_dates]) <= TOTAL_BUDGET

    prob.solve()

    # 结果
    plan_records = []
    for (i,date), var in decision_vars.items():
        if var.varValue > 0.5:
            row = filtered_data.loc[i]
            plan_records.append({
                '活动': row['活动'],
                '日期': date.strftime('%Y-%m-%d'),
                '渠道': row['渠道'],
                '广告系列ID': row['广告系列ID_h'],
                '广告组ID': row['广告组ID_h'],
                '花费': row['花费'],
                '曝光': row['曝光'],
                '点击': row['点击'],
                '业绩': row['业绩'],
                '预测订单量': row['predicted_orders']
            })
    plan_df = pd.DataFrame(plan_records)

    if plan_df.empty:
        return jsonify({'plan': [], 'summary': []})

    plan_df['日期'] = pd.to_datetime(plan_df['日期'])
    plan_df = plan_df.sort_values(by='日期')

    summary = plan_df.groupby('活动').agg(
        总投放天数=('日期', 'nunique'),
        总花费=('花费', 'sum'),
        总曝光=('曝光', 'sum'),
        总点击=('点击', 'sum'),
        总业绩=('业绩', 'sum'),
        总预测订单=('预测订单量', 'sum')
    ).reset_index()

    # 保存数据库（保证历史记录可查）
    run_time = save_results(plan_df, summary)

    return jsonify({
        'plan': plan_df.to_dict(orient='records'),
        'summary': summary.to_dict(orient='records'),
        'run_time': run_time
    })

# ---------------- 历史结果接口 ----------------
@app.route('/history', methods=['GET'])
def history():
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql("SELECT DISTINCT run_time FROM summary_results ORDER BY run_time DESC", conn)
    conn.close()
    return jsonify(df['run_time'].tolist())



@app.route('/history/<run_time>', methods=['GET'])
def history_detail(run_time):
    start_time = time.time()
    process = psutil.Process(os.getpid())
    mem_before = process.memory_info().rss / 1024**2  # MB

    conn = sqlite3.connect(DB_PATH)
    plan = pd.read_sql("SELECT * FROM plan_results WHERE run_time=?", conn, params=[run_time])
    summary = pd.read_sql("SELECT * FROM summary_results WHERE run_time=?", conn, params=[run_time])
    conn.close()

    mem_after = process.memory_info().rss / 1024**2  # MB
    time_s = round(time.time() - start_time, 2)
    mem_increase_MB = round(mem_after - mem_before, 2)

    return jsonify({
        "plan": plan.to_dict(orient="records"),
        "summary": summary.to_dict(orient="records"),
        "performance": {
            "time_s": time_s,
            "mem_increase_MB": mem_increase_MB
        }
    })
   



# ---------------- 导出结果接口 ----------------
@app.route('/export_result', methods=['GET'])
def export_result():
    run_time = request.args.get("run_time")
    conn = sqlite3.connect(DB_PATH)
    if run_time:
        plan = pd.read_sql("SELECT * FROM plan_results WHERE run_time=?", conn, params=[run_time])
        summary = pd.read_sql("SELECT * FROM summary_results WHERE run_time=?", conn, params=[run_time])
    else:
        df = pd.read_sql("SELECT DISTINCT run_time FROM summary_results ORDER BY run_time DESC LIMIT 1", conn)
        if df.empty:
            return jsonify({"message": "没有可导出的结果"}), 400
        run_time = df['run_time'].iloc[0]
        plan = pd.read_sql("SELECT * FROM plan_results WHERE run_time=?", conn, params=[run_time])
        summary = pd.read_sql("SELECT * FROM summary_results WHERE run_time=?", conn, params=[run_time])
    conn.close()

    out_file = os.path.join(BASE_DIR, f"优化结果_{run_time}.xlsx")
    with pd.ExcelWriter(out_file, engine="openpyxl") as writer:
        plan.to_excel(writer, index=False, sheet_name="计划明细")
        summary.to_excel(writer, index=False, sheet_name="汇总结果")
    return send_file(out_file, as_attachment=True)

if __name__ == '__main__':
    import os as _os
    port = int(_os.environ.get('PORT', 5050))
    app.run(debug=False, host='0.0.0.0', port=port)
