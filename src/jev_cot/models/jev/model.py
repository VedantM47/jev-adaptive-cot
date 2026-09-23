"""
jev_cot.models.jev.model
===========================
JEV — the compact classifier that replaces LLM self-gating (FR-08).
XGBoost-based, with 3 size variants (S/M/L) controlled by config.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from jev_cot.controller.actions import Action
from jev_cot.controller.state import ControllerState

# Feature order is fixed so a saved model and a live ControllerState always agree.
FEATURE_NAMES: tuple[str, ...] = (
    "num_steps_taken",
    "num_retrievals",
    "num_computations",
    "num_branches",
    "evidence_count",
    "has_required_evidence",
    "distinct_documents_seen",
    "elapsed_seconds",
)

ACTIONS: tuple[str, ...] = tuple(a.value for a in Action)

_SIZE_PARAMS: dict[str, dict[str, Any]] = {
    "S": {"n_estimators": 20, "max_depth": 2},
    "M": {"n_estimators": 60, "max_depth": 4},
    "L": {"n_estimators": 150, "max_depth": 6},
}


def state_to_vector(state: ControllerState) -> np.ndarray:
    """Turn a ControllerState into the fixed-order feature vector JEV consumes."""
    features = state.to_feature_dict()
    return np.array([features[name] for name in FEATURE_NAMES], dtype=np.float32)


@dataclass
class JEVModel:
    """A trained (or trainable) JEV classifier of a given size variant."""

    size: str = "M"
    _booster: Any = field(default=None, repr=False)
    _calibrator: Any = field(default=None, repr=False)
    _classes: tuple[str, ...] = field(default=(), repr=False)

    def __post_init__(self) -> None:
        if self.size not in _SIZE_PARAMS:
            raise ValueError(
                f"Unknown JEV size {self.size!r}; expected one of {list(_SIZE_PARAMS)}"
            )

    def fit(self, X: np.ndarray, y: list[str]) -> None:
        """
        Train the classifier on feature matrix X and string action labels y.

        A tiny seed dataset rarely has all 6 Action values represented in
        every split, so this trains on whatever subset of classes actually
        appears. This XGBoost version's sklearn wrapper does NOT do its own
        string-label encoding (it raises unless y is already 0..n-1 ints),
        so labels are encoded here — sorted alphabetically for a stable,
        reproducible mapping — and ``self._classes`` records the mapping so
        predict()/predict_proba() can decode back to Action strings.
        """
        import xgboost as xgb

        classes = tuple(sorted(set(y)))
        y_idx = np.array([classes.index(label) for label in y])

        params = _SIZE_PARAMS[self.size]
        n_classes = len(classes)
        objective = "binary:logistic" if n_classes <= 2 else "multi:softprob"
        kwargs: dict[str, Any] = {
            "n_estimators": params["n_estimators"],
            "max_depth": params["max_depth"],
            "objective": objective,
            "eval_metric": "logloss" if n_classes <= 2 else "mlogloss",
            "random_state": 42,
        }
        if n_classes > 2:
            kwargs["num_class"] = n_classes
        self._booster = xgb.XGBClassifier(**kwargs)
        self._booster.fit(X, y_idx)
        self._classes = classes

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """Return class probabilities, shape (n_samples, len(self.classes))."""
        if self._booster is None:
            raise RuntimeError("JEVModel is not fitted — call fit() or load() first")
        if self._calibrator is not None:
            return self._calibrator.predict_proba(X)  # type: ignore[no-any-return]
        return self._booster.predict_proba(X)  # type: ignore[no-any-return]

    def calibrate(self, X_calib: np.ndarray, y_calib: list[str]) -> None:
        """Fit an isotonic calibrator on top of the already-trained booster (held-out split)."""
        from sklearn.calibration import CalibratedClassifierCV
        from sklearn.frozen import FrozenEstimator

        if self._booster is None:
            raise RuntimeError("Cannot calibrate an unfitted JEVModel")
        # Same integer encoding fit() used — self._classes is the source of truth.
        # FrozenEstimator is this sklearn version's replacement for cv="prefit"
        # (removed) — it tells CalibratedClassifierCV to calibrate the already-fit
        # booster directly rather than refitting on each CV fold.
        y_idx = np.array([self._classes.index(label) for label in y_calib])
        calibrator = CalibratedClassifierCV(FrozenEstimator(self._booster), method="isotonic")
        calibrator.fit(X_calib, y_idx)
        self._calibrator = calibrator

    def predict(self, state: ControllerState) -> tuple[Action, float]:
        """Predict the next action + confidence for one ControllerState."""
        vector = state_to_vector(state).reshape(1, -1)
        proba = self.predict_proba(vector)[0]
        best_idx = int(np.argmax(proba))
        return Action(self._classes[best_idx]), float(proba[best_idx])

    @property
    def classes(self) -> tuple[str, ...]:
        """The action labels this model was trained on, in predict_proba column order."""
        return self._classes

    def num_parameters(self) -> int:
        """Rough parameter count: total number of tree leaves across the ensemble."""
        if self._booster is None:
            return 0
        booster = self._booster.get_booster()
        dump = booster.get_dump()
        return sum(tree.count("leaf") for tree in dump)

    def save(self, path: str | Path) -> None:
        """Save the model to *path* (a directory): booster.json + meta.json (+ calibrator.pkl)."""
        if self._booster is None:
            raise RuntimeError("Cannot save an unfitted JEVModel")
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        self._booster.save_model(str(p / "booster.json"))
        (p / "meta.json").write_text(
            json.dumps(
                {
                    "size": self.size,
                    "feature_names": list(FEATURE_NAMES),
                    "classes": list(self._classes),
                    "calibrated": self._calibrator is not None,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        if self._calibrator is not None:
            import joblib

            joblib.dump(self._calibrator, p / "calibrator.pkl")

    @classmethod
    def load(cls, path: str | Path) -> JEVModel:
        """Load a model previously saved with :meth:`save`."""
        import xgboost as xgb

        p = Path(path)
        meta = json.loads((p / "meta.json").read_text(encoding="utf-8"))
        model = cls(size=meta["size"])
        booster = xgb.XGBClassifier()
        booster.load_model(str(p / "booster.json"))
        model._booster = booster
        model._classes = tuple(meta["classes"])
        if meta.get("calibrated") and (p / "calibrator.pkl").exists():
            import joblib

            model._calibrator = joblib.load(p / "calibrator.pkl")
        return model
