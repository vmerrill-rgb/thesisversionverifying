# Project Rules: Quantitative Econometrics (Python & R)

## Environment & Paths
- Use relative project paths via `pathlib.Path` (Python) or `here::here()` (R). Never hardcode `C:\Users\...` or OneDrive paths.
- Never modify files in `data/raw/`. Write cleaned datasets to `data/clean/` and outputs to `output/tables/` and `output/figures/`.
- Declare all imports explicitly at the top of every `.py` script and `.ipynb` notebook (including `from IPython.display import display`).

## Econometrics & Language Parity (Python <-> R)
- Maintain schema, variable naming, and estimator parity between Python (`polars`, `pandas`, `pyfixest`, `statsmodels`) and R (`data.table`, `fixest`).
- Match fixed-effects absorption, sample filters, and clustered standard-error degrees-of-freedom corrections across languages.
- Log observation counts (`N`) before and after every join, drop, or sample restriction.

## LaTeX (.tex) & Figure Outputs
- Format all `.tex` tables with `booktabs` (`\toprule`, `\midrule`, `\bottomrule`, `\cmidrule`). Never use vertical rules (`|`) or `\hline`.
- Report standard errors in parentheses below point estimates, include observation count `N`, $R^2$ / fixed-effects indicators, and cluster level in table notes.
- Save plots headless (`dpi=300`) without blocking `plt.show()` calls.

## Git & Security
- Never stage, commit, or print `.env` files, API keys, or raw restricted datasets.
- Never run destructive Git commands (`git push --force`, `git reset --hard`) without explicit confirmation.
