"""
Environmental-spending study, extension: event study of regional decentralisation reforms.

Events are increases in the self-rule of regional governments in the Regional Authority Index (RAI, country
file of April 2021). Outcomes: the subnational share of environmental protection spending (first stage) and
ln PM2.5 exposure (reduced form). Estimator: imputation estimator of Borusyak, Jaravel and Spiess (2024),
with a country cluster bootstrap.

Run after env_federalism.py:
    python replication/environment/paperC_ext_es.py [--out DIR] [--rai FILE] [--reps 999]
Outputs (prefix es_): es_events.csv, es_results.json, es_eventtime.csv, es_figure.png/.pdf
"""
import argparse
import hashlib
import json
import sys
import urllib.request
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ANALYSIS = Path(__file__).resolve().parent
sys.path.insert(0, str(ANALYSIS))
import env_federalism as pc  # noqa: E402

RAI_URL = "https://garymarks.web.unc.edu/wp-content/uploads/sites/13018/2021/04/RAI_country-april-2021.xlsx"
RAI_SHA256 = "4ae1860a62b23ee0f0adaf5f33beb648d878642a7c5829a1d0a04203ed60c610"
SEED, KMIN, KMAX, NLEAD = 20261101, 0, 10, 5
GE_CUT, GE_CUT2 = 1.0, 0.2  # sign change of the marginal association; upper end of its significance range


# ---------------------------------------------------------------------------
# events
# ---------------------------------------------------------------------------

def read_rai(path: Path) -> pd.DataFrame:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        req = urllib.request.Request(RAI_URL, headers={"User-Agent": "cofog-panel replication"})
        path.write_bytes(urllib.request.urlopen(req, timeout=120).read())
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != RAI_SHA256:
        print(f"WARNING: {path.name} differs from the RAI file used (SHA-256 {digest[:12]}...)")
    r = pd.read_excel(path).rename(columns={"abbr_country": "ISO", "year": "YEAR"})
    return r.sort_values(["ISO", "YEAR"])


def code_events(r: pd.DataFrame, sample: set, threshold: float = 1.0) -> pd.DataFrame:
    """Treated: first qualifying increase in 1996-2018 without another one in the five years before.
    Never treated: no qualifying change, up or down, in 1991-2018. All others are dropped."""
    r = r[r["ISO"].isin(sample)].copy()
    r["d"] = r.groupby("ISO")["n_selfrule"].diff()
    rows = []
    for iso, g in r.groupby("ISO"):
        g = g[g["YEAR"].between(1991, 2018)]
        inc, dec = g[g["d"] >= threshold], g[g["d"] <= -threshold]
        win = inc[inc["YEAR"].between(1996, 2018)]
        first = int(win["YEAR"].min()) if len(win) else None
        prior = inc[inc["YEAR"].between(first - 5, first - 1)] if first else inc.iloc[0:0]
        if len(inc) == 0 and len(dec) == 0:
            status = "never"
        elif first and len(prior) == 0:
            status = "treated"
        else:
            status = "dropped"
        rows.append(dict(ISO=iso, status=status, E=first if status == "treated" else np.nan,
                         increases=" ".join(map(str, inc["YEAR"])), decreases=" ".join(map(str, dec["YEAR"]))))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# imputation estimator
# ---------------------------------------------------------------------------

def _fe_fit_predict(d: pd.DataFrame, y: str, unit: str, time: str):
    """Two-way FE fitted on untreated rows, predicted for all rows (NaN where a unit or time effect is missing)."""
    u = d["UNTREATED"].values
    units = pd.Index(d.loc[u, unit].unique())
    times = pd.Index(d.loc[u, time].unique())
    iu, it = units.get_indexer(d[unit]), times.get_indexer(d[time])
    X = np.zeros((len(d), len(units) + len(times)))
    ok = (iu >= 0) & (it >= 0)
    X[np.where(ok)[0], iu[ok]] = 1
    X[np.where(ok)[0], len(units) + it[ok]] = 1
    beta = np.linalg.lstsq(X[u], d.loc[u, y].values, rcond=None)[0]
    pred = X @ beta
    pred[~ok] = np.nan
    return pred


def impute(d: pd.DataFrame, y: str, time: str = "YEAR") -> pd.DataFrame:
    d = d.copy()
    d["K"] = d["YEAR"] - d["E"]
    d["UNTREATED"] = d["E"].isna() | (d["YEAR"] < d["E"])
    d["Y0"] = _fe_fit_predict(d, y, "UNIT", time)
    d["TAU"] = d[y] - d["Y0"]
    return d[(~d["UNTREATED"]) & d["K"].between(KMIN, KMAX) & d["TAU"].notna()]


