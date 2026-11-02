"""
NT Crime Intelligence Dashboard (Plotly Dash)
Light government-report theme | decision-led layout | Carto tile map.

    python prepare_data.py     # once -> crime_clean.parquet
    python app.py              # http://127.0.0.1:8050
"""
import dash
from dash import dcc, html, Input, Output
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
ACCENT="#0d6e7d"; GOOD="#1d8a5f"; BAD="#c0392b"
# Data colours. ACCENT stays the brand colour for chrome; series use a set
# checked for colour-blind separation, chroma and contrast on white. They are
# assigned to fixed entities, so a filter never repaints the survivors.
S1="#008c9e"; S2="#eb6834"; S3="#6250d6"; S4="#c98500"
SOFT="#c9d6d9"          # de-emphasised marks when one location is in focus
ERA_FILL="#eef5f6"      # background of the SerPro period on time charts
SEQ_SCALE=[[0,"#f1f8f9"],[0.35,"#9fd0d6"],[0.7,"#2f9aa8"],[1,"#0d4d57"]]
TOWN_COLOURS={"Darwin":S1,"Alice Springs":S2,"Katherine":S3,"Palmerston":S4}
TRANSITION=dict(duration=450,easing="cubic-in-out")
UNKNOWN="Unknown / not stated"
LOCATIONS=sorted(l for l in df["Location"].unique() if l!=UNKNOWN)

pio.templates["nt"]=go.layout.Template(layout=dict(
    font=dict(family="Inter, system-ui, sans-serif", color=INK, size=13),
    paper_bgcolor=SURFACE, plot_bgcolor=SURFACE, colorway=[S1,S2,S3,S4],
    xaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(color=MUTE), title_font=dict(color=MUTE, size=12)),
    yaxis=dict(gridcolor=LINE, zerolinecolor=LINE, linecolor=LINE, tickfont=dict(color=MUTE), title_font=dict(color=MUTE, size=12)),
    legend=dict(font=dict(color=MUTE, size=11), bgcolor="rgba(0,0,0,0)"),
    hoverlabel=dict(bgcolor=SURFACE, bordercolor=LINE, font=dict(color=INK, size=12)),
))
T="nt"

app=dash.Dash(__name__, title="Territory Crime Atlas",
    external_stylesheets=["https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"])
server=app.server

# The custom PNG favicon from assets/. Styling and motion live in
# assets/style.css and assets/motion.js, which Dash loads automatically.
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

LBL={"fontSize":"11px","fontWeight":600,"color":MUTE,"textTransform":"uppercase",
     "letterSpacing":"0.05em","marginBottom":"5px","display":"block"}
GRID2={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}

def icon(name, size=18):
    return html.Img(src=app.get_asset_url(f"icons/{name}.svg"), alt="",
                    style={"width":f"{size}px","height":f"{size}px","flexShrink":0})

def card(gid, title, sub, clickable=False, extra=None):
    """A chart card with a plain-English heading. `title` may be a string or
    an id (prefixed 'h-') the callback fills in."""
    return html.Div(className="tca-card"+(" tca-clickable" if clickable else ""),
        style={"padding":"16px 14px 8px"}, children=[
        html.Div(style={"padding":"0 6px"}, children=[
            html.H3(title, id=f"h-{gid}", style={"fontSize":"15.5px","fontWeight":600,"margin":0}),
            html.P(sub, style={"color":MUTE,"fontSize":"12.5px","margin":"3px 0 0","lineHeight":1.5}),
            *(extra or [])]),
        dcc.Graph(id=gid, config={"displayModeBar":False})])

def chip(text, fill, border=LINE):
    return html.Span([html.Span(style={"display":"inline-block","width":"10px","height":"10px",
        "borderRadius":"3px","backgroundColor":fill,"border":f"1px solid {border}","marginRight":"6px",
        "verticalAlign":"-1px"}), text], style={"fontSize":"12px","color":MUTE,"marginRight":"14px"})

def step(n, ic, title, text):
    return html.Div(className="tca-card", style={"padding":"14px 16px","display":"flex","gap":"12px",
        "alignItems":"flex-start"}, children=[
        html.Div(icon(ic,20), style={"backgroundColor":"#e3f0f2","borderRadius":"10px","padding":"8px",
            "display":"flex"}),
        html.Div([html.Div(f"{n}. {title}", style={"fontWeight":600,"fontSize":"14px"}),
                  html.Div(text, style={"color":MUTE,"fontSize":"12.5px","marginTop":"2px","lineHeight":1.5})])])

MARKS={y*12:{"label":str(y),"style":{"color":MUTE,"fontSize":"11px"}} for y in YEARS if y%2==0 or y==YEARS[-1]}
# Quick presets for the period slider: the whole series, or one recording era.
PRESETS={"p-all":[FIRST,LAST],"p-old":[FIRST,CUT-1],"p-new":[CUT,LAST]}
# Dash 4 adds number boxes beside the slider; they would show raw month indexes,
# and the period is already spelled out above the slider.
SLIDER_OPTS=({"allow_direct_input":False}
             if "allow_direct_input" in dcc.RangeSlider().available_properties else {})

