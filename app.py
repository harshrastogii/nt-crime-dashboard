"""
NT Crime Intelligence Dashboard (Plotly Dash)
Light government-report theme | decision-led layout | Carto tile map.

    python prepare_data.py     # once -> crime_clean.parquet
    python app.py              # http://127.0.0.1:8050
"""
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
import json, os
import pandas as pd

df = pd.read_parquet("crime_clean.parquet")

# What the data was built from (written by prepare_data.py). The dashboard
# states this on screen so its figures can be traced to the Kaggle release.
SRC = {}
if os.path.isfile("dashboard_source.json"):
    with open("dashboard_source.json") as _fh:
        SRC = json.load(_fh)

FULL_MONTHS = ["January","February","March","April","May","June","July",
               "August","September","October","November","December"]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]
CURRENT_ERA = "Current / SerPro"

# Months are handled as one integer index (year*12 + month-1) so a period is a
# simple range, whatever years it spans.
df["ym"] = df["Year"].astype(int) * 12 + df["Month number"].astype(int) - 1
FIRST, LAST = int(df["ym"].min()), int(df["ym"].max())
# First month recorded under SerPro (December 2023). Taken from the dataset's
# own Data era tag, so the dashboard follows the dataset if it ever changes.
CUT = int(df.loc[df["Data era"] == CURRENT_ERA, "ym"].min())
YEARS = sorted(int(y) for y in df["Year"].unique())

def ym_label(i, full=False):
    return f"{(FULL_MONTHS if full else MONTHS)[i % 12]} {i // 12}"

def window_months(lo, hi, months=None):
    """Every month index in the selected period, after the month filter."""
    return [m for m in range(lo, hi + 1) if not months or m % 12 + 1 in months]

def span(ms):
    """Short label for a set of month numbers, e.g. 'Jan\u2013Aug'."""
    if len(ms) == 12: return "full year"
    if ms == list(range(ms[0], ms[-1] + 1)):
        return MONTHS[ms[0]-1] if len(ms) == 1 else f"{MONTHS[ms[0]-1]}\u2013{MONTHS[ms[-1]-1]}"
    return ", ".join(MONTHS[m-1] for m in ms)

