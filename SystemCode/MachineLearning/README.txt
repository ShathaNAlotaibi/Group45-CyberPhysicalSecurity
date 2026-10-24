GROUP 45 UPDATED ML SUBMISSION

Open Hybrid_ML_for_Cyber_Physical_Security_G45.ipynb in Google Colab.
Upload RawDataset(2).xlsx and Merged Dataset.csv when requested.
The notebook checks the merged records against raw facts and creates Risk_Labels.csv.
It uses the supplied risk_level exactly; it does not infer or invent a score formula.
The labels are shared by all nine experiments. Only predictor columns change.
Score, severity, IDs and raw timestamps are excluded from predictors.
Cyber-only, physical-only and hybrid tables show the exact inputs plus identifiers for traceability.
Identifiers in these exports are not used by the classifiers.
The time gap is hybrid-only. After-hours features are derived separately by domain.
80% training and 20% testing, with identical records across all experiments.
Five-fold training CV selects parameters by macro F1. Test results are exploratory.
Labels have changed from the earlier dataset; do not use the old metrics/report as current results.
Blue figures are generated in the notebook and saved in its runtime results folder.
The comparison file in this package contains results from the updated data.

A local run uses: python ml_classification.py (from this folder).
Dependencies: pandas, numpy, scikit-learn, matplotlib, openpyxl, joblib.
The data are synthetic. Labeling protocol validity and real-world detection are not established by these metrics.
