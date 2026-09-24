QIEA: pop 20 x gens 30 = 600 fitness evaluations per (regime, instrument)
genome: 11 genes x 8 bits = 88 bits (2^88 points)
per fold: 600 x 9 regimes x 8 instruments = 43200 evaluations
staged per fold: 9 ParamSets (1 per regime, best holdout E[R] across 8 instruments)
module on/off combinations: 2^6 = 64; numeric knobs in system_config.yaml: 100 (+55 instruments.yaml)

fitness window per fold: 2.00 years of calendar; a regime sees only its own bars
| N (effective independent trials) | E[max z] | noise-max annual SR on 2y full | on 2y x 20% regime share | MinBTL yrs @SR0.5 | MinBTL yrs @SR1.0 |
|---|---|---|---|---|---|
| 1 | 0.00 | 0.00 | 0.00 | 0.0 | 0.0 |
| 10 | 1.57 | 1.11 | 2.49 | 9.9 | 2.5 |
| 100 | 2.53 | 1.79 | 4.00 | 25.6 | 6.4 |
| 1000 | 3.26 | 2.30 | 5.15 | 42.4 | 10.6 |
| 10000 | 3.86 | 2.73 | 6.11 | 59.6 | 14.9 |
| 43200 | 4.20 | 2.97 | 6.65 | 70.7 | 17.7 |

Data available: 12 dev years x 8 instruments. At rho~0.4 common factor the 8 series are worth ~ 2.1 independent series (n/(1+(n-1)rho)), i.e. ~25 instrument-years
Graded DSR (tests/backtest/harness.py:217-218) counts n_trials = #surviving champions (+min), at most 72 per fold, vs 43200 evaluations actually searched per fold (ratio 600x).
