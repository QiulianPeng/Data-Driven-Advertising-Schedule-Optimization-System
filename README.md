# Data-Driven Advertising Schedule Optimization System

> 数据驱动的广告排期优化系统 — 基于机器学习与运筹优化的12月广告投放决策系统

A data-driven advertising schedule optimization system that uses **Random Forest** machine learning and **Linear Programming (PuLP)** to optimize ad placements across multiple channels for a December campaign.

---

## 🚀 Live Demo

The lightweight version is ready for Cloudflare Pages deployment.

> Open the page, select activities and set max days, click "提交求解" to see the optimized schedule with interactive Chart.js visualizations.

---

## 📁 Project Structure

```
├── full-version/                # Full Flask application (ML + LP optimization)
│   ├── backend.py               # Flask API with RandomForest + PuLP optimization
│   ├── frontend.html            # Web UI (connects to Flask backend)
│   └── requirements.txt         # Python dependencies
├── lightweight-version/         # Cloudflare-deployable standalone version
│   └── index.html               # Self-contained HTML (no backend needed)
├── notebooks/                   # Jupyter analysis notebooks
│   ├── A-2.ipynb                # Data exploration & feature analysis
│   └── A-3.ipynb                # Model training & optimization experiments
├── results/                     # Optimization output samples
└── README.md
```

---

## ✨ Features

### Full Version (Flask Backend)

| Feature | Description |
|---------|-------------|
| **ML Prediction** | Random Forest Regressor (300 trees) predicts order volume per ad placement |
| **LP Optimization** | PuLP-based integer linear programming maximizes total predicted orders |
| **Multi-Armed Bandit** | Beta-distribution Thompson Sampling for exploration-exploitation balance |
| **Holiday Weighting** | Special dates (Christmas, Winter Solstice, etc.) get 1.5x weight |
| **Budget Constraint** | Global budget cap (default: 1,000,000) enforced across all activities |
| **Day Constraint** | Per-activity max-day limits with day-level grouping |
| **History DB** | SQLite stores all optimization runs for comparison and export |
| **Performance Monitoring** | Time & memory tracking per API call |

### Lightweight Version (Static HTML)

| Feature | Description |
|---------|-------------|
| **Zero Dependencies** | Single HTML file, runs entirely in browser |
| **Simulated Data** | Generates realistic ad placement data client-side |
| **12 KPI Metrics** | Orders, Spend, Clicks, Impressions, Revenue, ROI, CTR, CPC, CPA, CPM, CVR |
| **Interactive Charts** | Chart.js line charts with activity-level breakdowns |
| **History Management** | Save/load multiple optimization runs in browser memory |
| **CSV Export** | Download results as CSV for further analysis |
| **Performance Timer** | Client-side execution time & memory measurement |

---

## 🔧 Tech Stack

### Full Version

- **Backend**: Python 3.9+, Flask
- **ML**: scikit-learn (RandomForestRegressor)
- **Optimization**: PuLP (CBC solver)
- **Database**: SQLite3
- **Data**: pandas, numpy, openpyxl

### Lightweight Version

- Pure HTML5 + CSS3 + Vanilla JavaScript
- Chart.js (CDN) for visualizations
- No build tools, no dependencies

---

## 🏃 How to Run

### Prerequisites

- Python 3.9+
- Git

### 1. Clone the Repository

```bash
git clone https://github.com/QiulianPeng/Data-Driven-Advertising-Schedule-Optimization-System.git
cd Data-Driven-Advertising-Schedule-Optimization-System
```

### 2. Run Full Version (Flask Backend)

```bash
cd full-version
pip install -r requirements.txt
python backend.py
# Open http://localhost:5050 in your browser
```

> **Note**: The full version requires the Excel data file in the same directory as backend.py.

### 3. Run Lightweight Version

```bash
# Just open the file in any browser!
open lightweight-version/index.html
```

Or deploy to Cloudflare Pages:

```bash
npx wrangler pages deploy lightweight-version/
```

---

## 📊 Optimization Model

### Objective Function

Maximize total predicted orders across all activities, with holiday weighting applied to special dates.

### Constraints

1. **Day limit**: Each activity <= max days (using day-level binary variables)
2. **Budget**: Total spend <= 1,000,000

---

## 📈 Key Metrics

| Metric | Formula |
|--------|---------|
| **ROI** | (Revenue - Spend) / Spend |
| **CTR** | Clicks / Impressions |
| **CPC** | Spend / Clicks |
| **CPA** | Spend / Predicted Orders |
| **CPM** | Spend / (Impressions / 1000) |
| **CVR** | Predicted Orders / Clicks |

---

## 📄 License

MIT License - see [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Qiulian Peng**

- GitHub: [@QiulianPeng](https://github.com/QiulianPeng)
