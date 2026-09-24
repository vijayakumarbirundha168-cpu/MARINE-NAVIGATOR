import os, re, math, json, threading, webbrowser
from datetime import datetime, timezone
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs, urlencode
from urllib.request import Request, urlopen

PORT = int(os.environ.get("PORT", "8093"))
BASE = os.path.dirname(os.path.abspath(__file__))

SEALAGOM = "https://www.sealagom.com/coastal/HYDROLANT/HYDROLANT/"
WEATHER = "https://api.open-meteo.com/v1/forecast"
MARINE = "https://marine-api.open-meteo.com/v1/marine"

LATEST_FALLBACK = {
    "id": "D33A",
    "lat": -64.03,
    "lon": -55.65,
    "observed_at": "2026-09-22T05:55:00Z",
    "source": "HYDROLANT 1877/26 fallback",
    "source_live": False
}

SIZE = {
    "length_nm": 19.0,
    "width_nm": 10.0,
    "length_m": 35188,
    "width_m": 18520,
    "size_date": "2026-06-21",
    "size_source": "U.S. National Ice Center"
}

TRACK = [
    {"date":"2026-09-03","lat":-64.04,"lon":-(55+53.4/60),"source":"HYDROLANT 1740/26"},
    {"date":"2026-09-08","lat":-(64+1.8/60),"lon":-55.60,"source":"HYDROLANT 1782/26"},
    {"date":"2026-09-14","lat":-64.00,"lon":-(55+35.4/60),"source":"HYDROLANT 1817/26"},
    {"date":"2026-09-20","lat":-(64+1.8/60),"lon":-55.65,"source":"HYDROLANT 1860/26"},
    {"date":"2026-09-21","lat":-(64+1.8/60),"lon":-55.65,"source":"HYDROLANT 1870/26"},
    {"date":"2026-09-22","lat":-(64+1.8/60),"lon":-55.65,"source":"HYDROLANT 1877/26"},
]

def fetch_text(url, timeout=7):
    req = Request(url, headers={"User-Agent":"PhantomStrikers-Navigation/3.0"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="replace")

def fetch_json(base, params, timeout=7):
    return json.loads(fetch_text(base + "?" + urlencode(params), timeout=timeout))

def dm_to_dec(deg, mins, hemi):
    v = float(deg) + float(mins)/60.0
    return -v if hemi.upper() in ("S","W") else v

def latest_hydrolant():
    try:
        text = re.sub(r"\s+", " ", fetch_text(SEALAGOM, timeout=7))
        # Example: 240000Z SEP 26 ... D33A, 64-01.80S 055-39.00W.
        matches = re.findall(
            r"(\d{2})(\d{4})Z\s+SEP\s+26.*?D33A,\s*"
            r"(\d{2})-(\d{2}(?:\.\d+)?)S\s+"
            r"(\d{3})-(\d{2}(?:\.\d+)?)W",
            text, re.I
        )
        if matches:
            matches.sort(key=lambda x:(int(x[0]), int(x[1])), reverse=True)
            day,hm,latd,latm,lond,lonm = matches[0]
            hh,mm = int(hm[:2]), int(hm[2:])
            return {
                "id":"D33A",
                "lat":dm_to_dec(latd,latm,"S"),
                "lon":dm_to_dec(lond,lonm,"W"),
                "observed_at":f"2026-09-{int(day):02d}T{hh:02d}:{mm:02d}:00Z",
                "source":"Latest HYDROLANT warning via SeaLagom",
                "source_live":True
            }
    except Exception:
        pass
    return dict(LATEST_FALLBACK)

def hav_nm(lat1,lon1,lat2,lon2):
    R=3440.065
    p1,p2=math.radians(lat1),math.radians(lat2)
    dp=math.radians(lat2-lat1)
    dl=math.radians(lon2-lon1)
    a=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(max(0,min(1,a))))

def bearing(lat1,lon1,lat2,lon2):
    p1,p2=math.radians(lat1),math.radians(lat2)
    dl=math.radians(lon2-lon1)
    y=math.sin(dl)*math.cos(p2)
    x=math.cos(p1)*math.sin(p2)-math.sin(p1)*math.cos(p2)*math.cos(dl)
    return (math.degrees(math.atan2(y,x))+360)%360

