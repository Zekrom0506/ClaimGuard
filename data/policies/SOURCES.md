# Coverage policy sources

ClaimGuard reads every PDF in this folder. Real policy PDFs are **not committed**
(they are in `.gitignore`); download them yourself from the links below and
record the date you downloaded each one.

## Included in the repository

| File | Source | Notes |
|---|---|---|
| `sample_lumbar_mri_policy.md` (built into `sample_lumbar_mri_policy.pdf` by `scripts/build_sample_policy.py`) | Written for this project | **SYNTHETIC.** A simplified policy modelled on the criteria that appear in public lumbar MRI policies (red flags, six weeks of conservative care, repeat imaging rules). The 40 evaluation labels refer to its section numbers, so evaluation results stay reproducible. It is not any insurer's real policy. |

## Public policies to download

| Policy | Where to find it | What to search for | Downloaded on |
|---|---|---|---|
| Medicare LCD L34220 "Lumbar MRI" (Noridian, Jurisdiction E) | [Medicare Coverage Database](https://www.cms.gov/medicare-coverage-database/search.aspx) | `L34220` → open the LCD → "Download" → PDF | |
| Medicare LCD L37281 "Lumbar MRI" (Noridian, Jurisdiction F) | Medicare Coverage Database | `L37281` | |
| Medicare NCD 220.2 "Magnetic Resonance Imaging" | Medicare Coverage Database | `220.2` (national rules that apply to every MRI) | |
| BCBS Louisiana "MRI Lumbar Spine" (MNG-018) | [providers.bcbsla.com](https://providers.bcbsla.com/-/media/Files/Providers/Blue%20Advantage%20Resources/2024-06%20MRI%20Lumbar%20Spine%20MNG-018%20pdf.pdf) | "MRI Lumbar Spine MNG-018" | |
| Kaiser Permanente Washington "MRI Lumbar Spine" criteria | [wa-provider.kaiserpermanente.org](https://wa-provider.kaiserpermanente.org/static/pdf/hosting/clinical/criteria/pdf/mri_lumbar%20spine.pdf) | "Kaiser Permanente Washington clinical review criteria MRI lumbar spine" | |
| HealthHelp "MRI Lumbar Spine" guideline | [healthhelp.com](https://www.healthhelp.com/wp-content/uploads/MRI-LSpine-HH_20251107.pdf) | "HealthHelp MRI lumbar spine guideline" | |

Other places worth searching: eviCore "Spine Imaging Guidelines" and Carelon
"Imaging of the Spine" clinical appropriateness guidelines (both used by large
US insurers for prior authorization).

Medicare documents are US government works. Commercial insurer policies are
published for providers; keep them local and do not redistribute them.