def compare_window(lo, hi, months=None):
    """Like-for-like year-on-year window: the latest year in the selection,
    using only the months of it that are selected, against the same months of
    the year before. Partial years (e.g. a January-August 2026) therefore
    compare fairly. Returns (y0, y1, month numbers, crosses_break) or None."""
    wm = window_months(lo, hi, months)
    if not wm: return None
    y1 = wm[-1] // 12
    ms = sorted(m % 12 + 1 for m in wm if m // 12 == y1)
    prev = [(y1 - 1) * 12 + m - 1 for m in ms]
    if any(p < lo for p in prev): return None
    both = prev + [y1 * 12 + m - 1 for m in ms]
    crosses = min(both) < CUT <= max(both)
    return y1 - 1, y1, ms, crosses

def _period_note():
    note = (f"The series runs {ym_label(FIRST, True)} to {ym_label(LAST, True)} "
            f"({LAST - FIRST + 1} months). NT Police changed recording systems between "
            f"{ym_label(CUT - 1, True)} and {ym_label(CUT, True)} (PROMIS to SerPro), and the NT Government "
            "advises against comparing the two periods directly. The trend chart marks the change, its "
            "12-month average restarts after it, and any comparison that spans it is labelled indicative. "
            f"{ym_label(CUT - 1, True)}, the cutover month, is provisional. ")
    for y in YEARS:
        ms = sorted(int(m) for m in df.loc[df["Year"] == y, "Month number"].unique())
        if len(ms) < 12:
            note += (f"{y} is a partial year ({FULL_MONTHS[ms[0]-1]}\u2013{FULL_MONTHS[ms[-1]-1]}); "
                     "year-on-year figures compare the same months of each year. ")
    return note

def _source_note():
    if not SRC:
        return "Data source details unavailable for this build."
    first = pd.Period(SRC["dashboard_first"], freq="M").strftime("%B %Y")
    last = pd.Period(SRC["dashboard_last"], freq="M").strftime("%B %Y")
    ver = f" (version {SRC['kaggle_version']})" if SRC.get("kaggle_version") else ""
    how = ("verified byte-for-byte against the published release"
           if SRC.get("verified_against_release") else "not verified against a release")
    origin = ("Kaggle dataset " if SRC["source"] == "Kaggle"
              else f"{SRC['source']}, mirroring Kaggle dataset ")
    return (f"Data: {origin}{SRC['dataset']}{ver}, {first} to {last}, {how}. "
            f"{SRC['dashboard_offences']:,} offences. Built {SRC['built_at']}.")

CRIME_TYPES = sorted(df["Crime Type"].unique())
LOC_TYPES = ["Urban", "Regional", "Remote"]
MONTH_OPTS = [{"label":m,"value":i+1} for i,m in enumerate(MONTHS)]

INK="#1f2733"; MUTE="#6b7480"; LINE="#e6e9ee"; PAGE="#f4f6f8"; SURFACE="#ffffff"
ACCENT="#0d6e7d"; GOOD="#1d8a5f"; BAD="#c0392b"; AMBER="#c39b3a"
SEQ=["#0d6e7d","#3f8a96","#6aa6af","#9ec9cd","#c39b3a","#e0bd6a","#9a5b3f","#8794a0","#b0392b","#cdd2d8"]

pio.templates["nt"]=go.layout.Template(layout=dict(
    font=dict(family="Inter, system-ui, sans-serif", color=INK, size=13),
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=SEQ,
    title=dict(font=dict(size=15, color=INK), x=0.02, xanchor="left", y=0.96),
    xaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(color=MUTE), title_font=dict(color=MUTE, size=12)),
    yaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(color=MUTE), title_font=dict(color=MUTE, size=12)),
    legend=dict(font=dict(color=MUTE, size=11), bgcolor="rgba(0,0,0,0)"),
))
T="nt"

