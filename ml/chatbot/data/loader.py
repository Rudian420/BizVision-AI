"""
Synthetic chatbot corpus + golden-query loader.

Generates a 100-doc corpus spanning the five BizVision modules plus
"general" finance/strategy content, and a 25-query golden set with
labelled relevant doc-ids per query. This is the AS-005 ablation
fixture — every retrieval arm scores on the same queries against the
same corpus.

Same posture as `ml.sustainability.data.loader` and
`ml.forecasting.data.loader`: pure-Python generation, no pandas /
sklearn dependency, fed into frozen `Corpus` / `tuple[GoldenExample, ...]`
containers.
"""

from __future__ import annotations

from ml.chatbot.data.schema import Corpus, Document, GoldenExample, Query

# 20 docs × 5 modules = 100-doc corpus. Topics keep the wording rich
# enough that bag-of-words hashing has a real signal to retrieve on.

_RECRUITMENT_DOCS: tuple[tuple[str, str], ...] = (
    ("Hiring funnel basics", "A hiring funnel tracks candidates from sourcing through offer. Conversion rates at each stage drive recruiting efficiency."),
    ("Senior engineer compensation", "Senior software engineers command salaries between 140k and 220k depending on region, experience, and equity grants."),
    ("Diversity hiring practices", "Blind resume screening, structured interviews, and diverse hiring panels reduce bias in technical hiring decisions."),
    ("Time-to-hire benchmarks", "Median time-to-hire is 42 days for senior engineering roles and 28 days for junior roles."),
    ("Offer acceptance modeling", "Offer acceptance probability depends on compensation gap, role seniority, and competing offers."),
    ("Resume parsing pipeline", "Resume parsers extract structured data: skills, education, work history, certifications, and contact info."),
    ("Skills inventory analysis", "A skills matrix maps team competencies against role requirements to identify hiring gaps."),
    ("Recruitment marketing", "Employer branding through engineering blogs and conference talks boosts inbound applications."),
    ("Interview panel design", "A panel of three interviewers covering technical, behavioral, and culture screens balances calibration and bandwidth."),
    ("Onboarding 30-60-90 plan", "New-hire success correlates with structured 30/60/90 day plans, clear mentors, and weekly check-ins."),
    ("Junior pipeline strategy", "Investing in early-career hiring builds long-term engineering bench strength."),
    ("Hiring freeze playbook", "During hiring freezes, prioritize backfills for critical roles and pause exploratory pipelines."),
    ("Internal mobility programs", "Internal transfers fill 20-30% of senior roles in companies with mature mobility programs."),
    ("Recruiter capacity planning", "Each recruiter handles 4-6 active reqs at steady state; surge hiring needs contract augmentation."),
    ("Candidate scoring rubric", "Standardized rubrics with anchor examples reduce inter-rater variance in interview scoring."),
    ("Sourcing channel mix", "LinkedIn, employee referrals, and university partnerships cover most senior + junior pipelines."),
    ("Recruiting analytics dashboard", "Funnel metrics, time-to-fill, source effectiveness, and offer-acceptance rate are core KPIs."),
    ("Reference-check protocol", "Two professional references plus one peer reference is the standard final-stage check."),
    ("Counter-offer strategy", "Counter-offers should match competing offers on base + equity; signing bonuses smooth timing gaps."),
    ("Headcount budgeting cycle", "Annual headcount planning aligns with revenue forecasts and product roadmap commitments."),
)

