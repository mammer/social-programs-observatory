"""Models on the household feature table built by features.py.

  1. PCA on household characteristics
  2. Household typology: k-means on the PCA scores
  3. PCA + k-means at area level
  4. KNN and logistic regression predicting "very vulnerable", with and without the area,
     to measure how much the rating depends on where it was made rather than on the household
  5. Random forest permutation importance

Input: features.csv (one row per assessed household, numeric features only).
Usage: python models.py features.csv output_dir
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score, balanced_accuracy_score, confusion_matrix
from sklearn.model_selection import StratifiedKFold, cross_val_predict, GridSearchCV
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.compose import ColumnTransformer
from sklearn.metrics import silhouette_score

SEED = 42
FEATURES = ["age", "female", "children", "household", "n_disabled", "n_chronic",
            "informal", "no_work", "no_coverage", "basic_cover", "widowed", "divorced_abandoned",
            "single", "health_disability", "health_chronic", "health_elderly", "head"]
LABELS = {
    "age": "Age", "female": "Woman", "children": "Children", "household": "Household size",
    "n_disabled": "Disabled members", "n_chronic": "Chronically ill members",
    "informal": "Informal work", "no_work": "No work", "no_coverage": "No health cover",
    "basic_cover": "Basic health cover", "widowed": "Widowed", "divorced_abandoned": "Divorced / abandoned",
    "single": "Single", "health_disability": "Has disability", "health_chronic": "Chronic / serious illness",
    "health_elderly": "Elderly", "head": "Head of household",
}


def main(src, out):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(src)
    df = df[df["target"].notna()].reset_index(drop=True)
    y = (df["target"] == "very_vulnerable").astype(int).to_numpy()
    res = {"n_households": int(len(df)), "share_very_vulnerable": float(y.mean())}

    # ---- 1. PCA on households -------------------------------------------
    prep = make_pipeline(SimpleImputer(strategy="median"), StandardScaler())
    X = prep.fit_transform(df[FEATURES])
    pca = PCA(n_components=6, random_state=SEED).fit(X)
    scores = pca.transform(X)
    res["pca_variance"] = [round(float(v), 4) for v in pca.explained_variance_ratio_]
    load = pd.DataFrame(pca.components_[:2].T * np.sqrt(pca.explained_variance_[:2]),
                        index=FEATURES, columns=["pc1", "pc2"])  # correlations variable/axis
    load.insert(0, "variable", [LABELS[f] for f in FEATURES])
    load.round(3).to_csv(out / "pca_loadings.csv", index=False)
    pd.DataFrame({"component": [f"PC{i+1}" for i in range(6)],
                  "variance_pct": (pca.explained_variance_ratio_ * 100).round(2),
                  "cumulative_pct": (np.cumsum(pca.explained_variance_ratio_) * 100).round(2)}
                 ).to_csv(out / "pca_variance.csv", index=False)

    # ---- 2. Household typology: k-means on first 4 PCA axes ---------------
    Z = scores[:, :4]
    sil = {}
    for k in range(3, 8):
        km = KMeans(n_clusters=k, n_init=10, random_state=SEED).fit(Z)
        sil[k] = silhouette_score(Z, km.labels_, sample_size=5000, random_state=SEED)
    k_best = max(sil, key=sil.get)
    res["kmeans_silhouette"] = {str(k): round(float(v), 3) for k, v in sil.items()}
    res["kmeans_k"] = int(k_best)
    km = KMeans(n_clusters=k_best, n_init=10, random_state=SEED).fit(Z)
    df["cluster"] = km.labels_
    raw = SimpleImputer(strategy="median").fit_transform(df[FEATURES])
    prof = pd.DataFrame(raw, columns=FEATURES).assign(cluster=km.labels_, vv=y,
                                                      aid_any=df["aid_any"])
    g = prof.groupby("cluster").mean()
    g["households"] = prof.groupby("cluster").size()
    g = g.sort_values("households", ascending=False).reset_index()
    g["cluster"] = [f"Group {chr(65 + i)}" for i in range(len(g))]
    g.round(3).to_csv(out / "household_clusters.csv", index=False)

    # ---- 3. Area-level PCA + k-means ----------------------------------------
    cm = df.groupby("area").agg(households=("target", "size"))
    cm = cm[cm["households"] >= 100]
    agg = df[df["area"].isin(cm.index)].assign(vv=y[df["area"].isin(cm.index).to_numpy()])
    cf = agg.groupby("area")[["female", "household", "informal", "no_work", "no_coverage",
                              "widowed", "health_disability", "health_chronic", "health_elderly",
                              "aid_any", "vv"]].mean()
    Xc = StandardScaler().fit_transform(cf.fillna(cf.mean()))
    pc = PCA(n_components=2, random_state=SEED).fit(Xc)
    sc = pc.transform(Xc)
    kc = KMeans(n_clusters=3, n_init=20, random_state=SEED).fit(sc)
    comm = cf.round(3).assign(pc1=sc[:, 0].round(3), pc2=sc[:, 1].round(3),
                              group=[f"Type {i + 1}" for i in kc.labels_],
                              households=cm.loc[cf.index, "households"]).reset_index()
    comm.to_csv(out / "area_pca.csv", index=False)
    res["area_pca_variance"] = [round(float(v), 4) for v in pc.explained_variance_ratio_]

    # ---- 4. KNN: is "very vulnerable" predictable from the household? ----
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    knn = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                        KNeighborsClassifier(weights="distance"))
    grid = GridSearchCV(knn, {"kneighborsclassifier__n_neighbors": [5, 11, 21, 31, 51, 75]},
                        scoring="roc_auc", cv=cv, n_jobs=-1).fit(df[FEATURES], y)
    k_knn = grid.best_params_["kneighborsclassifier__n_neighbors"]
    knn.set_params(kneighborsclassifier__n_neighbors=k_knn)

    def evaluate(model, Xd, name):
        p = cross_val_predict(model, Xd, y, cv=cv, method="predict_proba")[:, 1]
        thr = y.mean()  # classify at the base rate, so both classes count
        pred = (p >= thr).astype(int)
        tn, fp, fn, tp = confusion_matrix(y, pred).ravel()
        return {"model": name, "auc": round(roc_auc_score(y, p), 3),
                "balanced_accuracy": round(balanced_accuracy_score(y, pred), 3),
                "recall_very_vulnerable": round(tp / (tp + fn), 3),
                "precision_very_vulnerable": round(tp / (tp + fp), 3),
                "tp": int(tp), "fp": int(fp), "fn": int(fn), "tn": int(tn)}

    rows = [evaluate(knn, df[FEATURES], f"KNN (k={k_knn}), household only")]
    with_c = FEATURES + ["area"]
    ct = ColumnTransformer([
        ("num", make_pipeline(SimpleImputer(strategy="median"), StandardScaler()), FEATURES),
        ("area", make_pipeline(SimpleImputer(strategy="constant", fill_value="unknown"),
                              OneHotEncoder(handle_unknown="ignore")), ["area"])])
    knn_c = make_pipeline(ct, KNeighborsClassifier(n_neighbors=k_knn, weights="distance"))
    rows.append(evaluate(knn_c, df[with_c], f"KNN (k={k_knn}), household + area"))
    logit = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(),
                          LogisticRegression(max_iter=2000, class_weight="balanced"))
    rows.append(evaluate(logit, df[FEATURES], "Logistic regression, household only"))
    logit_c = make_pipeline(ct, LogisticRegression(max_iter=2000, class_weight="balanced"))
    rows.append(evaluate(logit_c, df[with_c], "Logistic regression, household + area"))
    pd.DataFrame(rows).to_csv(out / "knn_results.csv", index=False)

    # ---- 5. Random forest: which household factors drive the rating? -----
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.inspection import permutation_importance
    from sklearn.model_selection import train_test_split
    Xi = SimpleImputer(strategy="median").fit_transform(df[FEATURES])
    Xtr, Xte, ytr, yte = train_test_split(Xi, y, test_size=0.25, stratify=y, random_state=SEED)
    rf = RandomForestClassifier(n_estimators=300, min_samples_leaf=20, class_weight="balanced",
                                n_jobs=-1, random_state=SEED).fit(Xtr, ytr)
    res["rf_auc_test"] = round(roc_auc_score(yte, rf.predict_proba(Xte)[:, 1]), 3)
    pi = permutation_importance(rf, Xte, yte, scoring="roc_auc", n_repeats=5, random_state=SEED, n_jobs=-1)
    imp = pd.DataFrame({"variable": [LABELS[f] for f in FEATURES], "key": FEATURES,
                        "importance": pi.importances_mean.round(4)}).sort_values("importance", ascending=False)
    imp.to_csv(out / "rf_importance.csv", index=False)
    res["knn_best_k"] = int(k_knn)
    res["models"] = rows

    (out / "summary.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    print(json.dumps(res, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
