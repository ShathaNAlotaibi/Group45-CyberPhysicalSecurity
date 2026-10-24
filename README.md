# Hybrid Machine Reasoning for Cyber-Physical Security

**Group 45 · Intelligent Reasoning Systems · 25 October 2026**

A proof-of-concept framework that connects cyber activity and physical-access events to assess scenario risk and present supporting evidence to security analysts.

**[Project Report](ProjectReport/IRS-PM-2026-10-25-GRP-45-CyberPhysicalSecurity-Group-Report.pdf)** · **[Project Videos](Video)** · **[System Code](SystemCode)** · **[Dashboard](https://pixel-perfect-match-8226.lovable.app)**

## 1. Project Overview

Physical security and cybersecurity records are often monitored separately. This can obscure relationships between events involving the same user or device. This project brings both domains together through shared identities and event timing, then combines predictive classification with explicit security rules.

| Component | Role in the framework |
| --- | --- |
| **Knowledge Graph** | Neo4j connects users, devices, locations, physical-access events and cyber events, supplying linked facts for contextual reasoning. |
| **Machine learning** | Decision Tree, Random Forest and Gradient Boosting predict Low, Medium or High scenario risk using cyber-only, physical-only and combined features. |
| **Symbolic reasoning** | Eleven rules identify security conditions and record the evidence supporting each assessment. |
| **Hybrid integration** | The final assessment retains the higher risk level when ML and symbolic predictions disagree. |
| **LLM explanations** | `gpt-4o-mini` explains the supplied assessment using triggered rules and contextual evidence. It does not assign a new risk category. |

An analyst dashboard presents predictions, rules, relationships and explanations for investigation. The framework supports human review, with the final decision remaining with the analyst.

## 2. Dataset and Evaluation

The project uses **800 synthetic cyber-physical scenarios**, each assigned an overall Low, Medium or High reference label. The same labels and test records are retained across all ML experiments, allowing a consistent comparison as the features and classifier change.

| Setting | Configuration |
| --- | --- |
| Classifiers | Decision Tree, Random Forest and Gradient Boosting |
| Feature sets | Cyber-only: 7 features; physical-only: 5 features; combined: 13 features |
| Combined feature set | Cyber and physical predictors plus the time gap between linked events |
| Total ML experiments | 9 |
| Training and test split | Shared stratified 80/20 split: 640 training and 160 test scenarios |
| Model tuning | Five-fold stratified cross-validation within the training set |
| Model selection | Mean cross-validation macro F1 |

Identifiers, raw timestamps, risk scores and severity fields are excluded from ML inputs. Accuracy, macro precision, macro recall, macro F1, High-risk recall, confusion matrices and feature importance support evaluation and interpretation.

### Main results

| Method | Test accuracy | Macro F1 | High-risk recall |
| --- | ---: | ---: | ---: |
| Combined-feature Random Forest | **98.13%** | **98.30%** | **100.00%** |
| Symbolic reasoning | 96.25% | 94.83% | 96.15% |
| Final ML–symbolic assessment | 96.25% | 95.30% | **100.00%** |

Combining cyber and physical features improves test accuracy for all three ML classifiers. The selected Random Forest correctly classifies **157 of 160 scenarios** and detects all **26 High-risk test cases**. Its three errors occur between Low and Medium risk.

The final ML–symbolic assessment preserves High-risk recall but has lower overall accuracy than Random Forest alone. Its contribution is the integration of predictive results with explicit rule evidence and conservative risk prioritisation. The combined-feature ML model and final ML–symbolic assessment are distinct stages of the framework.

Explanations are generated for all 160 test scenarios. Manual review of 30 explanations reports a 100% pass rate for risk consistency, evidence faithfulness and absence of unsupported claims, and a 66.67% pass rate for clarity. These findings apply to the reviewed sample.

## 3. Team and Contributions

| Member | Student ID | Main contributions |
| --- | --- | --- |
| **Shatha Alotaibi** | A0350688R | Developed and tuned the nine ML experiments; evaluated classifiers and feature sets; analysed errors and feature importance; exported scenario-aligned predictions; documented ML methodology and results; wrote the overall project conclusion. |
| **Shouq Alqarni** | A0352233N | Developed and prepared the datasets; implemented preprocessing, integration and derived features; contributed to reference labelling; documented the introduction and dataset methodology. |
| **Maha Alasmari** | A0356640A | Designed and implemented the Neo4j Knowledge Graph; integrated prepared data and developed Cypher queries; prepared the literature review and Knowledge Graph methodology. |
| **Reem Alqarawy** | A0353748R | Developed the 11 symbolic rules; integrated KG evidence and ML predictions; implemented and evaluated risk fusion; generated and manually evaluated LLM explanations; documented the symbolic, hybrid and LLM components. |

Group details and the repository URL are also provided in [member-github.txt](member-github.txt).

## 4. Project Videos

Video materials are provided in the **[Video folder](Video)**.

| Video | Contents | Filename |
| --- | --- | --- |
| **Final presentation** | Team presentation covering the project problem, methodology, framework, evaluation and findings. | `IRS-PM-2026-10-25-GRP-45-CyberPhysicalSecurity-final-presentation.mp4` |
| **Promotion video** | Introduction to the project problem, proposed solution and benefits. | `IRS-PM-2026-10-25-GRP-45-CyberPhysicalSecurity-promotion.mp4` |

If a video is provided as a ZIP archive, download and extract it before playback. The filenames above identify the two video types for the final submission.

## 5. Repository Contents

| Location | Contents |
| --- | --- |
| [SystemCode/Dataset](SystemCode/Dataset) | Raw data, preprocessing notebook and prepared dataset. |
| [SystemCode/KnowledgeGraph](SystemCode/KnowledgeGraph) | Knowledge Graph materials. |
| [SystemCode/MachineLearning](SystemCode/MachineLearning) | ML notebook and Python script, input datasets, feature sets and model comparison results. |
| [SystemCode/SymbolicReasoning_HybridReasoning_LLM](SystemCode/SymbolicReasoning_HybridReasoning_LLM) | Reasoning notebook, symbolic and hybrid results, explanations, evaluation outputs and scenario mappings. |
| [ProjectReport](ProjectReport) | Final group report. |
| [Video](Video) | Promotion video and final presentation materials. |
| [member-github.txt](member-github.txt) | Group members, student IDs and repository URL. |

## 6. Getting Started

### Run the notebooks

1. Download the repository using **Code → Download ZIP**, then extract it.
2. Review the dataset preparation notebook in `SystemCode/Dataset` for the input preparation workflow.
3. Open `Hybrid_ML_for_Cyber_Physical_Security_G45 (1).ipynb` from `SystemCode/MachineLearning` in Google Colab. Upload the input files requested by the notebook and run the cells in order.
4. Review the model comparisons, confusion matrices, feature importances and prediction outputs.
5. Open `Member4_Symbolic_Hybrid_LLM_v2.ipynb` from `SystemCode/SymbolicReasoning_HybridReasoning_LLM`. Supply the KG context, relationship evidence and ML predictions as specified in the notebook, then run the reasoning and integration workflow.

Preserve input filenames and scenario identifiers when passing outputs between components. Regenerating LLM explanations requires OpenAI API access. Configure credentials privately and do not commit them to the repository.

### Explore the dashboard

Open **https://pixel-perfect-match-8226.lovable.app**.

| Page | Purpose |
| --- | --- |
| Security Overview | Review risk summaries, priority scenarios and rule patterns. |
| High-Risk Events | Browse scenarios and open their investigation details. |
| Disagreement Review | Examine differences between ML and symbolic predictions and manage review status. |
| Knowledge Graph | Explore entities and relationships associated with a scenario. |
| Analytics & Evaluation | Compare methods and review explanation-quality results. |

Select a scenario to inspect its component predictions, final risk, triggered rules, KG evidence and explanation. A time-critical flag indicates a qualifying cross-domain condition with an event gap of ten minutes or less; it supports prioritisation rather than confirming an incident.

The dashboard displays evaluated project scenarios rather than a live security feed. Review statuses are stored in the current browser and are not shared across users or devices. **Appendix C of the report provides the illustrated dashboard user guide.**

## 7. Project Report

The **[final group report](ProjectReport/IRS-PM-2026-10-25-GRP-45-CyberPhysicalSecurity-Group-Report.pdf)** documents the background and literature review, dataset preparation, Knowledge Graph design, ML experiments, symbolic rules, hybrid integration, LLM evaluation and project conclusions. Its appendices include the project proposal, course-functionality mapping and dashboard user guide.

## 8. Scope and Limitations

This master's course project is a proof of concept evaluated on synthetic data. Reported metrics measure agreement with the assigned reference labels and do not establish real-world threat-detection performance. The final fusion policy may increase false-positive risk escalations, and explanation evaluation covers only 30 manually reviewed cases.

The framework provides evidence and risk assessments to support investigation. It does not replace the analyst's judgement.

---

**Project repository:** https://github.com/ShathaNAlotaibi/Group45-CyberPhysicalSecurity