_PRICING_DOCS: tuple[tuple[str, str], ...] = (
    ("Price elasticity primer", "Price elasticity of demand measures the percentage change in quantity demanded per 1% price change."),
    ("Monte Carlo revenue simulation", "Monte Carlo simulators sample demand from a distribution to estimate revenue confidence intervals."),
    ("Competitive pricing analysis", "Competitor price tracking enables dynamic positioning: premium, parity, or value tiers."),
    ("Optimal price discovery", "Optimal prices maximize an objective (revenue / profit / volume) subject to cost and demand constraints."),
    ("Demand curve fitting", "Fitting log-log demand curves yields constant-elasticity estimates; piecewise fits capture kinks."),
    ("Dynamic pricing strategy", "Dynamic pricing adjusts prices based on demand signals, inventory levels, and competitor moves."),
    ("Promotion ROI modeling", "Promotion lift decomposes into incremental volume, halo effects, and pull-forward cannibalization."),
    ("Cost-plus vs value pricing", "Cost-plus is simple but ignores willingness-to-pay; value-based pricing requires customer segmentation."),
    ("Bundling and unbundling", "Bundle discounts can capture customers with heterogeneous valuations across product attributes."),
    ("Price tiering for SaaS", "Three-tier pricing (good/better/best) anchors decoy effects and increases average revenue per user."),
    ("Surge pricing mechanics", "Surge multipliers balance supply and demand in real time; price caps limit consumer backlash."),
    ("Seasonality in pricing", "Seasonal demand peaks justify temporary price increases; underpricing leaves revenue on the table."),
    ("Subscription pricing renewals", "Renewal pricing should account for usage growth, competitive pressure, and switching costs."),
    ("B2B pricing negotiation", "Volume discounts and multi-year commitments are standard levers in enterprise pricing negotiations."),
    ("Reinforcement-learning pricing", "RL agents learn pricing policies from simulated or live revenue feedback under exploration constraints."),
    ("Price discrimination ethics", "First-degree price discrimination is rarely legal; second/third-degree variants are widely practiced."),
    ("SKU-level price optimization", "SKU-level optimization handles per-product elasticity, cross-elasticity, and inventory constraints."),
    ("Loss-leader strategy", "Loss leaders attract foot traffic; success requires high-margin attachment in the rest of the basket."),
    ("Price-fence strategy", "Price fences (loyalty, geography, time) segment willingness-to-pay without overt discrimination."),
    ("A/B price testing", "Randomized price tests on traffic slices yield clean elasticity estimates if pre-period drift is controlled."),
)

_FORECASTING_DOCS: tuple[tuple[str, str], ...] = (
    ("Time series decomposition", "Time series decompose into trend, seasonality, and residual components — additive or multiplicative."),
    ("Profit forecast horizon", "Short-horizon profit forecasts (30/60/90 days) drive cash management; long-horizon drives strategy."),
    ("Prophet model basics", "Prophet decomposes a series into trend + weekly + yearly seasonality with optional holiday regressors."),
    ("LSTM for time series", "LSTMs capture long-term dependencies but require careful regularization and sufficient training data."),
    ("Ensemble stacking", "Stacking combines forecasts from multiple models via a meta-learner trained on out-of-fold predictions."),
    ("Holt-Winters method", "Holt-Winters smooths level, trend, and seasonal components with three exponential smoothing parameters."),
    ("MAPE and RMSE metrics", "MAPE expresses error as a percentage; RMSE penalizes large errors quadratically in the original units."),
    ("Prediction intervals", "Prediction intervals quantify forecast uncertainty; Winkler score is a proper scoring rule for PIs."),
    ("Scenario forecasting", "Base / bull / bear scenarios condition the forecast on different macroeconomic assumptions."),
    ("Sensitivity analysis", "Tornado charts rank input drivers by their impact on forecast outcomes."),
    ("What-if simulation", "What-if simulations re-run a forecast with perturbed inputs to estimate the impact of business decisions."),
    ("Cross-module forecasting", "Cross-module signals (pricing changes, headcount growth) improve profit forecasts via integrated models."),
    ("Backtesting methodology", "Rolling-origin backtests preserve temporal order and report robust out-of-sample error estimates."),
    ("Seasonal pattern detection", "Autocorrelation and spectral analysis detect dominant seasonal periods in revenue series."),
    ("Recession-impact modeling", "Historical recession years are used as shock-test scenarios for forecast robustness checks."),
    ("Cohort revenue forecasting", "Cohort-based forecasting projects revenue per acquisition cohort separately for finer accuracy."),
    ("Outlier handling", "Outliers should be flagged but not discarded — they may indicate regime changes worth modeling."),
    ("Trend break detection", "Bayesian change-point detection identifies structural breaks in trend; informs model retraining."),
    ("Forecast bias correction", "Persistent forecast bias is corrected by adding the rolling mean residual to future predictions."),
    ("Forecast review cadence", "Monthly forecast reviews compare predictions against actuals; quarterly cycles re-estimate model fit."),
)

