# TRINETRA data folder

Nothing in here except this file and `.gitkeep` markers is tracked by Git.
Create the folders with `python ml/scripts/init_data_layout.py`.

| Folder | Contents | Size | Lives where |
|---|---|---|---|
| raw/imd_best_track | IMD RSMC best-track (cyclone tracks + intensity) | small | local + Drive |
| raw/ibtracs | NOAA IBTrACS North Indian Ocean (cross-check) | small | local + Drive |
| raw/mosdac/insat3d | INSAT-3D/3DR satellite imagery | large | Drive only |
| raw/mosdac/oscat | OSCAT scatterometer winds | medium | Drive only |
| raw/era5 | ERA5 reanalysis fields (NetCDF) | large | Drive only |
| interim | cleaned / aligned data | varies | Drive |
| processed | model-ready data | varies | Drive |

Rule: raw/ is never edited by hand. Fixes happen in code, output goes to interim/.

## Dataset status
| Dataset | Account needed | Status |
|---|---|---|
| IMD best-track (1982-2026 workbook) | none | Steps 2 + 4: download, verify, build storm list |
| IBTrACS (backup) | none | not downloaded |
| MOSDAC INSAT-3D/3DR + OSCAT | MOSDAC registration | account not requested |
| ERA5 | Copernicus CDS account + API key | account not requested |