def compass(deg):
    dirs=["N","NE","E","SE","S","SW","W","NW"]
    return dirs[int((deg+22.5)//45)%8] if isinstance(deg,(int,float)) else "N/A"

def vec_from_bearing(speed, deg):
    r=math.radians(deg)
    return speed*math.sin(r), speed*math.cos(r)  # east, north

def bearing_from_vec(e,n):
    return (math.degrees(math.atan2(e,n))+360)%360

def linear_track_velocity():
    # Least-squares regression of latitude and longitude against days.
    t=[]
    lat=[]
    lon=[]
    d0=datetime.fromisoformat(TRACK[0]["date"]+"T00:00:00+00:00")
    for p in TRACK:
        dt=datetime.fromisoformat(p["date"]+"T00:00:00+00:00")
        t.append((dt-d0).total_seconds()/86400)
        lat.append(p["lat"])
        lon.append(p["lon"])
    def slope(xs,ys):
        xm=sum(xs)/len(xs); ym=sum(ys)/len(ys)
        den=sum((x-xm)**2 for x in xs) or 1
        return sum((x-xm)*(y-ym) for x,y in zip(xs,ys))/den
    slat=slope(t,lat)   # deg/day
    slon=slope(t,lon)
    mlat=sum(lat)/len(lat)
    north_nm_day=slat*60
    east_nm_day=slon*60*max(.15,math.cos(math.radians(mlat)))
    speed_kn=math.hypot(east_nm_day,north_nm_day)/24
    brg=bearing_from_vec(east_nm_day,north_nm_day)
    return {
        "speed_kn":round(speed_kn,3),
        "speed_nm_day":round(speed_kn*24,2),
        "bearing_deg":round(brg,1),
        "direction":compass(brg),
        "method":"Linear regression over reported HYDROLANT track"
    }

def get_environment(lat,lon):
    out={"weather":{},"marine":{},"health":{"weather":False,"marine":False}}
    try:
        j=fetch_json(WEATHER,{
            "latitude":lat,"longitude":lon,
            "current":"temperature_2m,apparent_temperature,relative_humidity_2m,pressure_msl,wind_speed_10m,wind_direction_10m,wind_gusts_10m,cloud_cover,precipitation,snowfall",
            "hourly":"visibility",
            "wind_speed_unit":"kn","timezone":"GMT","forecast_hours":3,"cell_selection":"sea"
        })
        c=j.get("current",{}); h=j.get("hourly",{})
        vis=(h.get("visibility") or [None])[0]
        out["weather"]={
            "temperature_c":c.get("temperature_2m"),
            "apparent_c":c.get("apparent_temperature"),
            "humidity_pct":c.get("relative_humidity_2m"),
            "pressure_hpa":c.get("pressure_msl"),
            "wind_kn":c.get("wind_speed_10m"),
            "wind_dir_deg":c.get("wind_direction_10m"),
            "gust_kn":c.get("wind_gusts_10m"),
            "cloud_pct":c.get("cloud_cover"),
            "precip_mm":c.get("precipitation"),
            "snow_cm":c.get("snowfall"),
            "visibility_km":round(vis/1000,1) if isinstance(vis,(int,float)) else None,
            "time":c.get("time")
        }
        out["health"]["weather"]=True
    except Exception:
        pass
    try:
        j=fetch_json(MARINE,{
            "latitude":lat,"longitude":lon,
            "current":"wave_height,wave_direction,wave_period,swell_wave_height,swell_wave_direction,swell_wave_period,sea_surface_temperature,ocean_current_velocity,ocean_current_direction",
            "timezone":"GMT","cell_selection":"sea","wind_speed_unit":"kn"
        })
        c=j.get("current",{})
        out["marine"]={
            "wave_height_m":c.get("wave_height"),
            "wave_direction_deg":c.get("wave_direction"),
            "wave_period_s":c.get("wave_period"),
            "swell_height_m":c.get("swell_wave_height"),
            "swell_direction_deg":c.get("swell_wave_direction"),
            "swell_period_s":c.get("swell_wave_period"),
            "sst_c":c.get("sea_surface_temperature"),
            "current_kn":c.get("ocean_current_velocity"),
            "current_direction_deg":c.get("ocean_current_direction"),
            "time":c.get("time")
        }
        out["health"]["marine"]=True
    except Exception:
        pass
    return out

def fused_iceberg_velocity(track_vel, env):
    # Physics-informed data fusion:
    # 55% data-driven historical regression + 35% current advection
    # + 10% windage component (windage approximated at 2% of wind speed).
    he,hn=vec_from_bearing(track_vel["speed_kn"], track_vel["bearing_deg"])
    m=env.get("marine",{})
    w=env.get("weather",{})
    cs=m.get("current_kn") if isinstance(m.get("current_kn"),(int,float)) else 0.0
    cd=m.get("current_direction_deg") if isinstance(m.get("current_direction_deg"),(int,float)) else track_vel["bearing_deg"]
    ce,cn=vec_from_bearing(cs,cd)
    ws=w.get("wind_kn") if isinstance(w.get("wind_kn"),(int,float)) else 0.0
    wd=w.get("wind_dir_deg") if isinstance(w.get("wind_dir_deg"),(int,float)) else 0.0
    # Meteorological wind direction is FROM; iceberg windage is roughly toward opposite direction.
    we,wn=vec_from_bearing(ws*0.02,(wd+180)%360)
    e=0.55*he+0.35*ce+0.10*we
    n=0.55*hn+0.35*cn+0.10*wn
    speed=math.hypot(e,n)
    brg=bearing_from_vec(e,n) if speed>1e-8 else track_vel["bearing_deg"]
    return {"east_kn":e,"north_kn":n,"speed_kn":speed,"bearing_deg":brg,"direction":compass(brg)}

def destination_point(lat,lon,bearing_deg,distance_nm):
    R=3440.065
    brg=math.radians(bearing_deg); d=distance_nm/R
    p1=math.radians(lat); l1=math.radians(lon)
    p2=math.asin(math.sin(p1)*math.cos(d)+math.cos(p1)*math.sin(d)*math.cos(brg))
    l2=l1+math.atan2(math.sin(brg)*math.sin(d)*math.cos(p1),math.cos(d)-math.sin(p1)*math.sin(p2))
    return {"lat":math.degrees(p2),"lon":((math.degrees(l2)+540)%360)-180}

def prediction_bundle(latest, vel, source_live, env_health):
    base_conf=86 if source_live else 70
    if not env_health.get("weather"): base_conf-=5
    if not env_health.get("marine"): base_conf-=8
    result={}
    for h,loss,unc in [(6,0,4.0),(12,8,7.5),(24,18,14.0)]:
        p=destination_point(latest["lat"],latest["lon"],vel["bearing_deg"],vel["speed_kn"]*h)
        result[str(h)]={
            "lat":round(p["lat"],5),"lon":round(p["lon"],5),
            "uncertainty_nm":round(unc*(1+(100-base_conf)/100),1),
            "confidence_pct":max(35,base_conf-loss)
        }
    return result

def local_xy_nm(origin, p):
    north=(p["lat"]-origin["lat"])*60
    east=(p["lon"]-origin["lon"])*60*max(.15,math.cos(math.radians((p["lat"]+origin["lat"])/2)))
    return east,north

def dcpa_tcpa(vessel, iceberg, vessel_speed, vessel_heading, ice_speed, ice_heading):
    rx,ry=local_xy_nm(vessel,iceberg)
    ve,vn=vec_from_bearing(vessel_speed,vessel_heading)
    ie,in_=vec_from_bearing(ice_speed,ice_heading)
    vx,vy=ie-ve,in_-vn
    vv=vx*vx+vy*vy
    if vv<1e-9:
        return {"dcpa_nm":round(math.hypot(rx,ry),2),"tcpa_h":None}
    t=-(rx*vx+ry*vy)/vv
    if t<0:
        dcpa=math.hypot(rx,ry)
        return {"dcpa_nm":round(dcpa,2),"tcpa_h":round(t,2)}
    dcpa=math.hypot(rx+vx*t,ry+vy*t)
    return {"dcpa_nm":round(dcpa,2),"tcpa_h":round(t,2)}

def collision_risk(dcpa, tcpa, sea_ice_pct=None, wave_m=None):
    if tcpa is None:
        base=45
    elif tcpa < 0:
        base=20
    else:
        # Strongly weight near-term closest approach.
        base=max(0,100-dcpa*4)
        if tcpa<=6: base+=20
        elif tcpa<=12: base+=10
        elif tcpa>24: base-=15
    if isinstance(sea_ice_pct,(int,float)):
        base += max(0,min(15,sea_ice_pct*0.15))
    if isinstance(wave_m,(int,float)):
        base += max(0,min(10,wave_m*2))
    score=max(0,min(100,base))
    level="HIGH" if score>=70 else "MEDIUM" if score>=40 else "LOW"
    return round(score,1),level

def astar(start,goal,hazard,avoid_radius_nm):
    step=.045
    minlat=min(start["lat"],goal["lat"],hazard["lat"])-.55
    maxlat=max(start["lat"],goal["lat"],hazard["lat"])+.55
    minlon=min(start["lon"],goal["lon"],hazard["lon"])-.85
    maxlon=max(start["lon"],goal["lon"],hazard["lon"])+.85
    rows=int((maxlat-minlat)/step)+2; cols=int((maxlon-minlon)/step)+2
    # safety cap
    if rows*cols>140000:
        step=.07
        rows=int((maxlat-minlat)/step)+2; cols=int((maxlon-minlon)/step)+2
    def idx(p): return (round((p["lat"]-minlat)/step),round((p["lon"]-minlon)/step))
    def coord(n): return {"lat":minlat+n[0]*step,"lon":minlon+n[1]*step}
    s,g=idx(start),idx(goal)
    moves=[(-1,-1),(-1,0),(-1,1),(0,-1),(0,1),(1,-1),(1,0),(1,1)]
    def hz(n):
        p=coord(n); return hav_nm(p["lat"],p["lon"],hazard["lat"],hazard["lon"])
    def heur(n):
        p=coord(n); return hav_nm(p["lat"],p["lon"],goal["lat"],goal["lon"])
    import heapq
    pq=[(heur(s),0,s)]; best={s:0}; came={}; seen=set()
    while pq:
        _,cost,n=heapq.heappop(pq)
        if n in seen: continue
        seen.add(n)
        if n==g: break
        for di,dj in moves:
            nb=(n[0]+di,n[1]+dj)
            if not(0<=nb[0]<rows and 0<=nb[1]<cols): continue
            if nb not in (s,g) and hz(nb)<avoid_radius_nm: continue
            a,b=coord(n),coord(nb)
            base=hav_nm(a["lat"],a["lon"],b["lat"],b["lon"])
            d=hz(nb)
            penalty=max(0,avoid_radius_nm*1.6-d)*.12 if d<avoid_radius_nm*1.6 else 0
            nc=cost+base+penalty
            if nc<best.get(nb,1e99):
                best[nb]=nc; came[nb]=n
                heapq.heappush(pq,(nc+heur(nb),nc,nb))
    if g not in came:
        return [start,goal]
    nodes=[g]
    while nodes[-1]!=s:
        nodes.append(came[nodes[-1]])
    nodes.reverse()
    route=[coord(n) for k,n in enumerate(nodes) if k==0 or k==len(nodes)-1 or k%3==0]
    route[0]=start; route[-1]=goal
    return route

def route_dist(route):
    return sum(hav_nm(a["lat"],a["lon"],b["lat"],b["lon"]) for a,b in zip(route,route[1:]))

def min_clearance(route,hazard):
    return min(hav_nm(p["lat"],p["lon"],hazard["lat"],hazard["lon"]) for p in route)

def make_route_option(name, route, hazard, speed_kn, base_direct):
    dist=route_dist(route)
    clearance=min_clearance(route,hazard)
    eta=dist/max(1,speed_kn)
    risk="HIGH" if clearance<15 else "MEDIUM" if clearance<30 else "LOW"
    fuel_proxy=100*(dist/max(.1,base_direct))*(speed_kn/15)**2
    return {
        "name":name,"route":route,
        "distance_nm":round(dist,1),
        "eta_h":round(eta,2),
        "clearance_nm":round(clearance,1),
        "risk":risk,
        "fuel_proxy":round(fuel_proxy,0)
    }

def dashboard_payload(q):
    latest=latest_hydrolant()
    env=get_environment(latest["lat"],latest["lon"])
    track_vel=linear_track_velocity()
    fused=fused_iceberg_velocity(track_vel,env)
    preds=prediction_bundle(latest,fused,latest.get("source_live",False),env["health"])

    start={"lat":float(q.get("start_lat",[-64.0])[0]),"lon":float(q.get("start_lon",[-57.0])[0])}
    goal={"lat":float(q.get("dest_lat",[-64.0])[0]),"lon":float(q.get("dest_lon",[-54.2])[0])}
    vessel_speed=max(1,float(q.get("vessel_speed",[15])[0]))
    vessel_heading=float(q.get("vessel_heading",[90])[0])%360
    sea_ice_raw=q.get("sea_ice_pct",[""])[0].strip()
    sea_ice_pct=float(sea_ice_raw) if sea_ice_raw not in ("","null","None") else None

    cpa=dcpa_tcpa(start,latest,vessel_speed,vessel_heading,fused["speed_kn"],fused["bearing_deg"])
    wave=env.get("marine",{}).get("wave_height_m")
    risk_score,risk_level=collision_risk(cpa["dcpa_nm"],cpa["tcpa_h"],sea_ice_pct,wave)

    direct=[start,goal]
    route_b=astar(start,goal,preds["12"],30)
    route_c=astar(start,goal,preds["24"],45)
    direct_dist=route_dist(direct)
    options=[
        make_route_option("A · Direct",direct,preds["12"],vessel_speed,direct_dist),
        make_route_option("B · Safer",route_b,preds["12"],vessel_speed,direct_dist),
        make_route_option("C · Conservative",route_c,preds["24"],vessel_speed,direct_dist),
    ]
    risk_pen={"LOW":0,"MEDIUM":120,"HIGH":300}
    for o in options:
        o["cost"]=o["distance_nm"]+risk_pen[o["risk"]]+0.08*o["fuel_proxy"]
    recommended=min(options,key=lambda x:x["cost"])
    for o in options:
        o["recommended"]=(o["name"]==recommended["name"])
        o.pop("cost",None)

    half_diag=.5*math.sqrt(SIZE["length_nm"]**2+SIZE["width_nm"]**2)
    return {
        "generated_at":datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sources":{
            "iceberg":{"ok":latest.get("source_live",False),"label":"HYDROLANT latest" if latest.get("source_live") else "HYDROLANT fallback"},
            "weather":{"ok":env["health"]["weather"],"label":"Open-Meteo weather"},
            "ocean":{"ok":env["health"]["marine"],"label":"Open-Meteo marine"},
            "sea_ice":{"ok":sea_ice_pct is not None,"label":"User / latest external sea-ice input"},
            "vessel":{"ok":q.get("gps_live",["0"])[0]=="1","label":"Browser GPS" if q.get("gps_live",["0"])[0]=="1" else "Manual vessel input"}
        },
        "fusion":{
            "coordinate_system":"WGS84",
            "time_basis":"UTC",
            "common_reference":"Lat/Lon + UTC",
            "last_update":datetime.now(timezone.utc).isoformat(timespec="seconds")
        },
        "iceberg":{
            **latest,**SIZE,
            "track":TRACK,
            "data_driven_velocity":track_vel,
            "fused_velocity":{
                "speed_kn":round(fused["speed_kn"],3),
                "bearing_deg":round(fused["bearing_deg"],1),
                "direction":fused["direction"]
            },
            "prediction":preds,
            "model":"Data-driven regression + wind/current physics correction",
            "high_risk_radius_nm":round(half_diag+5,1),
            "medium_risk_radius_nm":30,
            "low_risk_radius_nm":50
        },
        "environment":{
            **env,
            "sea_ice_pct":sea_ice_pct,
            "sea_ice_source":"User/latest external product" if sea_ice_pct is not None else "Not connected"
        },
        "vessel":{
            "lat":start["lat"],"lon":start["lon"],
            "speed_kn":vessel_speed,"heading_deg":vessel_heading,
            "gps_live":q.get("gps_live",["0"])[0]=="1"
        },
        "collision":{
            **cpa,
            "risk_score_pct":risk_score,
            "risk_level":risk_level
        },
        "routes":{
            "options":options,
            "recommended_name":recommended["name"]
        }
    }

class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        # Serve files only from project directory.
        parsed=urlparse(path).path
        if parsed=="/":
            parsed="/index.html"
        clean=os.path.normpath(parsed.lstrip("/"))
        return os.path.join(BASE,clean)

    def end_headers(self):
        self.send_header("Cache-Control","no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma","no-cache")
        self.send_header("Expires","0")
        super().end_headers()

    def do_GET(self):
        u=urlparse(self.path)
        if u.path=="/api/dashboard":
            try:
                payload=dashboard_payload(parse_qs(u.query))
                body=json.dumps(payload).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            except Exception as e:
                body=json.dumps({"error":str(e)}).encode("utf-8")
                self.send_response(500)
                self.send_header("Content-Type","application/json; charset=utf-8")
                self.send_header("Content-Length",str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            return
        return super().do_GET()

if __name__=="__main__":
    os.chdir(BASE)
    url=f"http://127.0.0.1:{PORT}/"
    print("="*72)
    print("PHANTOM STRIKERS - AI-ENABLED ANTARCTIC NAVIGATION DASHBOARD")
    print("No pip install required.")
    print("Open:",url)
    print("Keep this terminal open while using the dashboard.")
    print("="*72)
    if os.environ.get("RENDER") is None:
        threading.Timer(1.0,lambda:webbrowser.open(url)).start()
    ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