_SUSTAINABILITY_DOCS: tuple[tuple[str, str], ...] = (
    ("ESG composite scoring", "ESG composite scores aggregate environmental, social, and governance pillar scores into a 0-100 index."),
    ("Scope 1 emissions accounting", "Scope 1 emissions are direct emissions from owned sources: fleet, on-site combustion, fugitive gases."),
    ("Scope 2 emissions accounting", "Scope 2 emissions cover purchased energy: grid electricity, district heating, purchased steam."),
    ("Scope 3 supply chain emissions", "Scope 3 emissions span upstream and downstream value chain — typically the largest share."),
    ("Renewable energy procurement", "PPAs and on-site solar are the primary levers for reducing Scope 2 emissions at scale."),
    ("Carbon intensity metrics", "Carbon intensity per revenue normalizes emissions by company size for cross-company comparison."),
    ("Industry ESG benchmarks", "Manufacturing has 4x the carbon intensity of technology; logistics is highest at 300 tCO2e/$M."),
    ("Carbon offset markets", "Voluntary carbon markets offer offsets at $10-100/tCO2e; quality varies dramatically by project."),
    ("Multi-label ESG classifier", "Binary-relevance multi-label classifiers predict (E-strong, S-strong, G-strong) labels independently."),
    ("AIF360 fairness toolkit", "AIF360 implements bias detection metrics: disparate impact, equal opportunity, demographic parity."),
    ("EEOC four-fifths rule", "The four-fifths rule flags disparate impact when minority-group positive rate < 80% of majority's."),
    ("DEI program effectiveness", "Structured DEI metrics — pay equity, leadership diversity, promotion rates — drive social-pillar scores."),
    ("Board independence requirements", "Independent directors strengthen governance: target 60%+ board independence for SMEs."),
    ("Anti-corruption policies", "Formal anti-corruption codes plus annual training are governance-pillar table stakes."),
    ("Supply-chain ESG screening", "Supplier ESG audits reduce Scope 3 risk and surface upstream regulatory exposure."),
    ("Climate-risk financial disclosure", "TCFD recommendations structure climate-risk reporting around governance, strategy, risk, metrics."),
    ("Water stewardship programs", "Water-stressed regions require source water audits and reduction targets in water-intensive industries."),
    ("Biodiversity impact assessment", "Operations near critical habitats require biodiversity impact assessments and offset strategies."),
    ("Circular economy strategies", "Closed-loop materials recovery reduces both Scope 3 emissions and raw-material cost exposure."),
    ("ESG reporting frameworks", "GRI, SASB, and TCFD are the dominant ESG reporting frameworks; many companies use a hybrid."),
)

_GENERAL_DOCS: tuple[tuple[str, str], ...] = (
    ("Quarterly strategy review", "Quarterly business reviews align finance, operations, and product on the next quarter's priorities."),
    ("Cash runway calculation", "Cash runway = cash on hand / monthly burn rate; informs hiring and investment cadence."),
    ("Working capital management", "Working capital efficiency tracks DSO, DPO, and inventory days; cash conversion cycle is the headline."),
    ("Unit economics review", "Unit economics decompose contribution margin, CAC, LTV, and payback period per customer."),
    ("Board reporting cadence", "Board updates cover revenue, runway, hiring, product milestones, and emerging risks."),
    ("Strategic planning cycle", "Annual strategic planning sets multi-year priorities; quarterly OKRs operationalize them."),
    ("Competitive intelligence", "Tracking competitor moves — pricing, hiring, product launches — informs strategic positioning."),
    ("Capital allocation framework", "Capital allocation balances growth investments, M&A, share buybacks, and balance sheet strength."),
    ("Risk register review", "Top-risk reviews surface emerging operational, regulatory, and competitive risks for mitigation."),
    ("Executive dashboard design", "Executive dashboards prioritize 5-7 leading indicators over comprehensive but unfocused metric sprawls."),
    ("Annual budget process", "Annual budgets set departmental envelopes; rolling forecasts adjust as the year progresses."),
    ("Cross-functional alignment", "Joint OKRs and embedded business partners drive alignment across product, engineering, and GTM."),
    ("Vendor management policy", "Standardized vendor reviews cover SLA compliance, security posture, and spend trend."),
    ("Customer health scoring", "Customer health scores combine usage, NPS, and support ticket trends into a retention risk signal."),
    ("Pricing-and-packaging review", "Annual pricing-and-packaging reviews adjust tiers, discounts, and feature gates to revenue goals."),
    ("Talent calibration sessions", "Calibration sessions normalize performance ratings across teams to reduce manager bias."),
    ("Executive communication style", "Concise written updates with a single decision ask outperform unfocused status decks."),
    ("Metrics that misbehave", "Vanity metrics inflate without indicating health; pair every metric with a contrasting failure indicator."),
    ("Strategic narrative discipline", "A strong strategic narrative is testable, falsifiable, and connects to a small number of bets."),
    ("Decision-making framework", "Type-1 (irreversible) decisions warrant deep analysis; Type-2 (reversible) decisions favor speed."),
)

