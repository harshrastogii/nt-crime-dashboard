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
import pandas as pd

df = pd.read_parquet("crime_clean.parquet")
CRIME_TYPES = sorted(df["Crime Type"].unique())
LOC_TYPES = ["Urban", "Regional", "Remote"]
MONTHS = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]

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

app.layout=html.Div(className="tca-page", style={"backgroundColor":PAGE,"color":INK,"minHeight":"100vh",
    "fontFamily":"Inter, system-ui, sans-serif","padding":"28px 34px","maxWidth":"1480px","margin":"0 auto"}, children=[
    html.Div(style={"display":"flex","justifyContent":"space-between","alignItems":"flex-end",
        "borderBottom":f"2px solid {ACCENT}","paddingBottom":"14px","marginBottom":"22px"}, children=[
        html.Div([html.Div(style={"display":"flex","alignItems":"center","gap":"12px"}, children=[
            html.Div(style={"width":"6px","height":"32px","backgroundColor":ACCENT,"borderRadius":"3px"}),
            html.H1("Territory Crime Atlas", style={"fontWeight":700,"fontSize":"26px","margin":0})]),
            html.P("Recorded offences, complete calendar years 2024-2025  |  Source: NT Police, NTG Open Data Portal",
                style={"color":MUTE,"margin":"6px 0 0 18px","fontSize":"13px"})]),
        html.Div("Built with Python + Dash", style={"fontSize":"12px","color":MUTE})]),

    html.Div(style={**CARD,"padding":"16px","marginBottom":"22px","display":"flex","gap":"22px",
        "flexWrap":"wrap","alignItems":"flex-end"}, children=[
        html.Div([html.Label("Year", style=LBL), dcc.Dropdown([2023,2024,2025,2026],[2024,2025],
            multi=True,id="f-year",clearable=False,style={"minWidth":"190px"})]),
        html.Div([html.Label("Location type", style=LBL), dcc.Dropdown(LOC_TYPES,[],multi=True,
            id="f-loc",placeholder="All locations",style={"minWidth":"170px"})]),
        html.Div([html.Label("Crime type", style=LBL), dcc.Dropdown(CRIME_TYPES,[],multi=True,
            id="f-crime",placeholder="All crime types",style={"minWidth":"210px"})]),
        html.Div([html.Label("Region ranking shows", style=LBL), dcc.RadioItems(id="f-mode",value="rate",
            inline=True,options=[{"label":" Per 1,000 residents","value":"rate"},{"label":" Raw count","value":"raw"}],
            labelStyle={"marginRight":"16px","color":INK,"fontSize":"14px","cursor":"pointer"},
            inputStyle={"marginRight":"6px","accentColor":ACCENT})])]),

    html.Div(id="kpis", className="tca-grid-4", style={"display":"grid","gridTemplateColumns":"repeat(4,1fr)","gap":"16px","marginBottom":"16px"}),

    html.Div(id="insight", style={"backgroundColor":"#eef5f6","border":f"1px solid #cfe3e6",
        "borderLeft":f"4px solid {ACCENT}","borderRadius":"12px","padding":"16px 20px",
        "marginBottom":"22px","fontSize":"14px","lineHeight":1.65,"color":INK}),

    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-rank"), g("g-map")]),
    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-yoy"), g("g-alcdv")]),
    html.Div(className="tca-grid-2", style={"display":"grid","gridTemplateColumns":"1fr 1fr","gap":"20px","marginBottom":"20px"}, children=[g("g-season"), g("g-comp")]),

    html.Div(style={"padding":"14px 16px","backgroundColor":"#fbf7ec","border":"1px solid #ecdfbf",
        "borderRadius":"12px","fontSize":"12.5px","color":"#7a6a2f","lineHeight":1.6}, children=[
        html.Strong("Notes:  "),
        "2023 (December only) and 2026 (Jan-Mar only) are partial periods, excluded from annual comparisons. "
        "Category trends cross the April 2025 ANZSOC reclassification. Per-1,000 rates use indicative 2021 census "
        "populations; small-population regions (e.g. Tennant Creek) have volatile rates. 'NT Balance' aggregates "
        "remaining NT localities and is excluded from the map as it has no single location."])])

def fdf(years,locs,crimes):
    d=df
    if years: d=d[d["Year"].isin(years)]
    if locs: d=d[d["Location Type"].isin(locs)]
    if crimes: d=d[d["Crime Type"].isin(crimes)]
    return d

def kpi(label,value,sub=None,color=INK):
    return html.Div(style={"backgroundColor":SURFACE,"borderRadius":"14px","padding":"16px 18px",
        "border":f"1px solid {LINE}","boxShadow":"0 1px 3px rgba(16,24,40,0.05)"}, children=[
        html.Div(label, style={"fontSize":"11px","fontWeight":600,"color":MUTE,"textTransform":"uppercase","letterSpacing":"0.05em"}),
        html.Div(value, style={"fontSize":"28px","fontWeight":700,"color":color,"marginTop":"4px"}),
        html.Div(sub or "", style={"fontSize":"12px","color":MUTE,"marginTop":"2px"})])