app.layout=html.Div(className="tca-page", style={"backgroundColor":PAGE,"color":INK,"minHeight":"100vh",
    "fontFamily":"Inter, system-ui, sans-serif","padding":"28px 34px","maxWidth":"1480px","margin":"0 auto"}, children=[
    html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"center","gap":"20px",
        "borderBottom":f"2px solid {ACCENT}","paddingBottom":"14px","marginBottom":"18px"}, children=[
        html.Div([html.Div(style={"display":"flex","alignItems":"center","gap":"12px"}, children=[
            html.Div(style={"width":"6px","height":"32px","backgroundColor":ACCENT,"borderRadius":"3px"}),
            html.H1("Territory Crime Atlas", style={"fontWeight":700,"fontSize":"26px","margin":0})]),
            html.P(f"Recorded offences in the Northern Territory, {ym_label(FIRST,True)} – {ym_label(LAST,True)}  |  Source: NT Police, NTG Open Data Portal",
                style={"color":MUTE,"margin":"6px 0 0 18px","fontSize":"13px"}),
            html.P("Where crime is concentrated, how it has changed since 2008, and what drives it, in one page.",
                style={"color":INK,"margin":"10px 0 0 18px","fontSize":"14.5px","maxWidth":"640px","lineHeight":1.5})]),
        html.Img(src=app.get_asset_url("nt-map.svg"), className="tca-hero-map",
                 alt="Map of the Northern Territory", style={"height":"140px","flexShrink":0})]),

    html.Div(className="tca-steps", style={"display":"grid","gridTemplateColumns":"repeat(3,1fr)","gap":"14px",
        "marginBottom":"18px"}, children=[
        step(1,"calendar","Choose a period","Drag the slider, or jump to before or after the November 2023 recording change."),
        step(2,"pointer","Click any place","Click a bar, bubble or heatmap row to focus the whole page on that location."),
        step(3,"play","Press play","Replay every year since 2008 and watch the rankings shift.")]),

    html.Div(className="tca-card tca-controls", style={"padding":"16px","marginBottom":"18px"}, children=[
        html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"center",
            "flexWrap":"wrap","gap":"8px","marginBottom":"6px"}, children=[
            html.Div([html.Span("Period", style={**LBL,"display":"inline","marginRight":"8px"}),
                html.Span(id="period-label", style={"fontSize":"14px","fontWeight":600})]),
            html.Div(style={"display":"flex","gap":"8px","flexWrap":"wrap"}, children=[
                html.Button(f"Whole series {YEARS[0]}–{YEARS[-1]}", id="p-all", className="tca-btn"),
                html.Button(f"Before the change (to {ym_label(CUT-1)})", id="p-old", className="tca-btn"),
                html.Button(f"After the change ({ym_label(CUT)} on)", id="p-new", className="tca-btn")])]),
        dcc.RangeSlider(id="f-period",min=FIRST,max=LAST,step=1,value=[FIRST,LAST],
            marks=MARKS,allowCross=False,updatemode="mouseup",**SLIDER_OPTS),
        html.Div(style={"display":"flex","gap":"18px","flexWrap":"wrap","alignItems":"flex-end","marginTop":"14px"}, children=[
            html.Div([html.Label("Focus on a location", style=LBL), dcc.Dropdown(LOCATIONS,None,
                id="f-focus",placeholder="Whole Territory",style={"minWidth":"200px"})]),
            html.Div([html.Label("Location type", style=LBL), dcc.Dropdown(LOC_TYPES,[],multi=True,
                id="f-loc",placeholder="All locations",style={"minWidth":"160px"})]),
            html.Div([html.Label("Crime type", style=LBL), dcc.Dropdown(CRIME_TYPES,[],multi=True,
                id="f-crime",placeholder="All crime types",style={"minWidth":"200px"})]),
            html.Div([html.Label("Month", style=LBL), dcc.Dropdown(MONTH_OPTS,[],multi=True,
                id="f-month",placeholder="All months",style={"minWidth":"150px"})]),
            html.Div([html.Label("Rank places by", style=LBL), dcc.RadioItems(id="f-mode",value="rate",
                inline=True,options=[{"label":" Per 1,000 residents","value":"rate"},{"label":" Raw count","value":"raw"}],
                labelStyle={"marginRight":"14px","color":INK,"fontSize":"14px","cursor":"pointer"},
                inputStyle={"marginRight":"6px","accentColor":ACCENT})]),
            html.Div(style={"display":"flex","gap":"8px","marginLeft":"auto"}, children=[
                html.Button([icon("reset",14),"Reset"], id="reset", className="tca-btn"),
                html.Button([icon("download",14),"Download data"], id="dl-btn", className="tca-btn"),
                dcc.Download(id="dl")])])]),

    html.Div(id="focus-banner", children=html.Button(id="focus-clear", style={"display":"none"})),

    html.Div(id="kpis", className="tca-grid-4", style={"display":"grid","gridTemplateColumns":"repeat(4,1fr)","gap":"16px","marginBottom":"16px"}),

    html.Div(className="tca-card", style={"backgroundColor":"#eef5f6","border":"1px solid #cfe3e6",
        "borderLeft":f"4px solid {ACCENT}","padding":"14px 20px","marginBottom":"20px","display":"flex","gap":"14px"}, children=[
        icon("bulb",22),
        html.Div([html.Div("Key takeaways", style={"fontWeight":600,"fontSize":"14px","marginBottom":"4px"}),
                  html.Ul(id="insight", style={"margin":0,"paddingLeft":"18px","fontSize":"14px","lineHeight":1.65})])]),

    html.Div(style={"marginBottom":"20px"}, children=[card("g-trend","How crime has moved, month by month",
        "Each point is one month. The darker line is the 12-month average, which smooths out the seasons.",
        extra=[html.Div(style={"marginTop":"8px"}, children=[
            chip(f"PROMIS system · {ym_label(FIRST)}–{ym_label(CUT-1)}", SURFACE),
            chip(f"SerPro system · {ym_label(CUT)} on", ERA_FILL, "#cfe3e6"),
            chip(f"{ym_label(CUT-1)} · provisional cutover month", S4, S4)])])]),
    html.Div(className="tca-grid-2", style=GRID2, children=[
        card("g-rank","Where crime hits hardest","Click a bar to focus on that place.",clickable=True),
        card("g-map","Crime across the Territory",
             "Bubble size is the number of offences; colour is the rate per 1,000 residents a year. Grey means no reliable population.",
             clickable=True)]),
    html.Div(className="tca-grid-2", style=GRID2, children=[
        card("g-replay","Replay the years","Press play to watch each place's rate change year by year. Bars keep their positions so you can follow one place.",clickable=True),
        card("g-yoy","Year-on-year change by place","Green fell, red rose, comparing the same months of the latest two years.",clickable=True)]),
    html.Div(className="tca-grid-2", style=GRID2, children=[
        card("g-season","Which months are busiest","100 is an average month. Above 100 is busier than usual."),
        card("g-alcdv","Alcohol and domestic violence","Offences where alcohol or domestic violence was involved, by place.",clickable=True)]),
    html.Div(style={"marginBottom":"20px"}, children=[card("g-mix","Each place's crime fingerprint",
        "Share of each place's offences by type. Darker cells are a bigger share. Places are ordered by total offences; click a row to focus.",
        clickable=True)]),

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

