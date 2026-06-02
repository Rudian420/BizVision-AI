"""
BizVision AI — Recruitment Intelligence

Research-grade, production-ready candidate-ranking module.

Public surface (everything below is stable and consumed by the backend
recruitment service and the thesis evaluation scripts):

    data           — schemas + reproducible loader
    parsers        — multi-format resume → CandidateRecord
    features       — structured tabular features for boosting rankers
    embeddings     — SBERT / TF-IDF encoders + content-hash cache
    models         — Random, TF-IDF, BM25, SBERT, XGBoost, Ensemble
    evaluation     — pure-numpy metrics + benchmark harness
    explainability — SHAP, LIME, deterministic narrative + bias decomposition (RC-002)
    fairness       — intersectional group audit + post-hoc mitigation
    reproducibility — seed control + env capture
    registry       — MLflow Model Registry helpers
    search         — pgvector candidate index
    copilot        — recruiter conversational LLM layer
    training       — full pipeline + ablation runner
"""
