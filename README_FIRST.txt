PHANTOM STRIKERS — FULL REAL-TIME ANTARCTIC NAVIGATION DECISION SUPPORT

EASY RUN (WINDOWS)
1. Extract the ZIP completely.
2. Double-click START_DASHBOARD.bat.
3. Browser opens automatically at:
   http://127.0.0.1:8093/
4. For live vessel location, click "Start Live Vessel GPS" and allow location access.
5. Keep the terminal window open.

NO PIP INSTALL REQUIRED.
NO API KEY REQUIRED for the public weather/marine feeds used in this prototype.

WHAT IS INCLUDED
INTEGRATED DATA COLLECTION
- Latest D33A HYDROLANT position when reachable, with verified fallback
- D33A size metadata
- Weather: temperature, wind, visibility
- Ocean: current, waves, SST
- Vessel: browser GPS or manual coordinates/speed/heading
- Sea-ice concentration input slot (enter the latest NSIDC/Copernicus value)

INTEGRATED DATA FUSION
- WGS84 coordinates
- UTC time reference
- Source health/status cards

ICEBERG PREDICTION
- 6 h / 12 h / 24 h predicted D33A positions
- Uncertainty radius and confidence
- Transparent model: regression of historical reported positions plus current/wind correction

COLLISION RISK
- DCPA
- TCPA
- Risk score
- HIGH / MEDIUM / LOW warning

ROUTE OPTIMIZATION
- Route A: Direct
- Route B: Safer
- Route C: Conservative
- Distance
- ETA
- Clearance
- Risk
- Relative fuel proxy
- Recommended route highlighted

INTEGRATED DASHBOARD
- White + light-blue Phantom Strikers interface
- Common fused route view
- No countries/islands are drawn on the display

IMPORTANT DATA LABELS
- Browser GPS can be live.
- HYDROLANT / weather / ocean are latest available source data, not second-by-second.
- Sea-ice concentration is NOT invented. Enter a latest external value when available.
- This is a hackathon/research decision-support prototype, not a certified navigation system.
- The predictor is data-driven + physics-informed; it is not a trained production ML model yet.


GITHUB PAGES + RENDER DEPLOYMENT (FIX FOR JSON ERROR)
1. Upload index.html (and your static/ logo folder if used) to the GitHub Pages repository.
2. Deploy this same project to Render using render.yaml.
3. IMPORTANT: the Python filename must be app.py (not app(1).py).
4. The frontend is configured to call:
   https://phantom-strikers-antarctic-navigation.onrender.com/api/dashboard
5. After the first Render deployment, open that API URL in a browser. It must show JSON beginning with {, not <!DOCTYPE html>.
6. Then refresh the GitHub Pages dashboard.

WHY THE OLD VERSION FAILED
GitHub Pages is static hosting. The old index.html called /api/dashboard on github.io, so GitHub returned an HTML page/404. JavaScript then tried to parse that HTML as JSON, causing: Unexpected token '<'.
