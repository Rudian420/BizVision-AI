"""
BizVision AI — Smart Pricing Advisor

Research-grade, production-ready pricing-optimisation module.

Public surface (mirrors `ml.recruitment` — same layout, same conventions
— see ADR-025 for why the modules share a shape):

    data           — Product / PriceObservation / PricingScenario schemas + loader
    features       — structured price-context features for boosting demand models
    models         — DemandModel + PricingPolicy interfaces; baselines, elasticity,
                     LightGBM demand, Monte Carlo simulator, PPO RL agent
    evaluation     — pure-numpy revenue/MAPE/Sharpe/VaR metrics + benchmark harness
    explainability — SHAP for LightGBM demand + deterministic narrative generator
    reproducibility — seed control + env capture for MLflow tags
    registry       — MLflow Model Registry helpers (smart-pricing-policy)
    copilot        — pricing advisory LLM layer (structured JSON I/O)
    training       — full pipeline + AS-002 ablation runner

Research contribution: RC-003 (Explainable RL pricing — post-hoc SHAP +
Monte Carlo uncertainty). Ablation: AS-002 (Constant · CompetitorMatch ·
Elasticity-optimal · LightGBM-grid · PPO-RL).

Single-attribute pricing decisions don't carry the same intersectional-
fairness risk as recruitment (RC-002 / `ml.recruitment.fairness`); the
fairness layer is deliberately omitted here.
"""