_MODULE_DOCS: dict[str, tuple[tuple[str, str], ...]] = {
    "recruitment": _RECRUITMENT_DOCS,
    "pricing": _PRICING_DOCS,
    "forecasting": _FORECASTING_DOCS,
    "sustainability": _SUSTAINABILITY_DOCS,
    "general": _GENERAL_DOCS,
}


def generate_synthetic_corpus() -> Corpus:
    """Return the deterministic 100-doc / 5-module corpus.

    The same call always returns the same doc IDs and ordering — the
    benchmark harness relies on this for reproducible scoring.
    """
    documents: list[Document] = []
    for module, docs in _MODULE_DOCS.items():
        for i, (title, content) in enumerate(docs):
            documents.append(
                Document(
                    doc_id=f"{module}-{i:02d}",
                    title=title,
                    content=content,
                    module=module,
                )
            )
    return Corpus(documents=tuple(documents))


# Golden-query set: each query references a small set of relevant doc IDs
# from the synthetic corpus. The benchmark harness measures whether the
# retriever surfaces these in its top-k.

_GOLDEN_QUERIES: tuple[tuple[str, str, str, tuple[str, ...]], ...] = (
    # (query_id, text, expected_module, relevant_doc_ids)
    ("q-rec-01", "How long does it take to hire a senior engineer?", "recruitment", ("recruitment-03", "recruitment-01", "recruitment-19")),
    ("q-rec-02", "What is a hiring funnel and how do I track it?", "recruitment", ("recruitment-00", "recruitment-16")),
    ("q-rec-03", "How do I reduce bias in technical interviews?", "recruitment", ("recruitment-02", "recruitment-14")),
    ("q-rec-04", "What is a structured onboarding plan?", "recruitment", ("recruitment-09",)),
    ("q-rec-05", "How should we plan headcount for next year?", "recruitment", ("recruitment-19", "recruitment-13")),
    ("q-prc-01", "How do I optimize a SaaS price tier?", "pricing", ("pricing-09", "pricing-12")),
    ("q-prc-02", "What is price elasticity of demand?", "pricing", ("pricing-00", "pricing-04")),
    ("q-prc-03", "How do Monte Carlo simulations help pricing?", "pricing", ("pricing-01",)),
    ("q-prc-04", "What is a loss leader pricing strategy?", "pricing", ("pricing-17",)),
    ("q-prc-05", "How do RL agents learn pricing policies?", "pricing", ("pricing-14",)),
    ("q-for-01", "What is Holt-Winters forecasting?", "forecasting", ("forecasting-05",)),
    ("q-for-02", "How do prediction intervals work in forecasts?", "forecasting", ("forecasting-07",)),
    ("q-for-03", "What is rolling-origin backtesting?", "forecasting", ("forecasting-12",)),
    ("q-for-04", "How do scenario forecasts work?", "forecasting", ("forecasting-08", "forecasting-10")),
    ("q-for-05", "What is MAPE in forecasting?", "forecasting", ("forecasting-06",)),
    ("q-esg-01", "How do I calculate Scope 3 emissions?", "sustainability", ("sustainability-03", "sustainability-14")),
    ("q-esg-02", "What is the four-fifths rule for fairness?", "sustainability", ("sustainability-10", "sustainability-09")),
    ("q-esg-03", "How does an ESG composite score work?", "sustainability", ("sustainability-00",)),
    ("q-esg-04", "What is carbon intensity per revenue?", "sustainability", ("sustainability-05", "sustainability-06")),
    ("q-esg-05", "How do I reduce Scope 2 emissions?", "sustainability", ("sustainability-04", "sustainability-02")),
    ("q-gen-01", "How do I calculate cash runway?", "general", ("general-01",)),
    ("q-gen-02", "What goes in an executive dashboard?", "general", ("general-09",)),
    ("q-gen-03", "How should board updates be structured?", "general", ("general-04", "general-16")),
    ("q-gen-04", "What is the difference between OKRs and budgets?", "general", ("general-10", "general-05")),
    ("q-gen-05", "How do customer health scores work?", "general", ("general-13",)),
)


def generate_golden_queries() -> tuple[GoldenExample, ...]:
    """Return the 25-query golden evaluation set."""
    examples: list[GoldenExample] = []
    for qid, text, module, relevant in _GOLDEN_QUERIES:
        examples.append(
            GoldenExample(
                query=Query(query_id=qid, text=text, include_modules=(module,)),
                relevant_doc_ids=relevant,
                expected_module=module,
            )
        )
    return tuple(examples)
