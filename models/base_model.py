from abc import ABC, abstractmethod
import numpy as np

class BaseModel(ABC):
    def __init__(self):
        self.model = None
    
    @abstractmethod
    def train(self, X, y):
        pass
    
    @abstractmethod
    def predict(self, X):
        pass
    
    def evaluate(self, X, y):
        predictions = self.predict(X)
        return self._calculate_metrics(y, predictions)
    
    def _calculate_metrics(self, y_true, y_pred):
        return {
            'accuracy': np.mean(y_true == y_pred)
        }
