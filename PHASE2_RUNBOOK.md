# TRINETRA Phase 2 runbook

Unzip into the repo root keeping folder paths. This overwrites `.gitignore`,
`ml/requirements.txt` and `ml/data/README.md` (check `git diff` if you edited them).

## Two ways to run
**A. Colab, no laptop:** open `ml/notebooks/phase2_data_colab.ipynb` in Colab, upload
this zip when asked, run cells top to bottom. Data lands in Drive `trinetra_data/`.
**B. Windows laptop** (commands below). Small files only locally; big MOSDAC data
should still go to Drive via Colab.

## Files
| Path | Step | Purpose |
|---|---|---|
| .gitignore | 1 | ignore data under ml/data/ except README + .gitkeep |
| ml/scripts/init_data_layout.py | 1 | create data folders |
| ml/scripts/fetch_imd_best_track.py | 2 | download + verify IMD workbook, write SOURCE.txt |
| ml/configs/mosdac_request_spec.yaml | 3 | plan: satellites, bands, AOI, windows (TO_VERIFY items) |
| ml/scripts/build_storm_list.py | 4 | workbook -> tidy fixes, storms.csv, mosdac_order_windows.csv |
| ml/scripts/mosdac_sftp_pull.py | 5 | copy MOSDAC orders from SFTP into Drive |
| ml/scripts/verify_raw_data.py | 6 | hash check, inventory, coverage per storm |
| ml/notebooks/phase2_data_colab.ipynb | all | run the above from Colab |
| ml/requirements.txt, ml/data/README.md | - | updated deps / status table |

## Windows commands (repo root)
```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install openpyxl pyyaml pandas
python ml/scripts/init_data_layout.py                       # step 1
python ml/scripts/fetch_imd_best_track.py                   # step 2 (or --inspect-only after manual download)
python ml/scripts/build_storm_list.py                       # step 4 - READ the column mapping it prints
```
Step 3: log in to mosdac.gov.in > Order Data, note INSAT-3D/3DR L1B band names, formats,
earliest date; fill the TO_VERIFY lines in the yaml.
Step 5: place the order using `interim/mosdac_order_windows.csv` (start with ONE storm, TIR1 only),
then run the SFTP pull from Colab. Step 6 afterwards.

## What was and was not tested
Tested only on synthetic data: init layout, IMD fetch (file:// URL), storm list (two layouts),
verify. NOT tested against the real IMD workbook, real MOSDAC site or SFTP server.
If anything fails or the column mapping looks wrong, send the printed output.

## Accounts (approval can take days)
MOSDAC (mosdac.gov.in) and Copernicus CDS (ERA5, later). Credentials in `.env` only.
