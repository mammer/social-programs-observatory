# Input data format

The app reads one UTF-8 CSV file, `data/raw/households.csv` by default (set `OBS_HOUSEHOLDS` to change it),
with one row per household. Do not include names, ID numbers, addresses or phone numbers: no analysis
uses them, so they should not be in the file at all.

| Column | Values | Required |
|---|---|---|
| `area` | Any label for the area (town, district…) | yes |
| `age` | Age of the head of household, in years | yes (may be blank) |
| `sex` | `F` or `M` | yes (may be blank) |
| `social_status` | `very_vulnerable`, `vulnerable`, `middle`, `well_off`, or blank if not assessed | yes |
| `health_cover` | `none`, `basic`, `contributory` | yes |
| `work_sector` | `informal`, `formal`, `no_work` | yes |
| `household_size` | Number of people living in the home | yes |
| `program_a` … `program_f` | `1` if the household received that programme, else `0` | yes |
| `family_status` | `married`, `widowed`, `single`, `divorced`, `abandoned`, `single_parent`, `other` | recommended |
| `health_status` | `healthy`, `chronic`, `serious`, `disability`, `elderly` | recommended |
| `children`, `n_disabled`, `n_chronic` | Counts | recommended |
| `head_of_household` | `1` or `0` | recommended |
| `aid_date` | `YYYY-MM-DD` of the first aid received | optional |
| `household_id` | Any row number | optional (not used) |

To use other programme names, keep the `program_a` … `program_f` columns and change their labels in
`observatory/web/i18n.js`. For a different number of programmes, edit `PROGRAMS` in `observatory/config.py`
and `analysis/stats.py`.

Areas with fewer than 50 households are left out of the area table, and areas with fewer than 100
assessed households are left out of the area-level PCA, so that small groups cannot be singled out.