# ---- control callbacks ------------------------------------------------------

@app.callback(Output("f-period","value"),
    Input("p-all","n_clicks"),Input("p-old","n_clicks"),Input("p-new","n_clicks"),Input("reset","n_clicks"),
    prevent_initial_call=True)
def preset(*_):
    return PRESETS.get(dash.ctx.triggered_id, [FIRST,LAST])

@app.callback(Output("f-loc","value"),Output("f-crime","value"),Output("f-month","value"),Output("f-mode","value"),
    Input("reset","n_clicks"),prevent_initial_call=True)
def reset(_):
    return [],[],[],"rate"

CLICK_SOURCES={"g-rank":"y","g-map":"text","g-replay":"y","g-yoy":"y","g-alcdv":"x","g-mix":"y"}

@app.callback(Output("f-focus","value"),
    *[Input(gid,"clickData") for gid in CLICK_SOURCES],Input("reset","n_clicks"),Input("focus-clear","n_clicks"),
    dash.State("f-focus","value"),prevent_initial_call=True)
def click_focus(*args):
    """Clicking a place in any chart focuses the page on it; clicking the
    focused place again, or the clear button, returns to the whole Territory."""
    current=args[-1]; src=dash.ctx.triggered_id
    if src not in CLICK_SOURCES: return None
    data=dash.ctx.triggered[0]["value"]
    if not data or not data.get("points"): return current
    loc=data["points"][0].get(CLICK_SOURCES[src])
    if loc not in LOCATIONS: return current
    return None if loc==current else loc

@app.callback(Output("dl","data"),Input("dl-btn","n_clicks"),
    dash.State("f-period","value"),dash.State("f-loc","value"),dash.State("f-crime","value"),
    dash.State("f-month","value"),dash.State("f-focus","value"),prevent_initial_call=True)
def download(_,period,locs,crimes,months,focus):
    d=fdf(period,locs,crimes,months)
    if focus: d=d[d["Location"]==focus]
    cols=["Date","Year","Month number","Data era","Location","Location Type","Crime Type",
          "Alcohol involvement","DV involvement"]
    out=d.groupby(cols,as_index=False)["Number of offences"].sum()
    name=f"nt-crime_{ym_label(period[0]).replace(' ','-')}_to_{ym_label(period[1]).replace(' ','-')}"
    return dcc.send_data_frame(out.to_csv,(name+(f"_{focus}" if focus else "")).replace(" ","-")+".csv",index=False)

def fdf(period,locs,crimes,months=None):
    lo,hi=period
    d=df[(df["ym"]>=lo)&(df["ym"]<=hi)]
    if locs: d=d[d["Location Type"].isin(locs)]
    if crimes: d=d[d["Crime Type"].isin(crimes)]
    if months: d=d[d["Month number"].isin(months)]
    return d

def kpi(ic,label,value,sub=None,color=INK):
    return html.Div(className="tca-card tca-kpi", style={"padding":"16px 18px"}, children=[
        html.Div(style={"display":"flex","alignItems":"center","gap":"8px"}, children=[
            icon(ic,16),
            html.Div(label, style={"fontSize":"11px","fontWeight":600,"color":MUTE,"textTransform":"uppercase","letterSpacing":"0.05em"})]),
        html.Div(value, className="kpi-value", style={"fontSize":"28px","fontWeight":700,"color":color,"marginTop":"6px"}),
        html.Div(sub or "", style={"fontSize":"12px","color":MUTE,"marginTop":"2px"})])

