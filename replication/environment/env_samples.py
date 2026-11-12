"""Environmental-spending study, sample definitions for the zero shares.

A country is *central-only* when, in every year of its series, environmental protection (COFOG 05) is reported
for central government alone, so its subnational share is zero by construction.

A central-only country has a *coverage gap* when the COFOG data of the IMF GFS cover central government alone
for all ten functions in every year of its series: no state or local government value is reported for any
division. Its zero then reflects what the data cover, not what subnational governments spend. Countries without
subnational government are the exception: their zero is a true zero, and they keep a share of zero.

    import env_samples as ps
    gaps = ps.coverage_gaps(pc, base)   # pc = env_federalism module, base = pc._sample(pc.gaps_as_zero(panel))

The function re-derives the list from the data and checks it against COVERAGE_GAPS.
"""
import pandas as pd

# Countries without subnational government, whose zero share is a true zero.
# SGP: Singapore is a city-state with a single tier of government. "There is no local government in
#      Singapore" (Commonwealth Local Government Forum, Country profile 2017-18: Singapore,
#      https://www.clgf.org.uk/default/assets/File/Country_profiles/Singapore.pdf). The five Community
#      Development Councils are central bodies.
# Other small states among the central-only countries were checked and are not listed, because the sources
# record some form of local government: Tonga (elected district and town officers, CLGF country profile
# 2017-18) and Samoa (village fono under the Village Fono Act 1990 and urban authorities, CLGF country profile
# 2017-18). The Gulf states (Kuwait, Oman, Qatar) have municipal councils whose status as subnational
# government in the GFS sense was not confirmed, so they stay coverage gaps.
NO_SUBNATIONAL_GOVERNMENT = {"SGP": "Singapore, city-state without local government (CLGF country profile)"}

# The 36 central-only countries of the 108-country baseline (r5z_details.json, 3 November 2026).
CENTRAL_ONLY = ["AGO", "BFA", "BGD", "BHS", "BTN", "BWA", "CHL", "CIV", "COG", "DZA", "ECU", "EGY", "FJI", "GNQ",
                "HND", "KWT", "LBN", "MDG", "MHL", "MOZ", "NIC", "OMN", "PAK", "PHL", "PLW", "PSE", "QAT", "SGP",
                "SLB", "STP", "SYC", "TLS", "TON", "TUN", "TZA", "WSM"]
# Central-only countries with subnational values for another COFOG division: their zero is not a coverage gap.
OTHER_FUNCTION = ["BWA", "FJI", "TUN"]
# Coverage gaps: CENTRAL_ONLY minus OTHER_FUNCTION minus NO_SUBNATIONAL_GOVERNMENT (32 countries).
COVERAGE_GAPS = sorted(set(CENTRAL_ONLY) - set(OTHER_FUNCTION) - set(NO_SUBNATIONAL_GOVERNMENT))
assert len(COVERAGE_GAPS) == 32


def coverage_gaps(pc, base: pd.DataFrame, check: bool = True) -> list:
    """Coverage gaps re-derived from the harmonised data of env_federalism (pc) and the sample `base`."""
    central_only = sorted(base.loc[base["NOSUB"] == 1, "ISO"].unique())
    h = pd.read_csv(pc.HARMONISED, dtype={"DIV": str}, usecols=["ISO", "DIV", "EVER_SG", "EVER_LG"])
    other = h[h["DIV"] != "05"].groupby("ISO")[["EVER_SG", "EVER_LG"]].any().any(axis=1)
    other_fn = {i for i in central_only if bool(other.get(i, False))}
    gaps = sorted(set(central_only) - other_fn - set(NO_SUBNATIONAL_GOVERNMENT))
    if check:
        assert central_only == CENTRAL_ONLY, sorted(set(central_only) ^ set(CENTRAL_ONLY))
        assert gaps == COVERAGE_GAPS, sorted(set(gaps) ^ set(COVERAGE_GAPS))
    return gaps