def summarise(t: pd.DataFrame, groups: dict) -> dict:
    out = {"att": float(t["TAU"].mean()) if len(t) else np.nan}
    for k in range(KMIN, KMAX + 1):
        x = t.loc[t["K"] == k, "TAU"]
        out[f"k{k}"] = float(x.mean()) if len(x) else np.nan
    for name, units in groups.items():
        x = t.loc[t["ISO"].isin(units), "TAU"]
        out[f"att_{name}"] = float(x.mean()) if len(x) else np.nan
    if "low" in groups and "high" in groups:
        out["att_low_minus_high"] = out["att_low"] - out["att_high"]
    return out


def estimate(d: pd.DataFrame, y: str, groups: dict, reps: int, time: str = "YEAR") -> dict:
    d = d.assign(UNIT=d["ISO"])
    t = impute(d, y, time)
    point = summarise(t, groups)
    rng = np.random.default_rng(SEED)
    isos = d["ISO"].unique()
    by = {i: g for i, g in d.groupby("ISO")}
    draws = []
    for _ in range(reps):
        pick = rng.choice(isos, size=len(isos), replace=True)
        bd = pd.concat([by[i].assign(UNIT=f"{i}_{j}") for j, i in enumerate(pick)], ignore_index=True)
        draws.append(summarise(impute(bd, y, time), groups))
    draws = pd.DataFrame(draws)
    res = {}
    for key, val in point.items():
        x = draws[key].dropna()
        se = float(x.std(ddof=1)) if len(x) > 1 else np.nan
        res[key] = {"est": round(val, 4), "se": round(se, 4),
                    "p": round(float(2 * stats.norm.sf(abs(val / se))), 4) if se and se > 0 else None,
                    "ci95": [round(float(x.quantile(0.025)), 4), round(float(x.quantile(0.975)), 4)] if len(x) else None}
    res["n_treated_contributing"] = int(t["ISO"].nunique())
    for name, units in groups.items():
        res[f"n_{name}"] = int(t.loc[t["ISO"].isin(units), "ISO"].nunique())
    res["n_obs_effects"] = int(len(t))
    return res


