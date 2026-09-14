"""
congestion_model.py — ML-based Congestion Predictor
[ML PERSON] — Train a classifier to predict cell congestion probability.

Integration:
    predictor = CongestionPredictor()
    predictor.train_from_log("data/sim_log.json")
    prob = predictor.predict_congestion(cell=(5,3), t=time.time(), robots=[(x,y), ...])

    This probability is passed to astar() as a congestion_weight.
"""

import json
import time
import os
import numpy as np

try:
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    import joblib
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False
    print("[WARNING] scikit-learn not installed. CongestionPredictor will use heuristic fallback.")


MODEL_PATH = "ml/congestion_model.pkl"


class CongestionPredictor:
    """
    Predicts whether a cell will be congested at a given time.

    Input features per (cell, time, robots) query:
        - cell_x, cell_y           : cell coordinates
        - time_bucket              : int(t % 60) — 1-minute time slot
        - num_robots_within_2      : number of robots within Manhattan distance 2
        - num_robots_within_5      : number of robots within Manhattan distance 5
        - is_narrow_corridor       : 1 if cell is in known choke-point list

    Label:
        - 1 if more than 1 robot was in a 2-cell radius in training data
        - 0 otherwise
    """

    # Known narrow corridors / choke points (matches warehouse_layout.py)
    CHOKE_POINTS = {(3, 5), (6, 5), (9, 5), (3, 14), (6, 14), (9, 14)}

    def __init__(self):
        self.model = None
        self.is_trained = False

    # ------------------------------------------------------------------
    # Training
    # ------------------------------------------------------------------

    def train_from_log(self, log_path: str) -> None:
        """
        Load simulation log data and train the classifier.

        Args:
            log_path: Path to JSON Lines file produced by DataLogger.

        TODO [ML PERSON]: Implement training pipeline.
        Steps:
            1. Load log_path (each line is a JSON tick snapshot)
            2. For each tick: compute features for each cell that had a robot
            3. Label = 1 if >1 robot in 2-cell radius at that tick
            4. Call self._train(X, y)
        """
        if not SKLEARN_AVAILABLE:
            print("[WARN] sklearn not available, skipping training.")
            return

        if not os.path.exists(log_path):
            print(f"[WARN] Log file not found: {log_path}. Using heuristic mode.")
            return

        X, y = [], []
        with open(log_path) as f:
            for line in f:
                tick = json.loads(line.strip())
                # TODO [ML]: Extract features from each tick
                # tick format: {"t": float, "robots": [{"id": str, "x": int, "y": int}, ...]}
                robots_pos = [(r["x"], r["y"]) for r in tick.get("robots", [])]

                for robot in tick.get("robots", []):
                    cell = (robot["x"], robot["y"])
                    features = self._extract_features(cell, tick["t"], robots_pos)
                    label = self._is_congested(cell, robots_pos)
                    X.append(features)
                    y.append(label)

        if len(X) < 10:
            print("[WARN] Not enough training data. Using heuristic mode.")
            return

        self._train(np.array(X), np.array(y))

    def _train(self, X: np.ndarray, y: np.ndarray) -> None:
        """Fit the RandomForest classifier and save to disk."""
        if not SKLEARN_AVAILABLE:
            print("[ERROR] sklearn not available — cannot train.")
            return

        print(f"[ML] Training on {len(X)} samples...")
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=0.2, random_state=42
        )
        self.model = RandomForestClassifier(
            n_estimators=100,
            random_state=42,
            n_jobs=-1,     # use all CPU cores
            class_weight="balanced",  # handle imbalanced data
        )
        self.model.fit(X_train, y_train)

        # Report accuracy
        y_pred = self.model.predict(X_test)
        print("[ML] Congestion model training complete.")
        print(classification_report(y_test, y_pred, zero_division=0))

        # Save model for future use
        os.makedirs(os.path.dirname(MODEL_PATH), exist_ok=True)
        joblib.dump(self.model, MODEL_PATH)
        print(f"[ML] Model saved to {MODEL_PATH}")
        self.is_trained = True

    def load(self, path: str = MODEL_PATH) -> bool:
        """Load a previously trained model from disk."""
        if not SKLEARN_AVAILABLE:
            return False
        try:
            self.model = joblib.load(path)
            self.is_trained = True
            print(f"[INFO] Loaded congestion model from {path}")
            return True
        except FileNotFoundError:
            print(f"[INFO] No saved model at {path}. Will train fresh.")
            return False

    # ------------------------------------------------------------------
    # Prediction
    # ------------------------------------------------------------------

    def predict_congestion(
        self,
        cell: tuple[int, int],
        t: float,
        robot_positions: list[tuple[int, int]],
    ) -> float:
        """
        Return probability [0.0, 1.0] that `cell` will be congested.

        Called by:
            - astar() in pathfinder.py (as congestion_weights[cell])
            - TaskAllocator.compute_score()

        TODO [ML PERSON]: Implement prediction.
        If model is trained: use self.model.predict_proba(features)[0][1]
        If not trained: use heuristic fallback below.
        """
        if self.is_trained and self.model is not None:
            features = self._extract_features(cell, t, robot_positions)
            try:
                prob = self.model.predict_proba([features])[0][1]
                return float(prob)
            except Exception:
                pass

        # Heuristic fallback (works without ML model)
        return self._heuristic_congestion(cell, robot_positions)

    def _heuristic_congestion(
        self, cell: tuple, robot_positions: list[tuple]
    ) -> float:
        """Simple distance-based fallback if model is not trained."""
        nearby = sum(1 for pos in robot_positions if _manhattan(pos, cell) <= 2)
        choke_bonus = 0.3 if cell in self.CHOKE_POINTS else 0.0
        return min(1.0, nearby * 0.3 + choke_bonus)

    # ------------------------------------------------------------------
    # Feature engineering
    # ------------------------------------------------------------------

    def _extract_features(
        self,
        cell: tuple[int, int],
        t: float,
        robot_positions: list[tuple[int, int]],
    ) -> list[float]:
        """
        Build feature vector for a (cell, time, robots) query.

        TODO [ML PERSON]: Implement feature extraction.
        Features:
            [cell_x, cell_y, time_bucket, num_robots_within_2, num_robots_within_5, is_choke]
        """
        cell_x, cell_y = cell
        time_bucket = int(t % 60)
        within_2 = sum(1 for p in robot_positions if _manhattan(p, cell) <= 2)
        within_5 = sum(1 for p in robot_positions if _manhattan(p, cell) <= 5)
        is_choke = 1.0 if cell in self.CHOKE_POINTS else 0.0
        return [float(cell_x), float(cell_y), float(time_bucket),
                float(within_2), float(within_5), is_choke]

    @staticmethod
    def _is_congested(cell: tuple, robot_positions: list[tuple]) -> int:
        """Label: 1 if >1 robot is within 2 cells of `cell`."""
        nearby = sum(1 for pos in robot_positions if _manhattan(pos, cell) <= 2)
        return 1 if nearby > 1 else 0


def _manhattan(a: tuple, b: tuple) -> float:
    return abs(a[0] - b[0]) + abs(a[1] - b[1])
