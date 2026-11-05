"""Original editable Nokia N95 front artwork; verified photographic references in asset provenance.

Geometry is expressed in editable SVG layers; no reference-photo pixels are embedded.
Run from the repository root to regenerate the two SVG masters. Blank screens are intentional.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]/'symport/web_assets/phones'

def draw(eight=False):
    model='Nokia N95 8GB' if eight else 'Nokia N95'
    key='nokia-n95-8gb' if eight else 'nokia-n95'
    x,y,w,h=(119,228,762,1016) if eight else (154,272,692,923)
    case=['#111419','#4b4d50','#1d2024','#080a0d','#33363a'] if eight else ['#e4e5e3','#fffef9','#a6aaa9','#dce0df','#8a8e8e']
    face='#15181c' if eight else '#d5d8d5'
    control='#25292e' if eight else '#e1e2da'
    ink='#cdd1d4' if eight else '#525857'
    svg=f'''<svg xmlns="http://www.w3.org/2000/svg" width="1000" height="1868" viewBox="0 0 1000 1868" role="img" aria-labelledby="title desc">
<title id="title">{model} — original front illustration</title><desc id="desc">Closed dual slider, blank glass screen; editable original vector drawing. No hardware connection or live telemetry is depicted.</desc>
<defs>
 <linearGradient id="case" x1="0" x2="1"><stop stop-color="{case[2]}"/><stop offset=".035" stop-color="{case[1]}"/><stop offset=".15" stop-color="{case[0]}"/><stop offset=".65" stop-color="{case[3]}"/><stop offset=".94" stop-color="{case[0]}"/><stop offset="1" stop-color="{case[4]}"/></linearGradient>
 <linearGradient id="rim" x1="0" x2="1" y2=".75"><stop stop-color="#454a4c"/><stop offset=".04" stop-color="#f8faf9"/><stop offset=".11" stop-color="#919b9d"/><stop offset=".4" stop-color="#f1f4f2"/><stop offset=".6" stop-color="#5a6061"/><stop offset=".86" stop-color="#e9eeee"/><stop offset="1" stop-color="#60696a"/></linearGradient>
 <linearGradient id="key" x1="0" y1="0" x2=".12" y2="1"><stop stop-color="{control}"/><stop offset=".35" stop-color="{face}"/><stop offset="1" stop-color="{control}"/></linearGradient>
 <linearGradient id="glass" x1="0" y1="0" x2=".85" y2="1"><stop stop-color="#263033"/><stop offset=".32" stop-color="#0a0f12"/><stop offset=".75" stop-color="#03070a"/><stop offset="1" stop-color="#151c20"/></linearGradient>
 <linearGradient id="reflection" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#fff" stop-opacity=".13"/><stop offset=".46" stop-color="#fff" stop-opacity=".015"/><stop offset=".49" stop-color="#fff" stop-opacity=".09"/><stop offset=".5" stop-color="#fff" stop-opacity="0"/><stop offset="1" stop-color="#fff" stop-opacity=".015"/></linearGradient>
 <radialGradient id="lens"><stop stop-color="#476d7a"/><stop offset=".3" stop-color="#17282f"/><stop offset=".58" stop-color="#090e12"/><stop offset=".8" stop-color="#303d44"/><stop offset="1" stop-color="#05080a"/></radialGradient>
 <pattern id="grille" width="10" height="10" patternUnits="userSpaceOnUse"><path d="M0 0L10 10M10 0L0 10" stroke="#c4c8c6" stroke-width="1.4"/></pattern>
 <pattern id="brushing" width="5" height="7" patternUnits="userSpaceOnUse"><path d="M0 1H5M0 5H5" stroke="#fff" stroke-opacity=".07" stroke-width=".7"/></pattern>
 <clipPath id="bodyClip"><rect x="25" y="14" width="950" height="1840" rx="84"/></clipPath>
 <clipPath id="screenClip"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9"/></clipPath>
</defs>
<g id="slider-rail"><path d="M24 85Q5 88 6 145V1737Q8 1803 43 1809L55 85Z" fill="{'#121417' if eight else '#503c4e'}"/><path d="M968 90Q992 95 991 148V1745L972 1810Z" fill="#1b2023"/><path d="M20 366V1510" stroke="#31343b" stroke-width="6"/></g>
<g id="case"><rect x="25" y="14" width="950" height="1840" rx="84" fill="url(#case)" stroke="#4a5052" stroke-width="3"/><rect x="37" y="24" width="925" height="1818" rx="75" fill="none" stroke="{'#777e85' if eight else '#fff'}" stroke-opacity=".65" stroke-width="3"/><path d="M60 77Q60 42 105 40H893Q936 43 939 93" fill="none" stroke="#fff" stroke-opacity=".4" stroke-width="4"/></g>
<g id="brushed-texture" clip-path="url(#bodyClip)"><rect x="28" y="20" width="943" height="1825" fill="url(#brushing)"/></g>
<g id="brand" fill="{'#d8dce0' if eight else '#313838'}" font-family="Arial,Helvetica,sans-serif">
 <text x="107" y="132" font-size="{'36' if eight else '51'}" font-weight="{'500' if eight else '900'}" letter-spacing="{'1' if eight else '-1.7'}">{'N95 8GB' if eight else 'NOKIA'}</text>
 {'' if eight else '<text x="214" y="187" font-size="34" letter-spacing="1">N95</text>'}
</g>
<g id="earpiece"><rect x="496" y="99" width="165" height="43" rx="18" fill="url(#rim)"/><rect x="504" y="107" width="149" height="26" rx="12" fill="#22282b"/><rect x="509" y="111" width="139" height="18" rx="8" fill="url(#grille)"/></g>
<g id="camera-sensor"><rect x="699" y="108" width="37" height="37" rx="10" fill="url(#rim)"/><rect x="707" y="115" width="21" height="24" rx="6" fill="#9ca999"/>
 <rect x="769" y="82" width="106" height="110" rx="33" fill="url(#rim)"/><rect x="777" y="89" width="90" height="96" rx="26" fill="#0a0e11"/><circle cx="822" cy="137" r="30" fill="url(#lens)"/><circle cx="822" cy="137" r="10" fill="#040809"/><circle cx="812" cy="124" r="5" fill="#9dced9" opacity=".5"/></g>
<g id="screen"><rect x="{x-12}" y="{y-12}" width="{w+24}" height="{h+24}" rx="17" fill="#596162"/><rect x="{x-6}" y="{y-6}" width="{w+12}" height="{h+12}" rx="12" fill="#03070a"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="url(#glass)"/><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="9" fill="url(#reflection)"/><path d="M{x+8} {y+h-2}H{x+w-8}" stroke="#b0bcc2" stroke-opacity=".25" stroke-width="2"/></g>
'''
    # Different physical nav geometry, not a recolour: 8GB has a compact black/chrome assembly and larger display.
    top=1414 if eight else 1360
    ch=374 if eight else 431
    svg+=f'''<g id="navigation"><rect x="111" y="{top}" width="778" height="{ch}" rx="67" fill="url(#rim)" stroke="#30383b" stroke-width="4"/><rect x="124" y="{top+14}" width="752" height="{ch-28}" rx="53" fill="#0c1115"/>
 <path d="M141 {top+48}Q144 {top+26} 177 {top+26}H363V{top+ch-82}H177Q141 {top+ch-82} 141 {top+ch-120}Z" fill="url(#key)" stroke="#81898a" stroke-width="2"/>
 <path d="M637 {top+26}H818Q855 {top+28} 856 {top+58}V{top+ch-119}Q855 {top+ch-82} 820 {top+ch-82}H637Z" fill="url(#key)" stroke="#81898a" stroke-width="2"/>
 <rect x="367" y="{top+23}" width="266" height="{ch-99}" rx="64" fill="url(#key)" stroke="#80898b" stroke-width="3"/>
 <rect x="428" y="{top+98}" width="144" height="{ch-247}" rx="37" fill="url(#rim)"/>
 <rect x="442" y="{top+112}" width="116" height="{ch-275}" rx="27" fill="{'#1d242a' if eight else '#bcc0bc'}" stroke="#3a4549" stroke-width="3"/>
 <g stroke="{ink}" stroke-width="7" stroke-linecap="round"><path d="M489 {top+64}H511M489 {top+ch-115}H511M401 {top+167}V{top+191}M599 {top+167}V{top+191}"/></g>
</g>
<g id="softkeys"><path d="M72 {top+30}Q72 {top-8} 106 {top-10}H108V{top+168}H71Z" fill="url(#key)" stroke="#7d8588" stroke-width="2"/><path d="M892 {top-10}H903Q932 {top-8} 932 {top+34}V{top+168}H892Z" fill="url(#key)" stroke="#7d8588" stroke-width="2"/>
 <path d="M91 {top+62}V{top+117}M914 {top+62}V{top+117}" stroke="{ink}" stroke-width="8" stroke-linecap="round"/>
 <path d="M71 {top+178}H108V{top+ch-33}Q72 {top+ch-35} 71 {top+ch-75}Z" fill="url(#key)" stroke="#7d8588" stroke-width="2"/><path d="M892 {top+178}H932V{top+ch-75}Q930 {top+ch-34} 892 {top+ch-33}Z" fill="url(#key)" stroke="#7d8588" stroke-width="2"/>
 <path d="M91 {top+219}V{top+ch-95}Q91 {top+ch-74} 109 {top+ch-75}" fill="none" stroke="#168c72" stroke-width="9" stroke-linecap="round"/>
 <path d="M913 {top+219}V{top+ch-95}Q913 {top+ch-74} 895 {top+ch-75}" fill="none" stroke="#b44b4a" stroke-width="9" stroke-linecap="round"/>
</g>
<g id="system-keys" fill="none" stroke="{'#a9c4d3' if eight else '#398099'}" stroke-width="9" stroke-linejoin="round">
 <path d="M237 {top+132}l-19 18 19 20M258 {top+132}l19 18-19 20M237 {top+178}l-19 18 19 20M258 {top+178}l19 18-19 20"/>
 <path d="M743 {top+149}l-25 27 25 28M762 {top+149}l25 27-25 28" stroke="{ink}"/>
</g>
<g id="edit-clear-keys"><path d="M155 {top+ch-69}H846V{top+ch-29}H155Z" fill="url(#key)" stroke="#778082" stroke-width="2"/>
 <path d="M233 {top+ch-58}l25 20-7 8-25-20Z M225 {top+ch-51}l-4 17 15 3" fill="none" stroke="{ink}" stroke-width="5"/>
 <text x="742" y="{top+ch-32}" fill="{ink}" font-family="Arial,sans-serif" font-size="35">C</text>
</g>
<path id="bottom-highlight" d="M89 1807Q500 1840 914 1807" fill="none" stroke="{'#69737b' if eight else '#f4f6f2'}" stroke-width="3" stroke-opacity=".65"/>
</svg>'''
    (ROOT/(key+'.svg')).write_text('\n'.join(line.rstrip() for line in svg.splitlines())+'\n',encoding='utf-8')

if __name__=='__main__':
    draw(False)
    draw(True)