app=dash.Dash(__name__, title="Territory Crime Atlas",
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"])
server=app.server

# Use the custom PNG favicon from the assets/ folder
app.index_string = '''<!DOCTYPE html>
<html>
<head>
{%metas%}
<title>{%title%}</title>
<link rel="icon" type="image/png" href="/assets/favicon.png">
{%favicon%}
{%css%}
</head>
<body>
{%app_entry%}
<footer>{%config%}{%scripts%}{%renderer%}</footer>
</body>
</html>'''


CARD={"backgroundColor":SURFACE,"borderRadius":"14px","padding":"4px 8px 10px",
      "border":f"1px solid {LINE}","boxShadow":"0 1px 3px rgba(16,24,40,0.05)"}
LBL={"fontSize":"11px","fontWeight":600,"color":MUTE,"textTransform":"uppercase",
     "letterSpacing":"0.05em","marginBottom":"5px","display":"block"}

def g(gid): return html.Div(dcc.Graph(id=gid, config={"displayModeBar":False}), style=CARD)

# Force the map's tile attribution to render small, grey and in-corner regardless
# of how the browser sizes it. The credit stays visible (a Carto/OSM licence
# requirement) but no longer dominates the card.
app.index_string = """
<!DOCTYPE html>
<html>
<head>{%metas%}<title>{%title%}</title>{%favicon%}{%css%}
<style>
  .maplibregl-ctrl-attrib, .mapboxgl-ctrl-attrib,
  .maplibregl-ctrl-attrib-inner, .mapboxgl-ctrl-attrib-inner {
    font-size: 9px !important;
    line-height: 12px !important;
    color: #9aa0aa !important;
    background: rgba(255,255,255,0.6) !important;
    padding: 0 4px !important;
  }
  .maplibregl-ctrl-attrib a, .mapboxgl-ctrl-attrib a { color: #9aa0aa !important; }
  .maplibregl-ctrl-bottom-right { bottom: 2px !important; right: 2px !important; }
  /* Hide the little collapse/expand toggle arrow the map library adds. */
  .maplibregl-ctrl-attrib-button, .mapboxgl-ctrl-attrib-button { display: none !important; }
  /* Keep the credit text visible without the toggle. */
  .maplibregl-ctrl-attrib.maplibregl-compact, .mapboxgl-ctrl-attrib.mapboxgl-compact {
    min-height: auto !important; padding: 0 4px !important;
  }
  .maplibregl-ctrl-attrib.maplibregl-compact-show .maplibregl-ctrl-attrib-inner,
  .maplibregl-ctrl-attrib-inner { display: block !important; }
</style>
</head>
<body>{%app_entry%}<footer>{%config%}{%scripts%}{%renderer%}</footer></body>
</html>
"""

BTN={"border":f"1px solid {LINE}","backgroundColor":SURFACE,"color":INK,"borderRadius":"8px",
     "padding":"5px 10px","fontSize":"12.5px","cursor":"pointer","fontFamily":"inherit"}
MARKS={y*12:{"label":str(y),"style":{"color":MUTE,"fontSize":"11px"}} for y in YEARS if y%2==0 or y==YEARS[-1]}
# Quick presets for the period slider: the whole series, or one recording era.
PRESETS={"p-all":[FIRST,LAST],"p-old":[FIRST,CUT-1],"p-new":[CUT,LAST]}
# Dash 4 adds number boxes beside the slider; they would show raw month indexes,
# and the period is already spelled out above the slider.
SLIDER_OPTS=({"allow_direct_input":False}
             if "allow_direct_input" in dcc.RangeSlider().available_properties else {})

app.layout=html.Div(className="tca-page", style={"backgroundColor":PAGE,"color":INK,"minHeight":"100vh",
    "fontFamily":"Inter, system-ui, sans-serif","padding":"28px 34px","maxWidth":"1480px","margin":"0 auto"}, children=[
    html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"flex-end",
        "borderBottom":f"2px solid {ACCENT}","paddingBottom":"14px","marginBottom":"22px"}, children=[
        html.Div([html.Div(style={"display":"flex","alignItems":"center","gap":"12px"}, children=[
            html.Div(style={"width":"6px","height":"32px","backgroundColor":ACCENT,"borderRadius":"3px"}),
            html.H1("Territory Crime Atlas", style={"fontWeight":700,"fontSize":"26px","margin":0})]),
            html.P(f"Recorded offences, {ym_label(FIRST,True)} – {ym_label(LAST,True)}  |  Source: NT Police, NTG Open Data Portal",
                style={"color":MUTE,"margin":"6px 0 0 18px","fontSize":"13px"})]),
        html.Div("Built with Python + Dash", style={"fontSize":"12px","color":MUTE})]),

    html.Div(style={**CARD,"padding":"16px","marginBottom":"22px"}, children=[
        html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"center",
            "flexWrap":"wrap","gap":"8px","marginBottom":"6px"}, children=[
            html.Div([html.Span("Period", style={**LBL,"display":"inline","marginRight":"8px"}),
                html.Span(id="period-label", style={"fontSize":"14px","fontWeight":600})]),
            html.Div(style={"display":"flex","gap":"8px","flexWrap":"wrap"}, children=[
                html.Button(f"Whole series {YEARS[0]}–{YEARS[-1]}", id="p-all", style=BTN),
                html.Button(f"Before the change (to {ym_label(CUT-1)})", id="p-old", style=BTN),
                html.Button(f"After the change ({ym_label(CUT)} on)", id="p-new", style=BTN)])]),
        dcc.RangeSlider(id="f-period",min=FIRST,max=LAST,step=1,value=[FIRST,LAST],
            marks=MARKS,allowCross=False,updatemode="mouseup",**SLIDER_OPTS),
        html.Div(style={"display":"flex","gap":"22px","flexWrap":"wrap","alignItems":"flex-end","marginTop":"14px"}, children=[
        html.Div([html.Label("Location type", style=LBL), dcc.Dropdown(LOC_TYPES,[],multi=True,
            id="f-loc",placeholder="All locations",style={"minWidth":"170px"})]),
        html.Div([html.Label("Crime type", style=LBL), dcc.Dropdown(CRIME_TYPES,[],multi=True,
            id="f-crime",placeholder="All crime types",style={"minWidth":"210px"})]),
        html.Div([html.Label("Month", style=LBL), dcc.Dropdown(MONTH_OPTS,[],multi=True,
            id="f-month",placeholder="All months",style={"minWidth":"170px"})]),
        html.Div([html.Label("Region ranking shows", style=LBL), dcc.RadioItems(id="f-mode",value="rate",
            inline=True,options=[{"label":" Per 1,000 residents","value":"rate"},{"label":" Raw count","value":"raw"}],
            labelStyle={"marginRight":"16px","color":INK,"fontSize":"14px","cursor":"pointer"},
            inputStyle={"marginRight":"6px","accentColor":ACCENT})])])]),

    html.Div(id="kpis", className="tca-grid-4", style={"display":"grid","gridTemplateColumns":"repeat(4,1fr)","gap":"16px","marginBottom":"16px"}),

    html.Div(id="insight", style={"backgroundColor":"#eef5f6","border":f"1px solid #cfe3e6",
        "borderLeft":f"4px solid {ACCENT}","borderRadius":"12px","padding":"16px 20px",
        "marginBottom":"22px","fontSize":"14px","lineHeight":1.65,"color":INK}),

    html.Div(style={"marginBottom":"20px"}, children=[g("g-trend")]),
    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-rank"), g("g-map")]),
    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-yoy"), g("g-alcdv")]),
    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-season"), g("g-comp")]),

    html.Div(style={"padding":"14px 16px","backgroundColor":"#fbf7ec","border":"1px solid #ecdfbf",
        "borderRadius":"12px","fontSize":"12.5px","color":"#7a6a2f","lineHeight":1.6}, children=[
        html.Strong("Notes:  "),
        _period_note(),
        "Crime types use the dataset's nine harmonised labels, which cover both recording eras; the "
        "government's detailed offence classifications differ either side of the change. Before the change, "
        "“alcohol involvement unknown” was recoded to “No”, so alcohol shares are not comparable across it. "
        "Per-1,000 rates are annualised and use 2021 census populations for every period, so they are indicative, "
        "more so the further a period is from 2021; small-population regions (e.g. Tennant Creek) have volatile rates. "
        "Koolpinyah and offences with no stated location have no map coordinates, so they are left off the map. "
        "Selecting individual months produces small samples, especially for low-population areas, so rates and trends for single months should be read with caution.",
        html.Div(_source_note(), id="data-source",
                 style={"marginTop":"8px","color":"#8a7b45","fontSize":"11.5px"})])])