def pretrend(d: pd.DataFrame, y: str) -> dict:
    """Borusyak et al. (2024) Test 1: leads k = -5..-1 on untreated observations, country and year effects."""
    from linearmodels.panel import PanelOLS
    u = d[d["E"].isna() | (d["YEAR"] < d["E"])].copy()
    k = u["YEAR"] - u["E"]
    leads = []
    for j in range(1, NLEAD + 1):
        u[f"lead{j}"] = (k == -j).astype(float)
        leads.append(f"lead{j}")
    u = u.set_index(["ISO", "YEAR"])
    r = PanelOLS(u[y], u[leads], entity_effects=True, time_effects=True).fit(cov_type="clustered",
                                                                              cluster_entity=True)
    b, V = r.params[leads].values, r.cov.loc[leads, leads].values
    stat = float(b @ np.linalg.pinv(V) @ b)
    return {"leads": {f"k-{j}": [round(float(r.params[f'lead{j}']), 4), round(float(r.std_errors[f'lead{j}']), 4)]
                      for j in range(1, NLEAD + 1)},
            "wald_chi2": round(stat, 3), "df": NLEAD, "p": round(float(stats.chi2.sf(stat, NLEAD)), 4)}


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(pc.OUT))
    ap.add_argument("--rai", default=str(pc.EXT / "rai_country-april-2021.xlsx"))
    ap.add_argument("--reps", type=int, default=999)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)

    p = pc.build_panel()
    sample = set(pc._sample(p)["ISO"])
    rai = read_rai(Path(a.rai))
    cov = pc.load_covariates()
    ge0 = cov[cov["YEAR"].between(1996, 1998)].groupby("ISO")["GE"].mean()
    lk = p[["ISO", "REGION"]].drop_duplicates("ISO").set_index("ISO")["REGION"]

    pm = pc._wb(pc.EXT / "wb_EN.ATM.PM25.MC.M3.json", "PM25")
    pm = pm[pm["YEAR"].between(1990, 2023)].assign(lnPM=lambda x: np.log(x["PM25"]))
    fs = p[["ISO", "YEAR", "SUBSHARE"]].dropna()

    results, et_rows = {"sample_countries": len(sample), "rai_countries_in_sample": int(rai["ISO"].isin(sample).groupby(rai["ISO"]).any().sum())}, []
    for label, thr in (("main", 1.0), ("large_reforms", 2.0)):
        ev = code_events(rai, sample, thr)
        if label == "main":
            ev.assign(GE0=ev["ISO"].map(ge0).round(3)).to_csv(out / "es_events.csv", index=False)
        keep = ev[ev["status"].isin(["treated", "never"])].set_index("ISO")["E"]
        tr = keep.dropna()
        groups = {"low": [i for i in tr.index if ge0.get(i, np.nan) < GE_CUT],
                  "high": [i for i in tr.index if ge0.get(i, np.nan) >= GE_CUT],
                  "below02": [i for i in tr.index if ge0.get(i, np.nan) < GE_CUT2]}
        info = {"threshold": thr, "treated": int(len(tr)), "never": int(keep.isna().sum()),
                "treated_low_ge": len(groups["low"]), "treated_high_ge": len(groups["high"]),
                "treated_ge_below_0.2": len(groups["below02"]),
                "event_years": {str(k): int(v) for k, v in tr.astype(int).items()}}
        rf = pm[pm["ISO"].isin(keep.index)].assign(E=lambda x: x["ISO"].map(keep), REGION=lambda x: x["ISO"].map(lk))
        fsd = fs[fs["ISO"].isin(keep.index)].assign(E=lambda x: x["ISO"].map(keep))
        # first stage: treated countries need an untreated observation of the share before E
        pre_fs = fsd[fsd["E"].notna() & (fsd["YEAR"] < fsd["E"])]["ISO"].unique()
        fsd = fsd[fsd["E"].isna() | fsd["ISO"].isin(pre_fs)]
        info["first_stage_treated"] = int(fsd.loc[fsd["E"].notna(), "ISO"].nunique())
        info["first_stage_never"] = int(fsd.loc[fsd["E"].isna(), "ISO"].nunique())
        # contribution rule (a): treated with >= 3 pre-years and an effect at k = 0..5
        pre_n = rf[rf["YEAR"] < rf["E"]].groupby("ISO").size()
        post_ok = rf[(rf["YEAR"] - rf["E"]).between(0, 5)].groupby("ISO").size()
        info["reduced_form_treated_rule_a"] = int(((pre_n.reindex(tr.index).fillna(0) >= 3) & (post_ok.reindex(tr.index).fillna(0) > 0)).sum())
        reps = a.reps
        info["first_stage"] = estimate(fsd, "SUBSHARE", groups, reps)
        info["first_stage_pretrend"] = pretrend(fsd, "SUBSHARE")
        info["reduced_form"] = estimate(rf, "lnPM", groups, reps)
        info["reduced_form_pretrend"] = pretrend(rf, "lnPM")
        if label == "main":
            info["reduced_form_region_year"] = estimate(rf.assign(RY=rf["REGION"] + "_" + rf["YEAR"].astype(str)),
                                                        "lnPM", groups, reps, time="RY")
            info["reduced_form_to_2018"] = estimate(rf[rf["YEAR"] <= 2018], "lnPM", groups, reps)
            for outc, key, pt in (("share", "first_stage", "first_stage_pretrend"),
                                  ("lnPM", "reduced_form", "reduced_form_pretrend")):
                for j in range(NLEAD, 0, -1):
                    b, s = info[pt]["leads"][f"k-{j}"]
                    et_rows.append(dict(outcome=outc, k=-j, est=b, se=s))
                for k in range(KMIN, KMAX + 1):
                    v = info[key][f"k{k}"]
                    et_rows.append(dict(outcome=outc, k=k, est=v["est"], se=v["se"]))
        results[label] = info
    (out / "es_results.json").write_text(json.dumps(results, indent=1), encoding="utf8")
    et = pd.DataFrame(et_rows)
    et.to_csv(out / "es_eventtime.csv", index=False)
    figure(et, out)
    print(json.dumps({k: v for k, v in results.items() if k != "main"}, indent=1)[:2000])
    m = results["main"]
    for key in ("first_stage", "reduced_form", "reduced_form_region_year", "reduced_form_to_2018"):
        print(key, {g: m[key][g] for g in ("att", "att_low", "att_high", "att_low_minus_high", "att_below02")},
              "n", m[key]["n_treated_contributing"])
    print("pretrend fs", m["first_stage_pretrend"]["p"], "rf", m["reduced_form_pretrend"]["p"])


def figure(et: pd.DataFrame, out: Path):
    plt = pc._plt()
    fig, axes = plt.subplots(1, 2, figsize=(pc.WIDTH_IN * 1.6, 2.6))
    for ax, (outc, lab) in zip(axes, (("share", "Subnational share of\nenvironmental spending"),
                                       ("lnPM", "ln PM2.5 exposure"))):
        d = et[et["outcome"] == outc]
        ax.axhline(0, color=pc.GRID, lw=1)
        ax.axvline(-0.5, color=pc.INK2, lw=0.8, ls="--")
        ax.errorbar(d["k"], d["est"], yerr=1.96 * d["se"], fmt="o", ms=3, color=pc.TIER_COLORS["T1"],
                    ecolor=pc.TIER_COLORS["T1"], elinewidth=0.8, capsize=0)
        ax.set_xticks(range(-5, 11, 5))
        ax.set_xlabel("Years since reform", fontsize=8)
        ax.set_ylabel(lab, fontsize=8)
        ax.tick_params(labelsize=8)
        pc._style(ax)
    fig.tight_layout()
    pc._save(fig, out / "es_figure.png")


if __name__ == "__main__":
    main()