def empty(msg, height=380):
    fig=go.Figure()
    fig.add_annotation(text=msg,showarrow=False,font=dict(color=MUTE,size=13),xref="paper",yref="paper",x=0.5,y=0.5)
    fig.update_layout(template=T,height=height,xaxis=dict(visible=False),yaxis=dict(visible=False),
        margin=dict(l=20,r=20,t=10,b=20))
    return fig

def emph(names, focus, base=S1):
    """One colour for every bar; when a place is in focus it keeps the colour
    and the rest step back."""
    return [base if not focus or n==focus else SOFT for n in names]

def location_table(d, nmon):
    gg=d.groupby("Location").agg(off=("Number of offences","sum"),pop=("Population","first"),
        lat=("lat","first"),lon=("lon","first"))
    gg=gg[gg.index!=UNKNOWN]
    # Annualised so the rate means the same thing for one month or eighteen years.
    gg["rate"]=gg["off"]/gg["pop"]*1000*12/max(nmon,1)
    return gg

@app.callback(
    Output("period-label","children"),Output("p-all","className"),Output("p-old","className"),Output("p-new","className"),
    Output("focus-banner","children"),Output("h-g-trend","children"),Output("h-g-rank","children"),
    Output("kpis","children"),Output("insight","children"),Output("g-trend","figure"),Output("g-rank","figure"),Output("g-map","figure"),
    Output("g-replay","figure"),Output("g-yoy","figure"),Output("g-alcdv","figure"),Output("g-season","figure"),Output("g-mix","figure"),
    Input("f-period","value"),Input("f-loc","value"),Input("f-crime","value"),Input("f-mode","value"),
    Input("f-month","value"),Input("f-focus","value"))