@app.callback(Output("f-period","value"),
    Input("p-all","n_clicks"),Input("p-old","n_clicks"),Input("p-new","n_clicks"),prevent_initial_call=True)
def preset(*_):
    return PRESETS[dash.ctx.triggered_id]

def fdf(period,locs,crimes,months=None):
    lo,hi=period
    d=df[(df["ym"]>=lo)&(df["ym"]<=hi)]
    if locs: d=d[d["Location Type"].isin(locs)]
    if crimes: d=d[d["Crime Type"].isin(crimes)]
    if months: d=d[d["Month number"].isin(months)]
    return d

def kpi(label,value,sub=None,color=INK):
    return html.Div(style={"backgroundColor":SURFACE,"borderRadius":"14px","padding":"16px 18px",
        "border":f"1px solid {LINE}","boxShadow":"0 1px 3px rgba(16,24,40,0.05)"}, children=[
        html.Div(label, style={"fontSize":"11px","fontWeight":600,"color":MUTE,"textTransform":"uppercase","letterSpacing":"0.05em"}),
        html.Div(value, style={"fontSize":"28px","fontWeight":700,"color":color,"marginTop":"4px"}),
        html.Div(sub or "", style={"fontSize":"12px","color":MUTE,"marginTop":"2px"})])

def empty(title, msg, height=380):
    fig=go.Figure()
    fig.add_annotation(text=msg,showarrow=False,font=dict(color=MUTE,size=13),xref="paper",yref="paper",x=0.5,y=0.5)
    fig.update_layout(template=T,title=title,height=height,xaxis=dict(visible=False),yaxis=dict(visible=False),
        margin=dict(l=20,r=20,t=54,b=20))
    return fig