@app.callback(
    Output("kpis","children"),Output("insight","children"),Output("g-rank","figure"),Output("g-map","figure"),
    Output("g-yoy","figure"),Output("g-alcdv","figure"),Output("g-season","figure"),Output("g-comp","figure"),
    Input("f-year","value"),Input("f-loc","value"),Input("f-crime","value"),Input("f-mode","value"))
def update(years,locs,crimes,mode):
    d=fdf(years,locs,crimes)
    total=d["Number of offences"].sum()
    alc=d[d["Alcohol involvement"]=="Yes"]["Number of offences"].sum()
    dv=d[d["DV involvement"]=="Yes"]["Number of offences"].sum()
    cy=d[d["complete_year"]]
    by=cy.groupby("Year")["Number of offences"].sum()
    if {2024,2025}.issubset(by.index):
        yoy=(by[2025]-by[2024])/by[2024]*100
        ytxt,ycol=((f"\u25bc {abs(yoy):.0f}%",GOOD) if yoy<0 else (f"\u25b2 {yoy:.0f}%",BAD)); ysub="2024 \u2192 2025"
    else: ytxt,ycol,ysub="\u2014",MUTE,"needs both full years"

    gg=d.groupby("Location").agg(off=("Number of offences","sum"),pop=("Population","first"),
        lat=("lat","first"),lon=("lon","first"))
    gg=gg[gg.index!="Unknown / not stated"]; gg["rate"]=gg["off"]/gg["pop"]*1000
    gg_rate=gg.dropna(subset=["pop"])  # only locations with verified population
    if mode=="rate":
        src=gg_rate; val="rate"
    else:
        src=gg; val="off"
    top_region=src.sort_values(val,ascending=False).index[0] if len(src) else "\u2014"

    # ---- dynamic plain-English insight for decision-makers ----
    ins=[]
    if {2024,2025}.issubset(by.index):
        d_overall=(by[2025]-by[2024])/by[2024]*100
        ins.append(html.Span([html.B("Overall, "),
            f"recorded offences {'fell' if d_overall<0 else 'rose'} "
            f"{abs(d_overall):.0f}% from 2024 to 2025 in this selection. "]))
    if len(gg):
        hi_vol=gg['off'].idxmax()
        hi_rate=gg_rate['rate'].idxmax() if len(gg_rate) else hi_vol
        ratio=gg_rate['rate'].max()/gg_rate['rate'].min() if len(gg_rate) and gg_rate['rate'].min()>0 else 0
        ins.append(html.Span([
            "By volume the largest count is in ",html.B(hi_vol),
            f", but per resident ",html.B(hi_rate),
            f" is the most affected community — about {ratio:.0f}× the rate of the least affected. "
            "Resourcing by raw counts alone would under-serve smaller remote communities."]))
    insight=ins

    kpis=[kpi("Total offences",f"{total:,.0f}","current selection"),
        kpi("Year-on-year change",ytxt,ysub,ycol),
        kpi("Highest "+("rate" if mode=="rate" else "volume"),top_region,
            "per 1,000 residents" if mode=="rate" else "total offences"),
        kpi("Alcohol / DV share",f"{alc/total*100:.0f}% / {dv/total*100:.0f}%" if total else "\u2014",
            f"{alc:,.0f} / {dv:,.0f} offences")]

    # (1) ranking — generous left margin, label headroom
    gr=src.sort_values(val).tail(12)
    x=gr[val]; text=[f"{v:,.0f}" for v in x]
    ttl=("Where crime hits hardest \u00b7 per 1,000 residents" if mode=="rate"
         else "Where crime is highest \u00b7 total offences")
    cols=[BAD if r==top_region else ACCENT for r in gr.index]
    fig_rank=go.Figure(go.Bar(x=x,y=gr.index,orientation="h",marker_color=cols,
        text=text,textposition="outside",cliponaxis=False,textfont=dict(size=12)))
    fig_rank.update_layout(template=T,title=ttl,height=380,
        margin=dict(l=120,r=70,t=54,b=34),
        xaxis=dict(title=None,range=[0,x.max()*1.18]),yaxis=dict(title=None))

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
                showscale=True,colorbar=dict(title="per 1,000",thickness=12,len=0.7),
                cmin=0,cmax=md_rate["rate"].max()),
            name="rate available",
            hovertemplate="<b>%{text}</b><br>%{customdata[0]:,.0f} offences<br>%{customdata[1]:,.0f} per 1,000<extra></extra>",
            customdata=md_rate[["off","rate"]].values)
    fig_map.update_layout(map_style="carto-positron",map_zoom=4.0,
        map_center=dict(lat=-19.2,lon=133.4),
        title="Crime intensity across the Territory",
        height=380,margin=dict(l=8,r=8,t=54,b=8),showlegend=False)

    # (3) YoY — margins fixed
    piv=cy.groupby(["Location","Year"])["Number of offences"].sum().unstack()
    fig_yoy=go.Figure()
    if {2024,2025}.issubset(piv.columns):
        piv=piv.dropna(subset=[2024,2025]); piv=piv[piv.index!="Unknown / not stated"]
        piv["y"]=(piv[2025]-piv[2024])/piv[2024]*100; piv=piv.sort_values("y")
        rng=max(abs(piv["y"].min()),abs(piv["y"].max()))*1.25
        fig_yoy=go.Figure(go.Bar(x=piv["y"],y=piv.index,orientation="h",
            marker_color=[GOOD if v<0 else BAD for v in piv["y"]],
            text=[f"{v:+.0f}%" for v in piv["y"]],textposition="outside",cliponaxis=False))
        fig_yoy.update_xaxes(range=[-rng,rng])
    fig_yoy.update_layout(template=T,title="Year-on-year change by region",height=380,
        margin=dict(l=120,r=50,t=54,b=46),xaxis_title="% change 2024 \u2192 2025",yaxis_title=None)

    # (4) alcohol & DV
    inv=d.groupby("Location").apply(lambda x:pd.Series({
        "Alcohol":x[x["Alcohol involvement"]=="Yes"]["Number of offences"].sum(),
        "DV":x[x["DV involvement"]=="Yes"]["Number of offences"].sum()}),
        include_groups=False)
    inv=inv[inv.index!="Unknown / not stated"].sort_values("DV",ascending=False).reset_index()
    fig_alc=go.Figure()
    fig_alc.add_bar(x=inv["Location"],y=inv["Alcohol"],name="Alcohol-related",marker_color=AMBER)
    fig_alc.add_bar(x=inv["Location"],y=inv["DV"],name="DV-related",marker_color=ACCENT)
    fig_alc.update_layout(template=T,barmode="group",title="Alcohol & DV-related offences by region",
        height=380,margin=dict(l=58,r=20,t=54,b=80),yaxis_title="Offences",
        legend=dict(orientation="h",y=1.02,x=1,xanchor="right"))

    # (5) seasonality — per region, indexed to each region's mean (pattern, not volume)
    sea=cy.groupby(["Month number","Location"])["Number of offences"].sum().unstack()
    keep=[r for r in ["Darwin","Alice Springs","Katherine","Palmerston"] if r in sea.columns]
    fig_sea=go.Figure()
    pal={"Darwin":ACCENT,"Alice Springs":BAD,"Katherine":AMBER,"Palmerston":"#6aa6af"}
    for r in keep:
        idx=sea[r]/sea[r].mean()*100
        fig_sea.add_scatter(x=MONTHS,y=idx.values,mode="lines+markers",name=r,
            line=dict(width=2.2,color=pal.get(r,MUTE)),marker=dict(size=5))
    fig_sea.add_hline(y=100,line_dash="dot",line_color=LINE)
    fig_sea.update_layout(template=T,title="Seasonality \u00b7 monthly offences vs each region's average",
        height=380,margin=dict(l=58,r=20,t=54,b=40),
        yaxis_title="index (100 = average month)",
        legend=dict(orientation="h",y=-0.18,font=dict(size=10)))

    # (6) composition — % share (regional fingerprint), not raw
    comp=cy.groupby(["Location","Crime Type"])["Number of offences"].sum().unstack(fill_value=0)
    comp=comp[comp.index!="Unknown"]
    comp=comp.loc[comp.sum(axis=1).sort_values(ascending=False).index]
    pct=comp.div(comp.sum(axis=1),axis=0)*100
    fig_comp=go.Figure()
    for i,ct in enumerate(comp.columns):
        fig_comp.add_bar(x=pct.index,y=pct[ct],name=ct,marker_color=SEQ[i%len(SEQ)])
    fig_comp.update_layout(template=T,barmode="stack",
        title="Crime mix by region \u00b7 share of each region's offences  (hover a segment for the category)",
        height=460,margin=dict(l=50,r=20,t=54,b=130),yaxis_title="% of region's offences",
        yaxis=dict(ticksuffix="%"),
        xaxis=dict(tickangle=-90,automargin=True),
        showlegend=False)
    fig_comp.update_traces(hovertemplate="<b>%{x}</b><br>%{fullData.name}: %{y:.0f}%%<extra></extra>")

    return kpis,insight,fig_rank,fig_map,fig_yoy,fig_alc,fig_sea,fig_comp

if __name__=="__main__":
    app.run(debug=True)