def update(period,locs,crimes,mode,months,focus):
    lo,hi=period
    crosses_sel=lo<CUT<=hi
    nsel=len(window_months(lo,hi,months))
    plabel=(f"{ym_label(lo)} – {ym_label(hi)}  ·  {nsel} month{'s' if nsel!=1 else ''}"
            +(f"  ·  spans the {ym_label(CUT-1)} recording change" if crosses_sel else ""))
    btn=lambda k:"tca-btn is-active" if list(period)==PRESETS[k] else "tca-btn"
    d=fdf(period,locs,crimes,months)
    # `dl` is what the headline figures describe: the focused place, or everywhere.
    dl=d[d["Location"]==focus] if focus else d
    place=focus or "the Territory"
    nmon=max(nsel,1)
    total=dl["Number of offences"].sum()
    alc=dl[dl["Alcohol involvement"]=="Yes"]["Number of offences"].sum()
    dv=dl[dl["DV involvement"]=="Yes"]["Number of offences"].sum()

    banner=(html.Div(className="tca-focus", style={"display":"flex","alignItems":"center","gap":"10px",
        "backgroundColor":ACCENT,"color":"#fff","borderRadius":"12px","padding":"10px 16px","marginBottom":"16px",
        "fontSize":"14px"}, children=[
            html.Img(src=app.get_asset_url("icons/pin.svg"),alt="",style={"width":"18px","filter":"brightness(0) invert(1)"}),
            html.Span(["Focused on ",html.B(focus),". Headline figures, the trend and seasonality show this place; "
                       "other charts highlight it."]),
            html.Button("Show whole Territory", id="focus-clear", className="tca-btn",
                        style={"marginLeft":"auto"})])
        if focus else html.Button(id="focus-clear", style={"display":"none"}))

    # Like-for-like year-on-year window (same months of consecutive years).
    cw=compare_window(lo,hi,months)
    if cw:
        Y0,Y1,cms,crosses=cw
        cmp_lbl=("" if len(cms)==12 else f"{span(cms)} ")+f"{Y0} → {Y1}"
        a=dl[(dl["Year"]==Y0)&dl["Month number"].isin(cms)]; b=dl[(dl["Year"]==Y1)&dl["Month number"].isin(cms)]
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

    gg=location_table(d,nmon)
    gg_rate=gg.dropna(subset=["pop"])  # only locations with verified population
    src,val=(gg_rate,"rate") if mode=="rate" else (gg,"off")
    ranked=src.sort_values(val,ascending=False)
    top_region=ranked.index[0] if len(ranked) else "—"

    # ---- plain-English takeaways ----
    ins=[]
    if cw and s0:
        ins.append(html.Li([f"Recorded offences in {place} ",html.B(f"{'fell' if yoy<0 else 'rose'} {abs(yoy):.0f}%"),
            f" from {Y0} to {Y1}"+(f" ({span(cms)})" if len(cms)<12 else "")
            +(", but that comparison spans the change in police recording systems, so treat it as indicative." if crosses else ".")]))
    if focus and focus not in gg.index:
        ins.append(html.Li([html.B(focus)," has no offences in this selection. The location type or crime type "
            "filters may exclude it; press Reset to clear them."]))
    elif focus:
        if focus in ranked.index:
            pos=list(ranked.index).index(focus)+1
            ins.append(html.Li([html.B(focus),f" ranks {pos} of {len(ranked)} places "
                +("per resident" if mode=="rate" else "by number of offences")
                +(f", at {gg.loc[focus,'rate']:,.0f} offences per 1,000 residents a year." if pd.notna(gg.loc[focus,'pop']) else ".")]))
        else:
            ins.append(html.Li([html.B(focus)," has no reliable population figure, so it is ranked by count only."]))
        mix=dl.groupby("Crime Type")["Number of offences"].sum().sort_values(ascending=False)
        if len(mix) and total:
            ins.append(html.Li(["Its most common offence is ",html.B(mix.index[0].lower()),
                f", {mix.iloc[0]/total*100:.0f}% of the total. Alcohol was involved in {alc/total*100:.0f}% of offences "
                f"(Territory-wide {d[d['Alcohol involvement']=='Yes']['Number of offences'].sum()/max(d['Number of offences'].sum(),1)*100:.0f}%)."]))
    elif len(gg) and len(gg_rate):
        hi_vol=gg['off'].idxmax()
        hi_rate=gg_rate['rate'].idxmax()
        ratio=gg_rate['rate'].max()/gg_rate['rate'].min() if gg_rate['rate'].min()>0 else 0
        ins.append(html.Li(["By volume the largest count is in ",html.B(hi_vol),", but per resident ",html.B(hi_rate),
            f" is the most affected, about {ratio:.0f}× the rate of the least affected. "
            "Resourcing by raw counts alone would under-serve smaller remote communities."]))
    if crosses_sel:
        ins.append(html.Li(["This period includes both sides of the ",html.B(f"{ym_label(CUT-1,True)} change"),
            " from PROMIS to SerPro; use the period buttons to look at one recording system at a time."]))
    insight=ins or [html.Li("No offences match this selection.")]

    if focus:
        pos_txt=(f"#{list(ranked.index).index(focus)+1} of {len(ranked)}" if focus in ranked.index else "—")
        third=kpi("pin",f"{focus} rank",pos_txt,"per 1,000 residents a year" if mode=="rate" else "by total offences")
    else:
        third=kpi("pin","Highest "+("rate" if mode=="rate" else "volume"),top_region,
            "per 1,000 residents a year" if mode=="rate" else "total offences")
    kpis=[kpi("bars","Total offences",f"{total:,.0f}",f"{place if focus else 'Territory'} · {ym_label(lo)} – {ym_label(hi)}"),
        kpi("trend","Year-on-year change",ytxt,ysub,ycol),
        third,
        kpi("alert","Alcohol / DV share",f"{alc/total*100:.0f}% / {dv/total*100:.0f}%" if total else "—",
            f"{alc:,.0f} / {dv:,.0f} offences")]

    # (0) monthly trend across the whole selected period. The 12-month average
    # is computed separately on each side of the recording-system change so it
    # never blends PROMIS and SerPro months.
    wm=window_months(lo,hi,months)
    ser=dl.groupby("ym")["Number of offences"].sum().reindex(wm,fill_value=0)
    xs=[pd.Timestamp(year=m//12,month=m%12+1,day=1) for m in ser.index]
    fig_trend=go.Figure()
    fig_trend.add_scatter(x=xs,y=ser.values,mode="lines" if not months else "markers",name="Monthly offences",
        line=dict(width=1.3,color="#9fd0d6"),marker=dict(size=8,color=S1),
        hovertemplate="<b>%{y:,.0f}</b> offences<extra></extra>")
    if not months:
        first_avg=True
        for part in (ser[ser.index<CUT],ser[ser.index>=CUT]):
            if len(part)>=12:
                roll=part.rolling(12).mean()
                fig_trend.add_scatter(x=[xs[wm.index(m)] for m in part.index],y=roll.values,mode="lines",
                    name="12-month average",showlegend=first_avg,legendgroup="avg",line=dict(width=2.6,color=ACCENT),
                    hovertemplate="<b>%{y:,.0f}</b> 12-month average<extra></extra>")
                first_avg=False
    if CUT-1 in ser.index:
        fig_trend.add_scatter(x=[xs[wm.index(CUT-1)]],y=[ser[CUT-1]],mode="markers",name="Provisional cutover month",
            marker=dict(size=11,color=S4,line=dict(width=2,color=SURFACE)),showlegend=False,
            hovertemplate="<b>%{y:,.0f}</b> provisional cutover month<extra></extra>")
    if crosses_sel:
        brk=pd.Timestamp(year=CUT//12,month=CUT%12+1,day=1)-pd.Timedelta(days=15)
        fig_trend.add_shape(type="rect",xref="x",yref="paper",x0=brk,x1=xs[-1]+pd.Timedelta(days=15),y0=0,y1=1,
            fillcolor=ERA_FILL,line_width=0,layer="below")
        fig_trend.add_shape(type="line",xref="x",yref="paper",x0=brk,x1=brk,y0=0,y1=1,
            line=dict(color=MUTE,width=1.2,dash="dash"))
        fig_trend.add_annotation(x=brk,y=0.02,xref="x",yref="paper",xanchor="center",yanchor="bottom",showarrow=False,
            text="PROMIS ←  → SerPro",bgcolor="rgba(255,255,255,0.85)",font=dict(size=11,color=MUTE))
    # Label the extremes of the average so the story reads without hovering.
    if len(ser) and ser.max()>0:
        pk=ser.idxmax()
        fig_trend.add_annotation(x=xs[wm.index(pk)],y=ser[pk],text=f"peak {ser[pk]:,.0f} · {ym_label(pk)}",
            showarrow=True,arrowhead=0,arrowcolor=MUTE,ax=0,ay=-22,font=dict(size=11,color=MUTE))
    fig_trend.update_layout(template=T,height=320,margin=dict(l=58,r=20,t=14,b=40),yaxis_title="Offences",
        hovermode="x unified",xaxis=dict(showspikes=True,spikemode="across",spikethickness=1,spikecolor=MUTE,
            spikedash="solid",hoverformat="%B %Y"),
        legend=dict(orientation="h",y=1.02,x=1,xanchor="right",yanchor="bottom"))
    trend_title=f"How crime has moved in {focus}, month by month" if focus else "How crime has moved, month by month"

    # (1) ranking
    gr=src.sort_values(val).tail(12)
    if focus and focus in src.index and focus not in gr.index:
        gr=pd.concat([src.loc[[focus]],gr.iloc[1:]])     # keep the focused place on screen
    rank_title=("Where crime hits hardest · per 1,000 residents a year" if mode=="rate"
                else "Where crime is highest · total offences")
    if len(gr):
        x=gr[val]
        fig_rank=go.Figure(go.Bar(x=x,y=gr.index,orientation="h",marker=dict(color=emph(gr.index,focus),
            cornerradius=4),text=[f"{v:,.0f}" for v in x],textposition="outside",cliponaxis=False,
            textfont=dict(size=12,color=INK),
            hovertemplate="<b>%{x:,.0f}</b> "+("per 1,000 a year" if mode=="rate" else "offences")+"<br>%{y}<extra></extra>"))
        fig_rank.update_layout(template=T,height=380,margin=dict(l=120,r=60,t=10,b=34),bargap=0.25,
            xaxis=dict(title=None,range=[0,x.max()*1.18]),yaxis=dict(title=None),transition=TRANSITION)
    else:
        fig_rank=empty("No offences match this selection")

    # (2) MAP — Carto tiles. Bubble = volume; colour = per-1,000 rate where a
    # verified population exists, grey where it doesn't (honest about coverage).
    md=gg.dropna(subset=["lat","lon"]).copy()
    md_rate=md.dropna(subset=["pop"])
    md_norate=md[md["pop"].isna()]
    fig_map=go.Figure()
    size=lambda s:s/max(gg["off"].max(),1)*38+8
    if focus and focus in md.index:
        r=md.loc[focus]
        fig_map.add_scattermap(lat=[r["lat"]],lon=[r["lon"]],text=[focus],mode="markers",hoverinfo="skip",
            marker=dict(size=size(r["off"])+16,color="rgba(235,104,52,0.35)"))
    if len(md_norate):
        fig_map.add_scattermap(lat=md_norate["lat"],lon=md_norate["lon"],
            text=md_norate.index,mode="markers",
            marker=dict(size=size(md_norate["off"]),color="#b8c0c8"),
            name="count only (no rate)",
            hovertemplate="<b>%{customdata:,.0f}</b> offences<br>%{text} · rate n/a<extra></extra>",
            customdata=md_norate["off"])
    if len(md_rate):
        fig_map.add_scattermap(lat=md_rate["lat"],lon=md_rate["lon"],
            text=md_rate.index,mode="markers",
            marker=dict(size=size(md_rate["off"]),color=md_rate["rate"],colorscale=SEQ_SCALE,
                showscale=True,colorbar=dict(title="per 1,000<br>a year",thickness=12,len=0.7),
                cmin=0,cmax=md_rate["rate"].max()),
            name="rate available",
            hovertemplate="<b>%{customdata[1]:,.0f}</b> per 1,000 a year<br>%{text} · %{customdata[0]:,.0f} offences<extra></extra>",
            customdata=md_rate[["off","rate"]].values)
    fig_map.update_layout(map_style="carto-positron",map_zoom=4.0,
        map_center=dict(lat=-19.2,lon=133.4),
        height=380,margin=dict(l=8,r=8,t=10,b=8),showlegend=False)

    # (3) replay — one frame per year in the period. The order of places is
    # fixed by their overall rank so each bar can be followed as it grows.
    fig_replay=replay(d,lo,hi,months,mode,focus)

    # (4) YoY — same like-for-like window as the KPI
    piv=pd.DataFrame()
    if cw:
        w=d[d["Month number"].isin(cms)&d["Year"].isin([Y0,Y1])]
        piv=w.groupby(["Location","Year"])["Number of offences"].sum().unstack()
    if cw and {Y0,Y1}.issubset(piv.columns):
        piv=piv.dropna(subset=[Y0,Y1]); piv=piv[piv.index!=UNKNOWN]
        piv["y"]=(piv[Y1]-piv[Y0])/piv[Y0]*100; piv=piv.sort_values("y")
        rng=max(abs(piv["y"].min()),abs(piv["y"].max()),1)*1.25
        cols=[MUTE if crosses else GOOD if v<0 else BAD for v in piv["y"]]
        if focus: cols=[c if n==focus else SOFT for c,n in zip(cols,piv.index)]
        fig_yoy=go.Figure(go.Bar(x=piv["y"],y=piv.index,orientation="h",marker=dict(color=cols,cornerradius=4),
            text=[f"{v:+.0f}%" for v in piv["y"]],textposition="outside",cliponaxis=False,
            textfont=dict(size=11,color=INK),
            customdata=piv[[Y0,Y1]].values,
            hovertemplate="<b>%{x:+.0f}%</b><br>%{y}: %{customdata[0]:,.0f} → %{customdata[1]:,.0f}<extra></extra>"))
        fig_yoy.update_xaxes(range=[-rng,rng])
        fig_yoy.update_layout(template=T,height=max(380,22*len(piv)+70),
            margin=dict(l=130,r=50,t=10,b=46),bargap=0.2,
            xaxis_title=f"% change, {cmp_lbl}"+(" · indicative, spans the change" if crosses else ""),
            yaxis_title=None,transition=TRANSITION)
    else:
        fig_yoy=empty("Needs the same months of the year before in the period")

    # (5) alcohol & DV
    inv=d.groupby("Location").apply(lambda x:pd.Series({
        "Alcohol":x[x["Alcohol involvement"]=="Yes"]["Number of offences"].sum(),
        "DV":x[x["DV involvement"]=="Yes"]["Number of offences"].sum()}),
        include_groups=False)
    fig_alc=go.Figure()
    if len(inv):
        inv=inv[inv.index!=UNKNOWN].sort_values("DV",ascending=False).head(15).reset_index()
        op=[1 if not focus or n==focus else 0.3 for n in inv["Location"]]
        fig_alc.add_bar(x=inv["Location"],y=inv["Alcohol"],name="Alcohol involved",marker=dict(color=S2,opacity=op,cornerradius=4),
            hovertemplate="<b>%{y:,.0f}</b> alcohol involved<extra></extra>")
        fig_alc.add_bar(x=inv["Location"],y=inv["DV"],name="Domestic violence",marker=dict(color=S1,opacity=op,cornerradius=4),
            hovertemplate="<b>%{y:,.0f}</b> domestic violence<extra></extra>")
    fig_alc.update_layout(template=T,barmode="group",bargap=0.25,bargroupgap=0.08,
        height=380,margin=dict(l=58,r=20,t=30,b=90),yaxis_title="Offences",hovermode="x unified",
        xaxis=dict(tickangle=-40),legend=dict(orientation="h",y=1.08,x=1,xanchor="right"),transition=TRANSITION)

    # (6) seasonality — indexed to each line's own mean (pattern, not volume).
    # Each calendar month is averaged over the years it appears in, so a
    # partial year does not inflate the months it covers.
    def season(frame):
        s=frame.groupby(["Year","Month number"])["Number of offences"].sum().groupby("Month number").mean()
        return s/s.mean()*100 if len(s) and s.mean() else s
    lines=([(focus,dl,S1),("Whole Territory",d,MUTE)] if focus else
           [(r,d[d["Location"]==r],TOWN_COLOURS[r]) for r in TOWN_COLOURS])
    fig_sea=go.Figure()
    ends=[]
    for name,frame,col in lines:
        idx=season(frame)
        if not len(idx): continue
        xm=[MONTHS[int(m)-1] for m in idx.index]
        fig_sea.add_scatter(x=xm,y=idx.values,mode="lines+markers",name=name,
            line=dict(width=2,color=col,dash="dot" if name=="Whole Territory" else "solid"),
            marker=dict(size=8,line=dict(width=2,color=SURFACE)),
            hovertemplate="<b>%{y:.0f}</b> "+name+"<extra></extra>")
        ends.append([float(idx.values[-1]),name,xm[-1]])
    # Direct labels at the line ends, nudged apart so close lines stay legible.
    ends.sort()
    for i in range(1,len(ends)):
        ends[i][0]=max(ends[i][0],ends[i-1][0]+3.2)
    for y,name,xl in ends:
        fig_sea.add_annotation(x=xl,y=y,text=name,xanchor="left",showarrow=False,xshift=8,font=dict(size=11,color=INK))
    fig_sea.add_hline(y=100,line_color=LINE)
    fig_sea.update_layout(template=T,height=380,margin=dict(l=58,r=100,t=10,b=40),
        yaxis_title="index (100 = average month)",hovermode="x unified",
        legend=dict(orientation="h",y=-0.14,font=dict(size=11)))

    # (7) crime fingerprint — share of each place's offences, as a heatmap:
    # one sequential hue reads more easily than nine stacked colours.
    comp=d.groupby(["Location","Crime Type"])["Number of offences"].sum().unstack(fill_value=0)
    comp=comp[comp.index!=UNKNOWN]
    if len(comp):
        comp=comp.loc[comp.sum(axis=1).sort_values(ascending=False).index]
        comp=comp[comp.sum().sort_values(ascending=False).index]
        pct=comp.div(comp.sum(axis=1),axis=0)*100
        fig_mix=go.Figure(go.Heatmap(z=pct.values,x=pct.columns,y=pct.index,colorscale=SEQ_SCALE,
            xgap=2,ygap=2,customdata=comp.values,colorbar=dict(title="% of<br>offences",thickness=12,ticksuffix="%"),
            hovertemplate="<b>%{z:.0f}%</b> of offences<br>%{y} · %{x}<br>%{customdata:,.0f} offences<extra></extra>"))
        fig_mix.update_layout(template=T,height=22*len(pct)+120,margin=dict(l=150,r=20,t=10,b=90),
            yaxis=dict(autorange="reversed",showgrid=False),xaxis=dict(side="bottom",tickangle=-25,showgrid=False))
        if focus in pct.index:
            i=list(pct.index).index(focus)
            fig_mix.add_shape(type="rect",xref="paper",x0=0,x1=1,yref="y",y0=i-0.5,y1=i+0.5,
                line=dict(color=S2,width=2.5))
    else:
        fig_mix=empty("No offences match this selection")

    return (plabel,btn("p-all"),btn("p-old"),btn("p-new"),banner,trend_title,rank_title,
            kpis,insight,fig_trend,fig_rank,fig_map,fig_replay,fig_yoy,fig_alc,fig_sea,fig_mix)

def replay(d,lo,hi,months,mode,focus):
    years=sorted(set(m//12 for m in window_months(lo,hi,months)))
    by=d.groupby(["Year","Location"]).agg(off=("Number of offences","sum"),pop=("Population","first")).reset_index()
    by=by[by["Location"]!=UNKNOWN]
    if mode=="rate": by=by.dropna(subset=["pop"])
    if by.empty or not years: return empty("No offences match this selection")
    nm={y:len([m for m in window_months(lo,hi,months) if m//12==y]) for y in years}
    by["val"]=(by["off"]/by["pop"]*1000*12/by["Year"].map(nm)) if mode=="rate" else by["off"]
    order=by.groupby("Location")["val"].mean().sort_values().tail(10).index.tolist()
    if focus and focus in by["Location"].values and focus not in order: order=[focus]+order[1:]
    piv=by.pivot(index="Year",columns="Location",values="val").reindex(index=years,columns=order).fillna(0)
    xmax=piv.values.max()*1.18 or 1
    unit="per 1,000 a year" if mode=="rate" else "offences"
    def era(y):
        if y*12+11<CUT: return "recorded under PROMIS"
        if y*12>=CUT: return "recorded under SerPro"
        return "PROMIS to November, SerPro from December"
    def bar(y):
        v=piv.loc[y]
        return go.Bar(x=v.values,y=order,orientation="h",marker=dict(color=emph(order,focus),cornerradius=4),
            text=[f"{x:,.0f}" for x in v.values],textposition="outside",cliponaxis=False,textfont=dict(color=INK,size=12),
            hovertemplate="<b>%{x:,.0f}</b> "+unit+"<br>%{y} · "+str(y)+"<extra></extra>")
    def label(y):
        # The year is drawn as a text layer in the frame itself: layout
        # annotations do not follow animation frames.
        part=f" ({span([m%12+1 for m in window_months(lo,hi,months) if m//12==y])})" if nm[y]<12 else ""
        base=dict(mode="text",x=[xmax*0.99],textposition="middle left",hoverinfo="skip",showlegend=False)
        return [go.Scatter(**base,y=[order[min(1,len(order)-1)]],text=[f"<b>{y}</b>"],textfont=dict(size=40,color=SOFT)),
                go.Scatter(**base,y=[order[0]],text=[era(y)+part],textfont=dict(size=11,color=MUTE))]
    fig=go.Figure(data=[bar(years[0]),*label(years[0])],
        frames=[go.Frame(data=[bar(y),*label(y)],name=str(y)) for y in years])
    fig.update_layout(template=T,height=380,margin=dict(l=120,r=50,t=10,b=86),
        xaxis=dict(range=[0,xmax],title=None),yaxis=dict(categoryorder="array",categoryarray=order),bargap=0.25,
        showlegend=False)
    if len(years)>1:
        play=dict(frame=dict(duration=1000,redraw=False),transition=dict(duration=600,easing="cubic-in-out"),fromcurrent=True)
        fig.update_layout(
            updatemenus=[dict(type="buttons",direction="left",x=0,y=-0.1,xanchor="left",yanchor="top",
                showactive=False,bgcolor=SURFACE,bordercolor=LINE,font=dict(size=12,color=INK),pad=dict(r=6,t=4),
                buttons=[dict(label="▶  Play",method="animate",args=[None,play]),
                         dict(label="❚❚  Pause",method="animate",
                              args=[[None],dict(frame=dict(duration=0,redraw=False),mode="immediate",transition=dict(duration=0))])])],
            sliders=[dict(active=0,x=0.36,y=-0.1,len=0.64,yanchor="top",pad=dict(t=8,b=0),currentvalue=dict(visible=False),
                font=dict(size=10,color=MUTE),bordercolor=LINE,tickcolor=LINE,activebgcolor=ACCENT,
                steps=[dict(label=str(y) if (y%2==0 or y==years[-1] or len(years)<10) else "",method="animate",
                            args=[[str(y)],dict(mode="immediate",frame=dict(duration=0,redraw=False),
                                                transition=dict(duration=300))]) for y in years])])
    return fig

if __name__=="__main__":
    app.run(debug=True)