@app.callback(
    Output("period-label","children"),
    Output("kpis","children"),Output("insight","children"),Output("g-trend","figure"),Output("g-rank","figure"),Output("g-map","figure"),
    Output("g-yoy","figure"),Output("g-alcdv","figure"),Output("g-season","figure"),Output("g-comp","figure"),
    Input("f-period","value"),Input("f-loc","value"),Input("f-crime","value"),Input("f-mode","value"),Input("f-month","value"))
def update(period,locs,crimes,mode,months):
    lo,hi=period
    crosses_sel=lo<CUT<=hi
    nsel=len(window_months(lo,hi,months))
    plabel=(f"{ym_label(lo)} – {ym_label(hi)}  ·  {nsel} month{'s' if nsel!=1 else ''}"
            +(f"  ·  spans the {ym_label(CUT-1)} recording change" if crosses_sel else ""))
    d=fdf(period,locs,crimes,months)
    nmon=max(len(window_months(lo,hi,months)),1)
    total=d["Number of offences"].sum()
    alc=d[d["Alcohol involvement"]=="Yes"]["Number of offences"].sum()
    dv=d[d["DV involvement"]=="Yes"]["Number of offences"].sum()

    # Like-for-like year-on-year window (same months of consecutive years).
    cw=compare_window(lo,hi,months)
    if cw:
        Y0,Y1,cms,crosses=cw
        cmp_lbl=("" if len(cms)==12 else f"{span(cms)} ")+f"{Y0} → {Y1}"
        a=d[(d["Year"]==Y0)&d["Month number"].isin(cms)]; b=d[(d["Year"]==Y1)&d["Month number"].isin(cms)]
        s0,s1=a["Number of offences"].sum(),b["Number of offences"].sum()
    else:
        Y0=Y1=None; crosses=False; s0=s1=0
    if cw and s0:
        yoy=(s1-s0)/s0*100
        ytxt=f"▼ {abs(yoy):.0f}%" if yoy<0 else f"▲ {yoy:.0f}%"
        ycol=MUTE if crosses else (GOOD if yoy<0 else BAD)
        ysub=cmp_lbl+(" · indicative, spans the change" if crosses else "")
    elif cw: ytxt,ycol,ysub="—",MUTE,f"no offences in {Y0} to compare with"
    else: ytxt,ycol,ysub="—",MUTE,"needs the same months of the year before"

    gg=d.groupby("Location").agg(off=("Number of offences","sum"),pop=("Population","first"),
        lat=("lat","first"),lon=("lon","first"))
    gg=gg[gg.index!="Unknown / not stated"]
    # Annualised so the rate means the same thing for one month or eighteen years.
    gg["rate"]=gg["off"]/gg["pop"]*1000*12/nmon
    gg_rate=gg.dropna(subset=["pop"])  # only locations with verified population
    if mode=="rate":
        src=gg_rate; val="rate"
    else:
        src=gg; val="off"
    top_region=src.sort_values(val,ascending=False).index[0] if len(src) else "—"

    # ---- dynamic plain-English insight for decision-makers ----
    ins=[]
    if cw and s0:
        ins.append(html.Span([html.B("Overall, "),
            f"recorded offences {'fell' if yoy<0 else 'rose'} "
            f"{abs(yoy):.0f}% from {Y0} to {Y1}"
            +(f" ({span(cms)})" if len(cms)<12 else "")+" in this selection"
            +(", although that comparison spans the change in police recording systems, so treat it as indicative. "
              if crosses else ". ")]))
    if len(gg) and len(gg_rate):
        hi_vol=gg['off'].idxmax()
        hi_rate=gg_rate['rate'].idxmax()
        ratio=gg_rate['rate'].max()/gg_rate['rate'].min() if gg_rate['rate'].min()>0 else 0
        ins.append(html.Span([
            "By volume the largest count is in ",html.B(hi_vol),
            f", but per resident ",html.B(hi_rate),
            f" is the most affected community — about {ratio:.0f}× the rate of the least affected. "
            "Resourcing by raw counts alone would under-serve smaller remote communities. "]))
    if crosses_sel:
        ins.append(html.Span([
            "This period includes both sides of the ",html.B(f"{ym_label(CUT-1,True)} change"),
            " from PROMIS to SerPro; use the period buttons above to look at one recording system at a time."]))
    insight=ins or "No offences match this selection."

    kpis=[kpi("Total offences",f"{total:,.0f}",f"{ym_label(lo)} – {ym_label(hi)}"),
        kpi("Year-on-year change",ytxt,ysub,ycol),
        kpi("Highest "+("rate" if mode=="rate" else "volume"),top_region,
            "per 1,000 residents a year" if mode=="rate" else "total offences"),
        kpi("Alcohol / DV share",f"{alc/total*100:.0f}% / {dv/total*100:.0f}%" if total else "—",
            f"{alc:,.0f} / {dv:,.0f} offences")]

    # (0) monthly trend across the whole selected period. The 12-month average
    # is computed separately on each side of the recording-system change so it
    # never blends PROMIS and SerPro months.
    wm=window_months(lo,hi,months)
    ser=d.groupby("ym")["Number of offences"].sum().reindex(wm,fill_value=0)
    xs=[pd.Timestamp(year=m//12,month=m%12+1,day=1) for m in ser.index]
    fig_trend=go.Figure()
    fig_trend.add_scatter(x=xs,y=ser.values,mode="lines" if not months else "markers",name="Monthly offences",
        line=dict(width=1.3,color="#9ec9cd"),marker=dict(size=5,color="#6aa6af"),
        hovertemplate="%{x|%b %Y}: %{y:,.0f} offences<extra></extra>")
    if not months:
        first_avg=True
        for part in (ser[ser.index<CUT],ser[ser.index>=CUT]):
            if len(part)>=12:
                roll=part.rolling(12).mean()
                fig_trend.add_scatter(x=[xs[wm.index(m)] for m in part.index],y=roll.values,mode="lines",
                    name="12-month average",showlegend=first_avg,legendgroup="avg",line=dict(width=2.6,color=ACCENT),
                    hovertemplate="%{x|%b %Y}: %{y:,.0f} (12-month average)<extra></extra>")
                first_avg=False
    if CUT-1 in ser.index:
        fig_trend.add_scatter(x=[xs[wm.index(CUT-1)]],y=[ser[CUT-1]],mode="markers",name="Provisional (cutover month)",
            marker=dict(size=9,color=AMBER,line=dict(width=1,color=SURFACE)),
            hovertemplate=f"{ym_label(CUT-1)}: %{{y:,.0f}} offences · provisional cutover month<extra></extra>")
    if crosses_sel:
        brk=pd.Timestamp(year=CUT//12,month=CUT%12+1,day=1)-pd.Timedelta(days=15)
        fig_trend.add_shape(type="rect",xref="x",yref="paper",x0=brk,x1=xs[-1]+pd.Timedelta(days=15),y0=0,y1=1,
            fillcolor="#eef5f6",line_width=0,layer="below")
        fig_trend.add_shape(type="line",xref="x",yref="paper",x0=brk,x1=brk,y0=0,y1=1,
            line=dict(color=MUTE,width=1.2,dash="dash"))
        fig_trend.add_annotation(x=brk,y=1,xref="x",yref="paper",xanchor="right",yanchor="top",showarrow=False,
            text="PROMIS ← | → SerPro  ", font=dict(size=11,color=MUTE))
    fig_trend.update_layout(template=T,
        title=f"Monthly offences · recording system changed after {ym_label(CUT-1)}, so compare each side separately",
        height=340,margin=dict(l=58,r=20,t=54,b=40),yaxis_title="Offences",hovermode="x unified",
        legend=dict(orientation="h",y=1.02,x=1,xanchor="right",yanchor="bottom"))

    # (1) ranking — generous left margin, label headroom
    gr=src.sort_values(val).tail(12)
    rank_ttl=("Where crime hits hardest · per 1,000 residents a year" if mode=="rate"
         else "Where crime is highest · total offences")
    if len(gr):
        x=gr[val]; text=[f"{v:,.0f}" for v in x]
        cols=[BAD if r==top_region else ACCENT for r in gr.index]
        fig_rank=go.Figure(go.Bar(x=x,y=gr.index,orientation="h",marker_color=cols,
            text=text,textposition="outside",cliponaxis=False,textfont=dict(size=12)))
        fig_rank.update_layout(template=T,title=rank_ttl,height=380,
            margin=dict(l=120,r=70,t=54,b=34),
            xaxis=dict(title=None,range=[0,x.max()*1.18]),yaxis=dict(title=None))
    else:
        fig_rank=empty(rank_ttl,"No offences match this selection")

    # (2) MAP — Carto tiles. Bubble = volume; colour = per-1,000 rate where a
    # verified population exists, grey where it doesn't (honest about coverage).
    md=gg.dropna(subset=["lat","lon"]).copy()
    md_rate=md.dropna(subset=["pop"])
    md_norate=md[md["pop"].isna()]
    fig_map=go.Figure()
    if len(md_norate):
        fig_map.add_scattermap(lat=md_norate["lat"],lon=md_norate["lon"],
            text=md_norate.index,mode="markers",
            marker=dict(size=(md_norate["off"]/gg["off"].max()*38+8),color="#b8c0c8"),
            name="count only (no rate)",
            hovertemplate="<b>%{text}</b><br>%{customdata:,.0f} offences<br>rate n/a<extra></extra>",
            customdata=md_norate["off"])
    if len(md_rate):
        fig_map.add_scattermap(lat=md_rate["lat"],lon=md_rate["lon"],
            text=md_rate.index,mode="markers",
            marker=dict(size=(md_rate["off"]/gg["off"].max()*38+8),
                color=md_rate["rate"],colorscale=[[0,"#bcdce0"],[0.5,"#3f8a96"],[1,"#0d4d57"]],
                showscale=True,colorbar=dict(title="per 1,000<br>a year",thickness=12,len=0.7),
                cmin=0,cmax=md_rate["rate"].max()),
            name="rate available",
            hovertemplate="<b>%{text}</b><br>%{customdata[0]:,.0f} offences<br>%{customdata[1]:,.0f} per 1,000 a year<extra></extra>",
            customdata=md_rate[["off","rate"]].values)
    fig_map.update_layout(map_style="carto-positron",map_zoom=4.0,
        map_center=dict(lat=-19.2,lon=133.4),
        title="Crime intensity across the Territory",
        height=380,margin=dict(l=8,r=8,t=54,b=8),showlegend=False)

    # (3) YoY — same like-for-like window as the KPI
    yoy_ttl="Year-on-year change by region"+(" · indicative, spans the change" if crosses else "")
    piv=pd.DataFrame()
    if cw:
        w=d[d["Month number"].isin(cms)&d["Year"].isin([Y0,Y1])]
        piv=w.groupby(["Location","Year"])["Number of offences"].sum().unstack()
    if cw and {Y0,Y1}.issubset(piv.columns):
        piv=piv.dropna(subset=[Y0,Y1]); piv=piv[piv.index!="Unknown / not stated"]
        piv["y"]=(piv[Y1]-piv[Y0])/piv[Y0]*100; piv=piv.sort_values("y")
        rng=max(abs(piv["y"].min()),abs(piv["y"].max()),1)*1.25
        fig_yoy=go.Figure(go.Bar(x=piv["y"],y=piv.index,orientation="h",
            marker_color=[MUTE if crosses else GOOD if v<0 else BAD for v in piv["y"]],
            text=[f"{v:+.0f}%" for v in piv["y"]],textposition="outside",cliponaxis=False))
        fig_yoy.update_xaxes(range=[-rng,rng])
        fig_yoy.update_layout(template=T,title=yoy_ttl,height=380,
            margin=dict(l=120,r=50,t=54,b=46),xaxis_title=f"% change, {cmp_lbl}",yaxis_title=None)
    else:
        fig_yoy=empty(yoy_ttl,"Needs the same months of the year before in the period")

    # (4) alcohol & DV
    inv=d.groupby("Location").apply(lambda x:pd.Series({
        "Alcohol":x[x["Alcohol involvement"]=="Yes"]["Number of offences"].sum(),
        "DV":x[x["DV involvement"]=="Yes"]["Number of offences"].sum()}),
        include_groups=False)
    fig_alc=go.Figure()
    if len(inv):
        inv=inv[inv.index!="Unknown / not stated"].sort_values("DV",ascending=False).reset_index()
        fig_alc.add_bar(x=inv["Location"],y=inv["Alcohol"],name="Alcohol-related",marker_color=AMBER)
        fig_alc.add_bar(x=inv["Location"],y=inv["DV"],name="DV-related",marker_color=ACCENT)
    fig_alc.update_layout(template=T,barmode="group",title="Alcohol & DV-related offences by region",
        height=380,margin=dict(l=58,r=20,t=54,b=80),yaxis_title="Offences",
        legend=dict(orientation="h",y=1.02,x=1,xanchor="right"))

    # (5) seasonality — per region, indexed to each region's mean (pattern, not
    # volume). Each calendar month is averaged over the years it appears in, so
    # a partial year does not inflate the months it covers.
    sea=(d.groupby(["Year","Month number","Location"])["Number of offences"].sum()
          .groupby(["Month number","Location"]).mean().unstack())
    keep=[r for r in ["Darwin","Alice Springs","Katherine","Palmerston"] if r in sea.columns]
    fig_sea=go.Figure()
    pal={"Darwin":ACCENT,"Alice Springs":BAD,"Katherine":AMBER,"Palmerston":"#6aa6af"}
    for r in keep:
        idx=sea[r]/sea[r].mean()*100
        fig_sea.add_scatter(x=[MONTHS[int(m)-1] for m in idx.index],y=idx.values,mode="lines+markers",name=r,
            line=dict(width=2.2,color=pal.get(r,MUTE)),marker=dict(size=5))
    fig_sea.add_hline(y=100,line_dash="dot",line_color=LINE)
    fig_sea.update_layout(template=T,title="Seasonality · monthly offences vs each region's average",
        height=380,margin=dict(l=58,r=20,t=54,b=40),
        yaxis_title="index (100 = average month)",
        legend=dict(orientation="h",y=-0.18,font=dict(size=10)))

    # (6) composition — % share (regional fingerprint), not raw
    comp=d.groupby(["Location","Crime Type"])["Number of offences"].sum().unstack(fill_value=0)
    comp=comp[comp.index!="Unknown / not stated"]
    comp=comp.loc[comp.sum(axis=1).sort_values(ascending=False).index]
    pct=comp.div(comp.sum(axis=1),axis=0)*100
    fig_comp=go.Figure()
    for i,ct in enumerate(comp.columns):
        fig_comp.add_bar(x=pct.index,y=pct[ct],name=ct,marker_color=SEQ[i%len(SEQ)])
    fig_comp.update_layout(template=T,barmode="stack",
        title="Crime mix by region · share of each region's offences  (hover a segment for the category)",
        height=460,margin=dict(l=50,r=20,t=54,b=130),yaxis_title="% of region's offences",
        yaxis=dict(ticksuffix="%"),
        xaxis=dict(tickangle=-90,automargin=True),
        showlegend=False)
    fig_comp.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.0f}%%<extra></extra>")

    return plabel,kpis,insight,fig_trend,fig_rank,fig_map,fig_yoy,fig_alc,fig_sea,fig_comp

if __name__=="__main__":
    app.run(debug=True)
