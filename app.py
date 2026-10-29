from pathlib import Path
import json, os, sqlite3
from flask import Flask, render_template, request, redirect
from dotenv import load_dotenv
import pandas as pd
import plotly.express as px
import plotly.io as pio

ROOT=Path(__file__).resolve().parent
load_dotenv(ROOT/'.env')
app=Flask(__name__)
app.secret_key=os.getenv('FLASK_SECRET_KEY','dev-key-change-before-deploy')
DB_PATH=Path(os.getenv('DATABASE_PATH',str(ROOT/'data'/'ev_market.db')))
if not DB_PATH.is_absolute(): DB_PATH=ROOT/DB_PATH
OUT=ROOT/'outputs'
DASHBOARD_URL=os.getenv('TABLEAU_DASHBOARD_URL','').strip()
STORY_URL=os.getenv('TABLEAU_STORY_URL','').strip()

def get_kpis():
    p=OUT/'data_quality_report.json'
    if p.exists(): return json.loads(p.read_text())
    if DB_PATH.exists():
        with sqlite3.connect(DB_PATH) as con:
            row=con.execute('SELECT COUNT(*),COUNT(DISTINCT manufacturer),COUNT(DISTINCT category),AVG(customer_rating),AVG(range_km),AVG(battery_capacity_kwh),SUM(annual_sales_units) FROM ev_market').fetchone()
        return dict(cleaned_rows=row[0],unique_manufacturers=row[1],unique_categories=row[2],avg_customer_rating=row[3],avg_range_km=row[4],avg_battery_capacity_kwh=row[5],total_annual_sales_units=row[6])
    return {}

def read_agg(name):
    p=OUT/f'{name}.csv'
    return pd.read_csv(p) if p.exists() else pd.DataFrame()

def chart_html(name, df, kind, x, y, title, color=None):
    if df.empty: return '<div class="empty">Run <code>python src/build_data.py</code> to generate charts.</div>'
    if kind=='bar': fig=px.bar(df,x=x,y=y,color=color,title=title,template='plotly_dark')
    elif kind=='line': fig=px.line(df,x=x,y=y,markers=True,title=title,template='plotly_dark')
    elif kind=='pie': fig=px.pie(df,names=x,values=y,title=title,hole=.42,template='plotly_dark')
    elif kind=='scatter': fig=px.scatter(df,x=x,y=y,color=color,title=title,template='plotly_dark')
    else: return ''
    fig.update_layout(margin=dict(l=20,r=20,t=55,b=25),paper_bgcolor='rgba(0,0,0,0)',plot_bgcolor='rgba(0,0,0,0)',font=dict(color='#e8edf5'),legend_title_text='')
    return pio.to_html(fig,full_html=False,include_plotlyjs='cdn',config={'displayModeBar':False,'responsive':True})

@app.route('/')
def home():
    k=get_kpis()
    charts=[
      ('Category comparison','category_performance','bar','category','model_count','Vehicle records by EV category',None),
      ('Manufacturer portfolios','manufacturer_performance','bar','manufacturer','model_count','Top manufacturers by vehicle records',None),
      ('Battery mix','battery_mix','pie','battery_type','model_count','Battery technology distribution',None),
      ('Model-year profile','sales_by_year','line','model_year','model_records','Vehicle records by model year',None),
      ('Manufacturing footprint','country_footprint','bar','manufacturing_country','model_count','Vehicle records by manufacturing country',None),
      ('Price vs range','price_range_by_category','scatter','avg_price_usd','avg_range_km','Average price vs driving range','category'),
    ]
    built=[]
    for title,file,kind,x,y,chart_title,color in charts:
        df=read_agg(file)
        if file=='manufacturer_performance': df=df.head(12)
        built.append({'title':title,'html':chart_html(file,df,kind,x,y,chart_title,color)})
    return render_template('index.html',k=k,charts=built,dashboard_url=DASHBOARD_URL,story_url=STORY_URL)

@app.route('/dashboard')
def dashboard():
    if DASHBOARD_URL:
        return redirect(DASHBOARD_URL)
    return render_template('tableau.html',page_title='Interactive Tableau Dashboard',embed_url=DASHBOARD_URL,kind='dashboard')

@app.route('/story')
def story():
    return render_template('tableau.html',page_title='EV Market Data Story',embed_url=STORY_URL,kind='story')

@app.route('/about')
def about():
    k=get_kpis(); return render_template('about.html',k=k)

@app.route('/health')
def health():
    return {'status':'ok','database_exists':DB_PATH.exists(),'database_path':str(DB_PATH),'tableau_dashboard_configured':bool(DASHBOARD_URL),'tableau_story_configured':bool(STORY_URL)}

if __name__=='__main__':
    app.run(host='127.0.0.1',port=int(os.getenv('PORT','5000')),debug=False)
